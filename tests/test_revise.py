"""Offline checks for revise pieces: reply parsing + request validation."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import revise_error, route_chat
from writer import split_refusals


class TestSplitRefusals(unittest.TestCase):
    def test_fenced_chart_plus_refusal(self):
        out = ("```mermaid\nflowchart LR\nA --> B\n```\n"
               "REFUSED: honey is not in the source.\n")
        chart, refused = split_refusals(out)
        self.assertIn("flowchart LR", chart)
        self.assertNotIn("REFUSED", chart)
        self.assertEqual(refused, ["REFUSED: honey is not in the source."])

    def test_clean_reply(self):
        chart, refused = split_refusals("flowchart LR\nA --> B\n")
        self.assertIn("A --> B", chart)
        self.assertEqual(refused, [])


class TestReviseError(unittest.TestCase):
    def test_ok(self):
        self.assertIsNone(revise_error("tea-test", "drop node A"))

    def test_empty_instruction(self):
        self.assertIsNotNone(revise_error("tea-test", "   "))

    def test_too_long(self):
        self.assertIsNotNone(revise_error("tea-test", "x" * 2001))


class TestRouteChat(unittest.TestCase):
    def test_material_needs_id(self):
        action, reply = route_chat("", False, True, "")
        self.assertEqual(action, "ask")
        self.assertIn("short id", reply)

    def test_material_with_id_builds(self):
        self.assertEqual(route_chat("demo", False, True, "")[0], "build")

    def test_message_with_chart_revises(self):
        self.assertEqual(route_chat("demo", True, False, "drop A")[0], "revise")

    def test_message_without_chart_asks(self):
        action, reply = route_chat("", False, False, "hello")
        self.assertEqual(action, "ask")
        self.assertIn("gallery", reply)

    def test_empty_message_with_chart_asks(self):
        action, _ = route_chat("demo", True, False, "   ")
        self.assertEqual(action, "ask")


if __name__ == "__main__":
    unittest.main()
