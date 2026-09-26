import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import OCRResult

db = SessionLocal()
try:
    num_deleted = db.query(OCRResult).delete()
    db.commit()
    print(f"CLEARED_SUCCESS: Deleted {num_deleted} cached OCR result records from database.")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
