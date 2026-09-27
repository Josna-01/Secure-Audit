"""PaddleOCR integration used by the Secure Audit evidence pipeline.

Processing flow for one evidence file::

    bytes/path ──► type sniffing & validation ──► page loader (image / TIFF / PDF)
         per page: preprocess ──► PaddleOCR pipeline (orientation, detection,
                   primary recognizer) ──► per-line re-recognition with the
                   other candidate languages ──► cleaning ──► layout rebuild

Models are initialized lazily and cached per language, which keeps API start-up
fast and avoids loading a model on every request. Pure text/layout logic lives
in ``services.ocr_text``.
"""
from __future__ import annotations

import importlib.util
import io
import logging
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from . import tesseract_engine
from .ocr_text import (
    SUPPORTED_LANGUAGES,
    UNKNOWN_LANGUAGE,
    char_script,
    clean_segment,
    dedupe_overlapping,
    detect_languages,
    dominant_language,
    is_noise_segment,
    language_label,
    native_script_ratio,
    reconstruct_layout,
    resolve_languages,
    script_counts,
    weighted_confidence,
)

logger = logging.getLogger("backend.ocr")

OCRSource = Union[str, Path, bytes, Image.Image, np.ndarray]


# ── Errors ───────────────────────────────────────────────────────────────────

class OCRServiceError(RuntimeError):
    """An OCR error whose message is safe to return to API clients."""

    status_code = 500


class OCRLanguageError(OCRServiceError):
    status_code = 400


class OCRLimitError(OCRServiceError):
    status_code = 413


class OCRUnsupportedFileError(OCRServiceError):
    status_code = 415


class OCRInvalidFileError(OCRServiceError):
    """Empty, truncated, corrupted or password-protected input."""

    status_code = 422


class OCREngineUnavailableError(OCRServiceError):
    status_code = 503


class OCRProcessingError(OCRServiceError):
    status_code = 500


# ── Configuration ────────────────────────────────────────────────────────────

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Mobile models by default: on CPU they are ~8-20x faster than the PP-OCRv6
# "medium" models PaddleOCR picks for lang="en", with near-identical document
# accuracy. The English-only recognizer also cannot emit stray CJK glyphs
# (the v6 recognizer has a Chinese+English dictionary). On a GPU host set
# OCR_DET_MODEL=PP-OCRv6_medium_det for better recall on small/dense text.
DETECTION_MODEL = os.getenv("OCR_DET_MODEL", "PP-OCRv5_mobile_det")
RECOGNITION_MODELS = {
    "en": os.getenv("OCR_REC_MODEL_EN", "en_PP-OCRv5_mobile_rec"),
    "hi": os.getenv("OCR_REC_MODEL_HI", "devanagari_PP-OCRv5_mobile_rec"),
    "kn": os.getenv("OCR_REC_MODEL_KN", "ka_PP-OCRv3_mobile_rec"),
    "te": os.getenv("OCR_REC_MODEL_TE", "te_PP-OCRv5_mobile_rec"),
    "ta": os.getenv("OCR_REC_MODEL_TA", "ta_PP-OCRv5_mobile_rec"),
}
def tesseract_languages() -> List[str]:
    """Languages whose lines are recognized by Tesseract (when its data is installed)."""
    configured = os.getenv("OCR_TESSERACT_LANGUAGES", "kn,ml")
    return [code.strip() for code in configured.split(",") if code.strip() in SUPPORTED_LANGUAGES]


def _unavailable_message(language: str) -> str:
    name = SUPPORTED_LANGUAGES[language].name
    if language in RECOGNITION_MODELS:
        return f"{name} OCR model is unavailable; skipped"
    return (f"{name} recognition needs Tesseract with '{tesseract_engine.TESSERACT_CODES[language]}' "
            f"language data; {name} text was not recognized")


# Recognizers that seldom emit spaces between words; their lines are re-read
# word by word (see _split_word_crops).
SPACE_POOR_LANGUAGES = ("kn",)
SUPPORTED_IMAGE_FORMATS = "PNG, JPEG, WEBP, TIFF, BMP, GIF"
MODEL_RETRY_SECONDS = 300


def check_dependencies() -> Dict[str, Any]:
    """Report optional runtime dependencies without importing/loading a model."""
    paddle_available = (
        importlib.util.find_spec("paddle") is not None
        and importlib.util.find_spec("paddleocr") is not None
    )
    return {
        "ocr_available": paddle_available,
        "paddleocr_installed": paddle_available,
        "pdf_conversion_available": importlib.util.find_spec("pypdfium2") is not None
        or importlib.util.find_spec("pdf2image") is not None,
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "tesseract_available": tesseract_engine.tesseract_command() is not None,
        "tesseract_languages": sorted(tesseract_engine.available_languages()),
    }


# ── Input loading ────────────────────────────────────────────────────────────

_PDFIUM_LOCK = threading.Lock()  # PDFium is not thread-safe


def _read_source(source: Union[str, Path, bytes]) -> bytes:
    max_bytes = _env_int("OCR_MAX_FILE_BYTES", 50 * 1024 * 1024)
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise OCRInvalidFileError("The evidence file could not be found")
        if path.stat().st_size > max_bytes:
            raise OCRLimitError(f"The file exceeds the OCR size limit of {max_bytes // (1024 * 1024)} MB")
        data = path.read_bytes()
    else:
        data = bytes(source)
    if not data:
        raise OCRInvalidFileError("The evidence file is empty")
    if len(data) > max_bytes:
        raise OCRLimitError(f"The file exceeds the OCR size limit of {max_bytes // (1024 * 1024)} MB")
    return data


