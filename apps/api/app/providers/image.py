import asyncio
import base64
import io
import ipaddress
import re
import socket
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image, ImageDraw, ImageOps

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.http import get_http_client

settings = get_settings()

MAX_FULL_EDGE_PX = 1920
MAX_THUMB_EDGE_PX = 480
WEBP_FULL_QUALITY = 80
WEBP_THUMB_QUALITY = 78
MAX_PROVIDER_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB hard cap
MAX_DOWNLOAD_REDIRECTS = 2
ALLOWED_IMAGE_DOWNLOAD_HOSTS: tuple[str, ...] = ("replicate.delivery",)

DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, typography, logo, blurry, low resolution, deformed, bad anatomy, "
    "disfigured, celebrity portrait, real living people names, oversaturated, neon glare"
)

ASPECT_RATIO_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "9:16": (576, 1024),
    "16:9": (1024, 576),
}


def build_negative_prompt(custom_negative: str | None = None) -> str:
    """Combine base safety negative prompt with dynamic brand restrictions."""
    if not custom_negative or not custom_negative.strip():
        return DEFAULT_NEGATIVE_PROMPT
    return f"{DEFAULT_NEGATIVE_PROMPT}, {custom_negative.strip()}"


PROMPT_BLOCKLIST = [
    "nsfw",
    "nude",
    "naked",
    "porn",
    "blood",
    "gore",
    "violence",
    "hate",
    "hitler",
    "nazi",
    "terrorist",
    "weapon",
    "kill",
    "assassinate",
]


def moderate_prompt(prompt: str) -> None:
    """Enforce basic safety moderation on image prompt using word boundaries."""
    for bad_word in PROMPT_BLOCKLIST:
        pattern = rf"\b{re.escape(bad_word)}\b"
        if re.search(pattern, prompt, re.IGNORECASE):
            raise APIError(
                code="PROMPT_MODERATION_FAILED",
                message=f"Image prompt contains forbidden or unsafe term: '{bad_word}'.",
                status_code=400,
            )


def encode_webp_variants(image_bytes: bytes) -> tuple[bytes, bytes]:
    """Decode raw image bytes and encode (full_webp, thumb_webp) stripping metadata."""
    with Image.open(io.BytesIO(image_bytes)) as opened:
        transposed = ImageOps.exif_transpose(opened)
        has_alpha = transposed.mode in ("RGBA", "LA") or (
            transposed.mode == "P" and "transparency" in transposed.info
        )
        target_mode = "RGBA" if has_alpha else "RGB"
        base_img = transposed.convert(target_mode)

    full_img = base_img.copy()
    if max(full_img.size) > MAX_FULL_EDGE_PX:
        full_img.thumbnail((MAX_FULL_EDGE_PX, MAX_FULL_EDGE_PX), Image.Resampling.LANCZOS)
    full_buf = io.BytesIO()
    full_img.save(full_buf, format="WEBP", quality=WEBP_FULL_QUALITY, method=4)

    thumb_img = base_img.copy()
    if max(thumb_img.size) > MAX_THUMB_EDGE_PX:
        thumb_img.thumbnail((MAX_THUMB_EDGE_PX, MAX_THUMB_EDGE_PX), Image.Resampling.LANCZOS)
    thumb_buf = io.BytesIO()
    thumb_img.save(thumb_buf, format="WEBP", quality=WEBP_THUMB_QUALITY, method=4)

    return full_buf.getvalue(), thumb_buf.getvalue()


