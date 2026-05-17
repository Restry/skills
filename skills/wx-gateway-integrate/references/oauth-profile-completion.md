# OAuth 补全 nickname / avatar

业务方接 wx-gateway 扫码登录后，**几乎都需要**这一步——纯 SCAN 事件只能拿到 openid，nickname/avatarUrl 要靠 snsapi_userinfo OAuth 拿。

**本文是 SKILL.md 主流程（扫码登录）的扩展**。如果业务方完全不需要展示用户头像/昵称，可以跳过本节。

---

## OAuth 补全 nickname / avatar（**所有业务方都要接**）

> 历史：这一节早期叫"微信内 OAuth 增强"（路径 B），只覆盖微信内置浏览器场景。
> 2026-04-28 后 wx-gateway 在 PC 扫码 reply XML 里也带了 OAuth 链接 (`b7acca5`)，
> **所以 PC 扫码用户也会被引导走 OAuth**——业务方现在必须支持，不再可选。

### 用户体验（两条路径，finalize 行为相同）

**路径 A：PC 网页扫码**
1. PC `/login` 显示二维码
2. 用户扫码 → 公众号推 SCAN/subscribe → 网关 confirm → SSE 推 confirmed → PC 跳 `/api/wx/finalize?token&openid&unionid&ts&sig`（**此次仅 openid，无 nickname/avatar**）→ 业务方建用户、登录成功
3. **同时**用户手机微信收到造悟者一条欢迎语，含 `https://wx.mvp.restry.cn/wx/oauth/start?app=<name>` 链接
4. 用户点链接 → 微信授权页 → 网关 callback 拿到 nickname/avatar/unionid → 302 业务方 `/api/wx/finalize?token&openid&unionid&ts&sig&nickname=...&avatarUrl=...`（**此次带 nickname/avatar**）
5. 业务方 finalize 检测到用户已存在 → 仅回填 nickname/avatar → 用户刷新页面看到头像昵称

**路径 B：微信内置浏览器打开**
1. 业务方 `/login` 检测到 MicroMessenger UA，**直接** `window.location.href = wx-gateway/wx/oauth/start?app=...`（跳过扫码）
2. 用户在微信里点"允许" → 网关 callback → 302 业务方 finalize 一次到位（带 nickname/avatar）

→ **同一个 finalize 路由处理两条路径，业务方不需要分支**。区别只在 query 里有没有 `nickname/avatarUrl`。

### 网关已就绪的路由（不用改）

- `GET https://wx.mvp.restry.cn/wx/oauth/start?app=<name>` — 微信内入口，跳造悟者 OAuth
- `GET https://wx.mvp.restry.cn/wx/oauth/callback` — 拿 access_token + sns userinfo（nickname/headimgurl/unionid）
- 同样走 `buildFinalizeRedirect` 302 业务方 finalize；**额外**带 `nickname` / `avatarUrl` query（不参与 HMAC，TLS 兜底）

### 业务方只改两处

**1. 登录页 UA 跳转**：

```tsx
const WX_GATEWAY = process.env.NEXT_PUBLIC_WX_GATEWAY_BASE;
const WX_APP_NAME = process.env.NEXT_PUBLIC_WX_GATEWAY_APP_NAME;
const IS_WECHAT_UA = /MicroMessenger/i;

useEffect(() => {
  if (
    typeof window !== "undefined" &&
    WX_GATEWAY && WX_APP_NAME &&
    IS_WECHAT_UA.test(navigator.userAgent) &&
    !searchParams.get("error")           // 防回跳死循环
  ) {
    window.location.href = `${WX_GATEWAY.replace(/\/+$/,"")}/wx/oauth/start?app=${encodeURIComponent(WX_APP_NAME)}`;
    return;
  }
  // ... 否则展示扫码 tab
}, []);
```

env 任一缺失时 **fallback 到扫码 tab，不要白屏**。

**2. `/api/wx/finalize` 多读两个字段 + 关键 idempotent 改造**：

⚠️ **字段名陷阱**：gateway 发的 query 是 **`nickname`** 和 **`avatarUrl`**（不是 `avatar`！）。业务方读取必须用 `sp.get("avatarUrl")`。PackHorizon R8/R9 第一次写成 `sp.get("avatar")`，结果只拿到 nickname 没拿到头像，第二次扫码才发现。


⚠️ **关键变更**：finalize 现在会被同一用户调**两次**（PC 扫码 + 后续 OAuth 补全）。**不能再用"token 一次性消费"防重放**——会把第二次 OAuth 路径误判 replay。

