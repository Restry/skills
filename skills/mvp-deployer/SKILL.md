---
name: mvp-deployer
description: Deploy Node/Python/Vite/Next.js/static projects to MVP Deployer at deploy.mvp.restry.cn. Async pipeline, zip upload, Caddy auto-routing, shared PG, smoke + rollback. Triggers — 发布/部署/上线/deploy/publish/redeploy/MVP/restry/mvp-deployer.
---

# MVP Deployer

自建多项目部署 PaaS。主文档讲铁律 + 入口,完整 setup+deploy 脚本 / manifest 模板 / 报错根因 → references。

## 🚨 6 条铁律(少踩 80% 坑)

1. **永远异步**。POST 返 `taskId`,轮询 `/api/deploy/tasks/<id>` 到 `succeeded`,失败自动 rollback。
2. **manifest.env 全量覆盖 .env**——只传一个 key 也会重写整份。redeploy 老项目**必须先抓全量再回灌**(`POST /api/exec/<project> {command:"cat .env"}` 拉现网真值,jq parse 后合到 manifest.env)。优先级 `manifest.env > vault > <PROJECT>__ 前缀`。⚠️ **deployer 主机故意不装 vault CLI**(secret 不应该在那台机器解密),`vault://` 占位必须**客户端**用 `vault inject` 渲染成真值再 POST;直接塞占位 → 字面字符串落 .env → Prisma 等读环境的代码立刻炸。
3. **manifest.host 必填**;**port 不自动注 PORT env**,进程读 PORT 必须显式 `env.PORT`。
4. **install/build 无 watchdog**——`pnpm install` 卡死永远不退,整队列锁死。99% 触发源是 `puppeteer` 包拉 chrome(必须 `puppeteer-core`)。
5. **smoke 太早**(PM2 起 ~70ms 后立刻 GET /)。Next.js/NextAuth/中间件重的项目 cold-start 300ms+ 必假 502 → rollback,加 `"smokeDisabled": true`。
6. **同项目部 ≥ 2 次必固化 `scripts/deploy-prod.sh`**(2026-07-02 image-studio 栽:同一套 curl+manifest+回灌 env 现凑到第 N 次还踩 env 全量覆盖 / 125M zip / python control-char parse 挂)。**模板** `templates/deploy-prod.sh` 已备好——改 4 处(`{{PROJECT}}` / `{{HOST}}` / `{{PORT}}` / `EXTRA_ZIP_EXCLUDE`)即可用。所有铁律 1-5 都编码进模板:自动抓现网 env 回灌 / 排 legacy 目录 / smokeDisabled=true / 用 jq 解 task response 避 python control char / dry-run 支持。CC / agent / 自己以后都跑同一份脚本,不再现凑 curl。首次已实装:`~/projects/image-studio/scripts/deploy-prod.sh`(commit 1e6f470)。

## §1. 认证 + 标准流程

**日常 redeploy 必走 `templates/deploy-prod.sh` 复制到项目 `scripts/deploy-prod.sh`**——脚本已经处理好 env 回灌 + zip 排除 + smoke + 用 jq 解 task response,现凑 curl 只会踩老坑(见 references/no-per-project-script.md 血案)。

Token: `vault get mvp-deployer/DEPLOYER_API_TOKEN` 或 `~/.credentials/.env` 的 `MVP_DEPLOYER__TOKEN`。Base: `https://deploy.mvp.restry.cn`。

`scripts/deploy.py` = Python 一键版(通用 fallback,新项目 / 一次性 / 项目脚本还没固化时)。⚠️ `--preserve-env` 无 SSH 时静默失效抹空 .env——bash 模板不用这个 flag,而是走 `POST /api/exec cat .env` 抓真值回灌。

## §2. Endpoints

```
POST   /api/deploy                       multipart: file=@zip + manifest=<JSON string,禁@file>
GET    /api/deploy/tasks/<id>            (不是 /api/tasks/)
GET    /api/inventory               ⭐   预检 ports/hosts
GET    /api/status                       项目状态
GET    /api/logs/<name>?lines=N          PM2 日志
POST   /api/exec/<project>          ⭐   远程跑命令 (替代 SSH)
POST   /api/db/provision            ⭐   共享 PG 建库
DELETE /api/deploy/<name>?removeFiles=true
POST   /api/webhooks/github              HMAC,见 auto-deploy.md
```

## §3. 排错三板斧

`inventory`(配置对吗)→ `logs`(PM2 报啥)→ `exec`(cat .env / pm2 env / ls)。

**⚠️ "看不到状态" ≠ "部署失败"** — 监控 loop 报错 / 卡住 / 没响应,**先 kill 自己的 loop 再查任务真实终态**,别重发 deploy:

```bash
set -a; source ~/.credentials/.env; set +a
HDR=$(mktemp); printf 'Authorization: Bearer %s\n' "$MVP_DEPLOYER__TOKEN" > "$HDR"
curl -sS -H @"$HDR" 'https://deploy.mvp.restry.cn/api/deploy/tasks?limit=5' \
  | jq 'if type=="array" then .[0:5] else .tasks[0:5]? end
      | .[] | {id, project, status, phase, startedAt, finishedAt}'
rm -f "$HDR"
```

最新 task `succeeded` → deploy 早成功了,直接跑 smoke。detail 见 `references/no-per-project-script.md` "血案 2026-07-02"。

## §4. 角色边界

HTTPS API 全套搞定。SSH `claw@163.228.243.161` 只维护者有,平台层故障(zombie task / Caddy 重复 @id / 端口被 root pm2 抢 / SQLite readonly / EACCES /tmp uploads / rsync 更新 deployer 自身) 走 SSH 手动,看到这些症状**停手让 daddy 上**,不要在这份 skill 里 loop debug。

## §5. 配套文件

- `scripts/deploy.py` — 通用一键 Python(新项目 / 一次性 deploy)
- `templates/deploy-prod.sh` ⭐ — 项目专属脚本模板(第 2 次部署必固化到项目 `scripts/deploy-prod.sh`)
- `references/no-per-project-script.md` ⭐ — 铁律 6 完整落地 + "监控脚本挂了 ≠ 部署失败" 血案 2026-07-02

下线 → `mvp-project-decommission` skill。
