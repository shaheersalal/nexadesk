"""
Inspect Railway deployments: list recent ones, or dump a deployment's logs.

Railway's build and deploy logs are separate streams, and a build that never
started has only the former — that distinction is what identifies an
infrastructure failure versus a code failure, so both are always shown.

    RAILWAY_TOKEN=... python scripts/railway_logs.py            # list recent
    RAILWAY_TOKEN=... python scripts/railway_logs.py <deployId> # dump logs
"""
import os
import sys

import httpx

URL = "https://backboard.railway.com/graphql/v2"
PROJECT = os.environ.get("RAILWAY_PROJECT_ID", "8595811d-3414-4eb1-9642-4467e0877c6b")
ENVIRONMENT = os.environ.get("RAILWAY_ENVIRONMENT_ID", "fc986dae-529c-4eb4-a7c1-80451fc75005")
SERVICE = os.environ.get("RAILWAY_SERVICE_ID", "af2ab6f8-44b1-4976-8962-ea341672e020")
PUBLIC = os.environ.get("RAILWAY_PUBLIC_URL", "https://nexadesk-api-production.up.railway.app")

H = {"Project-Access-Token": os.environ["RAILWAY_TOKEN"], "Content-Type": "application/json"}

LIST_Q = """
query($p: String!, $e: String!, $s: String!) {
  deployments(first: 5, input: {projectId: $p, environmentId: $e, serviceId: $s}) {
    edges { node { id status createdAt } }
  }
}
"""


def gql(query, variables):
    return httpx.post(URL, json={"query": query, "variables": variables},
                      headers=H, timeout=45).json()


def list_deployments():
    d = gql(LIST_Q, {"p": PROJECT, "e": ENVIRONMENT, "s": SERVICE})
    if d.get("errors"):
        print("ERR", d["errors"][0]["message"][:200])
        return
    print("recent deployments:")
    for e in d["data"]["deployments"]["edges"]:
        n = e["node"]
        print(f"  {n['status']:12} {n['id']}  {n['createdAt']}")

    print("\npublic endpoint:")
    for path in ("/health", "/docs"):
        try:
            r = httpx.get(PUBLIC + path, timeout=25, follow_redirects=True)
            print(f"  {path:8} HTTP {r.status_code}  {r.text[:110]}")
        except Exception as exc:
            print(f"  {path:8} {type(exc).__name__}")


def dump_logs(deployment_id):
    for field in ("buildLogs", "deploymentLogs"):
        q = f'query($id: String!) {{ {field}(deploymentId: $id, limit: 150) {{ message }} }}'
        d = gql(q, {"id": deployment_id})
        if d.get("errors"):
            print(f"===== {field}: {d['errors'][0]['message'][:120]}\n")
            continue
        lines = [(e.get("message") or "").rstrip() for e in (d["data"][field] or [])]
        print(f"===== {field} ({len(lines)} lines) =====")
        for line in lines[-50:]:
            print("  " + line[:200])
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dump_logs(sys.argv[1])
    else:
        list_deployments()
