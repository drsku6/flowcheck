"use strict";
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

const $ = (id) => document.getElementById(id);
const esc = (s) => s.replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let pz = null, claims = {}, flaggedSet = new Set(), pollTimer = null;
let galleryIds = [], galleryIdx = -1, panMode = false, renderN = 0;

function setOverlay(loading, logText) {
  $("overlay").hidden = !loading;
  if (logText !== undefined) $("log").textContent = logText;
}
function showError(msg) {
  const e = $("err");
  if (!msg) { e.hidden = true; e.textContent = ""; return; }
  e.hidden = false; e.textContent = msg;
}
function updateZoom() {
  const t = pz ? Math.round(pz.getZoom() * 100) + "%" : "100%";
  $("dpct").textContent = t;
  $("zpct").textContent = t;
}

async function loadGallery(selectId) {
  const r = await fetch("/api/charts");
  const list = await r.json();
  galleryIds = list.map((c) => c.id);
  const sel = $("gallery");
  sel.innerHTML = '<option value="">— gallery —</option>';
  for (const c of list) {
    const o = document.createElement("option");
    o.value = c.id;
    o.textContent = `${c.id} (${c.claims} claims${c.flagged ? `, ${c.flagged} flagged` : ""})`;
    sel.appendChild(o);
  }
  galleryIdx = selectId ? galleryIds.indexOf(selectId) : -1;
  if (selectId && galleryIdx >= 0) sel.value = selectId;
  updatePill();
}

