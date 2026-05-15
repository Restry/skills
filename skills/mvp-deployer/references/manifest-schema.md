# Manifest Schema

Submitted as a `manifest` form-field (JSON string) alongside the zip
`file` field in `POST /api/deploy`.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `project` | string | ✓ | Unique project name (matches PM2 app name, app dir `/opt/mvp-apps/<project>`) |
| `type` | `"node"` \| `"python"` \| `"static"` | ✓ | Runtime kind |
| `port` | int | ✓ | App listen port. Caddy reverse-proxies `127.0.0.1:<port>` |
| `run` | string | ✓ | PM2 start command. Shell allowed (e.g. `pnpm start`) — deployer auto-sets `interpreter: 'none'` |
| `build` | string | – | Build command. **Presence triggers async pipeline** (otherwise sync extract+start). |
| `host` | string | – | Custom CNAME (e.g. `design.mvp.restry.cn`). Default: `<project>.mvp.restry.cn` |
| `preserveData` | string[] \| `true` | – | Dirs to keep across deploys (not overwritten by zip). Default `["data"]` |
| `env` | object | – | Written to `.env` AND merged into PM2 process env. See pitfalls below |

## Env Pitfalls

1. **Empty `env: {}` clears existing `.env`** — prisma/runtime breaks.
   Always `--preserve-env` (fetch existing first) on redeploy.

2. **`NODE_ENV=production` breaks builds** — pnpm skips devDeps so prisma
   CLI is missing. Strip it; Next.js's `next start` defaults to production.

3. **Don't include secrets in commit history** — the manifest JSON appears
   in PM2 logs / task records. Generate manifests at deploy time from
   `~/.credentials/` files, never check them in.

## Async Pipeline Phases

When `build` is present, server runs:

```
extract → preserveData → write .env → install → prisma → build → atomic swap → pm2 → caddy → done
```

Poll `GET /api/deploy/tasks/<taskId>` every 4–6s. Status field cycles
`queued → running → succeeded|failed`. `phase` field shows current step.

## Returns

```json
{ "taskId": "1bcc88652a23a8df", "status": "queued",
  "statusUrl": "/api/deploy/tasks/1bcc88652a23a8df" }
```

Use the returned `statusUrl` exactly — don't manually construct
`/api/tasks/<id>` (404).
