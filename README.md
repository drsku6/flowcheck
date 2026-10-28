# flowcheck

Turns an open-licensed source text into a Mermaid flowchart where every node carries a verbatim quote and an independent verifier checks each node and edge. Content QA, not medical advice.

## Pipeline

Five stages, run in order. `<id>` names one source end to end.

```sh
python ingest.py <file_or_url> --id <id>          # -> workspace/<id>_source.md + _source.json
python extractor.py workspace/<id>_source.md --id <id>  # -> workspace/<id>_extract.json
python structurer.py --id <id>                    # -> workspace/<id>_graph.json
python renderer.py --id <id>                      # -> workspace/<id>.mmd
python verifier.py --id <id>                      # -> workspace/<id>_verify.json + _report.md
```

Or run everything at once (ingest + extractor, then structurer/verifier feedback rounds, then render):

```sh
python orchestrator.py input/<name> [--max-rounds 3]  # one file
python orchestrator.py --all [--max-rounds 3]         # every file in input/
```

The orchestrator loops structurer/verifier (default max 3 rounds); rounds whose repairs delete flagged content are rejected, and per-round `_graph_r<n>`/`_verify_r<n>` snapshots are kept.

- `ingest.py`: file (pdf, html, txt/md, docx, epub, pub via soffice) or URL to clean markdown plus provenance. No model calls. On wikipedia.org URLs it drops references/navboxes/edit markers, stops before appendix sections, pins the revision in provenance, and identifies as `flowcheck-bot/0.1`.
- `extractor.py`: model lists procedure steps/decision points with verbatim quotes; code verifies each quote against the source. The only stage that reads the source text.
- `structurer.py`: model decides graph structure only (edges, labels, unused); code owns all text, validates the graph, retries once. Node/edge text is copied from extractor items by id, never model-written.
- `renderer.py`: deterministic, no model call; unverified nodes and edges are styled red.
- `verifier.py`: independent model judgment on whether each node quote supports its claim and each labeled edge quote supports its transition; code enforces quote existence and verdict shape. Writes machine-readable verdicts plus a discrepancy report.

## Layout

- `input/` (bundled examples committed): `calvin-cycle.url`, `legal-sample.txt`. Other files placed here are ignored.
- `output/` (generated): `output/<name>.mmd` and `output/<name>_report.md` per input.
- `workspace/` (never committed): per-source working outputs (`_source`, `_extract`, `_graph`, `.mmd`, `_verify`, `_report`, plus orchestrator `_graph_r<n>`/`_verify_r<n>` snapshots and `_feedback`).

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `MODEL_API_KEY` to `.env`. Never commit `.env`.

## Run on your own text

Setup first (venv, dependencies, `.env` with `MODEL_API_KEY` — see Setup above).

Put files in `input/` (or run the bundled examples as they are), then run one file:

```sh
python orchestrator.py input/calvin-cycle.url
```

or everything with:

```sh
python orchestrator.py --all
```

Files with an existing `output/<name>.mmd` are skipped (`skip <name>: output exists`); add `--force` to reprocess, or delete `output/<name>.mmd` to reprocess that file. A failed file writes no output, so the next run retries it.

Read `output/<name>.mmd` (Mermaid; paste into mermaid.live or any Mermaid viewer) and `output/<name>_report.md` (discrepancies).

Input notes: the text needs a procedure (steps or decisions); scanned PDFs are rejected; plain `.txt` is safest; Wikipedia URLs are cleaned automatically.

License note: you are responsible for the license of third-party text; charts derived from Wikipedia text must be shared CC BY-SA 4.0 with attribution.

### Run stages one by one

```sh
python ingest.py <file_or_url> --id myid
python extractor.py workspace/myid_source.md --id myid
python structurer.py --id myid
python renderer.py --id myid
python verifier.py --id myid
```

## Models

Muse Spark via the Meta Model API.

## Sources

| file | URL | publisher | license | date fetched |
|---|---|---|---|---|
| input/legal-sample.txt | https://www.uspto.gov/trademarks/trademark-timelines/section-1a-timeline-application-based-use-commerce | U.S. Patent and Trademark Office | US government work, public domain | 2026-10-27 |
| input/calvin-cycle.url | https://en.wikipedia.org/w/index.php?oldid=1382160955 | Wikipedia contributors | CC BY-SA 4.0, text only, derived output is share-alike | 2026-10-27 |

- Allowed: Wikipedia text (CC BY-SA 4.0), US government works, Illustrative Mathematics first edition (CC BY 4.0).
- Not used: OpenStax (CC BY-NC-SA plus an LLM-ingestion prohibition, checked 2026-10-27), CK-12, Utah OER (non-commercial).
- Rule: check the live license page before adding a source, then add a row above.

## Known limitations

1. PDF tables without ruled lines get no row structure (their text still extracts as body lines).
2. HTML from government sites keeps some banner text.
3. Structurer edges are checked only for quote existence; the verifier entailment-checks each labeled edge against its endpoint claims.
4. Wikipedia ingests are revision-pinned snapshots; later article edits require a re-fetch.
5. Flowcharts derived from Wikipedia text must be shared under CC BY-SA 4.0 with attribution.
6. Wikipedia cleaning relies on standard class names, so some page text can survive.
7. Sub/superscript spacing (e.g. "CO 2") can fail the exact-match quote check.
