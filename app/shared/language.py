from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator

from app.config import get_settings

settings = get_settings()


def detect_language(text: str) -> str:
    """Detect language code from text. Falls back to 'en'."""
    try:
        if len(text.strip()) < 10:
            return "en"
        return detect(text)
    except LangDetectException:
        return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """Translate text to English. Returns original if already English."""
    if source_lang == "en":
        return text
    try:
        return GoogleTranslator(source=source_lang, target="en").translate(text)
    except Exception:
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """Translate response from English to target language."""
    if target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception:
        return text


def normalize_for_llm(text: str) -> tuple[str, str]:
    """
    Detect language, translate to English for LLM processing.
    Returns (english_text, detected_language_code).
    """
    lang = detect_language(text)
    english = translate_to_english(text, lang)
    return english, lang
