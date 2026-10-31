# 七天 SSO 接入

实现提交：wx-gateway `fac499adfb5784e2ad32f1153330e6c2f7def852` 已推送 main 并部署两套生产实例，迁移回读通过。真实 A/B 网站仍须完成接入改造和微信扫码验收；不得把网关上线当作各站已互通。使用前核实目标实时状态及回调登记。完整权威协议见仓库 `docs/SSO.md`，交付证据见 `docs/SSO-DELIVERY.md`。

- A/B 必须同一 issuer、同一浏览器；两个公众号独立网关不能互通。中央会话首次扫码起七天绝对过期，不滑动续期。
- 旧二维码 finalize 流程继续工作，但不建立 SSO。A/B 均须切换顶层授权跳转，不能只改 B。
- 在现有 App 登记 `ssoRedirectUri`：精确单个 HTTPS URL，无 query/fragment/通配符；独立于 finalizePath/callbackUrl。当前没有配置 UI，通过受控 DB 更新，先确认客户端回调实现。

## 网站修改

1. 本站未登录时，后端生成随机 state 和 PKCE verifier，以 HttpOnly Secure SameSite=Lax 短期 Cookie 或服务端事务绑定浏览器，五分钟有效；保存安全的本站返回路径。
2. 顶层导航 `GET {issuer}/sso/authorize?client_id={appName}&redirect_uri={registeredUri}&state={state}&code_challenge={base64url(SHA256(verifier))}&code_challenge_method=S256`。state 32–128 base64url，verifier 43–128 RFC7636 unreserved 字符。禁止 iframe 或跨域 fetch 替代导航。
3. 回调严格校验 iss、浏览器绑定 state，消费本地事务；后端 POST `/sso/token` JSON `{code,redirect_uri,code_verifier,state}`。
4. 请求 headers `X-App-Name`、`X-Ts`（毫秒）、`X-Internal-Auth`。签名为 HMAC-SHA256 hex，payload 精确为 `sso-token|<code>|<redirect_uri>|<code_verifier>|<state>|<ts>|<appName>`。**本接口遵循实际代码：createHmac('sha256', appSecret)，secret 作为字符串，不 hex 解码。** 不改变旧接口的既有签名合同。
5. 响应 `{ok:true,issuer,app,user:{openid,unionid,nickname,avatarUrl},sessionExpiresAt}`；再次检查 issuer/app，按 `(issuer,openid)` 匹配身份，建立本站会话，建议到期不超过 sessionExpiresAt。303 跳到干净的本站页面。回调 no-store/no-referrer，禁止记录 code、Cookie、请求 body 和密钥。不能依据 URL openid 建立身份。

授权码 60 秒、一次性原子消费，绑定 app/redirect/state/PKCE/session。错误兑换不会消费有效码。

## 登录和退出边界

首次授权页展示原生公众号 QR，手机扫码回调只确认服务器身份；原桌面浏览器 `/sso/complete` 才设置 `__Host-wx_sso`（host-only、HttpOnly、Secure、Lax、604800 秒）。浏览器完成接口同源 CSRF 校验，业务方无需调用。

`GET {issuer}/sso/logout` 展示确认页，POST 同源+CSRF 才撤销中央会话。中央退出不注销 A/B 已有本地会话；本站退出由接入方实施。账号权限、审批与注册政策仍属本站。

部署网关本身不能宣称线上站点已互通。验收需真实 A 登录→同浏览器 B 自动进入→退出/过期需扫码，并区分模拟微信测试与真实微信生产验收。
