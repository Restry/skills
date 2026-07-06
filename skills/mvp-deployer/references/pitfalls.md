# Pitfalls — 按症状索引

按 task log / curl response / PM2 log 的错误字面字符串查。每条都是真踩过的事故，根因 + 修法。

## 速查表

| 症状（错误字面字符串） | 章节 |
|---|---|
| `MulterError: Unexpected field` | upload |
| `end of central directory record signature not found` | upload |
| `MulterError: File too large` | upload |
| `task status=running` 永远不动 + 新 deploy queued | zombie-task |
| `puppeteer postinstall ... Skipping Firefox` 之后卡死 | puppeteer-core |
| smoke `(<200ms)` 失败立即 rollback | smoke-cold-start |
| `packages field missing or empty` | pnpm-workspace |
| `ETIMEDOUT registry.npmjs.org` | npm-mirror |
| `within the minimumReleaseAge cutoff` | pnpm10-release-age |
| `unrecognized configuration parameter "schema"` | drizzle-postgres |
| `drizzle-kit applying migrations...` 不动 | drizzle-migrate |
| `Environment variable not found: DATABASE_URL` (Prisma P1012) | env-missing |
| `Invalid project directory ... /-p` | pm2-port-arg |
| `ReferenceError: module is not defined` (PM2 phase) | esm-cjs-conflict |
| Caddy `duplicate ID 'mvp-route-<x>'` | admin.md |
| pm2 online + curl 200 但页面是旧 build | silent-fail |
| 重 deploy 后 OAuth/扫码跳 `https://localhost:<port>` | nextjs-req-url |
| 改了 .env / 凭据但 PM2 仍读旧值 | pm2-env-cache |
| `40125 invalid appsecret` / API 401 但 .env 看着对 | env-local-override |
| `Database '<name>' does not exist` / Prisma P1000 | shared-pg-password-drift |
| `403 ... yourIp: x.x.x.x` | ip-allowlist |
| `curl ... Bearer $TOKEN` 返 401（token 长度对） | scrubber-bearer |
| `<project>__KEY` 前缀 env 被冲掉 | prefix-overwrite |
| 部署后某历史业务数据全没了 | db-name-shell-escape |
| `Command "@scope/pkg" not found` | pnpm-exec-bin |
| `Cannot load module "sharp"` / `Cannot find module 'esbuild'` | pnpm-built-deps-ignored |
| `/api/exec` 跑的 script 读不到 env | exec-env-not-sourced |
| zsh `git add app/[slug]/...` → no matches | zsh-glob-bracket |

---

## upload — zip 上传相关

**`MulterError: Unexpected field`**：multer 字段名必须是 `file`，不是 `archive`/`tarball`。
**`end of central directory record signature not found`**：传了 tar.gz，必须 zip。
**`MulterError: File too large`**：上限 ~100MB。处理：(a) 排除非必要资源重打 zip；(b) 两次部署（第一次代码骨架 + preserveData，第二次大资源）；(c) `/api/exec git clone` 让服务器自己拉。

zip exclude 例（zsh 不展开 glob 给 zip）：
```bash
zip -rq out.zip . -x 'node_modules/*' '.git/*' 'public/prompts/[0-9]*'
# 或写到文件
ls dir | grep -v keep | sed 's|^|dir/|;s|$|/*|' > /tmp/x.txt
zip -rq out.zip . -x@/tmp/x.txt
```

---

## zombie-task — task 永远 running

**症状**：task `status=running phase=install` 几分钟没动；重发 POST /api/deploy 返回**同一个** taskId；新 task 一直 queued；DELETE /api/deploy/<name> 返 undeployed 但 task 还 running；POST /api/deploy/tasks/<id>/cancel 全 404。

**根因**：deployer 没给 install/build/postDeploy 阶段子进程加 watchdog，也没暴露 cancel API。卡死的子进程占着串行队列，全堵。最常触发：puppeteer 拉 chrome 黑洞（看下一节）。

