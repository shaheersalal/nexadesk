import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv; load_dotenv()
from app.dependencies import get_supabase_admin

sb = get_supabase_admin()

print("=== Companies ===")
for c in sb.table("companies").select("id, name").execute().data:
    print(f"  {c['id']}  {c['name']}")

print("\n=== Users (public.users) ===")
for u in sb.table("users").select("id, company_id, role").execute().data:
    print(f"  user={u['id']}")
    print(f"  company={u['company_id']}")
    print(f"  role={u['role']}")
