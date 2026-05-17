---
name: wx-gateway-integrate
description: 业务方接入爸爸的微信公众号能力（扫码登录 / OAuth / 支付）。**协议统一**走 wx-gateway（HMAC + finalize redirect），按公众号选实例：「造悟者」(`wx225bf76b06064faa`) → `wx.mvp.restry.cn`；「莆阳网络科技」(`wxe780b027c2c56921`) → `wxmsg.mvp.restry.cn`（同份代码两实例）。流程：admin 颁邀请码 → 业务方调 `/apps/register` 拿 secret → 写 env → 前端拉二维码 + 后端 finalize HMAC 校验 → 用户 upsert → 可选 JSAPI 支付。任何 Next.js / 非 Next.js MVP 项目要加微信扫码登录 / 公众号关注后登录 / 微信账号绑定 / 接入支付 都用本 skill。
---

# wx-gateway 接入

## 🔐 凭据 = 门神（vault）

业务方 register 拿到的 `WX_GATEWAY_SECRET`（以及支付场景的 `WXPAY_*`）必须 `vault add <project>/WX_GATEWAY_SECRET`，**禁止硬编码 / 禁止 `~/.credentials/.env`**。部署用 `vault inject manifest.tpl.json` 渲染。

> 网关自己的密钥（`WX_APP_SECRET` / `WX_AES_KEY` / `WX_TOKEN` / `ADMIN_*`）业务方不关心，归 `wx-gateway-operate` skill 管。

## 0. 公众号选择决策树（**先做这步**）

爸爸有两个公众号在用，**协议统一走 wx-gateway**（HMAC + finalize redirect）——只是部署成两个独立实例而已：

| 业务诉求 | 公众号 | 网关实例 | 域名 | vault prefix |
|---|---|---|---|---|
| 主流程：扫码登录 / 接支付 / OAuth 拿 openid | 「造悟者」`wx225bf76b06064faa` | **wx-gateway** | `wx.mvp.restry.cn` | `wx-gateway/*` |
| 业务必须用「莆阳网络科技」公众号（cspy / nexora 在用） | 「莆阳网络科技」`wxe780b027c2c56921` | **wx-gateway-pucs**（同份代码另一实例） | `wxmsg.mvp.restry.cn` | `wx-gateway-pucs/*` |

**两实例代码一份，差别只在 env**（DATABASE_URL / WX_APPID / PUBLIC_BASE_URL / INSTANCE_LABEL 等）。下面 §1-§3 流程**对两边都适用**——只需把"网关域名 / vault prefix"换成对应实例那一套。

> 🪦 莆阳号旧 `wx-msg-fanout` 路径已停（2026-04-29），新接入只走本 skill。

## ⚠️ access_token 必须走网关 internal API（铁律）

每个公众号 AppID **只能持有 1 个有效 access_token**——后拉的让前拉的失效。多业务方各自调 `cgi-bin/token` 一定相互挤掉，`errcode 40001 invalid credential` 间歇出现且难诊断。

**业务方代码里禁止出现 `cgi-bin/token` 调用**。改用网关 internal API,**鉴权复用 `WX_GATEWAY_SECRET`**(register 时已拿,不需要再要任何额外密钥):

```
GET https://wx.mvp.restry.cn/internal/wx-token        (造悟者实例)
GET https://wxmsg.mvp.restry.cn/internal/wx-token     (莆阳实例)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-token|<ts>|<appName>"))
  X-Ts: <ms timestamp>

Response 200: {"accessToken":"...","expiresAt":<ms>}
Response 401: 验签失败 / 时钟偏差 > 5min
Response 403: app_not_found / secret_unavailable
```

**调用建议**:业务方再叠一层本地 60s 缓存(避免每条消息都打网关),但**不要**自己 fallback 调 `cgi-bin/token`——网关挂了就报错,别自作聪明绕回去。

> 💡 **主动推消息也走网关**:`POST /internal/wx-push`,同样用 `WX_GATEWAY_SECRET` 签名(签名串 `"wx-push|<ts>|<appName>"`)。详见 `references/outbound-push.md`。**不要自己 POST cgi-bin/message/custom/send**,越权检查(A app 不能给 B app 的用户推)网关统一做。

