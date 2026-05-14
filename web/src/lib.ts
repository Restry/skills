/** Deterministic hue from a string, used for accent colors per skill. */
export function hueFor(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

export function accentFor(s: string) {
  const hue = hueFor(s);
  return {
    fg: `hsl(${hue} 70% 75%)`,
    bg: `hsl(${hue} 50% 20% / 0.55)`,
    ring: `hsl(${hue} 70% 60% / 0.45)`,
    dot: `hsl(${hue} 70% 60%)`,
  };
}

/** Relative time. */
export function ago(iso: string): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  if (s < 86400 * 30) return `${Math.round(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

/** "Freshness" bucket from last_seen_at. */
export function freshness(iso: string): "live" | "recent" | "stale" | "gone" {
  if (!iso) return "gone";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 5 * 60) return "live";
  if (s < 60 * 60) return "recent";
  if (s < 24 * 3600) return "stale";
  return "gone";
}

export const freshnessColor: Record<ReturnType<typeof freshness>, string> = {
  live: "var(--ok)",
  recent: "var(--accent)",
  stale: "var(--warn)",
  gone: "var(--muted-2)",
};

export function short(sha: string, n = 7): string {
  return (sha || "").slice(0, n);
}
