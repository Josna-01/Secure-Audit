import sys
import os
import uuid
from PIL import Image, ImageDraw, ImageFont
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Evidence, Case, OCRResult
from app import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_ocr_endpoint():
    db = SessionLocal()
    try:
        # Create test case and evidence in PostgreSQL
        test_case_id = uuid.uuid4()
        test_case = Case(
            id=test_case_id,
            title="OCR Test Case",
            offence_type="Fraud"
        )
        db.add(test_case)

        test_evidence_id = uuid.uuid4()
        
        # Create a sample image file locally in uploads
        os.makedirs("uploads", exist_ok=True)
        sample_path = os.path.join("uploads", f"test_evidence_{test_evidence_id}.png")
        
        img = Image.new("RGB", (400, 100), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 30), "EVIDENCE DOCUMENT SAMPLE TEXT 12345", fill=(0, 0, 0))
        img.save(sample_path)

        test_evidence = Evidence(
            id=test_evidence_id,
            case_id=test_case_id,
            evidence_type="Image",
            file_url=sample_path,
            file_name="sample_test.png"
        )
        db.add(test_evidence)
        db.commit()

        print(f"[TEST] Sending POST /ai/ocr/{test_evidence_id}...")
        response = client.post(f"/ai/ocr/{test_evidence_id}", json={"language": "en"})

        print(f"[TEST] Response Status Code: {response.status_code}")
        print(f"[TEST] Response Body: {response.json()}")

        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        res_data = response.json()
        assert res_data.get("success") is True, "Success should be True"

        # Check PostgreSQL for OCRResult
        saved_ocr = db.query(OCRResult).filter(OCRResult.evidence_id == test_evidence_id).first()
        assert saved_ocr is not None, "OCRResult record not found in PostgreSQL!"
        print(f"[TEST SUCCESS] Saved OCR text: '{saved_ocr.extracted_text}'")

        # Cleanup
        if saved_ocr:
            db.delete(saved_ocr)
        if test_evidence:
            db.delete(test_evidence)
        if test_case:
            db.delete(test_case)
        db.commit()


        if os.path.exists(sample_path):
            os.remove(sample_path)

        print("[TEST SUCCESS] All tests and cleanup completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"[TEST FAILED] Error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_ocr_endpoint()
