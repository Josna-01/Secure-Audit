"""Pure text utilities for the OCR pipeline.

Everything in this module operates on recognized text and line geometry only
(no PaddleOCR / OpenCV model state), so it is cheap to unit test:

* language registry and request parsing (English and five Indian languages)
* Unicode-script based language detection for pages and lines
* conservative cleaning of recognized text (noise, duplicates, stray glyphs)
* layout reconstruction: reading order, line breaks, paragraphs, lists, tables
"""
from __future__ import annotations

import math
import os
import re
import statistics
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ── Language registry ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LanguageSpec:
    code: str          # ISO 639-1 code exposed by the API
    name: str
    script: str        # Unicode script the language is written in
    paddle_lang: str   # PaddleOCR ``lang`` identifier


SUPPORTED_LANGUAGES: Dict[str, LanguageSpec] = {
    "en": LanguageSpec("en", "English", "latin", "en"),
    "hi": LanguageSpec("hi", "Hindi", "devanagari", "hi"),
    # PaddleOCR identifies Kannada as "ka"; the API uses the ISO code "kn".
    "kn": LanguageSpec("kn", "Kannada", "kannada", "ka"),
    "te": LanguageSpec("te", "Telugu", "telugu", "te"),
    "ta": LanguageSpec("ta", "Tamil", "tamil", "ta"),
    # No PaddleOCR model exists for Malayalam; it is recognized by Tesseract.
    "ml": LanguageSpec("ml", "Malayalam", "malayalam", ""),
}

# Accept the historic Tesseract-style values the frontend sends ("eng",
# "hin", "eng+hin") alongside ISO codes and plain names.
LANGUAGE_ALIASES: Dict[str, str] = {
    "en": "en", "eng": "en", "english": "en",
    "hi": "hi", "hin": "hi", "hindi": "hi",
    "kn": "kn", "kan": "kn", "ka": "kn", "kannada": "kn",
    "te": "te", "tel": "te", "telugu": "te",
    "ta": "ta", "tam": "ta", "tamil": "ta",
    "ml": "ml", "mal": "ml", "malayalam": "ml",
}

UNKNOWN_LANGUAGE = "unknown"


def auto_languages() -> List[str]:
    configured = os.getenv("OCR_AUTO_LANGUAGES", "en,hi,kn,te,ta,ml")
    codes = [LANGUAGE_ALIASES.get(part.strip().lower()) for part in re.split(r"[+,\s]+", configured)]
    return _unique([code for code in codes if code]) or ["en"]


def resolve_languages(requested: Optional[str]) -> List[str]:
    """Turn a client language value into an ordered list of candidate codes.

    ``auto`` → every configured language; ``eng+hin`` / ``en,kn`` → that
    combination (first entry is the primary recognizer); a single value →
    just that language. Raises ``ValueError`` for unknown languages.
    """
    value = (requested or "auto").strip().lower()
    if value in ("", "auto", "multi", "multilingual", "mixed"):
        return auto_languages()
    codes: List[str] = []
    for part in re.split(r"[+,\s]+", value):
        if not part:
            continue
        code = LANGUAGE_ALIASES.get(part)
        if code is None:
            supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
            raise ValueError(f"Unsupported OCR language '{part}'. Supported languages: {supported}, or 'auto'.")
        codes.append(code)
    return _unique(codes) or auto_languages()


def _unique(items: Iterable[str]) -> List[str]:
    seen, result = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ── Script / language detection ──────────────────────────────────────────────

_SCRIPT_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (0x0041, 0x005A, "latin"), (0x0061, 0x007A, "latin"),
    (0x00C0, 0x024F, "latin"), (0x1E00, 0x1EFF, "latin"),
    (0x0900, 0x097F, "devanagari"), (0xA8E0, 0xA8FF, "devanagari"),
    (0x0C80, 0x0CFF, "kannada"),
    (0x0980, 0x09FF, "bengali"), (0x0B80, 0x0BFF, "tamil"), (0x0C00, 0x0C7F, "telugu"),
    (0x0D00, 0x0D7F, "malayalam"),
    (0x0600, 0x06FF, "arabic"), (0x0400, 0x04FF, "cyrillic"),
    (0x3040, 0x30FF, "cjk"), (0x3400, 0x4DBF, "cjk"), (0x4E00, 0x9FFF, "cjk"),
    (0xF900, 0xFAFF, "cjk"), (0x1100, 0x11FF, "cjk"), (0x3130, 0x318F, "cjk"),
    (0xAC00, 0xD7AF, "cjk"),
)
_SCRIPT_TO_LANGUAGE = {spec.script: spec.code for spec in SUPPORTED_LANGUAGES.values()}
# Scripts none of the supported recognizers are meant to emit. The default
# English model (PP-OCRv6) has a Chinese+English dictionary and occasionally
# "reads" smudges as CJK glyphs; those characters are always noise here.
_FOREIGN_SCRIPTS = {"cjk"}


