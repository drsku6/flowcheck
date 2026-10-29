"""Insert (or refresh) the REFS block in a chart, from input/<stem>.url."""
import json
import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 4 or sys.argv[2] != "--id":
        sys.exit("usage: inject_refs.py <chart.mmd> --id <stem>")
    stem = sys.argv[3]
    chart_p = Path(sys.argv[1])
    root = Path(__file__).resolve().parent.parent
    text = chart_p.read_text(encoding="utf-8")

    url_file = root / "input" / f"{stem}.url"
    raw_url, lic = None, None
    if url_file.exists():
        url_lines = url_file.read_text(encoding="utf-8").splitlines()
        raw_url = url_lines[0].strip() if url_lines else None
        lic = url_lines[1].strip() if len(url_lines) > 1 and url_lines[1].strip() else None
    sj = root / "workspace" / f"{stem}_source.json"
    pinned = raw_url
    if sj.exists():
        pinned = json.loads(sj.read_text(encoding="utf-8")).get("url_or_null") or raw_url
    if not pinned:
        pinned = None
    if lic is None:
        lic = "Wikipedia contributors, CC BY-SA 4.0" if pinned and "wikipedia.org" in pinned else "See source"
    if pinned:
        ref_line = f'REFS["📚 Reference: <a href=\'{pinned}\'>{lic}</a>"]:::section'
    else:
        ref_line = 'REFS["📚 Reference: pasted text — See source"]:::section'
    block = ("%% REFS-BEGIN\n" + ref_line + "\n%% REFS-END")
    if "%% REFS-BEGIN" in text:
        text = re.sub(r"%% REFS-BEGIN.*?%% REFS-END", block, text, flags=re.S)
    elif re.search(r"^REFS\[", text, flags=re.M):
        fresh = block.splitlines()[1]  # the REFS[...] line
        text = re.sub(r"^REFS\[.*$", "%% REFS-BEGIN\n" + fresh + "\n%% REFS-END",
                      text, flags=re.M, count=1)
    else:
        text = text.rstrip("\n") + "\n" + block + "\n"
    atomic_write(chart_p, text)
    print(f"refs: {pinned or 'pasted text'}")


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


if __name__ == "__main__":
    main()
