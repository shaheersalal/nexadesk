from starlette.concurrency import run_in_threadpool

from app.config import get_settings

try:
    from langdetect import detect, LangDetectException
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

settings = get_settings()


def _single_language() -> str | None:
    """The only supported language, when exactly one is configured."""
    langs = [x.strip() for x in (settings.SUPPORTED_LANGUAGES or "").split(",") if x.strip()]
    return langs[0] if len(langs) == 1 else None


def detect_language(text: str) -> str:
    """
    Detect the language of `text`, or short-circuit when only one is supported.

    The short-circuit is not just a saving, it is a correctness fix. langdetect
    is unreliable on the short strings people actually type — "2 bed London"
    readily comes back as Afrikaans or Dutch — and a wrong answer here does not
    fail quietly: translate_to_english then makes a BLOCKING HTTP call to
    translate English into English through a bogus source language, adding a
    network round trip to the request and mangling the text on the way through.

    With SUPPORTED_LANGUAGES set to a single language there is nothing to
    detect, so neither the CPU-bound detection nor the translation hop runs.
    """
    only = _single_language()
    if only:
        return only
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

    Blocking. Prefer `anormalize_for_llm` from async code.
    """
    lang = detect_language(text)
    english = translate_to_english(text, lang)
    return english, lang


# ── Async wrappers ────────────────────────────────────────────────────────────
#
# GoogleTranslator performs a blocking HTTP request, and langdetect is CPU-bound.
# Both were being called directly from async request handlers, stalling the event
# loop for every other in-flight request on the worker (AUDIT.md M3). These
# wrappers push the work to the threadpool; the sync versions above are kept for
# any non-async caller.


async def anormalize_for_llm(text: str) -> tuple[str, str]:
    """
    Async form of normalize_for_llm — safe to call from a request handler.

    Skips the threadpool entirely in the single-language case: there is no
    detection to run and no translation to make, so the hop is pure overhead on
    the critical path of every message.
    """
    only = _single_language()
    if only:
        return text, only
    return await run_in_threadpool(normalize_for_llm, text)


async def atranslate_from_english(text: str, target_lang: str) -> str:
    """Async form of translate_from_english."""
    if target_lang == "en":
        return text  # No network call needed — skip the threadpool hop
    return await run_in_threadpool(translate_from_english, text, target_lang)
