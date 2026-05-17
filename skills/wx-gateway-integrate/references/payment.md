# 接入「支付」能力（v1：个人收款码人工审核）

## 目录

- **§1 v1 personal_qr 个人收款码 + 人工审核** (本文件 1-223 行)
  - 设计前提 / 4 个接口 (`/pay/create`, `/pay/personal/claim`, `/pay/status`, webhook)
  - 业务方实现骨架 + 反模式
- **§2 v2 wxpay_jsapi 微信官方支付** (224-406 行)
  - 唯一推荐：**统一付款页跳转**（gateway 托管支付 H5）
  - 业务方只调 1 个接口 + 收 1 个 webhook
- **§3 内部技术参考** (407 行起，业务方一般不需要看)

> 选择：**新接入直接读 §2**（微信官方支付，安全合规）。§1 仅维护已有 personal_qr 项目时参考。

---


⚠️ **触发**：业务方需要向用户收款（订阅、套餐、充值额度）。
**不触发**：单纯扫码登录的项目——不需要本节，回 SKILL.md 主流程。

⚠️ **触发**：业务方需要向用户收款（订阅、套餐、充值额度）。
**不触发**：单纯扫码登录的项目——不需要本节。

### 设计前提（拍板事项，不要再问）

- **Backend**：v1 仅支持 `personal_qr` —— 微信个人收款码（爸爸的码）+ 备注码 + admin 人工审核到账。jsapi/native 暂不实装，路由占位返 501
- **审核全在网关**：业务方**不需要**自己做审核 UI / 监听端 / 微信对账。爸爸在网关 admin Dashboard `Payments` tab 一键 approve / reject
- **业务方只调 4 件事**：`POST /pay/create`、`POST /pay/personal/claim`、`GET /pay/status/<id>`、收 webhook
- **金额**：整数分（fen），单笔上限 200 RMB（20000 fen）
- **签名**：HMAC-SHA256(secret, payload) hex；header 三件套 `X-WX-App-Name` / `X-WX-Sig` / `X-WX-Ts`。**payload 不是 raw_body**，每个接口的 payload 拼法不同，见各接口章节
- **secret 是 64 hex 字符的字符串**，HMAC 时**直接当 utf-8 字符串传 key**（不是 hex→bytes）。例：`createHmac("sha256", secret)`、`hmac.new(secret.encode(), ...)`
- **二维码**：每个 app 独立配置（admin Dashboard 上传），未配置 `/pay/create` 返 503

### 4 个接口

#### 1. `POST /pay/create` — 创建订单

请求 header：
```
X-WX-App-Name: <你的 app name>
X-WX-Ts:       <毫秒时间戳，5 分钟内>
X-WX-Sig:      hmac_sha256(secret_bytes, "<appName>|<orderId>|<amount_fen>|<ts>") hex
Content-Type:  application/json
```

⚠️ payload 是 4 段竖线拼接，**不是 raw_body**。例：
```
appName=copilot-proxy, orderId=ord_123, amount_fen=9900, ts=1735000000000
→ payload = "copilot-proxy|ord_123|9900|1735000000000"
→ X-WX-Sig = HMAC-SHA256(secret, payload).hexdigest()      # secret 直接当字符串
```

请求 body：
```json
{
  "orderId":     "your_internal_order_123",   // 你自家订单号，[a-zA-Z0-9_-]{1,64}
  "amount_fen":  9900,                          // 整数 1..20000
  "method":      "personal_qr",                 // 唯一支持值
  "subject":     "Pro 月度套餐",                // 用户能看到的描述，≤30 字
  "expiresIn":   1800,                          // 秒，默认 1800，最长 7200
  "userNote":    "openid:o123abc",              // 任意，用于审核辅助；≤200 字
  "openid":      "o123abc..."                   // 可选，传了能在 admin tab 显示
}
```

返回 200：
```json
{
  "payOrderId":  "pay_01HX...",                // 网关侧主键，后续都用它
  "qrcodeUrl":   "https://wx.mvp.restry.cn/payment/qr/<app>-<8hex>.png",
  "remark":      "K7M2QX",                     // 6 位备注码，base32 去歧义字符
  "amount_fen":  9900,
  "expiresAt":   "2026-04-29T12:34:56.789Z",
  "status":      "pending"
}
```

幂等：**同一 (appName, orderId) 重复调返已存在那条**，不报错。所以业务方网络重试是安全的。

错误码：
| code | 说明 |
|---|---|
| 400 amount_out_of_range | amount_fen 不在 1..20000 |
| 400 invalid_order_id | orderId 不符合正则 |
| 400 invalid_method | method !== "personal_qr" |
| 400 invalid_expires_in | expiresIn 越界 |
| 401 missing_signature | header 三件套不全 |
| 403 invalid_signature / expired_signature | sig 错或时钟偏 > 5 分钟 |
| 404 app_not_found | appName 不存在或 revoked |
| 501 not_implemented_yet | method 是 jsapi/native |
| 503 personal_qr_not_configured | app 没在 admin Dashboard 配二维码 |

