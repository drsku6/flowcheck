# Third-party components

Everything else in this repo (pipeline, cards, tools, server, UI) was written
fresh for it. Third-party pieces in use:

## Vendored JavaScript (shipped in `ui/vendor/`)

Full license texts: `ui/vendor/LICENSES.md`.

- Mermaid 10.9.1 (UMD build), MIT — Copyright (c) 2014–2022 Knut Sveidqvist.
  Source: github.com/mermaid-js/mermaid at tag v10.9.1. Renders the flowcharts;
  the bundle also includes third-party code (KaTeX 0.16.9 and others), each
  under its own permissive licence.
- svg-pan-zoom 3.6.1, BSD-2-Clause — Copyright 2009–2010 Andrea Leofreddi.
  Source: github.com/bumbu/svg-pan-zoom. Pan/zoom interaction on the chart.

## Python dependencies (`requirements.txt`, installed not vendored)

- openai 3.40.0, Apache-2.0 — github.com/openai/openai-python. SDK used to
  call the model API.
- python-dotenv 1.2.4, BSD-3-Clause — reads `MODEL_API_KEY` from `.env`.
- pdfplumber 0.11.10, MIT — github.com/jsvine/pdfplumber. PDF text/table
  extraction in `ingest.py`.

## Source data (never committed; see README Sources)

- Wikipedia text: CC BY-SA 4.0, attribution required, derived charts share-alike.
- US government works: public domain.
