"""Offline checks for server.py helpers: no key, no network, no socket."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import parse_report, slugify
import server as server_mod


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


class TestClaimSlot(unittest.TestCase):
    def test_same_id_serial(self):
        t1, _ = server_mod._claim_slot("slot-a")
        self.assertIsNotNone(t1)
        t2, err = server_mod._claim_slot("slot-a")
        self.assertIsNone(t2)
        self.assertIn("slot-a", err)

    def test_other_id_parallel(self):
        t1, _ = server_mod._claim_slot("slot-b")
        t2, _ = server_mod._claim_slot("slot-c")
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)


if __name__ == "__main__":
    unittest.main()
