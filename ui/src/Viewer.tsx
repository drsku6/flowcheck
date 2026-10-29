import { useEffect, useMemo, useRef, useState } from "react";
import mermaid from "mermaid";
import svgPanZoom from "svg-pan-zoom";

let mermaidReady = false;
function ensureMermaid() {
  if (mermaidReady) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    securityLevel: "loose",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    themeVariables: {
      primaryColor: "#ffffff",
      primaryTextColor: "#1e293b",
      primaryBorderColor: "#334155",
      lineColor: "#1e293b",
      secondaryColor: "#f8fafc",
      tertiaryColor: "#f1f5f9",
      edgeLabelBackground: "#ffffff",
      fontSize: "12px",
    },
    flowchart: { htmlLabels: true, curve: "basis", nodeSpacing: 50, rankSpacing: 50, padding: 16 },
  });
  mermaidReady = true;
}

function nodeIdFromSvg(g: SVGGElement): string {
  const id = g.id || "";
  const v11 = id.match(/-flowchart-(.+)$/);
  if (v11) return v11[1].replace(/-\d+$/, "");
  const m = id.replace(/^flowchart-/, "").match(/^(.*)-\d+$/);
  return m ? m[1] : "";
}

const EDGE_RE = /^(\w+)\s*-->(?:\|"[^"]*"\|)?\s*(\w+)$/;
const DEF_RE = /^(\w+)(?:\(\[|\[|\{)/;
const CLAIM_RE = /^%% CLAIM C\d+ \| (.*) \| (\w+)\s*$/;

function parseChildren(mmd: string): Map<string, string[]> {
  const children = new Map<string, string[]>();
  for (const ln of mmd.split("\n")) {
    const m = ln.trim().match(EDGE_RE);
    if (m) {
      if (!children.has(m[1])) children.set(m[1], []);
      children.get(m[1])!.push(m[2]);
    }
  }
  return children;
}

function descendants(children: Map<string, string[]>, id: string): Set<string> {
  const out = new Set<string>();
  const stack = [...(children.get(id) || [])];
  while (stack.length) {
    const n = stack.pop()!;
    if (out.has(n)) continue;
    out.add(n);
    stack.push(...(children.get(n) || []));
  }
  return out;
}

/** View-only filter: drop hidden node defs, their CLAIMs, touching edges; remap linkStyle. */
function filterMmd(mmd: string, hidden: Set<string>): string {
  const lines = mmd.split("\n");
  const edgePos: number[] = [];
  lines.forEach((ln, i) => {
    if (EDGE_RE.test(ln.trim())) edgePos.push(i);
  });
  const keep = new Array<boolean>(lines.length).fill(true);
  lines.forEach((ln, i) => {
    const s = ln.trim();
    const d = s.match(DEF_RE);
    if (d && hidden.has(d[1]) && /:::\w+\s*$/.test(s)) { keep[i] = false; return; }
    const c = s.match(CLAIM_RE);
    if (c && hidden.has(c[2])) { keep[i] = false; return; }
    const e = s.match(EDGE_RE);
    if (e && (hidden.has(e[1]) || hidden.has(e[2]))) keep[i] = false;
  });
  const oldToNew = new Map<number, number>();
  let n = 0;
  edgePos.forEach((li, p) => { if (keep[li]) oldToNew.set(p, n++); });
  const out: string[] = [];
  lines.forEach((ln, i) => {
    if (!keep[i]) return;
    const m = ln.trim().match(/^linkStyle\s+(\d+)\s+(.*)$/);
    if (m) {
      const nn = oldToNew.get(+m[1]);
      if (nn === undefined) return;
      out.push(`linkStyle ${nn} ${m[2]}`);
      return;
    }
    out.push(ln);
  });
  return out.join("\n");
}

interface Props {
  mmd: string;
  bg: string;
  onNodeClick: (nid: string | null) => void;
  onError: (msg: string) => void;
}

export default function Viewer({ mmd, bg, onNodeClick, onError }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const pzRef = useRef<SvgPanZoom.Instance | null>(null);
  const [zoom, setZoom] = useState(100);
  const [panMode, setPanMode] = useState(false);
  const [rendering, setRendering] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const nRef = useRef(0);

  const children = useMemo(() => parseChildren(mmd), [mmd]);
  const shown = useMemo(() => {
    if (!collapsed.size) return mmd;
    const hidden = new Set<string>();
    collapsed.forEach((id) => descendants(children, id).forEach((d) => hidden.add(d)));
    return filterMmd(mmd, hidden);
  }, [mmd, collapsed, children]);

  const live = useRef({ children, onNodeClick });
  live.current = { children, onNodeClick };

  const updateZoom = () => {
    try {
      if (pzRef.current) setZoom(Math.round(pzRef.current.getZoom() * 100));
    } catch { /* ignore */ }
  };

  useEffect(() => { setCollapsed(new Set()); }, [mmd]);

  useEffect(() => {
    let dead = false;
    (async () => {
      setRendering(true);
      onError("");
      ensureMermaid();
      if (pzRef.current) { try { pzRef.current.destroy(); } catch { /* ignore */ } pzRef.current = null; }
      try {
        const { svg } = await mermaid.render("fc" + ++nRef.current, shown);
        if (dead || !boxRef.current) return;
        boxRef.current.innerHTML = svg;
      } catch (e) {
        if (!dead) onError("render failed: " + (e instanceof Error ? e.message : String(e)));
        setRendering(false);
        return;
      }
      const svgEl = boxRef.current?.querySelector("svg");
      if (!svgEl || dead) { setRendering(false); return; }
      svgEl.setAttribute("width", "100%");
      svgEl.setAttribute("height", "100%");
      try {
        pzRef.current = svgPanZoom(svgEl as unknown as SVGElement, {
          zoomEnabled: true, panEnabled: true, controlIconsEnabled: false,
          mouseWheelZoomEnabled: false, dblClickZoomEnabled: false,
          fit: true, center: true, minZoom: 0.05, maxZoom: 20,
          zoomScaleSensitivity: 0.15,
          onZoom: updateZoom,
        });
      } catch (e) {
        if (!dead) onError("pan/zoom failed: " + (e instanceof Error ? e.message : String(e)));
      }
      setRendering(false);
      updateZoom();
    })();
    return () => { dead = true; };
  }, [shown]);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const onClick = (ev: MouseEvent) => {
      const t = ev.target as Element;
      const g = t.closest ? t.closest("g.node") : null;
      const nid = g ? nodeIdFromSvg(g as SVGGElement) || null : null;
      if (nid && descendants(live.current.children, nid).size > 0) {
        setCollapsed((prev) => {
          const nx = new Set(prev);
          if (nx.has(nid)) nx.delete(nid);
          else nx.add(nid);
          return nx;
        });
      }
      live.current.onNodeClick(nid);
    };
    const onWheel = (ev: WheelEvent) => {
      const pz = pzRef.current;
      if (!pz) return;
      ev.preventDefault();
      if (ev.ctrlKey) {
        const rect = el.getBoundingClientRect();
        pz.zoomAtPointBy(Math.exp(-ev.deltaY * 0.015),
          { x: ev.clientX - rect.left, y: ev.clientY - rect.top });
      } else if (ev.shiftKey) pz.panBy({ x: -ev.deltaY, y: 0 });
      else pz.panBy({ x: -ev.deltaX, y: -ev.deltaY });
      updateZoom();
    };
    el.addEventListener("click", onClick);
    el.addEventListener("wheel", onWheel, { passive: false });
    const ro = new ResizeObserver(() => { try { pzRef.current?.resize(); } catch { /* ignore */ } });
    ro.observe(el);
    return () => {
      el.removeEventListener("click", onClick);
      el.removeEventListener("wheel", onWheel);
      ro.disconnect();
    };
  }, []);

  const pz = () => pzRef.current;
  const btn = "px-2 py-1 rounded border text-sm leading-none";
  const btnStyle = { borderColor: "var(--line)", color: "var(--ink)", background: "var(--panel)" };
  const expand = (id: string) => setCollapsed((prev) => {
    const nx = new Set(prev);
    nx.delete(id);
    return nx;
  });

  return (
    <div className="relative h-full w-full">
      <div ref={boxRef} className={bg + " mermaid h-full w-full overflow-hidden"} />
      {rendering && (
        <div className="absolute inset-0 grid place-items-center">
          <div className="flex items-center gap-2 rounded-full px-4 py-2 text-sm shadow"
            style={{ background: "var(--panel)", border: "1px solid var(--line)" }}>
            <span className="spin" /><span>Rendering…</span>
          </div>
        </div>
      )}
      {collapsed.size > 0 && (
        <div className="absolute left-3 top-3 flex max-w-[60%] flex-wrap items-center gap-1 rounded-full px-2 py-1 text-xs shadow"
          style={{ background: "var(--panel)", border: "1px solid var(--line)" }}
          aria-label="collapsed branches">
          <span style={{ color: "var(--muted)" }}>− hidden:</span>
          {[...collapsed].map((id) => (
            <button key={id} onClick={() => expand(id)} title={"Expand " + id}
              className="rounded-full px-1.5 font-mono"
              style={{ background: "var(--canvas)", border: "1px solid var(--line)" }}>
              {id} ×
            </button>
          ))}
        </div>
      )}
      <div className="absolute bottom-3 right-3 flex items-center gap-1 rounded-full px-1.5 py-0.5 text-xs shadow"
        style={{ background: "var(--panel)", border: "1px solid var(--line)" }}>
        <button className={btn} style={{ ...btnStyle, fontWeight: panMode ? 700 : 400 }}
          title="Pan mode (drag canvas)" onClick={() => setPanMode(!panMode)}>Pan</button>
        <button className={btn} style={btnStyle} title="Zoom in"
          onClick={() => { pz()?.zoomIn(); updateZoom(); }}>+</button>
        <button className={btn} style={btnStyle} title="Zoom out"
          onClick={() => { pz()?.zoomOut(); updateZoom(); }}>−</button>
        <button className={btn} style={btnStyle} title="Reset to 100%"
          onClick={() => { pz()?.resetZoom(); pz()?.center(); updateZoom(); }}>1:1</button>
        <button className={btn} style={btnStyle} title="Fit to screen (0)"
          onClick={() => { pz()?.resize(); pz()?.fit(); pz()?.center(); updateZoom(); }}>Fit</button>
        <button className={btn} style={btnStyle} title="Fullscreen"
          onClick={() => {
            const v = boxRef.current?.parentElement;
            if (!document.fullscreenElement) v?.requestFullscreen?.().catch(() => {});
            else document.exitFullscreen?.().catch(() => {});
          }}>⤢</button>
        <span className="px-1 text-xs tabular-nums" style={{ color: "var(--muted)" }}>{zoom}%</span>
      </div>
    </div>
  );
}
