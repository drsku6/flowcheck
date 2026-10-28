---
name: flowcheck-chart
description: Turn any source text into a verified Mermaid flowchart via the flowcheck cards and gates.
---

# Flowcheck Chart

Build a verified Mermaid flowchart from a Wikipedia link, pasted text, or a file, using this repo's cards and tools. If asked to check an existing chart instead, use flowcheck-verify.

Run everything from the repo root.

## Workflow

1. Get the source text and pick sid (lowercase stem, a-z0-9-).
   - URL or file: `python ingest.py <file_or_url> --id <sid>` writes `workspace/<sid>_source.md`.
   - Pasted text: save it to `workspace/<sid>_source.md` yourself, and write the matching `workspace/<sid>_source.json` with keys source, url_or_null, title, fetched_at, chars, pages.
   - Under ~25000 chars is one chart. Longer sources: `python analyst.py workspace/<sid>_source.md --id <sid>` (at most 3 units) and chart each unit.
2. Draft each chart yourself from `cards/WRITER_CARD.md` plus the matching `cards/profiles/<type>.md` and `cards/STYLE_TARGET.mmd`. Classify short sources yourself (procedure, mechanism, classification, evidence, rules, general). Every bullet and labeled edge gets a `%% CLAIM` line with one complete verbatim source sentence.
3. Save the draft to `workspace/<sid>.mmd` (`workspace/<sid>_<n>.mmd` per unit). Run `python tools/inject_refs.py <chart> --id <sid>`, then `python tools/validate_mmd.py <chart> workspace/<sid>_source.md`.
4. On FAIL, fix only what the validator names (near-verbatim quotes first, replaced with the exact source sentence), re-run inject plus validate. At most 2 redrafts; remaining failures stay red (safetyNode class, red linkStyle, ⚠ bullet prefix).
5. Publish atomically: write to a temp file in `output/`, then `os.replace` to `output/<stem>.mmd` (`_<n>` per unit), prepended with `%% generated via flowcheck-chart | source: <url-or-input> | <date>`. Copy the report to `output/<stem>_report.md`. Same name replaces; never touch other ids' files.

(Headless equivalent of steps 1–5: `python orchestrator.py input/<file>`, `--text`, or `--url`.)

## Rules

- Only facts stated in the source. Keep hedges and numbers exactly as written.
- Omit what is uncertain and list it as LOW-CONFIDENCE with why.
- Never edit the source, the cards, or another id's outputs.
