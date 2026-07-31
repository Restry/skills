---
name: preserve-trust-across-agent-dataflows
description: |
  当用户要审计用户/History/Context-RAG/LLM/Tool/第三方协议/AG-UI 到 HTML、SQL、代码等 sink 的信任与 provenance，出现“prompt injection”“role spoofing”“untrusted tool arguments”“state/context injection”“data egress”时调用；要求变换不升级信任并收窄控制面。不用于 CodeAct/direct tools 选型、Skill 脚本供应链或 Session/Checkpoint 生命周期治理。
source_book: 《Microsoft Agent Framework》 Microsoft
source_chapter: Agent Framework overview · Third-Party Systems；Agent Safety；Agent Security with FIDES；AG-UI · Security Considerations
source_lines: 67-81, 3202-3277, 3313-3331, 14853-14979
tags: [security, trust-boundary, provenance, prompt-injection, ag-ui, output-sink, maf]
related_skills: []
---

# 沿 Agent 数据流保持来源信任并收窄协议控制面

## R — 原文（Reading）

> “Data flows through several components when an agent runs: user input, chat history providers, context providers, the LLM service, and function tools. Each boundary where data enters or exits your application represents a potential attack surface.”
>
> — Microsoft, *Agent Safety · Understand trust boundaries*, 原文第 3207–3209 行

自行翻译：Agent 运行时，数据会流经用户输入、聊天历史 provider、上下文 provider、LLM 服务和函数工具。数据每次进入或离开应用的边界，都可能成为攻击面。

> “Treat LLMprovided arguments as untrusted input, similar to user input in a web API.”
>
> — Microsoft, *Agent Safety · Validate function inputs*, 原文第 3227 行

自行翻译：把 LLM 生成的参数视为不可信输入，就像 Web API 对待用户输入一样。

---

## I — 方法论骨架（Interpretation）

1. 不按组件品牌推定安全，而按双向数据流画信任边界：用户、History、Context/RAG、LLM、Tool、第三方系统、协议客户端与输出 sink。
2. 给每条数据记录来源、完整性、机密性、tenant/owner、授权范围和第三方处理边界；包装、检索、摘要或模型重述都不能自动提高信任。
3. `system` 角色只由可信开发者和受控 provider 构造；用户、assistant、tool 与可被外部写入的 RAG 内容持续保持不可信。
4. 模型生成的工具参数必须再次通过 allowlist、类型/范围、长度、路径归一化、参数化查询与服务端授权。
5. 模型输出进入 HTML、SQL、shell、代码执行或其他敏感 sink 前，要验证、转义、净化，或转换成窄类型接口。
6. 协议兼容不继承供应商的许可、地域、数据保留、授权和费用边界；跨第三方双向流动必须显式审计。
7. AG-UI 是规范/反例分支：客户端可提交 messages、tools、State、Context、ForwardedProperties，这些都是控制面，不是无害元数据。
8. 不可信浏览器或移动端不应直接构造完整 AG-UI envelope；由可信前端重建角色、工具与状态并做 schema/allowlist/tenant 授权。
9. 可借用 FIDES 的标签传播思想让 provenance 随工具调用传播，但该文档截面中的实现是 Python-only experimental，不能当作跨语言成熟保证。

---

## A1 — 书中的应用（Past Application）

### 案例 1：Contoso 退货政策通过 RAG 按请求注入（c04）

- **问题**：支持助手需要使用外部政策回答退货问题，又不应把全部政策永久写进系统提示。
- **方法论的使用**：官方把 `TextSearchProvider` 接入助手，检索器返回政策片段及来源名称/链接，形成可追溯的 Context/RAG 输入。
- **结论**：外部知识应保持独立来源与引用元数据，按请求注入，而不是因进入上下文就等同开发者 system 指令。
- **结果**：Agent 能根据检索片段回答并附来源；但示例没有证明数据源防篡改、tenant 授权或 prompt-injection 防护。

### 案例 2：A2A 远程 Agent 被包装成统一 AIAgent（c08）

- **问题**：调用方需要通过协议访问远端 Agent 的长任务，同时使用统一运行接口。
- **方法论的使用**：教程把 A2A 端点包装成 `AIAgent` 并使用 continuation token 轮询。
- **结论**：统一协议契约可以简化调用，但远端系统仍是独立信任与数据处理边界；适配成 `AIAgent` 不会继承本地许可、鉴权或数据保留策略。
- **结果**：示例证明协议互操作和轮询行为，不证明远端服务已满足组织合规、安全或授权要求。

### 案例 3：OpenAI Chat Completions 暴露海盗 Agent（c24）

- **问题**：已有 OpenAI HTTP 客户端需要访问框架内 Agent。
- **方法论的使用**：官方将 Agent 映射到兼容 Chat Completions 的 HTTP 端点并支持普通/流式响应。
- **结论**：协议托管与 Agent 逻辑可解耦，但兼容 envelope 只是通信边界，仍需应用自行做认证、授权、输入校验与输出过滤。
- **结果**：教程证明标准客户端可获得结构化响应，不是协议暴露安全性的成功案例。

