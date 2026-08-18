"""
Manage the api.nexadesk.site DNS record in Cloudflare.

    python scripts/cloudflare_dns.py                      # show current records
    python scripts/cloudflare_dns.py <target> [--apply]   # point api -> target

The record must be **DNS only** (gray cloud), not proxied. Railway terminates
its own TLS, so proxying through Cloudflare puts a second certificate in front
of one that is already valid, and Cloudflare's proxy interferes with the
WebSocket upgrade that the streaming voice pipeline depends on end to end.

Reads CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID from .env.
"""
import os
import pathlib
import sys

import httpx

API = "https://api.cloudflare.com/client/v4"
NAME = "api.nexadesk.site"


def load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()
H = {"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
     "Content-Type": "application/json"}
ZONE = os.environ["CLOUDFLARE_ZONE_ID"]


def records():
    r = httpx.get(f"{API}/zones/{ZONE}/dns_records", headers=H,
                  params={"per_page": 100}, timeout=30)
    r.raise_for_status()
    return r.json()["result"]


def show():
    print(f"zone {ZONE}:")
    for rec in records():
        if rec["type"] in ("A", "AAAA", "CNAME"):
            cloud = "orange (proxied)" if rec.get("proxied") else "gray (DNS only)"
            print(f"  {rec['type']:6} {rec['name']:26} -> {str(rec['content'])[:46]:48} {cloud}")


def apply(target, dry=True):
    existing = [r for r in records() if r["name"] == NAME]

    payload = {
        "type": "CNAME",
        "name": NAME,
        "content": target,
        "ttl": 1,          # 1 = automatic
        "proxied": False,  # see module docstring
        "comment": "Railway backend — DNS only, proxying breaks TLS + WebSockets",
    }

    if existing:
        rec = existing[0]
        print(f"current: {rec['type']} {rec['name']} -> {rec['content']} "
              f"({'proxied' if rec.get('proxied') else 'DNS only'})")
        print(f"new:     CNAME {NAME} -> {target} (DNS only)")
        if dry:
            print("\n--dry run, nothing changed. Pass --apply to write.")
            return
        r = httpx.put(f"{API}/zones/{ZONE}/dns_records/{rec['id']}",
                      headers=H, json=payload, timeout=30)
    else:
        print(f"no existing {NAME} record; will create CNAME -> {target}")
        if dry:
            print("\n--dry run, nothing changed. Pass --apply to write.")
            return
        r = httpx.post(f"{API}/zones/{ZONE}/dns_records",
                       headers=H, json=payload, timeout=30)

    body = r.json()
    if not body.get("success"):
        print("FAILED:", str(body.get("errors"))[:300])
        return
    res = body["result"]
    print(f"\nOK: {res['type']} {res['name']} -> {res['content']} "
          f"({'proxied' if res.get('proxied') else 'DNS only'})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        show()
    else:
        apply(args[0], dry="--apply" not in sys.argv)
