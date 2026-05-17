---
name: mvp-deployer
description: Deploy/update Node/Python/static MVP projects to Daddy's MVP Deployer (deploy.mvp.restry.cn). Async build pipeline (Next.js/Prisma/pnpm/Vite), zip-only uploads, Caddy auto-routing. Triggers — 发布/部署/上线/deploy/publish/redeploy/Next.js 部署/MVP/restry/shutiao 上线/design 上线.
---

# MVP Deployer

Daddy 自建的多项目部署 PaaS。一条 `POST /api/deploy` 就能从源码 zip → install → build → PM2 → Caddy → 上线。本 skill 只讲**用法 + 排坑**，不讲实现。

> ## 🚨 v2 Breaking changes（自下次 redeploy 起生效，详见 `CHANGELOG.md`）
>
> 1. **`manifest.host` 现在必填**。省略 / 空串 → `400`。不再隐式拼 `<project>.mvp.restry.cn`。已有项目 redeploy 前先确认 manifest 里有 host，否则会被 400 挡掉。
> 2. **自动 `prisma migrate deploy` 已删除**。deployer 只跑 `prisma generate`。schema 同步请放在 `manifest.postDeploy` 里，用 manifest.env 里 owner 凭据的 `DATABASE_URL`（不要再依赖 `mvpadmin`）。
> 3. **`POST /api/deploy` 永远异步**。不论有没有 `manifest.build`，都立即返回 `202 + taskId`，走完整 pipeline。原本无 build 时的 sync 路径已删除。
> 4. **部署后自动跑 smoke test + 失败回滚**。默认探 `https://<manifest.host>/`（可选 `smokePaths: ["/health"]`），期望状态码 ∈ {200,204,301,302,307,308}。失败 → 自动回滚到上一版本（文件 + caddy 路由 + pm2）。紧急绕过：`"smokeDisabled": true`。
> 5. **路由 diff 守门**。caddy phase 完成后比对部署前 / 后的 host 列表；任何已有 host 丢失 = 立即回滚。第一次部署没快照，跳过。
> 6. **凭据优先级**：`manifest.env > vault export -p <project> > ~/.credentials/.env 抽前缀`。三者合并为 `finalEnv`，作为 `.env` 文件、PM2、`initOnce`、`postDeploy` 的唯一运行时 env。vault 不可用自动 fallback，task log 写一条 WARN，不阻塞部署。
> 7. **`preserveData` 现在支持显式列表**：`false` opt-out；`true`/省略 → `["data"]`；`string[]` → 自定义相对路径列表（如 `["data", "public/uploads"]`）。绝对路径 / `..` / `~` 会被忽略并 WARN。

> 📦 技能分发唯一来源：独立 `sync-skill` 仓库。本项目不再内置/托管 `skill/`，也不再提供 `/skill.zip` 或 `/install-instruction`。
> 📊 Dashboard：`https://deploy.mvp.restry.cn/`（浏览器支持微信扫码登录；agent / CI 继续走 `Authorization: Bearer $MVP_DEPLOYER__TOKEN`）
>
> ⚠️ **本文不含任何密钥**。所有 token / endpoint 用变量引用，真值见 `~/.credentials/mvp-deployer.env`（chmod 600）。

---

## 0. 触发条件 — 何时加载本 skill

- Daddy 说"发布 / 上线 / 部署 / redeploy"任何 MVP 项目
- 部署目标域名匹配 `*.mvp.restry.cn` 或自定义 CNAME
- `/api/deploy` 报错排查
- 需要修改 deployer 自身代码（`~/projects/mvp-deployer/`，**仅 deployer 作者本人**）
  - 先读 `references/deployer-self-maintenance.md`，里面记录 one-path deploy、finalEnv、preserveData 和自验清单

---

## 0.5 🔒 角色边界（**先看这条**）

本 skill 同时服务两类调用者，**操作集是分开的**：

### A. 普通 agent / 普通机器（默认）—— 你大概率属于这一类
**唯一通道：HTTPS API + Bearer token。** `https://deploy.mvp.restry.cn` + `MVP_DEPLOYER__TOKEN`。

可用动作：
- `POST /api/deploy` — 部署 / 重新部署
- `GET  /api/deploy/tasks/<id>` — 轮询任务
- `GET  /api/inventory` — 部署前预检（端口 / host / env keys）
- `GET  /api/status` — 项目状态
- `GET  /api/logs/<name>` — PM2 日志
- `POST /api/exec/<project>` — **远程在项目目录跑命令**（替代 SSH，见 §3c）
- `DELETE /api/deploy/<name>` — 卸载

