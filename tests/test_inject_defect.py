"""Offline checks for tools/inject_defect.py: swap keeps verbatim PASS."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ("Boil water in a kettle.\n"
          "Pour the water over tea leaves.\n")

CHART = """flowchart LR
A(["<b>Boil</b><br/>• Boil water"]):::altDx
B(["<b>Pour</b><br/>• Pour water"]):::altDx
A --> B
%% CLAIM C1 | Boil water in a kettle. | A
%% CLAIM C2 | Pour the water over tea leaves. | B
"""


def run(*argv, cwd=ROOT):
    return subprocess.run([sys.executable, *argv], capture_output=True,
                          text=True, cwd=cwd)


class TestInjectDefect(unittest.TestCase):
    def test_swap_keeps_verbatim_pass(self):
        with tempfile.TemporaryDirectory() as d:
            c, s, o = Path(d, "t.mmd"), Path(d, "t.md"), Path(d, "bad.mmd")
            c.write_text(CHART, encoding="utf-8")
            s.write_text(SOURCE, encoding="utf-8")
            r = run("tools/inject_defect.py", str(c), "--swap", "C1", "C2",
                    "-o", str(o))
            self.assertEqual(r.returncode, 0, r.stderr)
            bad = o.read_text(encoding="utf-8")
            self.assertIn("%% CLAIM C1 | Pour the water over tea leaves. | A", bad)
            self.assertIn("%% CLAIM C2 | Boil water in a kettle. | B", bad)
            v = run("tools/validate_mmd.py", str(o), str(s))
            self.assertEqual(v.returncode, 0, v.stdout)
            self.assertIn("PASS", v.stdout)

    def test_unknown_claim_fails(self):
        with tempfile.TemporaryDirectory() as d:
            c, o = Path(d, "t.mmd"), Path(d, "bad.mmd")
            c.write_text(CHART, encoding="utf-8")
            r = run("tools/inject_defect.py", str(c), "--swap", "C1", "C9",
                    "-o", str(o))
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
