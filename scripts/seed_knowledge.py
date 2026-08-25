"""
Ingest the general-knowledge documents in seed_knowledge/ into a company's RAG.

    python scripts/seed_knowledge.py <company_id> [--dry-run]

These documents are not listings. They are market orientation material and an
honest description of the service, and they exist because the receptionist used
to deflect anything that was not a specific property into lead capture. A
technical caller evaluating the system would ask how it works and be asked for
their phone number, which reads as a malfunction.

Re-running replaces the previous copy of each document rather than duplicating
it: the doc_id is derived from the filename.
"""
import asyncio
import os
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEED_DIR = ROOT / "seed_knowledge"
# Stable namespace so a re-run overwrites rather than duplicating.
NS = uuid.UUID("6f0d1d3e-9c1a-4f2b-9a77-2b1f5a0c8e41")


def load_env(path=ROOT / ".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
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

    # The Qdrant client is normally created by the app's lifespan. A script has
    # no lifespan, so the module-level client stays None and the first upsert
    # fails with AttributeError on NoneType. Initialise it explicitly.
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
        # Remove any previous copy so re-running does not duplicate chunks.
        try:
            await delete_doc_chunks(doc_id, client)
        except Exception as exc:
            print(f"     (no previous copy to remove: {type(exc).__name__})")
        result = await ingest_text(
            text=text,
            company_id=company_id,
            metadata={
                "source_type": "seed_knowledge",
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
