import re
import unicodedata

from app.rag.detector import QualityResult
from app.shared.llm import clean_text_with_llm


def normalize(text: str) -> str:
    """Basic text normalization: encoding, whitespace, control chars."""
    # Fix common mojibake
    text = text.replace("â€™", "'").replace("â€œ", '"').replace("â€", '"')
    text = text.replace("Ã©", "é").replace("Ã¨", "è").replace("Ã ", "à")

    # Remove control characters (keep newlines and tabs)
    text = "".join(
        c for c in text
        if unicodedata.category(c) not in ("Cc", "Cs") or c in ("\n", "\t", "\r")
    )

    # Collapse excessive blank lines (max 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of spaces/tabs on a line
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Strip lines that are pure noise (only symbols, no alphanumeric)
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        alnum = sum(1 for c in stripped if c.isalnum())
        if alnum / len(stripped) >= 0.2:  # at least 20% alphanumeric
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


async def clean(text: str, quality: QualityResult) -> str:
    """
    Clean extracted text. Applies progressively stronger cleaning
    based on the quality score:
      score > 0.7 → regex normalize only
      score 0.4–0.7 → aggressive normalize
      score < 0.4 → LLM-assisted cleaning
    """
    text = normalize(text)

    if quality.score >= 0.7:
        return text

    if quality.score >= 0.4:
        # Aggressive: also remove lines with < 3 words (likely extraction artefacts)
        lines = [
            l for l in text.splitlines()
            if not l.strip() or len(l.split()) >= 3
        ]
        return "\n".join(lines)

    # Score < 0.4 → LLM cleaning pass (batched in 4k chunks to control cost)
    chunks = _split_for_cleaning(text, max_chars=4000)
    cleaned_chunks = []
    for chunk in chunks:
        cleaned_chunks.append(await clean_text_with_llm(chunk))
    return "\n\n".join(cleaned_chunks)


def _split_for_cleaning(text: str, max_chars: int) -> list[str]:
    """Split text into chunks for LLM cleaning without breaking mid-sentence."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, max_chars)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    return chunks
