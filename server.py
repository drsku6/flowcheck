"""flowcheck web UI: serves the built ui/dist/ and a small JSON API over the pipeline.

Run: .venv/bin/python server.py [port]   (default port 8000)
Build the UI first: cd ui && npm install && npm run build
"""
import datetime
import json
import re
import subprocess
import sys
import tempfile
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def slugify(name):
    """Same id rule as the orchestrator: lowercase, non-alphanumerics to '-'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
CLAIM_RE = re.compile(r"%% CLAIM C\d+ \| (.*) \| (\w+)\s*$")
DIST = ROOT / "ui" / "dist"
MIME = {".js": "text/javascript", ".css": "text/css", ".html": "text/html",
        ".svg": "image/svg+xml", ".json": "application/json",
        ".png": "image/png", ".ico": "image/x-icon",
        ".woff": "font/woff", ".woff2": "font/woff2", ".map": "application/json"}

_lock = threading.Lock()
_jobs = {}
_job_n = 0


def chart_stats(text):
    claims = sum(1 for ln in text.splitlines() if CLAIM_RE.match(ln.strip()))
    flagged = text.count(":::safetyNode")
    return claims, flagged


def parse_report(text):
    """Chart type from the report's first `type: X` line, if any."""
    for ln in text.splitlines():
        if ln.startswith("type:"):
            return ln.split(":", 1)[1].strip() or None
    return None


def list_charts():
    out = []
    for p in sorted((ROOT / "output").glob("*.mmd")):
        if p.name.endswith("_report.md"):
            continue
        claims, flagged = chart_stats(p.read_text(encoding="utf-8"))
        rep = ROOT / "output" / f"{p.stem}_report.md"
        ctype = parse_report(rep.read_text(encoding="utf-8")) if rep.exists() else None
        out.append({"id": p.stem, "claims": claims, "flagged": flagged,
                    "type": ctype})
    return out


def _claim_slot(rid):
    """Per-chart lock: same-id jobs stay serial, different ids run together."""
    global _job_n
    with _lock:
        cur = _jobs.get("active:" + rid)
        if cur and cur["state"] == "running":
            return None, f"a job for {rid} is already in progress"
        _job_n += 1
        token = f"job{_job_n}"
        job = {"id": rid, "state": "running", "log": deque(maxlen=300), "rc": None}
        _jobs["active:" + rid] = job
        _jobs[token] = job
        return token, job


def start_run(rid, text, url, draft=False):
    """Launch orchestrator as a subprocess. Returns (job_token, error)."""
    token, job = _claim_slot(rid)
    if token is None:
        return None, job
    if url is not None:
        (ROOT / "input" / f"{rid}.url").write_text(url + "\n", encoding="utf-8")
        cmd = [sys.executable, "orchestrator.py", f"input/{rid}.url"]
    else:
        cmd = [sys.executable, "orchestrator.py", "--text", text, "--id", rid]
    # UI builds always re-run: the button means build, even over an existing chart.
    cmd.append("--force")
    if draft:
        cmd.append("--draft")

    def run_bg():
        try:
            pr = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in pr.stdout:
                job["log"].append(line.rstrip()[-500:])
            pr.wait(timeout=3600)
            job["log"].append(f"[exit {pr.returncode}]")
            job["rc"] = pr.returncode
            job["state"] = "done" if pr.returncode == 0 else "error"
        except Exception as e:  # never leave a run stuck
            job["log"].append(f"runner failed: {e}")
            job["state"] = "error"

    threading.Thread(target=run_bg, daemon=True).start()
    return token, None


def revise_error(rid, instruction):
    """Validate a revise request. Returns an error string or None."""
    if not instruction.strip():
        return "need id plus instruction"
    if len(instruction) > 2000:
        return "instruction too long"
    return None


def route_chat(rid, has_chart, has_material, message):
    """Route one chat message. Returns (action, reply).

    action is build (fresh text/URL), revise (loaded chart), or ask
    (immediate reply text, no job). Pure; no I/O.
    """
    if has_material:
        if not rid:
            return ("ask", "Give the chart a short id (letters, numbers, "
                    "dashes), then send your text or link again.")
        return ("build", None)
    if has_chart:
        if not message.strip():
            return ("ask", "Say what to change, e.g. drop the REGEN node.")
        return ("revise", None)
    return ("ask", "Paste text or a link to start a new chart, "
            "or open one from the gallery.")


