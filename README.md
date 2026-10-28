# flowcheck

Target design: a writer agent drafts a Mermaid flowchart from any open-licensed source text, each node carrying a verbatim quote; an independent verifier checks every node against the source and outputs a discrepancy report. Content QA, not medical advice.

Exist today: ingest, extractor, structurer, renderer. Not built yet: verifier.

Work started 2026-10-27 for the Meta Global AI Developer Hackathon (indie track). The legal-agent-workshop pattern was studied; no code was reused.

## Pipeline

Four stages, run in order. `<id>` names one source end to end.

```sh
python ingest.py <file_or_url> --id <id>          # -> workspace/<id>_source.md + _source.json
python extractor.py workspace/<id>_source.md --id <id>  # -> workspace/<id>_extract.json
python structurer.py --id <id>                    # -> workspace/<id>_graph.json
python renderer.py --id <id>                      # -> workspace/<id>.mmd
```

- `ingest.py`: file (pdf, html, txt/md, docx, epub, pub via soffice) or URL to clean markdown plus provenance. No model calls. On wikipedia.org URLs it drops references/navboxes/edit markers, stops before appendix sections, pins the revision in provenance, and identifies as `flowcheck-bot/0.1`.
- `extractor.py`: model lists procedure steps/decision points with verbatim quotes; code verifies each quote against the source. The only stage that reads the source text.
- `structurer.py`: model decides graph structure only (edges, labels, unused); code owns all text, validates the graph, retries once. Node/edge text is copied from extractor items by id, never model-written.
- `renderer.py`: deterministic, no model call; unverified nodes and edges are styled red.

## Layout

- `data/` (never committed): local test inputs — `tests/` PDFs and fixtures, `legal/` text.
- `samples/` (committed): `SOURCES.md` documents every source (file, URL, publisher, license); `samples/tests/` holds the stdlib-built fixtures.
- `workspace/` (never committed): per-source outputs (`_source`, `_extract`, `_graph`).

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `MODEL_API_KEY` to `.env`. Never commit `.env` or `data/`.

## Models

Muse Spark via the Meta Model API.

## Sources and licenses

Test inputs live in `data/` (never committed) and are documented in `samples/SOURCES.md` with file, URL, publisher, license, and fetch date.

- Allowed: Wikipedia text (CC BY-SA 4.0), US government works, Illustrative Mathematics first edition (CC BY 4.0).
- Not used: OpenStax (CC BY-NC-SA plus an LLM-ingestion prohibition, checked 2026-10-27), CK-12, Utah OER (non-commercial).
- Rule: check the live license page before adding a source, then add a SOURCES.md row.

## Known limitations

1. PDF tables without ruled lines get no row structure (their text still extracts as body lines).
2. HTML from government sites keeps some banner text.
3. Structurer edges are checked only for quote existence until the verifier stage exists.
4. Wikipedia ingests are revision-pinned snapshots; later article edits require a re-fetch.
5. Flowcharts derived from Wikipedia text must be shared under CC BY-SA 4.0 with attribution.
6. Wikipedia cleaning relies on standard class names, so some page text can survive.
7. Sub/superscript spacing (e.g. "CO 2") can fail the exact-match quote check.