#### 2. `POST /pay/personal/claim` — 用户「我已付款」

用户付完款点「我已付款」时调。HMAC payload 拼法：`<appName>|<payOrderId>|<ts>`。body：
```json
{
  "payOrderId":   "pay_01HX...",
  "screenshotUrl": "https://yourapp.com/uploads/proof.jpg"  // 可选，截图证据；https + 业务方同源域
}
```

返回 200：
```json
{ "payOrderId": "pay_01HX...", "status": "submitted" }
```

错误：`409 state_invalid`（订单不在 pending；可能已 paid / expired / disputed）。

#### 3. `GET /pay/status/<payOrderId>` — 查状态

带签查（HMAC payload 拼法：`<appName>|<payOrderId>|<ts>`）。返回：
```json
{
  "payOrderId":  "pay_01HX...",
  "orderId":     "your_internal_order_123",
  "amount_fen":  9900,
  "status":      "submitted",   // pending|submitted|paid|disputed|expired
  "remark":      "K7M2QX",
  "createdAt":   "...",
  "submittedAt": "...",
  "paidAt":      null,
  "rejectReason": null
}
```

业务方一般不需要 poll 这个——靠 webhook 推送即可。仅作兜底 / 用户主动刷新时用。

#### 4. Webhook：网关 → 业务方

业务方在 admin Dashboard 注册 `webhookUrl`（每个 app 一个），网关在状态变化时 POST 该 URL：

请求 header：
```
X-WX-Webhook-Sig: hmac_sha256(secret, "<event>|<payOrderId>|<status>|<ts>") hex
X-WX-Webhook-Ts:  <毫秒时间戳>
Content-Type:     application/json
```

请求 body：
```json
{
  "event":      "payment.paid",          // payment.paid | payment.disputed | payment.expired
  "payOrderId": "pay_01HX...",
  "orderId":    "your_internal_order_123",
  "status":     "paid",
  "amount_fen": 9900,
  "paidAt":     "2026-04-29T12:34:56.789Z",
  "externalRef": "微信收款记录里的对账号"  // approve 时 admin 录入
}
```

业务方必须返 2xx。否则按 `[0, 30s, 2m, 10m, 1h, 6h, 24h]` 退避重试 6 次失败 dead。dead 的 webhook 在 admin Dashboard 单行「重投」按钮可重置。

业务方收到后：
1. **验签**：用自己的 secret 算 HMAC，对比 `X-WX-Webhook-Sig`，5 分钟内
2. **幂等**：同一 `payOrderId` 多次推送只处理一次（网关重投 + 业务方重启叠加可能多次）
3. **回 200**：哪怕业务侧已是同状态也回 200，避免无意义重投

### 业务方典型实现（最小骨架）

```ts
// /api/checkout/create.ts
import crypto from "node:crypto";
const order = await db.payment.create({ /* internal order */ });
const ts = Date.now();
const amount_fen = 9900;
// ⚠️ 签 4 段竖线 payload，不是 body；secret 直接当字符串
const payload = `${APP_NAME}|${order.id}|${amount_fen}|${ts}`;
const sig = crypto.createHmac("sha256", SECRET).update(payload).digest("hex");
const r = await fetch(`${WX_GATEWAY}/pay/create`, {
  method: "POST",
  headers: { "X-WX-App-Name": APP_NAME, "X-WX-Ts": String(ts), "X-WX-Sig": sig, "Content-Type": "application/json" },
  body: JSON.stringify({ orderId: order.id, amount_fen, method: "personal_qr", subject, openid: user.openid }),
});
const { qrcodeUrl, remark, payOrderId } = await r.json();
return { qrcodeUrl, remark, payOrderId };  // 前端拿去显示
```

```tsx
// 前端付款页
<img src={qrcodeUrl} />
<div className="bg-red-50 border-2 border-red-500 p-4 text-2xl font-mono">
  付款时务必填写备注 <strong>{remark}</strong>，否则到账延迟 24h+
</div>
<button onClick={async () => {
  await fetch("/api/checkout/claim", { method:"POST", body: JSON.stringify({ payOrderId }) });
  setStatus("等待审核");
}}>我已付款</button>
```

```ts
// /api/wx/payment-webhook.ts
import crypto from "node:crypto";
const sig = req.headers["x-wx-webhook-sig"] as string;
const ts  = req.headers["x-wx-webhook-ts"] as string;
if (Math.abs(Date.now() - Number(ts)) > 5*60*1000) return res.status(403).end();
const expected = crypto.createHmac("sha256", SECRET)
  .update(`${body.event}|${body.payOrderId}|${body.status}|${ts}`).digest("hex");
if (!crypto.timingSafeEqual(Buffer.from(sig,"hex"), Buffer.from(expected,"hex"))) return res.status(403).end();
// 幂等：先查内部 status
const existing = await db.payment.findUnique({ where: { payOrderId: body.payOrderId } });
if (existing.status === body.status) return res.status(200).end();
// 改状态 + 给用户加额度
await db.$transaction([ /* update order, grant credits, etc. */ ]);
return res.status(200).end();
```

