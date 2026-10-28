---
name: flowcheck-verify
description: Independently audit a finished flowcheck chart against its source text; read-only, never edits.
---

# Flowcheck Verify

Audit a finished chart against its source. Read-only: never edit charts, sources, or cards.

Use it for requests like "verify <id>", "check this chart", "audit output/<name>.mmd". If you drafted the chart yourself in this session, verify only in a fresh context.

Run everything from the repo root.

## Workflow

1. Read the source (`workspace/<id>_source.md`), the chart (`output/<id>.mmd`), and `cards/VERIFY_CARD.md`, which defines PASS/FAIL and the exact output format.
2. Run `python tools/validate_mmd.py <chart> <source>` for the mechanical gates.
3. Judge meaning yourself: every bullet supported by its CLAIM and nothing more; START matches the source with nothing established only later; branches and loop-backs stated by the source; hedges and numbers exact (compression preserving meaning is PASS; upgraded certainty or new numbers are FAIL); no fact stated twice; TAKE adds nothing beyond its CLAIMs; profile fit.
4. Report `<id>: PASS|FAIL`, one ` - node or edge -> defect -> fix per source` line per defect, `LOW-CONFIDENCE: <why>` lines, and `flagged: N remain`. Stop there; do not fix.
