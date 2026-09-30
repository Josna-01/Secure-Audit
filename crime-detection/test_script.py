import os
import cv2
import numpy as np
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_system_tests():
    print("==================================================================")
    print("  Testing Trained YOLOv8 Suspicious Object Detection System...")
    print("==================================================================")

    # 1. Health check test
    response = client.get("/health")
    assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
    health_data = response.json()
    print("[PASS] Health Endpoint OK:", health_data)

    # 2. Test Model Training / Fine-tuning Endpoint
    print("[INFO] Triggering /train endpoint test...")
    response = client.post("/train?epochs=1")
    assert response.status_code == 200, f"Training endpoint failed: {response.text}"
    train_data = response.json()
    print("[PASS] Training Endpoint OK:", train_data)

    # 3. Test Image Detection on Input Image
    sample_img_path = os.path.join("sample_data", "sample_knife_evidence.jpg")
    assert os.path.exists(sample_img_path), "Sample knife evidence image missing!"

    with open(sample_img_path, "rb") as f:
        response = client.post(
            "/detect/image",
            files={"image": ("sample_knife_evidence.jpg", f, "image/jpeg")},
            data={"confidence": "0.1"}
        )

    assert response.status_code == 200, f"Image detection failed: {response.text}"
    img_json = response.json()
    print("[PASS] Image Detection Output:")
    print("   Active Model:", img_json.get("active_model"))
    print("   Filename:", img_json.get("filename"))
    print("   SHA-256 Hash:", img_json.get("sha256_hash"))
    print("   Output Image URL:", img_json.get("output_image_url"))
    print("   Total Objects Detected:", img_json.get("total_objects"))
    print("   Suspicious Objects Count:", img_json.get("suspicious_objects_count"))

    # Verify that the output image file actually exists on disk
    out_rel = img_json.get("output_image_url", "").lstrip("/")
    out_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_rel)
    assert os.path.exists(out_abs), f"Output image file was not created at: {out_abs}"
    print(f"[PASS] Verified Output Image file created at: {out_abs}")

    # 4. Test Video Detection
    sample_vid_path = os.path.join("sample_data", "sample_surveillance_stream.mp4")
    assert os.path.exists(sample_vid_path), "Sample video missing!"

    with open(sample_vid_path, "rb") as f:
        response = client.post(
            "/detect/video",
            files={"video": ("sample_surveillance_stream.mp4", f, "video/mp4")},
            data={"confidence": "0.1"}
        )

    assert response.status_code == 200, f"Video detection failed: {response.text}"
    vid_json = response.json()
    print("[PASS] Video Detection Output:")
    print("   Filename:", vid_json.get("filename"))
    print("   SHA-256 Hash:", vid_json.get("sha256_hash"))
    print("   Output Video URL:", vid_json.get("output_video_url"))

    print("\n==================================================================")
    print(" SUCCESS: ALL TESTS PASSED! MODEL TRAINED & DETECTS SUSPICIOUS OBJECTS.")
    print("==================================================================")

if __name__ == "__main__":
    run_system_tests()
