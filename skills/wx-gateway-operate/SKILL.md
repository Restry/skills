---
name: wx-gateway-operate
description: Use when operating WeChat gateway apps, SSO or callbacks.
---

# 微信网关运维

维护网关本身的接入注册、消息路由、部署、SSO 和故障排查。业务网站初次接入使用 `wx-gateway-integrate`；部署平台操作使用 `bounded-deployment-operations`。本技能不授权生产变更，执行范围以用户当前指令为准。

## 目标与边界

| 实例 | 域名 | 数据库 | 端口 | 状态 |
|---|---|---|---|---|
| wx-gateway（造悟者） | wx.mvp.restry.cn | wx_gateway | 3794 | 当前维护目标 |
| wx-gateway-pucs（莆阳） | wxmsg.mvp.restry.cn | wx_gateway_pucs | 3800 | 用户停用，禁止启动或随批次部署 |

运行目录 `/opt/mvp-apps/<instance>`；实际本地仓库、运行用户和发布版本先查证。莆阳保留配置与数据，用户明确恢复前不改变停用状态。不得因健康检查而启动它。

## 主流程

1. 锁定具体应用、实例和操作；读取生产安全字段及当前配置。注册名称与域名精确匹配，不用模糊搜索结果直接批量写入。
2. 根据下表只加载相关附录。修改前保留可恢复配置和数据；不输出 secret、Cookie、连接串、隐藏后台路径或签名 URL。
3. 执行最小变更。配置管理由控制器直接操作；非简单代码修改按用户当前执行器规则处理。禁止擅自修改业务方源码、部署或其他实例。
4. 回读精确目标，核对状态和未选对象；发布核对产物版本、实际进程与公网行为。外层命令 exit 0 不代表应用发布成功。
5. 报告实际变更、验证边界和剩余阻塞。真实微信扫码、替身协议验证和页面可打开分别报告，不互相替代。

## 必须保留的约束

- 业务方共享公众号唯一回调；access_token 由网关集中托管，业务方与排查脚本不得另行拉取使缓存失效。
- 核对实际端点的 HMAC payload 和 key 编码；不能因 secret 外观为 hex 就解码。签名比较使用恒时校验；修改契约同时更新接入文档和测试。
- 用户要求删除接入：撤销注册、清回调并清关联路由，保留扫码与支付历史；不扩大成删除网站。禁止撤销 `admin`、`selftest`。
- 数据库仅审阅后执行增量迁移；禁止 reset、`db push --accept-data-loss` 或重建表绕过错误。
- SSO 保留本站原二维码及备用入口，不显示中央扫码、确认或检查页。共享中央会话的接入站统一退出；后台仍校验管理员权限。
- 未经授权不 push、不部署；只处理明确获准且启用的实例。凭据通过受保护配置或 `vault` 取得，不写入技能与提交。

## 按需参考

| 场景 | 文件 |
|---|---|
| 注册、撤销、邀请码、消息路由与用户绑定 | [接入管理](references/app-management.md) |
| 发布、克隆实例、远程执行与凭据传递 | [部署运维](references/deployment.md) |
| 原二维码、无感登录、统一退出、Cookie/CSP 与验收 | [SSO](references/sso-operations.md) |
| 回调、SSE、签名、消息、菜单、模板与自检 | [排错与微信接口](references/troubleshooting.md) |

可执行工具：`scripts/register-app.py` 注册；`scripts/selftest.py` 协议回归；`scripts/inspect-wx-templates.js` 模板查询。运行前读取脚本参数和副作用；selftest 可能写测试状态，生产执行需在授权范围内。配置撤销无需运行整套写入型自检；验证目标已不可用及其他接入未变化即可。