**普通 agent 修法**：
1. 停手别再发部署
2. 查 task logs 最后一条是不是 `puppeteer postinstall` / 网络下载字眼
3. 找 Daddy，明确说："X task 卡 install 阶段 puppeteer 拉 chrome，需要 SSH kill 子进程"
4. **本地把代码改成 puppeteer-core**（下一节），不然解锁后再 deploy 还是卡

**Daddy 解锁流程** → `references/admin.md` 的 zombie-task 章节。

---

## puppeteer-core — 项目用 puppeteer 必死

**症状**：install phase 卡在
```
.../node_modules/puppeteer postinstall$ node install.mjs
.../node_modules/puppeteer postinstall: **INFO** Skipping Firefox download as instructed.
```
然后永远不动。

**根因**：`puppeteer` npm 包 postinstall 自动从 `storage.googleapis.com` 下 chrome ~150MB，国内 server 直连黑洞。`PUPPETEER_DOWNLOAD_BASE_URL` env 救不了——pnpm install 的 npm postinstall 子进程不一定继承 deployer 注入的 env。

**修**（强制）：

1. **package.json** 换包：
   ```jsonc
   "dependencies": {
     "puppeteer-core": "^25.2.0",
     "@puppeteer/browsers": "^2.10.0"
   }
   // 删 "puppeteer": "..."
   ```

2. **代码** `render.ts` 显式 executablePath：
   ```ts
   import puppeteer from "puppeteer-core";
   import { computeExecutablePath, Browser, detectBrowserPlatform } from "@puppeteer/browsers";
   const exePath = computeExecutablePath({
     cacheDir: process.env.PUPPETEER_CACHE_DIR!,
     browser: Browser.CHROME,
     buildId: process.env.PUPPETEER_CHROME_VERSION!,
     platform: detectBrowserPlatform()!,
   });
   await puppeteer.launch({ headless: true, executablePath: exePath, args: ["--no-sandbox"] });
   ```

3. **manifest.env**：
   ```jsonc
   "env": {
     "PUPPETEER_SKIP_DOWNLOAD": "true",
     "PUPPETEER_DOWNLOAD_BASE_URL": "https://cdn.npmmirror.com/binaries/chrome-for-testing",
     "PUPPETEER_CACHE_DIR": "/opt/mvp-apps/<project>/.cache/puppeteer",
     "PUPPETEER_CHROME_VERSION": "131.0.6778.204"
   },
   "preserveData": [".cache"]
   ```

4. **manifest.postDeploy** 装 chrome（走 npmmirror，幂等）：
   ```jsonc
   "postDeploy": "test -x \"$PUPPETEER_CACHE_DIR/chrome/linux-$PUPPETEER_CHROME_VERSION/chrome-linux64/chrome\" || node node_modules/@puppeteer/browsers/lib/cjs/main-cli.js install chrome@$PUPPETEER_CHROME_VERSION --path $PUPPETEER_CACHE_DIR"
   ```
   ⚠️ **不要** `pnpm exec @puppeteer/browsers ...`——包名 ≠ bin 名（bin 叫 `browsers`），pnpm exec 解析有 bug。直接 node 调脚本文件。

---

## smoke-cold-start — Next.js/NextAuth 必假 502

**症状**：task fail，phase log `smoke ... → 502 FAIL (70ms)`；自动 rollback；但你 sleep 5s 再 curl 又 200。

**根因**：deployer smoke 在 PM2 起来 ~70ms 后立刻 GET /，无 retry 无 readiness wait。Next.js 带 middleware 需要 300-500ms 才 listen TCP，smoke 抢跑必然 502。

**判定**：deploy log 里 smoke 是不是 `(<200ms)` 失败 → 100% timing。`(3000ms+)` 失败 → 真没起来，查别的。

