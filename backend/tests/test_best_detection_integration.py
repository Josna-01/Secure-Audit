import os
import sys
import requests
from fastapi.testclient import TestClient

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import app

client = TestClient(app)

def test_best_microservice_health():
    """Verify the new best microservice is running on port 8003 and reports healthy."""
    res = requests.get("http://127.0.0.1:8003/health", timeout=5)
    assert res.status_code == 200, f"Microservice health check failed: {res.text}"
    data = res.json()
    assert data["status"] == "healthy"
    assert data["classes_count"] == 6
    assert "pistol" in data["classes"].values()
    assert "knife" in data["classes"].values()
    assert "person" in data["classes"].values()
    assert "lying_person" in data["classes"].values()

def test_best_microservice_direct_inference():
    """Verify direct image detection on the new best microservice."""
    sample_path = os.path.join(os.path.dirname(BASE_DIR), "best", "sample_data", "sample_knife_evidence.jpg")
    assert os.path.exists(sample_path), f"Sample image missing at {sample_path}"

    with open(sample_path, "rb") as f:
        img_bytes = f.read()

    res = requests.post(
        "http://127.0.0.1:8003/detect/image",
        files={"image": ("sample.jpg", img_bytes, "image/jpeg")},
        data={"confidence": 0.25},
        timeout=10
    )
    assert res.status_code == 200, f"Inference failed: {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert "sha256_hash" in data
    assert "detections" in data
    assert len(data["detections"]) > 0
    first_det = data["detections"][0]
    assert "bbox" in first_det
    assert "x1" in first_det["bbox"]
    assert "y1" in first_det["bbox"]
    assert "x2" in first_det["bbox"]
    assert "y2" in first_det["bbox"]
    assert "confidence" in first_det
    assert "label" in first_det

if __name__ == "__main__":
    test_best_microservice_health()
    test_best_microservice_direct_inference()
    print("ALL BEST DETECTION INTEGRATION TESTS PASSED!")
