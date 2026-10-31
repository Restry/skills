# 公众号菜单管理(网关自管 cgi-bin/menu)

公众号开启服务器配置后,微信后台图形菜单 UI 自动禁用,只能 API 管。网关 admin 后台**Menu tab** 取代了它,scope 到当前实例的公众号。

## 操作入口

每个实例 admin Dashboard `→ Menu` tab(在 Outbound 后面)。**只配当前实例所属公众号**:
- 莆阳 admin (`wxmsg.mvp.restry.cn`) → 改莆阳号菜单
- 造悟者 admin (`wx.mvp.restry.cn`) → 改造悟者号菜单

UI 顶部 banner 显示 `instanceLabel` + 公众号 host,防止误改。

## 工作流

| 按钮 | 作用 | 风险 |
|---|---|---|
| Save Draft | 只写 `WxMenu` 表(`buttonsJson`),不调微信 | 0 |
| Push to WeChat | 写表 + 调 `cgi-bin/menu/create`(覆盖现有菜单) | 立即生效,微信侧 24h 缓存推送 |
| Pull Current | 调 `cgi-bin/menu/get` 看微信侧实际菜单,对比 DB drift | 0 |
| Delete Menu | 调 `cgi-bin/menu/delete` 清空 + 删 DB | 公众号底部菜单瞬间消失 |

Push 和 Delete 都有 confirm 二次确认。

## 菜单 Schema(微信原生)

```json
{
  "button": [
    { "name": "顶级A(1-16字符)", "type": "click", "key": "biz_a_root" },
    { "name": "顶级B", "sub_button": [
        { "name": "二级", "type": "click", "key": "biz_b_one" },
        { "name": "外链", "type": "view", "url": "https://..." }
    ]}
  ]
}
```

约束:
- 一级菜单 1-3 个
- 每个一级 name 1-16 字符,二级 name 1-60 字符
- type=`click` 必须有 `key`(1-128 字符,业务方约定前缀)
- type=`view` 必须有 `url`(必须 https + 在公众号"业务域名"白名单内)
- type=`miniprogram` 需 `appid` + `pagepath` + 兜底 `url`

合法性检查在网关 `lib/wx/menu.ts` 的 `isValidMenu`,PUT 不通过返 400 `invalid_menu`。

## click 事件路由

用户点 `click` 类型菜单 → 公众号给网关 POST 一条 event:
```xml
<MsgType>event</MsgType>
<Event>CLICK</Event>
<EventKey>biz_a_root</EventKey>
```

网关按 `MessageRoute` 的 `EventKey_prefix` 匹配。**约定 key 起业务前缀**(`interview_*` / `support_*` / `geniuspulse_*`),Routes tab 加对应路由:

```
匹配规则: { "Event": "CLICK", "EventKey_prefix": "interview_" }
endpoint: geniuspulse-prod
ownsReply: true
priority: 10        ← 必须比 catchall(100)小,先匹配
```

## 与 catchall 的冲突

当前莆阳两个 catchall(cspy + geniuspulse-prod)都 `ownsReply=true` + `matchJson={}`。新加 click prefix 路由 + ownsReply=true 时,**会同时匹配 prefix 路由 + 两个 catchall**,触发 `matchRoutes` 的 `route invariant: 3 ownsReply matches` fail-fast。

解决方案二选一:
1. **catchall 排除 event**:把 catchall 的 `matchJson` 改成 `{"MsgType":["text","image","voice","video","location"]}`,event 类消息只走专门路由
2. **catchall 改 ownsReply=false**(粗粒度方案):catchall 仅 fanout 不回复,所有 ownsReply 走精细路由 + UserAppBinding 兜底

方案 1 更稳,推荐。改 catchall 同时**必须**确保所有 event 都有路由覆盖(SCAN/subscribe 至少要写一条 EventKey_prefix=appName 的路由)。

## 调试

- Menu push 失败:`errcode 40017` = button name 太长 / 超 3 个一级;`errcode 65103` = 域名未在公众号"业务域名"白名单(view 类型菜单的 url)
- 推了菜单但用户没看到:微信侧菜单 24h 缓存,关注后才会拉新菜单。**已关注用户取消关注再关注立即生效**;或在公众号后台"自定义菜单"页面"重新发布"
- click 事件没触发业务回调:看 `FanoutLog` 表 `event=CLICK` 那条的 `matchedRouteName` / `boundApp` / `error`

## 反模式

- ❌ 在造悟者实例 Push 莆阳菜单(banner 会警告,看一眼再点)
- ❌ key 没有业务前缀(`btn1`/`menu_help`)→ 跨业务方撞 prefix
- ❌ 改了菜单不同步 Routes tab → click 事件无 owner,网关返空 reply 微信重试 3 次
- ❌ view 菜单 url 不在公众号业务域名白名单 → push 直接 errcode 65103
