"""
Poll the latest Railway deployment until it settles, then show the tail of its
logs and probe /health.

    RAILWAY_TOKEN=... python scripts/deploy_watch.py
"""
import json
import os
import sys
import time

import httpx

PROJECT = os.environ.get("RAILWAY_PROJECT_ID", "8595811d-3414-4eb1-9642-4467e0877c6b")
ENVIRONMENT = os.environ.get("RAILWAY_ENVIRONMENT_ID", "fc986dae-529c-4eb4-a7c1-80451fc75005")
SERVICE = os.environ.get("RAILWAY_SERVICE_ID", "af2ab6f8-44b1-4976-8962-ea341672e020")
PUBLIC = os.environ.get("RAILWAY_PUBLIC_URL", "https://nexadesk-api-production.up.railway.app")

URL = "https://backboard.railway.com/graphql/v2"
H = {"Project-Access-Token": os.environ["RAILWAY_TOKEN"], "Content-Type": "application/json"}

LATEST = """
query($p: String!, $e: String!, $s: String!) {
  deployments(first: 1, input: {projectId: $p, environmentId: $e, serviceId: $s}) {
    edges { node { id status createdAt } }
  }
}
"""
LOGS = """
query($id: String!) {
  deploymentLogs(deploymentId: $id, limit: 40) { message }
}
"""

TERMINAL = {"SUCCESS", "FAILED", "CRASHED", "REMOVED", "SKIPPED"}


def gql(query, variables):
    return httpx.post(URL, json={"query": query, "variables": variables},
                      headers=H, timeout=40).json()


def main() -> int:
    # A push takes a moment to become a deployment. Without this, polling
    # immediately returns the *previous* deployment and reports its outcome as
    # if it were the new one — which is exactly how a stale failure gets
    # mistaken for a fresh one.
    ignore_id = os.environ.get("IGNORE_DEPLOYMENT_ID", "")

    dep_id = status = None
    for i in range(40):
        d = gql(LATEST, {"p": PROJECT, "e": ENVIRONMENT, "s": SERVICE})
        if d.get("errors"):
            print("ERR", json.dumps(d["errors"])[:200])
            return 1
        node = d["data"]["deployments"]["edges"][0]["node"]
        dep_id, status, created = node["id"], node["status"], node["createdAt"]

        if ignore_id and dep_id == ignore_id:
            print(f"  [{i:02d}] waiting for a new deployment (still seeing {dep_id[:8]})")
            time.sleep(15)
            continue

        print(f"  [{i:02d}] {status:12} {dep_id[:8]}  {created}")
        if status in TERMINAL:
            break
        time.sleep(15)

    print(f"\nstatus: {status}")

    if status != "SUCCESS" and dep_id:
        d = gql(LOGS, {"id": dep_id})
        for e in (d.get("data", {}).get("deploymentLogs") or [])[-25:]:
            print("  " + (e.get("message") or "").rstrip()[:180])

    print("\nprobing public URL:")
    for path in ("/health", "/docs"):
        try:
            r = httpx.get(PUBLIC + path, timeout=25, follow_redirects=True)
            print(f"  {path:8} HTTP {r.status_code}  {r.text[:120]}")
        except Exception as exc:
            print(f"  {path:8} {type(exc).__name__}: {str(exc)[:100]}")

    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