### 业务方需要做的 / 不需要做的

| 业务方做 | 业务方不做（网关做） |
|---|---|
| 自家 Payment 表（payOrderId, internal orderId, userId, status） | 二维码生成 / 上传 |
| 4 个 fetch 调用 + HMAC | 备注码生成、唯一性、过期 |
| 前端：扫码 + 备注大字红框 + 「我已付款」按钮 | 用户「待审核」状态展示 |
| webhook handler：验签 + 幂等 + 改状态 + 加额度 | 微信收款对账（爸爸人工） |
| 用户订单列表（自家页） | 审核 UI、approve/reject、disputed 处理 |

### 测试 checklist（首次接入必跑）

1. **真钱 1 分钱**：业务方代理账号付 0.01 RMB，全链路打通到 webhook 收到 `paid`
2. **错备注**：故意填错备注码，admin Dashboard 应能看到这单，**reject** 后业务方收 `payment.disputed` webhook
3. **不付让过期**：create 后什么都不做，等 expiresIn 过去，业务方收 `payment.expired` webhook
4. **webhook 重试**：业务方 webhook handler 故意第一次返 500，第二次 200——验证网关按退避重试到成功

### 反模式

- ❌ 业务方做自家审核 UI / 跑监听端拉微信流水（v1 全部走 admin 人工，不省心也不靠谱）
- ❌ 直接 cookie / session 调网关支付接口（必须 HMAC）
- ❌ amount_fen 用 float（整数分）
- ❌ orderId 用 UUID 之外的奇怪字符（`[a-zA-Z0-9_-]{1,64}`）
- ❌ webhook handler 不做幂等（重投会重复加额度）
- ❌ webhook handler 不验签（任何人都能伪造 paid 给自己加额度）
- ❌ 前端不显示备注码或字号小于 24px（爸爸看不清就拒审）
- ❌ 把网关返的 `qrcodeUrl` 复制成自家域名做"图床优化"（cache TTL 不可控，爸爸换码后业务方还在用旧码）

---

# 接入「支付」能力（v2：微信官方 JSAPI 支付，统一付款页模式）

⚠️ **触发**：业务方在公众号 / 服务号 H5 内向用户收款。商户号、APIv3 key、证书已由网关 admin 录入（业务方代码里**不应该**出现这些值）。
**不触发**：只在网页 / PC / 非微信浏览器收款 → 走 v1 personal_qr 即可。

> 本节与 v1 personal_qr **并存**。每个 app 在 admin Dashboard 上**二选一**（`paymentChannel` 字段）。v1 章节的 HMAC、header、错误码体系**全部沿用**，本节只列差异。

---

## 🎯 唯一推荐路径：统一付款页跳转（2026-04-30 之后所有新接入项目都走这条）

业务方**只做 3 件事**：调 `/pay/create`、跳转、收 webhook。**不调 prepay、不调 wx.chooseWXPay、不碰证书、不申请微信支付授权目录**。

### 接入痛点回顾

业务方自家域名调 `wx.chooseWXPay()` 时，微信会校验 JSAPI 授权目录必须包含业务方页面路径。商户号最多 5 个授权目录，每接一个新业务方就要去微信商户后台改一次，配额很快用完，且改授权目录是**人工**操作，无法自动化。

### 解决方案

把 `wx.chooseWXPay` 搬到 wx-gateway 自家的统一付款页。所有业务方共用 `https://wx.mvp.restry.cn/pay/` **一个**授权目录，**永远只配一次**。

### 业务方 3 步接入

1. 业务方拿到用户 openid（自己 OAuth 得来）后调 `POST /pay/create`，body **必须**带 `openid` + `returnUrl`：
   - `returnUrl` = 付款完成后用户回到的业务方页面（推荐带个 `?paid=1` 这类 marker 让前端触发余额刷新轮询）
   - 必须 https + host 等于该 app 的 `appBaseUrl`，否则 gateway 静默 fallback 到 `appBaseUrl` 根
2. 拿响应里 `wxpay.checkoutUrl`（形如 `https://wx.mvp.restry.cn/pay/checkout/<payOrderId>?t=<48hex>`）
3. 前端 `window.location.href = checkoutUrl` 跳转

之后全自动：
- 用户看到 wx-gateway 渲染的统一付款页（"商家名 + 金额 + 立即支付"）
- 点"立即支付"→ gateway 内部调 prepay → 同页调 `wx.chooseWXPay`
- 付完 → 跳回 `returnUrl`
- 取消/失败 → 留在付款页可重试
- 加 credits / 改订单状态 → **只走 webhook**（见下，业务方必须实现）

### 商户后台一次性配置（仅 daddy 操作）

JSAPI 授权目录：`https://wx.mvp.restry.cn/pay/`（**一次配，永不再动**）
notify_url：**不需要**在商户后台配（每次 prepay 时由 gateway 动态传 path-style URL）

### 业务方最小代码模板（可直接照抄到任何 Next.js 项目）

