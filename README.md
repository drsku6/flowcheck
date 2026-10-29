# flowcheck

Built for students, teachers, and visual learners. Turns an open-licensed source text into a Mermaid flowchart where every bullet is backed by a verbatim quote, with mechanical gates on every chart and an optional independent verifier. Content QA, not medical advice.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd ui && npm install && npm run build && cd ..
```

Add `MODEL_API_KEY` to `.env`. Never commit `.env`. Run the offline checks
(no key needed): `.venv/bin/python -m unittest discover -s tests`. The last
line (`cd ui && ...`) builds the web UI once; rebuild it after pulling UI
changes. It needs Node.js (any recent LTS).

## Two ways to run

Give any Wikipedia link:

```sh
.venv/bin/python orchestrator.py --url <wikipedia-link> --id <name>
```

Or drop a `.pdf`, `.md`, `.txt` or other file in `input/` and run:

```sh
.venv/bin/python orchestrator.py input/<file>
```

Use `--all` to run everything in `input/`, and `--verify` for the slower independent meaning check (see below). Pass `--draft` to skip the writer repair round: one model call, roughly half the wait, with defects left flagged red. A name that already has `output/<name>.mmd` is skipped; pass `--force` to reprocess it, or delete that `.mmd` to run it again. (The web UI always re-runs: its Build button means build.)

## Where the chart appears

`output/<name>.mmd` (Mermaid; paste into mermaid.live or any Mermaid viewer) and `output/<name>_report.md` (discrepancies, ending in `final status: clean` or `flagged: N remain`).

Prefer a viewer with pan and zoom? Start the bundled web UI:

```sh
.venv/bin/python server.py   # serves http://127.0.0.1:8000
```

It shows the `output/` gallery in a searchable sidebar, renders charts with
pan, zoom, and click-to-collapse branches, and runs the same orchestrator as
a subprocess. The New MMD tab builds charts from pasted text or a URL with a
Draft (one call, fast) or Verified (plus repair round) toggle; the Chat tab
revises the open chart from instructions (unsupported additions are refused).
Both side panels collapse to slim rails. Different charts build in parallel;
rebuilding the same chart waits for its own run to finish.

## Classroom use

Setup happens once on one machine (a teacher's or IT's): follow Setup above, then start the server and open `http://127.0.0.1:8000` in a browser. Only that machine needs the API key. From here no coding is required:
1. In the New MMD tab, type a short id, paste lesson text or a link, pick Draft or Verified, Build. A minute or more later, depending on text length, the chart renders; the footer shows its type, claim count, and flagged count.
2. Click a branch root to collapse or expand it. Red nodes with ⚠ are unverified — check them against the source before teaching them.
3. In the Chat tab, ask for changes ("drop node X", "add Y"). Additions need a source sentence or come back refused.
4. Share `output/<id>.mmd` plus its `_report.md`: project them, print them, or open the `.mmd` in mermaid.live.

Input notes: plain `.txt` is safest; scanned PDFs are rejected; Wikipedia pages are cleaned automatically. Keep sources under 50,000 characters (`wc -m` to check); split longer texts and run each part separately.

## How it works

Every model call goes to Muse Spark; the repo supplies the cards, the mechanical gates, and the repair loop around it.

- Ingest turns the link or file into clean markdown plus provenance (for Wikipedia: revision-pinned, references and navboxes dropped). No model call.
- Sources up to 50,000 characters run as one chart; longer sources are refused with a shorten-and-retry message.
- The writer drafts one Mermaid chart from a text-type profile (procedure, mechanism, classification, evidence, rules, general): flowchart LR, every bullet backed by a `%% CLAIM` line carrying a verbatim source sentence, no outside knowledge.
- A validator checks every CLAIM quote is verbatim in the source and well-formed (complete sentence, no dangling anaphor, starts at a sentence boundary), bullet and CLAIM counts match per node, numbers in labels come from the source, no fact repeats across nodes, diamonds have at least 2 labeled exits with routing (never filler) labels, all nodes are reachable, and loop-back edges carry labels. Added certainty words fail; intensity words, unknown long words, and forkless (linear) charts warn. On failure, near-verbatim quotes are first fixed locally without a model call; the writer gets one repair round for whatever remains (`--draft` skips it).
- With `--verify`, a verifier call judges meaning — whether each quote actually supports its claim — plus one fix round.
- Defects surviving repair stay visible instead of blocking: the node turns red, its edges go red, its bullets get a `⚠` prefix. Output is written atomically with a header naming model, source, and date.
- Two drivers run that flow, never together on one chart (see Two drivers below).

## Two drivers

Orchestrator path — a program drives. Run a command (or Build in the UI) and
the script ingests, drafts via the model, gates, repairs, publishes; you
watch. Flags: `--draft` for one fast call, `--verify` for the extra
meaning-check, `--force` to rebuild, `--all` for every file in `input/`.

Agentic path — an assistant drives. Ask any AI assistant working in this repo
to chart a text and it performs `skills/flowcheck-chart` by hand: stage the
source, draft from the cards, inject refs, validate, repair once, publish —
or audit read-only via `skills/flowcheck-verify`. Name the skill explicitly
(e.g. “Use skills/flowcheck-chart to chart …”): this repo has no
`.agents/skills/` loader directory, so assistants will not auto-load it. The
orchestrator program never starts. Same cards, tools, gates, and red-flag
visibility either way.

## Models

Muse Spark via the Meta Model API. Every model call — drafts, repairs,
revises, and `--verify` audits — runs on the fast `muse-spark-1.2`.

## Licences

You are responsible for the license of third-party text you feed in. Charts derived from Wikipedia text must be shared CC BY-SA 4.0 with attribution.

No inputs ship with the repo; everything under `input/` stays local-only. A known-good example is any pinned Wikipedia revision URL (the demo used the Calvin cycle snapshot).

- Allowed: Wikipedia text (CC BY-SA 4.0), US government works, Illustrative Mathematics first edition (CC BY 4.0).
- Rule: check the live license page before using a source.
- Third-party components and licences: THIRD_PARTY.md

## Known limitations

1. PDF tables without ruled lines get no row structure (their text still extracts as body lines).
2. HTML from government sites keeps some banner text.
3. The default path checks quotes exist verbatim; whether they support their claims is only judged with `--verify`.
4. Wikipedia ingests are revision-pinned snapshots; later article edits require a re-fetch.
5. Flowcharts derived from Wikipedia text must be shared under CC BY-SA 4.0 with attribution.
6. Wikipedia cleaning relies on standard class names, so some page text can survive.
7. Sub/superscript spacing (e.g. "CO 2") can fail the exact-match quote check.
8. Model output is nondeterministic: re-runs of the same input can differ in wording, flags, and chart shape.
