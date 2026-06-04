import re
from dataclasses import dataclass, field

import tiktoken

TOKENIZER = tiktoken.get_encoding("cl100k_base")
CHUNK_SIZE = 512       # target tokens
CHUNK_OVERLAP = 64     # overlap tokens
MIN_CHUNK_TOKENS = 50  # merge chunks below this


@dataclass
class Chunk:
    text: str
    chunk_type: str = "paragraph"   # paragraph | section | table | list | fixed
    section_title: str = ""
    chunk_index: int = 0

    @property
    def token_count(self) -> int:
        return len(TOKENIZER.encode(self.text))


def smart_chunk(text: str) -> list[Chunk]:
    """
    Strategy cascade:
      1. Section-based (headings detected)
      2. Paragraph-based
      3. Fixed-size fallback
    Tables and list blocks are always kept as atomic chunks.
    """
    # Extract and remove tables first
    text, table_chunks = _extract_tables(text)

    # Detect structure
    if _has_headings(text):
        chunks = _chunk_by_sections(text)
    elif _has_paragraphs(text):
        chunks = _chunk_by_paragraphs(text)
    else:
        chunks = _chunk_fixed(text)

    # Merge tiny chunks
    chunks = _merge_short(chunks)

    # Combine with table chunks
    all_chunks = chunks + table_chunks

    # Assign sequential indices
    for i, c in enumerate(all_chunks):
        c.chunk_index = i

    return all_chunks


# ── Heading detection ─────────────────────────────────────────────────────────

_HEADING_RE = re.compile(
    r"^(?:#{1,4}\s+.+|[A-Z][A-Z\s]{3,}:|[A-Z].{0,60}(?:\n[-=]{3,}))",
    re.MULTILINE,
)


def _has_headings(text: str) -> bool:
    return bool(_HEADING_RE.search(text))


def _has_paragraphs(text: str) -> bool:
    return "\n\n" in text


# ── Section-based chunking ────────────────────────────────────────────────────

def _chunk_by_sections(text: str) -> list[Chunk]:
    parts = _HEADING_RE.split(text)
    headings = _HEADING_RE.findall(text)

    chunks = []
    current_title = ""
    for i, part in enumerate(parts):
        if i < len(headings):
            current_title = headings[i].strip()
        if not part.strip():
            continue
        for sub in _sub_chunk(part.strip(), current_title, "section"):
            chunks.append(sub)
    return chunks


# ── Paragraph-based chunking ──────────────────────────────────────────────────

def _chunk_by_paragraphs(text: str) -> list[Chunk]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    buffer = ""
    for para in paras:
        candidate = (buffer + "\n\n" + para).strip() if buffer else para
        if _token_count(candidate) <= CHUNK_SIZE:
            buffer = candidate
        else:
            if buffer:
                chunks.append(Chunk(text=buffer, chunk_type="paragraph"))
            buffer = para
    if buffer:
        chunks.append(Chunk(text=buffer, chunk_type="paragraph"))
    return chunks


# ── Fixed-size fallback ───────────────────────────────────────────────────────

def _chunk_fixed(text: str) -> list[Chunk]:
    tokens = TOKENIZER.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = TOKENIZER.decode(chunk_tokens)
        chunks.append(Chunk(text=chunk_text, chunk_type="fixed"))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Table extraction ──────────────────────────────────────────────────────────

_TABLE_RE = re.compile(
    r"(?:(?:[^\n]+\t[^\n]+\n){2,}|(?:\|.+\|\n){2,})",
    re.MULTILINE,
)


def _extract_tables(text: str) -> tuple[str, list[Chunk]]:
    tables = []
    for match in _TABLE_RE.finditer(text):
        tables.append(Chunk(text=match.group().strip(), chunk_type="table"))
    clean_text = _TABLE_RE.sub("\n", text)
    return clean_text, tables


# ── Helpers ───────────────────────────────────────────────────────────────────

def _token_count(text: str) -> int:
    return len(TOKENIZER.encode(text))


def _sub_chunk(text: str, title: str, chunk_type: str) -> list[Chunk]:
    """Break a section into CHUNK_SIZE chunks if it's too large."""
    if _token_count(text) <= CHUNK_SIZE:
        return [Chunk(text=text, chunk_type=chunk_type, section_title=title)]
    sub_chunks = _chunk_fixed(text)
    for sc in sub_chunks:
        sc.section_title = title
        sc.chunk_type = chunk_type
    return sub_chunks


def _merge_short(chunks: list[Chunk]) -> list[Chunk]:
    """Merge adjacent chunks that are under MIN_CHUNK_TOKENS."""
    if not chunks:
        return []
    merged = [chunks[0]]
    for chunk in chunks[1:]:
        last = merged[-1]
        if last.token_count < MIN_CHUNK_TOKENS:
            merged[-1] = Chunk(
                text=last.text + "\n\n" + chunk.text,
                chunk_type=last.chunk_type,
                section_title=last.section_title,
            )
        else:
            merged.append(chunk)
    return merged
