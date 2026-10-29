"""Offline gate checks for tools/validate_mmd.py via its real CLI."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ("Boil water in a kettle.\n"
          "Pour the water over tea leaves.\n"
          "Steep for three minutes before serving.\n")

GOOD = """flowchart LR
A(["<b>Boil</b><br/>• Boil water"]):::altDx
B(["<b>Pour</b><br/>• Pour water"]):::altDx
C(["<b>Steep</b><br/>• Steep tea"]):::altDx
A --> B
B --> C
%% CLAIM C1 | Boil water in a kettle. | A
%% CLAIM C2 | Pour the water over tea leaves. | B
%% CLAIM C3 | Steep for three minutes before serving. | C
"""


def run_chart(chart, source=SOURCE):
    """Run the validator CLI on inline text. Returns the CompletedProcess."""
    with tempfile.TemporaryDirectory() as d:
        c, s = Path(d, "t.mmd"), Path(d, "t.md")
        c.write_text(chart, encoding="utf-8")
        s.write_text(source, encoding="utf-8")
        return subprocess.run([sys.executable, "tools/validate_mmd.py", str(c), str(s)],
                              capture_output=True, text=True, cwd=ROOT)


class TestValidator(unittest.TestCase):
    def test_pass(self):
        r = run_chart(GOOD)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(r.stdout.strip().endswith("PASS"), r.stdout)

    def test_linear_warn_not_fail(self):
        r = run_chart(GOOD)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("linear chart: no fork", r.stdout)

    def test_fork_no_linear_warn(self):
        chart = ("flowchart LR\n"
                 "A([\"<b>Boil</b><br/>• Boil water\"]):::altDx\n"
                 "D{\"Hot or iced\"}:::decisionNode\n"
                 "B([\"<b>Hot tea</b><br/>• Pour hot\"]):::altDx\n"
                 "C([\"<b>Iced tea</b><br/>• Pour iced\"]):::altDx\n"
                 "A --> D\n"
                 "D -->|\"Hot\"| B\n"
                 "D -->|\"Iced\"| C\n"
                 "%% CLAIM C1 | Boil water in a kettle. | A\n"
                 "%% CLAIM C2 | Pour the water over tea leaves. | B\n"
                 "%% CLAIM C3 | Steep for three minutes before serving. | C\n")
        r = run_chart(chart)
        self.assertNotIn("linear chart", r.stdout)

    def test_nonverbatim_claim(self):
        bad = GOOD.replace("Steep for three minutes before serving.",
                           "Steep for five minutes before serving.")
        r = run_chart(bad)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("quote not found in source", r.stdout)

    def test_bullet_claim_mismatch(self):
        bad = GOOD.replace("• Boil water", "• Boil water<br/>• Pour slow")
        r = run_chart(bad)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("node A: 2 bullets but 1 CLAIM lines", r.stdout)

    def test_diamond_single_exit(self):
        chart = ("flowchart LR\n"
                 "A([\"<b>Boil</b><br/>• Boil water\"]):::altDx\n"
                 "D{\"Hot or iced\"}:::decisionNode\n"
                 "A -->|\"Hot\"| D\n"
                 "%% CLAIM C1 | Boil water in a kettle. | A\n")
        r = run_chart(chart)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("diamond D: needs >= 2 labeled exits", r.stdout)

    def test_unreachable_node(self):
        chart = GOOD.replace("A --> B\nB --> C", "A --> B")
        r = run_chart(chart)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("node C: unreachable", r.stdout)

    def test_banned_char_in_label(self):
        bad = GOOD.replace("• Boil water", "• Hot % tea")
        r = run_chart(bad)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("node A: label contains '%'", r.stdout)

    def test_banned_slash_in_label(self):
        bad = GOOD.replace("• Boil water", "• Boil/pour tea")
        r = run_chart(bad)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("node A: label contains '/'", r.stdout)

    def test_sourced_intensity_no_warn(self):
        source = ("Boil water in a kettle.\n"
                  "Severe heat cracks the pot.\n")
        chart = ("flowchart LR\n"
                 "A([\"<b>Boil</b><br/>• Severe heat\"]):::altDx\n"
                 "B([\"<b>Crack</b><br/>• Cracked pot\"]):::altDx\n"
                 "A --> B\n"
                 "%% CLAIM C1 | Boil water in a kettle. | A\n"
                 "%% CLAIM C2 | Severe heat cracks the pot. | B\n")
        r = run_chart(chart, source=source)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("intensity words", r.stdout)

    def test_heading_boundary_numeric_claim(self):
        source = ("# Title\n\n## Background\n\n"
                  "Assessment of visual acuity depends on the optotypes used for measurement.\n"
                  "100 patients were tested.\n")
        chart = ("flowchart LR\n"
                 "A([\"<b>Back</b><br/>• Assessment test\"]):::altDx\n"
                 "B([\"<b>Group</b><br/>• Patient group\"]):::altDx\n"
                 "A --> B\n"
                 "%% CLAIM C1 | Assessment of visual acuity depends on the optotypes used for measurement. | A\n"
                 "%% CLAIM C2 | 100 patients were tested. | B\n")
        r = run_chart(chart, source=source)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(r.stdout.strip().endswith("PASS"), r.stdout)


if __name__ == "__main__":
    unittest.main()
