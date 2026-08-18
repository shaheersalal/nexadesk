"""
Create (or inspect) a Railway custom domain and report the DNS target it needs.

    RAILWAY_TOKEN=... python scripts/railway_domain.py             # list
    RAILWAY_TOKEN=... python scripts/railway_domain.py api.example.com
"""
import json
import os
import sys

import httpx

URL = "https://backboard.railway.com/graphql/v2"
PROJECT = os.environ.get("RAILWAY_PROJECT_ID", "8595811d-3414-4eb1-9642-4467e0877c6b")
ENVIRONMENT = os.environ.get("RAILWAY_ENVIRONMENT_ID", "fc986dae-529c-4eb4-a7c1-80451fc75005")
SERVICE = os.environ.get("RAILWAY_SERVICE_ID", "af2ab6f8-44b1-4976-8962-ea341672e020")
H = {"Project-Access-Token": os.environ["RAILWAY_TOKEN"], "Content-Type": "application/json"}


def gql(query, variables=None):
    r = httpx.post(URL, json={"query": query, "variables": variables or {}},
                   headers=H, timeout=45)
    return r.json()


LIST_Q = """
query($p: String!) {
  project(id: $p) {
    services { edges { node { name
      serviceInstances { edges { node {
        domains {
          serviceDomains { domain }
          customDomains { id domain status { dnsRecords { hostlabel recordType requiredValue currentValue zone } } }
        }
      } } }
    } } }
  }
}
"""

CREATE_M = """
mutation($input: CustomDomainCreateInput!) {
  customDomainCreate(input: $input) {
    id
    domain
    status { dnsRecords { hostlabel recordType requiredValue currentValue zone } }
  }
}
"""


def show():
    d = gql(LIST_Q, {"p": PROJECT})
    if d.get("errors"):
        print("ERR:", d["errors"][0]["message"][:200])
        return
    for svc in d["data"]["project"]["services"]["edges"]:
        node = svc["node"]
        print(f"service: {node['name']}")
        for inst in node["serviceInstances"]["edges"]:
            dom = inst["node"]["domains"]
            for sd in dom.get("serviceDomains") or []:
                print(f"  railway domain: {sd['domain']}")
            for cd in dom.get("customDomains") or []:
                print(f"  custom domain:  {cd['domain']}  (id {cd['id']})")
                for rec in (cd.get("status") or {}).get("dnsRecords") or []:
                    print(f"     {rec['recordType']:6} host={rec['hostlabel'] or '@':20} "
                          f"required={rec['requiredValue']}")
                    print(f"            current={rec.get('currentValue')}")


def create(domain):
    d = gql(CREATE_M, {"input": {
        "domain": domain,
        "environmentId": ENVIRONMENT,
        "serviceId": SERVICE,
        "projectId": PROJECT,
    }})
    if d.get("errors"):
        print("ERR:", json.dumps(d["errors"])[:400])
        return
    cd = d["data"]["customDomainCreate"]
    print(f"created: {cd['domain']}  (id {cd['id']})")
    for rec in (cd.get("status") or {}).get("dnsRecords") or []:
        print(f"  {rec['recordType']} {rec['hostlabel'] or '@'} -> {rec['requiredValue']}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        create(sys.argv[1])
    else:
        show()
