"""Optional translation of OCR text (never replaces the original OCR text).

Providers are tried in order (``TRANSLATION_PROVIDERS``, default
``google,mymemory``), both via the ``deep-translator`` package:

* ``google``   – Google Translate web endpoint; free, no key, but Google may
  rate-limit or CAPTCHA a server's IP at any time.
* ``mymemory`` – MyMemory API; free, no key (set ``MYMEMORY_EMAIL`` for a
  larger daily quota). Requires an explicit source language, which the OCR
  line-level language detection provides.

Text is translated paragraph by paragraph, grouped by detected language, so
line breaks and paragraph structure survive and mixed-language pages are sent
with the correct source language. A provider that fails (429, CAPTCHA,
timeout) is skipped for a cool-down period instead of being retried on every
chunk. Any failure is reported in the result; it never raises into the OCR
response.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import urllib.parse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ocr_text import UNKNOWN_LANGUAGE, dominant_language

logger = logging.getLogger("backend.translation")

TARGET_LANGUAGES = {
    "en": "English", "hi": "Hindi", "kn": "Kannada", "te": "Telugu", "ta": "Tamil", "ml": "Malayalam",
}
TARGET_ALIASES = {
    "eng": "en", "english": "en", "hin": "hi", "hindi": "hi", "kan": "kn", "kannada": "kn",
    "tel": "te", "telugu": "te", "tam": "ta", "tamil": "ta", "mal": "ml", "malayalam": "ml",
}
# MyMemory expects locale-style codes.
_MYMEMORY_CODES = {"en": "en-GB", "hi": "hi-IN", "kn": "kn-IN", "te": "te-IN", "ta": "ta-IN", "ml": "ml-IN"}
# Per-request size limits. Google's endpoint takes the text in the URL, where
# each Indic character costs ~9 bytes once percent-encoded.
_LIMITS = {"google": (1800, 12000), "mymemory": (450, 4500)}  # (chars, url-encoded bytes)
PROVIDER_COOLDOWN_SECONDS = 300


class TranslationError(RuntimeError):
    """Raised for invalid translation requests (bad target language)."""


def resolve_target_language(value: Optional[str]) -> str:
    code = (value or "en").strip().lower()
    code = TARGET_ALIASES.get(code, code)
    if code not in TARGET_LANGUAGES:
        raise TranslationError(
            f"Unsupported translation language '{value}'. Supported: {', '.join(sorted(TARGET_LANGUAGES))}.")
    return code


# ── Providers ────────────────────────────────────────────────────────────────

def _google(text: str, source: str, target: str) -> str:
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source=source if source in TARGET_LANGUAGES else "auto", target=target).translate(text)


class NoTranslationFound(Exception):
    """The provider answered but has no translation for this text (e.g. OCR gibberish)."""


class QuotaExceeded(Exception):
    pass


def _mymemory(text: str, source: str, target: str) -> str:
    from deep_translator import MyMemoryTranslator
    if source not in _MYMEMORY_CODES:
        raise ValueError("MyMemory needs a known source language")
    kwargs = {"email": os.getenv("MYMEMORY_EMAIL")} if os.getenv("MYMEMORY_EMAIL") else {}
    try:
        result = MyMemoryTranslator(source=_MYMEMORY_CODES[source], target=_MYMEMORY_CODES[target], **kwargs).translate(text)
    except StopIteration as exc:  # deep-translator's way of saying "no match found"
        raise NoTranslationFound() from exc
    # When the free daily quota is used up MyMemory answers HTTP 200 with a
    # warning *as the translation*; never show that to users as translated text.
    if isinstance(result, str) and result.lstrip().upper().startswith("MYMEMORY WARNING"):
        raise QuotaExceeded(result.strip()[:160])
    return result


PROVIDERS: Dict[str, Callable[[str, str, str], str]] = {"google": _google, "mymemory": _mymemory}

_PROVIDER_NAMES = {"google": "Google Translate", "mymemory": "MyMemory"}


def _describe_failure(exc: BaseException) -> Tuple[str, bool]:
    """Plain-language failure reason and whether to pause the provider."""
    name = type(exc).__name__
    if name == "TooManyRequests":
        return "rate-limited or blocked for this network", True
    if isinstance(exc, QuotaExceeded):
        return "free daily quota used up (set MYMEMORY_EMAIL for a larger quota)", True
    if name in ("RequestError", "ConnectionError", "ProxyError", "SSLError") or isinstance(exc, OSError):
        return "could not be reached", True
    return f"failed ({name})", False


class TranslationService:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="translate")
        self._disabled_until: Dict[str, float] = {}
        self._cache: "OrderedDict[str, str]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def providers() -> List[str]:
        names = [name.strip().lower() for name in os.getenv("TRANSLATION_PROVIDERS", "google,mymemory").split(",")]
        return [name for name in names if name in PROVIDERS]

    def _available(self, name: str) -> bool:
        return time.monotonic() >= self._disabled_until.get(name, 0.0)

    def _cache_key(self, text: str, source: str, target: str) -> str:
        return hashlib.sha256(f"{source}>{target}\0{text}".encode("utf-8")).hexdigest()

    def _translate_chunk(self, text: str, source: str, target: str) -> Tuple[str, str]:
        """Translate one chunk with the first working provider → (text, provider)."""
        key = self._cache_key(text, source, target)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key], "cache"
        timeout = float(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "20"))
        errors = []
        no_match = False
        for name in self.providers():
            label = _PROVIDER_NAMES.get(name, name)
            if not self._available(name):
                errors.append(f"{label} paused after an earlier failure")
                continue
            max_chars, max_bytes = _LIMITS.get(name, _LIMITS["mymemory"])
            if len(text) > max_chars or len(urllib.parse.quote(text)) > max_bytes:
                errors.append(f"{label}: passage too long")
                continue
            try:
                result = self._executor.submit(PROVIDERS[name], text, source, target).result(timeout=timeout)
            except FutureTimeout:
                errors.append(f"{label} timed out")
                self._disabled_until[name] = time.monotonic() + PROVIDER_COOLDOWN_SECONDS
                continue
            except NoTranslationFound:
                no_match = True
                continue
            except Exception as exc:  # network, 429/CAPTCHA, quota, unsupported pair, ...
                reason, pause = _describe_failure(exc)
                errors.append(f"{label} {reason}")
                if pause:
                    self._disabled_until[name] = time.monotonic() + PROVIDER_COOLDOWN_SECONDS
                logger.warning("Translation provider %s failed: %r", name, exc)
                continue
            if not result or not result.strip():
                no_match = True
                continue
            with self._lock:
                self._cache[key] = result
                while len(self._cache) > 2000:
                    self._cache.popitem(last=False)
            return result, name
        if no_match:
            raise NoTranslationFound()
        raise RuntimeError("; ".join(errors) or "no translation provider configured")

    # Public API ---------------------------------------------------------------

    def translate_pages(self, pages: List[Dict[str, Any]], target: str) -> Dict[str, Any]:
        """Translate page texts into ``target``.

        Returns ``status`` = ``success`` | ``partial`` | ``failed`` | ``skipped``,
        per-page ``translated_text`` (untranslatable parts keep the original
        text), the providers used and any error. Never raises for provider
        failures.
        """
        started = time.perf_counter()
        max_chars = int(os.getenv("TRANSLATION_MAX_CHARS", "30000"))
        total_chars = sum(len(page.get("text") or "") for page in pages)
        base = {"target_language": target, "target_language_name": TARGET_LANGUAGES[target],
                "providers": [], "error": None, "source_languages": []}
        if total_chars > max_chars:
            return {**base, "status": "failed", "pages": [], "translated_text": None,
                    "error": f"Document has {total_chars} characters; translation limit is {max_chars}.",
                    "processing_time_ms": 0}

        jobs: List[Tuple[int, int, str, str]] = []  # (page index, segment index, text, source)
        page_segments: List[List[str]] = []
        sources = set()
        for page_index, page in enumerate(pages):
            segments = _segments(page.get("text") or "")
            page_segments.append([text for text, _ in segments])
            for segment_index, (text, source) in enumerate(segments):
                if source not in (None, target):
                    jobs.append((page_index, segment_index, text, source))
                    sources.add(source)

        if not jobs:
            translated = ["\n".join(segments) for segments in page_segments]
            return {**base, "status": "skipped", "error": None, "source_languages": sorted(sources),
                    "pages": [{"page_number": page.get("page_number", i + 1), "translated_text": text}
                              for i, (page, text) in enumerate(zip(pages, translated))],
                    "translated_text": "\n\n".join(t for t in translated if t).strip(),
                    "message": f"Text is already in {TARGET_LANGUAGES[target]}; nothing to translate.",
                    "processing_time_ms": _elapsed_ms(started)}

        failures, providers, untranslated = [], set(), 0
        for page_index, segment_index, text, source in jobs:
            try:
                translated, provider = self._translate_chunk(text, source, target)
                page_segments[page_index][segment_index] = translated
                providers.add(provider)
            except NoTranslationFound:
                untranslated += 1  # kept in the original language; not a service failure
            except Exception as exc:
                failures.append(str(exc))

        attempted = len(jobs) - untranslated
        if not failures:
            status = "success"
        elif len(failures) == attempted:
            status = "failed"
        else:
            status = "partial"
        translated_pages = ["\n".join(segments) for segments in page_segments]
        result = {
            **base,
            "status": status,
            "source_languages": sorted(sources),
            "providers": sorted(providers - {"cache"}) or (["cache"] if providers else []),
            "pages": [{"page_number": page.get("page_number", i + 1), "translated_text": text}
                      for i, (page, text) in enumerate(zip(pages, translated_pages))] if status != "failed" else [],
            "translated_text": "\n\n".join(t for t in translated_pages if t).strip() if status != "failed" else None,
            "processing_time_ms": _elapsed_ms(started),
            "untranslated_passages": untranslated,
        }
        if failures:
            reason = sorted(set(failures))[0]
            result["error"] = (f"Translation service unavailable — {reason}." if status == "failed"
                               else f"{len(failures)} of {len(jobs)} passages could not be translated "
                                    f"({reason}) and are shown in the original language.")
        if untranslated:
            result["message"] = (f"{untranslated} passage(s) had no translation available — usually unclear "
                                 f"OCR text — and are shown as extracted.")
        return result


def _segments(text: str) -> List[Tuple[str, Optional[str]]]:
    """Split page text into translation units, keeping blank lines.

    Consecutive lines in the same language form one unit (up to the provider
    chunk size). Blank lines and lines without letters (dates, numbers,
    separators) are units with source ``None`` and are never sent.
    """
    units: List[Tuple[str, Optional[str]]] = []
    max_chars = min(limit[0] for limit in _LIMITS.values())
    max_bytes = min(limit[1] for limit in _LIMITS.values())
    for line in text.split("\n"):
        language = dominant_language(line) if line.strip() else UNKNOWN_LANGUAGE
        source = None if language == UNKNOWN_LANGUAGE else language
        if units and source and units[-1][1] == source:
            merged = f"{units[-1][0]}\n{line}"
            if len(merged) <= max_chars and len(urllib.parse.quote(merged)) <= max_bytes:
                units[-1] = (merged, source)
                continue
        if source and (len(line) > max_chars or len(urllib.parse.quote(line)) > max_bytes):
            units.extend((piece, source) for piece in _split_long_line(line, max_chars, max_bytes))
            continue
        units.append((line, source))
    return units


def _split_long_line(line: str, max_chars: int, max_bytes: int) -> List[str]:
    pieces, current = [], ""
    for word in line.split(" "):
        candidate = f"{current} {word}".strip()
        if current and (len(candidate) > max_chars or len(urllib.parse.quote(candidate)) > max_bytes):
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


translation_service = TranslationService()
