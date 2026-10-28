"""Classify source text and split into chart units (one Muse call)."""
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI


def call_muse(prompt):
    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)
    return client.responses.create(model="muse-spark-1.3", input=prompt).output_text

TYPES = ("procedure", "mechanism", "classification", "evidence", "rules", "general")

PROMPT = """Classify this source text and split it into chart units.

Reply with raw JSON only:
{"type": "<one of procedure|mechanism|classification|evidence|rules|general>",
 "units": [{"title": "<short>", "start_quote": "<first verbatim sentence>",
            "end_quote": "<last verbatim sentence>"}],
 "reason": "<one sentence>"}

Rules: mechanism = how a natural process works; procedure = how a person does a task;
rules = what the law or a policy requires; evidence = findings weighed for a claim;
classification = sorting things into named types; general = none of these fit.
Return at most 3 units; each unit must stand alone as one chart.
start_quote and end_quote are copied verbatim from the text.

Text:
"""


def analyze(source):
    for _ in range(2):
        try:
            t0 = time.perf_counter()
            d = json.loads(call_muse(PROMPT + source))
            print(f"[analyst] call 1 {time.perf_counter() - t0:.1f}s", flush=True)
            assert d["type"] in TYPES and isinstance(d.get("units"), list) and d["units"]
            for u in d["units"]:
                assert u.get("start_quote") and u.get("end_quote")
            d["units"] = d["units"][:3]
            return d
        except (ValueError, AssertionError, KeyError) as e:
            print(f"analyst: retrying ({e})", file=sys.stderr)
    sys.exit("analyst: could not parse model reply")


def main():
    if len(sys.argv) != 4 or sys.argv[2] != "--id":
        sys.exit("usage: analyst.py <source.md> --id <sid>")
    source = open(sys.argv[1], encoding="utf-8").read()
    d = analyze(source)
    atomic_write(f"workspace/{sys.argv[3]}_analysis.json", json.dumps(d, indent=2))
    print(json.dumps(d, indent=2)[:2000])


def atomic_write(path, text):
    """Temp file in the same folder, then os.replace; prints created/replaced."""
    import os
    import tempfile
    existed = os.path.exists(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    print(f"{path}: {'replaced' if existed else 'created'}")


if __name__ == "__main__":
    main()