> 🩺 **自检配置快照**:`GET /internal/wx-config`,签名串 `"wx-config|<ts>|<appName>"`。一次拿到自己 app 的元信息 + fanout endpoint/route + 绑定用户数 + access_token 状态 + 实例信息(host/appId)。消息突然没到、二维码不对、token 401 时第一时间自查,不用打扰爸爸。详见 `references/health-check.md`。

> 📱 **业务方专属永久二维码**(自助绑定):`GET /internal/wx-qrcode`,签名串 `"wx-qrcode|<ts>|<appName>"`。返自己 app 的永久参数二维码 URL,scene_str 直接 = appName。任何人扫这码 → 自动 `upsertBinding(openid, appName)`,以后该用户消息 fanout 到本 app。**彻底解决"用户从 A 站登过又去 B 站登 binding 被覆盖"问题**。详见 `references/permanent-qrcode.md`。

> 👤 **查用户身份**(关注/未关注/昵称/头像):`GET /internal/wx-userinfo?openid=...`,签名串 `"wx-userinfo|<ts>|<appName>|<openid>"`(openid 入签防越权探测)。返 `subscribed: bool` + 关注用户的 nickname/avatar/unionid/subscribeTime/scene 等。越权规则同 wx-push(只能查"绑到自己 app 的 openid",admin 旁路)。60s 缓存。详见 `references/userinfo.md`。

> 🍔 **查公众号菜单**:`GET /internal/wx-menu`,签名串 `"wx-menu|<ts>|<appName>"`。返完整 `buttons` + `myButtons`(server 预筛——**只列绑到本 app 的 click 按钮**,带 key/name/type/path[菜单层级])。业务方收到 click 事件后用这个查上下文写智能回复。详见 `references/menu-view.md`。

## 1. 网关基础信息

- 公众号回调已配在网关上，**不要在业务项目里再配回调**
- 仓库 `Restry/wx-gateway`（私有，运维归 `wx-gateway-operate` skill）
- 业务方密钥放业务方自家 vault（`<myproject>/WX_GATEWAY_SECRET`）

> 签名/payload 公式如和 `references/payment.md` 有矛盾，以 wx-gateway 仓库的 `scripts/sample-client.py` 为准（selftest 每次跑都验证它和网关代码契约一致）。

## 2. 接入步骤：邀请码 + 自助注册

所有 app 必须通过 **邀请码 + 公开 register 接口** 注册。secret 由网关现生成现下发，业务方和网关拿到的是同一份。

### 步骤 1：爸爸（网关 admin）签发邀请码

登录 admin Dashboard：`https://wx.mvp.restry.cn/_a/<ADMIN_PUBLIC_PATH>/login`（path 在 wx-gateway 生产 env，`set -a; source ~/.credentials/.env; set +a` 后 `echo $WXGATEWAY__ADMIN_PUBLIC_PATH`），扫码登录后进 **Invites** tab，点 "Create invite"：

| 字段 | 含义 | 例 |
|---|---|---|
| `appNamePrefix` | 业务方注册时 name 必须以此开头 | `copilot-proxy` |
| `allowedHostPattern` | 业务方 appBaseUrl host 必须匹配此 glob | `*.mvp.restry.cn` |
| `displayName` | 公众号 reply 用人类可读名 | `Copilot 代理` |
| `expiresIn` | 秒，1 ~ 2592000 (30d) | 86400 |
| `usesLeft` | 整数 1 ~ 100 | 1 |

提交后 admin Dashboard **只显示一次**明文 `code`（32 hex）。把 code + 上面 5 个字段一起发给业务方代理。

### 步骤 2：业务方代理调 register 接口

```sh
curl -sX POST https://wx.mvp.restry.cn/apps/register \
  -H "X-Invite-Code: <爸爸给的 32-hex code>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":         "copilot-proxy-prod",
    "appBaseUrl":   "https://copilot.mvp.restry.cn",
    "finalizePath": "/api/wx/finalize"
  }'
```

