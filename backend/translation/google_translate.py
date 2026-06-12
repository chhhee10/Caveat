"""
Translation module — Google Translate for all languages.
IndicTrans2 can be plugged in later as a higher-quality alternative for Indian languages.

Get a free API key (500K chars/month):
  https://console.cloud.google.com → Enable Cloud Translation API → Create Credentials
"""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

# ISO 639-1 codes for languages supported in the UI
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "bho": "Bhojpuri",
    "mai": "Maithili",
    "or": "Odia",
    "as": "Assamese",
    "kn": "Kannada",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
}

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"


async def detect_language(text: str) -> str:
    """
    Detect the language of the given text using Google Translate API.
    Returns ISO 639-1 language code (e.g. 'en', 'hi', 'kn').
    Falls back to 'en' on error.
    """
    if not settings.GOOGLE_TRANSLATE_API_KEY:
        logger.warning("GOOGLE_TRANSLATE_API_KEY not set — skipping language detection")
        return "en"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{GOOGLE_TRANSLATE_URL}/detect",
                params={"key": settings.GOOGLE_TRANSLATE_API_KEY},
                json={"q": text[:1000]},  # small sample is enough
            )
            data = response.json()
            detected = data["data"]["detections"][0][0]["language"]
            logger.info(f"Language detected: {detected}")
            return detected
    except Exception as e:
        logger.warning(f"Language detection failed ({e}), defaulting to 'en'")
        return "en"


async def translate_to_english(text: str, source_lang: str = "auto") -> str:
    """
    Translate text to English.
    Returns original text unchanged if source is already English or if API unavailable.
    """
    if source_lang == "en" or source_lang.startswith("en"):
        return text

    if not settings.GOOGLE_TRANSLATE_API_KEY:
        logger.warning("GOOGLE_TRANSLATE_API_KEY not set — returning original text")
        return text

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TRANSLATE_URL,
                params={"key": settings.GOOGLE_TRANSLATE_API_KEY},
                json={
                    "q": text,
                    "target": "en",
                    "source": source_lang if source_lang != "auto" else None,
                    "format": "text",
                },
            )
            data = response.json()
            translated = data["data"]["translations"][0]["translatedText"]
            logger.info(f"Translated {source_lang} → en ({len(translated)} chars)")
            return translated
    except Exception as e:
        logger.error(f"Translation to English failed: {e}")
        return text  # graceful fallback: use original text


async def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate English text to the target language.
    Returns original text if target is English or API unavailable.
    """
    if target_lang == "en" or target_lang.startswith("en"):
        return text

    if not settings.GOOGLE_TRANSLATE_API_KEY:
        logger.warning("GOOGLE_TRANSLATE_API_KEY not set — returning English text")
        return text

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TRANSLATE_URL,
                params={"key": settings.GOOGLE_TRANSLATE_API_KEY},
                json={
                    "q": text,
                    "source": "en",
                    "target": target_lang,
                    "format": "text",
                },
            )
            data = response.json()
            translated = data["data"]["translations"][0]["translatedText"]
            return translated
    except Exception as e:
        logger.error(f"Translation en → {target_lang} failed: {e}")
        return text


async def translate_bulk_english(texts: list[str], target_lang: str) -> list[str]:
    """Translate a list of strings in a single API call."""
    if not texts: return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TRANSLATE_URL,
                params={"key": settings.GOOGLE_TRANSLATE_API_KEY},
                json={"q": texts, "source": "en", "target": target_lang, "format": "text"}
            )
            data = response.json()
            return [t["translatedText"] for t in data["data"]["translations"]]
    except Exception as e:
        logger.error(f"Bulk translation failed: {e}")
        return texts

async def translate_json(data: dict | list | str, target_lang: str, skip_keys: set = None) -> dict | list | str:
    """
    Translates all string values in a JSON structure in a SINGLE bulk API request to avoid latency bottlenecks.
    """
    if target_lang == "en" or target_lang.startswith("en") or not settings.GOOGLE_TRANSLATE_API_KEY:
        return data

    if skip_keys is None:
        skip_keys = {"clause_type", "risk_level", "document_type", "dark_pattern_type", "dark_pattern", "safe_to_sign", "overall_risk_score", "red_flags_count", "dark_patterns_count", "confidence"}

    strings_to_translate = []

    def extract_strings(obj, current_key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k not in skip_keys:
                    extract_strings(v, k)
        elif isinstance(obj, list):
            for item in obj:
                extract_strings(item, current_key)
        elif isinstance(obj, str):
            if len(obj) >= 2 and not obj.startswith("http"):
                strings_to_translate.append(obj)

    extract_strings(data)

    if not strings_to_translate:
        return data

    translated_strings = await translate_bulk_english(strings_to_translate, target_lang)
    trans_iter = iter(translated_strings)

    def inject_strings(obj, current_key=None):
        if isinstance(obj, dict):
            return {k: (v if k in skip_keys else inject_strings(v, k)) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [inject_strings(item, current_key) for item in obj]
        elif isinstance(obj, str):
            if len(obj) >= 2 and not obj.startswith("http"):
                return next(trans_iter, obj)
            return obj
        return obj

    return inject_strings(data)
