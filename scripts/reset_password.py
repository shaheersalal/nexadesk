"""
Reset password for a user directly via Supabase admin API.
Usage: conda activate nexa && python scripts/reset_password.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv; load_dotenv()

from supabase import create_client
from app.config import get_settings

NEW_PASSWORD = "NexaDesk2026!"   # change this to whatever you want

s = get_settings()
sb = create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)

users = sb.auth.admin.list_users()
users = users if isinstance(users, list) else getattr(users, 'users', [])

for u in users:
    uid = u.id if hasattr(u, 'id') else u['id']
    email = u.email if hasattr(u, 'email') else u.get('email', '')
    sb.auth.admin.update_user_by_id(uid, {"password": NEW_PASSWORD})
    print(f"Password reset for {email} → {NEW_PASSWORD}")
