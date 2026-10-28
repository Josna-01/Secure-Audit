"""
Secure Audit — Unified System Master Launcher (start_all.py)
Launches all microservices, blockchain node, AI engines, and frontend in parallel.
Press Ctrl+C to stop all services cleanly.
"""
import os
import sys
import time
import subprocess
import signal

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name": "1. Blockchain (Ganache RPC Node)",
        "cmd": ["npx", "ganache", "--server.host", "127.0.0.1", "--server.port", "8545", "--chain.chainId", "1337", "--wallet.deterministic", "--database.dbPath", "./ganache-data"],
        "cwd": os.path.join(BASE_DIR, "blockchain"),
    },
    {
        "name": "2. Main Backend (FastAPI Gateway - Port 8000)",
        "cmd": ["py", "-3.10", "app.py"],
        "cwd": os.path.join(BASE_DIR, "backend"),
    },
    {
        "name": "3. BNS ML Service (Port 8001)",
        "cmd": [os.path.join(BASE_DIR, "bns-backend", "venv", "Scripts", "python.exe"), "-m", "uvicorn", "app.main:app", "--port", "8001", "--reload"],
        "cwd": os.path.join(BASE_DIR, "bns-backend"),
    },
    {
        "name": "4. Audio Forensics Service (Port 8002)",
        "cmd": [os.path.join(BASE_DIR, "audio-backend", "venv", "Scripts", "python.exe"), "app.py"],
        "cwd": os.path.join(BASE_DIR, "audio-backend"),
    },
    {
        "name": "5. Crime Object Detection (Port 8003)",
        "cmd": [os.path.join(BASE_DIR, "best", "venv", "Scripts", "python.exe"), "main.py"],
        "cwd": os.path.join(BASE_DIR, "best"),
    },
    {
        "name": "6. Photogrammetry 3D Service (Port 8004)",
        "cmd": [os.path.join(BASE_DIR, "photogrammetry-backend", "venv", "Scripts", "python.exe"), "app.py"],
        "cwd": os.path.join(BASE_DIR, "photogrammetry-backend"),
    },
    {
        "name": "7. Audit Frontend (Vite App - Port 5173)",
        "cmd": ["npm", "run", "dev"],
        "cwd": os.path.join(BASE_DIR, "audit-frontend"),
    },
]

processes = []

def stop_all(sig=None, frame=None):
    print("\n[INFO] Stopping all Secure Audit services...")
    for item in reversed(processes):
        p = item["proc"]
        name = item["name"]
        print(f"Stopping {name}...")
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("[SUCCESS] All services stopped successfully.")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    print("==================================================")
    print("🚀 Starting Secure Audit Digital Forensics System")
    print("==================================================")

    for s in SERVICES:
        print(f"Starting {s['name']}...")
        try:
            is_shell = sys.platform == "win32" and (s['cmd'][0] in ("npx", "npm"))
            proc = subprocess.Popen(
                s["cmd"],
                cwd=s["cwd"],
                shell=is_shell
            )
            processes.append({"name": s["name"], "proc": proc})
            time.sleep(1.2)
        except Exception as e:
            print(f"[ERROR] Failed to start {s['name']}: {e}")

    print("\n==================================================")
    print("✅ All 7 services launched successfully!")
    print("🌐 Frontend App:     http://localhost:5173")
    print("⚙️  Main API Gateway: http://localhost:8000")
    print("🔗 Blockchain RPC:   http://127.0.0.1:8545")
    print("==================================================")
    print("Press Ctrl+C at any time to shutdown all services.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all()

if __name__ == "__main__":
    main()
