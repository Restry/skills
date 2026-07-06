# mvp-deployer 管理员手册（Daddy 专用）

> ⚠️ **普通 agent 不要看这份**。这里全是 SSH `claw@163.228.243.161` 的命令，你本机没那台机的 SSH key，照抄跑不动。正确做法是用 `/api/exec` + `/api/deploy`（见主 SKILL.md §3）。
>
> 这份只给 deployer 作者本人（Daddy）翻。

合并自原 admin-runbook + caddy-recovery + dashboard-local-qa + deployer-self-maintenance + 卡死 task 解锁。

---

## 1. zombie task 解锁（最常见）

任务卡 `status=running phase=install`、重发 POST /api/deploy 返同一 taskId、新 task 永远 queued、DELETE/cancel API 全 404 → 必走 SSH 解锁。最常触发：puppeteer 拉 chrome（项目侧坑，见 pitfalls puppeteer-core）。

### Step 1: 确认 deployer 自身没挂

```bash
ssh claw@163.228.243.161 'pm2 status mvp-deployer 2>&1 | grep -E "online|errored"'
```
errored → 直接 `pm2 restart mvp-deployer`（内存 task 清零，所有 task 直接报错）。

### Step 2: 找卡死子进程（**不要**先 restart deployer）

```bash
ssh claw@163.228.243.161 'ps -ef | grep -E "pnpm install|install.mjs|node install|puppeteer|chromium" | grep -v grep'
```

典型输出：
```
claw  1749763 1732757  0 11:55 ?  00:00:08 node /usr/bin/pnpm install --frozen-lockfile
claw  1749786 1749763  0 11:55 ?  00:00:00 sh -c node install.mjs
claw  1749788 1749786  0 11:55 ?  00:00:10 node install.mjs       ← 元凶
```

`1732757` 是 deployer 自己 spawn 的 shell，**不要杀**；杀**孙子**那几个。

### Step 3: 杀链（孙子 → 子 → 父，自下而上）

```bash
ssh claw@163.228.243.161 'kill -9 1749788 1749786 1749763 2>&1; sleep 2; pgrep -af "install.mjs|install --frozen" || echo clean'
```

### Step 4: 验 task 已自动 failed

```bash
ssh claw@163.228.243.161 '
. ~/.credentials/.env
H=$(mktemp); printf "Authorization: Bearer*** > $H
curl -sS -H @$H "http://127.0.0.1:9800/api/deploy/tasks/<tid>" | jq .status
rm -f $H
'
```
期望 `failed`。

### Step 5: 清残骸

```bash
curl -sS -X POST .../api/exec/<project> \
  -d '{"command":"rm -rf /opt/mvp-apps/<project>.deploy-*","timeoutMs":10000}'
```

**修真根因**（通常是 puppeteer 类 postinstall 拉外网），再 redeploy。

### 反模式

| 想做 | 结果 | 真做法 |
|---|---|---|
| POST /api/deploy 重发 | 返同 taskId | 必须先 kill 让 task failed |
| DELETE /api/deploy/<p> | undeployed 但 task 还 running | 该接口只清 pm2/caddy，不动 task state |
| POST /api/deploy/tasks/<tid>/cancel | 404 | 没这接口，只能杀子进程 |
| 改 project 名重发 | 新 task queued 排不上 | 队列串行，改名没用 |
| 等自然超时 | 永远不超时 | 必须主动杀 |
| `pm2 restart mvp-deployer` 当首选 | 能解，但其他正在 deploy 的 task state 全丢 | 万不得已 |

### 永久修法（待 Daddy 改 deployer）

1. install/build/postDeploy 阶段总超时（`installTimeoutMs` default 600s）
2. `POST /api/deploy/tasks/<tid>/cancel`（kill descendants + 标 failed）
3. `POST /api/deploy` 看到同 project 还在 running → 409 / `force=true` 杀掉重发

---

## 2. 更新 deployer 自身（rsync）