约束：
- `name` 必须以邀请码的 `appNamePrefix` 开头，且全局唯一（`/^[a-z0-9_-]+$/`）
- `appBaseUrl` host 必须匹配 `allowedHostPattern`（glob，`*` 通配单段）
- `finalizePath` 可选，默认 `/api/wx/finalize`
- `displayName` **不能**业务方传，邀请码里写死

返回（**secret 只这一次能拿到，落库前必须保存**）：
```json
{
  "name": "copilot-proxy-prod",
  "secret": "<64-hex>",
  "appBaseUrl": "https://copilot.mvp.restry.cn",
  "displayName": "Copilot 代理",
  "finalizePath": "/api/wx/finalize",
  "gatewayBase": "https://wx.mvp.restry.cn"
}
```

### 步骤 3：业务方写 env

```
WX_GATEWAY_BASE=https://wx.mvp.restry.cn
WX_GATEWAY_APP_NAME=copilot-proxy-prod
WX_GATEWAY_SECRET=<返回的 secret>
NEXT_PUBLIC_WX_GATEWAY_BASE=https://wx.mvp.restry.cn
NEXT_PUBLIC_WX_GATEWAY_APP_NAME=copilot-proxy-prod
```

`NEXT_PUBLIC_*` 是 build-time 内联，部署前要进生产 .env 然后重 build。

### 失败码速查（register 接口）

| code | 意思 | 修法 |
|---|---|---|
| `missing_invite` | header 没传 | 加 `X-Invite-Code` header |
| `invalid_invite` | code 错 / 不存在 | 找爸爸要正确 code |
| `expired_invite` | 邀请码过期 | 重发一份 |
| `exhausted_invite` | usesLeft 已 0 | 重发一份 |
| `name_prefix_mismatch` | name 没以 prefix 开头 | 改 name |
| `host_mismatch` | host 不匹配 pattern | 改 appBaseUrl 或让爸爸放宽 pattern |
| `name_taken` | name 全局已存在 | 换名（建议带 `-prod` / `-staging` 后缀）|
| `invalid_app_base_url` | 必须 https + 公网域名 | 不能填 localhost / 内网 IP |

注册接口直接落 DB（App 表），网关运行时读 DB 秒级生效，爸爸只发邀请码不碰部署。

### 步骤 4：业务项目前端：扫码登录页

```tsx
"use client";
import { useEffect, useState } from "react";

export default function WxScanLogin() {
  const [qr, setQr] = useState<{ token: string; qrcodeUrl: string } | null>(null);
  const [status, setStatus] = useState<string>("loading");

  async function refreshQr() {
    setStatus("loading");
    const r = await fetch(
      `${process.env.NEXT_PUBLIC_WX_GATEWAY_BASE}/wx/qr/${process.env.NEXT_PUBLIC_WX_GATEWAY_APP_NAME}`,
      { method: "POST" }
    );
    const data = await r.json();
    if (!data.ok) { setStatus("error"); return; }
    setQr({ token: data.token, qrcodeUrl: data.qrcodeUrl });
    setStatus("pending");
  }

  useEffect(() => { refreshQr(); }, []);

  useEffect(() => {
    if (!qr) return;
    const es = new EventSource(
      `${process.env.NEXT_PUBLIC_WX_GATEWAY_BASE}/wx/poll/${qr.token}`
    );
    es.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      setStatus(data.status);
      if (data.status === "confirmed" && data.redirect) {
        es.close();
        window.location.href = data.redirect;     // → /api/wx/finalize?...
      }
      if (data.status === "expired" || data.status === "timeout") {
        es.close();
        refreshQr();                              // 重拉一张
      }
    };
    es.onerror = () => { es.close(); refreshQr(); };
    return () => es.close();
  }, [qr?.token]);

  return (
    <div>
      {qr && <img src={qr.qrcodeUrl} alt="微信扫码" />}
      <p>状态：{status}</p>
    </div>
  );
}
```

