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
    o.textContent = `${c.id} (${c.type ? c.type + " · " : ""}${c.claims} claims${c.flagged ? `, ${c.flagged} flagged` : ""})`;
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
function slug(id) { return id.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); }
function addRevise(who, text) {
  const d = document.createElement("div");
  d.className = "r-" + who;
  d.textContent = (who === "you" ? "You: " : "flowcheck: ") + text;
  $("revise-log").appendChild(d);
}
async function pollRevise(job, id) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    let s;
    try { s = await (await fetch("/api/status?job=" + job)).json(); }
    catch { return; }
    if (s.state === "running") { setOverlay(true, s.log_tail); return; }
    clearInterval(pollTimer); setOverlay(false);
    addRevise("fc", (s.log_tail || "").split("\n").filter(Boolean).pop() || s.state);
    if (s.state === "done") {
      $("revise-msg").textContent = "";
      await loadGallery(id);
      await loadChart(id);
    } else $("revise-msg").textContent = "failed";
  }, 1000);
}

function updateFooter(mmd, report) {
  const n = Object.values(claims).reduce((a, l) => a + l.length, 0);
  $("counts").textContent = `${n} claims · ${flaggedSet.size} flagged`;
  let t = null;
  for (const ln of String(report || "").split("\n")) {
    if (ln.startsWith("type:")) { t = ln.slice(5).trim() || null; break; }
  }
  $("ctype").textContent = t || "";
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
  const { mmd, report } = await r.json();
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
  $("revise").hidden = false;
  updateZoom();
  updateFooter(mmd, report);
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
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) { $("runmsg").textContent = "bad id"; return; }
  const payload = { id, [/^https?:\/\//.test(src) ? "url" : "text"]: src };
  const r = await fetch("/api/run", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
  const d = await r.json();
  if (!r.ok) { $("runmsg").textContent = d.error || "rejected"; return; }
  $("runmsg").textContent = "running…";
  showError(""); setOverlay(true, "");
  poll(d.job);
});
$("drawer-x").addEventListener("click", closeDrawer);
$("revise-x").addEventListener("click", () => { $("revise").hidden = true; });
$("revise-send").addEventListener("click", async () => {
  const raw = (galleryIdx >= 0 && galleryIds[galleryIdx]) || $("runid").value.trim();
  const id = slug(raw);
  const body = $("revise-text").value.trim();
  if (!body) { $("revise-msg").textContent = "say something first"; return; }
  const payload = { id };
  if (/^https?:\/\//.test(body)) payload.url = body;
  else if (galleryIdx < 0 || body.length > 280) payload.text = body;
  else payload.message = body;
  const r = await fetch("/api/chat", { method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload) });
  const d = await r.json();
  if (!r.ok) { $("revise-msg").textContent = d.error || "rejected"; return; }
  addRevise("you", body);
  $("revise-text").value = "";
  if (d.reply) { addRevise("fc", d.reply); return; }
  $("revise-msg").textContent = "working…";
  showError(""); setOverlay(true, "");
  pollRevise(d.job, id);
});
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
  if (e.key === "Escape") { closeDrawer(); $("revise").hidden = true; }
  else if (e.key === "0" && pz) { pz.resize(); pz.fit(); pz.center(); updateZoom(); }
  else if (e.key === "[" ) step(-1);
  else if (e.key === "]") step(1);
});
loadGallery();
