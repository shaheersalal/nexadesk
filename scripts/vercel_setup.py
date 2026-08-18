"""
Inspect and configure the Vercel project.

    python scripts/vercel_setup.py                 # status
    python scripts/vercel_setup.py --set-api-url   # set VITE_API_URL and redeploy

The dashboard reads VITE_API_URL at build time (Vite inlines env vars into the
bundle), so changing it requires a rebuild — setting the variable alone does
nothing to the already-deployed assets.
"""
import os
import pathlib
import sys

import httpx

API = "https://api.vercel.com"


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
TOKEN = os.environ["VERCEL_TOKEN"]
PROJECT = os.environ.get("VERCEL_PROJECT_ID", "prj_PCFQ3AHiYrK7C9RmiJFE8IOpFRbQ")
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

API_URL = "https://api.nexadesk.site"


def status():
    r = httpx.get(f"{API}/v9/projects/{PROJECT}", headers=H, timeout=30)
    if r.status_code != 200:
        print(f"project: HTTP {r.status_code} {r.text[:200]}")
        return
    p = r.json()
    print(f"project: {p['name']}  framework={p.get('framework')}")
    print(f"  root dir:   {p.get('rootDirectory') or '(repo root)'}")
    print(f"  build cmd:  {p.get('buildCommand') or '(framework default)'}")
    print(f"  output dir: {p.get('outputDirectory') or '(framework default)'}")

    link = p.get("link") or {}
    if link:
        print(f"  git: {link.get('type')}:{link.get('org')}/{link.get('repo')} "
              f"branch={link.get('productionBranch')}")

    print("\nenvironment variables:")
    r = httpx.get(f"{API}/v10/projects/{PROJECT}/env", headers=H, timeout=30)
    if r.status_code == 200:
        for e in r.json().get("envs", []):
            targets = ",".join(e.get("target") or [])
            print(f"  {e['key']:24} [{targets}]")
    else:
        print(f"  HTTP {r.status_code} {r.text[:160]}")

    print("\nrecent deployments:")
    r = httpx.get(f"{API}/v6/deployments", headers=H,
                  params={"projectId": PROJECT, "limit": 5}, timeout=30)
    if r.status_code == 200:
        for d in r.json().get("deployments", []):
            print(f"  {d.get('state', '?'):10} {d.get('url')}  target={d.get('target')}")
    else:
        print(f"  HTTP {r.status_code} {r.text[:160]}")


def set_api_url():
    # Remove any existing VITE_API_URL first — the API rejects duplicates.
    r = httpx.get(f"{API}/v10/projects/{PROJECT}/env", headers=H, timeout=30)
    for e in r.json().get("envs", []):
        if e["key"] == "VITE_API_URL":
            httpx.delete(f"{API}/v9/projects/{PROJECT}/env/{e['id']}", headers=H, timeout=30)
            print(f"  removed existing VITE_API_URL ({e['id']})")

    r = httpx.post(
        f"{API}/v10/projects/{PROJECT}/env",
        headers=H,
        json={
            "key": "VITE_API_URL",
            "value": API_URL,
            "type": "plain",
            "target": ["production", "preview", "development"],
        },
        timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"  set VITE_API_URL={API_URL}")
    else:
        print(f"  FAILED HTTP {r.status_code}: {r.text[:250]}")


if __name__ == "__main__":
    if "--set-api-url" in sys.argv:
        set_api_url()
        print()
    status()
