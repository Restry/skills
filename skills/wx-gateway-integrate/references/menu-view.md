# 查公众号菜单(wx-menu)

业务方收到 click 事件后,需要知道"这个 EventKey 对应的按钮叫什么名字、在菜单哪一级、有没有兄弟按钮"才能写智能回复(比如"我要面试"按钮回复面试流程引导)。本接口拿菜单上下文。

## 端点

```
GET https://wx.mvp.restry.cn/internal/wx-menu        (造悟者)
GET https://wxmsg.mvp.restry.cn/internal/wx-menu     (莆阳)

Headers:
  X-App-Name: <你的 appName>
  X-Internal-Auth: hex(HMAC-SHA256(WX_GATEWAY_SECRET, "wx-menu|<ts>|<appName>"))
  X-Ts: <ms>
```

## 返回

```json
{
  "buttons": [
    { "name": "我要面试", "type": "click", "key": "interview_start" },
    { "name": "找服务", "sub_button": [
        { "name": "联系客服", "type": "click", "key": "support_contact" }
    ]},
    { "name": "我的", "sub_button": [
        { "name": "个人中心", "type": "view", "url": "https://..." }
    ]}
  ],
  "myButtons": [
    { "key": "interview_start", "name": "我要面试", "type": "click", "path": ["我要面试"] },
    { "key": "support_contact", "name": "联系客服", "type": "click", "path": ["找服务", "联系客服"] }
  ],
  "pushedAt": "2026-05-13T...",
  "instance": { "host": "wxmsg.mvp.restry.cn", "appId": "wxe...", "instanceLabel": "莆阳" }
}
```

| 字段 | 说明 |
|---|---|
| `buttons` | 微信原生菜单 JSON,业务方理解整体结构 |
| `myButtons` | **server 预筛**——只列调用方绑了 MessageRoute 的 click 按钮(网关查 `name='menu-${key}' AND endpointName=<你的 appName>`)。业务方直接迭代,不用自己过滤 |
| `myButtons[].path` | 菜单层级,一级菜单 `["我要面试"]`,二级菜单 `["找服务","联系客服"]` |
| `pushedAt` | null = 菜单还没 Push 到微信;有值 = 微信侧已生效 |
| `instance` | 当前公众号实例信息 |

## 调用示例(Node)

```ts
import { createHmac } from "crypto";

async function getMenu() {
  const appName = process.env.WX_GATEWAY_APP_NAME!;
  const ts = Date.now().toString();
  const sig = createHmac("sha256", process.env.WX_GATEWAY_SECRET!)
    .update(`wx-menu|${ts}|${appName}`).digest("hex");

  const r = await fetch(`${process.env.WX_GATEWAY_BASE}/internal/wx-menu`, {
    headers: { "X-App-Name": appName, "X-Internal-Auth": sig, "X-Ts": ts },
  });
  return r.json();
}
```

## 典型用法:click 事件智能回复

业务方 fanout 端点收到 CLICK 事件:
```xml
<MsgType>event</MsgType>
<Event>CLICK</Event>
<EventKey>interview_start</EventKey>
<FromUserName>oXXX</FromUserName>
```

业务方:
1. 启动时 fetch `/internal/wx-menu`,缓存 `myButtons` 进内存(菜单变更频率低)
2. 收到 CLICK 时按 EventKey 查缓存:
```ts
const btn = myButtonsCache.find(b => b.key === eventKey);
if (!btn) return;   // 不是绑给我的按钮,可能 EventKey_prefix 路由命中但实际不归我
// 用 btn.name / btn.path 写回复
return replyText(`你点的是「${btn.name}」,接下来...`);
```

## 缓存

业务方自己缓存即可。**菜单极少变**(更新需爸爸去 admin Push),建议:
- 启动时拉一次进内存
- 命中 click 事件无 myButtons 时拉一次(检测漂移)
- 周期性 5min 刷一次(可选)

不要每条 click 事件都拉。

## 排查

- `myButtons` 空:你这个 app 没绑任何 click 按钮 → 找爸爸去 admin Menu tab 给对应按钮 select 选你的 app
- `pushedAt: null`:菜单存了但没 push 到微信 → 找爸爸去 admin Menu tab 点 Push to WeChat
- 收到 CLICK 但 `myButtons` 没那个 key:可能爸爸更新了菜单,按钮归别人了 → 重拉 menu