#### A. `POST /api/checkout/start` —— 用户点付款的入口

```ts
// 不分什么 channel；如果项目还要保留个人收款码 fallback，自己 if 切
import crypto from "node:crypto";

const APP   = process.env.WX_GATEWAY_APP_NAME!;
const SEC   = process.env.WX_GATEWAY_SECRET!;
const GW    = process.env.WX_GATEWAY_BASE!;       // https://wx.mvp.restry.cn
const BASE  = process.env.PUBLIC_BASE_URL!;       // https://yourapp.mvp.restry.cn

function sign(payload: string) {
  return crypto.createHmac("sha256", SEC).update(payload).digest("hex");
}

export async function POST(req: Request) {
  const user = await getSessionUser(req);                          // 你的 session 实现
  if (!user?.wechatOpenid) return Response.json(
    { error: { code: "missing_openid", message: "请先用微信扫码登录" }}, { status: 400 });

  const { tierLabel } = await req.json();                          // 业务挑档/选商品
  const { amountFen, credits, subject } = lookupTier(tierLabel);   // 业务自己实现

  const orderId = crypto.randomBytes(16).toString("hex");          // 业务自家订单号
  // ⚠️ 落业务自家订单（status=pending），webhook 来时按 payOrderId 找回来
  await db.payment.create({ data: {
    orderId, payOrderId: "", userId: user.id, amountFen, credits,
    channel: "wxpay_jsapi", status: "pending", openid: user.wechatOpenid,
  }});

  const ts = Date.now();
  const r = await fetch(`${GW}/pay/create`, {
    method: "POST",
    headers: {
      "X-WX-App-Name": APP,
      "X-WX-Ts":  String(ts),
      "X-WX-Sig": sign(`${APP}|${orderId}|${amountFen}|${ts}`),    // payload = appName|orderId|amount_fen|ts
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      orderId,
      amount_fen: amountFen,
      method:  "wxpay_jsapi",
      subject,
      openid:  user.wechatOpenid,
      returnUrl:  `${BASE}/topup?paid=1`,                           // 付完跳回这里
      webhookUrl: `${BASE}/api/wx/payment-webhook`,                 // 必传，否则 gateway 没地方推
    }),
  });
  const data = await r.json();
  if (!r.ok || !data.wxpay?.checkoutUrl) {
    return Response.json({ error: { code: "checkout_url_missing", message: data.error?.message ?? "支付发起失败" }}, { status: 502 });
  }

  await db.payment.update({ where: { orderId }, data: { payOrderId: data.payOrderId }});
  return Response.json({ checkoutUrl: data.wxpay.checkoutUrl });
}
```

#### B. `POST /api/wx/payment-webhook` —— gateway 推过来加 credits

```ts
import crypto from "node:crypto";

export async function POST(req: Request) {
  const sig = req.headers.get("x-wx-webhook-sig") ?? "";
  const ts  = req.headers.get("x-wx-webhook-ts")  ?? "";
  if (Math.abs(Date.now() - Number(ts)) > 5*60*1000) return new Response(null, { status: 403 });

  const body = await req.json();
  const expected = crypto.createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`${body.event}|${body.payOrderId}|${body.status}|${ts}`)             // payload = event|payOrderId|status|ts
    .digest("hex");
  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(sig, "hex");
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return new Response(null, { status: 403 });

  // 幂等查
  const p = await db.payment.findUnique({ where: { payOrderId: body.payOrderId }});
  if (!p) return new Response("ok", { status: 200 });            // 找不到也回 200，避免 gateway 死循环重投
  if (p.status === body.status) return new Response("ok", { status: 200 });

  if (body.event === "payment.paid") {
    await db.$transaction([
      db.payment.update({ where: { id: p.id }, data: { status: "paid", paidAt: new Date() }}),
      db.user.update({ where: { id: p.userId }, data: { balance: { increment: p.credits }}}),
      db.creditLedger.create({ data: { userId: p.userId, amount: p.credits, reason: "wxpay", memo: p.payOrderId }}),
    ]);
  } else {
    await db.payment.update({ where: { id: p.id }, data: { status: body.status }});
  }
  return new Response("ok", { status: 200 });
}
```

#### C. 前端最小骨架（无 SDK，无 jweixin，无 wx.chooseWXPay）

```tsx
"use client";
async function handlePay(tierLabel: string) {
  const r = await fetch("/api/checkout/start", { method: "POST", body: JSON.stringify({ tierLabel }) });
  const data = await r.json();
  if (!r.ok || !data.checkoutUrl) { alert(data.error?.message ?? "支付发起失败"); return; }
  window.location.href = data.checkoutUrl;     // 全部交给 gateway
}

// 付完跳回时（returnUrl 带 ?paid=1），mount 时 5 次 1.5s 轮询余额
useEffect(() => {
  if (typeof window === "undefined") return;
  if (!new URLSearchParams(window.location.search).get("paid")) return;
  let i = 0;
  const t = setInterval(async () => {
    const r = await fetch("/api/user/me").then(r => r.json());
    setBalance(r.balance);
    if (++i >= 5) clearInterval(t);
  }, 1500);
  history.replaceState(null, "", window.location.pathname);
  return () => clearInterval(t);
}, []);
```

