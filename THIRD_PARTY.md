# Third-party components

Everything else in this repo (pipeline, cards, tools, server, UI) was written
fresh for it. Third-party pieces in use:

## JavaScript dependencies (`ui/package.json`, installed not vendored)

- Mermaid 11, MIT — github.com/mermaid-js/mermaid. Renders the flowcharts.
- svg-pan-zoom 3.6, BSD-2-Clause — github.com/bumbu/svg-pan-zoom.
  Pan/zoom interaction on the chart.
- React 19 + React DOM 19, MIT — react.dev. UI components and rendering.
- Tailwind CSS 4, MIT — tailwindcss.com. Utility styling (built at
  `npm run build` time; no runtime code ships beyond generated CSS).
- Vite 6 (build tool only, not shipped), MIT — vite.dev.

## Python dependencies (`requirements.txt`, installed not vendored)

- openai 3.40.0, Apache-2.0 — github.com/openai/openai-python. SDK used to
  call the model API.
- python-dotenv 1.2.4, BSD-3-Clause — reads `MODEL_API_KEY` from `.env`.
- pdfplumber 0.11.10, MIT — github.com/jsvine/pdfplumber. PDF text/table
  extraction in `ingest.py`.
- Modal 1.6.3, Apache-2.0 — modal.com. Deploy-only client used by
  `modal_app.py`; not needed for local runs.

## Source data (never committed; see README Licences)

- Wikipedia text: CC BY-SA 4.0, attribution required, derived charts share-alike.
- PubMedQA: MIT — github.com/pubmedqa/pubmedqa. Biomedical questions from
  PubMed abstracts; several demo charts derive from it.
- US government works: public domain.
