import sys
sys.path.append('.')
from app import supabase_admin

def main():
    try:
        res = supabase_admin.table("users").select("*").execute()
        print("Supabase Users:")
        for u in res.data:
            print(f"ID: {u.get('id')}, Email: {u.get('email')}, Name: {u.get('full_name')}, Role: {u.get('role')}")
    except Exception as e:
        print(f"Error fetching Supabase users: {e}")

if __name__ == "__main__":
    main()
