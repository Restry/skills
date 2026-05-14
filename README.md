# sync-skill

跨机器同步 Agent skills (Claude / OpenClaw / Hermes …) 用一个 GitHub 仓库作中央存储 + 小后端 + Web 看板。**客户端本身就是一个 skill**，由 agent 在对话里调用。

```
GitHub repo (skills/<name>/SKILL.md) ──> 后端 ──> Web 看板
                                            ▲
                                            │ heartbeat
                                  sync-skill skill (装在每台机器上)
                                            │
                                            └──> ~/.claude/skills/
```

## 三块

- `server/` — FastAPI + SQLite。镜像 GitHub 仓库，索引 skills，存机器心跳，提供 REST API。
- `web/` — Vite + React 看板。技能列表 / 详情 / 版本历史 / 机器看板。
- `skill/sync-skill/` — **agent 端 skill**，包含 SKILL.md 和 stdlib-only Python 脚本。装在每台机器的 `~/.claude/skills/sync-skill/` 下，agent 读到指令后自动调用脚本。

## 1. 准备 GitHub 仓库

```
skills/
  my-skill/
    SKILL.md       # YAML frontmatter: name / description / tags
    helper.py
```

## 2. 部署服务端

```bash
cp .env.example .env             # 填 SYNC_SKILL_REPO
docker compose up -d --build
```

- Web: `http://<host>:8080`
- API: `http://<host>:8000/api`
- 后端每 60 秒 `git pull` 一次

## 3. 在每台机器上装 sync-skill skill 自己

第一次需要手动 bootstrap（鸡生蛋）：

```bash
git clone https://github.com/<you>/sync-skill.git /tmp/ss
cp -r /tmp/ss/skill/sync-skill ~/.claude/skills/sync-skill
```

之后 agent 就能看到这个 skill。要求 Python ≥ 3.8（脚本只用 stdlib）。

## 4. 在 agent 里用

直接告诉 agent，比如：

- "帮我初始化 sync-skill，server 是 `http://host:8000/api`，repo 是 `https://github.com/me/skills.git`"
- "同步一下所有技能"
- "看看服务器上有哪些技能"
- "把 `~/code/my-skill` 发布出去"
- "我本地装了哪些技能？哪些过时了？"

Agent 会读 `SKILL.md`，调用对应脚本：

```
~/.claude/skills/sync-skill/scripts/
  init.py     首次配置 + 注册机器
  list.py     列出服务器上所有技能
  pull.py     拉技能到 ~/.claude/skills/（无参=全部，有参=指定）
  publish.py  发布一个本地 skill 目录到仓库
  status.py   本地 vs 服务器版本对比
```

发布之后，sync-skill 自己的更新也走这套机制 —— 在一台机器上 `publish ~/.claude/skills/sync-skill`，其他机器 `pull sync-skill`。

## 设计要点

- **无鉴权**：内网可信。
- **格式统一**：所有 runtime 都用同一份 SKILL.md，无需转换。
- **手动触发**：不跑后台 daemon，agent 调用即同步。
- **git 是真相**：删了后端 SQLite 也能从仓库重建，只丢心跳。
- **客户端零依赖**：stdlib-only Python 脚本，目标机器不需要 `pip install`。
- **技能内容不经过后端**：CLI/脚本直接 `git pull`，后端只接收心跳。

完整设计文档：`docs/superpowers/specs/2026-05-14-sync-skill-design.md`。

## 仓库布局

```
sync-skill/
├── server/                       FastAPI 后端 + 索引器
├── web/                          Vite + React 前端
├── skill/sync-skill/             agent 端 skill（SKILL.md + 脚本）
│   ├── SKILL.md
│   └── scripts/{init,list,pull,publish,status,_common}.py
├── docker-compose.yml
└── docs/superpowers/specs/2026-05-14-sync-skill-design.md
```
