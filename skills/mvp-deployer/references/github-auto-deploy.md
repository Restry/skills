# GitHub Auto-Deploy Runbook

This reference captures the durable workflow for mvp-deployer's GitHub push-triggered auto-deploy feature.

## Contract

A project opts in via its deployed `.deploy-manifest.json`:

```jsonc
"autoDeploy": {
  "enabled": true,
  "provider": "github",
  "repo": "Owner/repo",
  "branch": "main",
  "path": "."
}
```

GitHub webhook:
- URL: `https://deploy.mvp.restry.cn/api/webhooks/github`
- Content type: `application/json`
- Secret: server-side `MVP_DEPLOYER__GITHUB_WEBHOOK_SECRET` only; never store it in the repo or chat
- Events: `push` (GitHub `ping` should return `{ "pong": true }`)

## Safety model

- Webhook is intentionally registered before bearer auth / IP allowlist because GitHub cannot send those.
- Security boundary is HMAC-SHA256 verification of `X-Hub-Signature-256` over the raw request body.
- Webhook payload is only a trigger. The server must cross-check deployed manifests and only deploy projects with `autoDeploy.enabled === true` and matching repo+branch.
- Webhook should ACK push quickly (`202`) and do clone/zip/enqueue asynchronously.
- Auto-deploy must reuse the existing deploy pipelines (`builder.enqueue` or legacy `deployer.deploy`), so smoke tests, Caddy diff guard, and rollback still apply.

## State semantics pitfall

Do **not** mark a SHA as deployed at enqueue time.

Correct state flow:
1. enqueue: write `lastQueuedSha`, `lastTaskId`, `lastSeenSha`, `pendingSha=null`.
2. reconcile succeeded task: set `lastDeployedSha = lastQueuedSha`, set `lastDeployAt`, clear `lastError`.
3. reconcile failed task: set `lastError`, leave `lastDeployedSha` unchanged so the poller can retry the same remote SHA.
4. poller should call reconcile before checking `pendingSha` or `git ls-remote`.

This prevents the bug where a failed build/smoke was treated as already deployed and never retried.

## PM2 / env passthrough

`ecosystem.config.js` must pass server credential variables through from `~/.credentials/.env`:

```js
GITHUB_WEBHOOK_SECRET: process.env.MVP_DEPLOYER__GITHUB_WEBHOOK_SECRET,
AUTO_DEPLOY_POLL_INTERVAL_MS: process.env.MVP_DEPLOYER__AUTO_DEPLOY_POLL_INTERVAL_MS,
AUTO_DEPLOY_STATE_FILE: process.env.MVP_DEPLOYER__AUTO_DEPLOY_STATE_FILE,
```

When adding new PM2 env fields, restart with:

```bash
set -a; source ~/.credentials/.env; set +a
pm2 delete mvp-deployer
pm2 start ecosystem.config.js --update-env
pm2 save
```

Verify the env exists in the running process without printing the secret value:

```bash
PID=$(pm2 jlist | jq -r '.[] | select(.name=="mvp-deployer") | .pid')
tr '\0' '\n' </proc/$PID/environ | grep '^GITHUB_WEBHOOK_SECRET=' >/dev/null && echo present
```

## Verification checklist

Local:
- `npm test`
- `node --check server.js`
- `node --check lib/autoDeploy.js`
- `node --check ecosystem.config.js`
- Local webhook smoke: with IP allowlist set to reject `127.0.0.1`, `/api/status` should be blocked while `/api/webhooks/github` still accepts a correctly signed ping.

Online:
- `GET /api/status` with bearer token returns 200.
- Bad webhook signature returns 401.
- Correct signed `ping` returns 200 `{ "pong": true }`.
- PM2 logs show `autoDeploy poller started`.

## mvp-deployer self-update reminder

Do **not** deploy mvp-deployer through its own `/api/deploy` endpoint. Self-update is rsync + PM2 only (see `references/admin-runbook.md`). A failed self-deploy attempt may produce `MulterError: Unexpected field` or task/state clutter; the durable lesson is to use the admin runbook, not the public deploy API.

## curl multipart pitfall

The deploy API expects `manifest` as a text form field. `-F manifest=@/tmp/manifest.json` uploads it as a file and can trigger `MulterError: Unexpected field` on older deployments. Use a string field instead, e.g.:

```bash
curl -F "file=@/tmp/app.zip" \
     -F "manifest=$(cat /tmp/manifest.json)" \
     -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
     https://deploy.mvp.restry.cn/api/deploy
```
