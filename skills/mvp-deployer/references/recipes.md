# Recipes — Setup + 4 类 stack manifest

主 SKILL.md `§1 认证 + 标准流程` 跳到这里。**先跑 §0 Setup,再 §1 完整 deploy 脚本,再 §2-5 按 stack 抄 manifest**。

---

## §0. Setup(每次开新 shell / 派 CC 必先跑)

> **vault key 名以实际为准**:
> ```bash
> vault list | grep -i mvp-deployer   # 当前实际是 mvp-deployer/DEPLOYER_API_TOKEN
> ```
> 跑前确认一次,key 可能被改名(2026-06-30 真踩过)。
>
> **运行环境提示**:
> - ✅ CC (Claude Code) / Codex / 普通 zsh/bash shell: 直接抄,一次跑通(已实测)
> - ⚠️ Hermes Agent 自己的 `terminal` 工具: 必须把整段写文件再 `bash <file>` 跑——Hermes scrubber 会把命令行里 `vault get` 紧贴 token 输出的字面变成 `***` → bash 语法错。或用 `execute_code` 起 subprocess 绕开

```bash
# 1) 从门神(vault skill)取 token,sed 必洗 ANSI escape
#    (vault get 头部带 \x1b[F\x1b[K 控制码,塞 HTTP header 触发 400 bare control character)
TOKEN=*** get mvp-deployer/DEPLOYER_API_TOKEN | sed $'s/\x1b\\[[0-9;]*[A-Za-z]//g' | tr -d '\r\n ')
[ ${#TOKEN} -eq 64 ] || { echo "TOKEN 长度异常 (${#TOKEN}, 应该 64), 检查 vault"; return 1; }

# 2) Authorization header 写临时文件——curl 用 -H @file 而不是 -H "Authorization: Bearer $TOKEN"
#    (Hermes scrubber 会把命令行 / .sh 文件里 'Bearer <长 hex>' 字面 mask 成 ***,真改写落盘;
#     CC / 普通 shell 无此问题,但模板统一不出错)
HDR=$(mktemp); chmod 600 "$HDR"
printf '%s %s\n' 'Authorization: Bearer' "$TOKEN" > "$HDR"

# 3) Base URL + 自检
export ENDPOINT=https://deploy.mvp.restry.cn
curl -sS -H @"$HDR" "$ENDPOINT/api/status" | jq '.projects | length' || { echo "auth 失败"; return 1; }
```

> **绝对不要** 把 `Bearer $TOKEN` 字面写进 .sh / write_file / patch 内容——Hermes scrubber 会把整段真改写成 `***` 落盘,看起来 shell 跑通其实 curl 发的是 字面被 mask 后的 `Authorization: ***`` → 401。永远走 `printf` 拼到 file + `-H @file`。

---

## §1. 完整 deploy 脚本(端到端,从 zip 到验真)

假设 `$HDR` / `$ENDPOINT` 已按 §0 准备好。

```bash
P=my-app                                       # 项目名
HOST=$P.mvp.restry.cn                          # 公网域名

# 1) 预检 — 拿可用端口、看 host 是否被占
curl -sS -H @"$HDR" "$ENDPOINT/api/inventory" | jq '{port_suggested: .ports.next_suggested, ports_used: .ports.used, hosts: .hosts, base_domain: .baseDomain}'

# 2) 打 zip (必 zip 禁 tar.gz)
cd ~/projects/$P
zip -rq /tmp/$P.zip . \
  -x 'node_modules/*' '.git/*' '.next/*' 'dist/*' '*.log' \
     'data/*' '.env' '.env.local' '.env.development' '.env.production'

# 3) 写 manifest 模板(secret 用 vault://<p>/<KEY> 占位,**客户端**用 `vault inject` 渲染成真值再 POST)
#    ⚠️ deployer 主机故意不装 vault CLI——secret 不应该在那台机器上有解密能力。
#    `vault://` 占位必须在本机渲染完,POST 上去的是真值明文(deployer 端会把 .env 落盘时打 redacted log)。
#    忘了 inject 直接 POST 占位 → deployer 把字面字符串写进 .env → Prisma/任何读 DATABASE_URL 的代码直接炸。
cat > /tmp/$P-manifest.tpl.json <<'EOF'
{
  "project": "my-app",
  "type": "node",
  "port": 3801,
  "host": "my-app.mvp.restry.cn",
  "build": "pnpm install --no-frozen-lockfile && pnpm prisma generate && pnpm build",
  "run": "pnpm start",
  "smokeDisabled": true,
  "env": {
    "DATABASE_URL": "vault://my-app/DATABASE_URL",
    "NEXTAUTH_SECRET": "vault://my-app/NEXTAUTH_SECRET",
    "NEXTAUTH_URL": "https://my-app.mvp.restry.cn",
    "AUTH_TRUST_HOST": "true",
    "PORT": "3801"
  },
  "postDeploy": "pnpm prisma migrate deploy"
}
EOF
vault inject /tmp/$P-manifest.tpl.json > /tmp/$P-manifest.json
rm /tmp/$P-manifest.tpl.json   # 模板带 vault:// 不敏感,但勤打扫

