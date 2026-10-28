"""flowcheck web UI: serves ui/ and a small JSON API over the pipeline.

Run: .venv/bin/python server.py [port]   (default port 8000)
"""
import json
import re
import subprocess
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CLAIM_RE = re.compile(r"%% CLAIM C\d+ \| (.*) \| (\w+)\s*$")
STATIC = {"app.js": "text/javascript", "style.css": "text/css",
          "vendor/mermaid.min.js": "text/javascript",
          "vendor/svg-pan-zoom.min.js": "text/javascript"}

_lock = threading.Lock()
_jobs = {}
_job_n = 0


def chart_stats(text):
    claims = sum(1 for ln in text.splitlines() if CLAIM_RE.match(ln.strip()))
    flagged = text.count(":::safetyNode")
    return claims, flagged


def list_charts():
    out = []
    for p in sorted((ROOT / "output").glob("*.mmd")):
        if p.name.endswith("_report.md"):
            continue
        claims, flagged = chart_stats(p.read_text(encoding="utf-8"))
        out.append({"id": p.stem, "claims": claims, "flagged": flagged})
    return out


def start_run(rid, text, url):
    """Launch orchestrator as a subprocess. Returns (job_token, error)."""
    global _job_n
    with _lock:
        cur = _jobs.get("current")
        if cur and cur["state"] == "running":
            return None, "a run is already in progress"
        _job_n += 1
        token = f"job{_job_n}"
        job = {"id": rid, "state": "running", "log": deque(maxlen=300), "rc": None}
        _jobs["current"] = job
        _jobs[token] = job
    if url is not None:
        (ROOT / "input" / f"{rid}.url").write_text(url + "\n", encoding="utf-8")
        cmd = [sys.executable, "orchestrator.py", f"input/{rid}.url"]
    else:
        cmd = [sys.executable, "orchestrator.py", "--text", text, "--id", rid]

    def run_bg():
        try:
            pr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600)
            job["log"].append(f"[exit {pr.returncode}]")
            if pr.stderr.strip():
                job["log"].append(pr.stderr.strip()[-2000:])
            job["rc"] = pr.returncode
            job["state"] = "done" if pr.returncode == 0 else "error"
        except Exception as e:  # never leave a run stuck
            job["log"].append(f"runner failed: {e}")
            job["state"] = "error"

    threading.Thread(target=run_bg, daemon=True).start()
    return token, None


class H(BaseHTTPRequestHandler):
    server_version = "flowcheck-ui/0.1"

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, (ROOT / "ui" / "index.html").read_bytes(), "text/html")
        elif u.path in ("/app.js", "/style.css", "/vendor/mermaid.min.js",
                        "/vendor/svg-pan-zoom.min.js"):
            rel = u.path.lstrip("/")
            self._send(200, (ROOT / "ui" / rel).read_bytes(), STATIC[rel])
        elif u.path == "/api/charts":
            self._json(200, list_charts())
        elif u.path == "/api/chart":
            rid = parse_qs(u.query).get("id", [""])[0]
            if not ID_RE.match(rid):
                self._json(400, {"error": "bad id"})
                return
            mmd = ROOT / "output" / f"{rid}.mmd"
            if not mmd.exists():
                self._json(404, {"error": "no such chart"})
                return
            rep = ROOT / "output" / f"{rid}_report.md"
            self._json(200, {"mmd": mmd.read_text(encoding="utf-8"),
                             "report": rep.read_text(encoding="utf-8") if rep.exists() else ""})
        elif u.path == "/api/status":
            job = _jobs.get(parse_qs(u.query).get("job", [""])[0])
            if job is None:
                self._json(404, {"error": "no such job"})
                return
            self._json(200, {"state": job["state"], "log_tail": "\n".join(job["log"])})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/run":
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
        rid = d.get("id", "")
        text, url = d.get("text", ""), d.get("url", "")
        if not ID_RE.match(rid) or (not text and not url):
            self._json(400, {"error": "need id plus text or url"})
            return
        if url and not url.startswith(("http://", "https://")):
            self._json(400, {"error": "url must be http(s)"})
            return
        token, err = start_run(rid, text, url or None)
        if err:
            self._json(409, {"error": err})
            return
        self._json(200, {"job": token})

    def log_message(self, *a):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"flowcheck ui: http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
