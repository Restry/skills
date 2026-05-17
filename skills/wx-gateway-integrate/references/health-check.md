# 自检配置快照(wx-config)

业务方接入后,任何时候想确认"我的配置在网关侧是不是正常"——**消息没到、二维码生不出、token 401**——第一步先打这个接口。

## 端点

```
GET https://wx.mvp.restry.cn/internal/wx-config        (造悟者)
GET https://wxmsg.mvp.restry.cn/internal/wx-config     (莆阳)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-config|<ts>|<appName>"))
  X-Ts: <ms timestamp>
```

签名串前缀是 `wx-config`(token 是 `wx-token`,push 是 `wx-push`)。其余鉴权规则同 wx-token / wx-push。

## 返回

```json
{
  "app": {
    "name": "geniuspulse-prod",
    "displayName": "Genius-Pulse",
    "appBaseUrl": "https://geniuspulse.nexora.restry.cn",
    "finalizePath": "/api/wx/finalize",
    "requireProfileCompletion": true,
    "status": "active",
    "createdAt": "2026-..."
  },
  "fanout": {
    "endpoint": {                  // null 表示业务方还没在网关注册回调地址
      "name": "geniuspulse-prod",
      "url":  "https://geniuspulse.nexora.restry.cn/api/wx/callback",
      "enabled": true
    },
    "routes": [                    // 路由配置,空数组 = 不会有消息派发到你
      { "name": "...", "matchJson": {}, "ownsReply": true, "priority": 100, "enabled": true }
    ],
    "boundUsers": 12               // UserAppBinding 表里绑到本 app 的 openid 数
  },
  "wxToken": { "ok": true, "expiresAt": 1234567890123 },
  "instance": {
    "host":  "wxmsg.mvp.restry.cn",
    "appId": "wxe780b027c2c56921",
    "instanceLabel": "莆阳"
  }
}
```

不返回任何 secret / token 明文。

## 排查矩阵

| 现象 | 看哪里 | 修法 |
|---|---|---|
| 消息全没到 | `fanout.endpoint == null` 或 `enabled == false` | 找爸爸去 admin Dashboard 加 endpoint / enable |
| 部分消息没到 | `fanout.routes == []` 或 routes 都 `enabled: false` | 加 catchall route(`matchJson: {}`)+ enable |
| 看不到任何用户 | `boundUsers == 0` | 用户从来没在你 app 扫码登录过;或 binding 被其他 app 抢了(查 `wx-gateway-operate` skill 排查) |
| token 401 | `wxToken.ok == false` 或 `expiresAt < now` | 找爸爸看网关 `WX_APP_SECRET` / 公众号 IP 白名单 |
| 二维码 host 错 | `instance.host` 不对 | 你接的是错实例(造悟者/莆阳搞混) |
| `requireProfileCompletion: true` 但前端没处理 scanned 状态 | 前端 SSE 分支缺 scanned/rejected | 改前端,见 SKILL.md「状态展示与强制 OAuth」 |

## 调用示例(Node)

```ts
import { createHmac } from "crypto";

async function wxConfig() {
  const appName = process.env.WX_GATEWAY_APP_NAME!;
  const ts = Date.now().toString();
  const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`wx-config|${ts}|${appName}`).digest("hex");

  const r = await fetch(`${process.env.WX_GATEWAY_BASE}/internal/wx-config`, {
    headers: { "X-App-Name": appName, "X-Internal-Auth": sig, "X-Ts": ts },
  });
  if (!r.ok) throw new Error(`wx-config ${r.status}`);
  return r.json();
}
```

建议挂到业务方自家 `/api/health/wechat` 或 admin 后台一个按钮上,出问题点一下立刻看到完整状态。

## 频率

只读、便宜,但每次都查 DB + 触发一次 token 检查。**不要拿来当心跳**(秒级轮询)。建议:
- 出问题时手动调
- 业务方部署后 smoke test 调一次确认配置就绪
- 每分钟 / 每 5 分钟轮询一次做监控可以,再高没意义
