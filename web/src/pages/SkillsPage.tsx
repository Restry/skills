import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Skill } from "../api";
import { accentFor, ago, short } from "../lib";

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = () => api.skills().then((r) => setSkills(r.skills));

  useEffect(() => {
    setLoading(true);
    load().catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, []);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    skills.forEach((sk) => sk.tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [skills]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase().trim();
    return skills.filter((s) => {
      if (tag && !s.tags.includes(tag)) return false;
      if (!ql) return true;
      return s.name.toLowerCase().includes(ql) || (s.description || "").toLowerCase().includes(ql);
    });
  }, [skills, q, tag]);

  const totalInstalls = skills.reduce((a, s) => a + s.install_count, 0);

  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Skills</h1>
          <p className="text-sm text-[var(--muted)] mt-1">
            {skills.length} published · {totalInstalls} total installs across machines
          </p>
        </div>
        <button
          onClick={async () => {
            setRefreshing(true);
            try { await api.refresh(); await load(); } catch (e) { setErr(String(e)); }
            setRefreshing(false);
          }}
          className="text-xs px-2.5 py-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--accent)]"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <div className="relative flex-1">
          <input
            className="w-full px-3.5 py-2.5 pl-9 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-sm placeholder:text-[var(--muted-2)] focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]"
            placeholder="Search skills by name or description…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-3.5-3.5"/></svg>
        </div>
      </div>

      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-5">
          <TagChip active={tag === null} onClick={() => setTag(null)}>all</TagChip>
          {allTags.map((t) => (
            <TagChip key={t} active={tag === t} onClick={() => setTag(t)}>{t}</TagChip>
          ))}
        </div>
      )}

      {loading && <SkeletonGrid />}
      {err && <div className="text-[var(--bad)] text-sm">{err}</div>}
      {!loading && filtered.length === 0 && (
        <EmptyState
          title={q || tag ? "No skills match your filter" : "No skills published yet"}
          hint={q || tag ? "Try clearing the search." : "Run `sync-skill publish <dir>` from a machine to add one."}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((s) => <SkillCard key={s.name} s={s} />)}
      </div>
    </div>
  );
}

function TagChip({ children, active, onClick }: { children: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={
        "text-xs px-2 py-0.5 rounded-full border transition-colors " +
        (active
          ? "bg-[var(--accent-soft)] border-[var(--accent)] text-[var(--text)]"
          : "bg-[var(--surface)] border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]")
      }
    >
      {children}
    </button>
  );
}

function SkillCard({ s }: { s: Skill }) {
  const a = accentFor(s.name);
  return (
    <Link
      to={`/skills/${encodeURIComponent(s.name)}`}
      className="group relative block rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 hover:border-[color:var(--accent)] transition-colors overflow-hidden"
    >
      <span
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: a.dot }}
      />
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="w-7 h-7 rounded-md grid place-items-center font-bold text-[11px] shrink-0"
            style={{ background: a.bg, color: a.fg }}
          >
            {s.name.slice(0, 2).toUpperCase()}
          </span>
          <div className="min-w-0">
            <div className="font-medium truncate">{s.name}</div>
            <div className="text-[10px] font-mono text-[var(--muted-2)]">{short(s.latest_commit)}</div>
          </div>
        </div>
        <span
          className="shrink-0 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full"
          style={{ background: "var(--surface-2)", color: "var(--muted)" }}
          title={`${s.install_count} machine(s)`}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.install_count ? "var(--ok)" : "var(--muted-2)" }} />
          {s.install_count}
        </span>
      </div>
      <p
        className="text-xs text-[var(--muted)] leading-relaxed"
        style={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}
      >
        {s.description || <span className="italic">No description.</span>}
      </p>
      {s.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {s.tags.slice(0, 4).map((t) => (
            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--surface-2)] text-[var(--muted)]">{t}</span>
          ))}
        </div>
      )}
      <div className="mt-3 text-[10px] text-[var(--muted-2)]">updated {ago(s.updated_at)}</div>
    </Link>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4 h-32 animate-pulse" />
      ))}
    </div>
  );
}

function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] py-10 px-6 text-center">
      <div className="text-sm text-[var(--text)] mb-1">{title}</div>
      <code className="text-xs text-[var(--muted)]">{hint}</code>
    </div>
  );
}
