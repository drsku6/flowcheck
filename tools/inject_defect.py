"""Make a verifier-grade defect: swap two CLAIM quotes between nodes.

The swapped quotes stay verbatim in the source, so validate_mmd.py still
PASSes -- but each sits on the wrong node, so the verifier FAILs it.
Demo use: trust punch after a clean audit.

usage: inject_defect.py <chart.mmd> --swap C1 C2 -o <out.mmd>
"""
import argparse
import re
import sys
from pathlib import Path

CLAIM_RE = re.compile(r"^(\s*%% CLAIM C\d+ \| )(.*)( \| \w+\s*)$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chart")
    ap.add_argument("--swap", nargs=2, required=True, metavar=("C1", "C2"))
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    for c in args.swap:
        if not re.fullmatch(r"C\d+", c):
            sys.exit(f"error: bad claim id {c!r}, want like C1")

    lines = Path(args.chart).read_text(encoding="utf-8").splitlines()
    idx = {}
    for i, ln in enumerate(lines):
        m = re.match(r"\s*%% CLAIM (C\d+) \| .* \| \w+\s*$", ln)
        if m:
            idx[m.group(1)] = i
    try:
        i, j = idx[args.swap[0]], idx[args.swap[1]]
    except KeyError as e:
        sys.exit(f"error: claim not in chart: {e}")
    if i == j:
        sys.exit("error: swap needs two different claims")

    qi = CLAIM_RE.match(lines[i]).group(2)
    qj = CLAIM_RE.match(lines[j]).group(2)
    lines[i] = CLAIM_RE.sub(lambda m: m.group(1) + qj + m.group(3),
                            lines[i], count=1)
    lines[j] = CLAIM_RE.sub(lambda m: m.group(1) + qi + m.group(3),
                            lines[j], count=1)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"swapped {args.swap[0]} <-> {args.swap[1]} -> {args.out}")


if __name__ == "__main__":
    main()