**完成所有日常运维（包括"初始化数据库""跑 seed""手动 migrate""排查 .env"）只需要这一组接口。** 这部分文档里出现的代码 = 普通 agent 可以照抄。

### B. 管理员（deployer 作者本人 = Daddy）
当 deployer 自身坏了 / 端口被占 / root pm2 影子 / EACCES 这种平台层故障，才需要 SSH `claw@163.228.243.161`。这些操作集中在 **§附录 A**，普通 agent **完全不要看、看不懂也别试**——你没那台机的 SSH key。

> 如果你正在写"普通 agent"代码并打算 `ssh claw@…`，停下来回到 §3c 用 `/api/exec/`。

---

## 1. Token 与 Secrets

### 1.1 唯一硬要求：deployer token

agent 要部署，**只**需要一样东西：`MVP_DEPLOYER__TOKEN`。其他全部走接口。

```bash
# 调用前 source（如 shell 已有 bashrc auto-load 可跳过）
set -a; source ~/.credentials/.env; set +a

# 现在 shell 里至少有：
#   MVP_DEPLOYER__TOKEN
# 调用：
curl -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" https://deploy.mvp.restry.cn/api/status
```

Python：
```python
import os
token = os.environ["MVP_DEPLOYER__TOKEN"]
```

**没有 token？** 找 Daddy 要。**绝不**在代码、注释、commit、聊天记录里硬编码。Token 一旦泄露立刻轮换：Daddy 改 server `~/.credentials/.env` 的 `MVP_DEPLOYER__TOKEN`，重启 deployer，所有持有旧 token 的 agent 全部失效。

⚠️ Hermes terminal 输出层会把长字符串显示成 `sk-xxx...yyyy` mask。**文件里值是完整的，只是肉眼看不到。** 验证用 `echo ${#MVP_DEPLOYER__TOKEN}` 看长度。

### 1.2 项目 secrets：两条互补路径

应用本身要的 secrets（`DATABASE_URL`、`OPENAI_API_KEY` 之类）有两种交付方式，**任选其一或混用**：

| | Path A：manifest.env 全量传（**外部 agent 默认走这条**） | Path B：服务器抽前缀（Daddy 自用便利层） |
|---|---|---|
| 怎么用 | deploy 时把所有 env KEY/VAL 塞进 `manifest.env` 对象 | Daddy 提前把 `<UPPER_PROJECT>__KEY=val` 写进服务器 `~/.credentials/.env` |
| 优点 | 纯 token+API，agent 完全自包含，不依赖服务器侧预置 | secrets 不落 manifest 文件、不在 API 流量里出现，省心 |
| 缺点 | secrets 会写进 deployer 的 `.deploy-manifest.json`（明文落盘） | 必须 SSH 预置；外部 agent 做不了 |
| 场景 | 你是外部 agent / 一次性新项目 / 想完全自助 | Daddy 维护的常驻项目，懒得每次重传 secrets |

**合并规则**：`finalEnv = { ...credEnv, ...vaultEnv, ...manifestEnv }` —— **manifest 优先级最高**，vault 其次，服务器 `<PROJECT>__` 前缀兜底。最终的 `finalEnv` 会同时写入 `.env`、注入 PM2、`initOnce`、`postDeploy`。

#### Path A 示例（推荐外部 agent 走）

```bash
curl -X POST https://deploy.mvp.restry.cn/api/deploy \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -F "file=@/tmp/my-app.zip" \
  -F 'manifest={
    "project": "my-app", "type": "node", "port": 3801, "run": "pnpm start",
    "host": "my-app.mvp.restry.cn",
    "env": {
      "DATABASE_URL": "postgres://user:pass@host/db",
      "OPENAI_API_KEY": "sk-...",
      "REDIS_URL": "redis://..."
    },
    "postDeploy": "pnpm prisma migrate deploy"
  }'
```

这一发出去：env 写文件 + 注入 install/prisma/build + 注入 PM2 runtime + DB schema 跑 migration —— **全套 0 SSH 完成**。

#### Path B 示例（Daddy 自用）

服务器 `~/.credentials/.env`：
```
IMAGE_STUDIO__DATABASE_URL=postgresql://...
IMAGE_STUDIO__AZURE_OPENAI_API_KEY=...
```