> **AG-UI 证据声明**：本单元**没有 AG-UI 的独立官方正向成功案例**。AG-UI 仅作为规范性安全分支，并由 ce28/ce29 反例支撑；不得把推荐架构或 validation checklist 虚构成已验证生产案例。

---

## A2 — 触发场景（Future Trigger）★

### 正向 Trigger / Positive triggers

1. 要为 Agent 画用户、History、RAG、LLM、Tool、第三方服务和输出 sink 的数据流/威胁模型。
2. 怀疑 RAG 文档、tool result 或 assistant 内容被错误提升为 `system` 角色，或来源经模型重述后丢失 provenance。
3. 模型生成的文件路径、SQL、金额、账户、命令或 API 参数准备进入真实工具，需要服务端再校验。
4. 浏览器/移动端通过 AG-UI 发送 role、tools、State、Context 或 ForwardedProperties，需要设计可信前端中介。
5. 数据要出组织边界到第三方模型、Agent、MCP/协议服务，需检查字段、地域、保留、授权和成本。

### 精确语言信号 / Exact language signals

- 中文：`沿 Agent 数据流画信任边界`、`RAG 结果能当 system 吗？`、`模型生成参数还要校验吗？`、`AG-UI state 会不会注入？`、`第三方 Agent 会拿到哪些数据？`、`输出进 HTML/SQL 怎么净化？`
- English: `agent dataflow trust boundaries`, `preserve provenance`, `indirect prompt injection`, `untrusted LLM tool arguments`, `role spoofing`, `AG-UI state/context injection`, `trusted frontend server`, `sanitize output sinks`, `third-party data egress`.

### Negative triggers（出现时不应调用）

- 只是决定大量查询、循环和聚合是否折进 CodeAct，以及哪些副作用保留逐调用审批：应转 `choose-codeact-or-direct-tools-by-risk`。
- 只是治理 Agent Skill 的 `SKILL.md`、resources、scripts、远程 archive、load/read/run 审批或供应链：应转 `design-and-govern-executable-agent-skills`。
- 只是决定 Session、History Provider、Context Provider 与 Tool 各自放什么信息：应转 `separate-session-history-context-and-tools`；只有出现信任/注入/跨租户风险时才叠加本 skill。
- 只是治理序列化 Session/Checkpoint 的 owner、TTL、完整性和恢复版本：应转持久状态生命周期 skill。

### 与相邻 skill 的最终区分与负触发

- 若只是在 CodeAct 与 direct tools 之间按调用密度、宿主逃逸和审批原子性切分，**不触发本 skill**；改用 `choose-codeact-or-direct-tools-by-risk`。
- 若只治理 Agent Skill 的指令、资源、脚本、远程 archive 与 load/read/run 供应链，**不触发本 skill**；改用 `design-and-govern-executable-agent-skills`。
- 若只决定 Session、History Provider、Context Provider 与 Tool 各自承载什么，尚未出现注入、授权或跨边界风险，**不触发本 skill**；改用 `separate-session-history-context-and-tools`。
- 若只治理序列化 Session/Checkpoint 的 owner、tenant、完整性、TTL 与恢复版本，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。

---

## E — 可执行步骤（Execution）

1. **绘制双向数据流与敏感 sink**
   - 标出用户、客户端协议、History、Context/RAG、LLM、Tool、第三方服务、日志/遥测及 HTML/SQL/shell/代码等 sink 的输入和输出。
   - **完成标准**：每条跨进程、跨组织或跨解释器边界都有方向、字段与处理者；不存在笼统的“框架内部可信”。

2. **建立字段级 provenance 与标签**
   - 为数据项记录 source、integrity、confidentiality、tenant/owner、允许用途、保留/地域和变换链；摘要、检索和模型重述沿用最低来源信任。
   - **完成标准**：任一工具参数或输出字段都能追溯原始来源；没有因 role 名、RAG 包装或 LLM 重述发生隐式信任升级。

3. **锁定角色与 provider 控制权**
   - 只让可信开发者/受控 provider 构造 `system`；用户、assistant、tool 和可外部写入内容保持不可信；审查 History/Context provider 可生成哪些角色。
   - **完成标准**：不可信数据不能进入 system；未知 provider 不能构造高信任角色；间接 prompt injection 测试不会改变安全策略。

4. **收窄工具入口与输出 sink**
   - 对 LLM 工具参数执行 allowlist、类型/范围/长度、路径归一化、参数化查询和服务端授权；对 HTML/SQL/shell/代码等输出做转义、净化或窄类型转换。
   - **完成标准**：越权账户、路径穿越、超范围金额、字符串拼接 SQL/命令和恶意 HTML 均 fail closed；日志不泄露敏感原文。

