import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROLES = {"step", "branch", "output", "pearl", "context", "takeaway"}

PROMPT = """You extract a flowchart procedure from SOURCE TEXT for a teaching chart.

Return ONLY a JSON list. Each item must have:
{"id": "n1", "phase": "<short phase name from the source headings or wording>", "role": "step | branch | output | pearl | context | takeaway", "claim": "short paraphrase (max 15 words)", "details": [{"text": "short paraphrase (max 20 words)", "quote": "exact passage copied from the source"}], "quote": "exact passage copied from the source"}

Roles:
- context: background the reader needs first. Exactly one, and it must be the first item.
- step: one action in the procedure, in source order.
- branch: a decision or choice point with alternatives.
- output: a product or result of the procedure.
- pearl: a teaching tip or pitfall, tightly tied to the previous step.
- takeaway: at most one, and only as the last item; the single bottom-line message.
Number ids n1, n2, ... in source order.

Rules:
- phase groups nearby items; reuse the same short name for items in the same phase.
- claim is your short paraphrase; details carry the evidence.
- Keep source hedges (can, may, often) in details text; do not state uncertain things as certain.
- Every quote must be copied VERBATIM from SOURCE TEXT. Do not paraphrase, shorten, or reorder words inside quote. Short quotes (1-2 sentences max) preferred.
- claim, details text and phase are your words; quotes are the evidence.
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


def check_schema(items):
    """Return error list for the teaching-chart schema; [] means valid."""
    errors = []
    if not items:
        return ["no items returned"]
    for k, it in enumerate(items):
        if not isinstance(it, dict):
            errors.append(f"item {k} is not an object")
            continue
        for key in ("id", "phase", "role", "claim", "quote"):
            if not isinstance(it.get(key), str) or not it[key].strip():
                errors.append(f"item {k}: missing or empty {key!r}")
        if it.get("role") not in ROLES:
            errors.append(f"item {k}: bad role {it.get('role')!r}")
        dets = it.get("details")
        if not isinstance(dets, list) or not dets:
            errors.append(f"item {k}: details must be a non-empty list")
            continue
        for j, d in enumerate(dets):
            if not isinstance(d, dict):
                errors.append(f"item {k} detail {j} is not an object")
                continue
            if not isinstance(d.get("text"), str) or not d["text"].strip():
                errors.append(f"item {k} detail {j}: missing text")
            elif len(d["text"].split()) > 20:
                errors.append(f"item {k} detail {j}: text over 20 words")
            if not isinstance(d.get("quote"), str) or not d["quote"].strip():
                errors.append(f"item {k} detail {j}: missing quote")
    roles = [it.get("role") for it in items if isinstance(it, dict)]
    if not roles or roles[0] != "context" or roles.count("context") != 1:
        errors.append("exactly one context item required, as the first item")
    takes = [k for k, r in enumerate(roles) if r == "takeaway"]
    if len(takes) > 1 or (takes and takes[0] != len(roles) - 1):
        errors.append("at most one takeaway item, and only as the last item")
    return errors


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
    items, errors = None, []
    for attempt in (1, 2):  # initial try + one retry on parse/schema failure
        resp = client.responses.create(model="muse-spark-1.3", input=prompt)
        try:
            items = parse_list(resp.output_text)
            errors = check_schema(items)
        except (ValueError, json.JSONDecodeError) as e:
            items, errors = None, [f"unparseable model output: {e}"]
        if not errors:
            break
        print(f"attempt {attempt} invalid: {len(errors)} problems; retrying")
        for e in errors:
            print(f"  - {e}")
        prompt = prompt + "\nYour previous output had these problems:\n" + "\n".join(
            f"- {e}" for e in errors) + "\nFix every problem and return raw JSON only."
    if errors:
        sys.exit("error: extractor output invalid after retry:\n" + "\n".join(f"- {e}" for e in errors))

    for it in items:
        it["quote_found"] = quote_in_source(it.get("quote", ""), source)
        for d in it["details"]:
            d["quote_found"] = quote_in_source(d.get("quote", ""), source)

    print(f"{'id':<6}{'role':<10}{'phase':<16}{'found':<8}claim")
    for it in items:
        print(f"{it['id']:<6}{it['role']:<10}{it['phase'][:15]:<16}{str(it['quote_found']):<8}{it['claim']}")
    found = sum(1 for it in items if it["quote_found"])
    dfound = sum(1 for it in items for d in it["details"] if d["quote_found"])
    dtotal = sum(len(it["details"]) for it in items)
    print(f"items {found}/{len(items)}, detail quotes {dfound}/{dtotal}")

    out = Path("workspace") / f"{args.source_id}_extract.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
