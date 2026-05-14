import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Skill } from "../api";

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.skills()
      .then((r) => setSkills(r.skills))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    skills.forEach((sk) => sk.tags.forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [skills]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return skills.filter((s) => {
      if (tag && !s.tags.includes(tag)) return false;
      if (!ql) return true;
      return s.name.toLowerCase().includes(ql) || (s.description || "").toLowerCase().includes(ql);
    });
  }, [skills, q, tag]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <input
          className="flex-1 px-3 py-2 border rounded bg-white"
          placeholder="Search skills..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          className="px-3 py-2 border rounded bg-white hover:bg-slate-100"
          onClick={() => api.refresh().then(() => api.skills()).then((r) => setSkills(r.skills))}
        >
          Refresh
        </button>
      </div>
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            className={"px-2 py-1 rounded text-sm " + (tag === null ? "bg-slate-900 text-white" : "bg-white border")}
            onClick={() => setTag(null)}
          >
            all
          </button>
          {allTags.map((t) => (
            <button
              key={t}
              className={"px-2 py-1 rounded text-sm " + (tag === t ? "bg-slate-900 text-white" : "bg-white border")}
              onClick={() => setTag(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      {loading && <div>Loading…</div>}
      {err && <div className="text-red-600">{err}</div>}
      {!loading && filtered.length === 0 && <div className="text-slate-500">No skills found.</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((s) => (
          <Link
            key={s.name}
            to={`/skills/${encodeURIComponent(s.name)}`}
            className="block bg-white rounded border hover:shadow p-4"
          >
            <div className="flex items-center justify-between">
              <div className="font-semibold">{s.name}</div>
              <div className="text-xs text-slate-500">{s.install_count} installs</div>
            </div>
            <div className="text-sm text-slate-600 mt-1 line-clamp-3">{s.description}</div>
            {s.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {s.tags.map((t) => (
                  <span key={t} className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
            <div className="text-xs text-slate-400 mt-2">{s.latest_commit?.slice(0, 8)}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
