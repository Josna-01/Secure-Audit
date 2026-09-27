import os
import sys
import hashlib
import requests
from dotenv import load_dotenv

sys.path.append('.')
load_dotenv()

from db import SessionLocal
from models import Evidence, Case
from app import UPLOADS_DIR, SUPABASE_URL, supabase_admin, USE_LOCAL_STORAGE

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def main():
    db = SessionLocal()
    print("=" * 80)
    print("CONFIGURATION & ENVIRONMENT")
    print("=" * 80)
    print(f"USE_LOCAL_STORAGE: {USE_LOCAL_STORAGE}")
    print(f"UPLOADS_DIR: {UPLOADS_DIR} (exists: {os.path.exists(UPLOADS_DIR)})")
    print(f"SUPABASE_URL: {SUPABASE_URL}")

    print("\n" + "=" * 80)
    print("ALL FILES IN backend/uploads DIRECTORY TREE")
    print("=" * 80)
    uploads_files = []
    if os.path.exists(UPLOADS_DIR):
        for root, dirs, files in os.walk(UPLOADS_DIR):
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, UPLOADS_DIR)
                sz = os.path.getsize(full_p)
                uploads_files.append((rel_p, full_p, sz))
                print(f" - {rel_p} ({sz} bytes)")
    if not uploads_files:
        print(" [EMPTY] No files found in backend/uploads")

    print("\n" + "=" * 80)
    print("DATABASE EVIDENCE RECORDS")
    print("=" * 80)
    records = db.query(Evidence).order_by(Evidence.created_at.desc()).all()
    print(f"Total evidence records found in database: {len(records)}\n")

    summary_table = []

    for idx, ev in enumerate(records, 1):
        ev_id = str(ev.id)
        case_id = str(ev.case_id) if ev.case_id else "None"
        orig_name = ev.file_name or "N/A"
        f_url = ev.file_url or ""
        db_hash = ev.file_hash or ""
        status = ev.status or "N/A"

        # Determine stored filename from URL
        stored_filename = os.path.basename(f_url.split("?")[0]) if f_url else "N/A"

        # Determine storage type and paths
        is_uploads_url = "/uploads/" in f_url
        is_supabase_url = "supabase.co" in f_url or f_url.startswith("http") and not is_uploads_url

        # Check local existence
        local_path = None
        local_exists = False
        local_hash = None

        if is_uploads_url:
            rel = f_url.split("/uploads/")[-1].replace("/", os.sep)
            local_path = os.path.join(UPLOADS_DIR, rel)
            local_exists = os.path.isfile(local_path)
            if local_exists:
                local_hash = sha256_file(local_path)
        else:
            # Check if stored_filename exists anywhere in UPLOADS_DIR
            potential_local = os.path.join(UPLOADS_DIR, "cases", case_id, stored_filename)
            if os.path.isfile(potential_local):
                local_path = potential_local
                local_exists = True
                local_hash = sha256_file(potential_local)
            else:
                local_path = "N/A (not local URL)"

        # Check Supabase existence
        supabase_path = None
        supabase_exists = False
        supabase_status_code = None
        supabase_hash = None

        if is_supabase_url:
            # URL format: .../object/public/evidence/cases/{case_id}/{filename}
            if "/evidence/" in f_url:
                supabase_path = f_url.split("/evidence/")[-1].split("?")[0]
            else:
                supabase_path = f_url

            try:
                res = requests.get(f_url, timeout=10)
                supabase_status_code = res.status_code
                if res.status_code == 200:
                    supabase_exists = True
                    supabase_hash = hashlib.sha256(res.content).hexdigest()
            except Exception as e:
                supabase_status_code = f"Err: {e}"
        else:
            supabase_path = "N/A (local URL)"

        # Determine what verification uses
        if is_uploads_url:
            used_for_verification = "Local File"
        elif is_supabase_url:
            used_for_verification = "Supabase HTTP GET"
        else:
            used_for_verification = "Local Path Fallback"

        print(f"[{idx}] Evidence ID: {ev_id}")
        print(f"    Case ID:             {case_id}")
        print(f"    Original Filename:   {orig_name}")
        print(f"    Stored Filename:     {stored_filename}")
        print(f"    file_url in DB:      {f_url}")
        print(f"    file_hash in DB:     {db_hash}")
        print(f"    Status:              {status}")
        print(f"    Local Path:          {local_path} (Exists: {local_exists})")
        if local_exists:
            print(f"    Local File SHA256:   {local_hash} (Matches DB: {local_hash == db_hash})")
        print(f"    Supabase Path:       {supabase_path} (Exists: {supabase_exists}, HTTP {supabase_status_code})")
        if supabase_exists:
            print(f"    Supabase SHA256:     {supabase_hash} (Matches DB: {supabase_hash == db_hash})")
        print(f"    Used for Verify:     {used_for_verification}")
        print("-" * 60)

        summary_table.append({
            "original_filename": orig_name,
            "stored_filename": stored_filename,
            "local_path": local_path if local_exists else ("Missing locally" if is_uploads_url else "N/A"),
            "supabase_path": supabase_path if supabase_exists else ("Missing in Supabase" if is_supabase_url else "N/A"),
            "database_path": f_url,
            "exists": "Yes (Supabase)" if supabase_exists else ("Yes (Local)" if local_exists else "No"),
            "used_for_verification": used_for_verification,
            "db_hash_match": (supabase_hash == db_hash) if supabase_exists else ((local_hash == db_hash) if local_exists else False),
            "evidence_id": ev_id
        })

    print("\n" + "=" * 80)
    print("SUPABASE STORAGE 'evidence' BUCKET LISTING")
    print("=" * 80)
    try:
        # list root or cases
        res = supabase_admin.storage.from_("evidence").list()
        print("Root items in 'evidence' bucket:")
        for item in res:
            print(f" - {item.get('name')} (id: {item.get('id')})")
        
        # list cases folder
        cases_res = supabase_admin.storage.from_("evidence").list("cases")
        print("\nFolders inside 'cases/':")
        for c in cases_res:
            c_name = c.get('name')
            print(f" [Folder] cases/{c_name}")
            try:
                sub_res = supabase_admin.storage.from_("evidence").list(f"cases/{c_name}")
                for sub in sub_res:
                    print(f"     -> {sub.get('name')} ({sub.get('metadata', {}).get('size', 'N/A')} bytes)")
            except Exception as e:
                print(f"     -> Error listing cases/{c_name}: {e}")
    except Exception as e:
        print(f"Error accessing Supabase Storage bucket: {e}")

if __name__ == "__main__":
    main()
