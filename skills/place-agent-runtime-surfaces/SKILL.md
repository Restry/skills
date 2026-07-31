---
name: place-agent-runtime-surfaces
description: |
  当用户要放置日志、审计、重试、参数校验、request-id、会话草稿等横切逻辑或运行时数据，出现“which middleware / runtime context / 放哪一层 / per-run vs per-session”时调用；按 Agent、ChatClient、Function 与 AdditionalProperties/StateBag/FunctionInvocationContext 的最窄作用域定位。不用于选择 Agent/Workflow 架构，也不用于 Session/History/RAG/Tool 分层或持久化治理。
source_book: 《Microsoft Agent Framework》 Microsoft
source_chapter: Middleware（原文 4789–4945 行）；Runtime Context（5534–5547 行）
tags: [middleware, runtime-context, agent-pipeline, state-scope, observability, maf]
related_skills:
  - slug: separate-session-history-context-and-tools
    relation: composes-with
---

# 将横切逻辑与运行时数据放到最窄执行面

## R — 原文 (Reading)

> “Use the narrowest surface that fits. Per-run metadata belongs in AdditionalProperties, persistent conversation state belongs in the session's StateBag, and tool-argument manipulation belongs in function invocation middleware.”
>
> 自译：使用能够满足需要的最窄执行面。单次运行的元数据应放入 `AdditionalProperties`，持续的会话状态应放入 Session 的 `StateBag`，工具参数的调整应放入函数调用中间件。
>
> — Microsoft, *Middleware · Runtime Context*, 原文 5545–5547 行

---

## I — 方法论骨架 (Interpretation)

1. 先按“覆盖多少执行过程”和“数据活多久”描述责任，再选 API 名称。
2. 包裹所有 `AIAgent` run 的输入输出校验、整轮审计或转换，放 Agent middleware。
3. 只观察或调整本地 `IChatClient` 模型通信的重试、传输指标与请求响应，放 ChatClient middleware。
4. 单次工具调用的参数、结果、授权钳制、跳过或终止控制，放 Function invocation middleware。
5. 仅本次 run 使用的 request-id、tenant hint 等元数据，放 `AgentRunOptions.AdditionalProperties`。
6. 同一会话跨 run 延续的草稿、游标或配置，放 `AgentSession.StateBag`。
7. 不要把这些表面当成同一个全局字典；生命周期过宽会泄漏，过窄会丢失，层级重复会造成双重执行或双重采集。
8. 最后必须用远端 Agent 与双层遥测复核：远端 `AIAgent` 未必有本地 ChatClient，Agent 与 ChatClient 同时观测又可能重复记录敏感数据。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：在 Agent、Function 与 ChatClient 三层放置 Middleware（c27）
- **问题**：同一应用需要整轮输入输出统计、单次工具调用检查和模型通信观测；若都塞进一个拦截器，作用域与能力会混淆。
- **方法论的使用**：官方教程在 Agent run middleware 统计整轮消息输入输出，在 Function invocation middleware 查看工具名与调用结果，在 `IChatClient` middleware 拦截发往推理服务的请求响应；每层都通过 `next` 或 `inner` 延续责任链。
- **结论**：横切逻辑按实际责任放在最窄、确实存在的执行面，而不是统一塞进“middleware”。
- **结果**：教程展示三类拦截器各自独立工作，整轮审计、工具参数/结果检查和模型通信观测落到对应层；文档同时警告，提前终止工具循环可能留下只有 tool call、没有 tool result 的不一致历史。（原文 4789–4945 行）

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 正在实现日志、审计、遥测、重试、输入输出转换或授权校验，但不确定应放 Agent、ChatClient 还是 Function middleware。
2. 正在传递 request-id、tenant-id、用户偏好、会话草稿或工具参数，不确定是 per-run、per-session 还是 per-invocation 数据。
3. 同一逻辑在多个层重复执行，出现重复 span、重复日志、重复重试或敏感信息双份落盘。
4. 本地 `ChatClientAgent` 要替换或组合远端 A2A Agent，需要判断现有 ChatClient 扩展是否仍有效。

### 语言信号 (用户的话里出现这些就应激活)

- “这段逻辑该放哪个 middleware？” / “Which middleware layer should own this?”
- “request-id 放 AdditionalProperties 还是 StateBag？” / “per-run vs per-session runtime context”
- “工具参数校验应该在 Agent 层还是 function invocation middleware？”
- “Why is telemetry duplicated at the agent and chat-client layers?” / “为什么 trace 重复了？”

### 明确不触发

- 用户尚未决定用函数、Agent、Skill、Workflow 还是人审，正在做整体架构选型。
- 用户要区分 Session、ChatHistoryProvider、AIContextProvider、RAG 与 Tool 的职责。
- 用户要设计持久状态的 owner、tenant、完整性、TTL，或跨进程 Durable 恢复。

### 与相邻 skill 的最终区分与负触发

