import sys, os
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
admin_client = create_client(url, service_key)

users = admin_client.auth.admin.list_users()
print(f"Total Auth Users: {len(users)}")
for u in users:
    print(f"Email: {u.email} | ID: {u.id} | Last Sign In: {u.last_sign_in_at}")