### 安全模型（写死了，照搬别瞎改）

- **加 credits 唯一可信来源 = webhook**。`?paid=1` 是 UI 暗号不是支付凭证，用户瞎拼 `/topup?paid=1` 加不了任何 credit
- **webhook 必须三件事**：HMAC 验签 + 5min skew + 按 payOrderId 幂等。任何一件漏了 = 用户能伪造无限 credit
- **returnUrl 防开放重定向**：gateway 端做了 host 校验（必须 = `app.appBaseUrl` 的 host），业务方再传 URL 上 `return=evil.com` 也无效
- **payment 表落两条 id**：`orderId`（业务自家）+ `payOrderId`（gateway 返）。webhook 只带 `payOrderId`，建索引

### 已知坑（爸爸 2026-04-30 实测踩的）

- ❌ `?paid=1` 写到 ledger 触发 → 整个安全模型崩。**只**触发 UI 轮询
- ❌ 在 `wx.chooseWXPay` 回调里加 credits → 用户能 hack 回调。只信 webhook
- ❌ 业务方域名加 JSAPI 授权目录 → 浪费 5 个配额。新模式不需要业务方域名出现在授权目录
- ❌ 没传 `returnUrl` → 付完用户卡在 gateway done 页，回不去你的页
- ❌ 没传 `webhookUrl` → gateway 收到微信回调但**推不到业务方**，credit 永远不到账
- ❌ 商户后台填 `notify_url` → JSAPI 用动态 path-style，**不需要**在商户后台配
- ⚠️ 付款时返 `NO_AUTH:此商家的收款功能已被限制` → **不是代码问题**，是商户号在微信侧被限制（新进件未审核 / 未开通 JSAPI 产品 / 风控冻结 / mch 与 appid 没绑定），登微信商户平台看原因

---

## ⚙️ 内部技术参考（业务方一般不需要看）

下面是 `/pay/create` / `/pay/wxpay/jsapi/prepay` / webhook 的接口定义。**业务方走推荐路径只调 `/pay/create`**，不需要直调 prepay。下方保留是为了：(a) 老接入向后兼容，(b) 极少数业务方要自己定制付款页 UI。

### 设计前提（拍板事项）

- **per-app 商户号**：每个 app 在 admin Dashboard `wxpay-config` 单独配置自己的微信支付凭据（`mchId` / `wxpayAppId` / `apiV3Key` / `certSerial` / `privateKeyPem`）。网关用 `WXPAY_ENCRYPTION_KEY` 在 DB 内 AES 加密存储。
- **网关代签发 prepay**：业务方**不直接调微信支付 API**，全部走 gateway。gateway 持证书，请求 `POST https://api.mch.weixin.qq.com/v3/pay/transactions/jsapi`，把返的 `prepay_id` 二次 RSA 签名后下发给业务方前端。
- **网关接收 wxpay 回调**：微信支付 → gateway `/pay/wxpay/notify?app=<appName>` 验签 + AES-GCM 解密 + 状态机更新 + 触发 webhook。**业务方不需要管这个 URL**，不要在微信支付商户后台填业务方域名。
- **业务方只调 2 件事 + 收 webhook**：`POST /pay/create`（method=wxpay_jsapi）→ `POST /pay/wxpay/jsapi/prepay` → 前端 `wx.chooseWXPay` → 等 webhook。`/pay/status/<id>` 仍可用作兜底查询。
- **没有 personal_qr 的 remark 概念**：v2 不需要备注码，钱直接走商户号入账，不走人工审核。
- **HMAC / secret 用法**：与 v1 **完全一致**（`X-WX-App-Name` / `X-WX-Sig` / `X-WX-Ts` 三件套，secret 当 utf-8 字符串传 key）。
- **金额上限**：复用 v1 `app.maxAmountFen`（admin 可调，默认 20000 fen=200 RMB；商户号实战经常上调到 100000+，找爸爸改）。

### admin 配置流程（业务方读，但不自己干 — 找爸爸）

接入前必须在 admin Dashboard 内完成：

1. 点 app → `wxpay-config` tab → 上传/填入：
   - `paymentChannel`：`wxpay_jsapi`
   - `mchId`：8–32 位数字（微信支付商户号）
   - `wxpayAppId`：`wx[0-9a-zA-Z]{14,30}`（公众号 / 小程序 appid，**不是** app.name）
   - `apiV3Key`：32 位字母数字（商户后台「APIv3 密钥」）
   - `certSerial`：32–64 位 hex（商户证书序列号）
   - `privateKeyPem`：商户私钥 PEM（`-----BEGIN PRIVATE KEY-----…`）
   - `enabled`：true
2. 在微信支付商户后台 → 「产品中心 → 开发配置」→ 设置回调 URL 为 `https://<gateway>/pay/wxpay/notify?app=<appName>`（**只填一次，gateway 自己 dispatch**）。
3. 在网关 admin → `app.paymentEnabled = true`。
4. 配置完成后，`/pay/create` 的 `wxpay_jsapi` 分支才生效；否则返 `payment_channel_not_configured`。