def _is_allowed_provider_host(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    return any(
        host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_IMAGE_DOWNLOAD_HOSTS
    )


def _resolve_host_ips(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos if info[4]]


def validate_image_download_url(url: str) -> str:
    """Enforce HTTPS, allowlisted host, and public IP checks to prevent SSRF."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message="Provider image URL must use HTTPS.",
            status_code=502,
        )
    if parts.username or parts.password or not parts.hostname:
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message="Provider image URL contains invalid host or credentials.",
            status_code=502,
        )
    if parts.port not in (None, 443):
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message="Provider image URL port is not allowed.",
            status_code=502,
        )

    hostname = parts.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message="Direct IP addresses are not allowed for provider image downloads.",
            status_code=502,
        )

    if not _is_allowed_provider_host(hostname):
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message=f"Provider image host '{hostname}' is not in allowlist.",
            status_code=502,
        )

    try:
        resolved_ips = _resolve_host_ips(hostname)
    except OSError as exc:
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message=f"Failed to resolve provider image host '{hostname}'.",
            status_code=502,
        ) from exc

    if not resolved_ips:
        raise APIError(
            code="UNSAFE_IMAGE_URL",
            message=f"Provider image host '{hostname}' resolved to no addresses.",
            status_code=502,
        )

    for raw_ip in resolved_ips:
        ip_obj = ipaddress.ip_address(raw_ip)
        if not ip_obj.is_global:
            raise APIError(
                code="UNSAFE_IMAGE_URL",
                message="Provider image URL resolved to a non-public IP address.",
                status_code=502,
            )

    return url


async def download_provider_image(
    url: str,
    client: httpx.AsyncClient | None = None,
    max_bytes: int = MAX_PROVIDER_DOWNLOAD_BYTES,
) -> bytes:
    """Safely stream-download generated image bytes from an allowlisted provider URL."""
    http_client = client or get_http_client()
    # Offload synchronous DNS resolution inside validate_image_download_url off the event loop
    current_url = await asyncio.to_thread(validate_image_download_url, url)

    for _ in range(MAX_DOWNLOAD_REDIRECTS + 1):
        try:
            async with http_client.stream(
                "GET",
                current_url,
                timeout=30.0,
                follow_redirects=False,
            ) as res:
                if res.status_code in (301, 302, 303, 307, 308):
                    location = res.headers.get("location")
                    if not location:
                        raise APIError(
                            code="IMAGE_GENERATION_FAILED",
                            message="Provider image download returned redirect without Location.",
                            status_code=502,
                        )
                    current_url = await asyncio.to_thread(
                        validate_image_download_url, urljoin(current_url, location)
                    )
                    continue

                if res.status_code != 200:
                    raise APIError(
                        code="IMAGE_GENERATION_FAILED",
                        message=f"Provider image download failed with status {res.status_code}.",
                        status_code=502,
                    )

                content_length = res.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise APIError(
                        code="IMAGE_TOO_LARGE",
                        message="Provider image exceeds maximum allowed download size.",
                        status_code=502,
                    )

                buf = bytearray()
                async for chunk in res.aiter_bytes(chunk_size=64 * 1024):
                    buf.extend(chunk)
                    if len(buf) > max_bytes:
                        raise APIError(
                            code="IMAGE_TOO_LARGE",
                            message="Provider image exceeds maximum allowed download size.",
                            status_code=502,
                        )
                return bytes(buf)
        except httpx.HTTPError as exc:
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Provider image download failed ({type(exc).__name__}): {exc}",
                status_code=502,
            ) from exc

    raise APIError(
        code="UNSAFE_IMAGE_URL",
        message="Provider image download exceeded maximum redirect limit.",
        status_code=502,
    )


class BaseImageProvider(ABC):
    """Abstract interface for Stable Diffusion image generation APIs."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
    ) -> bytes:
        """Generate an image from prompt and return raw image bytes (PNG/JPEG/WebP)."""
        pass


