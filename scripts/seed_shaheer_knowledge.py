"""
Ingest seed_knowledge_shaheer/ into the Shaheer Salal Studio company's RAG —
Part A of the two-part ai_studio knowledge base (Part B is the ephemeral
per-visitor URL fetch, see app/rag/live_fetch.py).

This is deliberately a separate directory and script from
scripts/seed_knowledge.py / seed_knowledge/, which hold real-estate market
orientation material meant for real_estate-vertical tenants. Ingesting that
content into the studio company (or this content into a real-estate one)
would be wrong for both.

    python scripts/seed_shaheer_knowledge.py <company_id> [--dry-run]

Re-running replaces the previous copy of each document rather than
duplicating it: the doc_id is derived from the filename.
"""
import asyncio
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEED_DIR = ROOT / "seed_knowledge_shaheer"
# Distinct namespace from seed_knowledge.py's NS so doc_ids never collide
# even if both were ever (mistakenly) ingested into the same company.
NS = uuid.UUID("b1c9a7f2-4e3d-4a1b-9c6e-7f2a5d8b1e04")


def load_env(path=ROOT / ".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            import os
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        print(__doc__)
        return 2
    company_id = args[0]

    load_env()
    from app.config import get_settings
    from app.dependencies import get_qdrant, ensure_collection
    from app.rag.pipeline import ingest_text
    from app.rag.store import delete_doc_chunks

    settings = get_settings()
    client = await get_qdrant(settings)
    await ensure_collection(client, settings)

    docs = sorted(SEED_DIR.glob("*.md"))
    if not docs:
        print(f"no documents in {SEED_DIR}")
        return 1

    print(f"company: {company_id}")
    print(f"documents: {len(docs)}\n")

    total = 0
    for path in docs:
        text = path.read_text(encoding="utf-8")
        doc_id = str(uuid.uuid5(NS, path.name))
        title = path.stem.replace("_", " ").title()
        print(f"  {path.name}  ({len(text.split())} words)  doc_id={doc_id}")
        if dry:
            continue
        try:
            await delete_doc_chunks(doc_id, client)
        except Exception as exc:
            print(f"     (no previous copy to remove: {type(exc).__name__})")
        result = await ingest_text(
            text=text,
            company_id=company_id,
            metadata={
                "source_type": "seed_knowledge_shaheer",
                "doc_category": "general_knowledge",
                "filename": path.name,
                "title": title,
                "property_id": "",
            },
            doc_id=doc_id,
        )
        chunks = result.get("chunks") or result.get("chunk_count") or 0
        total += chunks
        print(f"     -> {chunks} chunks")

    print(f"\n{'would ingest' if dry else 'ingested'} {len(docs)} documents"
          + ("" if dry else f", {total} chunks total"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
