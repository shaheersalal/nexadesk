import re
import unicodedata
from dataclasses import dataclass, field

try:
    import magic
    _HAS_MAGIC = True
except ImportError:
    _HAS_MAGIC = False


MIME_TO_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/csv": "csv",
    "text/plain": "txt",
    "text/html": "html",
    "image/jpeg": "image",
    "image/png": "image",
    "image/tiff": "image",
    "image/webp": "image",
}


@dataclass
class InputMeta:
    mime: str
    file_type: str  # simplified: pdf|docx|xlsx|csv|txt|html|image|unknown
    is_scanned_pdf: bool = False
    detected_language: str = "en"


@dataclass
class QualityResult:
    score: float  # 0.0 – 1.0
    flags: list[str] = field(default_factory=list)

    @property
    def needs_llm_clean(self) -> bool:
        return self.score < 0.4


def detect_file_type(file_bytes: bytes, filename: str) -> InputMeta:
    """Detect file type using magic bytes first, extension as fallback."""
    mime = "application/octet-stream"
    if _HAS_MAGIC:
        try:
            mime = magic.from_buffer(file_bytes[:2048], mime=True)
        except Exception:
            pass

    if mime == "application/octet-stream":
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "txt": "text/plain",
            "md": "text/plain",
            "markdown": "text/plain",
            "html": "text/html",
            "htm": "text/html",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "ppt": "application/vnd.ms-powerpoint",
        }
        mime = ext_map.get(ext, "application/octet-stream")

    file_type = MIME_TO_TYPE.get(mime, "unknown")
    is_scanned = file_type == "pdf" and not _has_extractable_text(file_bytes)

    return InputMeta(mime=mime, file_type=file_type, is_scanned_pdf=is_scanned)


def _has_extractable_text(pdf_bytes: bytes) -> bool:
    """Quick heuristic: real PDFs have /Font resources."""
    try:
        sample = pdf_bytes[:8192].decode("latin-1", errors="ignore")
        return "/Font" in sample or "/Contents" in sample
    except Exception:
        return False


def assess_quality(text: str) -> QualityResult:
    """Score extracted text quality 0.0–1.0. Lower = noisier."""
    if not text or not text.strip():
        return QualityResult(score=0.0, flags=["empty"])

    score = 1.0
    flags = []

    # Noise: non-printable / non-alphanumeric characters
    total = len(text)
    noise_chars = sum(
        1 for c in text
        if unicodedata.category(c) in ("Cc", "Cs") and c not in ("\n", "\t", "\r")
    )
    noise_ratio = noise_chars / total
    if noise_ratio > 0.05:
        score -= min(0.4, noise_ratio * 4)
        flags.append("noisy")

    # Encoding issues: replacement characters or obvious mojibake
    if "�" in text or "Ã©" in text or "â€™" in text:
        score -= 0.3
        flags.append("encoding_issues")

    # Sparsity: too many single-char lines
    lines = [l for l in text.splitlines() if l.strip()]
    if lines:
        short_ratio = sum(1 for l in lines if len(l.strip()) <= 2) / len(lines)
        if short_ratio > 0.4:
            score -= 0.2
            flags.append("sparse")

    # Duplication: many repeated lines
    if lines:
        unique_ratio = len(set(lines)) / len(lines)
        if unique_ratio < 0.6:
            score -= 0.1
            flags.append("duplicates")

    # Too short to be useful
    word_count = len(text.split())
    if word_count < 10:
        score -= 0.2
        flags.append("too_short")

    return QualityResult(score=max(0.0, score), flags=flags)
