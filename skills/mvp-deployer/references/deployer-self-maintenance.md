# MVP Deployer self-maintenance notes

Use this when modifying `~/projects/mvp-deployer` itself, especially deploy pipeline / env / preserveData / Dashboard work.

## One-path deploy invariant

`POST /api/deploy` must stay a single async path:

- Always create a task and return `202 { taskId, status:'queued', statusUrl }`.
- Do not reintroduce a sync/legacy branch based on `manifest.build` or project type.
- No-build projects still go through builder; build phase logs skip when there is no `manifest.build` and no package `scripts.build`.
- Keep active-task `409` protection for same project.

## Env invariant

`finalEnv` is the only runtime env:

- Merge order: credentials prefix < vault < `manifest.env`.
- Sanitize env keys before writing/using them.
- `.env`, PM2, `initOnce`, `postDeploy`, and child build commands must all receive the same sanitized `finalEnv`.
- Task logs may print counts and skipped key names, never secret values.

## preserveData copy pitfall

When preserving nested dirs such as `public/uploads`, never run `cp -a old/public/uploads new/public/uploads` if destination already exists: Linux copies into the existing directory and creates `new/public/uploads/uploads/...`.

Correct behavior:

1. Normalize allowed relative paths (`false` => none, `true`/unset => `['data']`, array => filtered relative paths).
2. Resolve `src` and `dest` with `path.resolve` and assert both stay inside their roots.
3. If `dest` exists inside the deploy dir, remove it first.
4. `mkdir -p dirname(dest)`.
5. Copy `src` to `dest`.
6. Test with a real tmpdir fixture where both old and new deployments contain `public/uploads` and assert there is no nested `uploads/uploads`.

## Verification checklist for deployer self-changes

Do not trust a coding agent's success report. Hermes should verify:

```bash
cd ~/projects/mvp-deployer
python3 -m py_compile skill/scripts/deploy.py
node --check server.js deploy.config.js ecosystem.config.js
for f in lib/*.js; do node --check "$f" || exit 1; done
npm test
git diff --stat
git status --short
```

Also run a secret grep for any sensitive value handled in the session. Keep values out of summaries and commits.

For pipeline changes, run at least one local API smoke where possible:

- Start the server with temp `DEPLOYER_APPS_DIR`, `DEPLOYER_UPLOAD_DIR`, and `AUTO_DEPLOY_STATE_FILE`.
- Put a fake `pm2` earlier in `PATH` to avoid touching real processes.
- Upload a minimal no-build zip and verify `/api/deploy` returns a taskId and task logs reach expected phases.
- It is acceptable for a local smoke to fail at Caddy if `CADDY_ADMIN_URL` intentionally points to a dead local port; the useful signal is that no-build deployment entered the task pipeline and wrote expected env/build-skip logs.

## Masked output caveat

Hermes terminal output may mask `Authorization: Bearer ...` or other token-looking strings in displayed logs. If a generated file appears syntactically broken in the tool output because of masking, verify the actual file with `python3 -m py_compile` or by reading raw file content before assuming the file is corrupt.