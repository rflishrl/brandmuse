import base64

from langchain_core.messages import HumanMessage

from app.core.config import get_settings
from app.core.logging import logger
from app.providers.llm import get_llm

settings = get_settings()

VISUAL_OCR_SYSTEM_PROMPT = (
    "You are an expert brand identity analyst. Examine this visual brand guideline diagram. "
    "Transcribe all visual rules, color names, hex codes, typography specs, "
    "logo clearspace requirements, and DOs/DONTs visible in the image. "
    "Be direct, concise, and strictly factual. Do not add conversational filler."
)


async def extract_text_from_image_bytes(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Transcribe brand specifications from raster image bytes using multimodal LLM."""
    if not (settings.GEMINI_API_KEY or settings.OPENAI_API_KEY):
        return ""

    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        message = HumanMessage(
            content=[
                {"type": "text", "text": VISUAL_OCR_SYSTEM_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        )

        llm = get_llm(streaming=False, temperature=0.1, max_tokens=600)
        res = await llm.ainvoke([message])
        content = res.content if isinstance(res.content, str) else str(res.content)
        return content.strip()
    except Exception as exc:
        logger.warning("Visual OCR extraction skipped or failed: %s", exc)
        return ""