deploy 时 manifest 只放元信息：
```jsonc
{ "project": "image-studio", "type": "node", "port": 3789, "run": "pnpm start" }
```

deployer 自动抽 `IMAGE_STUDIO__` 前缀去前缀后写入项目 .env。**轮换密钥**：Daddy 改服务器一行 → 重新 deploy → 新值生效，无需改 manifest。

### 1.3 Tradeoff 与 best practice

- **完全外部 agent**（你）：走 Path A，所有 env 在 manifest 里。一次自包含部署。
- **想 Path A 但不想 secrets 落盘**：未来加 `manifest.envFile`（base64 一次性传，deployer 用完不写盘）—— 现在还没做，需要的话提。
- **想引用服务器 secrets 又不想看到值**：未来加 `manifest.env.fromCredentials: ["DATABASE_URL"]` —— 现在还没做。
- **绝不要做的**：把 secrets 硬编码到代码 / commit / SKILL.md。token 文档里只能用 `$MVP_DEPLOYER__TOKEN` 引用。

---

## 2. Endpoints

| 用途 | URL | Auth |
|---|---|---|
| 部署 | `POST /api/deploy` | ✓ |
| 任务状态 | `GET /api/deploy/tasks/<taskId>` ⚠️ 不是 `/api/tasks/` | ✓ |
| 项目状态 | `GET /api/status` | ✓ |
| **部署前预检** | **`GET /api/inventory`** ⭐ 强烈建议每次 deploy 前先调 | ✓ |
| **远程执行** | **`POST /api/exec/<project>`** ⭐ 替代 SSH，见 §3c | ✓ |
| **建库建用户** | **`POST /api/db/provision`** ⭐ 共享 PG 上一键建 role+db，见 §3d | ✓ |
| PM2 日志 | `GET /api/logs/<name>?lines=N` | ✓ |
| 卸载 | `DELETE /api/deploy/<name>?removeFiles=true` | ✓ |
| **GitHub 自动部署 webhook** | `POST /api/webhooks/github` | HMAC (无 Bearer) |

**Base URL**: `https://deploy.mvp.restry.cn`

> Skill 分发不走 deployer 运行时 API；`/skill.zip` / `/install-instruction` 已移除。更新技能请发布到 `sync-skill` 仓库。
**Apps live in**: `/opt/mvp-apps/<project>/` （server-side path，普通 agent 用不到，给排错时心里有数）

---

## 3. 标准发布流程

### 3a. 简单项目（无 build，纯 node/python/static）

打包 + 发布：

```bash
set -a; source ~/.credentials/.env; set +a
cd /path/to/project
zip -rq /tmp/$PROJECT.zip . -x 'node_modules/*' '.git/*' '*.log' 'data/*'
```

然后 `curl -X POST /api/deploy` 带 zip + manifest JSON。**manifest 格式和 env 传法见 §1.2 Path A 示例**（完整 curl 在那里，不重复）。返回 `{"taskId": "..."}` → 轮询 `/api/deploy/tasks/<taskId>` 直到 `status:succeeded`。

**Daddy 模式**（省略 env，靠服务器抽前缀）：manifest 只放元信息，env 省略。见 §1.2 Path B。

### 3b. Next.js / Prisma / 需要 build 的项目（异步管线）

参考脚本：`scripts/deploy.py`（本 skill 自带，零依赖、轮询；v2 起 `--preserve-env` 已删除，见上方 breaking changes）。

```bash
python3 ~/.hermes/skills/devops/mvp-deployer/scripts/deploy.py \
  --project image-studio \
  --zip /tmp/image-studio.zip \
  --port 3789 \
  --host design.mvp.restry.cn \
  --build "pnpm install --frozen-lockfile && pnpm prisma generate && pnpm build" \
  --run "pnpm start"
```

成功 phase 序列：`snapshot → extract → preserveData → envLoad → install → prisma → build → swap → pm2 → caddy → [initOnce] → [postDeploy] → smoke → done`（典型 60–90s；中括号项仅当 manifest 提供时跑；smoke 失败自动 rollback）。

### 3c. 远程执行 / 初始化（`/api/exec` + manifest hooks）⭐

普通 agent **不要 SSH**。任何在项目目录下要跑的命令都通过 API：

#### 选项 1：manifest 钩子（部署管线内自动跑）

