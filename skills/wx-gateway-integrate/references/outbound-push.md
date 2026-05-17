# 主动推消息(出向 wx-push)

业务方主动向用户推消息(客服消息 custom / 订阅模板 subscribe)**走网关代理**,不要自己 POST cgi-bin。理由对称 access_token:每个公众号 AppID 只有 1 个有效 token,业务方各自调一定相互挤掉;且越权检查(A 业务方不能给 B 业务方的用户推)网关已经统一做了。

## 端点

```
POST https://wx.mvp.restry.cn/internal/wx-push        (造悟者)
POST https://wxmsg.mvp.restry.cn/internal/wx-push     (莆阳)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-push|<ts>|<appName>"))
  X-Ts: <ms timestamp>
  Content-Type: application/json

Body:
{
  "toUser":  "<openid>",              // 目标用户
  "type":    "custom" | "subscribe",
  "payload": { ... 微信原 payload, touser 不用填,网关注入 ... }
}
```

**鉴权密钥就是 register 时拿到的 `WX_GATEWAY_SECRET`**——同一份,不需要别的 token。

## 越权规则

1. HMAC + 5min skew:不通 → 401
2. `X-App-Name` 不存在 / 未 active → 403 `app_not_found`
3. **越权**:`UserAppBinding(toUser).appName !== <你的 appName>` → 403 `not_bound_to_app`
   - 含义:业务方只能给"曾经在自己 app 扫码登录过"的用户推消息
4. 微信回 `errcode=40001`(token 失效)网关自动强刷重试 1 次

## 返回

```
200 { "ok": true,  "errcode": 0, "msgId": "...", "errmsg": "ok" }
200 { "ok": false, "errcode": 40003, "errmsg": "invalid openid hash" }   ← 微信侧业务错,HTTP 仍 200
401 { "error": "bad_auth" | "ts_skew" }
403 { "error": "app_not_found" | "not_bound_to_app" | "secret_unavailable" }
```

注意:**HTTP 200 不等于发送成功**。必须看 `ok` / `errcode`。

## 调用示例(Node)

```ts
import { createHmac } from "crypto";

async function wxPush(toUser: string, payload: object) {
  const appName = process.env.WX_GATEWAY_APP_NAME!;
  const ts = Date.now().toString();
  const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`wx-push|${ts}|${appName}`).digest("hex");

  const r = await fetch(`${process.env.WX_GATEWAY_BASE}/internal/wx-push`, {
    method: "POST",
    headers: {
      "X-App-Name": appName,
      "X-Internal-Auth": sig,
      "X-Ts": ts,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      toUser,
      type: "custom",
      payload: { msgtype: "text", text: { content: "你的任务已完成 ✅" } },
    }),
  });
  const j = await r.json();
  if (!j.ok) throw new Error(`wx-push failed: ${j.errcode} ${j.errmsg}`);
  return j;
}
```

## 客服消息 vs 订阅消息

| type | 微信 API | 触发条件 | 内容限制 |
|---|---|---|---|
| `custom` | `cgi-bin/message/custom/send` | 用户最近 48h 与公众号有交互(关注/扫码/发消息) | text/image/voice/video/news 等 |
| `subscribe` | `cgi-bin/message/subscribe/send` | 用户主动订阅了模板 | 模板 ID + data,格式严格 |

订阅消息 payload 必须按微信模板结构,详见微信公众平台「订阅通知」官方文档。

## 排查

- 401 `ts_skew` → 本机时钟偏 > 5min,校 NTP
- 403 `not_bound_to_app` → 该 openid 没在你的 app 扫码登录过;先让用户扫码(自动写 binding),再推
- 403 `secret_unavailable` → app 是老 secret(register 在 2026-05 之前),找爸爸到 admin Dashboard rotate 一次拿新 secret
- `errcode 45015` (custom) → 用户超出 48h 互动窗口,换 subscribe 模板
- `errcode 40003` → openid 不属于本公众号实例(造悟者 openid 推到莆阳实例必报这个)
- 网关后台 Outbound tab 看所有出向日志(`OutboundMessageLog` 表)