**修**：manifest 加 `"smokeDisabled": true`，部署后自己 `sleep 10 && curl` 验。已知踩坑项目：menshen-ui（卡 41 天 100% fail）、任何 NextAuth / 中间件重的 Next.js。

**何时不该 smokeDisabled**：刚改完 schema（要靠 smoke 兜底 migration 失败）、第一次部署新项目（确认 host/port 路由对）。

---

## pnpm-workspace — `pnpm-workspace.yaml` 缺 packages

**症状**：install phase `ERROR packages field missing or empty`。

**根因**：pnpm 9+ 看到 `pnpm-workspace.yaml` 就当 monorepo，必须有 `packages:` 数组。脚手架经常只往里塞 `ignoredBuiltDependencies`。pnpm 10 更狠——`pnpm install` 后会**自动重建**这文件（没 packages 字段），你刚删它又出现。

**修**：
1. 删 `pnpm-workspace.yaml`，把内容挪到 `package.json` 的 `pnpm` 字段：
   ```json
   "pnpm": { "ignoredBuiltDependencies": ["sharp", "unrs-resolver"] }
   ```
2. 加 `.gitignore`：`pnpm-workspace.yaml`
3. CI / deploy 前 check：`[ -f pnpm-workspace.yaml ] && echo "DANGER rm it"`

---

## npm-mirror — registry.npmjs.org ETIMEDOUT

**症状**：install 一堆 `WARN GET https://registry.npmjs.org/xxx error (ETIMEDOUT)`。

**修**：项目根 `.npmrc`：
```
registry=https://registry.npmmirror.com
minimum-release-age=0
```

但 lockfile 里 `resolved:` URL 仍指 npmjs.org，所以 `--frozen-lockfile` 还会撞。`manifest.build` 用 `--no-frozen-lockfile` 让 pnpm 重新解析下载源（副作用：lockfile 会改写，本地 `pnpm install` 后 commit 新 lockfile 再发即可）。

---

## pnpm10-release-age — `within the minimumReleaseAge cutoff`

**根因**：pnpm 10 默认拒绝 < 14h 的新包。
**修**：`.npmrc` 加 `minimum-release-age=0`。

---

## drizzle-postgres — `unrecognized configuration parameter "schema"`

**根因**：`?schema=public` 是 Prisma 风格 query param，被当 PG 启动参数。`postgres@3.x` / drizzle runtime 不认。

**修**（连接前 strip）：
```ts
const url = process.env.DATABASE_URL.replace(/\?schema=[^&]+/, '');
```
或 .env 里别写 `?schema=public`（drizzle 默认 public schema）。

---

## drizzle-migrate — `drizzle-kit applying migrations...` 不动

**根因**：drizzle-kit 内部 spinner 在非 TTY 异常 + `?schema=public` 让连接挂起。

**修**：绕开 drizzle-kit，直接 node + postgres 跑 SQL，幂等：
```js
const postgres = require('postgres');
const url = process.env.DATABASE_URL.replace(/\?schema=[^&]+/, '');
const sql = postgres(url);
const fs = require('fs'), path = require('path');
const files = fs.readdirSync('src/db/migrations').filter(f=>f.endsWith('.sql')).sort();
for (const f of files) {
  const stmts = fs.readFileSync(path.join('src/db/migrations',f),'utf-8')
    .split('--> statement-breakpoint').map(s=>s.trim()).filter(Boolean);
  for (const s of stmts) {
    try { await sql.unsafe(s); } catch(e) {
      if (!/already exists|duplicate/.test(e.message)) throw e;
    }
  }
}
await sql.end();
```
manifest.postDeploy 改成 `node scripts/apply-migrations.js`。

---

## env-missing — Prisma P1012 DATABASE_URL not found

**根因**：manifest.env 漏传 + 服务器也没配 `<APP>__DATABASE_URL` 前缀。**或者** redeploy 时只传少数几个 env 把 .env 文件擦掉了。

