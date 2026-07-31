---
name: separate-session-history-context-and-tools
description: |
  当用户要拆分 Agent 的会话状态、消息历史、长期记忆/RAG、动态政策与实时查询，或询问“放 Session、History Provider、Context Provider 还是 Tool / where should this state or context live?”时调用。不要用于通用中间件选层、状态恢复完整性或 Skill 供应链治理。
source_book: 《Microsoft Agent Framework》 Microsoft
author: Microsoft
source_chapter: Agent Pipeline · Context layer；Conversations & Memory · Session；Context Providers
source_lines: 922-927, 3992-4009, 4069-4075, 17211-17241
tags: [agent, session, chat-history, context-provider, tools, memory, rag, maf]
related_skills:
  - slug: govern-agent-state-lifecycles
    relation: composes-with
---

# 分离 Session、History、主动 Context 与按需 Tool

## R — 原文（Reading）

> “The context layer runs before each LLM call to build the full message history and inject additional context. ChatClientAgent has two distinct provider types: ChatHistoryProvider (single) — Manages conversation history storage and retrieval; AIContextProviders (list) — Injects additional context like memories, retrieved documents, or dynamic instructions.”
>
> — Microsoft, *Agent Pipeline · Context layer*, 原文第 922–927 行

自行翻译：上下文层在每次 LLM 调用前运行，用于构建完整消息历史并注入额外上下文。`ChatClientAgent` 有两类不同的 Provider：唯一的 `ChatHistoryProvider` 负责消息历史的存取；多个 `AIContextProvider` 负责注入记忆、检索文档或动态指令。

> “A good rule of thumb: if the agent should have this information every single time it runs, use a context provider. If the agent should fetch it only when relevant, use a tool.”
>
> — Microsoft, *Context Providers · Why not just use tools?*, 原文第 17240–17241 行

自行翻译：一个实用判断是：如果 Agent 每次运行都必须拥有某项信息，就使用 Context Provider；如果只应在相关时才获取，就使用 Tool。

---

## I — 方法论骨架（Interpretation）

1. 不要把 Session、聊天历史、长期记忆、RAG 和实时查询统称为“memory”；先按责任拆开。
2. `AgentSession` 是跨多次 run 的会话连续性容器，保存本会话状态、索引键及服务侧会话标识。
3. 消息账本只有一个 owner：由 `ChatHistoryProvider` 负责加载、追加与持久化，避免多处重复写历史。
4. 每轮都必须可见、由开发者保证提供的偏好、政策、RAG 结果或动态指令，交给可信的 `AIContextProvider` 主动注入。
5. 只有在当前问题相关时才需要、并允许模型决定何时查询的信息，做成参数收窄的 Tool。
6. Provider 实例可跨 Session 复用，因此会话专属值必须进入 Session，不能藏在 Provider 实例字段里。
7. Context 每轮消耗 token 但不会漏取；Tool 按需付费，却可能漏调用、选错工具或传错参数。
8. 服务侧 conversation/session ID 只表示 Provider 范围内的连续性，不代表应用用户或租户授权。
9. 最终设计应同时回答四个问题：状态归谁、账本归谁、谁触发取数、该信息是否每轮必需。

---

## A1 — 书中的应用（Past Application）

### 案例 1：Alice 的多轮会话（绑定案例 c02）
- **问题**：第一轮告诉 Agent“我叫 Alice，喜欢徒步”，第二轮只问“你记得我什么”。
- **方法论的使用**：两次调用显式复用同一个 `AgentSession`，把连续性放在 Session，而不是假设 Agent 实例自己记住用户。
- **结论**：跨 run 的会话上下文应由明确的 Session 生命周期承载。
- **结果**：第二轮能使用第一轮的姓名和爱好信息；案例证明的是 Session 连续性，不是跨会话长期记忆或授权安全。

### 案例 2：Contoso 退货政策 RAG（绑定案例 c04）
- **问题**：支持助手需要按问题检索退货政策，而不是把全部政策写进聊天历史或常驻系统提示。
- **方法论的使用**：通过 `TextSearchProvider` 注入与 return/refund 问题相关的政策片段、来源名与链接。
- **结论**：外部知识检索属于 Context Provider 注入面，和消息账本分工；实时业务动作则仍应保留给 Tool。
- **结果**：Agent 可依据检索片段回答并在具备来源元数据时给出引用，减少无关政策的常驻上下文成本。

---

## A2 — 触发场景（Future Trigger）★

### 正向 Trigger / Positive triggers

1. 正在设计多轮 Agent，需要决定草稿、偏好、聊天记录、RAG 政策和实时数据分别放在哪里。
2. 发现 Agent 单例、Provider 字段或共享缓存里混入用户/会话状态，担心并发串租户。
3. 在 Context Provider 与 Tool 之间犹豫：信息究竟应每轮自动出现，还是相关时才让模型查询。
4. 需要审查 provider conversation ID、Session ID 与应用侧用户/租户 owner 映射。
5. 想降低每轮上下文成本，同时避免模型漏取必须遵守的政策或租户约束。

### 精确语言信号 / Exact language signals

- 中文：`这个状态该放 Session 还是 Provider？`、`聊天历史和 RAG 怎么分？`、`每轮注入还是做成工具？`、`为什么会串会话/串租户？`、`conversation ID 能当授权吗？`
- English: `Session vs history provider`, `context provider vs tool`, `where should agent memory live?`, `inject every run or fetch on demand?`, `provider state leaks across sessions`, `is conversation_id an authorization boundary?`

### Negative triggers（出现时不应调用）