- 若尚未决定使用函数、Agent、Skill、Workflow、Harness 还是人审，**不触发本 skill**；先用 `choose-minimum-sufficient-agent-architecture` 做全局选型。
- 若问题是 Session、ChatHistoryProvider、AIContextProvider、RAG 与 Tool 分别承载什么，**不触发本 skill**；改用 `separate-session-history-context-and-tools`。
- 若问题是对象能否跨 run 复用，以及持久状态的 owner、tenant、完整性、配置兼容和 TTL，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后，agent 应按以下步骤执行：

1. **建立责任清单**
   - 逐项列出横切逻辑或运行数据，标注目标对象、覆盖范围、生命周期、是否修改数据以及所需能力。
   - 完成标准：每项都回答“观察/修改什么、覆盖一轮/一次模型调用/一次工具调用、活多久”，不存在笼统的“加 middleware”。

2. **为横切逻辑选择最窄拦截层**
   - 整轮 `AIAgent` 行为放 Agent middleware；仅本地模型通信放 ChatClient middleware；单次工具参数、结果与执行控制放 Function invocation middleware。
   - 完成标准：每项逻辑只指定一个主落点，并写明为何更宽或更窄的层不合适。
   - 判停条件：若目标 Agent 是远端代理且不存在本地 `IChatClient`，禁止选择 ChatClient middleware，改用公共 Agent 层或远端服务自身能力。

3. **为运行数据选择生命周期表面**
   - 单次 run 元数据放 `AdditionalProperties`；跨 run 的会话状态放 `StateBag`；单次工具调用参数和结果控制留在 `FunctionInvocationContext`。
   - 完成标准：形成字段级映射表，每个字段有唯一 owner、写入点、读取点和清理时机。

4. **审查责任链与协议完整性**
   - 确认 middleware 正确调用 `next`/`inner`；流式与非流式路径均有对应处理；若终止工具循环，保证 tool call/result 历史仍一致。
   - 完成标准：每条链都有继续、短路和异常三条路径说明，流式行为不因只实现非流式拦截器而被意外降级。

5. **验证远端兼容与去重**
   - 用一个无本地 ChatClient 的远端 `AIAgent` 场景检查层级假设；再同时开启 Agent/ChatClient 观测，检查是否重复 span、重复重试或重复记录敏感内容。
   - 完成标准：远端场景不依赖不存在的扩展面；同一责任只执行/采集一次；生产环境未记录不必要的提示词、响应、函数参数或结果。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 系统仍在函数、Agent、Skill、Workflow 或人审之间选型；应先做最低充分架构判断。
- 问题是 Session、History、长期记忆、RAG、动态指令与 Tool 如何分层，而非运行面与生命周期定位。
- 问题是持久化状态的 owner、tenant、完整性、TTL、跨版本恢复或 Durable execution；这些属于状态治理与持久化边界。

### 作者在书中警告的失败模式

- **ce05**：同时在 Agent 与 ChatClient 层开启敏感遥测，会让相同 prompt、响应、函数参数和结果进入两套 span，扩大泄漏面与保留量。
- **ce30**：Python 1.6.0 的 instrumentation 默认值发生变化；升级后即使代码没有显式开启，也可能自动发 span，与自定义遥测重复或把数据送往未预期后端。
- Middleware 若不继续调用 `next`，会意外截断责任链；Function middleware 终止工具循环还可能留下缺少 tool result 的不可用历史。（原文 4802–4804、4894–4898、4921–4928 行）

### 作者的盲点 / 时代局限

- 文档主要展示单个中间件的 happy path，较少量化多层责任链的延迟、故障传播、重试叠加和采样成本。
- “关注点分离”不能自动解决敏感数据治理；字段脱敏、采样、保留周期和下游 trace 权限仍需应用设计。
- 远端 Agent 统一为 `AIAgent` 只保证公共运行契约，不保证本地模型客户端、相同状态能力或相同扩展点。

### 版本边界

- 本方法基于 2026-07-10 左右的文档截面；middleware API、流式 overload 与 instrumentation 默认值必须按目标 SDK 版本复核。
- ce30 是明确的 Python 1.6.0 版本变化，不应外推为所有语言、所有版本都默认开启遥测。
- Function invocation middleware 在该截面只支持使用 `FunctionInvokingChatClient` 的 `AIAgent`（例如 `ChatClientAgent`）；不能假设任意远端 Agent 都支持。（原文 4906–4909 行）

### 容易混淆的邻近方法论

- `AgentSession.StateBag` 是跨 run 会话状态表面，不等于消息历史、长期记忆数据库或授权边界。
- Agent middleware 适用面最广，但只能依赖所有 `AIAgent` 的公共能力，不能据此假设底下存在 `IChatClient`。
- “放在最窄层”不是越底层越好，而是选择仍能覆盖所需责任、又不扩大生命周期和数据暴露的最窄表面。

---

## 相关 skills

- 与 [`separate-session-history-context-and-tools`](../separate-session-history-context-and-tools/SKILL.md) `composes-with`：先区分运行数据与横切逻辑的最窄执行面，再确定 Session、History、主动 Context 与按需 Tool 的职责，可避免“作用域”和“信息归属”混为一谈。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定案例**：c27（verified v02 的唯一允许案例）
- **绑定反例**：ce05 / ce30
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
