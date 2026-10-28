import argparse
import json
import sys
from pathlib import Path

CLASSDEFS = [
    "classDef startNode fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0c4a6e,font-weight:bold",
    "classDef safetyNode fill:#fef2f2,stroke:#ef4444,stroke-width:2px,color:#991b1b",
    "classDef decisionNode fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#0f172a",
    "classDef targetDx fill:#ecfdf5,stroke:#10b981,stroke-width:3px,color:#065f46,font-weight:bold",
    "classDef altDx fill:#f1f5f9,stroke:#94a3b8,stroke-width:1.5px,color:#334155",
    "classDef dispoNode fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e40af",
    "classDef section fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#000,font-weight:bold;",
]

ROLE_CLASS = {"context": "startNode", "step": "altDx", "branch": "decisionNode",
              "output": "dispoNode", "takeaway": "dispoNode", "pearl": "altDx"}


def clean(t):
    # Strip banned label chars (%, #, ;, double quotes); collapse whitespace.
    out = " ".join((t or "").split())
    for ch in ("%", "#", ";", '"'):
        out = out.replace(ch, "")
    return out


def one_line(t):
    return " ".join((t or "").split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, dest="source_id")
    args = ap.parse_args()
    sid = args.source_id
    try:
        items = json.loads(Path("workspace", f"{sid}_extract.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: missing input: workspace/{sid}_extract.json")

    det_bad = set()  # (node id, bullet index) with a failing detail verdict
    vpath = Path("workspace", f"{sid}_verify.json")
    if vpath.exists():
        vj = json.loads(vpath.read_text(encoding="utf-8"))
        rows = vj.get("results", vj) if isinstance(vj, dict) else vj
        for v in rows:
            if (isinstance(v, dict) and v.get("kind") == "detail"
                    and v.get("verdict") in ("unsupported", "unclear")):
                det_bad.add((v.get("id"), v.get("index")))

    try:
        srcinfo = json.loads(Path("workspace", f"{sid}_source.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        srcinfo = {}
    href = srcinfo.get("url_or_null")
    if not href:
        up = Path("input", f"{sid}.url")
        if up.exists():
            href = up.read_text(encoding="utf-8").splitlines()[0].strip()

    # Pearls fold into the previous node as bullets.
    emitted, claim_comments = [], []
    for it in items:
        if it.get("role") == "pearl" and emitted:
            target = emitted[-1]
        else:
            target = {"id": it["id"], "role": it.get("role"), "claim": it.get("claim"),
                      "bullets": [], "failed": not it.get("quote_found", False)}
            emitted.append(target)
        for d in it.get("details", []):
            target["bullets"].append(d)
            claim_comments.append((target["id"], d))
            if not d.get("quote_found", False):
                target["failed"] = True

    lines = ["flowchart LR"]
    for c in CLASSDEFS:
        lines.append("    " + c)
    bad_links, li = [], 0
    seen_phase, ph_no = {}, 0
    order = []
    for n in emitted:
        ph = next(it.get("phase", "") for it in items if it["id"] == n["id"])
        if ph not in seen_phase:
            ph_no += 1
            seen_phase[ph] = ph_no
        order.append((seen_phase[ph], ph, n))
    cur = None
    for ph_no, ph, n in order:
        if ph_no != cur:
            if cur is not None:
                lines.append("    end")
                lines.append(f"    class PH{cur} section")
            lines.append(f"    subgraph PH{ph_no} [\"{clean(ph)}\"]")
            cur = ph_no
        if any((n["id"], bi) in det_bad for bi in range(len(n["bullets"]))):
            n["failed"] = True
        label = "<b>" + clean(n.get("claim")) + "</b>"
        for bi, b in enumerate(n["bullets"]):
            mark = "⚠ " if (n["id"], bi) in det_bad else ""
            label += "<br/>• " + mark + clean(b.get("text"))
        cls = "safetyNode" if n["failed"] else ROLE_CLASS.get(n.get("role"), "altDx")
        if n.get("role") == "branch":
            lines.append(f"    {n['id']}{{\"{label}\"}}:::{cls}")
        else:
            lines.append(f"    {n['id']}([\"{label}\"]):::{cls}")
    if cur is not None:
        lines.append("    end")
        lines.append(f"    class PH{cur} section")
    ids = [n["id"] for n in emitted]
    failed_by_id = {n["id"]: n["failed"] for n in emitted}
    for k in range(len(ids) - 1):
        a, b = ids[k], ids[k + 1]
        lines.append(f"    {a} --> {b}")
        if failed_by_id.get(a):
            bad_links.append(str(li))
        li += 1
    if bad_links:
        lines.append(f"    linkStyle {','.join(bad_links)} stroke:#ef4444,stroke-width:2px;")
    for k, (nid, d) in enumerate(claim_comments, 1):
        lines.append(f"    %% CLAIM C{k} | {one_line(d.get('quote'))} | {nid}")
    lines.append("    %% REFS-BEGIN")
    if href:
        lines.append(f"    REFS[\"📚 Reference: <a href='{href}'>Wikipedia contributors, CC BY-SA 4.0</a>\"]:::section")
    lines.append("    %% REFS-END")

    out = Path("workspace") / f"{sid}.mmd"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"nodes: {len(emitted)}, edges: {max(0, len(emitted) - 1)}, phases: {len(seen_phase)}")


if __name__ == "__main__":
    main()