# 4) POST /api/deploy (manifest 必 string 不是 @file)
TASK=$(curl -sS -X POST "$ENDPOINT/api/deploy" \
  -H @"$HDR" \
  -F "file=@/tmp/$P.zip" \
  -F "manifest=$(cat /tmp/$P-manifest.json)" | jq -r .taskId)
echo "taskId=$TASK"
rm /tmp/$P-manifest.json       # 渲染后的 .json 含真 secret,部署完立删

# 5) 轮询到 succeeded / failed
while true; do
  S=$(curl -sS -H @"$HDR" "$ENDPOINT/api/deploy/tasks/$TASK" | jq -r .status)
  echo "$(date +%T) $S"
  [[ $S == succeeded || $S == failed ]] && break
  sleep 5
done

# 6) 验真 bundle hash (光看 succeeded + curl 200 不够, silent-fail 必踩)
LIVE=$(curl -fsSL "https://$HOST/" | grep -oE 'index-[A-Za-z0-9]+\.(js|css)' | head -1)
DISK=$(curl -sS -X POST "$ENDPOINT/api/exec/$P" -H @"$HDR" -H 'Content-Type: application/json' \
  -d '{"command":"ls .next/static/chunks/*.js dist/assets/*.{js,css} 2>/dev/null | head -1"}' | jq -r .stdout)
echo "live=$LIVE"
echo "disk=$DISK"
[[ "$LIVE" == *"$(basename $DISK | cut -d. -f1)"* ]] && echo "✅ bundle 一致" || echo "❌ silent-fail, 看 pitfalls.md silent-fail 节"
```

phase 序列: `snapshot → extract → preserveData → envLoad → install → prisma → build → swap → pm2 → caddy → [initOnce] → [postDeploy] → smoke → done`

---

## §2. 决策树

```
项目根 package.json 有 next?      → §3 Next.js
项目根有 vite.config.*?            → §4 Vite SPA
全是静态 HTML/CSS/JS?              → §5 纯静态
Python (requirements.txt/pyproject)?→ §6 Python
其他 Node?                         → §7 通用 Node
```

---

## §3. Next.js + Prisma/Drizzle + pnpm(最常见)

```jsonc
{
  "project": "my-app",
  "type": "node",
  "port": 3801,
  "host": "my-app.mvp.restry.cn",
  "build": "pnpm install --no-frozen-lockfile && pnpm prisma generate && pnpm build",
  "run": "pnpm start",
  "smokeDisabled": true,                                    // 铁律 5: Next.js cold-start 必假 502
  "env": {
    "DATABASE_URL": "vault://my-app/DATABASE_URL",          // 客户端 vault inject,POST 前渲染成真值;deployer 端无 vault CLI
    "NEXTAUTH_SECRET": "vault://my-app/NEXTAUTH_SECRET",
    "NEXTAUTH_URL": "https://my-app.mvp.restry.cn",
    "AUTH_TRUST_HOST": "true",
    "PORT": "3801"                                          // 铁律 3: 显式注入,manifest.port 不会自动注
  },
  "postDeploy": "pnpm prisma migrate deploy"                // 必须幂等 (v2 起不再自动 migrate)
}
```

⚠️ **铁律 2**:这个 env 列表对**新项目**第一次 deploy 是完整的;**redeploy 老项目**时如果有更多 env(用户后加的),只传这 5 个会把其他抹掉。redeploy 老项目必走 `pitfalls.md` 的 `redeploy-env-wipe`(先抓全量再回灌)。

**强制 checklist(不过这关 deploy 必挂)**:

- [ ] `.npmrc` 有 `registry=https://registry.npmmirror.com`(npmjs 国内 ETIMEDOUT)
- [ ] `.npmrc` 有 `minimum-release-age=0`(pnpm 10 默认拒新包)
- [ ] 删 `pnpm-workspace.yaml`(pnpm 10 自动重建一份没 `packages:` 字段的,CI 守门)
- [ ] **不要** `puppeteer`,必须 `puppeteer-core` + `@puppeteer/browsers`(见 `pitfalls.md puppeteer-core`)
- [ ] DATABASE_URL **不带** `?schema=public`(drizzle/postgres-js 不认)
- [ ] `manifest.build` **不能** chain 多条命令——deployer 只跑 `pnpm install --no-frozen-lockfile && pnpm run build`,其他放进 package.json `scripts.build`
- [ ] redirect 不要用 `req.url` 当 base,要用 `process.env.NEXTAUTH_URL`(Caddy 反代后 req.url host=`localhost:port`)
- [ ] `.env.local` 必排除(生产优先级高于 .env,会覆盖真值)

