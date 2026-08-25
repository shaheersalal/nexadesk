"""
Backfill existing properties into the vector knowledge base.

    python scripts/backfill_property_rag.py <company_id> [--dry-run]

properties/router.py ingests a property when it is created or updated, but
anything that predates that hook never made it into Qdrant. A company can
therefore show a full listings table in the dashboard while the receptionist
knows nothing about any of it and falls back to lead capture on every question.

Re-running is safe: the doc_id is derived from the property id, so a property
is replaced rather than duplicated.
"""
import asyncio
import os
import pathlib
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NS = uuid.UUID("2c8f4a71-6d3e-4b5a-9f21-77c0e4a1b9d3")


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
    from app.dependencies import get_qdrant, ensure_collection, get_supabase_admin
    from app.rag.pipeline import ingest_text
    from app.rag.store import delete_doc_chunks
    from app.properties.router import property_to_text

    settings = get_settings()
    client = await get_qdrant(settings)
    await ensure_collection(client, settings)

    sb = get_supabase_admin()
    rows = sb.table("properties").select("*").eq("company_id", company_id).execute().data
    print(f"company: {company_id}")
    print(f"properties: {len(rows)}\n")

    ok = failed = total_chunks = 0
    for p in rows:
        doc_id = str(uuid.uuid5(NS, str(p["id"])))
        label = p.get("title") or p.get("address") or p["id"]
        if dry:
            print(f"  would ingest: {str(label)[:70]}")
            continue
        try:
            try:
                await delete_doc_chunks(doc_id, client)
            except Exception:
                pass
            result = await ingest_text(
                text=property_to_text(p),
                company_id=company_id,
                metadata={
                    "source_type": "property_form",
                    "property_id": str(p["id"]),
                    "doc_category": "listing",
                    "filename": f"property_{p['id']}.txt",
                },
                doc_id=doc_id,
            )
            n = result.get("chunks") or result.get("chunk_count") or 0
            total_chunks += n
            ok += 1
            print(f"  ok  {str(label)[:60]:62} {n} chunks")
        except Exception as exc:
            failed += 1
            print(f"  FAIL {str(label)[:60]:61} {type(exc).__name__}: {exc}")

    if not dry:
        print(f"\ningested {ok}/{len(rows)} properties, {total_chunks} chunks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