def char_script(char: str) -> Optional[str]:
    code = ord(char)
    for start, end, script in _SCRIPT_RANGES:
        if start <= code <= end:
            return script
    return None


def script_counts(text: str) -> Dict[str, int]:
    """Count script-bearing characters (letters and Indic vowel signs)."""
    counts: Dict[str, int] = {}
    for char in text:
        if char.isdigit():
            continue
        script = char_script(char)
        if script:
            counts[script] = counts.get(script, 0) + 1
    return counts


def detect_languages(text: str, min_ratio: float = 0.05, min_chars: int = 20) -> List[Dict[str, Any]]:
    """Return the supported languages present in ``text``, largest share first.

    A language is reported when it makes up at least ``min_ratio`` of the
    script-bearing characters, or at least ``min_chars`` of them (so a few
    English sentences inside a long Hindi FIR are still reported).
    """
    counts = script_counts(text)
    total = sum(counts.get(script, 0) for script in _SCRIPT_TO_LANGUAGE)
    if not total:
        return []
    detected = []
    for script, code in _SCRIPT_TO_LANGUAGE.items():
        count = counts.get(script, 0)
        ratio = count / total
        if count and (ratio >= min_ratio or count >= min_chars):
            detected.append({"code": code, "name": SUPPORTED_LANGUAGES[code].name,
                             "ratio": round(ratio, 4), "char_count": count})
    return sorted(detected, key=lambda item: item["char_count"], reverse=True)


def language_label(detected: Sequence[Dict[str, Any]]) -> str:
    """Compact string form, e.g. ``"hi+en"`` (kept for the legacy ``language`` field)."""
    return "+".join(item["code"] for item in detected) or UNKNOWN_LANGUAGE


def dominant_language(text: str) -> str:
    detected = detect_languages(text, min_ratio=0.0, min_chars=0)
    return detected[0]["code"] if detected else UNKNOWN_LANGUAGE


def native_script_ratio(text: str, language: str) -> float:
    """Share of script-bearing characters that a language's model should emit.

    The Hindi and Kannada recognizers also carry Latin characters, so Latin
    output never counts against them; digits/punctuation are neutral (1.0).
    """
    counts = script_counts(text)
    total = sum(counts.values())
    if not total:
        return 1.0
    native = {SUPPORTED_LANGUAGES[language].script, "latin"}
    return sum(counts.get(script, 0) for script in native) / total


# ── Text cleaning ────────────────────────────────────────────────────────────

_BULLET_GLYPHS = "•·●▪■◦‣∙○◆◇►➢➤✓✔"
_TABLE_RULE_CHARS = "|¦│┃"
_KEEP_FORMAT_CHARS = {"‌", "‍"}  # ZWNJ / ZWJ change Indic conjunct rendering
_REPEATED_PUNCT = re.compile(r"([^\w\s])\1{3,}")
_WORD = re.compile(r"\S+")
_LIST_MARKER = re.compile(
    r"^(?:[" + re.escape(_BULLET_GLYPHS) + r"\-\*–]"
    r"|\(?\d{1,3}[.)]"
    r"|\(?[a-zA-Z][.)]"
    r"|\(?(?:i{1,3}|iv|v|vi{1,3}|ix|x)[.)])\s+",
    re.IGNORECASE,
)


# Indic digit zero → anusvara of the same script. Recognizers (Tesseract in
# particular) confuse the two round glyphs; a "zero" directly after a letter or
# vowel sign is never a number, while real numbers ("೧೦") are left alone.
_ZERO_TO_ANUSVARA = {"०": "ं", "೦": "ಂ", "౦": "ం", "൦": "ം"}
# Preceded by a letter or vowel sign of Devanagari / Telugu / Kannada /
# Malayalam (each block minus its digits 0x?66-0x?6F).
_MISREAD_ANUSVARA = re.compile(
    r"(?<=[ऀ-॥॰-ॿఀ-౥౰-౿ಀ-೥೰-೿ഀ-൥൰-ൿ])"
    r"([०೦౦൦])")