def start_revise(rid, instruction):
    """Launch a revision job. Returns (job_token, error)."""
    token, job = _claim_slot(rid)
    if token is None:
        return None, job
    threading.Thread(target=lambda: run_revise_bg(job, rid, instruction),
                     daemon=True).start()
    return token, None


def run_revise_bg(job, rid, instruction):
    """Revise output/<rid>.mmd per instruction: model, inject, validate, publish."""
    from orchestrator import claim_nodes as _claim_nodes
    from orchestrator import validate_nodes as _validate_nodes
    from writer import mark_residual as _mark_red
    from writer import revise_chart as _model_revise

    def done(state, msg):
        job["log"].append(msg)
        job["state"] = state

    try:
        src = ROOT / "workspace" / f"{rid}_source.md"
        chart_path = ROOT / "output" / f"{rid}.mmd"
        if not src.exists() or not chart_path.exists():
            done("error", f"no source or chart for {rid}; run the pipeline first")
            return
        rep_path = ROOT / "output" / f"{rid}_report.md"
        utype = parse_report(rep_path.read_text(encoding="utf-8")) \
            if rep_path.exists() else None
        unit = src.read_text(encoding="utf-8")
        scratch = ROOT / "workspace" / f"{rid}.revise.mmd"
        job["log"].append("asking Meta Muse to revise...")
        new_chart, refused = _model_revise(
            unit, chart_path.read_text(encoding="utf-8"), instruction, utype,
            progress=job["log"].append)
        scratch.write_text(new_chart, encoding="utf-8")
        subprocess.run([sys.executable, "tools/inject_refs.py", str(scratch),
                        "--id", rid], cwd=ROOT, check=True)
        v = subprocess.run([sys.executable, "tools/validate_mmd.py",
                            str(scratch), str(src)],
                           cwd=ROOT, capture_output=True, text=True)
        if v.returncode != 0:  # at most one repair round, then publish as-is
            job["log"].append("validate found defects; repairing once...")
            new_chart, refused2 = _model_revise(
                unit, scratch.read_text(encoding="utf-8"),
                instruction + "\nFix these validator defects, changing "
                "nothing else:\n" + v.stdout, utype,
                progress=job["log"].append)
            refused = refused + refused2
            scratch.write_text(new_chart, encoding="utf-8")
            subprocess.run([sys.executable, "tools/inject_refs.py", str(scratch),
                            "--id", rid], cwd=ROOT, check=True)
            v = subprocess.run([sys.executable, "tools/validate_mmd.py",
                                str(scratch), str(src)],
                               cwd=ROOT, capture_output=True, text=True)
        ok, out = v.returncode == 0, v.stdout
        defects = [] if ok else _validate_nodes(out) + _claim_nodes(str(scratch), out)
        lines = [f" - {i} -> validator defect -> fix per source" for i in defects]
        body = "\n".join(l for l in new_chart.splitlines()
                         if not l.startswith("%% generated"))
        prov = (f"%% revised by muse-spark-1.2 via api.meta.ai | "
                f"{datetime.date.today().isoformat()}\n")
        final = prov + (_mark_red(body, lines) if defects else body + "\n")
        with tempfile.NamedTemporaryFile("w", delete=False, dir=ROOT / "output",
                                         suffix=".mmd", encoding="utf-8") as t:
            t.write(final)
        Path(t.name).replace(chart_path)
        print(f"{chart_path}: replaced")
        old = rep_path.read_text(encoding="utf-8") if rep_path.exists() else ""
        if old and not old.endswith("\n"):
            old += "\n"
        status = "clean" if ok and not defects else \
            f"flagged: {len(defects)} remain"
        note = (f"revise: {instruction}\nrevise result: {status}; "
                f"refused: {'; '.join(refused) if refused else 'none'}\n")
        with tempfile.NamedTemporaryFile("w", delete=False, dir=ROOT / "output",
                                         suffix=".md", encoding="utf-8") as t:
            t.write(old + note)
        Path(t.name).replace(rep_path)
        print(f"{rep_path}: replaced")
        try:
            scratch.unlink()
        except OSError:
            pass
        done("done", f"revise {status}")
    except Exception as e:  # never leave a job stuck
        job["log"].append(f"revise failed: {e}")
        job["state"] = "error"


