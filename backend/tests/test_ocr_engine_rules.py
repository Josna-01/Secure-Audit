"""Unit tests for engine-combination rules in services.ocr_service (no models loaded).

Run from the backend directory:  python -m unittest discover tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ocr_service import _adds_missing_script, restore_dropped_digits  # noqa: E402


class RestoreDroppedDigitsTest(unittest.TestCase):
    def test_leading_one_restored(self):
        self.assertEqual(restore_dropped_digits("(धारा 54 दंड)", "( 154 "), "(धारा 154 दंड)")
        self.assertEqual(restore_dropped_digits("Time From (समय से): 3:30 hrs", "Time From (7 ) 13:30 hrs"),
                         "Time From (समय से): 13:30 hrs")

    def test_alignment_skips_extra_paddle_runs(self):
        # PaddleOCR read garbage "M7" before the date; the time is still aligned.
        self.assertEqual(restore_dropped_digits("समय): 28/03/2022 7:30 hrs", "M7): 28/03/2022 17:30 hrs"),
                         "समय): 28/03/2022 17:30 hrs")

    def test_other_disagreements_untouched(self):
        self.assertEqual(restore_dropped_digits("Room 58", "Room 38"), "Room 58")
        self.assertEqual(restore_dropped_digits("no digits", "123"), "no digits")


class AddsMissingScriptTest(unittest.TestCase):
    def test_reading_with_dropped_hindi_is_replaced(self):
        self.assertTrue(_adds_missing_script("District():ROURKELA", "District (जिला): ROURKELA", 0.91, "hi"))

    def test_garbled_latin_is_not_accepted(self):
        self.assertFalse(_adds_missing_script("District():ROURKELA", "फा5(पं८६ (जिला): 00ाराटाएा", 0.9, "hi"))

    def test_low_confidence_not_accepted(self):
        self.assertFalse(_adds_missing_script("Year(a): 2022", "Year (वर्ष): 2022", 0.5, "hi"))


if __name__ == "__main__":
    unittest.main()
