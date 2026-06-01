from supabase import create_client
import os

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
from dotenv import load_dotenv
load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

print('Testing audit logs table...')
try:
    res = supabase.table('audit_logs').select('*').execute()
    print('Logs:', len(res.data))
    
    count_res = supabase.table('audit_logs').select('id', count='exact').execute()
    print('Count:', count_res.count)
except Exception as e:
    print('Error:', e)
