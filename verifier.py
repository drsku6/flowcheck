import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from common import quote_in_source

ALLOWED = {"supported", "unsupported", "unclear"}

PROMPT = """You verify a flowchart against its source text. Reply with raw JSON only, no fences, no commentary.

SOURCE TEXT:
<<<SOURCE>>>

NODES (id | type | claim | quote):
<<<NODES>>>

EDGES (from -> to | label | quote | from-claim | to-claim), labeled edges only:
<<<EDGES>>>

DETAILS (node-id#index | bullet text | bullet quote):
<<<DETAILS>>>

You may call check_quote to confirm a passage appears verbatim in the source.

Return {"verdicts": [{"kind": "node", "id": "<id>", "verdict": "supported|unsupported|unclear", "reason": "<one sentence>", "evidence_quote": "<verbatim passage or empty>"}, {"kind": "edge", "from": "<id>", "to": "<id>", "verdict": "supported|unsupported|unclear", "reason": "<one sentence>", "evidence_quote": "<verbatim passage or empty>"}, {"kind": "detail", "id": "<node-id>", "index": <bullet index>, "verdict": "supported|unsupported|unclear", "reason": "<one sentence>", "evidence_quote": "<verbatim passage or empty>"}]}.
Rules:
- Node: does the quote support the claim?
- Edge: does the quote support the transition from -> to under that label, judged against both endpoint claims?
- Bullet: does the bullet quote support the bullet text?
- evidence_quote must be copied verbatim from the source; "" if none.
- Give one verdict per listed node, bullet and labeled edge."""

TOOLS = [{"type": "function", "name": "check_quote",
          "description": "Check whether an exact passage appears verbatim in the source text.",
          "parameters": {"type": "object", "properties": {"quote": {"type": "string"}},
                         "required": ["quote"]}}]


def judge(client, first_input, source):
    """One judging call with tool rounds; returns (text, tool-call count)."""
    try:
        calls_made = 0
        resp = client.responses.create(model="muse-spark-1.3", input=first_input, tools=TOOLS)
        for _ in range(3):  # tool-round cap
            calls = [o for o in resp.output if getattr(o, "type", "") == "function_call"]
            if not calls:
                break
            outs = []
            for c in calls:
                calls_made += 1
                try:
                    q = json.loads(c.arguments or "{}").get("quote", "")
                    ok = quote_in_source(q, source)
                except Exception:
                    ok = False
                outs.append({"type": "function_call_output", "call_id": c.call_id,
                             "output": json.dumps({"found": ok})})
            resp = client.responses.create(model="muse-spark-1.3", input=outs,
                                           previous_response_id=resp.id, tools=TOOLS)
        return resp.output_text, calls_made
    except Exception:
        resp = client.responses.create(model="muse-spark-1.3", input=first_input)
        return resp.output_text, 0


def card_mode(client, sid, chart_path, source, call_n=1):
    """Fresh VERIFY_CARD read of a finished chart; defects become verify results."""
    card = Path("cards/VERIFY_CARD.md").read_text(encoding="utf-8")
    chart = Path(chart_path).read_text(encoding="utf-8")
    first = (card + "\n\nSOURCE TEXT:\n" + source + "\n\nCHART:\n" + chart)
    raw = None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        resp = client.responses.create(model="muse-spark-1.3", input=first)
        raw = resp.output_text
        print(f"[verifier] call {call_n} attempt {attempt} "
              f"{time.perf_counter() - t0:.1f}s", flush=True)
        if raw.strip().startswith(f"{sid}:"):
            break
        first += f"\nYour reply must start with '{sid}: PASS' or '{sid}: FAIL'."
    else:
        raw = raw or ""
    if not raw.strip().startswith(f"{sid}:"):
        sys.exit("error: verifier output missing PASS/FAIL header after retry")
    lines = [l.rstrip() for l in raw.strip().splitlines()]
    defects = [l for l in lines if l.startswith(" - ")]
    results = [{"kind": "defect", "id": d[3:].split(" -> ")[0].strip() or "chart",
                "verdict": "unsupported", "reason": d[3:],
                "evidence_quote": "", "evidence_found": False} for d in defects]
    atomic_write(Path("workspace", f"{sid}_verify.json"),
                 json.dumps({"results": results, "tool_calls": 0}, indent=2))
    if not any(l.startswith("flagged:") for l in lines):
        lines.append(f"flagged: {len(defects)} remain")
    atomic_write(Path("workspace", f"{sid}_report.md"), "\n".join(lines) + "\n")
    print("\n".join(lines))


