# wx-gateway 部署历史 / commit 节点

时间线参考。改代码或排查回归 bug 时先看相关 commit 知道当时改了什么。

## 10. 部署历史 / commit 节点

- `8541dc4` 初版上线（PackHorizon 单租户）
- `8623bf5` 加 `/wx/selftest` 路由 + AppEntry.finalizePath 可选
- `d804328` 加 CORS：`lib/wx/cors.ts`，`/wx/qr` + `/wx/poll` 严格 whitelist（APPS_JSON 各 appBaseUrl origin），`/wx/callback`/`/wx/selftest` 不加
- `e4a09da` 微信内 OAuth 一键登录：`/wx/oauth/start` + `/wx/oauth/callback`（snsapi_userinfo），WxLoginToken 加 nickname/avatarUrl
- `c3df1c7` MP_verify 域名校验文件提交进 `public/`，走正常 deploy 即可
- `b7acca5` PC 扫码 reply XML 加 OAuth 引导链接：用户在公众号会话里看到「完善头像昵称：…/wx/oauth/start?app=X」，点一下补全 PII
- `db0d8b5` **v2 batch 1**：APPS_JSON 迁 DB（Prisma `App` 表）+ env 兼容期 merge（DB 优先，env 缺失打 warn）+ admin/invites/scan log 表骨架 + `instrumentation.ts` 启动 hook 读 `ADMIN_BOOTSTRAP_OPENIDS` upsert admin。**首次切 prisma migrate 踩了 baseline 坑**，见 mvp-deployer skill §6.5
- `ee29c04`+`db86edf` **v2 batch 2**：admin 微信扫码登录（吃自家狗粮，admin app `name=admin`，env `ADMIN_APP_SECRET` 启动 hook 自 upsert） + 全套 admin API（`/admin/apps` `/admin/invites` `/admin/admins` `/admin/scans`） + `/apps/register` 公开接口（`X-Invite-Code` header，sha256 hash 存 DB）+ selftest 升级（自签 admin cookie 跑全流程）+ login 页设计风格抄 Image Studio (`#C24E29` 砖红 + `#F8F7F4` 米色 + DM Sans/Mono)
- `020d0ae` 修 React #418 hydration：admin/login 把 server-rendered + inline `<script>` 改成 `"use client"`（之前 #13 已知 issue 关闭）
- `430dc71` 反代 redirect 内网泄露修复：`lib/public-base.ts` 提供 `publicBase(req)`（env > x-forwarded-host > host），所有 redirect/cookie/OAuth callback 都过这层。env 须有 `PUBLIC_BASE_URL=https://wx.mvp.restry.cn`。详见 skill `nextjs-reverse-proxy-redirect-leak`
- `86badb2` **安全加固**：admin 路径随机化（env `ADMIN_PUBLIC_PATH=/_a/<32hex>`）+ 直 `/admin/*` 访问 404 camouflage + login 5/min 速率限制（5min 锁定）+ cookie 1h sliding TTL；middleware.ts 做外部 → 内部 rewrite。`finalizePath` 必须用 `${ADMIN_PUBLIC_PATH}/auth/finalize` 否则被自家 404 拦（踩过一次）
- `aa15e8f` **v2 batch 3**：admin Dashboard UI 4 tab（Apps / Invites / Admins / Scans）+ revoke / rotate-secret / issue invite / promote scan 一键操作。Image Studio 风格
- `929a118` Dashboard 收尾：apps PATCH `status:"active"` 恢复路由 + OPENID 值用 `.dash-sub-val` 单独 reset uppercase
- `f49e91d` **scans 全量留痕**：UnauthorizedScanLog → ScanLog（4 类 kind: admin/business/unauthorized/promoted）+ 30d TTL（启动 60s + 6h 间隔）+ OAuth 用 update 回填 PII 不新增 + Scans tab 4 chips + admin Dashboard 操作列样式
- `6167839` docs: payment v1 plan（personal_qr 人工审核 + jsapi 留口）
- `3d9ddd0` **payment schema**：App.webhookUrl/personalQrUrl + Payment + PaymentWebhookDelivery 两表 + 6 索引（含 `Payment_appName_orderId_key` 幂等 / `Payment_remark_amount_fen_idx` 热路径），postDeploy 永久切到 `prisma migrate deploy`
- `d5e051d` payment v1 commit 2：核心路由 `/pay/create`（HMAC 中间件 + 幂等 + remark base32 去歧义字符）/ `/pay/status` / `/pay/personal/claim`（CAS 状态机）+ `lib/payment/auth.ts`+`state.ts`+`errors.ts` + 占位 personal-qr.png
- `7592620` payment v1 commit 3：admin Payments tab（5th tab）+ approve/reject/redeliver-webhook 路由（事务 CAS + enqueue webhook）+ 6 filter chips + Payments/Scans 操作列右边界修复（共享 `t-scroll`/`table.t`）
- `9bcbc48` payment v1 commit 4：`lib/payment/webhook.ts` 投递 worker（Web Crypto HMAC）+ instrumentation.ts 注册 expire job (60s) / redeliver job (10s) + 单 instance lock（`globalThis.__paymentCronStarted`）
- `e70f813` payment v1 commit 5：selftest +10 case T-PAY-1..10（含 selftest 自跑 webhook endpoint + selftest-only `setNextAttemptOverrideForTest` 把 retry 等待压到 2s）。**总 selftest 28/28**
- `1d0b5a9` **hotfix**：`/apps/register` 加 appBaseUrl 唯一性检查（防 copilot-proxy / -prod 重复事故复发）+ T-REG-DUP selftest case，dup 不扣邀请码。**总 selftest 29/29**
- `9e59813` chore: 删 `output: standalone`（PM2 日志 `next start does not work...` 警告清场，mvp-deployer 不需要 standalone artifact）

