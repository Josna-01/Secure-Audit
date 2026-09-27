"""Unit tests for OCR translation (providers are faked; no network).

Run from the backend directory:  python -m unittest discover tests
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import translation_service as ts  # noqa: E402


class FakeTooManyRequests(Exception):
    pass


FakeTooManyRequests.__name__ = "TooManyRequests"


def upper(text, source, target):
    return f"[{source}>{target}] {text.upper()}"


def blocked(text, source, target):
    raise FakeTooManyRequests("429")


class TranslationTest(unittest.TestCase):
    def service(self, **providers):
        service = ts.TranslationService()
        patcher = mock.patch.dict(ts.PROVIDERS, providers, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {"TRANSLATION_PROVIDERS": ",".join(providers)})
        env.start()
        self.addCleanup(env.stop)
        return service

    def test_translates_by_language_and_keeps_structure(self):
        service = self.service(fake=upper)
        pages = [{"page_number": 1, "text": "Police Station: HSR\n\nघटना रात हुई।\nपुलिस आई।\n12/03/2024"}]
        result = service.translate_pages(pages, "en")
        self.assertEqual(result["status"], "success")
        text = result["pages"][0]["translated_text"]
        lines = text.split("\n")
        self.assertEqual(lines[0], "Police Station: HSR")         # already English: not sent
        self.assertEqual(lines[1], "")                            # paragraph break kept
        self.assertTrue(lines[2].startswith("[hi>en]"))           # Hindi lines sent together
        self.assertEqual(lines[-1], "12/03/2024")                 # numbers-only line not sent
        self.assertEqual(result["source_languages"], ["hi"])

    def test_falls_back_and_disables_rate_limited_provider(self):
        service = self.service(google=blocked, mymemory=upper)
        result = service.translate_pages([{"page_number": 1, "text": "घटना रात हुई।"}], "en")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["providers"], ["mymemory"])
        self.assertFalse(service._available("google"))

    def test_total_failure_is_reported_not_raised(self):
        service = self.service(google=blocked)
        result = service.translate_pages([{"page_number": 1, "text": "ಘಟನೆ ರಾತ್ರಿ ನಡೆದಿದೆ."}], "en")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["translated_text"])
        self.assertIn("unavailable", result["error"])

    def test_partial_failure_keeps_original_for_failed_parts(self):
        def only_hindi(text, source, target):
            if source != "hi":
                raise ValueError("unsupported")
            return "TRANSLATED"
        service = self.service(fake=only_hindi)
        result = service.translate_pages([{"page_number": 1, "text": "घटना हुई।\n\nಘಟನೆ ನಡೆದಿದೆ."}], "en")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["translated_text"], "TRANSLATED\n\nಘಟನೆ ನಡೆದಿದೆ.")

    def test_no_translation_found_keeps_original_without_error(self):
        def no_match(text, source, target):
            if "gibberish" in text:
                raise ts.NoTranslationFound()
            return "OK"
        service = self.service(fake=no_match)
        result = service.translate_pages([{"page_number": 1, "text": "gibberish words\n\nघटना हुई।"}], "kn")
        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["error"])
        self.assertEqual(result["untranslated_passages"], 1)
        self.assertEqual(result["translated_text"], "gibberish words\n\nOK")
        self.assertTrue(service._available("fake"))

    def test_mymemory_quota_warning_is_not_shown_as_translation(self):
        class FakeMyMemory:
            def __init__(self, **kwargs):
                pass

            def translate(self, text):
                return "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY."
        with mock.patch("deep_translator.MyMemoryTranslator", FakeMyMemory):
            with self.assertRaises(ts.QuotaExceeded):
                ts._mymemory("घटना हुई।", "hi", "en")

    def test_text_already_in_target_is_skipped(self):
        service = self.service(fake=blocked)
        result = service.translate_pages([{"page_number": 1, "text": "Already English."}], "en")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["translated_text"], "Already English.")

    def test_long_lines_are_split_under_provider_limits(self):
        line = "पुलिस ने मामला दर्ज कर जांच शुरू कर दी है। " * 40
        units = ts._segments(line)
        self.assertGreater(len(units), 1)
        self.assertTrue(all(len(text) <= 450 for text, _ in units))

    def test_target_language_validation(self):
        self.assertEqual(ts.resolve_target_language("Kannada"), "kn")
        with self.assertRaises(ts.TranslationError):
            ts.resolve_target_language("xx")


if __name__ == "__main__":
    unittest.main()
