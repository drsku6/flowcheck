# What each file does, and where Meta Muse is used

Model everywhere below is Meta Muse (`muse-spark-1.2` via the Meta Model API).
"Meta Muse: no" means deterministic code. Cards are knowledge Meta Muse reads, not calls.

| File | Does | Meta Muse |
|---|---|---|
| `orchestrator.py` | One command driving the whole flow; skips existing output unless `--force`; refuses sources over 50K chars; spawns stages, repairs, writes atomically | no (spawns model stages) |
| `ingest.py` | URL/file → clean markdown + provenance JSON | no |
| `writer.py` | Drafts the one chart (classifies type in-call); `revise_chart` per instruction; marks residual failures red | yes — 1 call + repairs |
| `verifier.py` | Fresh VERIFY_CARD audit of source + chart | yes — 1 call, `--verify` only |
| `common.py` | Shared verbatim-match helpers (`norm`, `quote_in_source`) | no |
| `tools/validate_mmd.py` | Mechanical gates: verbatim quotes, counts, exits, labels | no |
| `tools/inject_refs.py` | Stamps the REFS/license block onto charts | no |
| `tools/inject_defect.py` | Swaps two CLAIM quotes for a verifier-grade demo defect | no |
| `tests/test_common.py` | Offline checks for `norm` + `quote_in_source` (stdlib unittest) | no |
| `tests/test_validate_mmd.py` | Offline gate checks driving the real validator CLI | no |
| `tests/test_server.py` | Offline checks for report-type parsing + id slugify | no |
| `tests/test_inject_defect.py` | Swap keeps validator PASS (quotes stay verbatim) | no |
| `tests/test_revise.py` | Revise reply parsing, request validation, chat routing | no |
| `cards/WRITER_CARD.md` | Universal chart rules the writer follows | read by Meta Muse |
| `cards/VERIFY_CARD.md` | PASS/FAIL rules the verifier follows | read by Meta Muse |
| `cards/STYLE_TARGET.mmd` | ClassDefs + node syntax the writer copies | read by Meta Muse |
| `cards/profiles/*.md` (6) | Node/diamond/edge/bullet meaning per text type | read by Meta Muse |
| `skills/flowcheck-chart/SKILL.md` | Agentic chart-building role for AI assistants | executed by Meta Muse |
| `skills/flowcheck-verify/SKILL.md` | Agentic read-only audit role for AI assistants | executed by Meta Muse |
| `server.py` | Web UI backend; `/api/chat` routes build vs revise; spawns pipeline | no (spawns pipeline) |
| `ui/index.html`, `ui/app.js`, `ui/style.css` | Gallery, viewer, evidence drawer, chat panel, footer | no |
| `ui/vendor/mermaid.min.js` | Renders flowcharts in the browser (v10.9.1, MIT) | no |
| `ui/vendor/svg-pan-zoom.min.js` | Pan/zoom interaction (v3.6.1, BSD-2-Clause) | no |
| `ui/vendor/LICENSES.md` | Full license texts for the vendored files | no |
| `input/` | Drop inputs here; everything inside stays local-only | no |
| `output/` | Charts + reports land here; everything inside stays local-only | product of Meta Muse calls |
| `output/.gitkeep` | Keeps empty `output/` committable | no |
| `requirements.txt` | Pinned Python deps (openai, dotenv, pdfplumber) | no |
| `.env.example` | Template for `MODEL_API_KEY` | no |
| `.gitignore` | Keeps secrets, scratch, inputs, outputs, venv out of git | no |
| `LICENSE` | MIT licence of this repo | no |
| `README.md` | Setup, run forms, pipeline, sources, limitations | no |
| `THIRD_PARTY.md` | All third-party components + licences | no |
| `docs/workflow.mmd` | This repo's workflow as a diagram | no |
| `docs/FILES.md` | This table | no |
| `docs/demo-script.md` | Demo video plan (local only, gitignored) | no |
| `docs/judging-punchlist.md` | Rubric punch list (local only, gitignored) | no |

Ignored at runtime, not repo content: `workspace/` (per-run scratch),
`.venv/`, `.env`, untracked scratch inputs/outputs.

Skills under `skills/` are local drafts: assistants auto-load only from
`.agents/skills/` (not writable from here), so move them there and run
`muse skills validate` manually before use.
