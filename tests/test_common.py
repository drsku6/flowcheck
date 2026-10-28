"""Offline checks for common.py: no model, no key, no network."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common import norm, quote_in_source


class TestNorm(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(norm("  Boil   water\nin a kettle. "),
                         "Boil water in a kettle.")

    def test_strips_page_markers(self):
        self.assertEqual(norm("Boil [page 12] water."), "Boil water.")

    def test_empty(self):
        self.assertEqual(norm("   "), "")


class TestQuoteInSource(unittest.TestCase):
    SRC = "Boil water in a kettle.\nPour the water over tea leaves.\n"

    def test_verbatim(self):
        self.assertTrue(quote_in_source("Pour the water over tea leaves.", self.SRC))

    def test_whitespace_variant(self):
        self.assertTrue(quote_in_source("  Pour   the water\nover tea leaves. ", self.SRC))

    def test_reworded(self):
        self.assertFalse(quote_in_source("Pour water onto the tea.", self.SRC))

    def test_empty(self):
        self.assertFalse(quote_in_source("", self.SRC))
        self.assertFalse(quote_in_source("   ", self.SRC))


if __name__ == "__main__":
    unittest.main()
