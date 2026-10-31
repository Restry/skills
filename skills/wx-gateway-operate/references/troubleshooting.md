# 排错与微信接口

回调、SSE、签名、消息、菜单或模板异常时读取。先复现和观察实际响应，再判断根因；仅输出安全元数据。所有接口和字段以部署版本源码为准，不能从历史技能示例推定已支持。

## 登录链路

| 症状 | 检查顺序 |
|---|---|
| 二维码失败 | App active → 原始微信错误分类 → 公众号配置存在性 → access_token 缓存；禁止假占位图 |
| 扫码无反应 | 微信 callback 验签 → SCAN/subscribe 与 EventKey → WxLoginToken 对应 app/状态/期限 → SSE |
| finalize 签名失败 | 实际 payload 字段顺序、时间单位、两端 secret/key 编码；恒时比较不变 |
| expired/replay | 当前 token 期限、服务器时钟、是否重复消费；扫码确认后刷新二维码，不延长期限绕过 |
| SSO/退出异常 | 加载 sso-operations.md；观察浏览器 Cookie、CSP 与完整跳转链 |

微信唯一回调入口为 /wx/callback；业务 QR、SSE 和 finalize 实现分别查 app/wx/qr、app/wx/poll、lib/wx/sign。明文/密文模式必须与实际实现一致，不擅自切微信平台配置。用户可见 URL 使用 publicBase(req) 或 PUBLIC_BASE_URL，不硬编码另一实例域名。

## 48001、token 与消息

48001 api unauthorized 不能单独证明 access_token 作废。核对调用的具体微信接口、公众号能力、权限、token 缓存及近期是否有外部刷新；与正常业务请求比较，不先手工调 cgi-bin/token。集中刷新只能沿用网关加锁托管路径，避免并发使现有 token 失效。

消息路由检查精确 App、MessageRoute、UserAppBinding、FanoutLog 的实际过滤链。下游失败不能向微信返回5xx触发重试放大。endpoint health 的 error 应代表真实失败，不能把 owner 决议警告计入。

## 菜单与模板

操作公众号菜单前读取实际菜单接口、结构和现有远程菜单，备份后仅修改授权按钮。CLICK 对应 EventKey 必须和路由匹配；保存数据库和推送微信是两个动作，分别回读。不要重建整套菜单覆盖未选按钮。

模板查询工具 scripts/inspect-wx-templates.js。先看脚本参数及数据输出范围，再运行。模板消息使用 cgi-bin/message/template/send；服务号一次性订阅通知使用 cgi-bin/message/subscribe/bizsend，小程序的 subscribe/send 不是同一个接口。

WxTemplate.enabled 用于业务清单展示；现有 wx-push 不以 enabled 或用户绑定阻止发送。wx-userinfo 的绑定隐私校验仍保留。修改这类授权语义必须有明确用户要求，不能因字段存在而自行补限制。同步模板时不覆盖管理员已有 enabled 选择。

业务调用 /internal/*，使用自己的应用 secret 按 lib/internal-auth.ts 定义的 scope/payload 鉴权，不能直接调原生 token API。支付签名与状态契约查看 wx-gateway-integrate；不要凭旧示例改 HMAC 编码。

## 执行与自检

Node 脚本位于目标项目目录以解析依赖，临时文件使用唯一名称并清理；凭据留内存，JSON 用序列化，shell 参数正确引用。不要 source 含未引用中文值的 .env；使用已审阅解析器。API exec 不可用走已授权云 guest-command，不开放公网管理端。

读取 scripts/selftest.py 的参数和副作用后再执行；它可能写 token/模拟 confirmed，只能作为明确标识的协议测试。不能冒充真实扫码、用户身份或业务记录。真实浏览器验收另查页面、Cookie、CSP、重定向及受保护业务行为。更新协议时同时修接入文档与契约测试，不用一次 HTTP 200 宣称全链路通过。