```jsonc
{
  "project": "image-studio",
  "type": "node", "port": 3789, "host": "design.mvp.restry.cn",
  "run": "pnpm start",
  "build": "pnpm install --frozen-lockfile && pnpm prisma generate && pnpm build",

  // 仅首次部署跑一次，标记文件 .deployer-initialized 写入项目根，下次跳过
  "initOnce":            "node scripts/seed-initial-data.js",
  "initOnceTimeoutMs":   600000,   // 默认 600s，最大 600s

  // 每次 deploy 都跑（pm2 起完之后）。**v2 起：schema migration 必须放这里**——
  // deployer 不再自动跑 prisma migrate deploy。
  // 用项目自己的 DATABASE_URL（manifest.env 里的 owner 凭据），不是 mvpadmin。
  "postDeploy":          "pnpm prisma migrate deploy",
  "postDeployTimeoutMs": 300000    // 默认 300s
}
```

幂等性铁律：
- `initOnce` **失败会让整个部署 task 失败**，且不会写标记文件——下次 deploy 还会再试。成功才写 marker。
- `postDeploy` 每次都跑，**自己写成幂等**（如 `prisma migrate deploy`、`upsert` SQL，而不是 `INSERT`/`CREATE TABLE`）。
- 想强制再跑一次 `initOnce`：先调一次 `/api/exec` 删掉 marker（见下），再 redeploy。

#### 选项 2：临时一次性远程执行

```bash
# 例：手动跑一次种子脚本
curl -sS -X POST https://deploy.mvp.restry.cn/api/exec/image-studio \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"pnpm prisma db seed","timeoutMs":120000}'

# 例：抓现有 .env（替代 SSH base64 那条老路。v2 起也是 --preserve-env 的官方替代）
curl -sS -X POST https://deploy.mvp.restry.cn/api/exec/image-studio \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"cat .env | base64 -w0"}' \
  | jq -r .stdout | base64 -d > /tmp/image-studio.env
# 然后把 /tmp/image-studio.env 解析后塞进下一次 manifest.env（Path A 全量传）

# 例：清掉 initOnce 标记，强制下次重新初始化
curl -sS -X POST https://deploy.mvp.restry.cn/api/exec/image-studio \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"rm -f .deployer-initialized && echo cleared"}'
```

返回结构（**始终 200**，靠 `exitCode` 判断成败）：
```json
{ "exitCode": 0, "signal": null, "stdout": "...", "stderr": "...", "timedOut": false, "durationMs": 423 }
```

字段说明：
- `command` 必填，跑在 `bash -lc` 下，cwd 锁死 `/opt/mvp-apps/<project>`
- `timeoutMs` 可选，默认 60_000，最大 600_000（10 分钟）
- `env` 可选对象，会合并到子进程 env（覆盖 deployer 注入的 credentials）
- 输出每个流截断在 256KB（够看大部分日志，超长的话改 timeout 让命令自己写文件 + 二次 exec `tail`）

什么场景**不应该**用 `/api/exec`：
- ❌ `pm2 restart / delete` —— 走 redeploy 即可
- ❌ `chown / sudo` —— 你没 sudo，会失败；这是平台层故障，找 Daddy
- ❌ 长驻进程（`watch`、tailing logs）—— 会被 10 分钟硬超时杀掉，用 `/api/logs` 代替

---

### 3d. 数据库初始化（`/api/db/provision`）⭐

**何时用**：项目第一次部署、需要 Postgres 库时。**幂等** —— 已存在的库/用户不会报错，可以放在每次部署前都跑（CI 友好）。

**底层**：服务器跑了一个共享的 `mvp-postgres` 容器（postgres:16-alpine），所有 MVP 项目都挂在它下面。一个项目一个 role + 一个同名 db，OWNER = role 自己。**不要自己 SSH 上去 `docker exec psql`** —— 走这个 API 就行。

#### 请求

```bash
curl -sS -X POST https://deploy.mvp.restry.cn/api/db/provision \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"project":"my-app"}'
```

#### Body 字段

| 字段 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `project` | ✓ | — | 项目 slug，sanitize 后作为 db/user 默认名 |
| `dbName` | | =`project` | 库名覆盖（一般不动） |
| `dbUser` | | =`project` | 用户名覆盖 |
| `dbPassword` | | 自动生成 | **新建用户**时不传 → 服务端生成 24 位强密码并返回；**用户已存在**时传 → 轮换密码 |
| `ifExists` | | `"skip"` | `"skip"`=幂等（推荐）；`"error"`=已存在则 409 |

