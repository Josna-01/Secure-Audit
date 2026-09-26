"""End-to-end test: verify ocr_service.extract_image works with PaddleOCR 3.x."""
import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ocr_service import ocr_service

# Build a synthetic test image with readable text
img = np.ones((200, 700, 3), dtype=np.uint8) * 255
cv2.putText(img, "SECURE AUDIT TEST 12345", (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)

print("Testing ocr_service.extract_image...")
try:
    result = ocr_service.extract_image(img, "en")
    print("\n========== OCR RESULT ==========")
    print(f"  text:       {result['text']!r}")
    print(f"  confidence: {result['confidence']}")
    print(f"  language:   {result['language']}")
    print(f"  lines:      {result['lines']}")
    print("================================")
    print("\nSUCCESS — OCR extraction passed!")
except Exception as e:
    import traceback
    print(f"FAILED: {e}")
    traceback.print_exc()
