import asyncio
import base64
import io
import re
from abc import ABC, abstractmethod
from typing import Any

from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.http import get_http_client

settings = get_settings()

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

# Basic safety blocklist for prompt moderation
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


class BaseImageProvider(ABC):
    """Abstract interface for Stable Diffusion image generation APIs."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
    ) -> bytes:
        """Generate an image from prompt and return raw image bytes (PNG/JPEG)."""
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

        # Replicate SDXL official model endpoint
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
        res = await client.post(create_url, headers=headers, json=payload, timeout=90.0)
        if res.status_code not in (200, 201):
            raise APIError(
                code="IMAGE_GENERATION_FAILED",
                message=f"Replicate API error: {res.text}",
                status_code=502,
            )

        prediction = res.json()
        poll_url = prediction["urls"]["get"]

        # Poll for completion with bounded attempts
        attempts = 0
        max_attempts = 45  # 90 seconds max polling
        while prediction.get("status") not in ("succeeded", "failed", "canceled"):
            attempts += 1
            if attempts > max_attempts:
                raise APIError(
                    code="IMAGE_GENERATION_TIMEOUT",
                    message="Replicate generation timed out waiting for completion.",
                    status_code=504,
                )
            await asyncio.sleep(2)
            poll_res = await client.get(poll_url, headers=headers, timeout=30.0)
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

        # Download output image bytes
        image_res = await client.get(output_urls[0], timeout=30.0)
        return image_res.content


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

        # Generate a clean synthetic image matching requested aspect ratio
        img = Image.new("RGB", (w, h), color=(34, 43, 39))  # Deep Forest Slate
        draw = ImageDraw.Draw(img)
        # Terracotta accent border
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
