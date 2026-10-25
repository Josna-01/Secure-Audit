import os
import sys
import uvicorn

if __name__ == "__main__":
    # Ensure current directory is on sys.path
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
        
    print("[INFO] Starting Secure Audit Object Detection Service (best) on port 8003...")
    uvicorn.run("app:app", host="127.0.0.1", port=8003, reload=False)
