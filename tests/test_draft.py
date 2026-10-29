"""Offline checks for --draft: repair round skipped, residuals stay red.

Stubs orchestrator.write_chart so no model call runs. Uses a source plus a
bad chart (invented quote, unfixable by local_repair) and a good chart.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import orchestrator

SOURCE = ("Boil water in a kettle.\n"
          "Pour the water over tea leaves.\n")

GOOD = """flowchart LR
A(["<b>Boil</b><br/>• Boil water in a kettle"]):::altDx
B(["<b>Pour</b><br/>• Pour the water over tea leaves"]):::altDx
A --> B
%% CLAIM C1 | Boil water in a kettle. | A
%% CLAIM C2 | Pour the water over tea leaves. | B
"""

BAD = GOOD.replace("Pour the water over tea leaves. | B",
                   "Steep the tea for five hours. | B")


class DraftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        Path("workspace").mkdir()
        Path("output").mkdir()
        Path("input").mkdir()
        Path("tools").symlink_to(ROOT / "tools", target_is_directory=True)
        Path("workspace/t_source.md").write_text(SOURCE, encoding="utf-8")
        self.calls = []
        self.models = []

        def fake_write_chart(unit, utype=None, extra="", progress=None,
                           model=None):
            from writer import DRAFT_MODEL
            self.calls.append(extra)
            self.models.append(model or DRAFT_MODEL)
            return ("general", GOOD if extra else BAD)

        self.orig = orchestrator.write_chart
        orchestrator.write_chart = fake_write_chart
        self.addCleanup(setattr, orchestrator, "write_chart", self.orig)
        self.addCleanup(os.chdir, self.old)
        self.addCleanup(self.tmp.cleanup)

    def run_cards(self, draft):
        return orchestrator.run_cards("--text", "t", "t", "t", False, {},
                                      skip_ingest=True, draft=draft)

    def test_draft_skips_repair(self):
        res = self.run_cards(draft=True)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("flagged:", res["status"])
        out = Path("output/t.mmd").read_text(encoding="utf-8")
        self.assertIn(":::safetyNode", out)

    def test_verified_repairs(self):
        res = self.run_cards(draft=False)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(res["status"], "clean")

    def test_draft_model_routing(self):
        self.run_cards(draft=True)
        self.assertEqual(self.models, ["muse-spark-1.2"])
        self.models.clear()
        self.calls.clear()
        Path("output/t.mmd").unlink()
        self.run_cards(draft=False)
        self.assertEqual(self.models, ["muse-spark-1.2", "muse-spark-1.2"])


if __name__ == "__main__":
    unittest.main()
