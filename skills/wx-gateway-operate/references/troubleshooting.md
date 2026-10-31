# wx-gateway 故障排查手册

按链路段分类。每条都有真实事故复盘 + 一句话根因 + 修复路径。

---

## A. 二维码 / scan reply 不出来

| 症状 | 根因 | 修复 |
|---|---|---|
| `/wx/qr/{app}` 返 404 | app 不在 DB 也不在 APPS_JSON | admin Dashboard 注册或检查 `/admin/apps` |
| `/wx/qr/{app}` 返 500 access_token | cgi-bin token 失效 / IP 白名单 | 检查公众号后台 IP 白名单含部署机出口 |
| 扫码后微信不回任何文字 | callback POST 验签失败 / parseXml 报错 | pm2 日志看 `[wx/callback]`，重点查 `WX_TOKEN`/`WX_AES_KEY` 与公众号后台一致 |
| reply 文字里 OAuth 链接错 | finalize URL builder bug 或 `appBaseUrl` 缺 https | 复 §伪造 SCAN 端到端烟测，确认 reply XML |

---

## B. OAuth callback 阶段失败

### 案例 1：cgi-bin/user/info errcode 40003 invalid openid（**2026-04-28 撞过**）

**症状**：扫码完跳 finalize "闪一下就没了"，pm2 日志：
```
[wx] user/info errcode 40003 invalid openid hint: [...]
```

**根因**：网关在 OAuth callback 里调了 `cgi-bin/user/info`（关注者客服接口），但用户**未关注**或者 openid 是 sns 域而非 cgi-bin 域。微信对未关注用户 / 错域 openid 直接 40003。

**正确做法**：snsapi_userinfo 走完后**只用 `/sns/userinfo?access_token=...&openid=...`**，**绝不**调 cgi-bin/user/info（2021 起后者把 nickname/avatar 都置空，2022 起对未关注用户直接 40003）。当前 `app/wx/oauth/callback/route.ts` 已经对，调的是 `fetchSnsUserInfo`。

**关联 skill**：`wechat-mp-profile-pii-gotcha`

---

### 案例 2：finalize 签名校验失败 / 业务方手里 secret 跟 DB 对不上

**症状**：扫码完业务方拒接 finalize redirect，业务方报"签名错"或"sig invalid"。

#### 子案例 2a：duplicate appBaseUrl（**2026-04-28 撞过，copilot-proxy 事故**）

业务方 7 秒内注册了两个 app（`copilot-proxy` + `copilot-proxy-prod`），**同 `appBaseUrl: https://api.eagle.openclaws.co.uk`**，两个不同 secret。业务方 .env 写的 secret 跟某一个对应，但用户 token 落表用的 `appName` 是另一个 → finalize 时签名用的 secret 不匹配。

**根因**：v2 之前 `/apps/register` 不查 appBaseUrl 唯一性。

**修复（已落地 commit `1d0b5a9`，2026-04-28）**：`/apps/register` 命中已有 active 同 appBaseUrl 直接返 `409 duplicate_app_base_url`，且**不消耗邀请码**。selftest case `T-REG-DUP` 守门。

**事故诊断快路**：
```sh
# 列出指向同一 appBaseUrl 的所有 app
deployer-exec '
  node -e "const{PrismaClient}=require(\"@prisma/client\");
  const p=new PrismaClient();
  p.app.findMany({where:{appBaseUrl:\"<URL>\"}}).then(rs=>{
    for(const r of rs)console.log(r.name,r.status,r.secret.slice(0,8),r.createdAt);
    process.exit(0);
  });"'
```

如果同 URL 有多条 active，先把多余的 revoke：`prisma.app.update({where:{name:"X"},data:{status:"revoked"}})`，再让业务方核对手里的 secret 跟剩下那条是否一致；不一致就把正确 secret 用 base64 给业务方（基础工卫生：永不在聊天里贴 hex 原文）。

#### 子案例 2b：业务方 secret 配错（拷贝丢字符）

**典型症状**：业务方 .env 里 secret 长度不是 64 hex（base64 解码后短了 / 多了换行 / 缺尾字符）。

**诊断**：让业务方贴 base64 编码版本（让聊天/日志层 mask 不到原文），本地 `echo X | base64 -d | wc -c` 看长度——必须**恰好 64**。

**修复**：网关侧用 `prisma.app.findUnique({where:{name}})` 取真 secret 的 base64，让业务方覆盖。

