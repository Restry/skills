# Manifest schema

Submitted as a `manifest` form-field (JSON string) alongside the zip `file` field in `POST /api/deploy`.

`POST /api/deploy` is always async. It returns `202 { taskId, status:'queued', statusUrl }` and the task runs the full pipeline whether or not a build step exists.

## Fields

| Field | Type | Required | Default | Notes |
|---|---:|---:|---:|---|
| `project` | string | yes | – | PM2 app name; sanitized to `[a-z0-9_-]` |
| `type` | `node` \| `python` \| `static` | yes | – | Runtime type |
| `port` | number | yes | – | App listen port; Caddy proxies to it |
| `run` | string | yes | – | PM2 start command |
| `host` | string | yes | – | Public hostname. No default fallback. |
| `build` | string | no | – | Explicit `bash -lc <build>` command. If omitted, server runs package.json `scripts.build` when present; otherwise build phase is skipped. |
| `preserveData` | `false` \| `true` \| string[] | no | `["data"]` | `false` disables preserve; `true`/omitted preserves `data`; array preserves listed relative dirs such as `["data","public/uploads"]`. Absolute paths, `..`, `~`, empty entries rejected. |
| `env` | object | no | `{}` | Highest-priority env source; values may be persisted in `.deploy-manifest.json`, so do not put secrets here unless acceptable. |
| `initOnce` | string | no | – | Shell command run only once after PM2/Caddy, guarded by `.deployer-initialized`. Receives `finalEnv`. |
| `initOnceTimeoutMs` | number | no | 600000 | Max 600s. |
| `postDeploy` | string | no | – | Shell command run every deploy after PM2/Caddy. Receives `finalEnv`. Use for migrations. |
| `postDeployTimeoutMs` | number | no | 300000 | Max 600s. |
| `smokePaths` | string[] | no | `["/"]` | Additional HTTPS paths to probe; `/` always first. |
| `smokeDisabled` | bool | no | false | Emergency bypass only. |

## Env precedence

Final runtime env is:

```text
manifest.env > vault export -p <project> > ~/.credentials/.env PROJECT__KEY prefix
```

The merged and sanitized `finalEnv` is the only runtime env: it is written to `.env`, passed to PM2, and passed to `initOnce` / `postDeploy` / child build commands.

Key rules:

- env keys must match `[A-Za-z_][A-Za-z0-9_]*`; illegal keys are skipped with a task WARN.
- values are stringified.
- `.env` values containing whitespace, `#`, quotes, or newlines are JSON-quoted.
- task logs print counts and skipped key names, not values.

## Pipeline phases

```text
snapshot -> extract -> preserveData -> envLoad -> install -> prisma -> build -> swap -> pm2 -> caddy -> [initOnce] -> [postDeploy] -> smoke -> done
```

Failures after `swap` trigger rollback where possible.

## Examples

No explicit build; package has no build script:

```json
{
  "project": "simple-node",
  "type": "node",
  "port": 3810,
  "run": "node server.js",
  "host": "simple-node.mvp.restry.cn",
  "preserveData": ["data", "public/uploads"]
}
```

Next.js with migration:

```json
{
  "project": "image-studio",
  "type": "node",
  "port": 3789,
  "run": "pnpm start",
  "host": "design.mvp.restry.cn",
  "build": "pnpm build",
  "env": {
    "DATABASE_URL": "postgresql://..."
  },
  "postDeploy": "pnpm prisma migrate deploy",
  "preserveData": ["data", "public/uploads"]
}
```
