"""PaddleOCR integration used by the Secure Audit evidence pipeline.

Models are initialized lazily and cached per language.  This keeps API startup
fast and prevents a model download/load on every OCR request.
"""
import importlib.util
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Union

import cv2
import numpy as np
from PIL import Image


class OCRServiceError(RuntimeError):
    """A recoverable OCR setup or processing error safe to expose to an API."""


# Preserve existing client values while using PaddleOCR's language identifiers.
LANGUAGE_ALIASES = {
    "auto": os.getenv("PADDLEOCR_DEFAULT_LANGUAGE", "en"),
    "eng": "en",
    "en": "en",
    "hin": "hi",
    "hi": "hi",
    # PaddleOCR loads one recognition model at a time. English is a safe
    # fallback for the historic combined option; callers can configure another
    # model through PADDLEOCR_DEFAULT_LANGUAGE when their deployment needs it.
    "eng+hin": os.getenv("PADDLEOCR_MULTILINGUAL_LANGUAGE", "en"),
}


def check_dependencies() -> Dict[str, Any]:
    """Report optional runtime dependencies without importing/loading a model."""
    paddle_available = (
        importlib.util.find_spec("paddle") is not None
        and importlib.util.find_spec("paddleocr") is not None
    )
    poppler_path = os.getenv("POPPLER_PATH", "")
    poppler_available = bool(
        (poppler_path and Path(poppler_path).exists())
        or shutil.which("pdftoppm")
        or shutil.which("pdfinfo")
    )
    return {
        "ocr_available": paddle_available,
        "paddleocr_installed": paddle_available,
        "pdf_conversion_available": poppler_available,
        "supported_languages": sorted(set(LANGUAGE_ALIASES.values())),
    }


