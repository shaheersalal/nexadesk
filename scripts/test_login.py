import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv; load_dotenv()
from supabase import create_client
from app.config import get_settings

s = get_settings()
sb = create_client(s.SUPABASE_URL, s.SUPABASE_ANON_KEY)

try:
    result = sb.auth.sign_in_with_password({"email": "shaheersalal@gmail.com", "password": "NexaDesk2026!"})
    print("Login OK:", result.user.email)
except Exception as e:
    print("Login FAILED:", e)

    # Try resetting again with admin client
    sb_admin = create_client(s.SUPABASE_URL, s.SUPABASE_SERVICE_KEY)
    users = sb_admin.auth.admin.list_users()
    users = users if isinstance(users, list) else getattr(users, 'users', [])
    for u in users:
        uid = u.id if hasattr(u, 'id') else u['id']
        res = sb_admin.auth.admin.update_user_by_id(uid, {"password": "NexaDesk2026!"})
        print("Force reset for:", u.email if hasattr(u, 'email') else u.get('email'))
    print("Done — try logging in again with NexaDesk2026!")