**修**：见下一节 redeploy-env-wipe。

---

## redeploy-env-wipe — Redeploy 老项目 .env 被抹空(铁律 2 落地)

**症状**:第二次 deploy 后 prisma `P1012 url must start with postgresql://` / 业务 401 / 任何只读到 .env 一半字段的错。

**根因**:manifest.env 是**全量覆盖**——只传几个 key 也会重写整份 `.env`。或者 `scripts/deploy.py --preserve-env` 在没 SSH key 的 agent 上**静默 no-op**(`fetch_remote_env` 返 `{}`,只打 stderr),manifest.env 是空,部署完 .env 全空。

**标准 redeploy 流程**(先按 `recipes.md §0 Setup` 准备 `$HDR` / `$ENDPOINT`):

```bash
P=my-app    # 项目名

# 1) 抓服务器现有 .env(base64 绕 Hermes mask)
curl -sS -X POST "$ENDPOINT/api/exec/$P" -H @"$HDR" -H "Content-Type: application/json" \
  -d '{"command":"base64 -w0 .env 2>/dev/null || base64 .env | tr -d \"\\n\""}' \
  | python3 -c 'import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)["stdout"].strip()).decode())' \
  > /tmp/$P.env

# 2) sanity check
grep -c '^[A-Z_]*=' /tmp/$P.env       # ≥5 行
grep '^\*\*\*' /tmp/$P.env             # 命中说明字段被 mask(必须从门神补真值)

# 3) 从门神补 mask 字段(如有)
REAL=*** get $P/DATABASE_URL | sed $'s/\x1b\\[[0-9;]*[A-Za-z]//g' | tr -d '\r\n ')
sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$REAL|" /tmp/$P.env

# 4) 增量改 + 全量塞进 manifest.env 部署(bash while 展开成多个 --env KEY=VAL)
echo "NEW_KEY=value" >> /tmp/$P.env
ENV_ARGS=()
while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  ENV_ARGS+=("--env" "$line")
done < /tmp/$P.env
python3 ~/.claude/skills/mvp-deployer/scripts/deploy.py \
  --project "$P" --zip /tmp/$P.zip --port <PORT> --host <HOST> \
  --build '...' --run '...' "${ENV_ARGS[@]}"
```

⚠️ **`***` mask 路径区别**:`/api/inventory` / 部分 exec wrapper 返回的 .env **走 mask**(敏感字段变 `***`)。`/api/exec base64` 路径**不走 mask**,是裸 .env 内容。如果用了走 mask 的路径,必须从门神(`vault get $P/KEY`)取真值替换 `***` 行再回灌——否则真值被 `***` 覆盖。

**反模式**:
- ❌ `deploy.py --env /tmp/x.env`(`--env` 是 KEY=VAL 重复模式,不接文件路径)
- ❌ `--post-deploy`(这 flag 不存在)
- ❌ `--preserve-env`(agent / CI 静默 no-op)
- ❌ 只发**少数几个 env** 的 manifest 给老项目(必擦其他)

---

## pm2-port-arg — `Invalid project directory ... /-p`

**根因**：`pnpm start -- -p PORT` 在 PM2 下被吞参数（PM2 把 `-p` 当自己的 flag）。

**修**：用 PORT env，不要命令行传 `-p`：
```jsonc
"run": "pnpm start",
"env": { "PORT": "3795" }
```

---

## esm-cjs-conflict — `module is not defined`

**根因**：deployer 生成的 `ecosystem.config.js` 是 CJS，但项目 package.json 带 `"type": "module"` → Node 把所有 .js 当 ESM 解析。

**修**：从 package.json 删 `"type": "module"`。Vite/TS/React 没这字段照常工作（ESM 通过 .ts/.tsx 扩展名识别）。

---

## silent-fail — pm2 online + curl 200 但页面是旧 build

**症状**：deploy succeeded、PM2 online、curl 200，但渲染的还是上一版本。