def _is_pdf(data: bytes) -> bool:
    # The PDF spec allows junk before the header; readers accept it within 1 KB.
    return b"%PDF-" in data[:1024]


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    image = ImageOps.exif_transpose(image)  # phone photos store rotation in EXIF
    if image.mode in ("I;16", "I;16B", "I;16L", "I", "F"):
        # 16/32-bit scans: stretch to 8-bit rather than clipping to white.
        array = np.asarray(image, dtype=np.float32)
        low, high = float(array.min()), float(array.max())
        array = (array - low) * (255.0 / (high - low)) if high > low else np.zeros_like(array)
        image = Image.fromarray(array.astype(np.uint8))
    if image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info):
        # Transparent pixels are black in RGB; flatten onto white paper instead.
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, rgba)
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _open_document(source: OCRSource) -> Tuple[int, Callable[[int], np.ndarray], Callable[[], None], str]:
    """Return ``(page_count, load_page, close, kind)`` for any supported input."""
    if isinstance(source, np.ndarray):
        array = source
        if array.size == 0:
            raise OCRInvalidFileError("The image is empty")
        if array.ndim == 2:
            array = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
        elif array.ndim == 3 and array.shape[2] == 4:
            array = cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
        return 1, lambda _index: array, lambda: None, "image"
    if isinstance(source, Image.Image):
        return 1, lambda _index: _pil_to_bgr(source), lambda: None, "image"

    data = _read_source(source)
    if _is_pdf(data):
        return _open_pdf(data)
    return _open_image(data)


def _open_image(data: bytes) -> Tuple[int, Callable[[int], np.ndarray], Callable[[], None], str]:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Image.DecompressionBombError as exc:
        raise OCRLimitError("The image resolution is too large to process safely") from exc
    except UnidentifiedImageError as exc:
        raise OCRUnsupportedFileError(
            f"Unsupported file type for OCR. Upload an image ({SUPPORTED_IMAGE_FORMATS}) or a PDF."
        ) from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise OCRInvalidFileError("The image file is corrupted or truncated and cannot be read") from exc

    if image.width < 2 or image.height < 2:
        raise OCRInvalidFileError("The image is empty")

    # Multi-page TIFF scans are treated as documents; animated GIFs are not.
    frames = getattr(image, "n_frames", 1) if image.format == "TIFF" else 1
    max_pages = _env_int("OCR_MAX_PDF_PAGES", 50)
    if frames > max_pages:
        raise OCRLimitError(f"The document has {frames} pages; the OCR limit is {max_pages} pages")

    def load_page(index: int) -> np.ndarray:
        try:
            image.seek(index)
            return _pil_to_bgr(image)
        except (OSError, ValueError, EOFError) as exc:
            raise OCRInvalidFileError(f"Page {index + 1} of the image is corrupted") from exc

    return frames, load_page, image.close, "image"


def _open_pdf(data: bytes) -> Tuple[int, Callable[[int], np.ndarray], Callable[[], None], str]:
    max_pages = _env_int("OCR_MAX_PDF_PAGES", 50)
    dpi = _env_int("OCR_PDF_DPI", 300)
    max_dim = _env_int("OCR_MAX_IMAGE_DIM", 2560)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return _open_pdf_with_poppler(data, max_pages, dpi)

    try:
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(data)
            page_count = len(document)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise OCRInvalidFileError("The PDF is password-protected; upload an unlocked copy") from exc
        raise OCRInvalidFileError("The PDF file is corrupted or incomplete and cannot be opened") from exc

    if page_count < 1:
        document.close()
        raise OCRInvalidFileError("The PDF contains no pages")
    if page_count > max_pages:
        document.close()
        raise OCRLimitError(f"The PDF has {page_count} pages; the OCR limit is {max_pages} pages")

    def load_page(index: int) -> np.ndarray:
        try:
            with _PDFIUM_LOCK:
                page = document[index]
                width, height = page.get_size()
                # Render at the configured DPI, but no larger than the OCR
                # working resolution (rendering bigger only to downscale later
                # wastes memory on large-format pages).
                scale = min(dpi / 72.0, max_dim / max(width, height, 1.0))
                bitmap = page.render(scale=max(scale, 1.0), fill_color=(255, 255, 255, 255))
                image = bitmap.to_pil()
                page.close()
            return _pil_to_bgr(image)
        except pdfium.PdfiumError as exc:
            raise OCRInvalidFileError(f"Page {index + 1} of the PDF is corrupted and cannot be rendered") from exc

    def close() -> None:
        with _PDFIUM_LOCK:
            document.close()

    return page_count, load_page, close, "pdf"