业务方 **没有 admin 权限**，整个 1–4 都是爸爸操作。业务方需要做的只是把 (mchId / wxpayAppId / apiV3Key / certSerial / privateKeyPem) 这 5 件事**通过靠谱渠道**交给爸爸（不要走 webhook / 邮件附件明文）。

### 接口清单（v1 vs v2 差异）

| 接口 | v1 personal_qr | v2 wxpay_jsapi |
|---|---|---|
| `POST /pay/create` | 返 `qrcodeUrl` + `remark` | 返 `wxpay.prepayEndpoint`，无 remark |
| `POST /pay/personal/claim` | ✅ 必须，用户「我已付款」 | ❌ **不调用** |
| `POST /pay/wxpay/jsapi/prepay` | ❌ | ✅ **新增**，前端拉起前调 |
| `GET /pay/status/<id>` | ✅ 沿用 | ✅ 沿用 |
| Webhook | ✅ `payment.paid` / `payment.disputed` / `payment.expired` | ✅ `payment.paid` / `payment.cancelled` / `payment.rejected` / `payment.expired`（**事件名变化**） |

### 1. `POST /pay/create`（wxpay_jsapi 模式）

源码：`app/pay/create/route.ts:82-147`。

请求 header：与 v1 完全一致。HMAC payload：`<appName>|<orderId>|<amount_fen>|<ts>`。

请求 body：
```json
{
  "orderId":    "your_internal_order_123",   // 同 v1，[a-zA-Z0-9_-]{1,64}
  "amount_fen": 9900,                          // 整数
  "subject":    "Pro 月度套餐",                // ≤80 字（注意 v2 后端校验是 80，v1 文档写 30 是过时；以代码为准）
  "method":     "wxpay_jsapi",                 // 可省略，但传了必须与 app.paymentChannel 一致
  "expiresIn":  1800,                          // 秒，60..7200
  "openid":     "o123abc...",                  // 可选；create 时不传，prepay 时一定要传
  "webhookUrl": "https://yourapp.com/wx/hook"  // 可选，覆盖 admin 配置的 url（per-payment）
}
```

返回 200：
```json
{
  "payOrderId":  "pay_01HX...",
  "method":      "wxpay_jsapi",
  "amount_fen":  9900,
  "expiresAt":   1714478096789,                // ⚠️ ms 数值（与 v1 ISO 字符串不同，按代码 expiresAt.getTime() 是 number）
  "wxpay": {
    "prepayEndpoint": "/pay/wxpay/jsapi/prepay",
    "checkoutUrl": "https://wx.mvp.restry.cn/pay/checkout/<payOrderId>?t=<48hex>"
  },
  "reused": true                                // 可选，仅幂等命中时存在
}
```

幂等：同 v1，(appName, orderId) 重复返已存在那条；如果 existing.method 不匹配 → 409 `method_mismatch_existing`。

新增 / 变化的错误码：

| code | 说明 |
|---|---|
| 400 channel_mismatch | body.method 与 app.paymentChannel 不一致 |
| 400 invalid_method | method 必须等于 app.paymentChannel |
| 400 method_mismatch_existing | 同 orderId 已存在但 method 不同 |
| 503 payment_channel_not_configured | app 未配 wxpay credentials 或 enabled=false |
| 501 wxpay_channel_not_yet_implemented | 目前只 wxpay_jsapi 实装，其他 channel（h5/native/app）仍占位 |

### 2. `POST /pay/wxpay/jsapi/prepay`（新增，v2 专用）

源码：`app/pay/wxpay/jsapi/prepay/route.ts`。

业务方在用户**点付款按钮**、且已拿到 openid 后调一次。返回的 `wxpay` 对象**直接喂给前端 `wx.chooseWXPay`**。

请求 header：HMAC payload 拼法 = `<appName>|<refKey>|<ts>`，其中 `refKey` 是 body 三选一里**实际填的那个**（推荐 paymentId）。

请求 body：
```json
{
  "paymentId": "pay_01HX...",   // payOrderId（推荐）
  // 或 "outTradeNo": "pay_01HX...",   // 别名，与 paymentId 等价
  // 或 "orderId":    "your_internal_order_123",  // 用业务方自家 orderId
  "openid":   "oXXXX...XXXXXXX"  // 必填，正则 /^[A-Za-z0-9_-]{8,64}$/
}
```

> ⚠️ `paymentId` / `outTradeNo` / `orderId` 三选一，**HMAC 用谁就在签里写谁**。想清楚不要混用。

返回 200：
```json
{
  "payOrderId":  "pay_01HX...",
  "method":      "wxpay_jsapi",
  "amount_fen":  9900,
  "expiresAt":   1714478096789,
  "wxpay": {
    "appId":     "wxd930ea5d5a258f4f",
    "timeStamp": "1714478000",
    "nonceStr":  "5K8264ILTKCH16CQ2502SI8ZNMTM67VS",
    "package":   "prepay_id=wx20240430...",
    "signType":  "RSA",
    "paySign":   "<base64 RSA-SHA256 sig>"
  }
}
```

