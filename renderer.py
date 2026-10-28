import argparse
import json
import sys
from pathlib import Path


def esc(t):
    # Mermaid-safe label: collapse whitespace, neutralize quotes and #<>.
    return (" ".join((t or "").split()).replace('"', "'")
            .replace("#", "#35;").replace("<", "#60;").replace(">", "#62;"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, dest="source_id")
    args = ap.parse_args()

    g = json.loads(Path("workspace", f"{args.source_id}_graph.json").read_text(encoding="utf-8"))
    unused = set(g.get("unused", []))
    nodes = [n for n in g["nodes"] if n["id"] not in unused]
    by_id = {n["id"]: n for n in nodes}

    lines = ["flowchart TD"]
    for n in nodes:
        shape = "{\"%s\"}" if n.get("type") == "decision" else "[\"%s\"]"
        lines.append(f"    {n['id']}" + shape % esc(n.get("claim")))
        lines.append(f"    %% {n['id']}: {esc(n.get('quote'))}")
    bad_links, li = [], 0  # li counts emitted links for linkStyle
    for e in g.get("edges", []):
        a, b = e.get("from"), e.get("to")
        if a in unused or b in unused:
            continue
        if a not in by_id or b not in by_id:
            sys.exit(f"error: edge to unknown node: {a!r} -> {b!r}")
        lab = esc(e.get("label"))
        if lab:
            lines.append(f"    {a} -->|\"{lab}\"| {b}")
            if (e.get("quote") or "").strip():
                lines.append(f"    %% {a} -> {b}: {esc(e.get('quote'))}")
        else:
            lines.append(f"    {a} --> {b}")
        if e.get("quote_found") is False:
            bad_links.append(str(li))
        li += 1
    lines.append("    classDef unverified fill:#fdd,stroke:#c00;")
    for n in nodes:
        if n.get("quote_found") is False:
            lines.append(f"    class {n['id']} unverified;")
    if bad_links:
        lines.append(f"    linkStyle {','.join(bad_links)} stroke:#c00,stroke-width:2px;")

    out = Path("workspace", f"{args.source_id}.mmd")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    nedges = sum(1 for e in g.get("edges", []) if e.get("from") not in unused and e.get("to") not in unused)
    print(f"nodes: {len(nodes)}, edges: {nedges}")


if __name__ == "__main__":
    main()
