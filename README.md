# flowcheck

Writer agent drafts a Mermaid flowchart from any open-licensed source text, each node carrying a verbatim quote. An independent verifier checks every node against the source and outputs a discrepancy report. Content QA, not medical advice.

Work started 2026-10-27 for the Meta Global AI Developer Hackathon (indie track). The legal-agent-workshop pattern was studied; no code was reused.

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
