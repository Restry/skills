# SSO 发布与验收

实现提交 `fac499adfb5784e2ad32f1153330e6c2f7def852` 已推送 main，并部署两套生产实例。发布任务均 succeeded/done，生产回读两库存在 SsoSession，App/WxLoginToken 数量保持发布前值（造悟者 12/255739，莆阳 9/34648）。跨站真实微信扫码和业务方本地会话验收仍待客户端改造，不能据发布成功宣称已互通。协议权威源为仓库 docs/SSO.md；后续仍须核实目标实时状态。

两实例分别配置 `SSO_ISSUER` 为各自 HTTPS origin（无末尾 /），`SSO_SESSION_KEY` 为独立随机 32 bytes、64 hex，保存在门神并经保护机制注入。禁止复用测试零密钥或在日志显示。缺配置时 SSO 503；旧 QR/pay/internal 保持原功能。

发布前备份并核对运行用户、数据库、旧记录数、迁移历史和可恢复制品。增量迁移 `20261031000000_gateway_sso` 新增 App.ssoRedirectUri、SsoSession/SsoTransaction/SsoCode；`20261031000001_native_login_prerequisites` 幂等补齐原生 App 相关列。审阅实际 SQL；只用 prisma migrate deploy，禁止 db push --accept-data-loss/reset。若现网 schema/迁移历史异常，先只读核实，禁止重建数据表。部署包包含 lockfile 和 pnpm-workspace.yaml。

先冻结安装、generate、build，再按既有平台顺序执行安全迁移和重启，两个实例均需发布。保留原 .env 和权限，校验部署版本、进程及新路由，不用 CLI 外层 exit 0 替代远程结果。

会话为首次扫码起七天绝对有效，访问 A/B 不续期；Cookie 由原桌面浏览器 complete 响应设置，不能只在微信手机回调设置。只支持同 issuer；中央退出不自动删除网站本地会话。

现有 active App 需精确登记 ssoRedirectUri，不能覆盖 finalizePath/callbackUrl，当前无 UI。只登记已上线客户端真实回调；无授权不建生产测试 App/身份。接口和 HMAC 字符串约定见 docs/SSO.md 与 wx-gateway-integrate/references/sso.md。

验收：父控制器独立跑 PostgreSQL 行为测试、继承回归、tsc；真实浏览器证明 A 原生扫码确认→桌面 Cookie→B 无扫码→session expiry 不变→退出失效。模拟微信响应只算协议测试，不能报告生产扫码成功。缺生产授权登录或真实扫码时明确剩余边界。