5. **重建协议控制面并审计第三方流出**
   - 对 AG-UI 使用可信前端，仅接受有限用户输入，由服务端重建 roles/tools/State/Context/ForwardedProperties，并做 schema、size、allowlist、用户/tenant 授权；对第三方列出发送/接收字段、地域、保留、许可与成本。
   - **完成标准**：客户端不能指定 system/assistant/tool role、未授权工具或任意 state 字段；`state.accountId` 等对象由服务端按认证身份重新解析；所有第三方流向有批准记录。
   - **证据约束**：此 AG-UI 步骤来自规范与反例，不得报告为官方生产成功案例。

6. **执行攻击性验证与审计回放**
   - 测试恶意 RAG 文档、伪 tool message、模型生成越权参数、AG-UI state/context/forwarded-properties 注入、第三方回传攻击载荷与恶意 HTML/SQL/shell 输出。
   - **完成标准**：所有路径均在敏感动作或 sink 前拒绝/净化；审计记录保留来源与策略决策但不泄露秘密；可回放一次跨边界决策。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 任务只是决定 CodeAct 与 direct tools 的性能/审批切分；那是执行编排问题，不是数据来源信任问题。
- 任务只是一般字段放置或 Session/History/Context 分层，尚未出现注入、授权、跨边界或输出 sink 风险。
- 任务只治理 Skill 包内脚本与资源；一般数据流方法不能替代第三方 Skill 的完整供应链审计。
- 任务只治理 Checkpoint/Session 的持久化 owner、TTL 和版本恢复；本 skill 可指出状态是不可信输入，但不完成生命周期设计。

### 绑定反例与失败模式

- **ce02：把第三方协议接入当成微软托管信任边界**。框架适配不继承第三方许可、地域、保留、授权或费用；必须审计双向字段流。
- **ce16：允许不可信 Provider/RAG 注入 system**。外部内容一旦被角色提升，就把攻击者文本伪装成开发者策略。
- **ce17：直接渲染或执行 LLM 输出**。模型可能复述攻击载荷；HTML/JavaScript、SQL、shell 和代码 sink 前必须净化或类型化。
- **ce28：AG-UI 直连不可信浏览器/移动端**。客户端可伪造 system/assistant/tool 消息与工具定义，接管协议控制面。
- **ce29：只清洗 message.text，却信任 State、Context、ForwardedProperties**。这些字段同样可携带隐藏指令或下游控制数据。

### AG-UI 规范/反例分支限制

- AG-UI 的推荐 trusted frontend pattern、schema 校验与 allowlist 是**规范性设计建议**，不是本资料中的官方生产成功案例。
- c04、c08、c24 分别说明 RAG、A2A、OpenAI-compatible 协议边界，但都不能替代 AG-UI 成功案例，更不能证明完整安全链已验证。
- 若项目并未使用 AG-UI，不要为了套用文档引入该协议；仍可使用本 skill 的通用数据流、角色、参数和 sink 方法。

### 局限与版本边界

- 本方法基于 2026 年中快速演进的文档截面；AG-UI、FIDES 和多个 SDK 能力处于 preview/experimental，落地前必须核对当前官方 API 与默认值。
- FIDES 在该截面是 **Python-only experimental**；可以借鉴 integrity/confidentiality 标签传播，但不得承诺 .NET/Go 已有同等成熟实现或确定性保障。
- 通用 best practices 仍含启发式防护；prompt injection 不会因 allowlist 或 system prompt 单点措施而被“彻底解决”。
- Provider-neutral 只说明抽象统一，不代表供应商部署、鉴权、数据地域、托管工具和运维能力等价。
- 官方示例多为 happy path，未量化多租户隔离、攻击检测误报/漏报、性能成本和灾难恢复；必须在自己的威胁模型下测试。

### 容易混淆的邻近方法论

- provenance 不是“记住来源链接”而已；它还要携带完整性、机密性、tenant、用途与变换链。
- role 是协议语义，不是信任证明；`tool` 和 `assistant` 内容仍可能来自外部或被攻击者影响。
- schema-valid 不等于 authorized；AG-UI state 结构合法后仍需按认证用户重新解析资源所有权。
- Tool Approval 只提供人类确认点，不能替代参数校验、最小权限和输出净化。

---

## 相关 skills

本 skill 不声明出边；它是通用信任治理基础节点。`design-and-govern-executable-agent-skills` 与 `choose-codeact-or-direct-tools-by-risk` 均通过 `composes-with` 将供应链或执行编排叠加到本方法的数据流控制上。

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定候选**：f12, p12, p14, p15, p30
- **绑定案例**：c04, c08, c24（均有明确证据边界；无 AG-UI 正向案例）
- **绑定反例**：ce02, ce16, ce17, ce28, ce29
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
