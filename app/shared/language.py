from app.config import get_settings

try:
    from langdetect import detect, LangDetectException
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

settings = get_settings()


def detect_language(text: str) -> str:
    if not _HAS_LANGDETECT or len(text.strip()) < 10:
        return "en"
    try:
        return detect(text)
    except Exception:
        return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    if source_lang == "en":
        return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=source_lang, target="en").translate(text)
    except Exception:
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    if target_lang == "en":
        return text
    try:
        from deep_translator import GoogleTranslator
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
