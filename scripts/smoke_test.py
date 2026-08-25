"""
Smoke-test the deployed API.

Sends a browser-like User-Agent deliberately: BotBlockMiddleware rejects
python-httpx and friends, so a default client gets a 403 that looks like a
deployment failure but is actually the bot filter doing its job.

    python scripts/smoke_test.py [base_url]
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://nexadesk-api-production.up.railway.app"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA}

CHECKS = [
    ("GET", "/health", None, "liveness"),
    ("GET", "/docs", None, "OpenAPI UI"),
    ("GET", "/openapi.json", None, "schema"),
    ("GET", "/v1/leads", None, "API key required -> expect 401"),
    ("GET", "/mcp/", None, "MCP discovery"),
    ("POST", "/voice/inbound", None, "voice mounted, unsigned -> expect 403"),
    ("GET", "/leads/", None, "auth required -> expect 401"),
]


def main() -> int:
    print(f"target: {BASE}\n")
    failures = 0
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as c:
        for method, path, body, note in CHECKS:
            try:
                r = c.request(method, BASE + path, json=body)
                snippet = r.text[:90].replace("\n", " ")
                print(f"  {r.status_code}  {method:5} {path:16} {note}")
                if snippet and r.status_code >= 400:
                    print(f"        {snippet}")
            except Exception as exc:
                print(f"  ERR  {method:5} {path:16} {type(exc).__name__}: {exc}")
                failures += 1

    # Confirm the bot filter still works, using a default httpx UA.
    print("\nbot filter:")
    try:
        r = httpx.get(BASE + "/health", timeout=20)
        verdict = "OK — blocked" if r.status_code == 403 else f"NOT blocking (HTTP {r.status_code})"
        print(f"  python-httpx UA -> {verdict}")
    except Exception as exc:
        print(f"  {type(exc).__name__}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