def preprocess_image(image_input: Union[str, Path, Image.Image, np.ndarray, bytes]) -> Image.Image:
    """Apply the established OpenCV denoise and adaptive-threshold pipeline."""
    if isinstance(image_input, (str, Path)):
        img = cv2.imread(str(image_input))
        if img is None:
            raise OCRServiceError(f"Failed to read image: {image_input}")
    elif isinstance(image_input, bytes):
        img = cv2.imdecode(np.frombuffer(image_input, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise OCRServiceError("Failed to decode image bytes")
    elif isinstance(image_input, Image.Image):
        img = np.array(image_input.convert("RGB"))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
    else:
        raise OCRServiceError("OCR input must be a path, bytes, PIL image, or numpy array")

    if img.ndim == 3:
        if img.shape[2] == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    blurred = cv2.medianBlur(gray, 3)
    thresholded = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    rgb = cv2.cvtColor(thresholded, cv2.COLOR_GRAY2RGB)
    return Image.fromarray(rgb)



class PaddleOCRService:
    """Thread-safe lazy PaddleOCR model cache and document extraction service."""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._models = {}
                    cls._instance._model_lock = threading.Lock()
                    # Paddle inference sessions are not guaranteed to be safe
                    # for concurrent use by every CPU/GPU build.
                    cls._instance._inference_lock = threading.Lock()
        return cls._instance

    @staticmethod
    def normalize_language(language: str = "auto") -> str:
        requested = (language or "auto").strip().lower()
        if requested in LANGUAGE_ALIASES:
            return LANGUAGE_ALIASES[requested]
        # PaddleOCR language codes are deliberately configurable, but reject
        # invalid values rather than letting them become a model-path argument.
        if requested.replace("_", "").isalpha():
            return requested
        raise OCRServiceError(f"Unsupported OCR language: {language}")

    def _get_model(self, language: str):
        language = self.normalize_language(language)
        if language in self._models:
            return self._models[language]
        with self._model_lock:
            if language in self._models:
                return self._models[language]
            try:
                from paddleocr import PaddleOCR
                try:
                    model = PaddleOCR(lang=language, use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
                except Exception:
                    model = PaddleOCR(use_angle_cls=True, lang=language)

            except ImportError as exc:
                raise OCRServiceError(
                    "PaddleOCR is not installed. Install backend requirements before running OCR."
                ) from exc
            except Exception as exc:
                raise OCRServiceError(
                    f"Unable to initialize PaddleOCR for '{language}'. "
                    "The first run downloads model files; check network access and model cache permissions."
                ) from exc
            self._models[language] = model
            return model

    @staticmethod
    def _parse_legacy_result(result: Any) -> List[Dict[str, Any]]:
        lines: List[Dict[str, Any]] = []
        for page in result or []:
            if not page:
                continue
            for entry in page:
                try:
                    bbox, (text, confidence) = entry
                    lines.append({"text": str(text), "confidence": float(confidence), "bbox": bbox})
                except (TypeError, ValueError):
                    continue
        return lines

    @staticmethod
    def _parse_predict_result(result: Any) -> List[Dict[str, Any]]:
        """Parse PaddleOCR 3.x OCRResult objects safely.

        PaddleOCR 3.x returns a list of ``OCRResult`` objects that support
        both dict-style key access and a ``.json()`` serialiser.  We try
        several access strategies so the parser stays compatible across minor
        PaddleOCR / PaddleX releases.

        Supported result schemas
        ------------------------
        • ``{"res": {"rec_texts": [...], "rec_scores": [...], "rec_polys": [...], ...}}``
          — PaddleOCR 3.x default (``.json()`` wrapper)
        • ``{"rec_texts": [...], "rec_scores": [...], ...}``
          — flat dict (direct dict-key access on OCRResult)
        • Legacy list-of-tuples ``[[bbox, (text, score)], ...]``
          — handled by the caller (``_parse_legacy_result``)
        """
        lines: List[Dict[str, Any]] = []
        for item in result or []:
            # ── Strategy 1: OCRResult direct dict-key access ────────────────
            # OCRResult exposes its fields as dict keys without any wrapping.
            data: Any = None
            if hasattr(item, "keys"):
                try:
                    data = dict(item)
                except Exception:
                    data = None

            # ── Strategy 2: .json() serialiser ──────────────────────────────
            if not isinstance(data, dict):
                if hasattr(item, "json"):
                    try:
                        raw = item.json() if callable(item.json) else item.json
                        if isinstance(raw, str):
                            raw = json.loads(raw)
                        if isinstance(raw, dict):
                            data = raw
                    except Exception:
                        pass

            # ── Strategy 3: plain dict / str passed in directly ─────────────
            if not isinstance(data, dict):
                if isinstance(item, dict):
                    data = item
                elif isinstance(item, str):
                    try:
                        data = json.loads(item)
                    except Exception:
                        continue

            if not isinstance(data, dict):
                continue

            # PaddleOCR 3.x .json() wraps everything under "res"
            inner = data.get("res")
            if isinstance(inner, dict):
                data = inner

            texts  = data.get("rec_texts")  or data.get("texts")  or []
            scores = data.get("rec_scores") or data.get("scores") or []
            boxes  = (
                data.get("rec_polys")
                or data.get("rec_boxes")
                or data.get("boxes")
                or []
            )

            for index, text in enumerate(texts):
                try:
                    confidence = float(scores[index]) if index < len(scores) else 0.0
                except (TypeError, ValueError, IndexError):
                    confidence = 0.0
                try:
                    bbox = boxes[index] if index < len(boxes) else None
                    # Convert numpy arrays to plain Python lists for JSON serialisation
                    if bbox is not None and hasattr(bbox, "tolist"):
                        bbox = bbox.tolist()
                except (IndexError, TypeError):
                    bbox = None
                lines.append({"text": str(text), "confidence": confidence, "bbox": bbox})

        return lines

    def extract_image(self, image_input: Union[str, Path, Image.Image, np.ndarray, bytes], language: str = "auto") -> Dict[str, Any]:
        """Extract a page's text, word/line confidence, and bounding boxes."""
        normalized_language = self.normalize_language(language)
        image = preprocess_image(image_input)
        model = self._get_model(normalized_language)
        array = np.array(image)
        try:
            with self._inference_lock:
                # PaddleOCR 3.x exposes predict() and rejects the retired
                # `cls` keyword. Prefer it even when a compatibility `ocr`
                # alias is present on the installed package.
                if hasattr(model, "predict"):
                    lines = self._parse_predict_result(list(model.predict(array)))
                elif hasattr(model, "ocr"):
                    # PaddleOCR 2.x fallback; do not pass deprecated cls.
                    lines = self._parse_legacy_result(model.ocr(array))
                else:
                    raise OCRServiceError("Installed PaddleOCR version does not expose a compatible OCR API")
        except Exception as exc:
            if isinstance(exc, OCRServiceError):
                raise
            raise OCRServiceError(f"PaddleOCR extraction failed: {exc}") from exc
        text = "\n".join(line["text"] for line in lines).strip()
        confidence = round(sum(line["confidence"] for line in lines) / len(lines), 4) if lines else 0.0
        return {"text": text, "confidence": confidence, "language": normalized_language, "lines": lines}

    def extract_document(self, source: Union[str, Path, bytes], language: str = "auto") -> List[Dict[str, Any]]:
        """Extract all pages from an image or a scanned PDF."""
        is_pdf = isinstance(source, (str, Path)) and str(source).lower().endswith(".pdf")
        if not is_pdf and isinstance(source, bytes):
            is_pdf = source[:5] == b"%PDF-"
        if not is_pdf:
            return [self.extract_image(source, language)]
        try:
            from pdf2image import convert_from_bytes, convert_from_path, pdfinfo_from_bytes, pdfinfo_from_path
            max_pages = int(os.getenv("OCR_MAX_PDF_PAGES", "50"))
            info = pdfinfo_from_bytes(source) if isinstance(source, bytes) else pdfinfo_from_path(str(source))
            page_count = int(info.get("Pages", 0))
            if page_count < 1:
                raise OCRServiceError("The PDF contains no renderable pages")
            if page_count > max_pages:
                raise OCRServiceError(f"PDF has {page_count} pages; the OCR limit is {max_pages} pages")
            conversion = convert_from_bytes if isinstance(source, bytes) else convert_from_path
            pages = conversion(source, first_page=1, last_page=page_count, thread_count=1)
        except Exception as exc:
            raise OCRServiceError(
                "Unable to render PDF pages. Ensure Poppler is installed and POPPLER_PATH is configured when needed."
            ) from exc
        return [self.extract_image(page, language) for page in pages]


ocr_service = PaddleOCRService()


def extract_text(image: Union[str, Path, Image.Image, np.ndarray, bytes], lang: str = "eng") -> Dict[str, Any]:
    """Compatibility wrapper retained for existing internal callers/tests."""
    return ocr_service.extract_image(image, lang)
