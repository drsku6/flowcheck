import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from extractor import norm, quote_in_source

PROMPT = """You structure a flowchart. Reply with raw JSON only, no fences, no commentary.

NODES (id, role, phase, claim, quote) in source order:
<<<NODES>>>

Return {"edges": [{"from": "<id>", "to": "<id>", "label": "", "quote": ""}], "unused": ["<id>"], "start": "<id>"}.
Rules:
- "start" is optional; omit it to start at the first node.
- Every decision node needs >= 2 outgoing edges, each with a short label (Yes / No / the condition).
- "label" is "" for unlabeled step-to-step edges.
- Every labeled edge requires a non-empty "quote", copied verbatim from the node quotes above or the source; "" only for unlabeled edges.
- If the source says to repeat or redo steps, add an edge back to the earlier node with a label that says so.
- A step which repeats or loops back must have a label on each of its outgoing edges, with a quote for each.
- An edge back to an earlier node, or a branch, is allowed only if the source text states it. The edge quote must contain the sentence that states it. Do not connect nodes with role output back into the cycle unless the source says so.
- "unused" lists ids that are background or warnings, not part of the main procedure."""


def node_kind(it):
    # role branch == old decision; old "type" field still works when role is absent.
    if it.get("role"):
        return "decision" if it["role"] == "branch" else "step"
    return "decision" if it.get("type") == "decision" else "step"


def num(iid):
    m = re.fullmatch(r"n(\d+)", iid or "")
    return int(m.group(1)) if m else None


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else ""
    g = json.loads(text.strip())
    if not isinstance(g, dict):
        raise ValueError("model output is not a JSON object")
    return g


def apply_promotions(by_id, edges):
    """Ids of steps with >= 2 outgoing edges, all labeled and quoted."""
    promoted = set()
    for nid, it in by_id.items():
        if it.get("role") == "takeaway":
            continue  # terminal takeaways are never promoted
        if node_kind(it) == "step":
            outs = [e for e in edges if isinstance(e, dict) and e.get("from") == nid]
            if len(outs) >= 2 and all(
                    isinstance(e.get("label"), str) and e.get("label").strip()
                    and isinstance(e.get("quote"), str) and e.get("quote").strip()
                    for e in outs):
                promoted.add(nid)
    return promoted