class H(BaseHTTPRequestHandler):
    server_version = "flowcheck-ui/0.1"

    def _send(self, code, body, ctype="application/json", nocache=False):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        if nocache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj))

    def _serve_dist(self, path):
        target = (DIST / path.lstrip("/")).resolve()
        if not str(target).startswith(str(DIST.resolve()) + "/") and target != DIST.resolve():
            return False
        if target.is_file():
            nocache = target.suffix == ".html"
            self._send(200, target.read_bytes(), MIME.get(target.suffix, "application/octet-stream"),
                       nocache=nocache)
            return True
        index = DIST / "index.html"
        if index.is_file():
            self._send(200, index.read_bytes(), "text/html", nocache=True)
            return True
        return False

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/charts":
            self._json(200, list_charts())
        elif u.path == "/api/chart":
            rid = parse_qs(u.query).get("id", [""])[0]
            if not ID_RE.match(rid):
                self._json(400, {"error": "bad id"})
                return
            rid = slugify(rid)
            mmd = ROOT / "output" / f"{rid}.mmd"
            if not mmd.exists():
                self._json(404, {"error": "no such chart"})
                return
            rep = ROOT / "output" / f"{rid}_report.md"
            rep_text = rep.read_text(encoding="utf-8") if rep.exists() else ""
            self._json(200, {"mmd": mmd.read_text(encoding="utf-8"),
                             "report": rep_text, "type": parse_report(rep_text)})
        elif u.path == "/api/status":
            job = _jobs.get(parse_qs(u.query).get("job", [""])[0])
            if job is None:
                self._json(404, {"error": "no such job"})
                return
            self._json(200, {"state": job["state"], "log_tail": "\n".join(job["log"])})
        elif not u.path.startswith("/api/"):
            if not self._serve_dist(u.path if u.path != "/" else "/index.html"):
                self._json(404, {"error": "ui not built: run `npm run build` in ui/"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in ("/api/run", "/api/revise", "/api/chat"):
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        if n > 600_000:
            self._json(413, {"error": "body too large"})
            return
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            self._json(400, {"error": "bad json"})
            return
        raw = d.get("id", "")
        if raw and not ID_RE.match(raw):
            self._json(400, {"error": "bad id"})
            return
        rid = slugify(raw)
        if not rid and u.path != "/api/chat":
            self._json(400, {"error": "bad id"})
            return
        if u.path == "/api/revise":
            err = revise_error(rid, d.get("instruction", ""))
            if err:
                self._json(400, {"error": err})
                return
            token, err = start_revise(rid, d.get("instruction", "").strip())
        elif u.path == "/api/chat":
            text, url = d.get("text", ""), d.get("url", "")
            message = d.get("message", "")
            has_chart = (ROOT / "output" / f"{rid}.mmd").exists() if rid else False
            action, reply = route_chat(rid, has_chart, bool(text or url),
                                       message)
            if action == "ask":
                self._json(200, {"reply": reply})
                return
            if action == "build":
                if url and not url.startswith(("http://", "https://")):
                    self._json(400, {"error": "url must be http(s)"})
                    return
                token, err = start_run(rid, text, url or None,
                                       draft=d.get("mode") == "draft")
            else:
                err = revise_error(rid, message)
                if err:
                    self._json(400, {"error": err})
                    return
                token, err = start_revise(rid, message.strip())
        else:
            text, url = d.get("text", ""), d.get("url", "")
            if not text and not url:
                self._json(400, {"error": "need id plus text or url"})
                return
            if url and not url.startswith(("http://", "https://")):
                self._json(400, {"error": "url must be http(s)"})
                return
            token, err = start_run(rid, text, url or None,
                                   draft=d.get("mode") == "draft")
        if err:
            self._json(409, {"error": err})
            return
        self._json(200, {"job": token})

    def log_message(self, *a):
        pass


def main():
    import os

    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), H)
    print(f"flowcheck ui: http://{host}:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
