---
name: choose-codeact-or-direct-tools-by-risk
description: |
  当用户要在 CodeAct/execute_code 与 direct tool calling 间分配调用，出现“many tool calls”“loops/aggregation”“per-call approval”“call_tool 是否仍在沙箱内”时调用；按调用密度与副作用、敏感度、可逆性、影响范围切分混合执行面。不用于一般数据流信任审计、Function/MCP/Hosted Tool 来源选型或审批等待状态机。
source_book: 《Microsoft Agent Framework》 Microsoft
source_chapter: CodeAct · When CodeAct is a good fit；Integrations · Hyperlight CodeAct；Agent Safety · Require approval for high-risk tools
source_lines: 3122-3168, 3240-3249, 13363-13426
tags: [codeact, direct-tools, approval-granularity, sandbox, host-tools, risk, maf]
related_skills:
  - slug: preserve-trust-across-agent-dataflows
    relation: composes-with
---

# 按调用密度与风险选择 CodeAct 或直接工具

## R — 原文（Reading）

> “`call_tool(...)` is a bridge back to host callbacks; it is not an in-sandbox reimplementation of the tool. That means provider-owned tools still execute in the host process, with whatever filesystem, network, and credentials the host process itself can access.”
>
> — Microsoft, *Integrations · Hyperlight CodeAct*, 原文第 13371–13373 行

自行翻译：`call_tool(...)` 是回到宿主回调的桥梁，不是在沙箱中重新实现工具。因此，provider 管理的工具仍在宿主进程执行，并能使用宿主进程本身可访问的文件系统、网络和凭据。

> “Put cheap, deterministic, safe-to-chain tools on the provider so the model can compose many calls inside one `execute_code` turn. Wrap side-effecting or sensitive operations in `ApprovalRequiredAIFunction` (and consider keeping them as direct agent tools instead) so each invocation stays individually visible and approvable.”
>
> — Microsoft, *Integrations · Hyperlight CodeAct*, 原文第 13388–13393 行

自行翻译：把廉价、确定、可安全串联的工具交给 provider，让模型在一次 `execute_code` 中组合多次调用；对有副作用或敏感操作使用 `ApprovalRequiredAIFunction`，并考虑继续作为直接工具暴露，使每次调用都能单独可见、单独审批。

---

## I — 方法论骨架（Interpretation）

1. 先判断瓶颈：CodeAct 的收益来自把循环、分支、过滤、聚合与转换压进一次程序执行，而不是“写代码更高级”。
2. 再判断风险：每个操作分别按副作用、数据敏感度、可逆性与影响范围评分；“只读”不自动等于低风险，批量读取工资或凭据仍可高风险。
3. 低风险、确定、窄返回、可安全串联且调用密集的操作可以进入 CodeAct 候选区。
4. 写入、发送、购买、删除、批量敏感读取以及任何必须逐项确认的动作保留为 direct tools。
5. `execute_code` 当前通常是一个整体审批单元；把多个敏感内部调用装进去，会丢失逐调用审批粒度。
6. `call_tool` 会从沙箱回到宿主进程；沙箱的文件挂载与网络 allowlist 只约束沙箱代码，**不自动约束宿主回调的权限**。
7. 因此必须同时设计两层最小权限：沙箱 capability 与宿主工具的身份、凭据、文件、网络及业务授权。
8. 最终方案可以混用 CodeAct 和直接工具；目标是压缩低风险往返，而不是把整个任务强行归入单一模式。

---

## A1 — 书中的应用（Past Application）

### 案例：安全查询走 CodeAct，敏感邮件保持单独审批（c28，必选案例）

