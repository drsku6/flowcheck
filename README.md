# flowcheck

Target design: a writer agent drafts a Mermaid flowchart from any open-licensed source text, each node carrying a verbatim quote; an independent verifier checks every node against the source and outputs a discrepancy report. Content QA, not medical advice.

Exist today: ingest, extractor, structurer. Not built yet: renderer and verifier.

Work started 2026-10-27 for the Meta Global AI Developer Hackathon (indie track). The legal-agent-workshop pattern was studied; no code was reused.

## Pipeline

Three stages, run in order. `<id>` names one source end to end.

```sh
python ingest.py <file_or_url> --id <id>          # -> workspace/<id>_source.md + _source.json
python extractor.py workspace/<id>_source.md --id <id>  # -> workspace/<id>_extract.json
python structurer.py --id <id>                    # -> workspace/<id>_graph.json
```

- `ingest.py`: file (pdf, html, txt/md, docx, epub, pub via soffice) or URL to clean markdown plus provenance. No model calls.
- `extractor.py`: model lists procedure steps/decision points with verbatim quotes; code verifies each quote against the source. The only stage that reads the source text.
- `structurer.py`: model decides graph structure only (edges, labels, unused); code owns all text, validates the graph, retries once. Node/edge text is copied from extractor items by id, never model-written.

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

## Known limitations

1. PDF tables without ruled lines get no row structure (their text still extracts as body lines).
2. HTML from government sites keeps some banner text.
3. Structurer edges are checked only for quote existence until the verifier stage exists.