# ZWNJ/ZWJ right after a virama at the end of a word changes nothing visually
# but breaks search ("ಮೋಟಾರ್‌" != "ಮೋಟಾರ್").
_TRAILING_JOINER = re.compile(r"(?<=[्್్്்])[‌‍](?=\s|[^\w]|$)")


# Malayalam chillu letters in the pre-Unicode-5.1 encoding (consonant +
# virama + ZWJ, still emitted by Tesseract) → atomic chillu characters. Must
# run before the joiner clean-up, which would otherwise change the letter.
_CHILLU = {"ണ": "ൺ", "ന": "ൻ", "ര": "ർ", "ല": "ൽ", "ള": "ൾ", "ക": "ൿ"}
_LEGACY_CHILLU = re.compile("([ണനരലളക])്‍")


def fix_indic_confusions(text: str) -> str:
    text = _MISREAD_ANUSVARA.sub(lambda m: _ZERO_TO_ANUSVARA[m.group(1)], text)
    text = _LEGACY_CHILLU.sub(lambda m: _CHILLU[m.group(1)], text)
    return _TRAILING_JOINER.sub("", text)


def _is_noise_char(char: str) -> bool:
    if char in _KEEP_FORMAT_CHARS:
        return False
    category = unicodedata.category(char)
    # Control, private-use, unassigned and invisible format characters
    # (zero-width space, BOM, ...) plus the replacement character.
    return category in ("Cc", "Co", "Cn", "Cf") or char == "�"


def clean_segment(text: str, collapse_duplicates: bool = True) -> str:
    """Clean a single recognized text segment without rewriting its content."""
    text = unicodedata.normalize("NFC", text or "")
    chars = []
    for char in text:
        if char in "\t\n\r":
            chars.append(" ")
        elif _is_noise_char(char) or char_script(char) in _FOREIGN_SCRIPTS:
            continue
        elif 0xFF01 <= ord(char) <= 0xFF5E:  # full-width ASCII from CJK-trained models
            chars.append(unicodedata.normalize("NFKC", char))
        else:
            chars.append(char)
    text = fix_indic_confusions("".join(chars))
    text = _REPEATED_PUNCT.sub(lambda m: m.group(1) * 3, text)
    # Table borders are frequently read as a leading/trailing "|".
    text = text.strip().strip(_TABLE_RULE_CHARS).strip()
    text = re.sub(r"\s+", " ", text)
    if collapse_duplicates:
        text = collapse_repeated_words(text)
    return text


def collapse_repeated_words(text: str) -> str:
    """Remove immediately repeated words ("the the" → "the").

    Only words containing at least two letters are collapsed, so repeated
    numbers, initials and table values are left untouched.
    """
    words = text.split(" ")
    result: List[str] = []
    for word in words:
        if result and _letter_count(word) >= 2 and word.casefold() == result[-1].casefold():
            continue
        result.append(word)
    return " ".join(result)


def _letter_count(word: str) -> int:
    return sum(1 for char in word if char.isalpha())


def is_noise_segment(text: str, confidence: float) -> bool:
    """True for stray marks: symbol-only output, or very short low-confidence fragments.

    Stamps, handwriting and specks on photographed documents produce 1–3
    character readings ("C6r", "#O", "ണു") at middling confidence; real short
    tokens ("PS", "5", "(b)") are usually read with high confidence.
    """
    if not text:
        return True
    content = sum(1 for char in text if char.isalnum() or char_script(char))
    if not content:
        return len(text) <= 3 or confidence < 0.8
    if content <= 1:
        return confidence < 0.9
    return content <= 3 and confidence < 0.7


def normalize_list_marker(text: str) -> str:
    """Standardise bullet glyphs (``●``, ``▪``, ``·``) to ``•``."""
    if text and text[0] in _BULLET_GLYPHS:
        return "• " + text[1:].lstrip()
    return text


def is_list_item(text: str) -> bool:
    return bool(_LIST_MARKER.match(text))


# ── Layout reconstruction ────────────────────────────────────────────────────

@dataclass
class _Box:
    text: str
    confidence: float
    x0: float
    y0: float
    x1: float
    y1: float
    index: int

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)

    @property
    def width(self) -> float:
        return max(1.0, self.x1 - self.x0)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def _poly_points(poly: Any) -> Optional[List[Tuple[float, float]]]:
    try:
        points = [(float(p[0]), float(p[1])) for p in poly]
    except (TypeError, ValueError, IndexError):
        return None
    if len(points) == 2:  # axis-aligned [x0, y0], [x1, y1]
        (x0, y0), (x1, y1) = points
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if len(points) == 4 and all(len(p) == 2 for p in points):
        return points
    if not points:
        return None
    try:  # flat [x0, y0, x1, y1]
        x0, y0, x1, y1 = (float(v) for v in poly)
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    except (TypeError, ValueError):
        return None


