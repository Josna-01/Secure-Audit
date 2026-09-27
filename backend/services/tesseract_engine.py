"""Tesseract 5 (LSTM) line recognizer used alongside PaddleOCR.

PaddleOCR detects and lays out every page; Tesseract only *recognizes* the
text lines of scripts where it measured more accurate (Kannada) or
where PaddleOCR has no model at all (Malayalam).

All line crops for one language are stacked into a single image and read in
one Tesseract call (starting a process and loading a model per line would be
far too slow). The TSV output is mapped back to crops by vertical position.

Tesseract is optional: when the binary or a language's ``.traineddata`` is
missing, callers fall back to PaddleOCR for that language.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Set, Tuple

import cv2
import numpy as np

logger = logging.getLogger("backend.ocr.tesseract")

TESSERACT_CODES = {"en": "eng", "hi": "hin", "kn": "kan", "te": "tel", "ta": "tam", "ml": "mal"}
_WINDOWS_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_BACKEND_TESSDATA = Path(__file__).resolve().parent.parent / "tessdata"
_LINE_HEIGHT = 64   # px; Tesseract's LSTM models read best with ~20-30 px x-height
_PADDING = 24
_GAP = 40

_languages_lock = threading.Lock()
_languages_cache: Optional[Tuple[str, Set[str]]] = None


def tesseract_command() -> Optional[str]:
    configured = os.getenv("TESSERACT_CMD")
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("tesseract")
    if found:
        return found
    return _WINDOWS_DEFAULT if os.name == "nt" and Path(_WINDOWS_DEFAULT).is_file() else None


def tessdata_dir() -> Optional[str]:
    configured = os.getenv("OCR_TESSDATA_DIR")
    if configured:
        return configured
    return str(_BACKEND_TESSDATA) if _BACKEND_TESSDATA.is_dir() else None


def available_languages() -> Set[str]:
    """ISO codes of languages Tesseract can read here (cached per configuration)."""
    global _languages_cache
    command, data_dir = tesseract_command(), tessdata_dir()
    key = f"{command}|{data_dir}"
    with _languages_lock:
        if _languages_cache and _languages_cache[0] == key:
            return _languages_cache[1]
        codes: Set[str] = set()
        if command:
            args = [command, "--list-langs"] + (["--tessdata-dir", data_dir] if data_dir else [])
            try:
                output = subprocess.run(args, capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
                installed = {line.strip() for line in output.splitlines()[1:]}
                codes = {iso for iso, tess in TESSERACT_CODES.items() if tess in installed}
            except (OSError, subprocess.SubprocessError) as exc:
                logger.warning("Tesseract is not usable: %s", exc)
        _languages_cache = (key, codes)
        return codes


def _normalize_crop(crop: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    scale = min(_LINE_HEIGHT / max(1, gray.shape[0]), 4.0)
    interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=interpolation)


def read_lines(crops: List[np.ndarray], language: str, timeout: float = 120.0,
               with_english: bool = True) -> List[Tuple[str, float]]:
    """Recognize each line crop; returns ``(text, confidence 0..1)`` per crop.

    With ``with_english`` (and English data installed) the language model is
    combined with English ("hin+eng"): Indian documents routinely mix English
    into Indic lines ("District (जिला): ROURKELA"), which an Indic-only model
    garbles. Raises ``RuntimeError`` if Tesseract cannot run for this language.
    """
    if not crops:
        return []
    command = tesseract_command()
    if not command or language not in available_languages():
        raise RuntimeError(f"Tesseract data for '{language}' is not installed")

    lines = [_normalize_crop(crop) for crop in crops]
    width = max(line.shape[1] for line in lines) + 2 * _PADDING
    height = sum(line.shape[0] for line in lines) + _GAP * (len(lines) - 1) + 2 * _PADDING
    sheet = np.full((height, width), 255, dtype=np.uint8)
    bands = []
    y = _PADDING
    for line in lines:
        sheet[y:y + line.shape[0], _PADDING:_PADDING + line.shape[1]] = line
        bands.append((y - _GAP // 2, y + line.shape[0] + _GAP // 2))
        y += line.shape[0] + _GAP

    handle, path = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    try:
        cv2.imwrite(path, sheet)
        models = TESSERACT_CODES[language]
        if with_english and language != "en" and "en" in available_languages():
            models += "+eng"
        args = [command, path, "stdout", "-l", models, "--oem", "1", "--psm", "6"]
        if tessdata_dir():
            args += ["--tessdata-dir", tessdata_dir()]
        # A parameter, not the "tsv" config file: that file lives in Tesseract's
        # own tessdata/configs and is missing from a custom --tessdata-dir.
        completed = subprocess.run(args + ["-c", "tessedit_create_tsv=1"], capture_output=True, timeout=timeout)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.decode("utf-8", "replace").strip()[:200] or "Tesseract failed")
        tsv = completed.stdout.decode("utf-8", "replace")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    # Group words by Tesseract line, then assign each line to a crop band.
    words: List[List[Tuple[int, str, float]]] = [[] for _ in crops]
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        center = int(row["top"]) + int(row["height"]) // 2
        for index, (top, bottom) in enumerate(bands):
            if top <= center < bottom:
                words[index].append((int(row["left"]), text, max(0.0, float(row["conf"])) / 100.0))
                break
    results = []
    for entries in words:
        entries.sort()
        text = " ".join(word for _, word, _ in entries)
        weights = [len(word) for _, word, _ in entries]
        confidence = sum(w * c for w, (_, _, c) in zip(weights, entries)) / sum(weights) if weights else 0.0
        results.append((text, round(confidence, 4)))
    return results
