"""Download Tesseract language data used by the OCR pipeline.

Fetches the high-accuracy LSTM models (tessdata_best) from the official
tesseract-ocr GitHub repository into backend/tessdata/ (git-ignored), which
the OCR service uses automatically. Tesseract itself must be installed
separately (Windows: https://github.com/UB-Mannheim/tesseract/wiki).

Usage:  python setup_tessdata.py [hi kn ml ...]   (default: OCR_TESSERACT_LANGUAGES or kn,ml; English is always included)
"""
import os
import sys
import urllib.request
from pathlib import Path

CODES = {"en": "eng", "hi": "hin", "kn": "kan", "te": "tel", "ta": "tam", "ml": "mal"}
SOURCE = "https://github.com/tesseract-ocr/tessdata_best/raw/main/{code}.traineddata"
TARGET = Path(__file__).resolve().parent / "tessdata"


def main(languages):
    TARGET.mkdir(exist_ok=True)
    for language in languages:
        code = CODES.get(language, language)
        path = TARGET / f"{code}.traineddata"
        if path.exists():
            print(f"{code}: already present")
            continue
        print(f"{code}: downloading ...", end=" ", flush=True)
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(SOURCE.format(code=code), partial)
        partial.replace(path)
        print(f"{path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    requested = sys.argv[1:] or os.getenv("OCR_TESSERACT_LANGUAGES", "kn,ml").split(",")
    # English is always fetched: Indic models are combined with it ("hin+eng")
    # to read the English words mixed into Indian documents.
    main(["en"] + [language.strip() for language in requested if language.strip() not in ("", "en")])
