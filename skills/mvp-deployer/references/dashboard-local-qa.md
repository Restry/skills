# Dashboard local QA notes

Use this when changing `public/index.html`, WeChat dashboard login, or browser-only Dashboard docs such as the Skill install panel.

## Sync-skill install guide rule

When the Dashboard tells users how to install the `mvp-deployer` skill, it must point to **sync-skill**, not deployer runtime endpoints.

Recommended public install snippet:

```bash
SCRIPTS=${SYNC_SKILL_SCRIPTS:-$HOME/.claude/skills/sync-skill/scripts}
python3 "$SCRIPTS/pull.py" mvp-deployer
```

Notes:
- Do not hardcode Hermes source paths like `~/.hermes/skills/...` in user install instructions.
- The install target is controlled by `~/.config/sync-skill/config.toml` (`target_dir`). Say that explicitly if explaining where files land.
- It is OK to keep the maintainer publish command separately, but label it “maintainer / ottor-laptop only”:

```bash
python3 ~/.hermes/skills/sync-skill/scripts/publish.py \
  ~/.hermes/skills/devops/mvp-deployer \
  -m "publish mvp-deployer"
```

- `/skill.zip` and `/install-instruction` are removed. Mention them only as deprecated/removed, never as an install path.

## Local visual QA for authenticated dashboard

For Dashboard UI changes, do not stop at curl or tests. Start a local server with throwaway dirs and dummy WeChat config, then enter via the finalize callback so the real logged-in dashboard renders.

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

Generate a local login URL:

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

Open that URL, then inspect the logged-in dashboard. Use visual QA to catch layout issues such as right-column code blocks wrapping, copy buttons overlapping, or install docs being visually buried.

## Status dashboard data-shape pitfall

`/api/status` returns nested deployment data, not the flat fields older dashboard code may assume:

```js
{
  project: "cspy",
  manifest: { project, type, port, host, deployedAt, /* env must never render */ },
  pm2: { status: "online", memory, cpu, uptime, restarts } || null,
  route: { hosts: ["cspy.mvp.restry.cn"], upstream: "127.0.0.1:3791" } || null,
  autoDeploy: { /* optional */ }
}
```

When editing `public/index.html`, normalize this shape before rendering. Use `p.project` for name, `p.pm2.status` for state, `p.pm2.memory/cpu/restarts/uptime` for metrics, and `p.manifest.host || p.route.hosts[0]` for host. Do not read status/metrics from top-level `p.status`, `p.memory`, `p.cpu`, or `p.restartCount`; that makes the UI show every project as `UNKNOWN` / `—` even when PM2 is healthy. Treat `.rollback`, `*.failed-*`, and directories with no manifest/pm2/route as archived/no-PM2 rather than active services. Never render `manifest.env` or other secret-bearing fields.

## Visual QA for status metrics

The local throwaway server is useful for layout and login-state checks, but unless PM2 has matching local processes it will only show `NO PM2`, so it does **not** prove mem/cpu/restarts rendering. For dashboard status UI changes, also run one of:

- a production logged-in visual check after deploy; or
- a local fixture/PM2 setup with at least one matching online PM2 process.

Verify specifically that the page shows non-UNKNOWN states plus `MEM`, `CPU`, `RESTART`, `UPTIME`, and active/archived counts.

## Verification checklist

- `node --check server.js deploy.config.js ecosystem.config.js`
- `for f in lib/*.js; do node --check "$f" || exit 1; done`
- `npm test`
- `git diff --check`
- secret fingerprint scan before commit
- browser visual check for Dashboard UI changes
- for Dashboard status/metrics changes: visual check with real PM2-backed data, not only the dummy local `NO PM2` fixture
