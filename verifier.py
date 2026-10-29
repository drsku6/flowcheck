"""Verify a finished chart with a fresh VERIFY_CARD read. Card mode only."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def card_mode(client, sid, chart_path, source, call_n=1):
    """Fresh VERIFY_CARD read of a finished chart; defects become verify results."""
    card = Path("cards/VERIFY_CARD.md").read_text(encoding="utf-8")
    chart = Path(chart_path).read_text(encoding="utf-8")
    first = (card + "\n\nSOURCE TEXT:\n" + source + "\n\nCHART:\n" + chart)
    raw = None
    for attempt in (1, 2):
        t0 = time.perf_counter()
        resp = client.responses.create(model="muse-spark-1.2", input=first)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, dest="source_id")
    ap.add_argument("--chart", required=True, help="verify this chart file")
    ap.add_argument("--call-n", type=int, default=1, help="call number for logging")
    args = ap.parse_args()
    sid = args.source_id
    try:
        source = Path("workspace", f"{sid}_source.md").read_text(encoding="utf-8")
    except FileNotFoundError as e:
        sys.exit(f"error: missing input: {e.filename}")

    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)

    card_mode(client, sid, args.chart, source, args.call_n)


if __name__ == "__main__":
    main()