```bash
cd ~/projects/mvp-deployer
rsync -az --delete \
  --exclude='node_modules' --exclude='.git' --exclude='public/uploads' \
  --exclude='data' --exclude='*.log' --exclude='.credentials' \
  ./ claw@163.228.243.161:/opt/mvp-deployer/
ssh claw@163.228.243.161 'pm2 restart mvp-deployer && pm2 status mvp-deployer'
```

改了 `ecosystem.config.js` 或启动 env：必须 `pm2 delete + pm2 start --update-env`，restart 不重读 env：

```bash
set -a; source ~/.credentials/.env; set +a
pm2 delete mvp-deployer
pm2 start ecosystem.config.js --update-env   # ← 关键
pm2 save
```

**加新 ecosystem env 字段**时（不只 rotate 已有 key）：光 delete+start 还不够。PM2 跟 `~/.pm2/dump.pm2` 缓存旧 env 合并，新 key 进程拿 undefined。必须叠 `--update-env`。

验证（不打值）：
```bash
PID=$(pm2 jlist | jq '.[]|select(.name=="mvp-deployer").pid')
sudo cat /proc/$PID/environ | tr '\0' '\n' | grep <NEW_KEY>=
```

🔥 **铁律**：deployer 自身**只能** ssh+rsync+`pm2 delete && pm2 start`。**禁止当普通 app 通过自己 `/api/deploy` 部署**——污染 `/opt/mvp-apps/`、tasks.json 留垃圾、PM2 中途 kill 自己导致 task 死锁。

误操作清理：
```bash
ssh claw@163.228.243.161 'rm -rf /opt/mvp-apps/mvp-deployer && pm2 restart mvp-deployer'
# 手动从 /opt/mvp-deployer/data/tasks.json 里删 project=="mvp-deployer" 的记录
```

---

## 3. 平台层故障速查

| 症状 | 命令 |
|---|---|
| API 401（改了 ecosystem 后） | `pm2 delete mvp-deployer && pm2 start /opt/mvp-deployer/ecosystem.config.js && pm2 save` |
| 端口 9800 EADDRINUSE | `sudo fuser -k 9800/tcp; sleep 1; pm2 restart mvp-deployer` |
| 🔥 root pm2 影子守护抢端口 | `sudo pm2 delete all && sudo pm2 kill`（`fuser -k` 治标，daemon 几分钟复活） |
| EACCES 写 `/tmp/mvp-uploads` / `/opt/mvp-apps/<x>` | `sudo chown -R claw:claw /tmp/mvp-uploads /opt/mvp-apps/<project>` |
| SQLite `SQLITE_READONLY`（data/ 被 root 覆盖） | `sudo chown -R claw:claw /opt/mvp-apps/<project>/data && pm2 restart <project>`（预防：zip `-x 'data/*'`） |

诊断快查：
- 端口属主：`lsof -i :<port>` —— USER 列是 root 就是影子守护
- PM2 状态：`pm2 list && pm2 logs <name> --lines 50 --nostream`

---

## 4. Caddy 重复 `@id` 路由清理

### 症状

deploy API 报：
```
Caddy API POST .../routes → 400: indexing config: duplicate ID 'mvp-route-<project>' found at routes/N and routes/M
```
所有 redeploy 失败直到清理。

### 根因（2026-04-20 已修）

旧 `lib/caddy.js` `addRoute()` 用 `PUT /id/mvp-route-<project>`。**Caddy 的 PUT 是 insert，不是 replace**。每次 redeploy 追加重复 `@id`。Fix: PUT → PATCH。Backup `lib/caddy.js.bak`。**如果 rsync 旧分支盖了 lib/，记得重新应用 PATCH 改动。**

### 清理流程（已堆积时）

Caddy admin API 监听 `localhost:2019`，不暴露公网。

1. 列当前路由（服务器端）：
   ```bash
   curl -s http://localhost:2019/config/apps/http/servers/srv0/routes
   ```
   每项可能有 `@id` 和 `match[0].host`。

