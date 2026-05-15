# Vault Snapshot 部署模式

## 触发场景

应用本身要在运行时读门神（vault）数据（不是只在部署时读 env），且部署到 mvp-deployer host 上。例：
- menshen-ui（vault 浏览器 UI）
- 任何 dashboard / admin 工具想展示 vault 元数据

mvp-deployer host **没有** `vault` CLI、`~/.ssh/id_rsa`、`~/.vault/store/`，应用调 `child_process.execSync('vault get')` 一定失败。

## 核心方案

**打包前导出 vault → JSON 快照 → 包进 zip → 运行时读文件**。

### Snapshot 文件结构

```ts
type Snapshot = {
  version: 1;
  exported_at: string;  // ISO
  projects: Record<string, {
    desc?: string; stack?: string; domain?: string;
    repo?: string; status?: string; aliases?: string[];
    deploy?: string; app_slug?: string; wechat_app?: string;
    local_path?: string; notes?: string;
  }>;
  secrets: Record<string, string>;          // "echo/DATABASE_URL" -> 真值
  secrets_meta: Record<string, {
    desc?: string; vendor?: string; severity?: string;
    where_to_get?: string; category?: string; tags?: string;
    created_at?: string; notes?: string;
  }>;
};
```

### 生成脚本（部署前跑）

见 `scripts/export-vault-snapshot.py`。核心：
1. `age -d -i ~/.ssh/id_rsa ~/.vault/store/index.toml.age` 解 TOML index
2. 正则解析 `[_project.X]` 段 → projects
3. 正则解析 `[X/KEY]` 段 → secrets_meta
4. `os.walk(STORE)` 遍历所有 `*.age` 文件，逐个 `age -d` 解出真值 → secrets
5. 写到 `<repo>/.vault-snapshot.json`
6. **必须** `.gitignore` 加 `.vault-snapshot.json`（含全部真值，绝不能 push GitHub）

### 运行时 lib（替代 vault CLI 调用）

```ts
// src/lib/vault.ts
import fs from "node:fs";
import path from "node:path";

let _cache: { data: Snapshot; at: number } | null = null;
function loadSnapshot(): Snapshot {
  if (_cache && Date.now() - _cache.at < 5 * 60_000) return _cache.data;
  const p = path.join(process.cwd(), ".vault-snapshot.json");
  const data = JSON.parse(fs.readFileSync(p, "utf8"));
  _cache = { data, at: Date.now() };
  return data;
}

export function listProjects() { return Object.keys(loadSnapshot().projects); }
export function getProject(name: string) { return loadSnapshot().projects[name]; }
export function getSecret(key: string) {
  const v = loadSnapshot().secrets[key];
  if (!v) throw new Error(`secret not found: ${key}`);
  return v;
}
```

### bootstrapEnv 注入（NEXT_PUBLIC_* 必须 build-time 可见）

```js
// scripts/bootstrap-env.cjs (prebuild + prestart 都跑)
const fs = require("fs"), path = require("path");
const snap = JSON.parse(fs.readFileSync(path.join(__dirname, "..", ".vault-snapshot.json"), "utf8"));
const APP = "menshen-ui";  // 改成你的项目 slug
const lines = [];
for (const [key, val] of Object.entries(snap.secrets)) {
  if (!key.startsWith(APP + "/")) continue;
  const name = key.slice(APP.length + 1).replace(/__\w+$/, "");  // 去 __local 等后缀
  lines.push(`${name}=${val}`);
}
fs.writeFileSync(path.join(__dirname, "..", ".env.production.local"), lines.join("\n"));
console.log(`[prebuild] wrote ${lines.length} env vars to .env.production.local`);
```

`package.json`:
```json
"scripts": {
  "prebuild": "node scripts/bootstrap-env.cjs",
  "build": "next build",
  "prestart": "node scripts/bootstrap-env.cjs",
  "start": "next start"
}
```

`.env.production.local` 加 `.gitignore`。

## ⚠️ 3 个部署陷阱（已踩过）

### 1. NODE_ENV=production 让 pnpm 跳过 devDeps → Tailwind v4 build 炸

**症状**：deployer log 显示 `devDependencies: skipped because NODE_ENV is set to production`，然后 `globals.css` postcss 报 webpack 错（`@tailwindcss/postcss` 没装）。

**修法**：manifest.tpl.json 的 `env` **不要** `NODE_ENV: "production"`（PM2 默认会自动设运行时 NODE_ENV，但 build 阶段需要 devDeps）：

