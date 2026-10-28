# flowcheck

Built for students, teachers, and visual learners. Turns an open-licensed source text into a Mermaid flowchart where every bullet is backed by a verbatim quote, with an independent verifier checking each node and edge. Content QA, not medical advice.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `MODEL_API_KEY` to `.env`. Never commit `.env`. Run the offline checks
(no key needed): `.venv/bin/python -m unittest discover -s tests`.

## Two ways to run

Give any Wikipedia link:

```sh
.venv/bin/python orchestrator.py --url <wikipedia-link> --id <name>
```

Or drop a `.pdf`, `.md`, `.txt` or other file in `input/` and run:

```sh
.venv/bin/python orchestrator.py input/<file>
```

Use `--all` to run everything in `input/`, and `--verify` for the slower independent meaning check (see below). A name that already has `output/<name>.mmd` is skipped; pass `--force` to reprocess it, or delete that `.mmd` to run it again.

## Where the chart appears

`output/<name>.mmd` (Mermaid; paste into mermaid.live or any Mermaid viewer) and `output/<name>_report.md` (discrepancies, ending in `final status: clean` or `flagged: N remain`).

Prefer a viewer with pan and zoom? Start the bundled web UI:

```sh
.venv/bin/python server.py   # serves http://127.0.0.1:8000
```

It shows the `output/` gallery, runs the same orchestrator as a subprocess from pasted text or a URL, opens an evidence drawer with the verbatim quotes behind any clicked node, and revises charts from chat instructions (unsupported additions are refused).

Input notes: plain `.txt` is safest; scanned PDFs are rejected; Wikipedia pages are cleaned automatically. Keep sources under 50,000 characters (`wc -m` to check); split longer texts and run each part separately.

## How it works

Every model call goes to Muse Spark; the repo supplies the cards, the mechanical gates, and the repair loop around it.

- Ingest turns the link or file into clean markdown plus provenance (for Wikipedia: revision-pinned, references and navboxes dropped). No model call.
- Sources up to 50,000 characters run as one chart; longer sources are refused with a shorten-and-retry message.
- The writer drafts one Mermaid chart from a text-type profile (procedure, mechanism, classification, evidence, rules, general): flowchart LR, every bullet backed by a `%% CLAIM` line carrying a verbatim source sentence, no outside knowledge.
- A validator checks every CLAIM quote is verbatim in the source and well-formed (complete sentence, no dangling anaphor, starts at a sentence boundary), bullet and CLAIM counts match per node, numbers in labels come from the source, no fact repeats across nodes, diamonds have at least 2 labeled exits with routing (never filler) labels, all nodes are reachable, and loop-back edges carry labels. Added certainty words fail; intensity words and unknown long words warn. On failure, near-verbatim quotes are first fixed locally without a model call; the writer gets one repair round for whatever remains.
- With `--verify`, a verifier call judges meaning — whether each quote actually supports its claim — plus one fix round.
- Defects surviving repair stay visible instead of blocking: the node turns red, its edges go red, its bullets get a `⚠` prefix. Output is written atomically with a header naming model, source, and date.
- The same flow runs agentically: `skills/flowcheck-chart` builds charts conversationally and `skills/flowcheck-verify` audits them, through any AI assistant working in this repo.

## Models

Muse Spark via the Meta Model API.

## Licences

You are responsible for the license of third-party text you feed in. Charts derived from Wikipedia text must be shared CC BY-SA 4.0 with attribution.

| file | URL | publisher | license | date fetched |
|---|---|---|---|---|
| input/calvin-cycle.url | https://en.wikipedia.org/w/index.php?oldid=1382160955 | Wikipedia contributors | CC BY-SA 4.0, text only, derived output is share-alike | 2026-10-27 |

- Allowed: Wikipedia text (CC BY-SA 4.0), US government works, Illustrative Mathematics first edition (CC BY 4.0).
- Not used: OpenStax (CC BY-NC-SA plus a Meta Muse-ingestion prohibition, checked 2026-10-27), CK-12, Utah OER (non-commercial).
- Rule: check the live license page before adding a source, then add a row above.
- Third-party components and licences: THIRD_PARTY.md, ui/vendor/LICENSES.md

## Known limitations

1. PDF tables without ruled lines get no row structure (their text still extracts as body lines).
2. HTML from government sites keeps some banner text.
3. The default path checks quotes exist verbatim; whether they support their claims is only judged with `--verify`.
4. Wikipedia ingests are revision-pinned snapshots; later article edits require a re-fetch.
5. Flowcharts derived from Wikipedia text must be shared under CC BY-SA 4.0 with attribution.
6. Wikipedia cleaning relies on standard class names, so some page text can survive.
7. Sub/superscript spacing (e.g. "CO 2") can fail the exact-match quote check.
8. Model output is nondeterministic: re-runs of the same input can differ in wording, flags, and chart shape.
