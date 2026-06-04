"""
Links all Supabase auth users to the demo company in public.users.
Run whenever dashboard shows no data:
    conda activate nexa
    python scripts/bootstrap_user.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv; load_dotenv()

from supabase import create_client
from app.config import get_settings

s = get_settings()
sb = create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)

# 1. Get company
companies = sb.table("companies").select("id, name").limit(1).execute()
if not companies.data:
    print("ERROR: No company found. Run seed_demo.py first.")
    sys.exit(1)
company_id = companies.data[0]["id"]
company_name = companies.data[0]["name"]
print(f"Company: {company_name} ({company_id})")

# 2. Get all auth users via admin API
auth_users = sb.auth.admin.list_users()
users = auth_users if isinstance(auth_users, list) else getattr(auth_users, 'users', [])
if not users:
    print("ERROR: No auth users found. Create a user in Supabase Auth first.")
    sys.exit(1)

print(f"Found {len(users)} auth user(s)")

# 3. Upsert each into public.users
for u in users:
    uid = u.id if hasattr(u, 'id') else u['id']
    email = u.email if hasattr(u, 'email') else u.get('email', '')
    sb.table("users").upsert({
        "id": uid,
        "company_id": company_id,
        "full_name": email.split("@")[0],
        "role": "owner",
    }, on_conflict="id").execute()
    print(f"  linked: {email} → {company_name}")

# 4. Verify
result = sb.table("users").select("id, company_id, role").execute()
print(f"\npublic.users now has {len(result.data)} row(s)")
for row in result.data:
    print(f"  {row['id']}  company={row['company_id']}  role={row['role']}")
print("\nDone. Hard-refresh the dashboard (Ctrl+Shift+R).")
