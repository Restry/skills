# no-per-project-script — 同项目部 ≥ 2 次没固化脚本

铁律 6 的落地。

## 症状

- 同一个 MVP 项目部第 3、5、N 次，每次现凑 `curl -X POST /api/deploy -F file=@... -F manifest=...` 一大坨命令
- 每次都踩至少一个老坑：manifest.env 全量覆盖丢 key / zip 太大 MulterError / python json.loads 解 task response 挂在 control char / 忘 smokeDisabled 被 Next.js cold-start 假 502 rollback
- 用户开始烦躁："这个部署已经这么多次了，为什么还老报错？"

## 根因

**部署这件事在同一个项目上是稳定 recipe**——manifest 定值（project/host/port/build/run）、env 回灌流程、zip 排除清单、smoke 路径，一次跑通就该固化。凭印象每次现凑等于每次重新走一遍学习曲线。

## 修法（一次性）

**从 `templates/deploy-prod.sh` 复制到项目 `scripts/deploy-prod.sh`，改 4 处**：

```bash
PROJECT="your-app"          # deployer 项目名
HOST="your.mvp.restry.cn"   # 公网 host
PORT=3xxx                   # 进程端口
EXTRA_ZIP_EXCLUDE=(         # 项目专属 legacy（可空）
  # 'public/prompts/[0-9]*'    # image-studio 的 legacy 数字目录
)
```

如无 Prisma → 改 `POST_DEPLOY=":"`。有 uploads dir → `PRESERVE_DATA='["data","public/uploads"]'`。

**验证** `./scripts/deploy-prod.sh --dry-run`——脚本只打 zip + 生 manifest 不上传，看 env keys 数、zip size、manifest 内容都对再真跑。

**commit + push**：把脚本 + `scripts/deploy-prod.README.md` 一起进仓，README 讲清 9 步做什么 + 内置踩坑对照表。以后 CC / agent / 自己跑同一份，不再现凑。

## 模板已内置的坑（都是铁律 1-5 落地）

| 内置行为 | 对应铁律/pitfall |
|---|---|
| `curl POST /api/exec cat .env` 抓现网 env 回灌 | 铁律 2 · redeploy-env-wipe |
| zip 默认排 `pnpm-workspace.yaml` | pnpm-workspace |
| zip 默认排 `.env*` | env-local-override |
| `smokeDisabled: true` 硬编码 | 铁律 5 · smoke-cold-start |
| `jq` 解 task response（不用 python） | 环境防御——env value 常含 ANSI/\r control char |
| `-H @<mktemp>` 传 Bearer token | scrubber-bearer |
| `preserveData: ["data","public/uploads"]` | 数据保留默认 |
| trap 删临时 manifest（含明文 env） | 卫生 |
| `--dry-run` 支持 | 上线前自查 |
| 部完从 `/api/status` 拉 pm2 状态 | silent-fail 兜底 |

## 反模式

- ❌ 每次现凑 curl 一大坨——第 3 次就该固化
- ❌ 只固化 `deploy.sh` 但不写 README 讲坑——脚本注释里写清 9 步做什么和为什么
- ❌ 脚本硬编码 token 明文——从 `~/.credentials/.env` source
- ❌ 项目专属 legacy 排除写死在通用位置——用 `EXTRA_ZIP_EXCLUDE` 数组扩展点
- ❌ 部完不验 smoke——脚本尾部必 curl 几个 URL 打 http code

## 参考落地

`~/projects/image-studio/scripts/deploy-prod.sh`（commit 1e6f470，2026-07-02）——同一份 curl 命令凑到 N 次终于收进项目里，dry-run 一次通过。

---

## 血案 2026-07-02 image-studio — 监控脚本挂了 ≠ 部署失败

**症状**：派 background bash 上传 zip + 轮询 task，脚本用了 `python -m json.tool` / `python -c "json.load..."` parse `/api/deploy/tasks/<id>` 响应。task response 的 `logs[]` 里含 env value（含 ANSI escape / \r control char），python `JSONDecodeError: Invalid control character at char 174`。**内层 loop 每 5s 都 raise 空捕获**，status/phase 打印成空字符串，看起来任务卡死永远不出。

**我做了什么错**：以为 deploy 真挂了，`process kill` 干掉那个 loop 然后重发，结果又是同样 python parse 挂 → 又循环 → 又 kill。**整个过程 deploy 一次就成功了**，我瞎在那儿 debug 监控包装。

**如何识别**：`process kill` 那个 loop 后，直接查 deployer 最近 5 个 task：

```bash
set -a; source ~/.credentials/.env; set +a
HDR=$(mktemp); printf 'Authorization: Bearer %s\n' "$MVP_DEPLOYER__TOKEN" > "$HDR"
curl -sS -H @"$HDR" 'https://deploy.mvp.restry.cn/api/deploy/tasks?limit=5' \
  | jq 'if type=="array" then .[0:5] else .tasks[0:5]? end
      | .[] | {id, project, status, phase, startedAt, finishedAt}'
rm -f "$HDR"
```

**关键辨认**：
- ✅ 最新 task status=`succeeded` finishedAt 是几分钟前 → **部署已成功**，只是我的监控脚本瞎眼，直接跑 smoke 验证
- ❌ 最新 task status=`failed` → 真失败，看 `logs[-15:]` 找根因
- ❌ 最新 task status=`running` phase 长时间不进 → 才是真卡死，走 admin runbook 的 zombie task 解锁流程

**反射动作**：任何时候 "看不到 deploy 状态 / 监控脚本报错 / 轮询无响应" — **先 kill 掉自己的监控循环，再 curl /api/deploy/tasks?limit=5 + jq**，别再重发 deploy（可能已经跑到第 2 个 succeeded 了，重发浪费 30-90s 队列 + 可能撞并发保护 409）。

**根治**：这就是为什么 `templates/deploy-prod.sh` **强制用 jq 不用 python** parse task response——python 对 control char 严格失败，jq 直接吃掉。任何"我自己现凑一段监控 loop"的冲动都要按住，直接跑固化脚本。

**跟铁律 6 的关系**：这次栽栽在**没先用固化脚本就现凑监控 loop**。铁律 6 的一半意义就在于：脚本已经把这类坑内嵌了，别再 side-step。