**根因**：sirv-cli / http-server / 部分 express 启动时 bind 端口失败**不崩退出**，PM2 仍报 online，实际是僵尸进程。同 host:port 双 PM2 进程会出现这种 silent fail。常见触发：项目改名后老进程占着端口。

**验真**（光看 pm2 online + curl 200 不够，看 bundle hash）：
```bash
# 域名 vs 服务器 dist/
curl -fsSL https://<host>/ | grep -oE 'index-[A-Za-z0-9]+\.js'
curl -X POST .../api/exec/<project> -d '{"command":"ls dist/assets/*.js"}'
# hash 一致 = 真切过去；不一致 = 旧进程在服务
```

**修**：DELETE 旧项目 → pm2 restart 新项目让它重新 bind → 重验 hash。完整改名流程见下一节。

---

## project-rename — 项目改名

deployer **不支持 in-place rename**。流程：build-new → verify-port → delete-old。

```bash
# 1. 本地 mv + 改 package.json name + commit
# 2. 部 B（复用旧 host/port），返回 succeeded ≠ 在服务（见 silent-fail）
# 3. 必查端口 bind 在谁手里
curl -X POST .../api/exec/B -d '{"command":"pm2 list | grep -E \"A|B\"; ss -tlnp | grep :<PORT>"}'
# 4. DELETE A
curl -X DELETE ".../api/deploy/A?removeFiles=true"
# 5. 强 restart B 让它 bind
curl -X POST .../api/exec/B -d '{"command":"pm2 restart B && sleep 2 && ss -tlnp | grep :<PORT>"}'
# 6. bundle hash 验真
# 7. 清 .failed-* 残留
curl /api/status | jq -r '.projects[] | select(.project | startswith("A.failed-")) | .project' \
  | xargs -I{} curl -X DELETE ".../api/deploy/{}?removeFiles=true"
```

---

## nextjs-req-url — redirect 跳 `https://localhost:<port>`

**根因**：Caddy 反代到 `127.0.0.1:<port>`，Next.js `req.url` host 就是 `localhost:<port>`。`new URL(path, req.url)` 拼出来的 base 是 internal upstream。

**修**：route handler / server action 所有 redirect 用 `process.env.NEXTAUTH_URL` 或 `NEXT_PUBLIC_BASE_URL` 当 base：
```ts
const baseUrl = process.env.NEXTAUTH_URL ?? new URL(req.url).origin;
return NextResponse.redirect(new URL("/login?err=x", baseUrl));
```

---

## pm2-env-cache — 改了 .env 但 PM2 仍读旧值

**症状**：你改了 .env / 凭据，跑了 `pm2 restart --update-env`，PM2 内 env 仍是旧值。

**诊断**：
```bash
PMID=$(pm2 jlist | python3 -c 'import sys,json;[print(x["pm_id"]) for x in json.load(sys.stdin) if x["name"]=="<name>"]')
pm2 env $PMID | grep <KEY>
# 旧值 → 命中
```

**修**（delete + start，可靠）：
```bash
pm2 delete <name>
set -a && . ./.env && set +a
pm2 start "pnpm start" --name <name> --cwd /opt/mvp-apps/<name>
```
或 redeploy 一次（deployer PM2 阶段 atomic swap 会真正重新加载 env）。

---

## env-local-override — `.env.local` 静默覆盖 `.env`

**症状**：API 报 401 / invalid secret，但 `.env` 看着对、shell `set -a;. .env` 后 curl API 又能通。

**根因**：Next.js production runtime 优先级 `.env.local > .env.production > .env`。zip 带了 dev 用的 `.env.local`（含 placeholder/test secret），上传后 `preserveData` 留着 → Next.js 读 placeholder 值。

**诊断**：
```bash
curl -X POST .../api/exec/<p> -d '{"command":"ls -la .env*"}'
# 看到 .env.local 跟 .env 同时存在 → 命中
```

