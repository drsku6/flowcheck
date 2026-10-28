import argparse
import concurrent.futures
import datetime
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from common import norm, quote_in_source
from writer import mark_residual, write_chart


class StageFailed(RuntimeError):
    def __init__(self, stage, code):
        self.stage = stage
        super().__init__(f"error: {stage} failed with exit {code}")


def stage(name, cmd):
    print(f"== {name}", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise StageFailed(name, r.returncode)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def atomic_write(path, text):
    """Temp file in the same folder, then os.replace; prints created/replaced."""
    path = str(path)
    existed = os.path.exists(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    print(f"{path}: {'replaced' if existed else 'created'}")


def atomic_copy(src, dst):
    atomic_write(dst, Path(src).read_text(encoding="utf-8"))


def cleanup_splits(stem, sid, keep):
    """Remove id X's stale split files. keep = {'_1',..} tags written this run."""
    if keep:  # multi-unit run: the unsuffixed single is stale
        for f in (f"output/{stem}.mmd", f"output/{stem}_report.md"):
            if os.path.exists(f):
                os.remove(f)
                print(f"{f}: removed")
    for path in list(Path("output").glob(f"{stem}_*.mmd")) + \
                list(Path("output").glob(f"{stem}_*_report.md")) + \
                list(Path("workspace").glob(f"{sid}_*")):
        m = re.match(rf"^{re.escape(stem if path.parent.name == 'output' else sid)}(_\d+)",
                     path.name)
        if m and m.group(1) not in keep:
            os.remove(path)
            print(f"{path}: removed")


USAGE = """usage: orchestrator.py input/<name> [--verify]
       orchestrator.py --all [--verify]
       orchestrator.py --text "..." --id <name> [--verify]
       orchestrator.py --url <link> --id <name> [--verify]"""


def slice_units(source, units):
    """Cut unit texts from the source between the analyst's verbatim bounds."""
    ns = norm(source)
    texts = []
    for u in units:
        i, j = ns.find(norm(u["start_quote"])), ns.find(norm(u["end_quote"]))
        if i < 0 or j < 0 or j < i:
            return None
        texts.append(ns[i:j + len(norm(u["end_quote"]))])
    return texts


ANALYST_LIMIT = 25000


def validate_once(py, scratch, md_path, times):
    t0 = time.perf_counter()
    v = subprocess.run([py, "tools/validate_mmd.py", scratch, md_path],
                       capture_output=True, text=True)
    times["validate"] = times.get("validate", 0) + time.perf_counter() - t0
    print(v.stdout.strip() or "validate: PASS")
    return v.returncode == 0, v.stdout


def validate_nodes(out):
    """Node ids named in validator defects, for residual red marking."""
    ids = []
    for line in out.splitlines():
        m = re.match(r" - (?:node (\w+)|edge (\w+) -> (\w+))", line)
        if m:
            ids.extend(g for g in m.groups() if g)
    return ids


def local_repair(scratch, md_path, threshold=0.9, min_len=20):
    """Fix near-verbatim CLAIM quotes without a model call. Returns fixed count.

    A failing quote scoring >= threshold against a source sentence is replaced
    by that verbatim sentence. Anything else is left for the writer repair
    call; re-validation stays the gate either way.
    """
    lines = Path(scratch).read_text(encoding="utf-8").splitlines()
    src = Path(md_path).read_text(encoding="utf-8")
    sents = [s.strip() for ln in src.splitlines()
             for s in re.split(r"(?<=[.!?])\s+", ln) if len(s.strip()) >= min_len]
    normed = [(s, norm(s)) for s in sents]
    fixed = 0
    for i, ln in enumerate(lines):
        m = re.match(r"(%% CLAIM C\d+ \| )(.*)( \| \w+\s*)$", ln.strip())
        if not m or quote_in_source(m.group(2), src):
            continue
        nq = norm(m.group(2))
        if len(nq) < min_len:
            continue
        best, best_r = None, 0.0
        for s, ns in normed:
            r = difflib.SequenceMatcher(None, nq, ns).ratio()
            if r > best_r:
                best, best_r = s, r
        if best is not None and best_r >= threshold:
            indent = ln[:len(ln) - len(ln.lstrip())]
            lines[i] = f"{indent}{m.group(1)}{best}{m.group(3)}"
            fixed += 1
    if fixed:
        atomic_write(scratch, "\n".join(lines) + "\n")
    return fixed


def claim_nodes(scratch, out):
    """Node ids whose CLAIM lines failed the verbatim check."""
    ids = []
    try:
        lines = Path(scratch).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ids
    for line in out.splitlines():
        m = re.match(r" - CLAIM line (\d+):", line)
        if m:
            i = int(m.group(1)) - 1
            if 0 <= i < len(lines):
                cm = re.match(r"%% CLAIM C\d+ \| (.*) \| (\w+)\s*$",
                              lines[i].strip())
                if cm and cm.group(2) not in ids:
                    ids.append(cm.group(2))
    return ids


def run_cards(source, sid, stem, input_stem, verify, times, skip_ingest=False):
    """Fast default: ingest, writer, inject, validate, one repair. --verify adds checks."""
    py = sys.executable
    if not skip_ingest:
        t0 = time.perf_counter()
        stage("ingest", [py, "ingest.py", source, "--id", sid])
        times["ingest"] = time.perf_counter() - t0
    md_path = f"workspace/{sid}_source.md"
    src_text = Path(md_path).read_text(encoding="utf-8")

    if len(src_text) < ANALYST_LIMIT:  # one unit; the writer classifies in-call
        print(f"analyst: skipped (source under {ANALYST_LIMIT} chars)")
        unit_texts, utypes = [norm(src_text)], [None]
    else:
        t0 = time.perf_counter()
        stage("analyst", [py, "analyst.py", md_path, "--id", sid])
        times["analyst"] = time.perf_counter() - t0
        ana = json.loads(Path(f"workspace/{sid}_analysis.json").read_text(encoding="utf-8"))
        print(f"type: {ana['type']} ({ana.get('reason', '')})")
        unit_texts = slice_units(src_text, ana["units"])
        if unit_texts is None:
            print("analyst bounds not found; using whole source as one unit")
            unit_texts = [norm(src_text)]
        utypes = [ana["type"]] * len(unit_texts)
    multi = len(unit_texts) > 1

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        typed = list(ex.map(lambda ut: write_chart(*ut), zip(unit_texts, utypes)))
    times["writer"] = time.perf_counter() - t0
    if utypes[0] is None:
        print(f"type: {typed[0][0]}")
    charts = [c for _, c in typed]
    utypes = [t for t, _ in typed]

    jobs = []
    for n, (unit, chart, utype) in enumerate(zip(unit_texts, charts, utypes), 1):
        tag = f"_{n}" if multi else ""
        scratch, vid = f"workspace/{sid}{tag}.mmd", f"{sid}{tag}"
        atomic_write(scratch, chart)
        stage("inject_refs", [py, "tools/inject_refs.py", scratch, "--id", input_stem])
        ok, out = validate_once(py, scratch, md_path, times)
        if not ok:  # deterministic fix first; writer repair only for the rest
            n_fixed = local_repair(scratch, md_path)
            if n_fixed:
                print(f"local repair: fixed {n_fixed} quote(s)")
                ok, out = validate_once(py, scratch, md_path, times)
        if not ok:  # at most one repair call, validator errors only
            utype, chart = write_chart(unit, utype,
                                       "Fix every defect and return the full chart:\n" + out)
            atomic_write(scratch, chart)
            stage("inject_refs", [py, "tools/inject_refs.py", scratch, "--id", input_stem])
            ok, out = validate_once(py, scratch, md_path, times)
        if multi:
            shutil.copy(md_path, f"workspace/{vid}_source.md")
        defects = [] if ok else validate_nodes(out) + claim_nodes(scratch, out)
        jobs.append({"n": n, "tag": tag, "unit": unit, "utype": utype,
                     "scratch": scratch, "vid": vid, "ok": ok, "out": out,
                     "defects": defects})

    tlock = threading.Lock() if verify else None
    if verify:  # phase A: one verifier call per unit, concurrently
        print("== verifier (concurrent)", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            for job, defects in zip(jobs, ex.map(
                    lambda j: run_verify(py, j["scratch"], j["vid"], j["n"], tlock, times),
                    jobs)):
                job["vids"] = [d[3:].split(" -> ")[0].strip() or "chart" for d in defects]
                job["vlines"] = defects
        failing = [j for j in jobs if j["vlines"]]
        if failing:  # phase B: one concurrent fix round for failing units only
            print("== verifier fix round (concurrent)", flush=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(lambda j: fix_unit(py, j, md_path, input_stem, tlock, times),
                            failing))
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                for job, defects in zip(failing, ex.map(
                        lambda j: run_verify(py, j["scratch"], j["vid"], j["n"] + 100,
                                             tlock, times), failing)):
                    job["vlines"] = defects
                    job["vids"] = [d[3:].split(" -> ")[0].strip() or "chart"
                                   for d in defects]

    total_flagged, out_paths = 0, []
    for job in jobs:
        if verify:  # verifier defects plus any validate residuals it did not cover
            uncovered = [i for i in job["defects"] if i not in job.get("vids", [])]
            lines = (job.get("vlines", [])
                     + [f" - {i} -> validator defect -> fix per source" for i in uncovered])
            bad = job.get("vids", []) + uncovered
        else:
            lines = [f" - {i} -> validator defect -> fix per source" for i in job["defects"]]
            bad = [] if job["ok"] else job["defects"]
        if bad:  # residual failures stay red in both modes
            atomic_write(job["scratch"], mark_residual(
                Path(job["scratch"]).read_text(encoding="utf-8"), lines))
        total_flagged += len(bad)
        if not verify:
            atomic_write(f"workspace/{job['vid']}_report.md",
                         (job["out"] if job["out"].strip() else "validate: PASS")
                         + f"\nflagged: {len(bad)} remain\n")
        prov = (f"%% generated by muse-spark-1.3 via api.meta.ai | source: {source} | "
                f"{datetime.date.today().isoformat()}\n")
        outp = f"output/{stem}{job['tag']}.mmd"
        existed = os.path.exists(outp)
        with tempfile.NamedTemporaryFile("w", delete=False, dir="output", suffix=".mmd",
                                         encoding="utf-8") as tmp:
            tmp.write(prov + Path(job["scratch"]).read_text(encoding="utf-8"))
        os.replace(tmp.name, outp)
        print(f"{outp}: {'replaced' if existed else 'created'}")
        atomic_copy(f"workspace/{job['vid']}_report.md",
                    f"output/{stem}{job['tag']}_report.md")
        out_paths.append(outp)
    cleanup_splits(stem, sid, {j["tag"] for j in jobs if j["tag"]})
    status = "clean" if not total_flagged else f"flagged: {total_flagged} remain"
    print(f"final status: {status}")
    return {"status": status, "paths": out_paths}


def run_verify(py, scratch, vid, n, tlock, times):
    """One verifier subprocess call. Returns raw defect lines."""
    t0 = time.perf_counter()
    r = subprocess.run([py, "verifier.py", "--id", vid, "--chart", scratch,
                        "--call-n", str(n)], capture_output=True, text=True)
    dt = time.perf_counter() - t0
    with tlock:
        times["verifier"] = times.get("verifier", 0) + dt
        sys.stdout.write(r.stdout)
    if r.returncode != 0:
        raise StageFailed(f"verifier {vid}", r.returncode)
    return [l for l in Path(f"workspace/{vid}_report.md").read_text(
        encoding="utf-8").splitlines() if l.startswith(" - ")]


def fix_unit(py, job, md_path, input_stem, tlock, times):
    """One fix round for a failing unit: writer, inject, validate. Refreshes defects."""
    _, chart = write_chart(job["unit"], job["utype"],
                           "Fix only these defects, changing nothing else. "
                           "Return the full chart:\n" + "\n".join(job["vlines"]))
    atomic_write(job["scratch"], chart)
    subprocess.run([py, "tools/inject_refs.py", job["scratch"], "--id", input_stem],
                   check=True)
    with tlock:
        ok, out = validate_once(py, job["scratch"], md_path, times)
    job["ok"], job["out"] = ok, out
    job["defects"] = [] if ok else validate_nodes(out) + claim_nodes(job["scratch"], out)


def print_times(times, t0):
    for k, v in times.items():
        print(f"{k}: {v:.1f}s")
    print(f"total: {time.perf_counter() - t0:.1f}s")


def process_file(p, verify=False):
    """Run one input file end to end. Raises StageFailed on stage failure."""
    stem, sid = p.stem, slugify(p.stem)
    if not sid:
        raise StageFailed(f"cannot make an id from {p.name}", 1)
    if p.suffix == ".url":
        lines = p.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].strip():
            raise StageFailed(f"{p.name}: empty .url file", 1)
        source = lines[0].strip()
    else:
        source = str(p)
    times, t0 = {}, time.perf_counter()
    res = run_cards(source, sid, stem, p.stem, verify, times)
    print_times(times, t0)
    print(f"{p.name}: {res['status']}, {', '.join(res['paths'])}")


def process_url(url, sid, verify):
    """Run a URL end to end with no input file. ingest fetches it directly."""
    times, t0 = {}, time.perf_counter()
    res = run_cards(url, sid, sid, sid, verify, times)
    print_times(times, t0)
    print(f"--url: {res['status']}, {', '.join(res['paths'])}")


def process_text(text, sid, verify):
    """Run raw pasted text end to end. Writes source files directly, no ingest."""
    stem = sid
    atomic_write(f"workspace/{sid}_source.md", text.rstrip("\n") + "\n")
    atomic_write(f"workspace/{sid}_source.json", json.dumps(
        {"source": "--text", "url_or_null": None, "title": sid,
         "fetched_at": datetime.date.today().isoformat(),
         "chars": len(text), "pages": None}, indent=2))
    times, t0 = {}, time.perf_counter()
    res = run_cards("--text", sid, stem, sid, verify, times, skip_ingest=True)
    print_times(times, t0)
    print(f"--text: {res['status']}, {', '.join(res['paths'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_path", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--text", default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--id", default=None)
    args = ap.parse_args()

    if args.url is not None:
        if args.all or args.input_path or args.text is not None:
            sys.exit("error: --url takes no input file or --text")
        if not args.id:
            sys.exit("error: --url requires --id")
        if not args.url.startswith(("http://", "https://")):
            sys.exit("error: --url must be http(s)")
        sid = slugify(args.id)
        if not sid:
            sys.exit(f"error: cannot make an id from {args.id!r}")
        try:
            process_url(args.url, sid, args.verify)
        except StageFailed as e:
            sys.exit(str(e))
        print("processed 1, skipped 0, failed 0")
        return

    if args.text is not None:
        if args.all or args.input_path or args.url is not None:
            sys.exit("error: --text takes no input file or --url")
        if not args.id:
            sys.exit("error: --text requires --id")
        sid = slugify(args.id)
        if not sid:
            sys.exit(f"error: cannot make an id from {args.id!r}")
        try:
            process_text(args.text, sid, args.verify)
        except StageFailed as e:
            sys.exit(str(e))
        print("processed 1, skipped 0, failed 0")
        return

    if args.all:
        files = sorted(p for p in Path("input").iterdir()
                       if p.is_file() and not p.name.startswith("."))
        if not files:
            print("no files")
            return
        seen = {}
        for p in files:
            sid = slugify(p.stem)
            if not sid:
                sys.exit(f"error: cannot make an id from {p.name}")
            if sid in seen:
                sys.exit(f"error: duplicate id {sid!r} from {seen[sid]} and {p.name}")
            seen[sid] = p.name
        done, skipped, failures = 0, 0, 0
        for p in files:
            try:
                process_file(p, args.verify)
            except StageFailed as e:
                print(f"{p.name}: FAILED at {e.stage}")
                failures += 1
                continue
            done += 1
        print(f"processed {done}, skipped {skipped}, failed {failures}")
        if failures:
            sys.exit(f"error: {failures} file(s) failed")
        return

    if not args.input_path:
        print(USAGE)
        sys.exit(2)
    p = Path(args.input_path)
    if not p.is_file():
        sys.exit(f"error: file not found: {args.input_path}")
    try:
        process_file(p, args.verify)
    except StageFailed as e:
        sys.exit(str(e))
    print("processed 1, skipped 0, failed 0")


if __name__ == "__main__":
    main()
