import { useEffect, useState } from "react";
import { api, type Machine } from "../api";

export default function MachinesPage() {
  const [machines, setMachines] = useState<Machine[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.machines().then((r) => setMachines(r.machines)).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-red-600">{err}</div>;

  return (
    <div className="bg-white rounded border">
      <table className="w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="py-2 px-3">Hostname</th>
            <th>Runtime</th>
            <th>OS</th>
            <th>Last seen</th>
            <th>Skills</th>
            <th>Stale</th>
            <th className="px-3">Machine ID</th>
          </tr>
        </thead>
        <tbody>
          {machines.map((m) => (
            <tr key={m.id} className="border-t">
              <td className="py-2 px-3 font-medium">{m.hostname}</td>
              <td>{m.runtime}</td>
              <td className="text-slate-500">{m.os}</td>
              <td className="text-slate-500">{m.last_seen_at}</td>
              <td>{m.installed_count}</td>
              <td>{m.stale_count > 0 ? <span className="text-amber-600">{m.stale_count}</span> : 0}</td>
              <td className="px-3"><code className="text-xs text-slate-400">{m.id.slice(0, 8)}</code></td>
            </tr>
          ))}
          {machines.length === 0 && (
            <tr><td colSpan={7} className="py-4 px-3 text-slate-500">No machines registered yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