- **问题**：Agent 需要反复读取文档、查询数据并可能发送邮件；全部直接调用会增加模型—工具往返，但全部塞进一次代码执行又会隐藏敏感副作用。
- **方法论的使用**：官方 Hyperlight CodeAct 示例把 `fetch_docs` 与只读 `query_data` 作为可组合工具，让模型在一次 `execute_code` 中调用；`send_email` 则用 `ApprovalRequiredAIFunction` 包装，并明确建议敏感操作可保留为 direct agent tool。
- **结论**：低风险密集查询适合折叠，邮件等副作用应保留每次调用的真实参数、可见性与审批原子性。
- **结果**：示例展示了同一 Agent 混用两种执行面的设计：查询减少往返，敏感邮件仍可单独批准或拒绝。
- **宿主边界**：示例同时说明 `call_tool` 回到宿主进程；`FileMounts`、`AllowedDomains` 等沙箱限制只约束沙箱代码，**不会约束宿主工具继承的文件、网络、凭据或业务权限**。（原文第 13363–13393、13424–13426 行）
- **证据边界**：c28 是官方设计示例，不是延迟、安全或生产审批效果的量化成功案例；实际收益和隔离性必须在目标运行时验证。

---

## A2 — 触发场景（Future Trigger）★

### 正向 Trigger / Positive triggers

1. 一个 Agent 要循环、分支、过滤或聚合许多小工具调用，需要决定哪些折叠进 `execute_code`。
2. 同一任务既有大量只读查询，也有付款、发信、删除、部署等副作用，需要混合 CodeAct 与直接工具。
3. 审批 UI 只能看到一段总代码，用户担心无法逐项拒绝内部工具调用。
4. 团队把工具注册到 CodeAct provider，并误以为 `call_tool` 在沙箱内执行或自动受沙箱网络/文件限制。
5. 需要按副作用、敏感度、可逆性和 blast radius 决定审批粒度。

### 精确语言信号 / Exact language signals

- 中文：`CodeAct 还是直接工具？`、`30 次查询怎么减少往返？`、`execute_code 能否一次审批？`、`call_tool 在宿主还是沙箱？`、`哪些操作必须逐项审批？`
- English: `CodeAct vs direct tool calling`, `collapse many tool calls`, `loops and aggregation in execute_code`, `per-call approval`, `approval granularity`, `does call_tool run in the host process`, `sandbox vs host permissions`.

### Negative triggers（出现时不应调用）

- 只是要沿用户、History、RAG、LLM、Tool、AG-UI 与输出 sink 追踪 provenance、prompt injection 或角色信任：应转 `preserve-trust-across-agent-dataflows`。
- 只是选择自定义 Function Tool、MCP Tool 或 Provider-hosted Tool 的来源、托管和版本支持：属于工具类型选型，不是 CodeAct 编排粒度。
- 只是设计审批请求如何跨天等待、checkpoint、恢复、升级和处理迟到响应：应转可恢复人审状态机 skill。
- 只是治理 Skill 自带脚本及 advertise/load/read/run 权限：应转 `design-and-govern-executable-agent-skills`。

### 与相邻 skill 的最终区分与负触发

- 若核心问题是 RAG/LLM/Tool/协议后的来源信任、prompt injection、角色或输出净化，**不触发本 skill**；改用 `preserve-trust-across-agent-dataflows`。
- 若核心问题是 Agent Skill 包内资源、脚本、远程 archive 与 load/read/run 供应链，**不触发本 skill**；改用 `design-and-govern-executable-agent-skills`。
- 若已经决定人审，问题是审批如何跨断线、重启、超时与迟到响应恢复，**不触发本 skill**；改用 `model-recoverable-human-decisions`。
- 若只在 Function、MCP 或 Provider-hosted Tool 之间选择能力来源与托管位置，**不触发本 skill**；先查当前工具支持清单，本 skill 只决定调用编排粒度。

---

## E — 可执行步骤（Execution）

1. **盘点调用图与编排密度**
   - 列出每个工具、预计调用次数，以及循环、分支、过滤、聚合、转换和中间结果依赖。
   - **完成标准**：每项都有调用次数区间和控制流需求；能明确指出模型—工具往返是否真是主要瓶颈。
   - **判停条件**：若任务只有 1–2 次简单调用且无显著编排成本，默认保留 direct tools，跳到步骤 5 做权限核验。

2. **逐操作做四因子风险分级**
   - 对每项标注副作用、数据敏感度、可逆性、影响范围，并记录租户/用户授权与失败后补偿能力。
   - **完成标准**：形成逐工具风险表；任何敏感批量读取、写入、发送、购买、删除或广域操作均未因“只读/可重试”被漏标。

