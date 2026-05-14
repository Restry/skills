import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, type SkillDetail } from "../api";
import { accentFor, ago, short } from "../lib";

export default function SkillDetailPage() {
  const { name = "" } = useParams();
  const [d, setD] = useState<SkillDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setD(null);
    api.skill(name).then(setD).catch((e) => setErr(String(e)));
  }, [name]);

  if (err) return <div className="text-[var(--bad)]">{err}</div>;
  if (!d) return <div className="text-sm text-[var(--muted)]">Loading…</div>;

  const a = accentFor(d.name);
  const staleInstalls = d.installs.filter((i) => i.commit_sha && i.commit_sha !== d.latest_commit).length;

  return (
    <div>
      <Link to="/" className="text-xs text-[var(--muted)] hover:text-[var(--text)]">← back to skills</Link>

      <div
        className="mt-3 rounded-lg p-5 border"
        style={{
          borderColor: "var(--border)",
          background: `linear-gradient(180deg, ${a.bg}, transparent 80%), var(--surface)`,
        }}
      >
        <div className="flex items-start gap-4">
          <span
            className="w-12 h-12 rounded-lg grid place-items-center font-bold text-lg shrink-0"
            style={{ background: a.bg, color: a.fg, boxShadow: `0 0 0 1px ${a.ring}` }}
          >
            {d.name.slice(0, 2).toUpperCase()}
          </span>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{d.name}</h1>
            <p className="text-sm text-[var(--muted)] mt-1 leading-relaxed">
              {d.description || <span className="italic">No description.</span>}
            </p>
            {d.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {d.tags.map((t) => (
                  <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--muted)]">{t}</span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-[var(--border)] flex flex-wrap gap-6 text-xs">
          <Stat label="Latest" value={<code className="font-mono">{short(d.latest_commit)}</code>} />
          <Stat label="Updated" value={ago(d.updated_at)} />
          <Stat label="Installed on" value={`${d.installs.length} machine${d.installs.length === 1 ? "" : "s"}`} />
          <Stat label="Stale" value={staleInstalls === 0 ? "none" : `${staleInstalls}`} tone={staleInstalls ? "warn" : undefined} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5 mt-5">
        <section className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-5">
          <SectionHeader>SKILL.md</SectionHeader>
          <div className="md mt-3">
            <ReactMarkdown>{d.readme_md}</ReactMarkdown>
          </div>
        </section>

        <aside className="space-y-5">
          <section className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
            <SectionHeader compact>Sync command</SectionHeader>
            <code className="block mt-2 text-xs font-mono bg-[var(--bg)] border border-[var(--border)] rounded px-2.5 py-2 text-[var(--text)] select-all">
              sync-skill pull {d.name}
            </code>
          </section>

          <section className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
            <SectionHeader compact>Installed on</SectionHeader>
            {d.installs.length === 0 ? (
              <p className="text-xs text-[var(--muted)] mt-2">No machines have this yet.</p>
            ) : (
              <ul className="mt-2 space-y-1.5">
                {d.installs.map((i) => {
                  const stale = i.commit_sha && i.commit_sha !== d.latest_commit;
                  return (
                    <li key={i.machine_id} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: stale ? "var(--warn)" : "var(--ok)" }} />
                        <span className="truncate">{i.hostname}</span>
                        <span className="text-[10px] text-[var(--muted-2)]">· {i.runtime}</span>
                      </div>
                      <code className="font-mono text-[10px] text-[var(--muted)]">{short(i.commit_sha)}{stale && <span className="text-[var(--warn)] ml-1">stale</span>}</code>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="rounded-lg bg-[var(--surface)] border border-[var(--border)] p-4">
            <SectionHeader compact>Version history</SectionHeader>
            {d.versions.length === 0 ? (
              <p className="text-xs text-[var(--muted)] mt-2">No commits yet.</p>
            ) : (
              <ol className="mt-2 relative border-l border-[var(--border)] ml-1.5 pl-3 space-y-2.5">
                {d.versions.map((v, idx) => (
                  <li key={v.commit_sha} className="relative">
                    <span
                      className="absolute -left-[15px] top-1 w-2 h-2 rounded-full"
                      style={{ background: idx === 0 ? "var(--accent)" : "var(--muted-2)" }}
                    />
                    <div className="text-xs text-[var(--text)] leading-snug">{v.message}</div>
                    <div className="text-[10px] text-[var(--muted-2)] mt-0.5">
                      <code className="font-mono">{short(v.commit_sha)}</code> · {ago(v.committed_at)}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function SectionHeader({ children, compact }: { children: React.ReactNode; compact?: boolean }) {
  return (
    <h2 className={(compact ? "text-[10px]" : "text-xs") + " uppercase tracking-wider font-medium text-[var(--muted)]"}>
      {children}
    </h2>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: "warn" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted-2)]">{label}</div>
      <div className={"mt-0.5 text-sm " + (tone === "warn" ? "text-[var(--warn)]" : "text-[var(--text)]")}>
        {value}
      </div>
    </div>
  );
}
