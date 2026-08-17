"""
Connectivity check for the managed datastores, reading config from .env.

Run before a deploy: it fails fast and locally, instead of turning into a
crash-looping Railway container with a stack trace in the logs.

    python scripts/check_services.py
"""
import asyncio
import os
import pathlib
import sys


def load_env(path=".env") -> None:
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def mask(value: str) -> str:
    if not value:
        return "<empty>"
    return f"…{value[-6:]} ({len(value)} chars)"


async def check_qdrant() -> bool:
    import httpx
    url = os.environ.get("QDRANT_URL", "")
    key = os.environ.get("QDRANT_API_KEY", "")
    if not url:
        print("  QDRANT_URL not set — SKIP")
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{url.rstrip('/')}/collections", headers={"api-key": key})
        if r.status_code == 200:
            names = [c_["name"] for c_ in r.json()["result"]["collections"]]
            print(f"  Qdrant   OK   collections={names or '[]'}")
            return True
        print(f"  Qdrant   FAIL HTTP {r.status_code}: {r.text[:160]}")
    except Exception as exc:
        print(f"  Qdrant   FAIL {type(exc).__name__}: {exc}")
    return False


async def check_redis() -> bool:
    import redis.asyncio as aioredis
    url = os.environ.get("REDIS_URL", "")
    if not url:
        print("  REDIS_URL not set — SKIP")
        return False
    client = None
    try:
        client = await aioredis.from_url(url, encoding="utf-8", decode_responses=True)
        await client.set("nexadesk:healthcheck", "ok", ex=30)
        value = await client.get("nexadesk:healthcheck")
        await client.delete("nexadesk:healthcheck")
        print(f"  Redis    OK   round-trip={value!r}")
        return True
    except Exception as exc:
        print(f"  Redis    FAIL {type(exc).__name__}: {str(exc)[:200]}")
        return False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


async def check_supabase() -> bool:
    import httpx
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not (url and key):
        print("  Supabase not fully configured — SKIP")
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                f"{url.rstrip('/')}/rest/v1/companies",
                params={"select": "id", "limit": "1"},
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
        if r.status_code == 200:
            print(f"  Supabase OK   companies reachable ({len(r.json())} row(s) sampled)")
            return True
        print(f"  Supabase FAIL HTTP {r.status_code}: {r.text[:160]}")
    except Exception as exc:
        print(f"  Supabase FAIL {type(exc).__name__}: {exc}")
    return False


async def check_openai() -> bool:
    import httpx
    key = os.environ.get("LLM_API_KEY", "")
    if not key:
        print("  LLM_API_KEY not set — SKIP")
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://api.openai.com/v1/models",
                            headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 200:
            print("  OpenAI   OK")
            return True
        print(f"  OpenAI   FAIL HTTP {r.status_code}: {r.text[:120]}")
    except Exception as exc:
        print(f"  OpenAI   FAIL {type(exc).__name__}: {exc}")
    return False


async def main() -> int:
    load_env()
    print("config (masked):")
    for k in ("QDRANT_URL", "QDRANT_API_KEY", "REDIS_URL", "SUPABASE_URL", "LLM_API_KEY"):
        v = os.environ.get(k, "")
        print(f"  {k:22} {v if k.endswith('URL') and 'REDIS' not in k else mask(v)}")

    print("\nconnectivity:")
    results = await asyncio.gather(
        check_qdrant(), check_redis(), check_supabase(), check_openai()
    )
    ok = sum(1 for r in results if r)
    print(f"\n{ok}/{len(results)} services reachable")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
