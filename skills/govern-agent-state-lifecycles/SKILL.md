---
name: govern-agent-state-lifecycles
description: |
  当 Agent/Workflow 被单例复用、序列化或 resume，需防止跨 run/tenant 状态污染时调用；信号包括“fresh factory/reset/restore/session ownership/checkpoint integrity/config mismatch/TTL”。不用于 Session-History-Context 分层、HITL 等待状态机，或单独选择 checkpoint 与 Durable 故障域。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflows · State Isolation / Checkpoints（原文 8657–8844 行）；Conversations & Memory · Session（原文 3992–4036 行）
tags: [state-lifecycle, state-isolation, fresh-instance, reset, restore, multi-tenant, integrity, maf]
related_skills:
  - slug: choose-workflow-recovery-layer
    relation: composes-with
---

# 治理 Agent 状态的创建、复用、持久化与恢复生命周期

## R — 原文（Reading）

> It is not recommended to reuse a single workflow instance for multiple tasks or requests, as this can lead to unintended state sharing. Instead, it is recommended to create a new workflow instance from the builder for each task or request to ensure proper state isolation and thread safety. When executor instances are created once and shared across multiple workflow builds, their internal state is shared across all workflow executions.
>
> 中文翻译：不建议让一个 Workflow 实例处理多个任务或请求，否则会意外共享状态。每个任务或请求都应由 builder 创建新的 Workflow，以保证状态隔离和线程安全；若多个 Workflow build 共享一次创建的 Executor，其内部状态会在所有执行间共享。
>
> — Microsoft Agent Framework，State Isolation，原文 8689–8695 行

> Sessions are agent/service-specific. Reusing a session with a different agent configuration or provider can lead to invalid context. If the serialized session contains a service-side session ID, restore it only for the application user or tenant that owns that ID.
>
> 中文翻译：Session 绑定具体 Agent/服务；用不同 Agent 配置或 Provider 复用会产生无效上下文。若序列化 Session 含服务侧会话 ID，只能为拥有该 ID 的应用用户或租户恢复。
>
> — Microsoft Agent Framework，Session · Serialization and restoration，原文 4030–4036 行

---

## I — 方法论骨架（Interpretation）

状态治理的第一步不是选数据库，而是对每一份可变数据回答：属于哪个 run、谁拥有、何时创建、何时允许延续、何时必须清空、从哪里恢复。
`fresh`、`reset` 与 `restore` 是方向相反的三种生命周期动作：fresh 为下一个新任务创建无历史对象；reset 在不得不复用同一对象时清除上一个 run；restore 从可信状态恢复同一个 run 的连续性。
因此 fresh/reset 的完成标准是“下一 run 不继承任何上一次任务状态”，restore 的完成标准却是“同一 run 的合法状态被完整、且仅为原 owner 恢复”。
默认方案是每任务由 factory 创建新的 Workflow、Executor、Agent 与 Session；只共享线程安全、无 tenant/run 状态的客户端、连接池和不可变配置。
有状态 Executor 只有在构造昂贵或明确需要共享时才实现 `IResettableExecutor`；Reset 还必须覆盖外部缓存、Provider 实例字段和子图依赖，不能只清几个本地计数器。
持久化包不是无害聊天记录，而是控制面：它可能包含角色、provider service ID、线程、待处理消息、请求和共享状态。
客户端只应持有不可枚举的应用 handle；服务端把 handle 映射到 owner/user、tenant、run、Agent/Provider 配置版本与可信存储对象。
每次 restore 必须重验当前主体、owner、tenant、状态完整性、schema/config 兼容性、provenance、run 状态和 TTL；任何一项失败都要 fail closed 或走显式迁移。
TTL 只负责到期回收，不证明所有权或完整性；可信恢复也不自动提供跨进程/worker 的 Durable execution。

---

## A1 — 书中的应用（Past Application）

### 案例 1：Alice 的同一 AgentSession 多轮连续性（c02）

