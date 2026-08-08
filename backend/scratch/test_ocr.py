import os
import sys
from dotenv import load_dotenv

# Ensure backend folder is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from services import ocr_service

print("="*60)
print("RUNNING LOCAL OCR PIPELINE VALIDATION")
print("="*60)

# Check dependencies
status = ocr_service.check_dependencies()
print("Pre-flight Check status:")
print(f"  PaddleOCR Installed: {status['paddleocr_installed']}")
print(f"  PDF Conversion:      {status['pdf_conversion_available']}")
print(f"  OCR Available:       {status['ocr_available']}")
print("-"*60)

sample_image = "temp.jpg"
if not os.path.exists(sample_image):
    # Try parent directory or current directory
    if os.path.exists("../temp.jpg"):
        sample_image = "../temp.jpg"
    elif os.path.exists("backend/temp.jpg"):
        sample_image = "backend/temp.jpg"

if not os.path.exists(sample_image):
    print(f"Error: Sample image '{sample_image}' not found for testing.")
    sys.exit(1)

print(f"Found sample image at: {sample_image}")

try:
    print("Step 1: Running image preprocessing (grayscale -> median blur -> adaptive threshold)...")
    processed_img = ocr_service.preprocess_image(sample_image)
    print("  Preprocessing complete!")
    
    print("Step 2: Executing PaddleOCR text extraction (eng)...")
    result = ocr_service.extract_text(processed_img, lang="eng")
    
    print("="*60)
    print("OCR EXTRACTION RESULT")
    print("="*60)
    print(f"Language:   {result['language']}")
    print(f"Confidence: {result['confidence'] * 100}%")
    print("Text:")
    print("-" * 40)
    print(result['text'][:500] + ("..." if len(result['text']) > 500 else ""))
    print("-" * 40)
    
except Exception as e:
    print("Pipeline check failed with error:", e)
