import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, type SkillDetail } from "../api";

export default function SkillDetailPage() {
  const { name = "" } = useParams();
  const [d, setD] = useState<SkillDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.skill(name).then(setD).catch((e) => setErr(String(e)));
  }, [name]);

  if (err) return <div className="text-red-600">{err}</div>;
  if (!d) return <div>Loading…</div>;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-slate-500">← all skills</Link>
        <h1 className="text-2xl font-semibold mt-1">{d.name}</h1>
        <p className="text-slate-600">{d.description}</p>
        {d.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {d.tags.map((t) => (
              <span key={t} className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{t}</span>
            ))}
          </div>
        )}
        <code className="block mt-2 text-xs text-slate-500">
          sync-skill pull {d.name}
        </code>
      </div>

      <section className="bg-white rounded border p-4">
        <h2 className="font-semibold mb-2">SKILL.md</h2>
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown>{d.readme_md}</ReactMarkdown>
        </div>
      </section>

      <section className="bg-white rounded border p-4">
        <h2 className="font-semibold mb-2">Version history</h2>
        {d.versions.length === 0 ? (
          <div className="text-sm text-slate-500">No versions yet.</div>
        ) : (
          <ul className="text-sm">
            {d.versions.map((v) => (
              <li key={v.commit_sha} className="py-1 border-b last:border-b-0">
                <code className="text-xs text-slate-500">{v.commit_sha.slice(0, 8)}</code>{" "}
                <span className="text-slate-700">{v.message}</span>{" "}
                <span className="text-xs text-slate-400">{v.committed_at}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-white rounded border p-4">
        <h2 className="font-semibold mb-2">Installed on ({d.installs.length})</h2>
        {d.installs.length === 0 ? (
          <div className="text-sm text-slate-500">No machines have installed this yet.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Hostname</th>
                <th>Runtime</th>
                <th>Commit</th>
                <th>Installed</th>
              </tr>
            </thead>
            <tbody>
              {d.installs.map((i) => {
                const stale = d.latest_commit && i.commit_sha && i.commit_sha !== d.latest_commit;
                return (
                  <tr key={i.machine_id} className="border-t">
                    <td className="py-1">{i.hostname}</td>
                    <td>{i.runtime}</td>
                    <td>
                      <code className="text-xs">{i.commit_sha.slice(0, 8)}</code>
                      {stale && <span className="ml-1 text-xs text-amber-600">stale</span>}
                    </td>
                    <td className="text-slate-500">{i.installed_at}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