**修**（应急 + 根治）：
```bash
# 应急：服务器 mv .env.local .env.local.bak && pm2 restart
# 根治：zip 永远 -x '.env*'（保留 .env.example 因为不在排除列表）
```

---

## shared-pg-password-drift — Prisma P1000 但库存在

**症状**：deployer 跑 prisma migrate / 业务调 PG 报 P1000，但 `/api/exec` 内手跑 prisma 也 P1000；门神里项目副本的 DATABASE_URL 跟生产 PG 真值漂了。

**根因**：共享 PG 上 `image_studio` user 密码会被 deployer 不定期轮换。门神里已存项目副本 stale 的概率非常高。

**修**：建新项目 DATABASE_URL **永远从 packsmith 跳板的 .env 实时抓**：
```python
r = exec_cmd("packsmith", "grep ^DATABASE_URL .env | base64 -w 0")
url_full = base64.b64decode(r["stdout"].strip()).decode().split("=",1)[1].strip()
new_url = re.sub(r'(@127\.0\.0\.1:5432/)[^?]+', r'\g<1>NEW_DB', url_full)
```
顺手把门神里 stale 副本（nexora_wx_gw/echo 等）的 DATABASE_URL 用 packsmith 当前活密码重灌一次。

**为什么 packsmith**：它是 `image_studio` user + 有 createdb，密码是 deployer 注入的活密码。`cspy` 用户没 createdb 不行；`image-studio` 实际是 SQLite，env 里 postgresql:// 是历史残留。

---

## ip-allowlist — 403 + yourIp

**根因**：deployer 有应用层 IP 白名单 (`IP_ALLOWLIST` env)。本机出口 IP 可能不是直连 IP（走中间代理），必须信 server 报的 `yourIp`，不是本地 `ifconfig.me`。

**修**：把 `yourIp` 字段值给 Daddy 加白。

---

## scrubber-bearer — `curl ... Bearer $TOKEN` 401

**根因**:Hermes terminal scrubber 看到命令行 `Bearer <长 hex>` 字面,把后面 token 替换成 `***` —— 实际 curl 跑的是字面 `***`。`echo "$TOKEN"` 长度对(64)但 curl 仍 401。

**更阴险的子情况**:`write_file` / `patch` 内容里写 `Bearer $TOKEN` 紧贴长 hex 字面,Hermes scrubber 会**真改写落盘**(不是显示层 mask),`.sh` 文件磁盘内容真变成字面 `***`。看 vault skill pitfall 12。

**修**:走 `recipes.md §0 Setup` 标准模式 —— `printf` 拼到临时文件 + `curl -H @"$HDR"`。所有命令统一这个套路,CC / 普通 shell / Hermes 一套通用,不踩 scrubber。


## prefix-overwrite — `<PROJECT>__KEY` 前缀 env 被冲掉

**根因**：deployer 按 `<APP_UPPER>__*` 前缀从服务器 `~/.credentials/.env` 抽 env 写进 manifest.env。每次 redeploy 服务器侧 dotenv 被这份 manifest.env 重写，**之前手动追加的非前缀变量被静默冲掉**。

**修**：临时加的变量回填成带前缀形式，让脚本下次能抽到。

---

## db-name-shell-escape — 部署后业务数据"没了"

**症状**：prisma migrate deploy 跑成功 + smoke 200，但某段历史业务数据突然全空。

