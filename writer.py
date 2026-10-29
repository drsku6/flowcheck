"""Write a Mermaid chart for one unit: WRITER_CARD + profile + style + text."""
import os
import re
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

TYPES = ("procedure", "mechanism", "classification", "evidence", "rules", "general")
MODEL = "muse-spark-1.2"
DRAFT_MODEL = "muse-spark-1.2"
_calls, _lock = 0, threading.Lock()


def call_muse(prompt, progress=None, model=MODEL):
    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)
    try:
        return _call_streaming(client, prompt, progress, model)
    except Exception as e:  # streaming is progress only; never fail the call
        print(f"[writer] stream unavailable ({e}); single call", flush=True)
        return client.responses.create(model=model, input=prompt).output_text


def _call_streaming(client, prompt, progress, model):
    parts, nchars, last_note = [], [0], [0.0]
    with client.responses.create(model=model, input=prompt,
                                 stream=True) as stream:
        for ev in stream:
            d = getattr(ev, "delta", "")
            if getattr(ev, "type", "") == "response.output_text.delta" and d:
                parts.append(d)
                nchars[0] += len(d)
                now = time.perf_counter()
                if now - last_note[0] >= 10:
                    last_note[0] = now
                    msg = f"[writer] … {nchars[0] // 1000}k chars so far"
                    print(msg, flush=True)
                    if progress:
                        progress(msg)
    text = "".join(parts)
    if not text.strip():
        raise RuntimeError("empty stream")
    return text

ROOT = Path(__file__).resolve().parent


def profile_for(t):
    p = ROOT / "cards" / "profiles" / f"{t}.md"
    return p.read_text(encoding="utf-8") if p.exists() else (ROOT / "cards" / "profiles" / "general.md").read_text(encoding="utf-8")


def base_prompt(utype):
    prompt = (ROOT / "cards" / "WRITER_CARD.md").read_text(encoding="utf-8") + "\n"
    if utype is None:  # classify inside this same call: all profiles, type first
        for t in TYPES:
            prompt += (ROOT / "cards" / "profiles" / f"{t}.md").read_text(encoding="utf-8") + "\n"
        prompt += ("Begin your reply with exactly one line 'TYPE: <one of "
                   "procedure|mechanism|classification|evidence|rules|general>' "
                   "naming the profile you followed, then the chart.\n")
    else:
        prompt += profile_for(utype) + "\n"
    return prompt + (ROOT / "cards" / "STYLE_TARGET.mmd").read_text(encoding="utf-8") + "\n"


def extract_chart(out):
    m = re.search(r"```(?:mermaid)?\s*(flowchart LR.*?)```", out, re.S)
    return (m.group(1) if m else out).strip() + "\n"


def write_chart(unit_text, utype=None, extra="", progress=None, model=DRAFT_MODEL):
    """One model call per chart. Returns (type, chart). utype None = classify in-call.
    Drafts default to the fast model; repairs pass model=MODEL explicitly."""
    global _calls
    prompt = base_prompt(utype)
    if extra:
        prompt += extra + "\n"
    t0 = time.perf_counter()
    out = call_muse(prompt + "Unit text:\n" + unit_text, progress, model)
    dt = time.perf_counter() - t0
    with _lock:
        _calls += 1
        n = _calls
    print(f"[writer] call {n} {dt:.1f}s", flush=True)
    if utype is not None:
        return utype, extract_chart(out)
    m = re.match(r"\s*TYPE:\s*(\w+)", out)
    t = m.group(1).strip() if m else ""
    if t not in TYPES:  # malformed header: fall back rather than fail the run
        print(f"writer: bad TYPE header {t!r}; using general", file=sys.stderr)
        t = "general"
    body = out[m.end():] if m else out
    return t, extract_chart(body)


REVISE_TMPL = """Revise the chart below per the request. Obey the same card rules
(verbatim CLAIM per bullet and labeled edge, no outside knowledge, same label
rules). Return the full revised chart in one ```mermaid fenced block, nothing
else inside it. If the request asks for anything the unit text does not state,
leave that part out and list it after the fence as REFUSED: <reason> lines.

REVISION REQUEST:
<<<REQ>>>

CURRENT CHART:
<<<CHART>>>
"""


def split_refusals(out):
    """Chart plus REFUSED lines from a revise reply. Pure; no model call."""
    refused = [l.strip() for l in out.splitlines()
               if l.strip().startswith("REFUSED:")]
    body = "\n".join(l for l in out.splitlines()
                     if not l.strip().startswith("REFUSED:")) + "\n"
    return extract_chart(body), refused


def revise_chart(unit_text, chart, instruction, utype=None, progress=None):
    """One model call revising a chart. Returns (chart, refusals)."""
    global _calls
    prompt = (base_prompt(utype if utype in TYPES else "general")
              + "Unit text:\n" + unit_text + "\n"
              + REVISE_TMPL.replace("<<<REQ>>>", instruction)
                           .replace("<<<CHART>>>", chart))
    t0 = time.perf_counter()
    out = call_muse(prompt, progress)
    dt = time.perf_counter() - t0
    with _lock:
        _calls += 1
        n = _calls
    print(f"[writer] revise call {n} {dt:.1f}s", flush=True)
    return split_refusals(out)


def mark_residual(text, defects):
    """Red-style nodes/edges named in defect lines; ⚠ on bullets of bad nodes."""
    bad_nodes = {m.group(1) for d in defects for m in [re.match(r" - (\w+)", d)] if m}
    lines = text.splitlines()
    edge_idx, out = 0, []
    for line in lines:
        s = line.strip()
        m = re.match(r"(\w+)\s*-->(?:\|\"[^\"]*\"\|)?\s*(\w+)$", s)
        if m:
            edge_idx += 1
            if m.group(1) in bad_nodes or m.group(2) in bad_nodes:
                out.append(line)
                out.append(f"linkStyle {edge_idx - 1} stroke:#ef4444,stroke-width:2px")
                continue
        m = re.match(r"\s*(\w+)(?:\(\[|\[|\{)\".*\"(?:\]\)|\]|\}):::\w+", line)
        if m and m.group(1) in bad_nodes:
            line = re.sub(r":::\w+$", ":::safetyNode", line)
            line = line.replace("• ", "• ⚠ ")
        out.append(line)
    out.append("classDef safetyNode fill:#fef2f2,stroke:#ef4444,stroke-width:2px,color:#991b1b")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != "--type"):
        sys.exit("usage: writer.py <unit.txt> [--type <t>]")
    unit = open(sys.argv[1], encoding="utf-8").read()
    t, chart = write_chart(unit, sys.argv[3] if len(sys.argv) > 3 else None)
    sys.stdout.write(f"TYPE: {t}\n{chart}")


if __name__ == "__main__":
    main()