> ⚠️ `wxpay` 对象的 6 个字段（`appId` / `timeStamp` / `nonceStr` / `package` / `signType` / `paySign`）**字段名大小写完全照传给 `wx.chooseWXPay`**。手抄一定出错，**用脚本展开**，不要手敲字段名。

幂等：同 paymentId 多次调 → gateway 复用已存的 `wxpayPrepayId`，每次重新做 RSA 签名（timeStamp / nonceStr / paySign 会变；前端拿到的是新鲜签）。

错误码：

| code | 说明 |
|---|---|
| 400 invalid_openid | 不符合 `[A-Za-z0-9_-]{8,64}` |
| 400 missing_payment_ref | body 三个 ref 字段都没传 |
| 404 payment_not_found | (id, appName) 找不到对应订单 |
| 400 method_not_jsapi | 该 payment.method 不是 wxpay_jsapi |
| 400 payment_not_pending | 订单已 paid / cancelled / expired，不能再 prepay |
| 410 payment_expired | 订单已过 expiresAt |
| 502 wxpay_upstream_error | 微信支付 API 返非 200 / 无 prepay_id（透传 wechat 错误） |
| 500 wxpay_prepay_failed | 网关侧未预期错误（看日志） |

### 3. `GET /pay/status/<payOrderId>` — 同 v1，结构沿用

返回里 `status` 在 v2 的取值集：`pending` | `paid` | `cancelled` | `rejected` | `expired`。**没有** v1 的 `submitted` / `disputed` 状态。

### 4. Webhook（gateway → 业务方）

格式与 v1 **完全一致**：相同 header、相同 sig payload `<event>|<payOrderId>|<status>|<ts>`、相同重试退避策略 `[0, 30s, 2m, 10m, 1h, 6h, 24h]`。

事件枚举（v2 触发自 `app/pay/wxpay/notify/route.ts:174-183`）：
- `payment.paid`：微信回调 `trade_state=SUCCESS`
- `payment.cancelled`：`trade_state=CLOSED` / `REVOKED`
- `payment.rejected`：`trade_state=PAYERROR` / `NOTPAY`（异常）
- `payment.expired`：gateway 内 expire-cron 兜底

> ⚠️ v1 的 `payment.disputed` 在 v2 **不会触发**（v2 不走人工审核）。业务方 webhook handler 应同时支持两种事件名集合（同一 endpoint 兼容），否则切换通道时漏处理。

### 前端拉起代码（公众号 H5）

```html
<!-- 1. 引 jweixin SDK（公众号网页都要） -->
<script src="https://res.wx.qq.com/open/js/jweixin-1.6.0.js"></script>
<script>
async function pay() {
  // 2. 业务方后端：先 /pay/create 拿 payOrderId
  //    再 /pay/wxpay/jsapi/prepay 拿 wxpay 对象（包含 6 个签名字段）
  const { payOrderId, wxpay } = await fetch("/api/checkout/start", { method: "POST" }).then(r => r.json());

  // 3. 直接传给 wx.chooseWXPay —— 字段名一一对应，不要重命名
  WeixinJSBridge.invoke("getBrandWCPayRequest", {
    appId:     wxpay.appId,
    timeStamp: wxpay.timeStamp,
    nonceStr:  wxpay.nonceStr,
    package:   wxpay.package,
    signType:  wxpay.signType,
    paySign:   wxpay.paySign,
  }, (res) => {
    if (res.err_msg === "get_brand_wcpay_request:ok") {
      // 用户点完支付——别在这里加额度，等 webhook
      location.href = `/pay/result?id=${payOrderId}`;
    } else {
      // 用户取消 / 失败 —— webhook 也会推 cancelled，UI 这里只做提示
    }
  });
}
</script>
```

### 关于 openid

**网关不参与 openid 获取**。业务方自己用公众号 OAuth (`snsapi_base` 或 `snsapi_userinfo`) 拿到用户 openid 后，在 `/pay/wxpay/jsapi/prepay` 里传过去即可。

> openid 必须**与 admin 配的 `wxpayAppId` 同一公众号**，否则微信支付返 `appid_mchid_not_match` / `param_error`。这是接入最常见 bug 来源。

### 推荐方式：统一付款页跳转（gateway 托管 wx.chooseWXPay）

**接入痛点**：业务方自家域名调 `wx.chooseWXPay()` 时，微信会校验「JSAPI 支付授权目录」必须包含业务方页面路径。商户号最多只能配 5 个授权目录 —— 每接一个新业务方就要去微信商户后台改一次，配额很快就用完。

**解决方案**：把 `wx.chooseWXPay` 调用搬到 wx-gateway 自家的统一付款页。所有业务方共用 `https://wx.mvp.restry.cn/pay/` **一个**授权目录，再多业务方也不占额度。

**业务方 3 步接入**：