def validate(graph, by_id, source):
    """Return a list of error strings; empty means valid. Never raises."""
    errors = []
    kept = list(by_id)
    ids = set(kept)
    decisions = [nid for nid, it in by_id.items() if node_kind(it) == "decision"]
    edges = graph.get("edges")
    if not isinstance(edges, list):
        return ["edges is not a list"]
    seen = set()
    for k, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"edge {k} is not an object")
            continue
        a, b = e.get("from"), e.get("to")
        if not isinstance(a, str) or not isinstance(b, str):
            errors.append(f"edge {k}: non-string id {a!r} -> {b!r}")
            continue
        if a not in ids:
            errors.append(f"edge {k}: unknown from id {a!r}")
        if b not in ids:
            errors.append(f"edge {k}: unknown to id {b!r}")
        if a == b and a in ids:
            errors.append(f"edge {k}: self-loop on {a!r}")
        if (a, b) in seen:
            errors.append(f"duplicate edge {a!r} -> {b!r}")
        seen.add((a, b))
        lab = e.get("label")
        q = e.get("quote")
        if lab is None:
            lab = ""
        if q is None:
            q = ""
        if not isinstance(lab, str):
            errors.append(f"edge {k}: non-string label {lab!r}")
            lab = ""
        if not isinstance(q, str):
            errors.append(f"edge {k}: non-string quote")
            q = ""
        if lab.strip() and not q.strip():
            errors.append(f"edge {k} {a!r} -> {b!r}: labeled edge needs a quote")
        elif q.strip() and len(norm(q)) < 20:
            errors.append(f"edge {k} {a!r} -> {b!r}: quote too short to be evidence")
        elif q.strip() and not quote_in_source(q, source):
            errors.append(f"edge {k} {a!r} -> {b!r}: quote not found in source")
        na, nb = num(a), num(b)
        if na is not None and nb is not None and nb < na:
            if not lab.strip() or len(norm(q)) < 20:
                errors.append(f"edge {k} {a!r} -> {b!r}: loop-back needs a label and "
                              "a 20+ char quote stating it")
    unused_raw = graph.get("unused", [])
    if not isinstance(unused_raw, list):
        errors.append("unused is not a list")
        unused_raw = []
    unused = set()
    for u in unused_raw:
        if not isinstance(u, str) or u not in ids:
            errors.append(f"unknown unused id {u!r}")
        else:
            unused.add(u)
    for nid, it in by_id.items():
        if it.get("role") == "takeaway" and nid in unused:
            errors.append(f"takeaway {nid!r} must be reachable, not unused")
    start = graph.get("start") or (kept[0] if kept else None)
    if not isinstance(start, str) or start not in ids:
        errors.append(f"unknown start id {start!r}")
    adj = {}
    for e in edges:
        if (isinstance(e, dict) and isinstance(e.get("from"), str)
                and isinstance(e.get("to"), str)
                and e.get("from") in ids and e.get("to") in ids):
            adj.setdefault(e["from"], []).append(e["to"])
    if isinstance(start, str) and start in ids:  # every non-unused node reachable
        seen_r, stack = set(), [start]
        while stack:
            x = stack.pop()
            if x in seen_r:
                continue
            seen_r.add(x)
            stack.extend(adj.get(x, []))
        for nid in kept:
            if nid not in seen_r and nid not in unused:
                errors.append(f"node {nid!r} unreachable from start {start!r}")
    for d in decisions:
        if d in unused:
            continue  # unused decisions are exempt
        if by_id[d].get("role") == "takeaway":
            continue  # terminal takeaways need no outgoing edges
        outs = [e for e in edges if isinstance(e, dict) and e.get("from") == d]
        if len(outs) < 2:
            errors.append(f"decision {d!r} has {len(outs)} outgoing edges, need >= 2")
        for e in outs:
            lab = e.get("label") or ""
            if not isinstance(lab, str) or not lab.strip():
                errors.append(f"decision {d!r} edge -> {e.get('to')!r} missing label")
    promoted = apply_promotions(by_id, edges)
    for nid, it in by_id.items():
        if node_kind(it) == "step":
            outs = [e for e in edges if isinstance(e, dict) and e.get("from") == nid]
            if len(outs) >= 2 and nid not in promoted:
                errors.append(f"step {nid!r} has {len(outs)} outgoing edges: hidden branch; "
                              "make it a decision or remove an edge")
    color = {nid: 0 for nid in kept}  # 0=unvisited 1=on stack 2=done
    def dfs(u):
        color[u] = 1
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == 1:
                nu, nv = num(u), num(v)
                if nu is None or nv is None or nv >= nu:
                    errors.append(f"cycle edge {u!r} -> {v!r} does not go to an earlier id")
            elif color[v] == 0:
                dfs(v)
        color[u] = 2
    if isinstance(start, str) and start in ids:
        dfs(start)
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, dest="source_id")
    ap.add_argument("--feedback", default=None)
    args = ap.parse_args()
    sid = args.source_id
    try:
        items = json.loads(Path("workspace", f"{sid}_extract.json").read_text(encoding="utf-8"))
        source = Path("workspace", f"{sid}_source.md").read_text(encoding="utf-8")
    except FileNotFoundError as e:
        sys.exit(f"error: missing input: {e.filename}")
    kept = [it for it in items if isinstance(it, dict) and it.get("quote_found")
            and it.get("role") != "pearl"]
    pearls = [it for it in items if isinstance(it, dict) and it.get("quote_found")
              and it.get("role") == "pearl"]
    dropped = [it.get("id") for it in items if isinstance(it, dict) and not it.get("quote_found")]
    print(f"kept {len(kept)}/{len(items)}, dropped {len(dropped)}: {dropped}, pearls: {len(pearls)}")
    if not kept:
        sys.exit("error: no usable items")
    by_id = {it["id"]: it for it in kept}

    load_dotenv()
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        sys.exit("error: MODEL_API_KEY missing in .env")
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)

    nodes_txt = "\n".join(f"{it['id']} | {it.get('role') or it.get('type')} | {it.get('phase', '')} "
                           f"| {it.get('claim')} | {it.get('quote')}" for it in kept)
    prompt = PROMPT.replace("<<<NODES>>>", nodes_txt)
    if args.feedback:
        fb = Path(args.feedback).read_text(encoding="utf-8")
        prompt += ("\nA verifier found these edges unsupported by their quotes:\n" + fb +
                   "\nEvery flagged edge must stay in the graph. For each one, either replace "
                   "the quote with a passage from the source that actually supports the "
                   "transition, or change the target.")
    graph, errors = None, []
    for attempt in (1, 2):
        try:
            resp = client.responses.create(model="muse-spark-1.3", input=prompt)
        except Exception as e:
            print(f"attempt {attempt} api error: {e}")
            errors = [f"api error: {e}"]
            graph = None
        else:
            try:
                graph = parse_json(resp.output_text)
            except (ValueError, json.JSONDecodeError) as e:
                errors = [f"unparseable model output: {e}"]
                graph = None
            else:
                errors = validate(graph, by_id, source)
        if not errors:
            break
        print(f"attempt {attempt} failed validation with {len(errors)} errors; retrying")
        for e in errors:
            print(f"  - {e}")
        prompt = (prompt
                 + "\nYour previous output failed validation:\n"
                 + "\n".join(f"- {e}" for e in errors)
                 + "\nFix every error and return raw JSON only.")
    if errors:
        sys.exit("error: graph invalid after retry:\n" + "\n".join(f"- {e}" for e in errors))

    edges = []
    for e in graph["edges"]:
        q = e.get("quote") or ""
        edges.append({"from": e["from"], "to": e["to"], "label": e.get("label") or "",
                      "quote": q, "quote_found": None if not q.strip() else quote_in_source(q, source)})
    promoted = apply_promotions(by_id, graph["edges"])
    attached = {}  # pearl details folded into the preceding non-pearl node
    last = None
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("role") == "pearl" and it.get("quote_found"):
            if last is not None:
                attached.setdefault(last, []).extend(it.get("details", []))
        elif it["id"] in by_id:
            last = it["id"]
    nodes = []
    for it in kept:
        node = {"id": it["id"], "type": it.get("type"), "role": it.get("role"),
                "phase": it.get("phase"), "claim": it.get("claim"),
                "quote": it.get("quote"), "quote_found": it.get("quote_found"),
                "details": it.get("details", []) + attached.get(it["id"], [])}
        if it["id"] in promoted:
            node["type"] = "decision"
            node["promoted_from"] = "step"
            print(f"promoted {it['id']} step -> decision")
        nodes.append(node)
    ctx = next((it["id"] for it in kept if it.get("role") == "context"), kept[0]["id"])
    out = {"source_id": sid, "start": ctx,
           "nodes": nodes,
           "edges": edges, "unused": graph.get("unused", []), "dropped": dropped}
    Path("workspace", f"{sid}_graph.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"nodes: {len(out['nodes'])}, edges: {len(edges)}, start: {out['start']}")


if __name__ == "__main__":
    main()