function parseChart(mmd) {
  claims = {}; flaggedSet = new Set();
  for (const ln of mmd.split("\n")) {
    const s = ln.trim();
    let m = s.match(/^%% CLAIM C(\d+) \| (.*) \| (\w+)\s*$/);
    if (m) (claims[m[3]] = claims[m[3]] || []).push({ n: +m[1], quote: m[2] });
    m = s.match(/^(\w+)(?:\(\[|\[|\{).*:::(\w+)\s*$/);
    if (m && m[2] === "safetyNode") flaggedSet.add(m[1]);
  }
}

function nodeIdFromSvg(g) {
  const m = (g.id || "").replace(/^flowchart-/, "").match(/^(.*)-\d+$/);
  return m ? m[1] : "";
}

function openDrawer(nid) {
  const list = claims[nid] || [];
  $("drawer-title").textContent = nid;
  const b = $("drawer-badge");
  const bad = flaggedSet.has(nid);
  b.textContent = bad ? "flagged" : "verified";
  b.classList.toggle("bad", bad);
  const ul = $("claims");
  ul.innerHTML = "";
  for (const c of list) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="cn">C${c.n}</div><blockquote>${esc(c.quote)}</blockquote>`;
    ul.appendChild(li);
  }
  if (!list.length) {
    const li = document.createElement("li");
    li.textContent = "No claims attached to this node.";
    ul.appendChild(li);
  }
  $("drawer").hidden = false;
}
function closeDrawer() { $("drawer").hidden = true; }

function updateFooter(mmd) {
  const n = Object.values(claims).reduce((a, l) => a + l.length, 0);
  $("counts").textContent = `${n} claims · ${flaggedSet.size} flagged`;
  const m = mmd.match(/^REFS\["(.*)"\]:::/m);
  $("refs").textContent = "";
  if (m) {
    const d = document.createElement("div");
    d.innerHTML = m[1];
    const a = d.querySelector("a");
    if (a) {
      const link = document.createElement("a");
      link.href = a.getAttribute("href");
      link.textContent = a.textContent;
      link.rel = "noopener";
      $("refs").appendChild(link);
    } else $("refs").textContent = d.textContent;
  }
}

function updatePill() {
  const has = galleryIdx >= 0 && galleryIdx < galleryIds.length;
  $("pill").hidden = !has;
  if (!has) return;
  $("pillname").textContent = galleryIds[galleryIdx];
  $("pillcount").textContent = galleryIds.length > 1 ? `${galleryIdx + 1}/${galleryIds.length}` : "";
  $("prev").disabled = galleryIdx <= 0;
  $("next").disabled = galleryIdx >= galleryIds.length - 1;
}

function step(d) {
  const i = galleryIdx + d;
  if (i >= 0 && i < galleryIds.length) {
    $("gallery").value = galleryIds[i];
    loadChart(galleryIds[i]);
  }
}

async function loadChart(id) {
  galleryIdx = galleryIds.indexOf(id);
  updatePill();
  closeDrawer(); showError("");
  const r = await fetch("/api/chart?id=" + encodeURIComponent(id));
  if (!r.ok) { showError("chart not found: " + id); return; }
  const { mmd } = await r.json();
  parseChart(mmd);
  if (pz) { pz.destroy(); pz = null; }
  try {
    const { svg } = await mermaid.render("fc" + (++renderN), mmd);
    $("canvas").innerHTML = svg;
  } catch (e) {
    showError("render failed: " + (e && e.message ? e.message : e));
    return;
  }
  const svgEl = $("canvas").querySelector("svg");
  if (!svgEl) { showError("render produced no svg"); return; }
  svgEl.style.width = "100%";
  svgEl.style.height = "100%";
  svgEl.style.maxWidth = "none";
  pz = svgPanZoom(svgEl, {
    zoomEnabled: true, panEnabled: true, controlIconsEnabled: false,
    mouseWheelZoomEnabled: false, dblClickZoomEnabled: false,
    fit: true, center: true, minZoom: 0.05, maxZoom: 20,
    zoomScaleSensitivity: 0.15,
    onZoom: updateZoom,
    beforePan: function () {
      if (panMode) return true;
      const ev = window.event;
      return !(ev && ev.target && ev.target.tagName === "text");
    },
  });
  for (const a of svgEl.querySelectorAll("a")) {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
    const stop = (ev) => ev.stopPropagation();
    a.addEventListener("mousedown", stop);
    a.addEventListener("pointerdown", stop);
  }
  for (const t of svgEl.querySelectorAll("text")) {
    const stop = (ev) => { if (!panMode) ev.stopPropagation(); };
    t.addEventListener("mousedown", stop);
    t.addEventListener("pointerdown", stop);
  }
  $("dock").hidden = false;
  updateZoom();
  updateFooter(mmd);
}

async function poll(job) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    let s;
    try { s = await (await fetch("/api/status?job=" + job)).json(); }
    catch { return; }
    if (s.state === "running") { setOverlay(true, s.log_tail); return; }
    clearInterval(pollTimer); setOverlay(false);
    if (s.state === "done") {
      $("runmsg").textContent = "done";
      const id = $("runid").value.trim();
      await loadGallery(id);
      await loadChart(id);
    } else {
      $("runmsg").textContent = "failed";
      showError("run failed:\n" + s.log_tail);
    }
  }, 1000);
}

// Canvas-level handlers, attached once.
$("canvas").addEventListener("click", (ev) => {
  const g = ev.target.closest ? ev.target.closest("g.node") : null;
  if (g && nodeIdFromSvg(g)) openDrawer(nodeIdFromSvg(g));
  else closeDrawer();
});
$("canvas").addEventListener("wheel", (ev) => {
  if (!pz) return;
  ev.preventDefault();
  if (ev.ctrlKey) {
    const rect = $("canvas").getBoundingClientRect();
    pz.zoomAtPointBy(Math.exp(-ev.deltaY * 0.015),
      { x: ev.clientX - rect.left, y: ev.clientY - rect.top });
  } else if (ev.shiftKey) {
    pz.panBy({ x: -ev.deltaY, y: 0 });
  } else {
    pz.panBy({ x: -ev.deltaX, y: -ev.deltaY });
  }
  updateZoom();
}, { passive: false });
new ResizeObserver(() => { try { if (pz) pz.resize(); } catch { /* ignore */ } }).observe($("canvas"));

$("gallery").addEventListener("change", (e) => { if (e.target.value) loadChart(e.target.value); });
$("prev").addEventListener("click", () => step(-1));
$("next").addEventListener("click", () => step(1));
$("run").addEventListener("click", async () => {
  const id = $("runid").value.trim(), src = $("src").value.trim();
  if (!id || !src) { $("runmsg").textContent = "need id + text/url"; return; }
  if (!/^[A-Za-z0-9_-]+$/.test(id)) { $("runmsg").textContent = "bad id"; return; }
  const payload = { id, [src.startsWith("http") ? "url" : "text"]: src };
  const r = await fetch("/api/run", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
  const d = await r.json();
  if (!r.ok) { $("runmsg").textContent = d.error || "rejected"; return; }
  $("runmsg").textContent = "running…";
  showError(""); setOverlay(true, "");
  poll(d.job);
});
$("drawer-x").addEventListener("click", closeDrawer);
$("panbtn").addEventListener("click", () => {
  panMode = !panMode;
  $("panbtn").classList.toggle("on", panMode);
  $("viewer").classList.toggle("pan-on", panMode);
});
$("zin").addEventListener("click", () => { if (pz) { pz.zoomIn(); updateZoom(); } });
$("zout").addEventListener("click", () => { if (pz) { pz.zoomOut(); updateZoom(); } });
$("zone").addEventListener("click", () => { if (pz) { pz.resetZoom(); pz.center(); updateZoom(); } });
$("zfit").addEventListener("click", () => { if (pz) { pz.resize(); pz.fit(); pz.center(); updateZoom(); } });
$("zfull").addEventListener("click", () => {
  const el = $("viewer");
  if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen().catch(() => {});
  else if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {});
});
document.addEventListener("fullscreenchange", () => {
  $("zfull").classList.toggle("on", !!document.fullscreenElement);
});
document.addEventListener("keydown", (e) => {
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
  if (e.key === "Escape") closeDrawer();
  else if (e.key === "0" && pz) { pz.resize(); pz.fit(); pz.center(); updateZoom(); }
  else if (e.key === "[" ) step(-1);
  else if (e.key === "]") step(1);
});
loadGallery();
