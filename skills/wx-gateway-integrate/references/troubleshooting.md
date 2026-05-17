# 接入侧故障排查

业务方接 wx-gateway 后扫码不通的诊断手册。**网关侧故障**见 `wx-gateway-operate` skill 的 `references/troubleshooting.md`。

## 失败模式速查

| 现象 | 原因 | 修复 |
|---|---|---|
| `qrcodeUrl` 是 placehold.co | gateway 侧 WX_APPID/SECRET 没配 | 改 wx-gateway prod env |
| SSE 一直 pending | 公众号后台未启用配置 / Token 不匹配 / 走了加密模式 | 公众号后台改明文 + 重新提交 |
| finalize `err=sig` | 两边 secret 不一致 | 对比 `WX_GATEWAY_SECRET` |
| finalize `err=expired` | 时钟偏 5min+ | NTP；不要无脑放大 MAX_SKEW_MS |
| `app_not_found` | APPS_JSON 没注册 | 改 manifest redeploy gateway |
| finalize 全部 `err=sig` 即使 secret 对 | `.env` 里 APPS_JSON=`[object Object]`，secret 实际 undefined | manifest.env.APPS_JSON 必须 JSON.stringify 后传字符串 |
| 同一 token 二次回调被业务方拒绝 | 业务侧旧版做了 wxFinalizeLog 一次性消费 | 删掉那段，改成 idempotent upsert（见 OAuth 补全节）|
| 扫码后 SSE 推 confirmed 但业务方页面**不跳转** | 业务方前端用 `es.addEventListener("confirmed", ...)` 监听**命名事件**，但 wx-gateway 推的是**默认 message 事件**（`data: {"status":"confirmed",...}` 没有 `event:` 行）。 命名监听器永远不触发 | 必须 `es.onmessage = (ev) => { const d = JSON.parse(ev.data); if (d.status === "confirmed") window.location.href = d.redirect; }`。不要用 `addEventListener("confirmed"\|"scanned"\|"expired", ...)`。**抓真流验证**：`curl -sN https://wx.mvp.restry.cn/wx/poll/<token>` 看到的全是裸 `data: {...}`，没有命名事件。echo 2026-04-28 翻车 |
| 扫码后微信确认了但页面不跳转，SSE 一直\"已扫码请确认\" | 前端用了 `es.addEventListener(\"confirmed\", ...)` 监听**命名事件**，但 wx-gateway 推的是默认 message 事件 (`data: {...}` 无 `event: xxx` 行) | 必须 `es.onmessage = ev => { const d=JSON.parse(ev.data); if(d.status===\"confirmed\") window.location.href = d.redirect; }`。验证：`curl -sN https://wx.mvp.restry.cn/wx/poll/<token>` 看到的就是裸 `data:` 行无 `event:`。echo Phase 2.5 实战翻车 |

## 反模式（别做）

- ❌ 在业务项目里再配置一次微信回调 URL（公众号只能 1 个）
- ❌ 把 `WX_GATEWAY_SECRET` 暴露成 `NEXT_PUBLIC_*`
- ❌ 跳过 5 分钟时间窗校验
- ❌ 用 `==` 比 sig（必须 `timingSafeEqual`）
- ❌ 只用 openid 做用户主键（同一用户不同公众号会重复；优先 unionid）
- ❌ finalize 做 token 一次性消费（=拦截 OAuth 补全 nickname/avatar；改成 idempotent upsert）
- ❌ finalize redirect 用 `new URL("/login?err=x", req.url)`——Caddy/Nginx 反代后 req.url host 是内网 `localhost:3795`，浏览器拿到 `https://localhost:3795/...` 直接跳不过去。**必须** `process.env.NEXTAUTH_URL ?? new URL(req.url).origin` 拼 absolute base（echo Phase 2.5 实战翻车）
- ❌ 业务侧 secret 跟 wx-gateway 不一致 → 永远 `err=sig`。register-app.py 生成的 secret 是**唯一权威源**，不要手动再生成一份写进 .env.local；如果两边不一致，用 `/api/exec/wx-gateway grep ^APPS_JSON` 拿真值反向同步


## 反模式（别做）

- ❌ 在业务项目里再配置一次微信回调 URL（公众号只能 1 个）
- ❌ 把 `WX_GATEWAY_SECRET` 暴露成 `NEXT_PUBLIC_*`
- ❌ 跳过 5 分钟时间窗校验
- ❌ 用 `==` 比 sig（必须 `timingSafeEqual`）
- ❌ 只用 openid 做用户主键（同一用户不同公众号会重复；优先 unionid）
- ❌ finalize 做 token 一次性消费（=拦截 OAuth 补全 nickname/avatar；改成 idempotent upsert）
- ❌ finalize redirect 用 `new URL("/login?err=x", req.url)`——Caddy/Nginx 反代后 req.url host 是内网 `localhost:3795`，浏览器拿到 `https://localhost:3795/...` 直接跳不过去。**必须** `process.env.NEXTAUTH_URL ?? new URL(req.url).origin` 拼 absolute base（echo Phase 2.5 实战翻车）
- ❌ 业务侧 secret 跟 wx-gateway 不一致 → 永远 `err=sig`。register-app.py 生成的 secret 是**唯一权威源**，不要手动再生成一份写进 .env.local；如果两边不一致，用 `/api/exec/wx-gateway grep ^APPS_JSON` 拿真值反向同步

