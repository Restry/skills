export interface Skill {
  name: string;
  description: string;
  tags: string[];
  latest_commit: string;
  updated_at: string;
  install_count: number;
}

export interface Version {
  commit_sha: string;
  committed_at: string;
  message: string;
}

export interface Install {
  machine_id: string;
  hostname: string;
  runtime: string;
  commit_sha: string;
  installed_at: string;
}

export interface SkillDetail extends Skill {
  readme_md: string;
  versions: Version[];
  installs: Install[];
}

export interface Machine {
  id: string;
  hostname: string;
  os: string;
  runtime: string;
  last_seen_at: string;
  installed_count: number;
  stale_count: number;
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  skills: (q?: string, tag?: string) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (tag) p.set("tag", tag);
    return fetch(`/api/skills?${p}`).then(j<{ skills: Skill[] }>);
  },
  skill: (name: string) => fetch(`/api/skills/${encodeURIComponent(name)}`).then(j<SkillDetail>),
  machines: () => fetch("/api/machines").then(j<{ machines: Machine[] }>),
  refresh: () => fetch("/api/refresh", { method: "POST" }).then(j<{ ok: true; skills: number }>),
};