class StabilityImageProvider(BaseImageProvider):
    """Stability AI SDXL 1.0 generation via official REST API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.STABILITY_API_KEY
        self.engine_id = "stable-diffusion-xl-1024-v1-0"

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
    ) -> bytes:
        moderate_prompt(prompt)

        if not self.api_key:
            raise APIError(
                code="MISSING_API_KEY",
                message="STABILITY_API_KEY is not configured.",
                status_code=500,
            )

        api_url = f"https://api.stability.ai/v1/generation/{self.engine_id}/text-to-image"
        w, h = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (1024, 1024))
        neg = build_negative_prompt(negative_prompt)

        payload = {
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
                {"text": neg, "weight": -1.0},
            ],
            "cfg_scale": 7.0,
            "height": h,
            "width": w,
            "samples": 1,
            "steps": 30,
        }

        client = get_http_client()
        try:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Stability AI request failed ({type(exc).__name__}): {exc}",
                status_code=502,
            ) from exc

        if response.status_code != 200:
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Stability AI image generation failed: {response.text}",
                status_code=502,
            )

        data: dict[str, Any] = response.json()
        artifacts = data.get("artifacts", [])
        if not artifacts:
            raise APIError(
                code="NO_IMAGE_RETURNED",
                message="Stability AI did not return an image artifact.",
                status_code=502,
            )

        b64_image = artifacts[0]["base64"]
        return base64.b64decode(b64_image)


class ReplicateImageProvider(BaseImageProvider):
    """Replicate SDXL image generation provider."""

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or settings.REPLICATE_API_TOKEN

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
    ) -> bytes:
        moderate_prompt(prompt)

        if not self.api_token:
            raise APIError(
                code="MISSING_API_KEY",
                message="REPLICATE_API_TOKEN is not configured.",
                status_code=500,
            )

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait",
        }

        w, h = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (1024, 1024))
        neg = build_negative_prompt(negative_prompt)

        create_url = "https://api.replicate.com/v1/models/stability-ai/sdxl/predictions"
        payload = {
            "input": {
                "prompt": prompt,
                "negative_prompt": neg,
                "width": w,
                "height": h,
            }
        }

        client = get_http_client()
        try:
            res = await client.post(create_url, headers=headers, json=payload, timeout=90.0)
        except httpx.HTTPError as exc:
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Replicate request failed ({type(exc).__name__}): {exc}",
                status_code=502,
            ) from exc
        if res.status_code not in (200, 201):
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Replicate API error: {res.text}",
                status_code=502,
            )

        prediction = res.json()
        poll_url = prediction["urls"]["get"]

        attempts = 0
        max_attempts = 45
        while prediction.get("status") not in ("succeeded", "failed", "canceled"):
            attempts += 1
            if attempts > max_attempts:
                raise APIError(
                    code="IMAGE_GENERATION_TIMEOUT",
                    message="Replicate generation timed out waiting for completion.",
                    status_code=504,
                )
            await asyncio.sleep(2)
            try:
                poll_res = await client.get(poll_url, headers=headers, timeout=30.0)
            except httpx.HTTPError as exc:
                raise APIError(
                    code="IMAGE_GENERATION_FAILED",
                    message=f"Replicate polling failed ({type(exc).__name__}): {exc}",
                    status_code=502,
                ) from exc
            if poll_res.status_code != 200:
                raise APIError(
                    code="IMAGE_GENERATION_FAILED",
                    message=f"Replicate polling error ({poll_res.status_code}): {poll_res.text}",
                    status_code=502,
                )
            prediction = poll_res.json()

        if prediction.get("status") != "succeeded":
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Replicate generation failed: {prediction.get('error')}",
                status_code=502,
            )

        output_urls = prediction.get("output", [])
        if not output_urls:
            raise APIError(
                code="NO_IMAGE_RETURNED",
                message="Replicate returned no image output.",
                status_code=502,
            )

        return await download_provider_image(str(output_urls[0]), client=client)


class MockImageProvider(BaseImageProvider):
    """Mock image provider for testing and offline development."""

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
    ) -> bytes:
        moderate_prompt(prompt)
        _ = negative_prompt

        w, h = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (1024, 1024))

        img = Image.new("RGB", (w, h), color=(34, 43, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([30, 30, w - 30, h - 30], outline=(192, 108, 71), width=4)
        draw.text((w // 2 - 110, h // 2 - 10), f"BrandMuse ({aspect_ratio})", fill=(246, 244, 238))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def get_image_provider(name: str | None = None) -> BaseImageProvider:
    """Factory to retrieve configured image generation provider."""
    provider_name = (name or settings.IMAGE_PROVIDER).lower()
    if provider_name == "stability":
        return StabilityImageProvider()
    elif provider_name == "replicate":
        return ReplicateImageProvider()
    elif provider_name in ("mock", "test"):
        return MockImageProvider()
    else:
        raise ValueError(f"Unsupported image provider: {provider_name}")