def _open_pdf_with_poppler(data: bytes, max_pages: int, dpi: int):
    try:
        from pdf2image import convert_from_bytes, pdfinfo_from_bytes
        from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
    except ImportError as exc:
        raise OCREngineUnavailableError("PDF support requires pypdfium2 (or pdf2image with Poppler)") from exc
    poppler_path = os.getenv("POPPLER_PATH") or None
    try:
        page_count = int(pdfinfo_from_bytes(data, poppler_path=poppler_path).get("Pages", 0))
    except (PDFPageCountError, PDFSyntaxError) as exc:
        raise OCRInvalidFileError("The PDF file is corrupted or incomplete and cannot be opened") from exc
    except Exception as exc:
        raise OCREngineUnavailableError("Unable to render PDF pages. Ensure Poppler is installed.") from exc
    if page_count < 1:
        raise OCRInvalidFileError("The PDF contains no pages")
    if page_count > max_pages:
        raise OCRLimitError(f"The PDF has {page_count} pages; the OCR limit is {max_pages} pages")

    def load_page(index: int) -> np.ndarray:
        pages = convert_from_bytes(data, dpi=dpi, first_page=index + 1, last_page=index + 1,
                                   poppler_path=poppler_path, thread_count=1)
        if not pages:
            raise OCRInvalidFileError(f"Page {index + 1} of the PDF cannot be rendered")
        return _pil_to_bgr(pages[0])

    return page_count, load_page, lambda: None, "pdf"


# ── Preprocessing ────────────────────────────────────────────────────────────

def _is_blank(gray: np.ndarray) -> bool:
    low, high = np.percentile(gray, (0.5, 99.5))
    return float(gray.std()) < 2.5 and (high - low) < 16


def _noise_sigma(gray: np.ndarray) -> float:
    """Estimate Gaussian noise (Immerkær), ignoring strong edges such as text strokes."""
    small = gray if max(gray.shape) <= 1200 else cv2.resize(
        gray, None, fx=1200 / max(gray.shape), fy=1200 / max(gray.shape), interpolation=cv2.INTER_AREA)
    as_float = small.astype(np.float32)
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)
    response = np.abs(cv2.filter2D(as_float, -1, kernel))[1:-1, 1:-1]
    gradient = cv2.magnitude(cv2.Sobel(as_float, cv2.CV_32F, 1, 0), cv2.Sobel(as_float, cv2.CV_32F, 0, 1))[1:-1, 1:-1]
    flat = response[gradient < np.percentile(gradient, 80)]
    if flat.size == 0:
        return 0.0
    return float(np.mean(flat) * math.sqrt(math.pi / 2) / 6)


