export interface ChartInfo {
  id: string;
  claims: number;
  flagged: number;
  type: string | null;
}

export interface ChartData {
  mmd: string;
  report: string;
  type: string | null;
}

export interface Claim {
  n: number;
  quote: string;
}

export async function listCharts(): Promise<ChartInfo[]> {
  const r = await fetch("/api/charts");
  return r.json();
}

export async function getChart(id: string): Promise<ChartData | null> {
  const r = await fetch("/api/chart?id=" + encodeURIComponent(id));
  if (!r.ok) return null;
  return r.json();
}

export async function getStatus(job: string): Promise<{ state: string; log_tail: string }> {
  const r = await fetch("/api/status?job=" + encodeURIComponent(job));
  return r.json();
}

export function parseChart(mmd: string): { claims: Record<string, Claim[]>; flagged: Set<string> } {
  const claims: Record<string, Claim[]> = {};
  const flagged = new Set<string>();
  for (const ln of mmd.split("\n")) {
    const s = ln.trim();
    let m = s.match(/^%% CLAIM C(\d+) \| (.*) \| (\w+)\s*$/);
    if (m) (claims[m[3]] = claims[m[3]] || []).push({ n: +m[1], quote: m[2] });
    m = s.match(/^(\w+)(?:\(\[|\[|\{).*:::(\w+)\s*$/);
    if (m && m[2] === "safetyNode") flagged.add(m[1]);
  }
  return { claims, flagged };
}

export function reportType(report: string | null): string | null {
  for (const ln of String(report || "").split("\n")) {
    if (ln.startsWith("type:")) return ln.slice(5).trim() || null;
  }
  return null;
}

export function slug(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export const ID_RE = /^[A-Za-z0-9_-]{1,64}$/;