2. 识别同 hostname 的重复。保留 `@id == mvp-route-<project>` 的（canonical），删旧无 `@id` 的。

3. 按 array index 删：
   ```bash
   curl -X DELETE http://localhost:2019/config/apps/http/servers/srv0/routes/<INDEX>
   ```
   ⚠️ 每次 DELETE 后 index 移位。重新 list 或**从高 index 删起**。

4. 验剩一个 `@id` 的，重 deploy。

---

## 5. 从服务器恢复项目源码

本地丢源、`/opt/mvp-apps/<project>/` 还跑着时。

```bash
PROJECT=seenlens

# 0. 确认源真在（不是只剩 build 产物）
ssh claw@163.228.243.161 "ls /opt/mvp-apps/${PROJECT}/src 2>&1 | head"
# 看到 .tsx/.ts/.vue/.py 才继续；只有 dist/ 放弃，从 git 远端 / backup 找

# 1. 服务器打 tar（排产物 + deployer 元数据）
ssh claw@163.228.243.161 "cd /opt/mvp-apps/${PROJECT} && tar \
  --exclude=node_modules --exclude=dist --exclude=.next --exclude=build \
  --exclude=.deploy-manifest.json --exclude=.caddy-routes.json --exclude=metadata.json \
  --exclude=package-lock.json \
  -czf /tmp/${PROJECT}-src.tar.gz ."

# 2. 拉回 + init
scp claw@163.228.243.161:/tmp/${PROJECT}-src.tar.gz /tmp/
mkdir -p ~/projects/${PROJECT}
cd ~/projects/${PROJECT}
tar -xzf /tmp/${PROJECT}-src.tar.gz
git init -q && git add -A
git commit -q -m "initial: snapshot from /opt/mvp-apps/${PROJECT}"
```

之后**禁再直接编辑服务器 `/opt/mvp-apps/`**——本地 git 是 source of truth，走正常 `/api/deploy`。

---

## 6. Dashboard 本地 QA

改 `public/index.html` / WeChat dashboard login / Skill install panel 时。

### 启本地 server（throwaway dirs + dummy WeChat）

```bash
cd ~/projects/mvp-deployer
DEPLOYER_PORT=19803 \
DEPLOYER_APPS_DIR=/tmp/mvp-deployer-ui-apps \
DEPLOYER_UPLOAD_DIR=/tmp/mvp-deployer-ui-uploads \
AUTO_DEPLOY_STATE_FILE=/tmp/mvp-deployer-ui-auto.json \
AUTO_DEPLOY_DISABLE_SCHEDULE=true \
WX_GATEWAY_BASE=https://wxmsg.mvp.restry.cn \
WX_GATEWAY_APP_NAME=mvp-deployer \
WX_GATEWAY_SECRET=dummy \
DASHBOARD_ALLOWED_OPENIDS=dummy \
DASHBOARD_SESSION_SECRET=dummy \
node server.js
```

### 生成本地 login URL

```bash
node - <<'NODE'
const crypto = require('crypto');
const secret = 'dummy';
const q = { token: 'localvisual', openid: 'dummy', unionid: 'u', ts: String(Math.floor(Date.now()/1000)) };
q.sig = crypto.createHmac('sha256', secret)
  .update(`${q.token}|${q.openid}|${q.unionid}|${q.ts}`)
  .digest('hex');
console.log('http://127.0.0.1:19803/api/wx/finalize?' + new URLSearchParams(q).toString());
NODE
```

### `/api/status` data shape

```js
{
  project: "cspy",
  manifest: { project, type, port, host, deployedAt /* env never render */ },
  pm2: { status: "online", memory, cpu, uptime, restarts } || null,
  route: { hosts: ["cspy.mvp.restry.cn"], upstream: "127.0.0.1:3791" } || null,
  autoDeploy: { ... } || null
}
```