⚠️ **名字会被 sanitize 成 `[a-z0-9_]`**：`my-app` → db/user `my_app`（中划线变下划线）。返回的 `database` / `user` 字段是真实落地的名字，**写到 DATABASE_URL 之前先以响应为准**。

#### 响应（200，新建场景）

```json
{
  "ok": true, "created": true,
  "userCreated": true, "dbCreated": true, "passwordRotated": false,
  "userExisted": false, "dbExisted": false,
  "host": "127.0.0.1", "port": 5432,
  "database": "my_app", "user": "my_app",
  "password": "Xy7...auto-generated-24chars",
  "connectionString": "postgresql://my_app:Xy7...@127.0.0.1:5432/my_app",
  "note": null
}
```

#### 响应（200，幂等再调）

```json
{
  "ok": true, "created": false,
  "userExisted": true, "dbExisted": true,
  "password": null,            // 已存在用户，密码无法回读
  "connectionString": null,
  "note": "User pre-existed and no dbPassword was supplied; password cannot be returned. Pass dbPassword to rotate it."
}
```

➡️ 拿不到密码就传 `dbPassword` 让它**轮换**一遍，返回里就有连接串了。

#### 标准用法：deploy 前一行

```bash
# 1) 建库 → 拿连接串
RESP=$(curl -sS -X POST https://deploy.mvp.restry.cn/api/db/provision \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"project\":\"$PROJECT\",\"dbPassword\":\"$(openssl rand -base64 18 | tr -d '/+=')\"}")
DB_URL=$(echo "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["connectionString"])')

# 2) 把 DB_URL 写进 deploy manifest 的 env，然后 POST /api/deploy
# manifest.env.DATABASE_URL = "$DB_URL"
```

**v2 起 deployer 不再自动跑 `prisma migrate deploy`** —— 用 db.provision 拿到 owner 凭据后，把 migration 命令塞进 `manifest.postDeploy`（用 manifest.env 里的 `DATABASE_URL`），见 §3c。

#### 边界

- ✅ 建 role + 建 db + 设 OWNER + 轮换密码
- ❌ **不会 DROP / RENAME** —— 销毁性操作走 `references/admin-runbook.md`（要 SSH）
- ❌ 不管 GRANTs（OWNER 已经全权限，多余）
- ❌ 不管 schema migration —— 那是 Prisma / Alembic / SQL 脚本的事；落地后用 `/api/exec` 或 manifest hooks 执行（见 §3c）
- 不动其他容器（仅 `mvp-postgres`）。如果你的项目要跑独立 PG，找 Daddy。

---

## 4. Manifest 字段速查

```jsonc
{
  "project": "image-studio",      // 必填，匹配 PM2 app name
  "type": "node",                 // node | python | static
  "port": 3789,                   // 应用监听端口
  "run": "pnpm start",            // PM2 启动命令；shell 命令 OK（deployer 自动 interpreter:none）
  "build": "pnpm install && ...", // 可选；存在即触发异步管线
  "host": "design.mvp.restry.cn", // **必填**（v2 起）— Caddy 公开 hostname。省略 / 空串 → 400
  "preserveData": ["data", "public/uploads"], // 默认 ["data"]；false=不保留；数组=保留指定相对目录
  "env": {                        // **first-class**：所有进程 env 这里传。见 §1.2 Path A
    "DATABASE_URL": "file:./data/app.db",
    "OPENAI_API_KEY": "sk-..."
  },

  // —— smoke test 配置（默认开启） ——
  "smokePaths":    ["/health"],   // 可选，额外探测路径（永远先探 "/"）
  "smokeDisabled": false,         // 紧急绕过，默认 false

  // —— 部署后钩子（见 §3c） ——
  "initOnce":            "node scripts/seed.js",      // 仅首次跑（用 .deployer-initialized 标记）
  "initOnceTimeoutMs":   600000,                       // 默认 600s
  "postDeploy":          "pnpm prisma migrate deploy", // **v2 起 schema migration 唯一入口**（auto-migrate 已删）
  "postDeployTimeoutMs": 300000                        // 默认 300s
}
```