```json
{
  "build": "pnpm install --frozen-lockfile --prod=false && pnpm build",
  "env": { "PORT": "3812" }
}
```

`--prod=false` 是双保险，强制装 devDeps。

### 2. webpack `@/` alias 在 host 上不解析

**症状**：本地 `pnpm build` 通过，host 上报 `Module not found: Can't resolve '@/lib/vault'`。

根因：本地 next 通过 tsconfig paths 解析 `@/`，但 host 上某些情况下 webpack 不读 tsconfig。

**修法**：`next.config.mjs` 显式注册 alias：

```js
import path from "node:path";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  webpack: (config) => {
    config.resolve.alias["@"] = path.join(__dirname, "src");
    return config;
  },
};
```

### 3. mvp-deployer multipart 字段名

manifest **必须**是 inline JSON 字符串，**不能** `@file`：

```bash
# ❌ 错（MulterError: Unexpected field）
curl -F "manifest=@manifest.tpl.json"

# ✅ 对
curl -F "manifest=$(cat manifest.tpl.json)"
```

## 标准部署流程

```python
import subprocess, json, os, time

# 1. 重新生成 snapshot（每次部署前）
# 跑 scripts/export-vault-snapshot.py（见本 skill 的 scripts/ 目录）

# 2. 打 zip（排除 node_modules / .next / .git / screenshots）
subprocess.run(["zip","-rq","/tmp/app.zip",".",
    "-x","node_modules/*",".next/*",".git/*","screenshots/*"], cwd="<repo>")

# 3. 调 mvp-deployer
TOKEN = subprocess.run(["vault","get","mvp-deployer/TOKEN"], capture_output=True, text=True).stdout.strip()
manifest_str = open("manifest.tpl.json").read()
r = subprocess.run(["curl","-sS","-X","POST","https://deploy.mvp.restry.cn/api/deploy",
    "-H",f"Authorization: Bearer {TOKEN}",
    "-F","file=@/tmp/app.zip",
    "-F",f"manifest={manifest_str}"], capture_output=True, text=True)
task_id = json.loads(r.stdout)["taskId"]

# 4. 轮询（注意路径是 /api/deploy/tasks/，不是 /api/tasks/）
for i in range(60):
    time.sleep(5)
    r = subprocess.run(["curl","-s","-H",f"Authorization: Bearer {TOKEN}",
        f"https://deploy.mvp.restry.cn/api/deploy/tasks/{task_id}"], capture_output=True, text=True)
    t = json.loads(r.stdout)
    if t["status"] in ("succeeded","failed"):
        if t["status"] == "failed": print("LOG:", "".join(t.get("logs",[]))[-1500:])
        break
```

## 安全权衡（必读）

**这套方案的代价**：snapshot 包含全部 vault 真值，部署 zip 在传输和 host 磁盘上都是明文。任何 host 被攻破 = vault 全泄露。

**适用场景**：
- ✅ 应用必须运行时访问大量 vault 数据（如 UI 浏览器）
- ✅ 部署到自己控制的 host（mvp-deployer）
- ✅ 公网入口加了认证（微信扫码 + 白名单）

**不适用**：
- ❌ 应用只需 1-2 条凭据 → 用 `vault inject manifest.tpl.json` 标准模式
- ❌ 部署到第三方 PaaS（Vercel 等）→ 用对应平台的 secret manager

## 微信登录 admin 白名单的 bootstrap 模式

snapshot 模式下 host 写不回 vault（没 CLI/key），admin 白名单怎么管？

**bootstrap 方案**：第一个登录者自动成为 admin，写到 host 本地文件（重启会丢，可接受 MVP）：

```ts
async function tryBootstrapAdmin(openid: string) {
  const file = "/tmp/<app>-admin-openids.txt";
  if (fs.existsSync(file) && fs.readFileSync(file, "utf8").trim()) return false;
  fs.writeFileSync(file, openid);
  return true;
}

async function getAdminOpenids() {
  // 优先读本地 bootstrap 文件，再读 snapshot 里的 ADMIN_OPENIDS
  const file = "/tmp/<app>-admin-openids.txt";
  if (fs.existsSync(file)) return fs.readFileSync(file,"utf8").split(/[,\s]+/).filter(Boolean);
  try { return getSecret("<app>/ADMIN_OPENIDS").split(/[,\s]+/).filter(Boolean); }
  catch { return []; }
}
```

NextAuth `authorize` 里：