def parse(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else ""
    v = json.loads(text.strip())
    if not isinstance(v, dict) or not isinstance(v.get("verdicts"), list):
        raise ValueError("model output is not {verdicts: [...]}")
    return v["verdicts"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, dest="source_id")
    ap.add_argument("--chart", default=None, help="card mode: verify this chart file")
    ap.add_argument("--call-n", type=int, default=1, help="call number for logging")
    args = ap.parse_args()
    sid = args.source_id
    try:
        source = Path("workspace", f"{sid}_source.md").read_text(encoding="utf-8")
        if args.chart is None:
            graph = json.loads(Path("workspace", f"{sid}_graph.json").read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        sys.exit(f"error: missing input: {e.filename}")

    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)

    if args.chart is not None:
        card_mode(client, sid, args.chart, source, args.call_n)
        return

    by_id = {n["id"]: n for n in graph["nodes"]}
    nodes_txt = "\n".join(f"{n['id']} | {n.get('type')} | {n.get('claim')} | {n.get('quote')}"
                          for n in graph["nodes"])
    lab_edges = [e for e in graph["edges"] if (e.get("label") or "").strip()]
    edges_txt = "\n".join(
        f"{e['from']} -> {e['to']} | {e.get('label')} | {e.get('quote')} | "
        f"{by_id.get(e['from'], {}).get('claim')} | {by_id.get(e['to'], {}).get('claim')}"
        for e in lab_edges)
    det_input = [(n["id"], i, d) for n in graph["nodes"] for i, d in enumerate(n.get("details", []))]
    details_txt = "\n".join(f"{nid}#{i} | {d.get('text')} | {d.get('quote')}" for nid, i, d in det_input)
    first = (PROMPT.replace("<<<SOURCE>>>", source)
             .replace("<<<NODES>>>", nodes_txt).replace("<<<EDGES>>>", edges_txt)
             .replace("<<<DETAILS>>>", details_txt))

    raw, verdicts, tool_calls = None, None, 0
    for _ in range(2):  # one try + one retry on unparseable JSON
        try:
            raw, tool_calls = judge(client, first, source)
            verdicts = parse(raw)
            break
        except (ValueError, json.JSONDecodeError, KeyError) as e:
            verdicts = None
            print(f"retrying after parse failure: {e}")
    if verdicts is None:
        sys.exit("error: verifier output unparseable after retry")

    by_key = {}
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        if v.get("kind") == "node" and v.get("id") in by_id:
            by_key[("node", v["id"])] = v
        elif v.get("kind") == "edge":
            by_key[("edge", v.get("from"), v.get("to"))] = v
        elif v.get("kind") == "detail":
            by_key[("detail", v.get("id"), v.get("index"))] = v

    def settle(v, source):
        verdict = v.get("verdict") if v.get("verdict") in ALLOWED else "unclear"
        reason = v.get("reason") or "model returned no usable verdict for this item"
        ev = v.get("evidence_quote") or ""
        found = quote_in_source(ev, source) if ev.strip() else False
        if ev.strip() and not found:  # cited evidence must exist
            verdict, reason = "unclear", reason + " [cited evidence not found in source]"
        return verdict, reason, ev, found

    results = []
    for n in graph["nodes"]:
        verdict, reason, ev, found = settle(by_key.get(("node", n["id"]), {}), source)
        results.append({"kind": "node", "id": n["id"], "claim": n.get("claim"),
                        "verdict": verdict, "reason": reason,
                        "evidence_quote": ev, "evidence_found": found})
        for i, d in enumerate(n.get("details", [])):
            verdict, reason, ev, found = settle(by_key.get(("detail", n["id"], i), {}), source)
            results.append({"kind": "detail", "id": n["id"], "index": i, "claim": d.get("text"),
                            "verdict": verdict, "reason": reason,
                            "evidence_quote": ev, "evidence_found": found})
    for e in graph["edges"]:
        if not (e.get("label") or "").strip():
            results.append({"kind": "edge", "from": e["from"], "to": e["to"],
                            "label": e.get("label"), "verdict": "not checked",
                            "reason": "unlabeled edge carries no evidence",
                            "evidence_quote": "", "evidence_found": False})
            continue
        v = by_key.get(("edge", e["from"], e["to"]), {})
        verdict = v.get("verdict") if v.get("verdict") in ALLOWED else "unclear"
        reason = v.get("reason") or "model returned no usable verdict for this item"
        ev = v.get("evidence_quote") or ""
        found = quote_in_source(ev, source) if ev.strip() else False
        if ev.strip() and not found:
            verdict, reason = "unclear", reason + " [cited evidence not found in source]"
        results.append({"kind": "edge", "from": e["from"], "to": e["to"],
                        "label": e.get("label"), "verdict": verdict, "reason": reason,
                        "evidence_quote": ev, "evidence_found": found})

    atomic_write(Path("workspace", f"{sid}_verify.json"),
                 json.dumps({"results": results, "tool_calls": tool_calls}, indent=2))
    bad = [r for r in results if r["verdict"] not in ("supported", "not checked")]
    md = [f"# Verification: {sid}", ""]
    if bad:
        md += ["| id | claim / label | verdict | reason |", "|---|---|---|---|"]
        for r in bad:
            if r["kind"] == "detail":
                what = f"{r.get('id')}#{r.get('index')}"
            else:
                what = r.get("id") or f"{r.get('from')} -> {r.get('to')}"
            md.append(f"| {what} | {(r.get('claim') or r.get('label') or '').replace('|', '/')} "
                      f"| {r['verdict']} | {r['reason'].replace('|', '/')} |")
        md.append("")
    unrep = sorted({f"{r['id']}#{r['index']}" for r in results
                    if r["kind"] == "detail" and r["verdict"] not in ("supported",)})
    if unrep:
        md.append(f"Unrepairable by writer: {', '.join(unrep)}")
        md.append("")
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    summary = (f"{counts.get('supported', 0)} supported, {counts.get('unsupported', 0)} unsupported, "
               f"{counts.get('unclear', 0)} unclear, {counts.get('not checked', 0)} not checked "
               f"out of {len(results)} items.")
    md.append(summary)
    atomic_write(Path("workspace", f"{sid}_report.md"), "\n".join(md) + "\n")
    print(summary)


def atomic_write(path, text):
    """Temp file in the same folder, then os.replace; prints created/replaced."""
    import os
    import tempfile
    path = str(path)
    existed = os.path.exists(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    print(f"{path}: {'replaced' if existed else 'created'}")


if __name__ == "__main__":
    main()
