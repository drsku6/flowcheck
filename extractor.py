import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROMPT = """You extract a procedure from SOURCE TEXT for a flowchart.

Return ONLY a JSON list. Each item must have:
{"id": "n1", "type": "step" | "decision", "claim": "short paraphrase (max 15 words)", "quote": "exact passage copied from the source"}

Rules:
- Number ids n1, n2, ... in source order.
- type is "step" for actions, "decision" for branch/choice points.
- quote must be copied VERBATIM from SOURCE TEXT. Do not paraphrase, shorten, or reorder words inside quote. Short quotes (1-2 sentences max) preferred.
- claim is your short paraphrase; quote is the evidence.
- Output raw JSON only, no markdown fences, no commentary.

SOURCE TEXT:
<<<SOURCE>>>"""


def norm(t):
    # Strip ingest's page markers, then whitespace-only normalization.
    return " ".join(re.sub(r"\[page \d+\]", "", t).split())


def quote_in_source(quote, source):
    return bool(quote.strip()) and norm(quote) in norm(source)


def parse_list(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else ""
    items = json.loads(text.strip())
    if not isinstance(items, list):
        raise ValueError("model output is not a JSON list")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_file")
    ap.add_argument("--id", required=True, dest="source_id")
    args = ap.parse_args()

    source = Path(args.source_file).read_text(encoding="utf-8")

    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)

    prompt = PROMPT.replace("<<<SOURCE>>>", source)
    items = None
    err = None
    for _ in range(2):  # initial try + one retry on parse failure
        resp = client.responses.create(model="muse-spark-1.3", input=prompt)
        try:
            items = parse_list(resp.output_text)
            break
        except (ValueError, json.JSONDecodeError) as e:
            err = e
    if items is None:
        sys.exit(f"error: could not parse model output for {args.source_file}: {err}")

    rows, skipped = [], 0
    for it in items:
        if not isinstance(it, dict):
            skipped += 1  # recorded, not scored
            continue
        it["quote_found"] = quote_in_source(it.get("quote", ""), source)
        rows.append(it)

    print(f"{'id':<6}{'type':<10}{'found':<8}claim")
    for it in rows:
        print(f"{it.get('id', ''):<6}{it.get('type', ''):<10}{str(it['quote_found']):<8}{it.get('claim', '')}")
    found = sum(1 for it in rows if it["quote_found"])
    print(f"found {found}/{len(rows)}, missing {len(rows) - found}/{len(rows)}")
    if skipped:
        print(f"skipped {skipped} non-dict items")

    out = Path("workspace") / f"{args.source_id}_extract.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