def _estimate_page_skew(gray: np.ndarray, max_angle: float = 45.0) -> float:
    """Projection-profile skew estimate in degrees (0.0 when not confident).

    Text rows produce sharply peaked horizontal projections when the page is
    level. Searching ±45° covers every tilt; larger turns (90/180/270°) are
    left to PaddleOCR's document-orientation model. Photos and sparse pages
    are skipped because the profile carries no reliable signal for them.
    """
    scale = 800 / max(gray.shape)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    _, ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = float(np.count_nonzero(ink)) / ink.size
    if not 0.005 <= ink_ratio <= 0.3:
        return 0.0
    # Pad to the diagonal so large test rotations do not clip the corners.
    h, w = ink.shape
    diagonal = int(math.ceil(math.hypot(h, w)))
    top, left = (diagonal - h) // 2, (diagonal - w) // 2
    ink = cv2.copyMakeBorder(ink, top, diagonal - h - top, left, diagonal - w - left, cv2.BORDER_CONSTANT, value=0)
    center = (diagonal / 2, diagonal / 2)

    def sharpness(angle: float) -> float:
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(ink, matrix, (diagonal, diagonal), flags=cv2.INTER_NEAREST, borderValue=0)
        return float(np.var(rotated.sum(axis=1, dtype=np.float64)))

    coarse = {angle: sharpness(angle) for angle in np.arange(-max_angle, max_angle + 0.01, 1.0)}
    best = max(coarse, key=coarse.get)
    fine = {angle: sharpness(angle) for angle in np.arange(best - 1.0, best + 1.01, 0.1)}
    best = max(fine, key=fine.get)
    baseline = coarse.get(0.0) or sharpness(0.0)
    # Only rotate when levelling clearly sharpens the text rows.
    if abs(best) < 0.3 or fine[best] < baseline * 1.15:
        return 0.0
    return float(round(best, 2))


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w, new_h = int(h * sin + w * cos), int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - w / 2
    matrix[1, 2] += new_h / 2 - h / 2
    return cv2.warpAffine(image, matrix, (new_w, new_h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def preprocess_page(image: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Prepare a BGR page for PaddleOCR without degrading clean input.

    PaddleOCR's DBNet detector and CRNN/SVTR recognizers are trained on natural
    colour images, so binarization and blanket filtering are deliberately
    avoided. Each step below is applied only when the page needs it:

    * downscale oversized pages / upscale low-resolution scans
    * denoise visibly noisy scans (edge-aware noise estimate)
    * local contrast enhancement (CLAHE) for faded or low-contrast pages
    * skew correction for tilted scans (90°/180° turns are handled later by
      PaddleOCR's document-orientation model)
    """
    info: Dict[str, Any] = {"original_width": int(image.shape[1]), "original_height": int(image.shape[0]),
                            "scale": 1.0, "skew_angle": 0.0, "enhancements": [], "blank": False}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if _is_blank(gray):
        info["blank"] = True
        return image, info

    max_dim = _env_int("OCR_MAX_IMAGE_DIM", 2560)
    min_dim = _env_int("OCR_MIN_IMAGE_DIM", 1600)
    longest = max(image.shape[:2])
    if longest > max_dim:
        info["scale"] = max_dim / longest
        image = cv2.resize(image, None, fx=info["scale"], fy=info["scale"], interpolation=cv2.INTER_AREA)
        info["enhancements"].append("downscaled")

    # Denoise at native resolution (before any upscaling magnifies the noise).
    noise = _noise_sigma(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    if noise > _env_float("OCR_DENOISE_THRESHOLD", 8.0) and max(image.shape[:2]) <= 3000:
        strength = float(min(12.0, noise * 0.8))
        image = cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
        info["enhancements"].append("denoised")

    if longest < min_dim:
        factor = min(min_dim / longest, 3.0)
        info["scale"] = factor
        image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        info["enhancements"].append("upscaled")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Contrast between the paper (median) and the darkest ink; a global
    # percentile range would misjudge clean pages that are mostly white.
    paper, ink = float(np.median(gray)), float(np.percentile(gray, 0.2))
    if paper - ink < 100:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lightness, a_channel, b_channel = cv2.split(lab)
        lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
        image = cv2.cvtColor(cv2.merge((lightness, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
        info["enhancements"].append("contrast_enhanced")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if _env_bool("OCR_DESKEW", True):
        skew = _estimate_page_skew(gray)
        if skew:
            image = _rotate(image, skew)
            info["skew_angle"] = skew
            info["enhancements"].append("deskewed")

    return image, info


# Backwards-compatible helper used by diagnostic scripts.
def preprocess_image(image_input: OCRSource) -> Image.Image:
    _count, load_page, close, _kind = _open_document(image_input)
    try:
        processed, _info = preprocess_page(load_page(0))
    finally:
        close()
    return Image.fromarray(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))


# ── Recognition helpers ──────────────────────────────────────────────────────

def _result_dict(item: Any) -> Dict[str, Any]:
    """Normalise a PaddleOCR 3.x ``OCRResult`` into a plain dict."""
    data: Any = item
    if not isinstance(data, dict) and hasattr(item, "keys"):
        data = {key: item[key] for key in item.keys()}
    if isinstance(data, dict) and isinstance(data.get("res"), dict):
        data = data["res"]
    return data if isinstance(data, dict) else {}


def _to_list(value: Any) -> Any:
    return value.tolist() if hasattr(value, "tolist") else value


def _crop_line(image: np.ndarray, polygon: Any, orientation: int) -> np.ndarray:
    """Perspective-crop a text line the same way PaddleOCR's pipeline does."""
    points = np.array(polygon, dtype=np.float32).reshape(-1, 2)
    if len(points) != 4:
        x0, y0 = points.min(axis=0)
        x1, y1 = points.max(axis=0)
        points = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    width = int(max(np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])))
    height = int(max(np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2])))
    width, height = max(width, 1), max(height, 1)
    target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(points, target), (width, height),
                               borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    if height / width >= 1.5:
        crop = np.rot90(crop)
    if orientation == 1:  # textline classifier: 1 == upside down
        crop = cv2.rotate(crop, cv2.ROTATE_180)
    return np.ascontiguousarray(crop)


def _split_word_crops(crop: np.ndarray) -> List[np.ndarray]:
    """Split a line crop into word crops at wide blank column runs.

    Used for recognizers that rarely emit spaces (the Kannada model). Kannada
    aksharas are often disconnected, so only gaps clearly wider than the
    typical intra-word gap count as word boundaries.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    has_ink = ink.sum(axis=0) > 0
    columns = np.flatnonzero(has_ink)
    if columns.size == 0:
        return [crop]
    first, last = int(columns[0]), int(columns[-1])
    gaps, start = [], None
    for x in range(first, last + 1):
        if not has_ink[x] and start is None:
            start = x
        elif has_ink[x] and start is not None:
            gaps.append((start, x))
            start = None
    if not gaps:
        return [crop]
    widths = np.array([end - begin for begin, end in gaps])
    threshold = max(0.22 * crop.shape[0], 2.0 * float(np.median(widths)))
    cuts = [(begin + end) // 2 for (begin, end), width in zip(gaps, widths) if width >= threshold]
    if not cuts:
        return [crop]
    bounds = [max(0, first - 2)] + cuts + [min(crop.shape[1], last + 3)]
    return [np.ascontiguousarray(crop[:, left:right]) for left, right in zip(bounds, bounds[1:]) if right - left > 2]


def _reading_score(text: str, confidence: float, language: str) -> float:
    """Confidence discounted by how much of the output is outside the model's script."""
    return confidence * (0.5 + 0.5 * native_script_ratio(text, language))


_DIGIT_RUN = re.compile(r"\d+")


