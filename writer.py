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
_calls, _lock = 0, threading.Lock()


def call_muse(prompt):
    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)
    return client.responses.create(model="muse-spark-1.3", input=prompt).output_text

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


def write_chart(unit_text, utype=None, extra=""):
    """One model call per chart. Returns (type, chart). utype None = classify in-call."""
    global _calls
    prompt = base_prompt(utype)
    if extra:
        prompt += extra + "\n"
    t0 = time.perf_counter()
    out = call_muse(prompt + "Unit text:\n" + unit_text)
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
        m = re.match(r"(\s*\w+(?:\(\[|\{)\".*\"(?:\]\)|\}):::)\w+", line)
        if m and line.strip().split("(")[0].split("{")[0].strip() in bad_nodes:
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