**根因**：PG 同名两份库——真名（`wx_gateway_pucs`）和含 escape 残留的脏名（`wx_gateway_pucs\`）。历史 DATABASE_URL 写 `db\?schema=public`（`\?` 防 zsh glob），某次 deploy 多解析一层把反斜杠当库名 createdb，跑了几个月。新 deploy escape 正确反而连上真名空库，migrate 从 0_init 全跑成功——数据其实在脏名库。

**修**：`/api/exec` 跑 `psql -l`（借 packsmith 跳板）看是不是有奇怪的双库名。把数据从脏库 pg_dump 出来 restore 到真库，drop 脏库。

---

## pnpm-exec-bin — `Command "@scope/pkg" not found`

**根因**：`pnpm exec` 找 bin 名，不是包名。`@puppeteer/browsers` 的 bin 是 `browsers`，pnpm exec 解析撞包名常常失败。

**修**：直接 `node node_modules/@puppeteer/browsers/lib/cjs/main-cli.js`，绕开 pnpm exec。

---

## pnpm-built-deps-ignored — `sharp` / `esbuild` native binary 装不上

**症状**: deploy 完 build 跑 `import sharp from 'sharp'` → `Could not load the "sharp" module ... binary at <path> is not found`；或 drizzle-kit generate 跑 `Cannot find module 'esbuild'`；或 lightningcss/tailwindcss-oxide 缺 native binary。

**根因**: 项目 `package.json` 的 `pnpm.ignoredBuiltDependencies` 把这些 native 包列了进去 → pnpm install 时跳过 postinstall (native binary 下载)。常见误用——刚 scaffold 项目时 pnpm 弹「ignore unsafe build scripts?」一时手贱选了 ignore。

**修法**: `package.json` 里把它们从 `ignoredBuiltDependencies` 挪到 `onlyBuiltDependencies`:

```jsonc
"pnpm": {
  "onlyBuiltDependencies": [
    "sharp", "esbuild", "@tailwindcss/oxide", "lightningcss",
    "@parcel/watcher", "better-sqlite3"
  ]
  // 删掉 "ignoredBuiltDependencies": [...sharp, esbuild...]
}
```

deploy 后验:
```bash
node -e "require('sharp')" && echo OK
```

---

## exec-env-not-sourced — `/api/exec` 子 shell 看不到 .env

**症状**: `/api/exec` 跑 `node -e "console.log(process.env.DATABASE_URL)"` → undefined,但 PM2 进程跑得好好的;manifest.env 明明也有这个 key。

**根因**: deployer `/api/exec` spawn 的 `bash -lc` 子 shell **不自动 source 项目 `.env`**。manifest.env 只走到 PM2 子进程,不走到 exec 调用。

**修法**: ad-hoc node script 要读 env,前缀 `set -a` 包围:
```bash
curl ... /api/exec/<project> -d '{"command":"set -a && . ./.env && set +a && node scripts/migrate.js"}'
```

或一次性 inline 传:
```bash
DATABASE_URL='postgres://...' node scripts/migrate.js
```

---

## zsh-glob-bracket — `git add app/a/[slug]/page.tsx` 报 no matches found

**根因**: zsh 默认 `nomatch` on,把 `[slug]` 当 glob 解析,匹配空 → 报错。

**修法**: 加单引号 `git add 'app/a/[slug]/page.tsx'`,或临时 `setopt +o nomatch`,或 `unsetopt nomatch`。

---

## 反模式（每条都踩过）

- ❌ 只发**少数几个 env** 的 manifest 给老项目 → 必擦其他 env
- ❌ `--preserve-env` 在没 SSH key 的环境用（agent / CI）→ 静默 no-op
- ❌ 删 `.env.local` 一次但不改部署脚本 → 下次 zip 又传上去
- ❌ DELETE A 后立即 deploy B（中间窗口）→ 失去"旧版还在线 + 新版独立验证"机会，应先建后删
- ❌ 改了 .env 只 `pm2 restart --update-env` 不验 `pm2 env <pmid>` → 缓存读旧值
- ❌ task 卡死后狂发部署 → 返同 taskId 不会绕开，先解锁再发
- ❌ 不验 bundle hash 就报"上线成功"→ silent-fail 类问题肉眼检不出
- ❌ 一遇问题就找 Daddy SSH → 99% 走 `/api/exec` 能解
