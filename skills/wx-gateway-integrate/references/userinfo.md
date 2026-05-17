# 查用户身份(wx-userinfo)

业务方拿一手用户档案:是否关注公众号、nickname/头像、unionid、关注场景。基于微信 cgi-bin/user/info,网关代调 + 越权检查 + 60s 缓存。

## 端点

```
GET https://wx.mvp.restry.cn/internal/wx-userinfo?openid=<openid>     (造悟者)
GET https://wxmsg.mvp.restry.cn/internal/wx-userinfo?openid=<openid>  (莆阳)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-userinfo|<ts>|<appName>|<openid>"))
  X-Ts: <ms>
```

⚠️ **签名串多了 `|<openid>`** —— 跟其他 internal 不一样。这是为了防"业务方持有 secret 暴力枚举所有 openid 探测身份"。每次调要查哪个 openid 就拿那个 openid 入签。

## 越权规则

跟 wx-push 同:`UserAppBinding(openid).appName !== <你的 appName>` → 403 `not_bound_to_app`。也就是**只能查"在自己 app 扫码登录过 / 扫过自己永久码"的用户**。

例外:`appName === "admin"` 旁路(网关后台特权,业务方拿不到)。

## 返回

**关注用户**:
```json
{
  "openid": "...",
  "subscribed": true,
  "subscribeTime": 1696112000,
  "subscribeScene": "ADD_SCENE_QR_CODE",
  "nickname": "...",
  "avatarUrl": "https://thirdwx.qlogo.cn/mmopen/...",
  "unionid": "...",
  "language": "zh_CN",
  "tagidList": [],
  "remark": "",
  "groupid": 0
}
```

**未关注用户**:
```json
{ "openid": "...", "subscribed": false }
```

→ 业务方拿到 `subscribed: false` 引导关注(配合永久二维码效果最好)。

## 错误

| code | error | 说明 |
|---|---|---|
| 400 | missing_openid | query 没传 openid |
| 401 | bad_auth / ts_skew / sig_mismatch | HMAC 验签失败 |
| 403 | app_not_found | appName 不存在或未 active |
| 403 | not_bound_to_app | openid 没绑到本 app |
| 503 | wx_not_configured | 网关侧 WX_APP_SECRET 没配 |

微信 errcode 40003(invalid openid)/ 46004(user not exist)→ 网关转成 200 + `{subscribed: false}`(因为业务上等价于"用户不存在")。

## 调用示例(Node)

```ts
import { createHmac } from "crypto";

async function wxUserInfo(openid: string) {
  const appName = process.env.WX_GATEWAY_APP_NAME!;
  const ts = Date.now().toString();
  const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`wx-userinfo|${ts}|${appName}|${openid}`).digest("hex");

  const r = await fetch(
    `${process.env.WX_GATEWAY_BASE}/internal/wx-userinfo?openid=${encodeURIComponent(openid)}`,
    { headers: { "X-App-Name": appName, "X-Internal-Auth": sig, "X-Ts": ts } },
  );
  if (r.status === 403) return null;   // 没绑或不存在
  return r.json();
}

// 业务方典型用法:登录后引导关注
const u = await wxUserInfo(session.wxOpenid);
if (!u.subscribed) {
  // 弹"关注公众号送 100 积分"+ 永久二维码
}
```

## 缓存

网关进程内 60s LRU,key=`<appName>:<openid>`。业务方再叠一层本地缓存合理(比如 user session 期间不重拉)。

**严禁高频轮询**(< 10s 间隔同一 openid):本来就有 60s 缓存,频繁打没意义,只是浪费业务方/网关 CPU。

## 跟 OAuth 完成时返的 nickname/avatar 区别

| 来源 | 何时返 | 内容 | 时效 |
|---|---|---|---|
| 扫码登录 finalize URL 的 `nickname`/`avatarUrl` 参数 | 扫码登录完成那一刻 | 用户授权时的快照(`requireProfileCompletion=true` 时才有) | 一次性,不更新 |
| 本接口 wx-userinfo | 业务方任何时候调 | 公众号侧最新数据(关注用户改了昵称会反映) | 实时(60s 缓存) |

需要"用户改昵称同步业务方账号"的场景必须周期性调本接口,不能只信 finalize 那次的快照。
