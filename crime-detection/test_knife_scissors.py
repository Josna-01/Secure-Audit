import requests
import os
# Original code (Alisha):
# url = "http://127.0.0.1:8001/detect/image"
# Updated: Port 8003 to match active object detection service
url = "http://127.0.0.1:8003/detect/image"
sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
knife_path = os.path.join(sample_dir, "sample_knife_evidence.jpg")

if os.path.exists(knife_path):
    with open(knife_path, "rb") as f:
        files = {"image": ("sample_knife.jpg", f, "image/jpeg")}
        resp = requests.post(url, files=files)
        print("[TEST RESPONSE]:", resp.status_code)
        print("[JSON DATA]:", resp.json())
