# vault-project-onboard — 项目接入门神

## 触发

爸爸说"把 X 项目接入门神" / "X 项目改成走 vault" / "试点 X"。

## 核心范式（echo 试点验证）

**双轨值** — 一个 secret 对应多个环境值时不要互相覆盖：

| 后缀 | 含义 | 谁用 |
|---|---|---|
| 无 (默认) | 生产值 | mvp-deployer 部署 |
| `__local` | 本地 dev (如 192.168.1.235 局域网 PG) | `pnpm dev` |
| `__test` / `__remote` / `__cloud` | 其他环境 | 按需 |

**关键发现**：本地 `.env.local` 经常早就改过没回写门神。直接用 `vault inject` 会把本地真在用的 dev DB 覆盖成 prod。**先 diff，差异入 `__local`，再切换**。

## 标准 5 步

### 1. Diff 本地 vs 门神

读项目本地 `.env.local`，逐 key 对比 `vault get X/<KEY>`，记录 value 不一致的项。

### 2. 差异入 `__local`

对每个差异项 `K`，用 `age -R ~/.vault/store/.age-recipients -o ~/.vault/store/X/K__local.age` 写入本地 dev 真值。

### 3. 写 `.env.template` + `.env.template.prod`

```
# .env.template (本地 dev) — 差异项用 __local，无差异用默认
DATABASE_URL=vault://X/DATABASE_URL__local
AZURE_OPENAI_API_KEY=vault://X/AZURE_OPENAI_API_KEY

# .env.template.prod (部署用) — 全部用默认 (prod 值)
DATABASE_URL=vault://X/DATABASE_URL
```

### 4. 项目根加门神说明（5 行模板）

加到项目的 agent 上下文文件（CC 用 CLAUDE.md / Codex 用 AGENTS.md）：

```
## 凭据 / 密钥（门神）
本项目所有密钥在爸爸的 vault。禁止读 ~/.credentials/.env。
- vault project show <slug>     看全部
- vault inject .env.template > .env.local    渲染本地 dev
- vault inject .env.template.prod            渲染生产
- 找不到 key 跑 vault project show <slug>，不要瞎编默认值
```

### 5. 验证

```
cp .env.local .env.local.predoor    # 备份保命
rm .env.local
vault inject .env.template > .env.local
diff <(sort .env.local.predoor) <(sort .env.local)   # 应 0 差异
pnpm dev    # 跑通即成
```

最后 commit 门神：`cd ~/.vault/store && git add -A && git commit -m "X: __local dev 值入库" && git push`。

## Pitfalls

1. **不验证 diff 直接 inject** — 会把本地 dev 真在用的局域网 PG 覆盖成 mvp-deployer 内部的 127.0.0.1，启动连不上。**必须先 diff 后入 `__local`**。
2. **门神里 prod 值不动** — 默认无后缀 = prod，是 mvp-deployer 内的 127.0.0.1（部署到 host 内部访问）。本地永远连不上 127.0.0.1，所以才要 `__local`。
3. **`.env.local` 加 .gitignore** — 渲染产物不要 commit。
4. **备份原 `.env.local`** — `cp .env.local .env.local.predoor`，出事可恢复。
5. **不要扫 ~/projects 重复路径** — macOS 大小写不敏感，`~/Projects` 和 `~/projects` 是同一目录两份显示，去重避免假阳性。

## 已接入项目

- ✅ **echo** (2026-05-02 试点) — 2 条入 __local: DATABASE_URL / NEXTAUTH_URL
- ⏳ 其他 19 项目按需推广（部署/QA 时再做，不一次性强推）

## 相关

- skill `vault` — 门神主文档
- skill `mvp-deployer` — 部署时走 `vault inject manifest.tpl.json`
- `~/.claude/skills/vault.md` — CC 全局门神 skill（任何 CC session 自动加载）