**铁律**：
- archive **必须 zip**（用 extract-zip），传 tar.gz 报 `end of central directory record signature not found`
- 字段名 **`file`**（multer），不是 `archive`/`tarball`
- `env` **不要传 `NODE_ENV=production`**，否则 pnpm 跳过 devDeps，prisma CLI 装不上
- `env` 合并规则（v2）：`finalEnv = { credEnv, ...vault export, ...manifest.env }` → **manifest > vault > credEnv**。vault 不可用 → 自动 fallback,task log 写 WARN,不阻塞部署。外部 agent 默认走 Path A(manifest 全量传),见 §1.2
- `env: {}` 或省略 = 仅用 credEnv（如果服务器配了），**没 credEnv 就真是空 .env**
- `initOnce` / `postDeploy` 失败 = 整个部署 task 失败，要写**幂等**命令
- ⚠️ secrets 会落 `/opt/mvp-apps/<project>/.deploy-manifest.json` 明文存档。介意就走 Path B

---

## 5. 故障排查（普通 agent，全部走 API）

按错误信号查；这一节都不需要 SSH。

| 错误信号 | 原因 | 修复 |
|---|---|---|
| `MulterError: Unexpected field` | manifest 字段名错 / archive 不是 zip | multer 字段必须 `file`，archive 必须 zip |
| `end of central directory record signature not found` | 传了 tar.gz | 改 `zip -rq ...` |
| Prisma `Environment variable not found: DATABASE_URL` | manifest.env 没传 + 服务器也没配 `<APP>__DATABASE_URL` | **直接在 manifest.env 加 `DATABASE_URL`**（标准做法）；或让 Daddy 加到服务器 |
| `/api/deploy/tasks/<id>` 404 | 用了错误路径 `/api/tasks/` | 路径是 `/api/deploy/tasks/` |
| Caddy `duplicate ID 'mvp-route-<x>'` | 旧 deployer 残留路由 | 见 `references/caddy-recovery.md` |
| PM2 `ELF SyntaxError` 进程 errored | shell 命令被当 JS 解析 | 新版 deployer 自动加 `interpreter:none`；踩到说明 deployer 版本旧，找 Daddy |
| Next.js runtime `process.env.X` 是 undefined | `next start` 不读 .env | manifest.env 必须显式列出私有 env，或本地用 `npx dotenv-cli -e .env -- pnpm start` |
| 删了文件但旧版还在跑 | deployer 解压是增量，不清理旧文件 | `DELETE /api/deploy/<name>?removeFiles=true` 后再 POST 重部署 |
| `/api/status` 看到 restart 数 100k+ | 历史累计 | 别慌，正常 |
| `initOnce` 已跑过，想重跑 | marker 文件挡着 | `POST /api/exec/<p>` 跑 `rm -f .deployer-initialized` 后重 deploy |
| `postDeploy` 失败让整个 task 失败 | 命令不幂等或超时 | 检查 `addLog`，写成幂等（`migrate deploy` / `upsert`）/ 调大 `postDeployTimeoutMs` |
| `/api/exec` 返 `exitCode:-1` 且 `timedOut:true` | 命令超过 timeoutMs | 提高 `timeoutMs`（最大 600000）或拆分命令 |
| `/api/exec` `Project directory does not exist` | 项目还没 deploy 过 | 先 `POST /api/deploy` 一次 |

排错三板斧（自助流程）：
1. `GET /api/inventory` — 看 ports/hosts/envKeys/manifest 是否符合预期
2. `GET /api/logs/<name>?lines=200` — 看 PM2 stdout/stderr
3. `POST /api/exec/<name>` 跑 `cat .env` / `ls -la` / `node -e '...'` — 在项目目录排查

如果都用上还查不出，是平台层问题（端口冲突、root pm2、EACCES 之类），找 Daddy；普通 agent 走到这就该停手。

---

## 6. Pitfalls Speedrun（按频率）

