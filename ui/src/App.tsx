import { useCallback, useEffect, useRef, useState } from "react";
import Viewer from "./Viewer";
import {
  getChart, getStatus, listCharts, parseChart, reportType, slug, ID_RE,
  type ChartData, type ChartInfo,
} from "./api";

interface ChatLine { who: "you" | "fc"; text: string }
type RightTab = "new" | "chat";

function useTheme() {
  const [theme, setTheme] = useState(() =>
    typeof document !== "undefined" ? document.documentElement.dataset.theme || "light" : "light");
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    (window as unknown as { __setTheme: (v: string) => void }).__setTheme(next);
    setTheme(next);
  };
  return { theme, toggle };
}

export default function App() {
  const { theme, toggle } = useTheme();
  const [gallery, setGallery] = useState<ChartInfo[]>([]);
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [chart, setChart] = useState<ChartData | null>(null);
  const [tab, setTab] = useState<RightTab>("new");
  const [panelOpen, setPanelOpen] = useState(true);
  const [galleryOpen, setGalleryOpen] = useState(true);
  const [chatLog, setChatLog] = useState<ChatLine[]>([]);
  const [src, setSrc] = useState("");
  const [runId, setRunId] = useState("");
  const [mode, setMode] = useState<"draft" | "verified">("draft");
  const [runMsg, setRunMsg] = useState("");
  const [running, setRunning] = useState(false);
  const [runLog, setRunLog] = useState("");
  const [err, setErr] = useState("");
  const [bg, setBg] = useState(() => {
    try { return localStorage.getItem("flowcheck-bg") || "canvas-bg-grid"; } catch { return "canvas-bg-grid"; }
  });
  const pollRef = useRef<number | null>(null);

  const refreshGallery = useCallback(async () => {
    setGallery(await listCharts());
  }, []);

  const openChart = useCallback(async (id: string) => {
    setErr("");
    const d = await getChart(id);
    if (!d) { setErr("chart not found: " + id); return; }
    setActiveId(id);
    setChart(d);
    const u = new URL(window.location.href);
    u.searchParams.set("id", id);
    window.history.replaceState(null, "", u);
  }, []);

  useEffect(() => {
    refreshGallery().then(() => {
      const id = new URL(window.location.href).searchParams.get("id");
      if (id) openChart(id);
    });
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, []);

  const stopPoll = () => { if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; } };

  const pollJob = (job: string, done: (log: string, ok: boolean) => void) => {
    stopPoll();
    pollRef.current = window.setInterval(async () => {
      let s;
      try { s = await getStatus(job); } catch { return; }
      if (s.state === "running") { setRunLog(s.log_tail); return; }
      stopPoll(); setRunning(false);
      done(s.log_tail || "", s.state === "done");
    }, 1000);
  };

  const onRun = async () => {
    const id = runId.trim();
    if (!id || !src.trim()) { setRunMsg("need id + text/url"); return; }
    if (!ID_RE.test(id)) { setRunMsg("bad id"); return; }
    const payload = { id, mode, [/^https?:\/\//.test(src.trim()) ? "url" : "text"]: src.trim() } as Record<string, string>;
    let r;
    try {
      r = await fetch("/api/run", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    } catch {
      setRunMsg("request failed — is the server up?");
      return;
    }
    const d = await r.json();
    if (!r.ok) { setRunMsg(d.error || "rejected"); return; }
    setRunMsg("running…"); setErr(""); setRunning(true); setRunLog("");
    pollJob(d.job, async (log, ok) => {
      if (ok) { setRunMsg("done"); await refreshGallery(); await openChart(id); }
      else { setRunMsg("failed"); setErr("run failed:\n" + log); }
    });
  };

  const onChat = async (body: string) => {
    const id = slug(activeId || runId.trim());
    const text = body.trim();
    if (!text) return;
    const payload = { id } as Record<string, string>;
    if (/^https?:\/\//.test(text)) payload.url = text;
    else if (!activeId || text.length > 280) payload.text = text;
    else payload.message = text;
    let r;
    try {
      r = await fetch("/api/chat", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    } catch {
      setChatLog((l) => [...l, { who: "fc", text: "request failed — is the server up?" }]);
      return;
    }
    const d = await r.json();
    if (!r.ok) { setChatLog((l) => [...l, { who: "fc", text: d.error || "rejected" }]); return; }
    setChatLog((l) => [...l, { who: "you", text }]);
    if (d.reply) { setChatLog((l) => [...l, { who: "fc", text: d.reply }]); return; }
    setRunning(true); setRunLog("");
    pollJob(d.job, async (log, ok) => {
      const last = log.split("\n").filter(Boolean).pop() || (ok ? "done" : "failed");
      setChatLog((l) => [...l, { who: "fc", text: last }]);
      if (ok && id) { await refreshGallery(); await openChart(id); }
    });
  };

  const { claims, flagged } = chart ? parseChart(chart.mmd) : { claims: {}, flagged: new Set<string>() };
  const claimCount = Object.values(claims).reduce((a, l) => a + l.length, 0);
  const q = query.toLowerCase();
  const filtered = gallery.filter((c) => !q || c.id.toLowerCase().includes(q) || (c.type || "").toLowerCase().includes(q));
  const idx = activeId ? gallery.findIndex((c) => c.id === activeId) : -1;
  const step = (d: number) => {
    const i = idx + d;
    if (i >= 0 && i < gallery.length) openChart(gallery[i].id);
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = document.activeElement?.tagName;
      if (t === "INPUT" || t === "SELECT" || t === "TEXTAREA") return;
      if (e.key === "[") step(-1);
      else if (e.key === "]") step(1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const setBgPersist = (b: string) => {
    setBg(b);
    try { localStorage.setItem("flowcheck-bg", b); } catch { /* ignore */ }
  };

  const panel: React.CSSProperties = { background: "var(--panel)", borderColor: "var(--line)" };
  const field: React.CSSProperties = {
    background: "var(--canvas)", color: "var(--ink)",
    border: "1px solid var(--line)", borderRadius: 8, padding: "6px 10px", fontSize: 14, width: "100%",
  };
  const tabs: { id: RightTab; label: string }[] = [
    { id: "new", label: "New MMD" },
    { id: "chat", label: "Chat" },
  ];

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b px-4 py-2" style={panel}>
        <span className="flex items-center gap-2 text-base font-bold">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "var(--accent)" }} />
          flowcheck
        </span>
        <input value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search charts…" aria-label="search charts"
          style={{ ...field, maxWidth: 260 }} />
        <span className="flex-1" />
        {["canvas-bg-grid", "canvas-bg-dots", "canvas-bg-solid"].map((b) => (
          <button key={b} onClick={() => setBgPersist(b)} title={"Canvas: " + b.replace("canvas-bg-", "")}
            aria-label={"canvas " + b} className="h-5 w-5 rounded-full border"
            style={{
              borderColor: bg === b ? "var(--accent)" : "var(--line)",
              background: b === "canvas-bg-solid" ? "var(--canvas)"
                : b === "canvas-bg-dots" ? "radial-gradient(circle, var(--muted) 1.5px, transparent 1.5px)"
                : "radial-gradient(circle, var(--line) 1px, transparent 1px)",
              backgroundSize: "6px 6px", backgroundPosition: "center",
              boxShadow: bg === b ? "0 0 0 2px var(--accent)" : "none",
            }} />
        ))}
        <button onClick={toggle} className="rounded-lg px-2 py-1 text-base"
          style={{ ...field, width: "auto", flexShrink: 0 }}
          title="Toggle light/dark" aria-label="toggle theme">{theme === "dark" ? "☾" : "☀"}</button>
      </header>

      <div className="flex min-h-0 flex-1">
        {galleryOpen ? (
        <aside className="w-64 shrink-0 overflow-y-auto border-r" style={panel} aria-label="gallery">
          <div className="flex items-center border-b px-3 py-2 text-xs font-semibold uppercase tracking-wide" style={{ ...panel, color: "var(--muted)" }}>
            <span>Charts · {filtered.length}</span><span className="flex-1" />
            <button onClick={() => setGalleryOpen(false)} title="Collapse gallery"
              aria-label="collapse gallery panel" style={{ color: "var(--muted)" }}>‹</button>
          </div>
          {filtered.map((c) => (
            <button key={c.id} onClick={() => openChart(c.id)}
              className="block w-full border-b px-3 py-2 text-left"
              style={{
                borderColor: "var(--line)",
                background: c.id === activeId ? "var(--canvas)" : "transparent",
                borderLeft: c.id === activeId ? "3px solid var(--accent)" : "3px solid transparent",
                boxShadow: c.id === activeId ? "inset 0 0 0 1px var(--accent)" : "none",
              }}>
              <div className="truncate font-mono text-sm font-semibold">{c.id}</div>
              <div className="mt-0.5 flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
                {c.type && <span>{c.type}</span>}
                <span>{c.claims} claims</span>
                {c.flagged > 0
                  ? <span className="rounded-full px-1.5 font-semibold"
                      style={{ background: "var(--danger-wash)", color: "var(--danger)" }}>⚠ {c.flagged}</span>
                  : <span className="rounded-full px-1.5 font-semibold"
                      style={{ background: "var(--ok-wash)", color: "var(--ok)" }}>clean</span>}
              </div>
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-3 py-4 text-sm" style={{ color: "var(--muted)" }}>No charts yet. Use Run to build one.</p>
          )}
        </aside>
        ) : (
        <div className="flex w-9 shrink-0 flex-col items-center border-r pt-2" style={panel} aria-label="gallery rail">
          <button onClick={() => setGalleryOpen(true)} title="Open gallery"
            aria-label="open gallery panel" className="rounded-md px-1.5 py-1 text-sm"
            style={{ background: "var(--canvas)", border: "1px solid var(--line)" }}>›</button>
        </div>
        )}

        <main className="relative min-w-0 flex-1">
          {chart ? (
            <Viewer mmd={chart.mmd} bg={bg} onError={setErr} onNodeClick={() => {}} />
          ) : (
            <div className="grid h-full place-items-center p-8 text-center" style={{ color: "var(--muted)" }}>
              <div>
                <p className="text-lg font-semibold" style={{ color: "var(--ink)" }}>Every lesson, one trustworthy chart</p>
                <p className="mt-1 text-sm">Pick a chart on the left, or build one under Run.</p>
              </div>
            </div>
          )}
          {running && (
            <div className="absolute inset-0 grid place-items-center" style={{ background: "rgba(0,0,0,0.25)" }}>
              <div className="max-h-64 w-96 overflow-auto rounded-xl p-4 text-sm shadow-xl" style={panel}>
                <div className="mb-2 flex items-center gap-2"><span className="spin" /><span>Running…</span></div>
                <pre className="whitespace-pre-wrap text-xs" style={{ color: "var(--muted)" }}>{runLog}</pre>
              </div>
            </div>
          )}
          {err && (
            <div className="absolute bottom-3 left-3 max-w-md whitespace-pre-wrap rounded-xl p-3 text-sm"
              style={{ background: "var(--danger-wash)", color: "var(--danger)", border: "1px solid var(--danger)" }}>{err}</div>
          )}
        </main>

        {panelOpen ? (
        <aside className="flex w-80 shrink-0 flex-col border-l" style={panel} aria-label="workspace">
          <div className="flex border-b" style={{ borderColor: "var(--line)" }}>
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className="flex-1 px-2 py-2 text-sm"
                style={{
                  fontWeight: tab === t.id ? 700 : 400,
                  color: tab === t.id ? "var(--ink)" : "var(--muted)",
                  borderBottom: tab === t.id ? "2px solid var(--accent)" : "2px solid transparent",
                }}>
                {t.label}
              </button>
            ))}
            <button onClick={() => setPanelOpen(false)} title="Collapse panel"
              aria-label="collapse workspace panel" className="px-2 text-sm"
              style={{ color: "var(--muted)" }}>›</button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {tab === "new" && (
              <RunTab src={src} setSrc={setSrc} runId={runId} setRunId={setRunId}
                mode={mode} setMode={setMode}
                runMsg={runMsg} running={running} onRun={onRun} field={field} />
            )}
            {tab === "chat" && <ChatTab log={chatLog} onSend={onChat} field={field} />}
          </div>
          <footer className="border-t px-3 py-2 text-xs" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>
            {chart ? (
              <span>{reportType(chart.report) || "chart"} · {claimCount} claims · {flagged.size} flagged · </span>
            ) : <span>No chart open · </span>}
            <RefsInline mmd={chart?.mmd} />
          </footer>
        </aside>
        ) : (
        <div className="flex w-9 shrink-0 flex-col items-center border-l pt-2" style={panel} aria-label="workspace rail">
          <button onClick={() => setPanelOpen(true)} title="Open workspace"
            aria-label="open workspace panel" className="rounded-md px-1.5 py-1 text-sm"
            style={{ background: "var(--canvas)", border: "1px solid var(--line)" }}>‹</button>
        </div>
        )}
      </div>
    </div>
  );
}

function RunTab({ src, setSrc, runId, setRunId, mode, setMode, runMsg, running, onRun, field }: {
  src: string; setSrc: (v: string) => void; runId: string; setRunId: (v: string) => void;
  mode: "draft" | "verified"; setMode: (m: "draft" | "verified") => void;
  runMsg: string; running: boolean; onRun: () => void; field: React.CSSProperties;
}) {
  return (
    <div>
      <div className="mb-3 flex rounded-lg p-0.5 text-sm" style={{ background: "var(--canvas)" }} role="group" aria-label="run mode">
        {(["draft", "verified"] as const).map((m) => (
          <button key={m} onClick={() => setMode(m)} className="flex-1 rounded-md px-2 py-1 capitalize"
            style={mode === m
              ? { background: "var(--panel)", fontWeight: 700, boxShadow: "0 1px 2px rgba(0,0,0,0.15)" }
              : { color: "var(--muted)" }}
            title={m === "draft" ? "One model call; defects stay flagged" : "Adds a repair round; slower, not the --verify audit"}>
            {m}
          </button>
        ))}
      </div>
      <label className="mb-1 block text-xs font-semibold" style={{ color: "var(--muted)" }}>Source text or link</label>
      <textarea value={src} onChange={(e) => setSrc(e.target.value)} rows={6}
        placeholder="Paste lesson text or an https://… link" aria-label="source text or url" style={field} />
      <label className="mb-1 mt-3 block text-xs font-semibold" style={{ color: "var(--muted)" }}>Chart id</label>
      <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="e.g. calvin-cycle"
        aria-label="chart id" style={field} />
      <button onClick={onRun} disabled={running}
        className="mt-3 w-full rounded-lg px-3 py-2 text-sm font-semibold text-white"
        style={{ background: "var(--accent)", opacity: running ? 0.6 : 1 }}>
        {running ? "Running…" : mode === "draft" ? "Build draft" : "Build verified"}
      </button>
      {runMsg && <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{runMsg}</p>}
      <p className="mt-4 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>
        Drafts usually land in under a minute on short texts. Red nodes failed the
        mechanical checks — check them against the source.
      </p>
    </div>
  );
}

function ChatTab({ log, onSend, field }: {
  log: ChatLine[]; onSend: (body: string) => Promise<void>; field: React.CSSProperties;
}) {
  const [text, setText] = useState("");
  const send = () => { const t = text; setText(""); void onSend(t); };
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto text-sm">
        {log.length === 0 && (
          <p style={{ color: "var(--muted)" }}>Ask for changes (“drop node X”), or paste new text to build.</p>
        )}
        {log.map((l, i) => (
          <div key={i} className="rounded-lg p-1.5"
            style={{ background: l.who === "you" ? "var(--canvas)" : "var(--ok-wash)" }}>
            <span className="font-semibold">{l.who === "you" ? "You: " : "flowcheck: "}</span>{l.text}
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-1.5">
        <input value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          placeholder="Ask for changes…" aria-label="chat message" style={{ ...field, flex: 1 }} />
        <button onClick={send} className="rounded-lg px-3 text-sm font-semibold text-white"
          style={{ background: "var(--accent)" }}>Send</button>
      </div>
    </div>
  );
}

function RefsInline({ mmd }: { mmd?: string }) {
  if (!mmd) return null;
  const m = mmd.match(/^REFS\["(.*)"\]:::/m);
  if (!m) return null;
  const tmp = document.createElement("div");
  tmp.innerHTML = m[1];
  const a = tmp.querySelector("a");
  if (a) return <a href={a.getAttribute("href") || "#"} rel="noopener" className="underline">{a.textContent}</a>;
  return <span>{tmp.textContent}</span>;
}
