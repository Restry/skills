# In-repo Deploy Script — 项目部第 2 次以上必固化

## 触发点 (强反射)

任何 MVP 项目 (mvp-deployer 部署的 Next.js / Python / Vite / static site 等), **准备第 N 次凭手工 curl 组装 zip + manifest + POST /api/deploy 时, N ≥ 2 就要停下来**:

- 打开 `<项目>/scripts/deploy-prod.sh` — 有 → 直接跑
- 没有 → **不部**, 先固化脚本再部

爸爸 2026-07-02 原话:
> "这个部署已经这么多次了，为什么还老报错呢？我觉得很奇怪呀，这一次经验把它固化成一个脚本放到项目里不就行了吗？"

每次凭手工组 curl 会重踩:
- `manifest.env` 全量覆盖丢 key (skill §5 pitfalls 有, 但反射记不住)
- zip 太大 MulterError (每个项目对 exclude 目录清单不一样, 记忆里存不下)
- Next.js smoke 假 502 (要不要开 `smokeDisabled: true` 每次都想一遍)
- postDeploy prisma migrate 加了没加 (下次记不清)
- pnpm-workspace.yaml 不能进 zip (踩过, 但每次记不住)
- 用 python parse response 撞 env value 里的 control char → JSON parse 挂死循环

**固化脚本 = 把这些坑一次性写死在项目里, 下次任何 agent / 爸爸自己 / CC 全部跑同一条命令, 不会再各自现凑。**

## 已固化 app 清单 ⭐

**权威索引**——固化新 app 后**必回来加一行**,否则下次别人不知道有脚本又去现凑 curl。次序按 alphabet。

| App | 脚本路径 | Stack | 首次固化 | 上一次成功跑 | 备注 |
|---|---|---|---|---|---|
| `image-studio` | `~/projects/image-studio/scripts/deploy-prod.sh` | Next.js 15 + Prisma + PG | 2026-07-02 (commit `1e6f470`) | 2026-07-02 100s (commit `9ecddb6` 部 prod) | 排 `public/prompts/[0-9]*` legacy(125M→35M);postDeploy `prisma migrate deploy`;preserveData `data + public/uploads` |

<!-- 新 app 加行模板:
| `<app>` | `~/projects/<app>/scripts/deploy-prod.sh` | <stack> | YYYY-MM-DD (`<commit>`) | YYYY-MM-DD Ns (`<commit>`) | <特殊配置 / 踩过的坑> |
-->

**agent 反射动作**:接到 "部 X 到 prod" → 先看这张表 → 有就直接跑那个脚本 → 没有走 §"脚本必做的 9 件事" 固化流程。

## 脚本必做的 9 件事 (image-studio 版实测)

参考 `~/projects/image-studio/scripts/deploy-prod.sh` (2026-07-02 落地):

```
1. 前置检查      token / jq / zip / git 干净度
2. 拉现网 env    curl POST /api/exec/<project> -d '{"command":"cat .env"}'
3. 打 zip        排 node_modules/.next/.git/uploads/data + project-specific legacy
4. 生 manifest   project/type/port/host/build/run/env/postDeploy/preserveData/smokeDisabled
5. POST /api/deploy    上传 zip + manifest
6. 轮询 taskId   每 5s 拉 status, 换 phase 时打点, 失败打尾部日志
7. smoke         3-5 个核心 URL (200 / 3xx 都算 OK, 认证页会 307)
8. pm2 状态      /api/status 拿 pm2 状态 + restarts + memory
9. exit 0/1      成功 0, 失败 1 (给 CI / cron 用)
```

⚠️ **禁用 `python3 -c 'json.loads(sys.stdin)'` 解析 status/response**: env value 里常有 control char, python `raw_decode` 会抛 `JSONDecodeError` 死循环。**用 `jq`**, jq 对 control char 宽容。

⚠️ **`--dry-run` 支持**: 打 zip + 生 manifest 不上传, 用来验脚本本身不炸 + 看 zip 大小合理。

## 部署铁律 (脚本必内置)

| 铁律 | 怎么内置 |
|---|---|
| manifest.env 全量覆盖 → 必先 exec cat .env 回灌 | 步骤 2 拉现网, 步骤 4 回灌进 manifest |
| Next.js cold-start 假 502 | manifest 硬编码 `smokeDisabled: true` |
| Prisma 项目 migration | manifest 硬编码 `postDeploy: "pnpm prisma migrate deploy"` |
| uploads/data 不覆盖 | manifest 硬编码 `preserveData: ["data", "public/uploads"]` |
| pnpm workspace 冲突 | zip 排 `pnpm-workspace.yaml` |
| Legacy 大目录撑爆 MulterError | zip 排项目特定 legacy (如 `public/prompts/[0-9]*` 数字目录) |
| env control char | 全程 jq, 禁 python parse |

## 模板 (image-studio 版, 抽象点直接抄)

参考实文件: `~/projects/image-studio/scripts/deploy-prod.sh` (150 行 bash)。

每个项目**至少定制**:
- `PROJECT` / `HOST` / `PORT` 三个常量
- zip exclude 清单 (项目特有的 legacy 目录)
- smoke URL 清单 (项目特有的核心 endpoint)
- postDeploy (Prisma 项目要, 纯 static 不要)
- preserveData (有上传 / 数据文件的项目要)

## 反例 — 每次现凑 curl 的代价

**image-studio 2026-07-02 部署史**(为什么爸爸受不了):

- 5-13 之前: rsync + SSH 手动部, 每次撞不同坑
- 5-13 起走 mvp-deployer HTTP API, 但每次现凑 curl + manifest
- 每次都撞: env 丢 key / zip 太大 / Next.js 假 502 / postDeploy 忘加 / pnpm-workspace 冲突 / migrate 忘跑
- 7-02: 又一次凑 curl + 用 python 解析响应挂在 control char 死循环 → 爸爸戳穿 → 固化脚本 `1e6f470` commit

**固化后**: 下次部只需 `./scripts/deploy-prod.sh`, 8 min 全过, 不再重踩。

## 主 SKILL 引用

在 `mvp-deployer/SKILL.md` §5 "配套文件" 列表里加一行:

```
- `references/in-repo-deploy-script.md` ⭐ — 项目部第 2 次以上必固化 in-repo bash 脚本, 别再手工凑 curl
```

## 相关

- 主 SKILL.md 5 条铁律 §2 (env 全量覆盖) — 脚本内置修法
- `references/pitfalls.md` — 30+ 症状, 脚本内置的是最高频那批
- `references/recipes.md` §0 Setup — 完整可抄脚本, 本节说的是"抄完还要放进项目"