```ts
const nickname = sp.get("nickname")?.trim() || null;
const avatarUrl = sp.get("avatarUrl")?.trim() || null;

// ❌ 老逻辑（删掉）：
// const seen = await prisma.wxFinalizeLog.findUnique({ where: { token } });
// if (seen) return NextResponse.redirect(new URL("/login?err=replay", req.url));

// ✅ 新逻辑：token 5min skew 已经做了基本防重放；
// finalize 改成完全 idempotent，按 unionid/openid upsert，多次调用只补字段不冲突
// HMAC 校验串保持 `${token}|${openid}|${unionid}|${ts}`，nickname/avatar 不参与！

const account = await prisma.wechatAccount.findUnique({
  where: unionid ? { unionid } : { openid },
});

if (!account) {
  // 第一次：建新账号
  await prisma.wechatAccount.create({
    data: {
      openid, unionid: unionid || null,
      nickname,        // 路径 A 第一次为 null，路径 B 直接写入
      avatarUrl,       // 同上
      displayName: nickname || `微信用户${openid.slice(-6)}`,
    },
  });
} else {
  // 已存在：只回填空字段，不覆盖用户后续修改
  const updates: any = {};
  if (nickname && !account.nickname) updates.nickname = nickname;
  if (avatarUrl && !account.avatarUrl) updates.avatarUrl = avatarUrl;
  if (unionid && !account.unionid) updates.unionid = unionid;
  if (Object.keys(updates).length) {
    await prisma.wechatAccount.update({ where: { id: account.id }, data: updates });
  }
}
```

**为什么去掉 token replay 检查是安全的**：
- token 5min 内有效，过期后微信永远不会再签出同一 token（网关侧 wxLoginToken 一次性）
- HMAC 用业务方专属 secret，无法伪造
- finalize 是纯 upsert，多次调用幂等，没有副作用累积
- 路径 A 第一次 finalize 已建 session（PC 登录闭环完成）；路径 A 第二次只补 profile 字段，不需要重发 cookie（如果业务方想要"OAuth 完成后跳到某个页面提示"可以加，但默认 redirect 回 `/app` 即可）

### 反模式

- ❌ 同时保留业务方自家公众号 OAuth + 网关扫码两条路径——会产生两个 openid 两条用户记录。要删就全删，统一走网关（PackSmith 2026-04 教训）
- ❌ 把 nickname/avatarUrl 加进 HMAC payload——网关是按 `token|openid|unionid|ts` 签的，加了对不上
- ❌ 微信内跳转后 finalize 失败把用户死循环送回 `/login`——必须检查 `searchParams.get("error")` / `err`，命中则不再 UA 跳

### 部署前 checklist（mvp-deployer）

`NEXT_PUBLIC_*` env 是 **build-time 内联**，不是 runtime 读。每次部署前用 `/api/inventory` 确认目标项目的 envKeys 包含 `NEXT_PUBLIC_WX_GATEWAY_BASE` 和 `NEXT_PUBLIC_WX_GATEWAY_APP_NAME`。少了就补到服务器 `~/.credentials/.env` 的 `<UPPER>__NEXT_PUBLIC_WX_GATEWAY_*` 前缀，否则 build 出来的 JS 里这俩是 `undefined`，微信内会 fallback 到扫码（不崩但功能丢）。

### Schema 别忘了

WechatAccount 模型加 `nickname String?` 和 `avatarUrl String?`，路径 B finalize 才有地方写。改 schema 必须 `prisma db push` 或写 migration——光 push 代码不建表，finalize 会运行时报 `relation does not exist`（PackSmith 2026-04 实际踩过）。CC 任务 prompt 里要明确"如改 schema 必须 db push"。

### 业务自定义 ext 透传（邀请码 / 来源标记）

业务方需要让 finalize 知道「这次登录是从哪个邀请链接来的」时，用 `ext`：

```
GET https://wx.mvp.restry.cn/wx/oauth/start?app=<name>&ext=<urlencoded-string>
```

约束：
- **单个 `ext` 字段**，最多 256 字符（urlencoded 后长度）。超长返 400 `ext_too_long`。
- 要塞多字段（ref + utm_source + ...）业务方自己 base64 / JSON 后再 urlencode，gateway 不解释。
- gateway 把 `ext` 落进 `WxLoginToken.ext`，OAuth 完成后原样写回 finalize URL 的 `ext` query。两条路径（PC 扫码 SSE redirect / 微信内 OAuth 回跳）都会带。
- **`ext` 不进 HMAC payload**（与 nickname/avatarUrl 一致）：HMAC 仍是 `token|openid|unionid|ts`。TLS 保证传输完整性，gateway 不为 ext 内容背书。
- 这是 **opaque 业务透传通道**，gateway 不解析、不校验。如果业务方需要防篡改（例如邀请码不可被用户改），自行在 ext 内嵌业务方 HMAC，或在 finalize 拿到后查自家邀请表二次校验。
- 安全建议：敏感信息（密码、私钥、PII）禁止塞入 ext —— 它会出现在浏览器历史和 access log 里。

业务方 finalize 读取：`const ext = sp.get("ext");`（可空）。