注意：
- gateway 的 SSE 30s 超时返 `timeout`，前端必须自动重拉
- `NEXT_PUBLIC_*` 暴露在客户端没问题，**secret 绝不能 NEXT_PUBLIC_**
- SSE 推送的状态码完整列表：`pending | scanned | confirmed | rejected | expired | timeout | error`

### 状态展示与「强制 OAuth 完善信息」（可选开关）

默认行为：用户扫码 → 立即 `confirmed` → 跳 finalize。业务方拿到 `openid` / `unionid`，**没有 nickname / avatar**。

如果业务方需要昵称头像，admin Dashboard `Apps` 编辑里打开 **「强制完善信息」(`requireProfileCompletion`)** 开关。开关 ON 后流程变为：

| SSE status | 含义 | 前端应做 |
|---|---|---|
| `pending` | 二维码已生成，等待扫码 | 显示二维码 + "请用微信扫码" |
| `scanned` | 用户已扫码，但还没点公众号回的 OAuth 链接 | 显示 ✅ 已扫码 + "请点击微信中收到的链接完善个人信息" |
| `confirmed` | OAuth 完成，拿到 nickname/avatar | 立即 `window.location.href = data.redirect` |
| `rejected` | 用户在微信授权页点了"拒绝" | 显示 ❌ 已取消授权 + "请重新扫码" → 重拉 QR |
| `expired` / `timeout` | 二维码过期 / SSE 超时 | 重拉 QR |

前端示例 patch（在上面 `WxScanLogin` 的 `es.onmessage` 里加分支）：

```tsx
es.onmessage = (ev) => {
  const data = JSON.parse(ev.data);
  setStatus(data.status);
  if (data.status === "confirmed" && data.redirect) {
    es.close();
    window.location.href = data.redirect;
  }
  if (data.status === "rejected" || data.status === "expired" || data.status === "timeout") {
    es.close();
    refreshQr();
  }
  // pending / scanned: 继续等，UI 按 status 展示文案即可
};
```

UI 文案推荐：
- `pending` → 「请使用微信扫描二维码」
- `scanned` → 「✅ 已扫码，请点击微信中收到的链接完善个人信息」
- `rejected` → 「❌ 授权已取消，请重新扫码」

### 步骤 5：业务项目后端：`/api/wx/finalize`

```ts
// app/api/wx/finalize/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const SECRET = process.env.WX_GATEWAY_SECRET!;
const MAX_SKEW_MS = 5 * 60 * 1000;

function verifySig(p: { token: string; openid: string; unionid: string; ts: string; sig: string }) {
  const expected = createHmac("sha256", SECRET)
    .update(`${p.token}|${p.openid}|${p.unionid}|${p.ts}`)
    .digest("hex");
  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(p.sig, "hex");
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const token   = sp.get("token")   ?? "";
  const openid  = sp.get("openid")  ?? "";
  const unionid = sp.get("unionid") ?? "";
  const ts      = sp.get("ts")      ?? "";
  const sig     = sp.get("sig")     ?? "";

  if (!token || !openid || !ts || !sig)
    return NextResponse.redirect(new URL("/login?err=missing", req.url));
  if (Math.abs(Date.now() - Number(ts)) > MAX_SKEW_MS)
    return NextResponse.redirect(new URL("/login?err=expired", req.url));
  if (!verifySig({ token, openid, unionid, ts, sig }))
    return NextResponse.redirect(new URL("/login?err=sig", req.url));

  // ⚠️ 不要再做 wxFinalizeLog 一次性消费防重放——
  //    OAuth 补全 nickname/avatar 时同一 token 会被微信重新签发回业务方，
  //    若拒绝第二次会导致永远拿不到头像昵称。详见后面「OAuth 补全」节。
  //    token 已有 5min skew + HMAC 校验，安全够用。

  // upsert 用户：unionid 优先（跨公众号/小程序稳定），fallback openid
  const user = await prisma.user.upsert({
    where: unionid
      ? { wechatUnionid: unionid }
      : { wechatOpenid: openid },
    create: {
      wechatOpenid: openid,
      wechatUnionid: unionid || null,
      name: `微信用户${openid.slice(-6)}`,
    },
    update: { wechatOpenid: openid, wechatUnionid: unionid || null },
  });

  await prisma.wxFinalizeLog.create({ data: { token, userId: user.id } });

  // 业务自管 session
  const sessionId = await mintSession(user.id);
  const res = NextResponse.redirect(new URL("/app", req.url));
  res.cookies.set("session", sessionId, {
    httpOnly: true, sameSite: "lax", path: "/",
    secure: req.nextUrl.protocol === "https:",
    maxAge: 60 * 60 * 24 * 30,
  });
  return res;
}
```