- 只是在决定横切逻辑放 Agent/Function/ChatClient 哪层 middleware：应转运行面定位方法，不用本 skill。
- 重点是 Session/Checkpoint 的可信存储、篡改防护、TTL、配置兼容或恢复：应转状态生命周期治理，不用本 skill。
- 重点是第三方 Skill 的脚本审批、沙箱和供应链：应转可执行 Agent Skill 治理，不用本 skill。
- 只是一般性问“如何防 prompt injection”，且不涉及 Session/History/Provider/Tool 分工：应转 Agent 数据流信任方法。

### 与相邻 skill 的最终区分与负触发

- 若只是在选择 Agent、Function、ChatClient middleware，或区分 per-run/per-session/per-invocation 数据表面，**不触发本 skill**；改用 `place-agent-runtime-surfaces`。
- 若重点是 fresh/reset/restore、Session/Checkpoint 的 owner、tenant、完整性、TTL 或配置兼容，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。
- 若重点是用户、RAG、LLM、Tool、协议与输出 sink 的 provenance、注入或授权，**不触发本 skill**；改用 `preserve-trust-across-agent-dataflows`。
- 若重点是第三方 Skill 的渐进披露、脚本审批、沙箱和供应链，**不触发本 skill**；改用 `design-and-govern-executable-agent-skills`。

---

## E — 可执行步骤（Execution）

1. **建立信息清单并标注生命周期**
   - 列出会话草稿、完整消息、长期偏好、RAG/政策、实时库存/API、服务侧会话 ID。
   - **完成标准**：每项都有“本 run / 本 Session / 跨 Session”“是否每轮必需”“谁触发获取”“读写 owner”四个标注。

2. **分配 Session 与应用侧所有权**
   - 本会话状态、memory key、provider service ID 放入 `AgentSession`；应用存储建立 client handle → user/tenant → service ID 映射。
   - **完成标准**：没有把原始 service ID 当授权；resume 路径会验证已认证主体和 tenant。

3. **指定唯一消息账本**
   - 只让一个 `ChatHistoryProvider` 负责消息加载、追加和持久化，其他 Provider 不复制聊天账本职责。
   - **完成标准**：可画出唯一历史读写路径，且同一消息不会被多个组件重复持久化。

4. **按每轮必要性切分 Context 与 Tool**
   - 每轮必须出现且由开发者保证的信息接入可信 Context Provider；仅相关时获取的信息做成窄 Tool。
   - **完成标准**：每个 Context 项说明“为什么每轮必需”，每个 Tool 有参数 schema、权限边界和不调用时的可接受行为。
   - **判停条件**：若某项既不需要跨 run，也无需外部取数，直接作为当前调用输入，不强行引入 Provider 或 Tool。

5. **清除共享 Provider 的会话字段**
   - 把 `currentUserId`、`memoryId`、messages 等会话专属可变字段迁入 Session；Provider 仅保留线程安全客户端或无租户配置。
   - **完成标准**：代码审计找不到无 Session key 的会话状态字段，并发调用不共享可变用户状态。

6. **做隔离、成本与漏取验证**
   - 并发运行两个租户；尝试跨 owner 的 Session ID；测量 Context 每轮 token；构造需要/不需要实时查询的请求。
   - **完成标准**：无串租户、越权 resume 或隐式角色升权；必需政策不会漏注入，实时 Tool 不会每轮无谓调用。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 任务只是一次性、无跨 run 状态、无外部知识与查询：直接传入调用参数即可，不需要完整四分法。
- 主要问题是 Workflow/Executor/Checkpoint 的创建、复用和恢复：本 skill 不覆盖其生命周期与故障域。
- 主要问题是一般工具审批或输出净化：这属于更广的数据流安全，不应借“Context 分层”代替。

### 必须吸收的绑定反例

- **ce16：不可信 Provider/RAG 注入 system 角色**。Provider 能构造任意角色，不代表其内容可信；只有受控实现和可信底层数据才能产生高信任指令。
- **ce18：从不可信存储恢复 Session**。Session 是下一轮控制数据，不是无害游标；篡改可改写角色并提权。完整存储治理转 `govern-agent-state-lifecycles`。
- **ce21：把 service conversation ID 当授权令牌**。共享 key/project 下必须由应用保存 owner 映射并在 resume 时重验。
- **ce22：在 Context Provider 实例字段保存会话状态**。同一实例跨 Session 使用，会造成状态泄漏与并发覆盖；会话值必须进入 Session。

### 阶段 0 局限与作者盲点

- 文档是 2026 年中的快速演进截面，包、默认值和各语言 SDK 能力不对称；实现前必须核对目标语言和当前版本，不能把示例 API 固化为永久契约。
- 官方 happy path 没有完整证明多租户隔离、缓存一致性、成本上限与灾难恢复；四分法只确定责任，不自动完成这些生产控制。
- “Agent 默认无状态”不等于系统无竞态：Session、Provider、外部存储与 Tool 仍可能共享可变状态。
- Context Provider 主动注入不等于内容自动可信；RAG 包装不会提升来源信任等级。

### 容易混淆的邻近方法论

- `AgentSession` 承载本会话 key/状态；跨会话长期偏好通常位于外部持久存储，由 Context Provider 读取。
- Context 与 Tool 的切分回答“谁在何时取信息”；middleware 选层回答“横切逻辑包裹哪段执行”。
- 本 skill 决定归属，不替代状态 owner、完整性、TTL 和配置兼容性的恢复治理。

---

## 相关 skills

- 与 [`govern-agent-state-lifecycles`](../govern-agent-state-lifecycles/SKILL.md) `composes-with`：先确定信息归属，再治理其 fresh/reset/restore、owner、tenant、完整性与 TTL，形成从分层到安全生命周期的完整路径。

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定候选**：f04, f05
- **绑定案例**：c02, c04
- **绑定反例**：ce16, ce18, ce21, ce22
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