- **问题**：第一轮告诉 Agent“我叫 Alice，喜欢徒步”，第二轮只问“你记得我什么”；需要延续同一段会话，而不是让所有用户共享 Agent 实例字段。
- **方法论的使用**：两次 `RunAsync` 显式传入同一个 `AgentSession`；连续性归属于 Session，不隐含在 Agent 单例。
- **结论**：同一会话可有意复用/恢复 Session，但新用户或新任务必须使用 fresh Session。
- **结果**：第二轮能回忆姓名与爱好；该结果证明了同一 owner、同一会话的连续性，不是跨任务复用的许可。

### 案例 2：把研究—写作—审校 Workflow 包装为 Agent（c15）

- **问题**：复杂内部 Workflow 需要以统一 Agent 接口对外运行，并允许 Session 序列化后继续。
- **方法论的使用**：官方将三 Agent 顺序图 `AsAIAgent`，对外通过标准 Run/Streaming/Session 使用；Session 可序列化后恢复。
- **结论**：Workflow-as-Agent 并未消除内部 Workflow、Executor 和 Agent thread 的状态生命周期；恢复必须绑定原图和原 Agent/Provider 配置。
- **结果**：外部只看到一个 Agent，内部仍保持显式研究、写作、审校顺序；序列化能力提供连续性，但不能跨 owner 或任意配置通用。

### 案例 3：Durable Agent 用同一 thread 跨请求与重启继续（c22）

- **问题**：第一次询问三种流行编程语言，第二次只问“哪一种适合初学者”；Function App 可能重启或换实例。
- **方法论的使用**：教程复用同一 `thread_id`，会话历史保存在 Durable Task Scheduler；后续请求恢复同一 Durable Agent 状态。
- **结论**：这是 restore 同一会话，而不是 reset 或 fresh 新任务；thread 必须由服务端绑定原 owner/tenant 和配置。
- **结果**：第二次请求仍知道候选是 Python、JavaScript、Java，并推荐 Python；重启或换 worker 后也能延续。

### 案例 4：子 Workflow 作为父图中的隔离 Executor（c25）

- **问题**：父图要复用文本处理或分析流水线，但不应穿透访问子图内部状态。
- **方法论的使用**：官方通过 `BindAsExecutor` 或 `AsAIAgent` 把完整子图嵌入父图，只经强类型输入输出连接。
- **结论**：组合边界应保留子图内部状态隔离；父图复用“定义/工厂”不等于跨任务复用同一有状态运行实例。
- **结果**：父 Workflow 把子图视为单一步骤，结果继续路由到下游，内部状态不需要暴露给父图。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. DI 容器把 Workflow、Executor、Agent、Provider 或子图注册成 singleton，第二次 run 出现第一次的消息、计数器、缓存或线程历史。
2. 团队争论新任务应创建 fresh 实例、复用后 reset，还是从 Session/Checkpoint restore；三种语义被混用。
3. 多租户系统允许客户端提交 Session、provider conversation ID、checkpoint ID/路径或完整序列化状态来续接。
4. 需要设计 resume envelope、owner/tenant 映射、Agent/Provider 配置绑定、schema 迁移、完整性保护和 TTL。
5. 有状态 Executor 构造昂贵，确实要跨 run 共享，但不知道 `IResettableExecutor` 应清理哪些内部/外部状态。

**中文语言信号**：
- “第二次 workflow run 读到了第一次的状态”
- “fresh、reset 和 restore 到底有什么区别？”
- “客户端传 conversation ID 就能恢复，会不会串租户？”
- “Session/checkpoint 怎么绑定 owner、tenant 和配置版本？”
- “从旧版本 Agent 配置恢复失败，应该迁移还是拒绝？”

### Exact English triggers

- “create fresh workflow/executor/agent/session instances per task”
- “shared stateful executor needs IResettableExecutor between runs”
- “distinguish fresh/reset from restoring the same run”
- “validate session ownership, tenant, config fingerprint, provenance, and integrity before resume”
- “never trust client-supplied checkpoint contents or service conversation IDs”

### 与相邻 skill 的最终区分与负触发

