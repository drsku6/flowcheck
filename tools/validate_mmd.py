import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import norm, quote_in_source

BANNED = ("%", "/", "#", ";", '"')
ANAPHOR_RE = re.compile(
    r"^(these|this|it|they|them|such|similarly|those|both|neither|its|their)\b", re.I)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]+")
BANNED_EDGE = {"next", "then", "continue", "also", "other", "more", "na", "n/a", "tbd"}
COMPARATIVE_EDGE = re.compile(
    r"\b(superior|inferior|more effective|less effective|first-line|first line)\b", re.I)
HEDGE_FAIL = {"always", "never", "only", "must"}
HEDGE_WARN = {"urgent", "severe", "excessive", "mandatory", "contraindicated",
              "emergent", "immediate", "immediately"}
IGNORE_WORDS = {"reference", "references", "takeaway", "management", "figure", "table"}


def strip_tags(s):
    return re.sub(r"<[^>]+>", " ", s or "")


def stem(w):
    w = w.lower()
    for suf in ("ing", "es", "ed", "s"):
        if len(w) > len(suf) + 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


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
        if re.match(r"^\w+$", s):
            continue  # subgraph member list (bare node id, legal Mermaid)
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
        text = strip_tags(n["label"])  # tags like </b> and <br/> carry "/" legally
        for ch in BANNED:
            if ch in text:
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

    src_n = norm(source)
    for q, nid, ln in claims:  # claim form: complete sentence, no dangling anaphor
        s = norm(q)
        if not s:
            continue
        if not (s[0].isupper() or s[0].isdigit()):
            defects.append(f"CLAIM line {ln}: claim starts mid-sentence")
        elif ANAPHOR_RE.match(s):
            defects.append(f"CLAIM line {ln}: claim opens with anaphor: {s[:40]}")
        if s[-1] not in ".!?":
            defects.append(f"CLAIM line {ln}: claim does not end at sentence end")
        i = src_n.find(s)
        if i > 0 and not re.search(r"(?:[.!?:)]|\d)\s+$", src_n[:i]):
            defects.append(f"CLAIM line {ln}: claim does not start at a sentence boundary")

    def label_nums(label):  # numbers in labels must come from the source
        label = re.sub(r"^\d+\.\s*", "", label)
        return {n.rstrip(".,").replace(",", "") for n in NUM_RE.findall(label)}

    src_nums = {n.rstrip(".,").replace(",", "") for n in NUM_RE.findall(source)}
    have_nums = set()
    for nid, n in nodes.items():
        have_nums |= label_nums(strip_tags(n["label"]))
    for e in edges:
        have_nums |= label_nums(e["label"])
    miss = sorted(have_nums - src_nums, key=lambda x: (len(x), x))
    if miss:
        defects.append(f"numbers not in source (unsupported): {miss[:10]}")

    seen_bullets = []  # no fact twice: duplicate bullets or edge-echo bullets
    in_edge = {}
    for e in edges:
        if e["label"].strip():
            in_edge.setdefault(e["to"], []).append(
                re.sub(r"[^a-z0-9]+", " ", e["label"].lower()).strip())
    for nid, n in nodes.items():
        for part in re.split(r"<br\s*/?>", n["label"], flags=re.I):
            if "• " not in part:
                continue
            b = re.sub(r"[^a-z0-9]+", " ",
                       strip_tags(part.split("• ", 1)[1]).lower()).strip()
            if not b:
                continue
            for prev_nid, prev in seen_bullets:
                if prev_nid != nid and (
                        b == prev or (len(b) >= 35 and len(prev) >= 35
                                      and (b.startswith(prev) or prev.startswith(b)))):
                    defects.append(f"duplicate bullet across nodes {prev_nid} and {nid}")
                    break
            seen_bullets.append((nid, b))
            for en in in_edge.get(nid, []):
                if len(en) >= 15 and b == en:
                    defects.append(f"node {nid} bullet repeats incoming edge label")

    for e in edges:  # edge labels name the routing condition, never filler
        lab = e["label"].strip()
        if not lab:
            continue
        if lab.lower() in BANNED_EDGE:
            defects.append(f"edge line {e['line']}: generic edge label: {lab!r}")
        elif COMPARATIVE_EDGE.search(lab):
            defects.append(f"edge line {e['line']}: edge judges instead of routing: {lab!r}")

    warns = []
    low_labels = " ".join([strip_tags(n["label"]) for n in nodes.values()]
                          + [strip_tags(e["label"]) for e in edges]).lower()
    low_src = source.lower()
    for h in sorted(HEDGE_FAIL):  # added certainty is a defect, not a warning
        if re.search(rf"\b{h}\b", low_labels) and not re.search(rf"\b{h}\b", low_src):
            defects.append(f"chart adds certainty word not in source: {h}")
    inten = sorted(h for h in HEDGE_WARN
                   if re.search(rf"\b{h}\b", low_labels) and not re.search(rf"\bh{h}\b", low_src))
    if inten:
        warns.append(f"intensity words not in source: {inten}")
    src_words = {stem(w) for w in WORD_RE.findall(source) if len(w) >= 7}
    lab_words = {stem(w) for w in WORD_RE.findall(low_labels) if len(w) >= 7}
    unknown = sorted(lab_words - src_words - IGNORE_WORDS)
    if unknown:
        warns.append(f"long words not in source: {unknown[:10]}")

    for w in warns:
        print(f"~ WARN {w}")
    if defects:
        print(f"FAIL: {len(defects)} defects")
        for d in defects:
            print(f" - {d}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
