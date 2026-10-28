import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extractor import norm, quote_in_source

BANNED = ("%", "#", ";", '"')


def main():
    ap_msg = "usage: validate_mmd.py <chart.mmd> <source.md>"
    if len(sys.argv) != 3:
        sys.exit(ap_msg)
    chart = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    source = Path(sys.argv[2]).read_text(encoding="utf-8")
    defects = []

    nodes, edges, claims = {}, [], []
    for ln, line in enumerate(chart, 1):
        s = line.strip()
        if not s or s.startswith(("flowchart", "subgraph", "end", "class", "classDef",
                                          "linkStyle", "REFS[", "%% REFS", "%% generated")):
            continue
        m = re.match(r"%% CLAIM C\d+ \| (.*) \| (\w+)\s*$", s)
        if m:
            claims.append((m.group(1), m.group(2), ln))
            continue
        if s.startswith("%%"):
            continue
        m = re.match(r'(\w+)(?:\(\[|\[)"(.*)"(?:\]\)|\]):::(\w+)$', s)
        if m:
            nodes[m.group(1)] = {"label": m.group(2), "cls": m.group(3), "line": ln}
            continue
        m = re.match(r'(\w+)\{"(.*)"\}:::(\w+)$', s)
        if m:
            nodes[m.group(1)] = {"label": m.group(2), "cls": m.group(3), "line": ln, "diamond": True}
            continue
        m = re.match(r'(\w+)\s*-->(?:\|"([^"]*)"\|)?\s*(\w+)$', s)
        if m:
            edges.append({"from": m.group(1), "to": m.group(3), "label": m.group(2) or "", "line": ln})
            continue
        defects.append(f"line {ln}: unparseable line")

    for q, nid, ln in claims:  # verbatim evidence
        if not quote_in_source(q, source):
            defects.append(f"CLAIM line {ln}: quote not found in source")
    by_node = {}
    for q, nid, ln in claims:
        by_node.setdefault(nid, []).append((q, ln))
    for nid, n in nodes.items():  # label chars + bullet coverage
        for ch in BANNED:
            if ch in n["label"]:
                defects.append(f"node {nid}: label contains {ch!r}")
                break
        bullets = n["label"].count("• ")
        got = len(by_node.get(nid, []))
        if nid != "REFS" and bullets != got:
            defects.append(f"node {nid}: {bullets} bullets but {got} CLAIM lines")
    for q, nid, ln in claims:
        if nid != "REFS" and nid not in nodes:
            defects.append(f"CLAIM line {ln}: unknown node {nid!r}")
    outs = {}
    for e in edges:  # endpoints, labels, diamond exits, loop-back labels
        for ch in BANNED:
            if ch in e["label"]:
                defects.append(f"edge line {e['line']}: label contains {ch!r}")
                break
        if e["from"] not in nodes:
            defects.append(f"edge line {e['line']}: unknown from node {e['from']!r}")
        if e["to"] not in nodes:
            defects.append(f"edge line {e['line']}: unknown to node {e['to']!r}")
        outs.setdefault(e["from"], []).append(e)
    order = list(nodes)
    for nid, n in nodes.items():
        if n.get("diamond") and sum(1 for e in outs.get(nid, []) if e["label"].strip()) < 2:
            defects.append(f"diamond {nid}: needs >= 2 labeled exits")
    for e in edges:
        if e["from"] in order and e["to"] in order:
            if order.index(e["to"]) < order.index(e["from"]) and not e["label"].strip():
                defects.append(f"edge {e['from']} -> {e['to']} (line {e['line']}): "
                               f"loop-back needs a label")
    if order:  # reachability from the first node (REFS exempt)
        seen, stack = set(), [order[0]]
        adj = {}
        for e in edges:
            adj.setdefault(e["from"], []).append(e["to"])
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(adj.get(x, []))
        for nid in order:
            if nid not in seen and nid != "REFS":
                defects.append(f"node {nid}: unreachable")

    if defects:
        print(f"FAIL: {len(defects)} defects")
        for d in defects:
            print(f" - {d}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
