# GitHub auto-deploy

mvp-deployer 支持两种 GitHub 触发的自动部署，**互补不互斥**：

1. **轮询模式**（默认，无需 webhook）— 每 10 分钟 `git ls-remote`，发现新 sha 自动部署
2. **Webhook 模式**（可选加速）— GitHub push 立即触发

## 启用

项目的 `.deploy-manifest.json` 加：

```jsonc
"autoDeploy": {
  "enabled": true,
  "provider": "github",
  "repo": "Restry/my-app",   // owner/repo / https URL / git@ URL 都接受
  "branch": "main",
  "path": "."                // 可选，repo 内子目录
}
```

## 轮询模式行为

- 每 10 分钟 `git ls-remote`，发现新 sha → 完整部署管线（smoke + rollback 全照走）
- **白天才跑**：默认 `Asia/Shanghai` 09:00–23:00（区间 `[start, end)`，23:00 整已不再 active）
- 部署中又来新 sha → 落 `pendingSha`，下一 tick 接力
- task 跑挂（smoke fail / rollback）→ state 写 `lastError`，**lastDeployedSha 不前进**，下 tick 重试同一 sha
- `GET /api/status` 返回顶层 `autoDeploySchedule` + 每个项目的 `autoDeploy` 状态

## Webhook 模式（可选）

- URL: `https://deploy.mvp.restry.cn/api/webhooks/github`
- Content type: `application/json`
- Events: `push`（`ping` 应返 `{"pong": true}`）
- Secret: 服务端 `MVP_DEPLOYER__GITHUB_WEBHOOK_SECRET`，**永远不存进 repo 或聊天**

**安全模型**：
- webhook 故意注册在 bearer auth / IP allowlist **之前**——GitHub 发不了那些
- 安全边界 = HMAC-SHA256 验 `X-Hub-Signature-256` 对原始 body 的签名
- payload 只是触发，服务端必须 cross-check 部署 manifest 里 `autoDeploy.enabled === true` 且 repo+branch 匹配
- 快速 ACK push（202）+ 异步 clone/zip/enqueue
- 重用现有 deploy pipeline（`builder.enqueue` / `deployer.deploy`），smoke / Caddy diff guard / rollback 全照走

## State 语义陷阱（别再踩）

**不要**在 enqueue 时就把 sha 标记成 deployed。

正确流转：
1. **enqueue**：写 `lastQueuedSha`, `lastTaskId`, `lastSeenSha`, `pendingSha=null`
2. **succeeded 回收**：`lastDeployedSha = lastQueuedSha`，`lastDeployAt` set，`lastError` clear
3. **failed 回收**：`lastError` set，**`lastDeployedSha` 不动**，让 poller 重试同一 sha
4. poller 必须先 reconcile 再查 `pendingSha` / `git ls-remote`

错过这条 → 失败的 build/smoke 被当作"已部署"永远不重试。

## 服务端可调环境变量（Daddy 维护）

| Env | 默认 | 说明 |
|---|---|---|
| `AUTO_DEPLOY_POLL_INTERVAL_MS` | `600000` | 10 min |
| `AUTO_DEPLOY_ACTIVE_TZ` | `Asia/Shanghai` | 时区 |
| `AUTO_DEPLOY_ACTIVE_START_HOUR` | `9` | 白天起点 |
| `AUTO_DEPLOY_ACTIVE_END_HOUR` | `23` | 白天终点（exclusive）|
| `AUTO_DEPLOY_DISABLE_SCHEDULE` | – | 设 `true` 全天运行 |

## 验证

先按 `recipes.md §0 Setup` 准备 `$HDR` / `$ENDPOINT`。

```bash
# 1. /api/status 顶层有 autoDeploySchedule + 项目级 autoDeploy 字段
curl -sS -H @"$HDR" "$ENDPOINT/api/status" | jq .autoDeploySchedule

# 2. webhook signed ping(验 secret 配对)
#    SECRET 走门神
SECRET=*** get mvp-deployer/GITHUB_WEBHOOK_SECRET | sed $'s/\x1b\\[[0-9;]*[A-Za-z]//g' | tr -d '\r\n ')
BODY='{"zen":"test"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -sS -X POST "$ENDPOINT/api/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -d "$BODY"
# 期望: 200 {"pong":true}

# 3. 坏签名期望 401
curl -sS -X POST "$ENDPOINT/api/webhooks/github" \
  -H "X-Hub-Signature-256: sha256=bogus" -d "$BODY"
```