### 步骤 6：Prisma schema 增量

```prisma
model User {
  // ... 已有字段
  wechatOpenid  String?  @unique
  wechatUnionid String?  @unique
}

// ⚠️ 不要加 WxFinalizeLog 一次性消费表——见 finalize 注释，会拦截 OAuth 补全
```

跑 `prisma migrate dev --name add_wx_login` 或 `prisma db push`。

### 步骤 7：验证（强制 browser-agent skill）

派 Claude Code 用 browser-agent skill（端口 4822）做 E2E：
1. 业务项目 `/login` 显示二维码
2. 调 `POST {gateway}/wx/qr/{app}` 返回 `qrcodeUrl` (不是 placehold.co)
3. SSE `/wx/poll/{token}` 持续推 `pending`
4. 真扫码后 SSE 推 `confirmed` + `redirect`，浏览器跳到 finalize → 落 `/app`
5. cookie 设上，后续请求带 session 可访问 `/app`

不要让爸爸/Hermes 代跑浏览器。


## 进阶专题（按需加载）

本 SKILL.md 只覆盖**最常见的扫码登录基础接入**。下列专题按需加载：

| 场景 | 文件 |
|---|---|
| 业务方用 NextAuth v5 / Auth.js | `references/nextauth-v5.md` |
| 需要展示用户头像 / 昵称（snsapi_userinfo OAuth 补全） | `references/oauth-profile-completion.md` |
| 业务方需要向用户收款（订阅、套餐、充值额度、商品销售、SaaS 任何收钱场景） | `references/payment.md` |
| 业务方主动给用户推消息(任务完成通知、客服回复、订阅模板) | `references/outbound-push.md` |
| 自检接入配置(查 fanout/route/binding/token 是否就绪) | `references/health-check.md` |
| 业务方专属永久二维码(发海报 / 邀请页 / 自动 binding) | `references/permanent-qrcode.md` |
| 查用户身份(是否关注公众号 + nickname/avatar/unionid) | `references/userinfo.md` |
| 查公众号菜单(写 click 事件回复 / 知道自己绑了哪些按钮) | `references/menu-view.md` |
| 接入失败排查 / 反模式 | `references/troubleshooting.md` |

加载方式：`skill_view(name="wx-gateway-integrate", file_path="references/<file>")`

## 模板消息 & 订阅通知（2026-05-17）

公众号有两类「主动推」：

| 类型 | 触发条件 | 微信端点 | wx-push `type` |
|---|---|---|---|
| 模板消息 | 服务号用户已关注 | `cgi-bin/message/template/send` | `template` |
| 一次性订阅通知 | 用户在前端 `wx.requestSubscribeMessage` 授权 | `cgi-bin/message/subscribe/bizsend` | `subscribe` |

