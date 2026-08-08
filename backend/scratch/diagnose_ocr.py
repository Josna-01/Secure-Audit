"""Diagnostic script: prints the raw PaddleOCR predict() output so we can
understand the actual result format installed in this environment.
Run from the backend directory:
    .\\venv\\Scripts\\python.exe scratch\\diagnose_ocr.py
"""
import os
import sys
import traceback
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── 1. Build a clean synthetic test image ─────────────────────────────────────
img = np.ones((200, 700, 3), dtype=np.uint8) * 255
cv2.putText(img, "SECURE AUDIT TEST 12345", (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)

from services.ocr_service import preprocess_image

proc = preprocess_image(img)
array = np.array(proc)
print(f"Input array shape: {array.shape}  dtype: {array.dtype}")

# ── 2. Initialise PaddleOCR (use the same fallback logic as the service) ──────
from paddleocr import PaddleOCR

print("\n--- Initialising PaddleOCR ---")
try:
    model = PaddleOCR(lang="en",
                      use_doc_orientation_classify=False,
                      use_doc_unwarping=False,
                      use_textline_orientation=False)
    print("PaddleOCR 3.x init OK")
    mode = "predict"
except Exception as e:
    print(f"PaddleOCR 3.x init failed ({e}), falling back to 2.x")
    model = PaddleOCR(use_angle_cls=True, lang="en")
    mode = "ocr"

# ── 3. Run inference ──────────────────────────────────────────────────────────
print(f"\n--- Running inference (mode={mode}) ---")
try:
    if mode == "predict":
        raw = list(model.predict(array))
    else:
        raw = model.ocr(array)

    print("\n========== RAW OCR RESULT ==========")
    print(f"type(raw):            {type(raw)}")
    print(f"len(raw):             {len(raw)}")
    for i, item in enumerate(raw):
        print(f"\n  raw[{i}]:")
        print(f"    type:  {type(item)}")
        if hasattr(item, "__dict__"):
            print(f"    __dict__ keys: {list(item.__dict__.keys())[:20]}")
        if hasattr(item, "json"):
            try:
                j = item.json() if callable(item.json) else item.json
                print(f"    .json(): {repr(j)[:500]}")
            except Exception as je:
                print(f"    .json() ERROR: {je}")
        if hasattr(item, "keys"):
            print(f"    dict keys: {list(item.keys())}")
        if hasattr(item, "__iter__") and not isinstance(item, (str, bytes, dict)):
            try:
                sub = list(item)
                print(f"    iter len: {len(sub)}")
                for j2, s in enumerate(sub[:3]):
                    print(f"      [{j2}] type={type(s)}  val={repr(s)[:200]}")
            except Exception:
                pass
        print(f"    repr: {repr(item)[:500]}")
    print("====================================")

except Exception as exc:
    print(f"\nInference failed: {exc}")
    traceback.print_exc()