def estimate_skew(polys: Sequence[Sequence[Tuple[float, float]]]) -> float:
    """Median text-line angle in degrees, from wide (horizontal) line boxes."""
    angles = []
    for points in polys:
        (x0, y0), (x1, y1) = points[0], points[1]
        width, height = math.hypot(x1 - x0, y1 - y0), math.hypot(points[3][0] - x0, points[3][1] - y0)
        if width > 2 * height:
            angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    return statistics.median(angles) if angles else 0.0


def _to_boxes(lines: Sequence[Dict[str, Any]]) -> List[_Box]:
    parsed = [(index, line, _poly_points(line.get("bbox"))) for index, line in enumerate(lines)]
    parsed = [(index, line, pts) for index, line, pts in parsed if pts and line.get("text")]
    skew = math.radians(estimate_skew([pts for _, _, pts in parsed]))
    cos_a, sin_a = math.cos(-skew), math.sin(-skew)
    boxes = []
    for index, line, points in parsed:
        # Rotate into a de-skewed frame so rows of a slightly tilted scan
        # still group correctly; the image itself is never resampled for this.
        rotated = [(x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in points]
        xs, ys = [p[0] for p in rotated], [p[1] for p in rotated]
        boxes.append(_Box(line["text"], float(line.get("confidence") or 0.0),
                          min(xs), min(ys), max(xs), max(ys), index))
    return boxes


def _overlap_ratio(a: _Box, b: _Box) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    smaller = min(a.width * a.height, b.width * b.height)
    return (ix * iy) / smaller if smaller else 0.0


def _similar(a: str, b: str) -> bool:
    a, b = a.casefold(), b.casefold()
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.8


def dedupe_overlapping(lines: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop duplicate detections: heavily overlapping boxes with the same text.

    Keeps the most confident reading. Returns the surviving input dicts in
    their original order.
    """
    boxes = sorted(_to_boxes(lines), key=lambda box: box.confidence, reverse=True)
    kept: List[_Box] = []
    for box in boxes:
        if not any(_overlap_ratio(box, other) > 0.6 and _similar(box.text, other.text) for other in kept):
            kept.append(box)
    keep_indexes = {box.index for box in kept}
    return [line for index, line in enumerate(lines) if index in keep_indexes]


def _group_rows(boxes: List[_Box]) -> List[List[_Box]]:
    rows: List[List[_Box]] = []
    for box in sorted(boxes, key=lambda b: (b.cy, b.x0)):
        if rows:
            row = rows[-1]
            # Median band, not min/max: one tall box (slanted handwriting, a
            # stamp) must not stretch the row until it swallows the rows below.
            top, bottom = statistics.median(b.y0 for b in row), statistics.median(b.y1 for b in row)
            row_height = statistics.median(b.height for b in row)
            overlap = min(bottom, box.y1) - max(top, box.y0)
            if overlap >= 0.5 * min(box.height, row_height):
                row.append(box)
                continue
        rows.append([box])
    return [sorted(row, key=lambda b: b.x0) for row in rows]


def _split_cells(row: List[_Box], cell_gap: float) -> List[List[_Box]]:
    cells: List[List[_Box]] = [[row[0]]]
    for box in row[1:]:
        if box.x0 - cells[-1][-1].x1 >= cell_gap:
            cells.append([box])
        else:
            cells[-1].append(box)
    return cells


def _join_segments(boxes: List[_Box]) -> str:
    """Join horizontally adjacent segments, dropping a word duplicated across
    the boundary when two detection boxes overlap ("report dated" + "dated 12")."""
    text = boxes[0].text
    for previous, box in zip(boxes, boxes[1:]):
        addition = box.text
        if box.x0 < previous.x1:  # overlapping boxes
            tail, head = text.split(" ")[-1], addition.split(" ")
            if head and tail.casefold() == head[0].casefold():
                addition = " ".join(head[1:])
        if addition:
            text = f"{text} {addition}"
    return text


def _cluster_anchors(values: List[float], tolerance: float) -> List[float]:
    anchors: List[List[float]] = []
    for value in sorted(values):
        if anchors and value - statistics.mean(anchors[-1]) <= tolerance:
            anchors[-1].append(value)
        else:
            anchors.append([value])
    return [statistics.mean(group) for group in anchors]


def _table_from_rows(rows: List[List[List[_Box]]], tolerance: float) -> Optional[List[List[str]]]:
    """Return aligned cell text when the rows form a table, else ``None``."""
    anchors = _cluster_anchors([cell[0].x0 for row in rows for cell in row], tolerance)
    usage = [0] * len(anchors)
    grid: List[List[str]] = []
    for row in rows:
        cells = [""] * len(anchors)
        for cell in row:
            column = min(range(len(anchors)), key=lambda i: abs(anchors[i] - cell[0].x0))
            cells[column] = f"{cells[column]} {_join_segments(cell)}".strip()
        for column, value in enumerate(cells):
            usage[column] += bool(value)
        grid.append(cells)
    # A real table has at least three rows and two columns that are filled in
    # most rows; loosely aligned form fields (label ... value) are not tables.
    if len(rows) < 3 or sum(1 for count in usage if count >= max(2, len(rows) / 2)) < 2:
        return None
    used_columns = [i for i, count in enumerate(usage) if count]
    return [[row[i] for i in used_columns] for row in grid]


def reconstruct_layout(lines: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Rebuild page text from recognized line boxes.

    * rows are formed from vertically overlapping boxes, left to right
    * a large vertical gap between rows starts a new paragraph (blank line)
    * a large horizontal gap inside a row splits it into cells; consecutive
      multi-cell rows with aligned columns are emitted as a ``|``-separated
      table and also returned in structured form
    * list items keep their marker and relative indentation

    ``lines`` items need ``text``, ``confidence`` and a ``bbox`` polygon.
    Returns ``(text, tables)``.
    """
    boxes = _to_boxes(lines)
    if not boxes:
        return "", []

    median_height = statistics.median(box.height for box in boxes)
    char_width = statistics.median(box.width / max(1, len(box.text)) for box in boxes)
    cell_gap = max(2.5 * char_width, 1.2 * median_height)
    left_margin = min(box.x0 for box in boxes)

    rows = _group_rows(boxes)
    row_cells = [_split_cells(row, cell_gap) for row in rows]

    # Identify table blocks: runs of consecutive multi-cell rows without a
    # paragraph-sized gap between them.
    table_of_row: Dict[int, int] = {}
    table_row_text: Dict[int, str] = {}
    tables: List[Dict[str, Any]] = []
    start = 0
    while start < len(rows):
        end = start
        while (end + 1 < len(rows) and len(row_cells[end]) >= 2 and len(row_cells[end + 1]) >= 2
               and _row_gap(rows[end], rows[end + 1]) <= 1.5 * median_height):
            end += 1
        if end > start:
            grid = _table_from_rows(row_cells[start:end + 1], tolerance=3 * char_width)
            if grid:
                for offset, cells in enumerate(grid):
                    table_of_row[start + offset] = len(tables)
                    # Text view skips empty cells; ``tables`` keeps the full grid.
                    table_row_text[start + offset] = " | ".join(cell for cell in cells if cell)
                tables.append({"rows": grid, "row_count": len(grid), "column_count": len(grid[0])})
        start = end + 1

    output: List[str] = []
    for row_index, cells in enumerate(row_cells):
        if row_index and _row_gap(rows[row_index - 1], rows[row_index]) > 0.9 * median_height:
            output.append("")
        elif row_index and table_of_row.get(row_index) != table_of_row.get(row_index - 1):
            output.append("")  # separate a table from surrounding text

        if row_index in table_row_text:
            output.append(table_row_text[row_index])
            continue

        text = "   ".join(_join_segments(cell) for cell in cells)
        text = normalize_list_marker(text)
        if is_list_item(text):
            indent = int(round((cells[0][0].x0 - left_margin) / (4 * char_width)))
            text = "  " * max(0, min(indent, 4)) + text
        output.append(text)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()
    return text, tables


def _row_gap(upper: List[_Box], lower: List[_Box]) -> float:
    return min(b.y0 for b in lower) - max(b.y1 for b in upper)


# ── Aggregation helpers ──────────────────────────────────────────────────────

def weighted_confidence(items: Iterable[Tuple[str, float]]) -> float:
    """Character-weighted mean confidence (long lines count more than specks)."""
    total_weight, total = 0, 0.0
    for text, confidence in items:
        weight = len((text or "").strip())
        if weight:
            total_weight += weight
            total += weight * float(confidence or 0.0)
    return round(total / total_weight, 4) if total_weight else 0.0
