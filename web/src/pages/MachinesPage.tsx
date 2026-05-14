import { useEffect, useState } from "react";
import { api, type Machine } from "../api";
import { ago, freshness, freshnessColor, short } from "../lib";

export default function MachinesPage() {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.machines().then((r) => setMachines(r.machines)).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-[var(--bad)]">{err}</div>;

  const buckets = {
    live: machines.filter((m) => freshness(m.last_seen_at) === "live").length,
    recent: machines.filter((m) => freshness(m.last_seen_at) === "recent").length,
    stale: machines.filter((m) => ["stale", "gone"].includes(freshness(m.last_seen_at))).length,
  };
  const totalStale = machines.reduce((a, m) => a + m.stale_count, 0);

  return (
    <div>
      <div className="flex items-baseline justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Machines</h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            {machines.length} registered ·{" "}
            {totalStale > 0 ? (
              <span className="text-[var(--warn)]">{totalStale} skill(s) out of date</span>
            ) : (
              <span className="text-[var(--ok)]">all installs current</span>
            )}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5">
        <KPI label="Live (≤5m)" value={buckets.live} tone="ok" />
        <KPI label="Recent (≤1h)" value={buckets.recent} tone="accent" />
        <KPI label="Stale / gone" value={buckets.stale} tone={buckets.stale ? "warn" : "muted"} />
      </div>

      {machines.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] py-10 px-6 text-center">
          <div className="text-sm">No machines registered.</div>
          <code className="text-xs text-[var(--muted)] mt-1 block">
            python3 ~/.claude/skills/sync-skill/scripts/init.py --server &lt;url&gt; --repo &lt;git-url&gt;
          </code>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {machines.map((m) => <MachineCard key={m.id} m={m} />)}
        </div>
      )}
    </div>
  );
}

function MachineCard({ m }: { m: Machine }) {
  const f = freshness(m.last_seen_at);
  const dot = freshnessColor[f];
  return (
    <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="relative grid place-items-center w-8 h-8 rounded-md bg-[var(--surface-2)] shrink-0">
            <svg viewBox="0 0 24 24" className="w-4 h-4 text-[var(--muted)]" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="12" rx="2" />
              <path d="M8 20h8M12 16v4" />
            </svg>
            <span
              className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-[var(--surface)]"
              style={{ background: dot }}
              title={f}
            />
          </span>
          <div className="min-w-0">
            <div className="font-medium truncate">{m.hostname || "(unknown)"}</div>
            <div className="text-[10px] text-[var(--muted-2)]">
              {m.runtime || "—"} · <code className="font-mono">{short(m.id, 8)}</code>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-[var(--muted-2)]">Last seen</div>
          <div className="text-xs">{ago(m.last_seen_at)}</div>
        </div>
      </div>
      <div className="text-[11px] text-[var(--muted)] truncate" title={m.os}>{m.os || "—"}</div>

      <div className="mt-3 pt-3 border-t border-[var(--border)] flex items-center gap-5 text-xs">
        <Counter label="Installed" value={m.installed_count} />
        <Counter
          label="Stale"
          value={m.stale_count}
          tone={m.stale_count > 0 ? "warn" : "ok"}
        />
        <FreshnessChip f={f} />
      </div>
    </div>
  );
}

function KPI({ label, value, tone }: { label: string; value: number; tone: "ok" | "accent" | "warn" | "muted" }) {
  const colorMap = { ok: "var(--ok)", accent: "var(--accent)", warn: "var(--warn)", muted: "var(--muted-2)" };
  return (
    <div className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted-2)]">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-semibold" style={{ color: colorMap[tone] }}>{value}</span>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: colorMap[tone] }} />
      </div>
    </div>
  );
}

function Counter({ label, value, tone }: { label: string; value: number; tone?: "ok" | "warn" }) {
  const color = tone === "warn" ? "var(--warn)" : tone === "ok" ? "var(--text)" : "var(--text)";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted-2)]">{label}</div>
      <div className="text-sm font-medium" style={{ color }}>{value}</div>
    </div>
  );
}

function FreshnessChip({ f }: { f: ReturnType<typeof freshness> }) {
  const label = { live: "live", recent: "recent", stale: "stale", gone: "offline" }[f];
  return (
    <div className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: freshnessColor[f] }} />
      {label}
    </div>
  );
}