1. 业务方拿到 openid 后调 `POST /pay/create`，body 里**必须**带 `openid` 和 `returnUrl`（付款完成后用户要回到的业务方页面，必须是 https + 同 `app.appBaseUrl` 的 host，否则 gateway 会忽略）。
2. 拿到响应里的 `wxpay.checkoutUrl`（形如 `https://wx.mvp.restry.cn/pay/checkout/<payOrderId>?t=<48hex>`）。
3. 前端 `window.location.href = checkoutUrl` 跳转。**不再调** `/pay/wxpay/jsapi/prepay`，**也不再调** `wx.chooseWXPay`。

之后流程：

- 用户看到 wx-gateway 渲染的统一付款页（"确认支付 ¥X.XX"）
- 用户点"立即支付" → gateway 内部调 `/pay/checkout/<id>/prepay` → 同页面调 `wx.chooseWXPay`
- 付款成功 → 跳回 `returnUrl`（gateway 从 DB 读，业务方在 URL 上传 return 也无效，防开放重定向）
- 付款取消/失败 → 留在付款页，可以重试
- webhook 仍按旧规则推到业务方的 `webhookUrl`

**微信商户后台**：把 JSAPI 授权目录配成 `https://wx.mvp.restry.cn/pay/`（**一次性**），即可支撑所有接入方。业务方自家域名**不再需要**加授权目录。

> ⚠️ 适用于业务方使用默认付款 UI 的场景；如需高度定制付款页 UI（按钮文案、品牌色、附加营销信息），仍可走下面"业务方自行调 prepay + chooseWXPay"老路径。老路径**没有删除**，向后兼容。

### 业务方典型 ts 接入骨架（⚠️ 适用于业务方需要自定义付款 UI；推荐用统一付款页）

```ts
// /api/checkout/start.ts —— 一次 RTT 串起 create + prepay
import crypto from "node:crypto";
const APP_NAME = process.env.WX_APP_NAME!;
const SECRET   = process.env.WX_APP_SECRET!;     // 64 hex 字符串
const GW       = process.env.WX_GATEWAY!;        // https://wx.mvp.restry.cn

function sign(payload: string) {
  return crypto.createHmac("sha256", SECRET).update(payload).digest("hex");
}

export default async function handler(req, res) {
  const userOpenid = req.session.openid;          // 业务方自己 OAuth 拿到
  const order      = await db.payment.create({ /* ... */ });
  const amount_fen = 9900;

  // ① /pay/create with method=wxpay_jsapi
  let ts = Date.now();
  let r = await fetch(`${GW}/pay/create`, {
    method: "POST",
    headers: {
      "X-WX-App-Name": APP_NAME,
      "X-WX-Ts":  String(ts),
      "X-WX-Sig": sign(`${APP_NAME}|${order.id}|${amount_fen}|${ts}`),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      orderId: order.id,
      amount_fen,
      method: "wxpay_jsapi",
      subject: "Pro 月度套餐",
    }),
  });
  const { payOrderId } = await r.json();

  // ② /pay/wxpay/jsapi/prepay 用 paymentId 当 ref
  ts = Date.now();
  r = await fetch(`${GW}/pay/wxpay/jsapi/prepay`, {
    method: "POST",
    headers: {
      "X-WX-App-Name": APP_NAME,
      "X-WX-Ts":  String(ts),
      "X-WX-Sig": sign(`${APP_NAME}|${payOrderId}|${ts}`),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ paymentId: payOrderId, openid: userOpenid }),
  });
  const { wxpay } = await r.json();

  // ③ 透传给前端
  return res.json({ payOrderId, wxpay });
}
```

webhook handler 与 v1 共用即可（仅事件名集合扩 `payment.cancelled` / `payment.rejected`）。

### 反模式

- ❌ **业务方直接调 `api.mch.weixin.qq.com` 绕开 gateway** — 等于自己抄一遍证书加载 / V3 签名 / 回调验签 / AES-GCM 解密的 1500 行代码，必出 bug。
- ❌ **openid 拼写错** — 不是 `openId` / `OpenID`，是 `openid` 全小写。
- ❌ **手敲 wxpay 对象字段名** — `timeStamp`（注意 S 大写）、`nonceStr`（注意 S 大写）。复制粘贴或用脚本展开，不要手抄。
- ❌ **在前端 `wx.chooseWXPay` 回调里加额度** — 用户能 hack 这个回调，**只信 webhook**。
- ❌ **回调 URL 填业务方域名** — 微信支付商户后台只能配一个 notify URL，必须填 gateway 的，否则 gateway 收不到回调。
- ❌ **把商户私钥 / apiV3Key 提交到 git** — 全部走 admin Dashboard 让爸爸录，业务方代码里不应出现这两个值。
- ❌ **同一 orderId 在 v1 / v2 之间切换** — 已 create 过的订单会因为 `method_mismatch_existing` 拒绝；切通道前用新 orderId。
- ❌ **wxpay_jsapi 模式下还在前端展示 v1 备注码 UI** — 没这玩意了，移除。

