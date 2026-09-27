"""Unit tests for the model-free OCR text utilities.

Run from the backend directory:  python -m unittest discover tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ocr_text import (  # noqa: E402
    clean_segment,
    collapse_repeated_words,
    dedupe_overlapping,
    detect_languages,
    is_noise_segment,
    language_label,
    reconstruct_layout,
    resolve_languages,
    weighted_confidence,
)


def line(text, x0, y0, x1, y1, confidence=0.95):
    return {"text": text, "confidence": confidence, "bbox": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


class ResolveLanguagesTest(unittest.TestCase):
    def test_legacy_frontend_values(self):
        self.assertEqual(resolve_languages("eng"), ["en"])
        self.assertEqual(resolve_languages("hin"), ["hi"])
        self.assertEqual(resolve_languages("eng+hin"), ["en", "hi"])

    def test_kannada_aliases(self):
        for value in ("kan", "kn", "ka", "Kannada"):
            self.assertEqual(resolve_languages(value), ["kn"])

    def test_auto(self):
        self.assertEqual(resolve_languages("auto"), ["en", "hi", "kn", "te", "ta", "ml"])
        self.assertEqual(resolve_languages(None), ["en", "hi", "kn", "te", "ta", "ml"])

    def test_south_indian_languages(self):
        self.assertEqual(resolve_languages("tel+tam"), ["te", "ta"])
        self.assertEqual(resolve_languages("mal"), ["ml"])

    def test_unknown_language_rejected(self):
        with self.assertRaises(ValueError):
            resolve_languages("../../etc")


class DetectLanguagesTest(unittest.TestCase):
    def test_mixed_document(self):
        text = "First Information Report प्रथम सूचना रिपोर्ट ಪ್ರಥಮ ಮಾಹಿತಿ ವರದಿ"
        codes = [item["code"] for item in detect_languages(text)]
        self.assertEqual(set(codes), {"en", "hi", "kn"})
        self.assertEqual(codes[0], "en")

    def test_south_indian_scripts(self):
        text = "முதல் தகவல் అధికారి പ്രഥമ വിവരം"
        self.assertEqual({item["code"] for item in detect_languages(text)}, {"ta", "te", "ml"})

    def test_digits_are_neutral(self):
        self.assertEqual(detect_languages("12/03/2024 9876543210"), [])
        self.assertEqual(language_label([]), "unknown")

    def test_minor_language_reported_by_absolute_count(self):
        text = "क" * 2000 + " Police Station Koramangala"
        self.assertEqual(language_label(detect_languages(text)), "hi+en")


class CleaningTest(unittest.TestCase):
    def test_removes_cjk_noise_and_control_chars(self):
        self.assertEqual(clean_segment("Evidence一 memo\x07"), "Evidence memo")

    def test_keeps_indic_joiners(self):
        text = "क्‍ष"
        self.assertEqual(clean_segment(text), text)

    def test_indic_zero_read_as_anusvara(self):
        self.assertEqual(clean_segment("ಎ೦ದು ಗ೦ಟೆ"), "ಎಂದು ಗಂಟೆ")
        self.assertEqual(clean_segment("ಪುಟ ೧೦"), "ಪುಟ ೧೦")         # a real number is kept
        self.assertEqual(clean_segment("గ౦టల"), "గంటల")                # Telugu
        self.assertEqual(clean_segment("ആര൦ഭിച്ചു"), "ആരംഭിച്ചു")        # Malayalam
        self.assertEqual(clean_segment("ಮಾ೦ಸ"), "ಮಾಂಸ")                 # after a vowel sign

    def test_malayalam_legacy_chillu_normalized(self):
        self.assertEqual(clean_segment("പരാതിക്കാരന്‍ രജിസ്റ്റര്‍"), "പരാതിക്കാരൻ രജിസ്റ്റർ")
        self.assertEqual(clean_segment("ചെയ്ത്"), "ചെയ്ത്")  # a real virama ending is untouched

    def test_trailing_joiner_after_virama_removed(self):
        self.assertEqual(clean_segment("ಮೋಟಾರ್‌ ಸೈಕಲ್‌."), "ಮೋಟಾರ್ ಸೈಕಲ್.")
        self.assertEqual(clean_segment("क्‍ष"), "क्‍ष")  # inside a word it is meaningful

    def test_strips_table_rules_and_collapses_punctuation(self):
        self.assertEqual(clean_segment("| Name ....... Ram |"), "Name ... Ram")

    def test_collapses_repeated_words_only(self):
        self.assertEqual(collapse_repeated_words("the the report"), "the report")
        self.assertEqual(collapse_repeated_words("10 10 A A"), "10 10 A A")

    def test_noise_segments(self):
        self.assertTrue(is_noise_segment("|", 0.9))
        self.assertTrue(is_noise_segment("~.", 0.95))
        self.assertFalse(is_noise_segment("₹500", 0.8))
        self.assertFalse(is_noise_segment("हाँ", 0.8))
        self.assertFalse(is_noise_segment("PS", 0.78))
        self.assertFalse(is_noise_segment("Police Station", 0.4))  # long text is judged by min confidence
        self.assertTrue(is_noise_segment("C6r", 0.65))
        self.assertTrue(is_noise_segment("ണു", 0.46))
        self.assertTrue(is_noise_segment("7", 0.58))


class LayoutTest(unittest.TestCase):
    def test_paragraphs_and_line_breaks(self):
        text, tables = reconstruct_layout([
            line("First line", 100, 100, 400, 130),
            line("second line", 100, 140, 420, 170),
            line("New paragraph", 100, 260, 450, 290),
        ])
        self.assertEqual(text, "First line\nsecond line\n\nNew paragraph")
        self.assertEqual(tables, [])

    def test_reading_order_joins_segments_on_one_row(self):
        text, _ = reconstruct_layout([
            line("dated 12 March", 330, 102, 560, 130),
            line("Report", 100, 100, 200, 130),
            line("filed", 210, 101, 300, 129),
        ])
        self.assertEqual(text, "Report filed dated 12 March")

    def test_table_detection(self):
        rows = [("Name", "Role", "Contact"), ("Ram Kumar", "Complainant", "98765"),
                ("Suresh Rao", "Witness", "91234")]
        lines = []
        for index, cells in enumerate(rows):
            y = 100 + index * 45
            for x, cell in zip((100, 600, 1050), cells):
                lines.append(line(cell, x, y, x + 18 * len(cell), y + 30))
        text, tables = reconstruct_layout(lines)
        self.assertEqual(text.splitlines()[0], "Name | Role | Contact")
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["row_count"], 3)
        self.assertEqual(tables[0]["rows"][2], ["Suresh Rao", "Witness", "91234"])

    def test_list_items_keep_markers_and_indent(self):
        text, _ = reconstruct_layout([
            line("Items recovered:", 100, 100, 400, 130),
            line("● Mobile phone", 160, 140, 420, 170),
            line("2. Wallet", 160, 180, 330, 210),
        ])
        self.assertEqual(text.splitlines()[1].strip(), "• Mobile phone")
        self.assertTrue(text.splitlines()[2].startswith("  2. Wallet"))

    def test_skewed_rows_still_group(self):
        # A 3° tilt shifts the right end of each line down by ~26px.
        def tilted(text, x0, y0, width):
            return {"text": text, "confidence": 0.9,
                    "bbox": [[x0, y0], [x0 + width, y0 + 26], [x0 + width, y0 + 56], [x0, y0 + 30]]}
        text, _ = reconstruct_layout([tilted("line one", 100, 100, 500), tilted("line two", 100, 150, 500)])
        self.assertEqual(text, "line one\nline two")

    def test_tall_box_does_not_merge_rows(self):
        text, _ = reconstruct_layout([
            line("Name", 100, 100, 200, 130),
            line("handwritten note", 600, 90, 900, 300),   # tall slanted box
            line("Address", 100, 150, 250, 180),
            line("Occupation", 100, 200, 300, 230),
        ])
        self.assertIn("Address", text.splitlines()[-2] + text.splitlines()[-1])
        self.assertNotIn("Address", text.splitlines()[0])

    def test_duplicate_detections_removed(self):
        lines = [line("Witness statement", 100, 100, 400, 130, 0.97),
                 line("Witness statemnt", 102, 101, 398, 131, 0.80)]
        self.assertEqual([item["text"] for item in dedupe_overlapping(lines)], ["Witness statement"])


class ConfidenceTest(unittest.TestCase):
    def test_character_weighted(self):
        # 20 characters at 1.0 and 1 character at 0.0 → 20/21
        self.assertEqual(weighted_confidence([("a long accurate line", 1.0), ("x", 0.0)]), 0.9524)
        self.assertEqual(weighted_confidence([]), 0.0)


if __name__ == "__main__":
    unittest.main()