1. **每次 deploy 前先 `GET /api/inventory`** — 端口 / host / 已有 envKeys，一次拿全
2. **archive 必须 zip**（不是 tar.gz）；字段名 **`file`**
3. **manifest.env 别传 `NODE_ENV=production`** — pnpm 跳 devDeps，prisma 装不上
4. **`host` 字段 v2 起必填** — 省略 / 空串 → 400; deployer 不再隐式拼 `<project>.mvp.restry.cn`
5. **zip 永远 `-x 'data/*'`** — 防止覆盖项目 SQLite 数据库 / 用户上传
6. **`/api/deploy/tasks/<id>`**（不是 `/api/tasks/<id>`）
7. **`initOnce` / `postDeploy` 必须幂等** — 失败让整个部署失败
8. **token 只在 `~/.credentials/.env` `MVP_DEPLOYER__TOKEN`**，其他全部 `os.environ[]` / `$VAR`
9. **`/api/exec` 不要跑 `pm2 restart` / `sudo` / 长驻进程** — 用 redeploy / 找 Daddy / `/api/logs`
10. **deploy 失败要查的三件套**：inventory → logs → exec `cat .env`

---

---

## 6.5 GitHub 自动部署（manifest opt-in，**纯轮询，默认无需 webhook**）

给 `.deploy-manifest.json` 加一段就行,**不用配 webhook**:

```jsonc
"autoDeploy": {
  "enabled": true, "provider": "github",
  "repo": "Restry/skills",   // owner/repo / https URL / git@ URL 都接受
  "branch": "main",
  "path": "."                // 可选,repo 内子目录
}
```

行为:
- **默认每 10 分钟轮询一次 `git ls-remote`**,发现新 sha 自动走完整部署管线(smoke + rollback 全照走)
- **只在中国时间白天跑**:默认 `Asia/Shanghai` 09:00–23:00 (区间 `[start, end)`,23:00 整已不再 active),夜间 timer 照 tick 但 pollOnce 立刻返回,不查 GitHub、不刷日志
- 部署中又来新 sha → 落到 `pendingSha`,下一次 tick 接力
- task 跑挂(smoke fail / rollback) → state 写 `lastError`,**lastDeployedSha 不前进**,下次 tick 会重试同一个 sha
- `GET /api/status` 返回顶层 `autoDeploySchedule` 和每个项目的 `autoDeploy` 状态(lastQueuedSha / lastDeployedSha / pendingSha / lastTaskId / lastDeployAt / lastError)

可选加速:**配 GitHub webhook**(`POST /api/webhooks/github`,HMAC 验签,不需要 Bearer,绕过 IP allowlist)。push 立即触发,不用等 10 分钟。secret 未配 → 503(轮询照常工作)。

服务端可调环境变量(Daddy 维护,普通 agent 不用碰):
- `AUTO_DEPLOY_POLL_INTERVAL_MS` 默认 `600000` (10 min)
- `AUTO_DEPLOY_ACTIVE_TZ` 默认 `Asia/Shanghai`
- `AUTO_DEPLOY_ACTIVE_START_HOUR` 默认 `9`
- `AUTO_DEPLOY_ACTIVE_END_HOUR` 默认 `23`(exclusive)
- `AUTO_DEPLOY_DISABLE_SCHEDULE=true` 全天运行

## 7. 配套文件

| 路径 | 用途 |
|---|---|
| `scripts/deploy.py` | 异步部署 Python 脚本，轮询任务（host 必填；token 兼容 `DEPLOYER_TOKEN` 和 `MVP_DEPLOYER__TOKEN`） |
| `references/caddy-recovery.md` | Caddy 重复 @id 路由清理流程 |
| `references/manifest-schema.md` | manifest 完整字段定义 |
| `references/deployer-self-maintenance.md` | 修改 mvp-deployer 自身时的 one-path deploy/env/preserveData/验证清单 |

加载方式：`skill_view(name="mvp-deployer", file_path="scripts/deploy.py")`

### 7.1 发布/分发本 skill

唯一分发源是 `sync-skill` 仓库。更新本地 Hermes skill 后发布：

```bash
python3 ~/.hermes/skills/sync-skill/scripts/publish.py \
  ~/.hermes/skills/devops/mvp-deployer \
  -m "publish mvp-deployer"
```

不要再把 skill 副本放回 `~/projects/mvp-deployer/skill/`，也不要恢复 `/skill.zip` / `/install-instruction`。

---

## 8. 管理员维护（仅 Daddy）

平台层故障（API 解决不了的）、deployer 自身上线流程、安全 checklist 全部归到 **`references/admin-runbook.md`**——普通 agent 不需要、也跑不了那里的命令。

加载方式：`skill_view(name="mvp-deployer", file_path="references/admin-runbook.md")`

普通 agent 看到 deploy 卡住、API 401、端口冲突这类**平台层**问题，停手找 Daddy。日常的 manifest/部署/初始化全部走 §3 + §4。