- 若只是决定 Session、History Provider、主动 Context 与按需 Tool 各自承载什么，**不触发本 skill**；改用 `separate-session-history-context-and-tools`。
- 若只是判断标准 checkpoint 是否足够、何时升级 Durable Task，**不触发本 skill**；改用 `choose-workflow-recovery-layer`。
- 若只设计一笔人工请求的 Pending、恢复重发、超时、升级与迟到响应，**不触发本 skill**；改用 `model-recoverable-human-decisions`。
- 若只是选择 request-id、StateBag 或工具参数的运行时表面，**不触发本 skill**；改用 `place-agent-runtime-surfaces`。

---

## E — 可执行步骤（Execution）

1. **盘点全部可变状态与隐式 owner**
   - 枚举 Workflow run、Executor 字段、Agent Session/thread、History/Context Provider、子 Workflow、共享 state、pending message/request、外部缓存和 provider service ID。
   - 为每项记录：作用域、owner/user、tenant、创建者、读写者、当前存储、并发模型、是否敏感、是否需要跨 run。
   - **完成标准**：状态清单覆盖代码内字段与外部依赖；任何可变项都不再标作“全局/以后再看”，且能回答泄漏到下一 run 的路径。

2. **为每项状态选择且只选择 fresh、reset 或 restore 语义**
   - `fresh`：新任务/新 run 创建无历史对象；`reset`：复用昂贵对象前清除旧 run；`restore`：从可信持久状态继续同一 run/会话。
   - 明确禁止把 reset 用于 resume，也禁止把 restore 当作开始新用户任务的便利方式。
   - **完成标准**：生命周期矩阵中每项状态有唯一主动作、触发时机与不变量；fresh/reset 均承诺“不继承下一 run”，restore 承诺“只恢复同一 run”。

3. **默认实现 fresh factory 边界**
   - 把 Workflow builder、Executor、Agent 与 Session/thread 的实例化包进每任务 factory；子图也创建新的运行实例。
   - 只共享线程安全、无 tenant/run 状态的模型客户端、连接池、不可变配置与经过 tenant key 隔离的外部服务。
   - **完成标准**：两个串行 run 与两个不同 tenant 的并发 run 获得不同 Workflow/Executor/Agent/Session 身份；第二次 run 看不到第一次的消息、计数、缓存和 thread。

4. **对不得不共享的对象实现完整 Reset 契约**
   - 仅在构造成本有证据且 fresh 不可接受时共享；有状态 Executor 实现 `IResettableExecutor.ResetAsync()`，清理累积消息、计数器、缓存、临时句柄和订阅。
   - 审计外部 mutable dependency、Provider 实例字段和后台任务；reset 失败时隔离/销毁对象，不得带病进入下一 run。
   - **完成标准**：异常结束、取消、reset 抛错和并发复用测试均不会把旧状态带入新 run；无法证明外部状态已清理时回退 fresh。

5. **设计服务端权威的持久化 envelope**
   - 生成不可枚举的应用 handle；服务端记录 `state_id/run_id`、owner/user、tenant、Agent/Provider/workflow 配置指纹与版本、schema 版本、provenance、创建/更新时间、TTL、对象版本及完整性元数据。
   - provider conversation ID、checkpoint 存储键和序列化内容留在可信服务端；客户端只持 handle，不得指定权威路径或 payload。
   - **完成标准**：仅凭客户端 handle 无法推导别人的状态；任一状态都可追溯到创建配置、owner/tenant 和可信存储对象。

6. **保护 Session/Checkpoint 的机密性与完整性**
   - 使用私有、受访问控制、按 tenant 命名空间隔离的存储；传输/静态加密，并采用受控写权限、签名/MAC 或等价防篡改机制；备份和日志沿用同级保护。
   - 将消息角色、pending request、shared state 和 provider ID 都视为敏感控制数据，不接受客户端上传的完整 Session/checkpoint。
   - **完成标准**：未授权服务/用户不能读写；篡改角色、消息、owner、tenant、配置版本或状态体后完整性校验失败，恢复在执行任何 Executor 前终止。