def restore_dropped_digits(tesseract_text: str, paddle_text: str) -> str:
    """Put back leading digits Tesseract dropped, using PaddleOCR's reading.

    On some typefaces Tesseract loses a leading "1" ("17:30" -> "7:30",
    "154" -> "54"). Digit runs of both readings are aligned; where Tesseract's
    run is a strict suffix of PaddleOCR's aligned run, PaddleOCR's is used.
    Any other disagreement is left as Tesseract read it.
    """
    ours = [m for m in _DIGIT_RUN.finditer(tesseract_text)]
    theirs = [m.group() for m in _DIGIT_RUN.finditer(paddle_text)]
    if not ours or not theirs:
        return tesseract_text
    replacements = {}
    matcher = SequenceMatcher(None, [m.group() for m in ours], theirs, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        # Right-align unequal blocks: stray runs (misread marks) tend to come
        # before the real value, e.g. "(7 ) 13:30" vs "(समय से): 3:30".
        count = min(i2 - i1, j2 - j1)
        for offset in range(1, count + 1):
            short, long_ = ours[i2 - offset].group(), theirs[j2 - offset]
            if len(long_) > len(short) and long_.endswith(short):
                replacements[i2 - offset] = long_
    if not replacements:
        return tesseract_text
    pieces, last = [], 0
    for index, match in enumerate(ours):
        if index in replacements:
            pieces += [tesseract_text[last:match.start()], replacements[index]]
            last = match.end()
    return "".join(pieces) + tesseract_text[last:]


def _adds_missing_script(current: str, candidate: str, score: float, language: str) -> bool:
    """True when ``candidate`` is the same line plus words the current reading dropped.

    A confident English reading of "District (जिला): ROURKELA" silently omits
    the Hindi ("District():ROURKELA"). A reading that agrees on the Latin text
    and adds the missing script is strictly more complete.
    """
    script = SUPPORTED_LANGUAGES[language].script
    if language == "en" or score < 0.7 or script_counts(current).get(script, 0):
        return False
    if script_counts(candidate).get(script, 0) < 2:
        return False

    def latin(value: str) -> str:
        return "".join(char.casefold() for char in value if char.isascii() and char.isalnum())

    current_latin, candidate_latin = latin(current), latin(candidate)
    if len(current_latin) < 3:
        return False
    return SequenceMatcher(None, current_latin, candidate_latin).ratio() >= 0.8


def _own_script_ratio(text: str, language: str) -> float:
    counts = script_counts(text)
    total = sum(counts.values())
    return counts.get(SUPPORTED_LANGUAGES[language].script, 0) / total if total else 0.0


# ── Service ──────────────────────────────────────────────────────────────────

class PaddleOCRService:
    """Thread-safe lazy PaddleOCR model cache and document extraction service."""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._pipelines = {}
                    instance._recognizers = {}
                    instance._load_failures = {}
                    instance._model_lock = threading.Lock()
                    # Paddle inference sessions are not guaranteed to be safe
                    # for concurrent use by every CPU/GPU build.
                    instance._inference_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    @staticmethod
    def normalize_language(language: str = "auto") -> str:
        """Primary ISO language code for a client value (kept for older callers)."""
        return PaddleOCRService.resolve_languages(language)[0]

    @staticmethod
    def resolve_languages(language: Optional[str]) -> List[str]:
        try:
            return resolve_languages(language)
        except ValueError as exc:
            raise OCRLanguageError(str(exc)) from exc

    # Model loading -----------------------------------------------------------

    def _load_cached(self, cache: Dict[str, Any], key: str, factory: Callable[[], Any]) -> Any:
        if key in cache:
            return cache[key]
        with self._model_lock:
            if key in cache:
                return cache[key]
            failed_at = self._load_failures.get(key)
            if failed_at and time.monotonic() - failed_at < MODEL_RETRY_SECONDS:
                return None
            try:
                model = factory()
            except ImportError as exc:
                raise OCREngineUnavailableError("PaddleOCR is not installed on the server") from exc
            except Exception as exc:  # model download / init failure
                logger.warning("OCR model load failed for %s: %s", key, exc)
                self._load_failures[key] = time.monotonic()
                return None
            self._load_failures.pop(key, None)
            cache[key] = model
            return model

    def _get_pipeline(self, language: str):
        def factory():
            from paddleocr import PaddleOCR
            return PaddleOCR(
                text_detection_model_name=DETECTION_MODEL,
                text_recognition_model_name=RECOGNITION_MODELS[language],
                use_doc_orientation_classify=_env_bool("OCR_DOC_ORIENTATION", True),
                use_doc_unwarping=_env_bool("OCR_DOC_UNWARPING", False),
                # Off by default: the line classifier flags upright Devanagari
                # as upside down (the headline stroke looks like a baseline),
                # flipping every Hindi line. Whole-page 90/180/270° rotation is
                # still corrected by the document orientation model above.
                use_textline_orientation=_env_bool("OCR_TEXTLINE_ORIENTATION", False),
            )
        return self._load_cached(self._pipelines, f"pipeline:{language}", factory)

    def _get_recognizer(self, language: str):
        def factory():
            from paddleocr import TextRecognition
            return TextRecognition(model_name=RECOGNITION_MODELS[language])
        return self._load_cached(self._recognizers, f"recognizer:{language}", factory)

    # Recognition -------------------------------------------------------------

    def _run_pipeline(self, image: np.ndarray, languages: List[str], warnings: List[str]):
        # Malayalam has no PaddleOCR recognizer; such requests still use a
        # PaddleOCR pipeline for detection and layout (English as a carrier).
        candidates = [language for language in languages if language in RECOGNITION_MODELS] or ["en"]
        for language in candidates:
            pipeline = self._get_pipeline(language)
            if pipeline is None:
                _add_warning(warnings, f"{SUPPORTED_LANGUAGES[language].name} OCR model is unavailable; skipped")
                continue
            with self._inference_lock:
                results = list(pipeline.predict(image))
            return language, _result_dict(results[0]) if results else {}
        raise OCREngineUnavailableError("No OCR model could be loaded. Check the server's PaddleOCR installation.")

    def _read_crops(self, language: str, crops: List[np.ndarray], engine: str) -> Optional[List[Tuple[str, float]]]:
        """Recognize line crops with one language's model → ``[(text, score)]``, or None if unavailable."""
        if engine == "tesseract":
            try:
                return tesseract_engine.read_lines(crops, language)
            except Exception as exc:
                logger.warning("Tesseract recognition failed for %s: %s", language, exc)
                return None
        recognizer = self._get_recognizer(language)
        if recognizer is None:
            return None
        with self._inference_lock:
            outputs = [_result_dict(output) for output in recognizer.predict(crops, batch_size=16)]
        return [(str(output.get("rec_text") or ""), float(output.get("rec_score") or 0.0)) for output in outputs]

    def _rerecognize(self, lines: List[Dict[str, Any]], crop: Callable[[int], np.ndarray], alternates: List[str],
                     warnings: List[str]) -> None:
        """Identify each line's language by re-reading it with the other models.

        Only lines the primary model is unsure of are re-read. Once another
        language wins any line, the page is known to be mixed and the other
        lines are also compared against that language, which catches
        confident-but-wrong primary readings. Each language is read with the
        engine that produces its final text (Tesseract for Kannada and
        Malayalam when installed), and the languages are read concurrently.
        """
        threshold = _env_float("OCR_LANGUAGE_RECHECK_THRESHOLD", 0.93)
        margin = 0.02
        prefer_tesseract = set(tesseract_languages()) & tesseract_engine.available_languages()

        def engine_for(language: str) -> str:
            return "tesseract" if language in prefer_tesseract or language not in RECOGNITION_MODELS else "paddle"

        def read_all(languages: List[str], indexes: List[int]) -> Dict[str, Optional[List[Tuple[str, float]]]]:
            crops = [crop(i) for i in indexes]
            # Tesseract runs in separate processes and PaddleOCR releases the
            # GIL during inference, so the languages can be read in parallel.
            with ThreadPoolExecutor(max_workers=max(1, len(languages))) as pool:
                futures = {language: pool.submit(self._read_crops, language, crops, engine_for(language))
                           for language in languages}
            return {language: future.result() for language, future in futures.items()}

        def apply(language: str, indexes: List[int], readings: Optional[List[Tuple[str, float]]]) -> int:
            if readings is None:
                _add_warning(warnings, _unavailable_message(language))
                return 0
            wins = 0
            for index, (text, score) in zip(indexes, readings):
                line = lines[index]
                if _own_script_ratio(text, language) < 0.2:
                    continue  # e.g. the Hindi model re-reading an English line
                own_letters = script_counts(text).get(SUPPORTED_LANGUAGES[language].script, 0)
                if language != "en" and own_letters < 3:
                    continue  # 1-2 glyph readings of stamps or specks are not evidence of a script
                better = _reading_score(text, score, language) > _reading_score(line["text"], line["confidence"], line["model_language"]) + margin
                if better or _adds_missing_script(line["text"], text, score, language):
                    engine = engine_for(language)
                    if engine == "tesseract" and line.get("engine") == "paddle":
                        text = restore_dropped_digits(text, line["text"])
                    line.update(text=text, confidence=score, model_language=language, engine=engine)
                    wins += 1
            return wins

        uncertain = [i for i, line in enumerate(lines)
                     if _reading_score(line["text"], line["confidence"], line["model_language"]) < threshold]
        if not uncertain:
            return
        readings = read_all(alternates, uncertain)
        # Applied in the configured language order so results are deterministic.
        present = [language for language in alternates if apply(language, uncertain, readings[language]) > 0]
        uncertain_set = set(uncertain)
        remaining = [i for i in range(len(lines)) if i not in uncertain_set]
        if present and remaining:
            readings = read_all(present, remaining)
            for language in present:
                apply(language, remaining, readings[language])

    def _fix_upside_down_lines(self, lines: List[Dict[str, Any]], crop: Callable[[int], np.ndarray],
                               language: str) -> None:
        """Re-read low-confidence lines rotated 180° and keep clearly better readings.

        Replaces PaddleOCR's text-line orientation classifier, which flips
        upright Devanagari; recognition confidence is a script-neutral signal
        (an upside-down line reads as low-confidence gibberish, e.g.
        "spoqpm" for "methods").
        """
        indexes = [i for i, line in enumerate(lines) if line["confidence"] < 0.85 and line["orientation"] != 1]
        if not indexes or language not in RECOGNITION_MODELS:
            return
        flipped = [cv2.rotate(crop(i), cv2.ROTATE_180) for i in indexes]
        readings = self._read_crops(language, flipped, "paddle") or []
        for index, (text, score) in zip(indexes, readings):
            # An absolute bar too: a line in another script reads badly either
            # way up, and a slightly-less-bad flipped reading must not win.
            if score >= 0.85 and score >= lines[index]["confidence"] + 0.1 and text.strip():
                lines[index].update(text=text, confidence=score, orientation=1)

    def _refine_with_tesseract(self, lines: List[Dict[str, Any]], crop: Callable[[int], np.ndarray],
                               warnings: List[str]) -> None:
        """Re-read lines of Tesseract-preferred scripts with Tesseract.

        Benchmarks on this project's documents showed Tesseract (tessdata_best)
        clearly ahead of PaddleOCR for Kannada; Malayalam has no PaddleOCR model.
        Hindi stays on PaddleOCR: on real FIR scans Tesseract dropped leading
        digits ("17:30" -> "7:30") where PaddleOCR read them correctly. PaddleOCR's reading is
        kept whenever Tesseract returns nothing usable for a line.
        """
        for language in tesseract_languages():
            indexes = [i for i, line in enumerate(lines)
                       if line["model_language"] == language and line.get("engine") != "tesseract"]
            if not indexes:
                continue
            if language not in tesseract_engine.available_languages():
                _add_warning(warnings, f"{SUPPORTED_LANGUAGES[language].name} was read with PaddleOCR because Tesseract "
                                       f"'{tesseract_engine.TESSERACT_CODES[language]}' data is not installed (lower accuracy)")
                continue
            readings = self._read_crops(language, [crop(i) for i in indexes], "tesseract") or []
            for index, (text, score) in zip(indexes, readings):
                if text.strip() and score >= 0.3 and _own_script_ratio(text, language) >= 0.5:
                    text = restore_dropped_digits(text, lines[index]["text"])
                    lines[index].update(text=text, confidence=score, engine="tesseract")

    def _restore_word_spacing(self, lines: List[Dict[str, Any]], image: np.ndarray) -> None:
        """Re-read space-less lines word by word for models that drop spaces."""
        for language in SPACE_POOR_LANGUAGES:
            targets = [line for line in lines if line["model_language"] == language and line.get("engine") == "paddle"
                       and " " not in line["text"].strip() and len(line["text"]) >= 6]
            if not targets:
                continue
            recognizer = self._get_recognizer(language)
            if recognizer is None:
                continue
            for line in targets:
                words = _split_word_crops(_crop_line(image, line["bbox"], line["orientation"]))
                if len(words) < 2:
                    continue
                with self._inference_lock:
                    outputs = [_result_dict(output) for output in recognizer.predict(words, batch_size=16)]
                texts = [str(output.get("rec_text") or "").strip() for output in outputs]
                scores = [float(output.get("rec_score") or 0.0) for output in outputs]
                joined = " ".join(text for text in texts if text)
                confidence = weighted_confidence(zip(texts, scores))
                # Accept unless word-level reading is clearly worse than the line reading.
                if joined and confidence >= line["confidence"] - 0.05:
                    line.update(text=joined, confidence=confidence)

    def _recognize(self, image: np.ndarray, languages: List[str], warnings: List[str]) -> Dict[str, Any]:
        primary, data = self._run_pipeline(image, languages, warnings)
        texts = list(data.get("rec_texts") or [])
        scores = list(data.get("rec_scores") or [])
        polys = list(data.get("rec_polys") or data.get("rec_boxes") or [])
        orientations = list(data.get("textline_orientation_angles") or [])
        preprocessor = data.get("doc_preprocessor_res")
        preprocessor = _result_dict(preprocessor) if preprocessor is not None else {}
        base_image = preprocessor.get("output_img")
        base_image = base_image if isinstance(base_image, np.ndarray) else image

        lines = []
        for index, text in enumerate(texts):
            if index >= len(polys):
                break
            lines.append({
                "text": str(text),
                "confidence": float(scores[index]) if index < len(scores) else 0.0,
                "bbox": _to_list(polys[index]),
                "orientation": int(orientations[index]) if index < len(orientations) else 0,
                "model_language": primary,
                "engine": "paddle",
            })
        crops: Dict[Tuple[int, int], np.ndarray] = {}

        def crop(index: int) -> np.ndarray:
            key = (index, lines[index]["orientation"])
            if key not in crops:
                crops[key] = _crop_line(base_image, lines[index]["bbox"], lines[index]["orientation"])
            return crops[key]

        self._fix_upside_down_lines(lines, crop, primary)
        alternates = [language for language in languages if language != primary]
        # When the pipeline language was not requested (it only carries
        # detection, e.g. for Malayalam), its readings must not out-score the
        # requested languages; they are kept only where nothing else reads the line.
        carrier = primary not in languages
        if carrier:
            for line in lines:
                line["carrier_confidence"], line["confidence"] = line["confidence"], 0.0
        if lines and alternates:
            self._rerecognize(lines, crop, alternates, warnings)
        for line in lines:
            if "carrier_confidence" in line:
                confidence = line.pop("carrier_confidence")
                if line["model_language"] == primary:
                    line["confidence"] = confidence
        if lines:
            self._refine_with_tesseract(lines, crop, warnings)
            self._restore_word_spacing(lines, base_image)
        return {
            "lines": lines,
            "rotation": int(preprocessor.get("angle") or 0) if preprocessor else 0,
            "width": int(base_image.shape[1]),
            "height": int(base_image.shape[0]),
        }

    # Public API --------------------------------------------------------------

    def extract_page(self, image: np.ndarray, languages: List[str], page_number: int = 1) -> Dict[str, Any]:
        """OCR a single BGR page image and return a page result dict."""
        started = time.perf_counter()
        warnings: List[str] = []
        processed, prep = preprocess_page(image)
        page: Dict[str, Any] = {
            "page_number": page_number, "status": "success", "text": "", "confidence": 0.0,
            "language": UNKNOWN_LANGUAGE, "detected_languages": [], "line_count": 0,
            "lines": [], "tables": [], "warnings": warnings,
            "width": prep["original_width"], "height": prep["original_height"],
            "rotation": 0, "skew_angle": prep["skew_angle"], "preprocessing": prep["enhancements"],
        }
        if prep["blank"]:
            page["status"] = "empty"
            _add_warning(warnings, "The page is blank; no text to extract")
            page["processing_time_ms"] = _elapsed_ms(started)
            return page

        recognized = self._recognize(processed, languages, warnings)
        page["rotation"] = recognized["rotation"]
        # Unmodified recognizer output (before cleaning/layout), kept for audit.
        page["raw_text"] = "\n".join(line["text"] for line in recognized["lines"])

        collapse = _env_bool("OCR_COLLAPSE_DUPLICATE_WORDS", True)
        min_confidence = _env_float("OCR_MIN_LINE_CONFIDENCE", 0.35)
        lines = []
        for line in recognized["lines"]:
            text = clean_segment(line["text"], collapse_duplicates=collapse)
            if line["confidence"] < min_confidence or is_noise_segment(text, line["confidence"]):
                continue
            lines.append({
                "text": text,
                "confidence": round(line["confidence"], 4),
                "language": dominant_language(text) if any(char_script(c) for c in text) else line["model_language"],
                "engine": line.get("engine", "paddle"),
                # Coordinates are in the orientation-corrected, preprocessed
                # page frame; divide by ``scale`` for original pixel units.
                "bbox": line["bbox"],
            })
        lines = dedupe_overlapping(lines)
        text, tables = reconstruct_layout(lines)

        detected = detect_languages(text)
        page.update(
            text=text,
            confidence=weighted_confidence((line["text"], line["confidence"]) for line in lines),
            detected_languages=detected,
            language=language_label(detected),
            line_count=len(lines),
            lines=lines,
            tables=tables,
            scale=round(prep["scale"], 4),
        )
        if not text:
            page["status"] = "empty"
            _add_warning(warnings, "No readable text was detected on this page")
        page["processing_time_ms"] = _elapsed_ms(started)
        return page

    def extract_document(self, source: OCRSource, language: str = "auto") -> Dict[str, Any]:
        """Extract every page of an image, multi-page TIFF or PDF.

        Pages are processed one at a time (bounded memory). A page that fails
        is reported with ``status="failed"`` while the others still complete;
        the call only raises when no page could be processed.
        """
        started = time.perf_counter()
        languages = self.resolve_languages(language)
        page_count, load_page, close, kind = _open_document(source)
        pages: List[Dict[str, Any]] = []
        try:
            for index in range(page_count):
                page_started = time.perf_counter()
                try:
                    pages.append(self.extract_page(load_page(index), languages, page_number=index + 1))
                except (OCREngineUnavailableError, OCRLimitError):
                    raise
                except Exception as exc:
                    logger.exception("OCR failed on page %s", index + 1)
                    message = str(exc) if isinstance(exc, OCRServiceError) else "OCR processing failed on this page"
                    pages.append(_failed_page(index + 1, message, _elapsed_ms(page_started)))
        finally:
            close()

        if pages and all(page["status"] == "failed" for page in pages):
            reasons = {page["error"] for page in pages}
            raise OCRProcessingError(reasons.pop() if len(reasons) == 1 else "OCR processing failed on every page")
        return build_document_result(pages, languages, kind, _elapsed_ms(started))

    def extract_image(self, image_input: OCRSource, language: str = "auto") -> Dict[str, Any]:
        """Single-image helper retained for diagnostic scripts."""
        result = self.extract_document(image_input, language)
        page = result["pages"][0]
        return {**page, "text": result["text"], "confidence": result["confidence"]}


def build_document_result(pages: List[Dict[str, Any]], languages: List[str], kind: str,
                          processing_time_ms: int) -> Dict[str, Any]:
    text = "\n\n".join(page["text"] for page in pages if page.get("text")).strip()
    detected = detect_languages(text)
    warnings = [f"Page {page['page_number']}: {warning}"
                for page in pages for warning in page.get("warnings", [])]
    return {
        "text": text,
        "confidence": weighted_confidence((page.get("text", ""), page.get("confidence", 0.0)) for page in pages),
        "language": language_label(detected),
        "detected_languages": detected,
        "requested_languages": languages,
        "pages": pages,
        "total_pages": len(pages),
        "document_type": kind,
        "processing_time_ms": processing_time_ms,
        "warnings": warnings,
    }


def _failed_page(page_number: int, message: str, processing_time_ms: int) -> Dict[str, Any]:
    return {
        "page_number": page_number, "status": "failed", "error": message, "text": "",
        "confidence": 0.0, "language": UNKNOWN_LANGUAGE, "detected_languages": [], "line_count": 0,
        "lines": [], "tables": [], "warnings": [message], "processing_time_ms": processing_time_ms,
    }


def _add_warning(warnings: List[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


ocr_service = PaddleOCRService()


def extract_text(image: OCRSource, lang: str = "auto") -> Dict[str, Any]:
    """Compatibility wrapper retained for existing internal callers/tests."""
    return ocr_service.extract_image(image, lang)
