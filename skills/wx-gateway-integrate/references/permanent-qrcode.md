# 业务方专属永久二维码

每个 app **就一张**永久参数二维码,scene_str 直接 = appName。任何人扫这码:
1. 关注公众号(未关注者)/ 触发 SCAN 事件(已关注者)
2. 网关解析 EventKey → `upsertBinding(openid, appName)`
3. 该用户后续消息全 fanout 到本 app

**用途**:贴海报、嵌邀请页、加微信群、放官网底部——彻底解决"用户在 A 站登过又去 B 站登,binding 被覆盖"。一旦扫过本 app 的码,binding 永远绑死(直到再扫别 app 的码,但那是用户主动行为)。

## 端点

```
GET https://wx.mvp.restry.cn/internal/wx-qrcode        (造悟者)
GET https://wxmsg.mvp.restry.cn/internal/wx-qrcode     (莆阳)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-qrcode|<ts>|<appName>"))
  X-Ts: <ms>
```

## 返回

```json
{
  "appName": "geniuspulse-prod",
  "qrcodeUrl": "https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket=...",
  "ticket": "gQH...",
  "generatedAt": "2026-..."
}
```

`qrcodeUrl` 直接 `<img src=...>` 渲染,或者后端 fetch 拿图片字节再二次处理(嵌海报)。

## 行为

- **首次调用**:网关调微信 cgi-bin/qrcode/create(`QR_LIMIT_STR_SCENE`)生成永久 ticket,写 App 表落库
- **后续调用**:直接 SELECT 缓存返回,不打微信 API(永久码不变)
- **每个公众号永久二维码上限 10 万张**——网关侧 1 个 app = 1 张,不浪费
- 想换码?admin 后台 App 编辑页 "Regenerate" 按钮(警告"旧码即时失效")。业务方自己**不能**重生成

## 调用示例(Node)

```ts
import { createHmac } from "crypto";

async function getMyQrcode() {
  const appName = process.env.WX_GATEWAY_APP_NAME!;
  const ts = Date.now().toString();
  const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`wx-qrcode|${ts}|${appName}`).digest("hex");

  const r = await fetch(`${process.env.WX_GATEWAY_BASE}/internal/wx-qrcode`, {
    headers: { "X-App-Name": appName, "X-Internal-Auth": sig, "X-Ts": ts },
  });
  return r.json();   // { qrcodeUrl, ticket, generatedAt, appName }
}
```

业务方自己缓存即可(永久不过期),不用每次拉。

## 跟扫码登录二维码的区别

| | 永久 SCAN 二维码(本接口) | 扫码登录(`/wx/qr/<app>`) |
|---|---|---|
| 用途 | 引流 / 邀请 / 自动 binding | PC 端登录,拿 openid 注入业务方 finalize |
| 时效 | 永久 | 5min,每个 token 一次性 |
| scene_str | = appName(固定) | token(每次随机) |
| 扫完跳哪 | 关注公众号 / SCAN 事件给业务方 webhook | 业务方 finalize URL,拿 openid 起 session |
| 何时用 | 公众号粉丝增长 / 跨站点引流 | 网站登录入口 |

两个二维码可以并存,各管一摊。

## 排查

- `qrcodeUrl == null` 或 500 → 微信 API 失败,通常 access_token 配错;先调 `/internal/wx-config` 看 wxToken 状态
- 用户扫了没收到 SCAN webhook → 看自己的 fanout endpoint 是否注册(`/internal/wx-config` 的 `fanout.endpoint`)
- 已关注用户扫码无感 → 这是微信行为,已关注用户扫永久码只触发 SCAN 事件不会重弹关注页;业务方收 SCAN 即可
- 用户扫了 binding 还是别 app → 该用户后来又扫了别 app 的二维码或在别 app OAuth 过(最后一次写者赢)