7. **建立并验证严格的 restore gate 与回收策略**
   - 按顺序验证：已认证主体 → 应用 handle 映射 → owner/user → tenant → 状态完整性/provenance → schema 与 Agent/Provider/workflow 配置兼容性 → run/object 版本与终态 → TTL/合规保留。
   - 兼容升级必须走显式、可审计、可回滚迁移；未知旧版本、配置指纹不匹配和过期状态默认 fail closed。TTL 到期执行安全删除或合规归档，但 TTL 只做回收，所有权与完整性仍由 restore gate 判断。
   - 分别验证三类生命周期：Fresh 测试第二 run/另 tenant 无残留；Reset 测试正常/异常/取消后均清空；Restore 测试同一 run 连续，但篡改、错 owner、错 tenant、错配置、旧 schema、终态和过期状态全部拒绝。
   - **完成标准**：只有原 owner/tenant、匹配或已迁移配置、完整且未过期的同一 run 能恢复；任一 gate 失败均不调用模型或工具。跨租户并发、第二次 run、reset 失败、状态篡改、旧配置恢复、TTL 到期和客户端伪造 provider ID 的测试全部通过，并分别证明“不继承”和“同 run 连续”两个相反不变量。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 问题只是“客户偏好放 Session、History Provider、Context Provider 还是 Tool”：调用 `separate-session-history-context-and-tools`。
- 问题只是“进程内 checkpoint 还是跨 worker Durable Task”：调用 `choose-workflow-recovery-layer`；状态正确不代表运行层具备目标故障恢复能力。
- 问题只是一笔审批如何 Pending、重发、超时、升级和处理迟到响应：调用 `model-recoverable-human-decisions`。
- 对完全无状态、不可变、线程安全且不持有 tenant/run 数据的共享客户端，不要为了形式给它实现 reset。

### 真实反例与失败模式

- **复用有状态实例导致跨任务泄漏（ce24）**：单例 Workflow/Executor/Agent 把旧消息、计数器、缓存和 thread 带进下一请求；“Workflow 图不可变”不等于运行状态无状态。
- **从不可信 Session 恢复（ce18）**：攻击者篡改角色或会话标识，恢复后以合法控制状态进入模型管线，造成提权与数据泄漏。
- **把 provider conversation ID 当授权（ce21）**：共享 project/key 下，原始 ID 不携带应用 owner；只校验 ID 存在会形成 IDOR。
- **Provider 实例字段保存会话状态（ce22）**：共享 AIContextProvider 的 `currentUserId/currentMemoryId` 在并发 Session 间覆盖，造成串租户。
- **从可篡改 checkpoint 加载（ce27）**：攻击者修改待处理消息、请求、Executor 或 shared state，恢复直接改变下一步执行。
- **reset 与 restore 混淆**：resume 前调用 Reset 丢掉同一 run 的合法进度；新任务却 Restore 老 Session，又把旧用户状态带入下一 run。

### 作者的盲点 / 时代与版本局限

- 官方主要给出原则、教程和 happy path，没有交付完整的多租户 envelope、配置指纹、签名/MAC、schema migration 与密钥轮换实现；这些必须由应用基础设施补齐。
- `IResettableExecutor` 文档截面标有“Coming soon”上下文，具体 API、调用时机和语言支持可能变化；上线前需核对当前包版本并以运行测试验证。
- Agent、Provider 与 Workflow 的配置兼容性不只由版本号决定；工具 schema、system instructions、模型、middleware、序列化格式变化都可能使旧状态语义失效。
- TTL 能降低存储、隐私和成本风险，但过短会破坏合法恢复，过长会扩大数据暴露；应由业务与合规共同设定。
- 状态 owner、tenant、配置和完整性都正确，也不等于能跨进程/worker 恢复；运行故障域仍需 v13 单独选择。

---

## 相关 skills

- 与 [`choose-workflow-recovery-layer`](../choose-workflow-recovery-layer/SKILL.md) `composes-with`：恢复基础设施回答“能否跨目标故障继续”，状态治理回答“是否允许从这份状态恢复”，两者缺一不可。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f19、p16、p18、p19、p22、p26、p27；案例 c02、c15、c22、c25；反例 ce18、ce21、ce22、ce24、ce27；术语 g03、g05、g18、g19、g22、g23
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
