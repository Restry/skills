# 接入管理

注册、撤销、邀请码、消息路由或用户绑定时读取。生产 App 为真源，仅查询 name、displayName、appBaseUrl、status、callbackUrl、ssoRedirectUri，不输出 secret。

## 注册与修改

控制器通过既有后台 Invites 功能或经授权数据库操作颁发邀请码，绑定名称前缀、域名、期限和次数。业务方持 X-Invite-Code 调 POST /apps/register，提交 name、appBaseUrl、displayName、finalizePath；完整客户端步骤见 wx-gateway-integrate。邀请码及返回 secret 走保护通道，不进入公开日志。

同一 appBaseUrl 已有 active 注册时不能重复注册。修改 callbackUrl 不覆盖 finalizePath 或 ssoRedirectUri；SSO 仅登记真实客户端精确 HTTPS 回调。APPS_JSON 是历史配置来源，正常管理以数据库为准，不重导入过时配置。新应用通常自动创建 catchall，先查现有路由再修改。

## 撤销接入

1. 核对精确 name、域名及预期数量，排除 admin/selftest。模糊搜索仅用于发现，写入选择必须精确且非空。
2. 事务内设 status=revoked，清空 ssoRedirectUri、callbackUrl，按精确 appName 删除 MessageRoute。
3. 回读每项目标状态、空回调和剩余路由数，核对相邻未选应用。检查目标是否仍在 env 注册来源，避免恢复。
4. 保留 App 行和扫码、支付历史；不扩大到删除网站源码、部署、数据库或 vault 项目。报告撤销接入，不称物理删除历史。

## 消息与绑定

MessageRoute 按 MsgType、Event、EventKey_prefix 过滤；priority 越小越优先，ownsReply 决定 XML 回复权。当前运行算法以源码为准：纯规则过滤 → 绑定缩小范围 → priority/createdAt/id 确定回复 owner。历史 invariant 错误先查运行版本，不重复实施旧修复；决议事件不能写入错误字段污染统计。

UserAppBinding 为一用户多 App，source=oauth/admin-auto/manual；真实 confirmed 扫码/OAuth 才写绑定。缓存可能滞留60秒，修改后读回并考虑缓存，不随意部署。

后台 Apps 详情管理路由、Users 管理绑定、Messages 查时间线、Overview 查 endpoint health。排查只输出 FanoutLog 的时间、状态及必要路由元数据，不输出用户消息或身份真值。多个 catchall 命中不等于可以删除仍使用的应用。