---

## §4. Vite SPA(React/Vue/Svelte/Solid)

```jsonc
{
  "project": "my-spa",
  "type": "node",
  "port": 3816,
  "host": "my-spa.mvp.restry.cn",
  "build": "npm install && npm run build",
  "run": "npm start",
  "preserveData": false,
  "smokeDisabled": true,
  "env": { "PORT": "3816" }
}
```

**package.json 必改 3 处(不改必挂)**:

```json
{
  "scripts": {
    "start": "sirv dist --host 0.0.0.0 --port ${PORT:-3816} --single"
  },
  "dependencies": { "sirv-cli": "^3.0.0" }
  // ❌ 删 "type": "module" (deployer 生成的 ecosystem.config.js 是 CJS,冲突直接挂)
}
```

- **为什么不能用 `vite preview`**:dev 工具,PM2 子进程下不可靠读 PORT、静默退出、拒绝非 localhost Host header
- **为什么 sirv-cli 必须在 dependencies**:`npm ci` 生产跳过 devDeps,放 devDependencies 就 `command not found`
- **为什么 `--single`**:SPA 路由 fallback,所有未命中文件返回 index.html,react-router 必需

---

## §5. 纯静态

```jsonc
{
  "project": "my-static",
  "type": "static",
  "port": 3850,
  "host": "my-static.mvp.restry.cn",
  "run": "sirv . --host 0.0.0.0 --port ${PORT:-3850}"
}
```

不需要 build。zip 根目录直接放 `index.html` + assets。

---

## §6. Python

```jsonc
{
  "project": "my-py",
  "type": "python",
  "port": 3870,
  "host": "my-py.mvp.restry.cn",
  "build": "pip install -r requirements.txt",
  "run": "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-3870}",
  "env": { "PORT": "3870" }
}
```

---

## §7. 通用 Node(非 Next.js / 非 Vite)

```jsonc
{
  "project": "my-node",
  "type": "node",
  "port": 3880,
  "host": "my-node.mvp.restry.cn",
  "build": "pnpm install --no-frozen-lockfile",
  "run": "pnpm start",
  "env": { "PORT": "3880" }
}
```

---

## §8. 共用片段

### 钩子(按需加到 manifest)

```jsonc
{
  // 仅首次跑 (标记 .deployer-initialized 写项目根,下次跳过)
  "initOnce": "node scripts/seed.js",
  "initOnceTimeoutMs": 600000,

  // 每次 deploy 都跑,必须幂等 (migrate deploy / upsert SQL,不是 INSERT/CREATE TABLE)
  "postDeploy": "pnpm prisma migrate deploy",
  "postDeployTimeoutMs": 300000
}
```

### preserveData

```jsonc
"preserveData": ["data", "public/uploads"]   // 默认 ["data"]; false=不保留; 数组=显式相对路径
```

### smoke

```jsonc
"smokePaths": ["/health"],     // 永远先探 "/", 这里加额外路径
"smokeDisabled": false         // 紧急绕过 (Next.js 类项目设 true)
```

### 建库(部署前一次性,幂等)

```bash
curl -sS -X POST "$ENDPOINT/api/db/provision" \
  -H @"$HDR" -H "Content-Type: application/json" \
  -d '{"project":"my-app"}' | jq
# 返回 { user, database, password, connectionString }
# password 一次性返回, 必须立刻 vault add my-app/DATABASE_URL --from-stdin (见 vault skill)
```

库名/用户名会被 sanitize 成 `[a-z0-9_]`(`my-app` → `my_app`),以响应里的 `database` / `user` 字段为准。
