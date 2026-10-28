"""Offline checks for server.py helpers: no key, no network, no socket."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import parse_report, slugify


class TestParseReport(unittest.TestCase):
    def test_type_first_line(self):
        self.assertEqual(parse_report("type: mechanism\nPASS\nflagged: 0 remain\n"),
                         "mechanism")

    def test_missing(self):
        self.assertIsNone(parse_report("PASS\nflagged: 0 remain\n"))

    def test_blank_type(self):
        self.assertIsNone(parse_report("type: \nPASS\n"))

    def test_ignores_later_lines(self):
        self.assertEqual(parse_report("flagged: 1 remain\ntype: rules\n"), "rules")


class TestSlugify(unittest.TestCase):
    def test_lowercase_underscore(self):
        self.assertEqual(slugify("Tea_Test"), "tea-test")

    def test_spaces_and_punct(self):
        self.assertEqual(slugify("Hello World!"), "hello-world")

    def test_empty(self):
        self.assertEqual(slugify(""), "")
        self.assertEqual(slugify("___"), "")


if __name__ == "__main__":
    unittest.main()
