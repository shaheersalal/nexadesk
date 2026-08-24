"""
Verify Twilio credentials and report what the voice feature still needs.

    python scripts/twilio_check.py

Reads TELEPHONY_ACCOUNT_SID / TELEPHONY_AUTH_TOKEN from .env.
"""
import os
import pathlib
import sys

import httpx

API = "https://api.twilio.com/2010-04-01"


def load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    sid = os.environ.get("TELEPHONY_ACCOUNT_SID", "")
    token = os.environ.get("TELEPHONY_AUTH_TOKEN", "")

    if not (sid and token):
        print("TELEPHONY_ACCOUNT_SID / TELEPHONY_AUTH_TOKEN not set in .env")
        return 1

    auth = (sid, token)
    print(f"account: {sid[:10]}…{sid[-4:]}\n")

    # Credentials + account state
    r = httpx.get(f"{API}/Accounts/{sid}.json", auth=auth, timeout=30)
    if r.status_code != 200:
        print(f"auth FAILED  HTTP {r.status_code}: {r.text[:200]}")
        return 1
    acc = r.json()
    print(f"  status:   {acc.get('status')}")
    print(f"  type:     {acc.get('type')}")
    print(f"  name:     {acc.get('friendly_name')}")

    # Balance
    try:
        b = httpx.get(f"{API}/Accounts/{sid}/Balance.json", auth=auth, timeout=30).json()
        print(f"  balance:  {b.get('balance')} {b.get('currency')}")
    except Exception:
        pass

    # Owned numbers — the thing voice actually needs
    r = httpx.get(f"{API}/Accounts/{sid}/IncomingPhoneNumbers.json",
                  auth=auth, params={"PageSize": 50}, timeout=30)
    numbers = r.json().get("incoming_phone_numbers", []) if r.status_code == 200 else []

    print(f"\nphone numbers: {len(numbers)}")
    for n in numbers:
        caps = n.get("capabilities") or {}
        able = ",".join(k for k, v in caps.items() if v)
        print(f"  {n['phone_number']}  [{able}]")
        print(f"    voice webhook: {n.get('voice_url') or '(unset)'}")
        print(f"    status  hook:  {n.get('status_callback') or '(unset)'}")

    if not numbers:
        print("  none yet — voice cannot receive calls until one is bought")
        # What is available to buy?
        r = httpx.get(f"{API}/Accounts/{sid}/AvailablePhoneNumbers/US/Local.json",
                      auth=auth, params={"VoiceEnabled": "true", "PageSize": 3}, timeout=30)
        if r.status_code == 200:
            avail = r.json().get("available_phone_numbers", [])
            print(f"\n  US local numbers available to buy (showing {len(avail)}):")
            for a in avail:
                print(f"    {a['phone_number']}  {a.get('locality') or ''} {a.get('region') or ''}")
        else:
            print(f"\n  availability lookup HTTP {r.status_code}: {r.text[:160]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