```ts
let admins = await getAdminOpenids();
if (admins.length === 0) {
  await tryBootstrapAdmin(openid);
  admins = [openid];
}
const allowed = admins.includes(openid);
```

## 自动重生 + 重部署 hook（爸爸要求"每次门神改动自动调整"）

snapshot 模式下，vault 任何写命令（add/rm/meta/project set）后必须重生 snapshot + 重部署，否则线上和门神不一致。**装 hook 自动化**，不要手动跑：

### 装法

1. `~/.vault/hooks/regen-snapshot.py` — 解全 vault 重写 `<app>/.vault-snapshot.json`（脚本同本 skill「Snapshot 生成脚本」节）
2. `~/.vault/hooks/post-write.sh` — 防抖 + zip + 调 mvp-deployer + 异步轮询 task。关键 4 招：
   - **timestamp 文件 + 30s debounce**：写 `$NOW` 到 `/tmp/<app>-redeploy-pending`，fork 一个 child sleep 30s 后比对 `cat $STAMP == $NOW`，不匹配则 silent exit（被新写命令覆盖）。**不要用 flock**——下面 v1 失败教训
   - hook 主进程立刻 `exit 0` 不阻塞 vault 写命令（fork 出去的 child 跑实际部署）
   - child 内部同步部署 + 同步轮询都行（已经 detach），全部写 `/tmp/<app>-autoredeploy.log`
   - 每个子步骤要 robust 错误处理：snapshot 失败 / vault get TOKEN 失败 / curl JSON 解析失败 都要 log + exit，不能让 set -e 静默崩

### v1 flock 失败教训（**不要再走老路**）

最初实现用 `flock -n 9` + `sleep 5 + LAST_TRIGGER_FILE`。结果连续 vault 写命令时**全部跳过**，部署一次都没真跑：
- bash flock 持锁的 fd 在 subshell + nohup detach 时行为诡异，第一个 hook 进程的 lock fd 没及时释放
- 8 条豆包凭据连续 `vault add` 触发 8 次 hook，全部 `跳过(已有任务在跑)`
- 看 `pgrep -f post-write.sh` 没进程但 `lsof lock` 还显示占用

**根因**：bash flock + nohup + detach 三者交互不稳。换成 timestamp 文件 debounce（v2 上面那套）一次跑通。

3. patch `~/.vault/bin/vault` 的 `git_sync()` 末尾，push 后异步触发：

```
if [ -x "$HOME/.vault/hooks/post-write.sh" ]; then
    (nohup "$HOME/.vault/hooks/post-write.sh" >/dev/null 2>&1 &)
fi
```

### 关键约束（踩过的坑）

- **必须 nohup &**：否则 vault 写命令本身阻塞等部署
- **必须 timestamp debounce 不要 flock**：flock + nohup + detach 三者交互不稳，连续触发会全卡死。详见上面「v1 失败教训」
- **轮询 in child fork**：让 hook 主进程立刻返回
- **regen 脚本注意 `__edge-fn` 这种带连字符后缀**：早期 regex `[A-Z0-9_]+__\w+` 不匹配 `__edge-fn`，导致 secrets_meta 漏 122 条。正确：`[A-Z0-9_]+(?:__[\w-]+)?`
- **直接编辑 index.toml.age 时 hook 不触发**：批量整改（如健康检查修复、tag retag）走 `age -d / age -R + git commit` 绕过 vault CLI 时，`git_sync()` 没被调到 → hook 不触发 → snapshot 不更新 → 线上看不到改动。**修法**：脚本最后手动调一次 `subprocess.run([os.path.expanduser("~/.vault/hooks/post-write.sh")])`
- 监控：`tail -f /tmp/<app>-autoredeploy.log`

### 替代方案（爸爸 2026-05-02 拒绝）

cron 每小时跑一次 regen + redeploy。代价：vault 改完最长 1 小时才上线。爸爸明确要"每次都自动"。

## 实战案例

**menshen-ui** (2026-05-02 上线 https://menshen.mvp.restry.cn)
- 247 secrets / 22 项目，snapshot 60KB
- 全套套用本 skill：snapshot + bootstrapEnv + bootstrap admin + 自动 hook
- 踩过：NODE_ENV=production 跳 devDeps、`@/` alias 不认、CC 自己加回 NODE_ENV
- commit `bc7da48` 一次性修齐 3 个陷阱
- hook 装在 `~/.vault/hooks/`，每次 `vault meta/add/project set` 自动 5s 防抖触发重部署
