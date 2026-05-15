# Caddy Duplicate `@id` Route — Recovery Procedure

## Symptom

Deploy API replies:
```
Caddy API POST /config/apps/http/servers/srv0/routes → 400:
indexing config: duplicate ID 'mvp-route-<project>' found at routes/N and routes/M
```

All redeploys fail until cleaned up.

## Root Cause (historical, fixed 2026-04-20)

Old `/opt/mvp-deployer/lib/caddy.js` `addRoute()` used `PUT /id/mvp-route-<project>`.
**Caddy's PUT on a config path inserts at that position, it does not replace.**
Each redeploy appended another duplicate-`@id` route until the config became
un-patchable. Fix: change `PUT` → `PATCH` in `addRoute()`. Backup at
`lib/caddy.js.bak`. Server already has the patched version.

## Recovery Procedure (when duplicates have accumulated)

Caddy admin API runs on `localhost:2019` (not internet-exposed).

1. **List current routes** (server-side):
   ```
   curl -s http://localhost:2019/config/apps/http/servers/srv0/routes
   ```
   Each element may have an `@id` field and `match[0].host` array.

2. **Identify duplicates** pointing to the same hostname. Keep the route whose
   `@id` matches `mvp-route-<project>` (deployer's canonical one). Remove
   legacy ones lacking `@id`.

3. **Delete by array index**:
   ```
   curl -X DELETE http://localhost:2019/config/apps/http/servers/srv0/routes/<INDEX>
   ```
   ⚠️ Indices shift after each DELETE. Re-list between deletes, or delete
   highest-index-first.

4. **Verify** exactly one route with that `@id` remains, then rerun deploy.

## Shell Tip

In a single-quoted ssh command, `@` in Python string literals survives fine.
Use a short `python3 -c` script with `json.load` + `r.get('@id')` rather than
JSON-path tricks.

## Permanent Prevention

Don't downgrade `/opt/mvp-deployer/lib/caddy.js` below the PATCH commit.
If you `rsync` an old branch over `lib/`, re-apply the PATCH change before
restarting PM2.