UI 必须 normalize：用 `p.pm2.status` 而不是顶层 `p.status`，否则全显 UNKNOWN。`.rollback` / `*.failed-*` / 无 manifest+pm2+route 的当 archived。**`manifest.env` 永远不渲染**。

### Dashboard sync-skill install 文档

```bash
SCRIPTS=${SYNC_SKILL_SCRIPTS:-$HOME/.claude/skills/sync-skill/scripts}
python3 "$SCRIPTS/pull.py" mvp-deployer
```
不要硬编码 `~/.hermes/skills/...`。`/skill.zip` / `/install-instruction` 已删，**永远不要恢复**。

---

## 7. 改 deployer 自身的不变式（self-maintenance）

### One-path deploy invariant

`POST /api/deploy` 必须保持单一异步路径：
- 永远返 `202 {taskId, status:'queued', statusUrl}`
- 不要再引入基于 `manifest.build` / 项目类型的 sync/legacy 分支
- 无 build 项目仍走 builder；build phase 在没 `manifest.build` 且没 `scripts.build` 时 skip log
- 保留同 project active-task `409` 保护

### Env invariant

`finalEnv` 是唯一 runtime env：
- merge: credentials prefix < vault < manifest.env
- 写 .env / PM2 / initOnce / postDeploy / 子 build 都拿同一份 sanitized `finalEnv`
- task log 只打 count + skipped key 名，**永不打 value**

### preserveData copy pitfall

保留嵌套目录（如 `public/uploads`）时，**绝不**直接 `cp -a old/public/uploads new/public/uploads`——dest 已存在 → `new/public/uploads/uploads/...`。

正确：
1. normalize（`false`→none / `true`/unset→`['data']` / array→过滤相对路径）
2. `path.resolve` src+dest 并断言都在各自 root 内
3. dest 已存在 → 先删
4. `mkdir -p dirname(dest)`
5. copy

加 fixture 测试：old + new 都有 `public/uploads`，断言无 `uploads/uploads` 嵌套。

### deployer self-change 验证

```bash
cd ~/projects/mvp-deployer
node --check server.js deploy.config.js ecosystem.config.js
for f in lib/*.js; do node --check "$f" || exit 1; done
npm test
git diff --stat && git status --short
python3 -m py_compile ~/.hermes/skills/devops/mvp-deployer/scripts/deploy.py
```

Dashboard UI / WX login / install-instruction 改动 → 加跑 §6 本地 QA。

⚠️ WX finalize `ts` 可能 ms 或 sec 时间戳，`verifyWxFinalize` 必须两种都接受，保 ±5 分钟 skew，HMAC 算原始 `ts` 字符串。

---

## 8. 安全 Checklist（每次改主 SKILL.md 必跑）

- [ ] 文档无任何 token / API key / 密码（包括示例占位）
- [ ] 凭据只走 `~/.credentials/.env` 的 `MVP_DEPLOYER__TOKEN`
- [ ] 项目仓库无 `skill/` / 根 `SKILL.md` / `/skill.zip` / `/install-instruction`
- [ ] skill 更新已 sync-skill 发布：
  ```bash
  python3 ~/.hermes/skills/sync-skill/scripts/publish.py ~/.hermes/skills/devops/mvp-deployer -m "publish"
  ```
- [ ] 指纹扫描无泄漏：
  ```bash
  grep -RIf ~/.credentials/secret-fingerprints.txt ~/.hermes/skills/devops/mvp-deployer \
    && echo "❌ LEAK" || echo "✅ clean"
  ```
- [ ] `~/projects/mvp-deployer/.credentials` 在 `.gitignore`

---

## 9. Hermes terminal mask 注意

Hermes terminal 输出层 mask `Bearer ***` 等长 token 字面。如果生成的文件在 tool output 里看起来 syntax broken 因为 mask，**用 `python3 -m py_compile` 或读 raw file content 验证**，不要假设文件真坏了。

`-H @file` pattern（见主 SKILL.md §1）是绕这层 mask 的标准做法。
