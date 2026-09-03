"""
One-off: create the "Shaheer Salal — AI Product Studio" company row and
attach the platform admin (shaheersalal@gmail.com) to it as owner.

This is what turns shaheer.dev into a NexaDesk tenant like any other, using
the ai_studio vertical (app/shared/verticals.py) instead of real_estate.
None of the existing company-creation paths fit this case: app/companies
POST /child only creates children under an existing parent, and the
auto-provision trigger explicitly skips the admin UID. See
migrations/0005_company_vertical.sql for the vertical column this depends on
— apply that migration before running this.

Run once:
    conda activate nexa
    python scripts/create_shaheer_company.py [--dry-run]

Re-running is safe: it looks up by phone number first and updates the
existing row instead of creating a duplicate.
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The platform admin's own Supabase auth user id — same one app/admin/router.py
# gates on (ADMIN_UID). Attaching it here means this identity now owns both
# the platform-admin surface and a real tenant company; require_admin is
# UID-only so that doesn't conflict.
ADMIN_UID = "7227a933-56ef-45c4-8cbc-1c8331c74b21"

PHONE = "+17813655768"
EMAIL = "contact@shaheer.dev"

COMPANY = {
    "name": "Shaheer Salal — AI Product Studio",
    "phone": PHONE,
    "email": EMAIL,
    "address": "Karachi, Pakistan",
    "working_hours": {"Mon-Sat": "10:00-19:00 PKT"},
    "ai_persona": (
        "Shaheer's AI assistant — warm, sharp, and confident about what this "
        "studio builds. Sounds like someone who ships, not a script reading "
        "out a service catalogue."
    ),
    "receptionist_name": "Shaheer's Assistant",
    "vertical": "ai_studio",
    "onboarding_complete": True,
}


def _load_env(path=ROOT / ".env"):
    p = pathlib.Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    dry = "--dry-run" in sys.argv
    _load_env()

    from supabase import create_client
    from app.config import get_settings

    s = get_settings()
    sb = create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)

    existing = sb.table("companies").select("id, name, phone").eq("phone", PHONE).execute()
    if existing.data:
        company_id = existing.data[0]["id"]
        print(f"Existing company already owns {PHONE}: {existing.data[0]['name']} ({company_id})")
        if existing.data[0]["name"] == COMPANY["name"]:
            print("Already the studio company — updating its fields instead of creating a duplicate.")
            if not dry:
                sb.table("companies").update(COMPANY).eq("id", company_id).execute()
        else:
            print(
                "WARNING: a DIFFERENT company currently owns this number "
                f"({existing.data[0]['name']}). This script will not silently "
                "steal it — clear that company's `phone` column first "
                "(a manual UPDATE in the Supabase SQL editor), then re-run this."
            )
            return 1
    else:
        print(f"No company currently owns {PHONE} — creating a new one.")
        if dry:
            print(f"[dry-run] would insert: {COMPANY}")
            return 0
        result = sb.table("companies").insert(COMPANY).execute()
        company_id = result.data[0]["id"]
        print(f"Created company {company_id}")

    if dry:
        print(f"[dry-run] would upsert users: id={ADMIN_UID} company_id={company_id} role=owner")
        return 0

    sb.table("users").upsert({
        "id": ADMIN_UID,
        "company_id": company_id,
        "full_name": "Shaheer Salal",
        "role": "owner",
    }, on_conflict="id").execute()
    print(f"Linked admin user {ADMIN_UID} -> company {company_id} as owner")

    print(
        "\nNext steps:\n"
        f"  1. python scripts/seed_shaheer_knowledge.py {company_id}\n"
        "  2. Decommission the old Pinnacle demo's claim on this phone number "
        "(see migrations/README.md and CLAUDE.md resume notes) — staged: "
        "clear its `phone` first, verify a test call, then delete its rows.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
