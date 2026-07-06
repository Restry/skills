# Manifest schema

`POST /api/deploy` 接 multipart：
- `file=@<zip>` — 项目 zip
- `manifest=<JSON string>` — 本文件描述的对象

**curl 注意**：`-F "manifest=@/tmp/m.json"` 会当**文件**上传，触发 `MulterError: Unexpected field`。必须 `-F "manifest=$(cat /tmp/m.json)"` 当**字符串**。

## 字段表

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---:|---:|---:|---|
| `project` | string | ✓ | – | PM2 app name，sanitize 成 `[a-z0-9_-]` |
| `type` | `node` \| `python` \| `static` | ✓ | – | 运行时类型 |
| `port` | number | ✓ | – | 进程监听端口，Caddy 反代到它 |
| `host` | string | ✓ (v2) | – | 公网 hostname。**省略 → 400**，不再隐式拼 `<project>.mvp.restry.cn` |
| `run` | string | ✓ | – | PM2 启动命令 |
| `build` | string | ✗ | – | 显式 `bash -lc <build>`。省略则跑 package.json `scripts.build`；都没就跳过 |
| `preserveData` | `false` \| `true` \| `string[]` | ✗ | `["data"]` | false=禁；true/省略=保留 `data`；数组=显式相对目录 |
| `env` | object | ✗ | `{}` | **最高优先级 env**；值会落 `.deploy-manifest.json` 明文 |
| `initOnce` | string | ✗ | – | 仅首次跑（`.deployer-initialized` marker） |
| `initOnceTimeoutMs` | number | ✗ | 600000 | 上限 600s |
| `postDeploy` | string | ✗ | – | 每次 deploy 都跑（PM2/Caddy 后） |
| `postDeployTimeoutMs` | number | ✗ | 300000 | 上限 600s |
| `smokePaths` | string[] | ✗ | `["/"]` | 额外 HTTPS 探测路径，`/` 永远先探 |
| `smokeDisabled` | bool | ✗ | false | 紧急绕过（Next.js 类必开） |
| `autoDeploy` | object | ✗ | – | GitHub 自动部署，见 `auto-deploy.md` |

## Env 优先级

```
finalEnv = manifest.env > vault export -p <project> > ~/.credentials/.env <PROJECT>__ 前缀
```

merged 后的 `finalEnv` 是**唯一** runtime env：写 `.env`、注入 PM2、传给 `initOnce` / `postDeploy` / 子 build 命令。

规则：
- key 必须匹配 `[A-Za-z_][A-Za-z0-9_]*`，不合法的跳过 + WARN
- value 全 stringify
- 含空格/`#`/引号/换行的值会被 JSON-quote 写到 `.env`
- task log 只打 count + skipped key 名，不打值

⚠️ **manifest.env 是全量覆盖语义**：只传一个 key 也会重写整份 .env 文件。redeploy 老项目必须先抓全量再回灌（见主 SKILL.md §4）。

## Pipeline phases

```
snapshot → extract → preserveData → envLoad → install → prisma → build
        → swap → pm2 → caddy → [initOnce] → [postDeploy] → smoke → done
```

`swap` 之后失败触发自动 rollback（文件 + Caddy 路由 + PM2）。

## 字段使用守则

- **`build`** 不能 chain 多条命令——deployer 把整字符串丢给 `bash -lc`，但只跑写死的 `pnpm install --no-frozen-lockfile && pnpm run build`。要 chain 写进 package.json 的 `build` 脚本。
- **`initOnce`** 失败让整个 deploy task 失败，**且不写 marker**——下次 deploy 还会再试。成功才写。
- **`postDeploy`** 每次跑，必须幂等（`migrate deploy` / `upsert` SQL，不是 `INSERT` / `CREATE TABLE`）。
- 想强制重跑 initOnce：`/api/exec` 跑 `rm -f .deployer-initialized` 再 redeploy。

## 完整示例

### 最小（无 build）

```json
{
  "project": "simple-node",
  "type": "node",
  "port": 3810,
  "host": "simple-node.mvp.restry.cn",
  "run": "node server.js"
}
```

### Next.js + Prisma

```json
{
  "project": "image-studio",
  "type": "node",
  "port": 3789,
  "host": "design.mvp.restry.cn",
  "build": "pnpm install --no-frozen-lockfile && pnpm prisma generate && pnpm build",
  "run": "pnpm start",
  "smokeDisabled": true,
  "env": {
    "DATABASE_URL": "postgresql://...",
    "PORT": "3789",
    "NEXTAUTH_URL": "https://design.mvp.restry.cn"
  },
  "postDeploy": "pnpm prisma migrate deploy",
  "preserveData": ["data", "public/uploads"]
}
```