⚠️ `subscribe/bizsend` 是**服务号一次性订阅通知**端点；不要跟小程序的 `subscribe/send` 混（payload 字段完全不一样）。前端授权流程见 [微信官方文档](https://developers.weixin.qq.com/doc/offiaccount/Subscription_Messages/intro.html)。

### 拉可用模板清单

`GET /internal/wx-template/list?enabledOnly=1` —— 只返 admin 在 Panel 勾选了「启用」的模板。省 `enabledOnly` 时返全部（每条带 `enabled` 字段，业务方自行筛）。

HMAC payload 拼法：`"wx-template-list|<ts>|<appName>"`。

```bash
TS=$(date +%s%3N)
SIG=$(printf 'wx-template-list|%s|%s' "$TS" "$APP" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
curl -s "$GW/internal/wx-template/list?enabledOnly=1" \
  -H "X-App-Name: $APP" -H "X-Ts: $TS" -H "X-Internal-Auth: $SIG"
```

返回：
```json
{ "items": [
  { "templateId": "OPENID...", "title": "...", "content": "{{name.DATA}}", "kind": "template", "enabled": true, ... }
] }
```

> 网关 `/internal/wx-push` **不校验** enabled、**不校验** toUser→app binding。enabled 只是 admin 给业务方看的「可用清单」协议，业务方自觉只发自己用户、只用启用模板。

### 发模板消息 / 订阅通知

签名串：`"wx-push|<ts>|<appName>"`。

**curl 示例 (模板消息)：**
```bash
TS=$(date +%s%3N)
SIG=$(printf 'wx-push|%s|%s' "$TS" "$APP" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
curl -s "$GW/internal/wx-push" \
  -H "Content-Type: application/json" \
  -H "X-App-Name: $APP" -H "X-Ts: $TS" -H "X-Internal-Auth: $SIG" \
  -d '{
    "toUser": "oXxx_user_openid",
    "type": "template",
    "payload": {
      "template_id": "TEMPLATE_ID",
      "url": "https://yourapp.example.com/order/123",
      "data": { "name": { "value": "张三" }, "amount": { "value": "￥99" } }
    }
  }'
```

**Node 示例 (订阅通知)：**
```js
import { createHmac } from "node:crypto";
const ts = String(Date.now());
const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
  .update(`wx-push|${ts}|${process.env.WX_GATEWAY_APP_NAME}`).digest("hex");

const r = await fetch(`${process.env.WX_GATEWAY_BASE}/internal/wx-push`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-App-Name": process.env.WX_GATEWAY_APP_NAME!,
    "X-Ts": ts,
    "X-Internal-Auth": sig,
  },
  body: JSON.stringify({
    toUser: openid,
    type: "subscribe",
    payload: {
      template_id: priTmplId,
      page: "index.html",                       // 可选 H5 链接（须在授权域内）
      data: { thing1: { value: "订单已发货" }, time2: { value: "2026-05-17 12:00" } },
    },
  }),
});
const j = await r.json(); // { ok, errcode, errmsg, msgId }
```

返回 `{ok: errcode===0, errcode, errmsg, msgId}`。`errcode !== 0` 时业务方自行决定降级（重试 / 转邮件 / 弃）。

### 签名拼法速查

| scope | payload 字符串 |
|---|---|
| 拉模板列表 | `wx-template-list\|<ts>\|<appName>` |
| 推消息（含 template/subscribe/custom） | `wx-push\|<ts>\|<appName>` |
| 拉 access_token（**禁用**，业务方走 wx-push 代理即可） | `wx-token\|<ts>\|<appName>` |
| 拉用户信息 | `wx-userinfo\|<ts>\|<appName>\|<openid>` |

### 端点速查

| wx-push `type` | 微信端点 |
|---|---|
| `template` | `https://api.weixin.qq.com/cgi-bin/message/template/send` |
| `subscribe` | `https://api.weixin.qq.com/cgi-bin/message/subscribe/bizsend` |
| `custom` | `https://api.weixin.qq.com/cgi-bin/message/custom/send` |

---

## 关联 skills

| skill | 用途 |
|---|---|
| `wx-gateway-operate` | wx-gateway 网关本身的运维（改代码 / 加 app / selftest / 部署） |
| `mvp-deployer` | 部署平台 |

---

## 用户绑定（网关自动完成，业务方零感知）

一个公众号下挂多个业务 app 时，gateway 按 openid 路由消息。**绑定由网关在 OAuth/扫码完成时自动写入**——业务方不调任何 binding API。同一 openid 在多个 app 登录过：最后一次赢。

排错：消息没到预期 app → 查 `UserAppBinding` 表 + `FanoutLog.boundApp`。process 缓存 60s，跨 worker 切换可能滞留。**单 app 场景** 可完全忽略绑定。