3. **切分 CodeAct 候选与 direct-only 集合**
   - 仅把密集、确定、窄接口、低风险且可安全串联的操作放入 CodeAct；把高风险或需要逐调用可见的操作保留为 direct tools。
   - **完成标准**：每项只有一个默认执行面及书面理由；`execute_code` 内没有必须让审批者逐项拒绝的隐藏动作。

4. **设计审批原子性与展示内容**
   - 明确 `execute_code` 是整体审批还是由内部工具传播审批；direct tools 分别展示真实参数、对象、影响范围与授权主体。
   - **完成标准**：审批者可独立拒绝每个副作用；不存在“一次批准总代码即默许付款 + 发信 + 删除”的组合单元。

5. **核验沙箱—宿主双重权限**
   - 分别列出沙箱文件/网络 capability，以及 `call_tool` 宿主回调的进程身份、凭据、文件、网络和业务 API 权限；为宿主工具做窄接口与服务端授权。
   - **完成标准**：没有把 `FileMounts`/`AllowedDomains` 当成宿主权限控制；宿主工具即使被任意合法参数调用也不超出最小授权。

6. **用混合任务验证收益与失效模式**
   - 测试大量低风险查询 + 至少两个独立副作用；比较往返、token、延迟，并尝试拒绝其中一个副作用、注入宽参数和越权资源访问。
   - **完成标准**：低风险聚合确实减少往返；每个副作用可单独拒绝；沙箱和宿主越权均 fail closed；审计能还原代码及每次宿主调用。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 普通函数或固定批处理已能确定完成任务：不要为了减少几次调用而引入模型生成代码。
- 问题核心是来源信任、prompt injection、消息角色或输出净化，而不是调用编排；应转数据流信任 skill。
- 问题核心是 Function/MCP/Hosted Tool 的 build-vs-buy 和供应商支持矩阵；CodeAct 不回答能力从哪里来。
- 需要跨重启耐久审批时，本 skill 只决定审批原子性，不能替代 request/response、checkpoint、幂等与补偿设计。

### 绑定反例与失败模式

- **ce14：用 CodeAct 包住副作用后丢失逐操作审批**。当前审批围绕整个 `execute_code`；内部扣款、发送或删除无法逐项拒绝时，应保持 direct tools。
- **ce14：把 `call_tool` 当作沙箱内工具**。它实际回到宿主进程；沙箱限制不约束宿主回调，宽权限宿主工具会形成逃逸面。
- **ce15：假设普通 Agent 工具默认需要审批**。通用工具默认可能直接执行；高风险工具必须显式配置 approval-required 机制。

### 局限与版本边界

- 本方法基于 2026-07-10 左右的文档截面；Hyperlight CodeAct 与 .NET 包当时处于 preview，审批传播和 connector API 必须按目标 SDK/运行时重新核对。
- Go 在该截面尚不提供 CodeAct；不要把 Python/.NET 方案直接承诺给所有语言。
- “CodeAct 降低延迟和 token”是架构预期，官方 c28 未提供生产基准；必须以自己的调用密度、模型、工具时延和失败率测量。
- 沙箱不是完整安全证明：宿主工具、凭据、参数校验、业务授权、审计和外部副作用仍由应用负责。
- `execute_code` 的代码块可审计，不等于内部行为天然可理解或可逐项批准；动态分支仍需运行级调用日志。

### 容易混淆的邻近方法论

- “低副作用”与“低敏感度”不是同一维度；大范围只读 PII 查询仍应提高审批和权限强度。
- “在沙箱里”只描述代码运行位置；`call_tool` 的宿主回调是另一权限域。
- “需要人审”不等于“人审可恢复”；跨天等待和重启恢复要另建耐久状态机。

---

## 相关 skills

- 与 [`preserve-trust-across-agent-dataflows`](../preserve-trust-across-agent-dataflows/SKILL.md) `composes-with`：执行面切分后，还必须沿 CodeAct、宿主回调、工具参数与输出 sink 保留 provenance，并重新做服务端授权与净化。

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定候选**：f11, p11, f13, p13
- **绑定案例**：c28（必选）；c16、c20 仅作辅助证据
- **绑定反例**：ce14, ce15
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