---

## C. SSE poll 卡住 / 30s 超时

| 症状 | 根因 | 修复 |
|---|---|---|
| 业务方前端 EventSource 连不上 | Caddy 默认对 SSE 缓冲 | 网关本身 `app/wx/poll/[token]/route.ts` 已 `headers: { "X-Accel-Buffering": "no" }`；如 Caddy 仍缓冲检查 reverse_proxy 配置 |
| 30s 超时但用户已扫了 | callback POST 没把 status 改 confirmed | 真扫但 token 未 confirmed → 走 §伪造 SCAN 烟测查 callback 处理 |

---

## D. admin Dashboard 异常

| 症状 | 根因 | 修复 |
|---|---|---|
| `${ADMIN_PUBLIC_PATH}/login` 返 404 | `instrumentation.ts` admin app 没 upsert 或 `finalizePath` 写错 | pm2 日志看 `[bootstrap] admin app upserted`；finalizePath 必须 `${ADMIN_PUBLIC_PATH}/auth/finalize`，**不是** `/admin/auth/finalize`（被自家 404 camouflage 拦死） |
| 登录 6 次后 429 | rate-limit 5/min 被 selftest 自跑爆 | pm2 重启清内存 map / 等 5 分钟 / **selftest 串跑触发的假阳性**——该考虑给 selftest 加 X-Selftest-Token 白名单（TODO） |
| Server Action stale errors | Next.js App Router known limitation | 每次部署后旧客户端 RSC bundle 哈希失效；不可根治；用户刷一下页面就好 |

---

## E. Payment 链路异常

| 症状 | 根因 | 修复 |
|---|---|---|
| `/pay/create` 返 401 missing_signature | 业务方没传 X-WX-App-Name / X-WX-Sig / X-WX-Ts | 业务方按 `lib/payment/auth.ts` 文档算 HMAC |
| `/pay/create` 返 403 expired_signature | 时钟漂移 > 5 分钟 | 检查业务方机器 NTP |
| Webhook 一直 dead 掉 | 业务方 endpoint 返 5xx 6 次（按 [0,30s,2m,10m,1h,6h,24h] 退避后） | admin Dashboard Payments tab → 单行「重投」按钮重置 deliveryAttempt |
| Payment 状态一直 pending 不 expire | expire cron 没启动 | pm2 日志找 `[payment/cron]`；`instrumentation.ts` 单 instance lock 是否泄露 |
| **上传个人收款码后图返 404，文件物理存在** | Next.js `public/` prerender 缓存（响应头 `x-nextjs-prerender:1` + `x-nextjs-cache:HIT`），运行时新写文件不在 build 快照里。叠加 mvp-deployer 部署 zip 覆盖 `public/`，已上传文件下次 redeploy 也丢 | 必须改设计：上传写 `data/qr/`（preserveData 保留），加 `app/payment/qr/[file]/route.ts` 动态 handler 读盘并设 Content-Type。详见 skill `nextjs-public-upload-trap`。**Phase 2.0 commit `a6c49f1` 中招，待修** |

---

## F. 部署阶段

跟 mvp-deployer 协同的坑见根目录 SKILL.md §10 + skill `mvp-deployer`。重点：
- prisma 阶段强跑 `migrate deploy` 走 mvpadmin 用户，wx_gateway DB owner 不是 mvpadmin → P1000；schema 同步**绝不放 build**，放 `postDeploy: pnpm prisma migrate deploy`
- `output: standalone` 已删（commit `9e59813`），PM2 日志不再有 `next start does not work...` 警告
- 业务方接入 + 一次部署不等于"网关需要 redeploy"——v2 注册走 DB，cache TTL 60s 自然失效

---

## 排错三板斧（套路化）

任何"扫码不行"先按这个顺序走，不要瞎猜：

1. **pm2 日志**：`curl /api/logs/wx-gateway?lines=300` 找 `[wx]` / `[wx/oauth/callback]` / `[apps]` / `[bootstrap]` 行
2. **DB 状态**：`/api/exec` 跑 `prisma.wxLoginToken.findUnique({where:{token}})` 看 status / appName / openid 是否符合预期
3. **App 表行**：`prisma.app.findMany({where:{appBaseUrl,status:"active"}})` ——超过 1 行就是 §B 子案例 2a，立刻 revoke 多余的

诊断完之前**不要**改代码、不要 redeploy、不要重置 secret。
