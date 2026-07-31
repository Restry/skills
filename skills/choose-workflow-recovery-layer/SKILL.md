---
name: choose-workflow-recovery-layer
description: |
  当 MAF 任务需要从中断、superstep 故障、进程重启、worker 迁移或跨天等待中恢复，并要在 continuation token、Session 序列化、标准 Workflow checkpoint 与 Durable Task 之间选层时调用；信号包括“resume/recover/checkpoint/durable/断点续跑”。不用于单独设计 HITL 状态机、状态 owner/tenant 安全，或只分析既定图的 BSP 屏障。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflows · Checkpoints（原文 8733–8844 行）；Durable Extension（原文 11970–12369、12671–12852 行）；Agents · Background Responses（原文 1218–1350 行）
tags: [workflow, checkpoint, recovery, durable-task, superstep, continuation-token, maf]
related_skills:
  - slug: reason-about-superstep-barriers
    relation: depends-on
---

# 按故障域选择 Workflow Checkpoint 或 Durable Task

## R — 原文（Reading）

> Checkpoints are created at the end of each superstep, after all executors in that superstep have completed their execution. A checkpoint captures the entire state of the workflow, including: The current state of all executors; All pending messages in the workflow for the next superstep; Pending requests and responses; Shared states.
>
> 中文翻译：Checkpoint 在一个 superstep 的全部 Executor 完成后创建，捕获所有 Executor 状态、下一 superstep 的待处理消息、待处理请求与响应，以及共享状态。
>
> — Microsoft Agent Framework，Workflows · Checkpoints，原文 8741–8747 行

> To ensure that the state of an executor is captured in a checkpoint, the executor must override the OnCheckpointingAsync method and save its state to the workflow context. Also, to ensure the state is correctly restored when resuming from a checkpoint, the executor must override the OnCheckpointRestoredAsync method and load its state from the workflow context.
>
> 中文翻译：自定义 Executor 必须重写 `OnCheckpointingAsync`，把状态保存到 workflow context；恢复时必须重写 `OnCheckpointRestoredAsync`，从 context 装回状态。
>
> — Microsoft Agent Framework，Workflows · Rehydrating from Checkpoints，原文 8796–8801 行

> Durable Agent Framework workflows are different from checkpoint storage in standard workflows. Checkpoint storage helps resume a workflow run in the Agent Framework runtime. The Durable Extension runs the workflow on Durable Task infrastructure so workflow progress is checkpointed and recovered across distributed durable workers.
>
> 中文翻译：标准 checkpoint 用于在 Agent Framework runtime 内恢复一次 Workflow run；Durable Extension 则在 Durable Task 基础设施上运行 Workflow，使进度能跨分布式 durable workers 保存与恢复。
>
> — Microsoft Agent Framework，Durable Extension，原文 12153–12157 行

---

## I — 方法论骨架（Interpretation）

恢复层选型先看要承受的**故障域**，而不是先看任务“长不长”。
`continuation token` 只续接一次底层 Provider 支持的后台响应或中断流；它不包含 Workflow 图、Executor 状态和待处理消息。
`AgentSession` 序列化只保存同一 Agent/服务的会话连续性，如历史、StateBag 或服务侧 thread 标识；它不表示 Workflow 已执行到哪一个 superstep，也不承担调度恢复。
标准 Workflow checkpoint 是**同一次 run** 的一致性快照，只在完整 superstep 结束后形成；superstep 中途没有框架承诺的半步 checkpoint。
Checkpoint 捕获框架已知的 Executor 状态、下一轮消息、pending request/response 与 shared state，但不会猜测自定义 Executor 任意字段的序列化语义；必需私有状态必须显式 save/restore。
只需在 Agent Framework runtime 内暂停、调试或恢复同一 run 时，标准 checkpoint 是较小层级。
进程可能重启、任务会迁移到其他 worker、等待跨小时/跨天、需要持久定时器/外部事件或分布式 fan-out/fan-in 时，升级到 Durable Task；Durable 增加的是持久历史、调度与跨 worker 恢复，不只是“更大的 checkpoint”。
四种机制可组合但不可互代：一次 Durable Agent 也可能有 Session，一次 Provider 调用也可能返回 continuation token；组合不改变各自故障域。
无论选择 checkpoint 还是 Durable，框架状态与支付、邮件、发布等外部系统都没有天然原子提交；恢复可能重放外部成功但尚未被框架确认的动作，绝不能宣称 exactly-once。

---

## A1 — 书中的应用（Past Application）

### 案例 1：太空水獭长篇小说的断点续流（c03）

- **问题**：一次长篇生成可能超过客户端连接寿命，但业务只需继续取得同一次 Provider 响应。
- **方法论的使用**：非流式调用保存 continuation token 并轮询；流式调用保存最近一次 update 的 token，在网络中断后续接流。
- **结论**：这是响应/流层恢复，不是 Workflow checkpoint、Session 恢复或 Durable worker 调度。
- **结果**：调用方无需保持长连接；token 为空表示后台操作已完成、失败或无法继续。该能力还依赖底层 Agent/Provider 是否支持。

### 案例 2：24 小时内容审批与超时升级（c21）

- **问题**：审稿人可能隔天响应，运行期间会释放计算资源，并且 24 小时后必须可靠升级。
- **方法论的使用**：Durable orchestration 持久等待外部 `ApprovalDecision` 事件，并用持久 timeout 驱动批准、拒绝或升级分支。
- **结论**：跨天等待、重启与外部事件超出了普通响应 token、Session 序列化和 runtime 内 checkpoint 的责任范围，应使用 Durable Task 层。
- **结果**：等待期间不占用 worker；响应或超时到达时恢复编排继续执行。

### 案例 3：Durable Fan-out/Fan-in 翻译（c23）

- **问题**：主 Agent 结果要并发交给法语和西班牙语 Agent，聚合阶段需要在 worker 故障后保留已确认进度。
- **方法论的使用**：Durable Task 记录主步骤和两个并行翻译步骤，`Task.WhenAll` 汇合；DTS 仪表板显示每步时间线。
- **结论**：Durable 负责跨 worker 的执行历史与恢复；它不改变 Workflow 的 superstep/汇聚语义，也不让外部写操作天然 exactly-once。
- **结果**：实例返回 original/french/spanish，并可在耐久基础设施中观察各步骤进度。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 团队把 continuation token、Session 序列化、checkpoint 和 Durable 都叫“断点续跑”，需要澄清各自保存什么、能抗哪类故障。
2. Workflow 要在 superstep 末暂停/恢复，需列出快照内容并验证自定义 Executor 的私有状态能否正确还原。
3. 任务会经历进程重启、扩缩容、worker 迁移、跨天等待、持久 timeout/外部事件或分布式 fan-out/fan-in，需要判断标准 checkpoint 是否足够。
4. 支付、发信、发布等步骤可能在 checkpoint/Durable 记录前已成功，需要设计重放、幂等、outbox 或补偿。

**中文语言信号**：

- “这只是 continuation token，还是能恢复整个 Workflow？”
- “Session deserialize 后能从上个 superstep 继续吗？”
- “标准 checkpoint 能不能扛进程重启和 worker 迁移？”
- “自定义 Executor 恢复后字段丢了，save/restore hook 怎么验？”
- “Durable 能保证邮件或扣款 exactly-once 吗？”

### Exact English triggers

- “Choose between a continuation token, serialized AgentSession, workflow checkpoint, and Durable Task.”
- “Which fault domain does a standard checkpoint cover, and when must we use distributed durable workers?”
- “Where is the superstep checkpoint boundary, and how do custom executors save and restore private state?”
- “Test the crash window after an external side effect succeeds but before workflow progress is recorded.”

### 与相邻 skill 的最终区分与负触发

- 若只计算已定图的 superstep、straggler、状态可见性或 checkpoint 形成时点，**不触发本 skill**；改用 `reason-about-superstep-barriers`。
- 若只设计审批 request/response、Pending、超时升级、恢复重发与迟到响应，**不触发本 skill**；改用 `model-recoverable-human-decisions`。
- 若只治理状态的 fresh/reset/restore、owner、tenant、配置指纹、完整性与 TTL，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。
- 若只是网络中断后续接一次 Provider 响应，或仅恢复多轮会话历史，**不触发本 skill**；分别使用 continuation token 或 AgentSession，不要误上 Workflow/Durable。

---

## E — 可执行步骤（Execution）

1. **枚举故障与恢复目标**
   - 列出客户端断线、Provider 响应中断、runtime 内暂停、superstep 中途崩溃、进程重启、worker 迁移、跨天等待、持久 timeout、外部事件、并行聚合失败和区域级故障；为每项写明允许丢失/重放的最大范围与恢复时间目标。
   - **完成标准**：形成“故障 → 必须保留的状态 → 可接受重放 → 目标恢复点”矩阵；不能只写“任务很长所以要 Durable”。

2. **把四种连续性机制分账**
   - 建四栏清单：continuation token 保存 Provider 响应/流位置；Session 序列化保存会话上下文；checkpoint 保存同一 Workflow run 的 superstep 边界状态；Durable Task 保存持久执行历史并提供跨进程/worker 调度恢复。
   - **完成标准**：每个现有状态字段和恢复 API 只归入其真实责任栏；设计文档不再用“resume token/session/checkpoint/durable”互作同义词，也未把 A2A/AG-UI 等通信协议写成执行持久化。

3. **标出 superstep 一致点与重放窗口**
   - 在 Workflow 图上只于完整 superstep 末标 checkpoint；列出该点的 Executor state、下一轮 pending messages、pending requests/responses 与 shared state。模拟本步最早、外部副作用之后、屏障完成之前及 checkpoint 写入之后的崩溃。
   - **完成标准**：每个故障点都能回答“从哪个完整 checkpoint 恢复、哪些 Executor/消息会重放”；不存在“半个 superstep 已自动形成一致快照”的假设。

4. **为自定义 Executor 实现双向状态契约**
   - 盘点所有影响后续结果的 mutable/private fields、游标、累计值和业务进度；在目标 SDK 中实现对应 checkpoint save/restore hook。文档截面的 C# API 为 `OnCheckpointingAsync` 与 `OnCheckpointRestoredAsync`，其他语言/版本必须查当前官方 API，不能凭名称硬套。
   - **完成标准**：快照中可观察到每个必需字段；在非默认状态处恢复后，后续输出、路由和计数与无故障基线一致；缺字段、旧 schema 和 restore 失败均 fail closed，而不是静默回到初始值。

5. **按最小充分故障域选择运行层**
   - 仅续接一次支持后台响应的 Provider 调用：continuation token；仅恢复同一 Agent 会话上下文：Session 序列化；仅在 Agent Framework runtime 内暂停/恢复同一 Workflow run：标准 checkpoint；跨进程重启、无状态/分布式 worker、跨天等待、持久 timer/external event 或分布式进度恢复：Durable Task。
   - **完成标准**：为每项需求给出“最小机制 + 明确不保证什么”；若标准 checkpoint 无法覆盖任一必需故障，则升级 Durable；若只有连接中断或会话连续性，不误上完整 Durable。

6. **封住外部副作用原子性缺口**
   - 对支付、发信、发布、工单和第三方写入定义业务幂等键；按场景使用 inbox/outbox、条件写、去重账本、可查询结果或补偿。明确 checkpoint/Durable 与外部系统不存在自动的两阶段提交。
   - **完成标准**：故障注入覆盖“外部调用成功，但本 superstep checkpoint 或 Durable progress 尚未记录”；恢复重放不会产生第二个业务效果，或能检测并可靠补偿。任何文档中的 `exactly-once` 声明均被删除或限定为应用已证明的业务效果。

7. **执行分层恢复演练并留下证据**
   - 分别测试流中断续接、Session 序列化/反序列化、superstep 前后 checkpoint 恢复、自定义 Executor 非默认状态恢复、进程重启、换 worker、长等待/timeout、fan-out 部分完成和副作用崩溃窗。
   - **完成标准**：测试报告逐项记录故障注入点、实际恢复层、恢复起点、重放集合、最终状态与副作用计数；只有与步骤 1 的故障矩阵全部匹配时才验收，不能用“流程最终跑完”替代状态与重放核对。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 只是要计算已定 Workflow 中长短分支的 superstep、最早启动时间、共享状态可见性或 straggler：调用 `reason-about-superstep-barriers`。
- 只是要设计审批请求的强类型契约、Pending、超时升级、恢复重发和迟到响应：调用 `model-recoverable-human-decisions`。
- 只是 Session/checkpoint 的 owner、tenant、配置指纹、完整性、fresh/reset/restore 或 TTL 有问题：调用 `govern-agent-state-lifecycles`。
- 只是网络流中断后继续取同一次 Provider 响应，且不需要恢复 Workflow 图与 worker 调度：使用 continuation token 即可，不要误上 checkpoint/Durable。
- 只是多轮对话要保留历史，没有执行中的 Workflow 进度：使用并治理 AgentSession；Session 序列化不是本 skill 要解决的执行恢复。

### 真实反例与失败模式

- **把 checkpoint 当 exactly-once（ce25）**：外部扣款/发信已成功，但 superstep 尚未结束或 checkpoint 尚未落盘；恢复会重放。必须有业务幂等键、outbox 或补偿。
- **漏掉自定义 Executor 私有状态（ce26）**：图能 resume 不代表业务状态完整；未实现 save/restore hook 的字段会回到初始值，导致错误结果或重复工作。
- **加载可篡改 checkpoint（ce27）**：快照含控制流、消息、请求与共享状态，从不可信存储恢复会直接改变后续执行；存储 owner/tenant/完整性治理应组合 v12。
- **把 continuation token 当 Durable**：它只续接一次受支持的后台响应/流，不捕获整个 Workflow，也不负责跨 worker 调度。
- **把 Session 反序列化当 Workflow resume**：会话可恢复历史，却没有 Executor 位置、下一轮消息、pending request 和 superstep 一致性信息。

### 作者的盲点 / 时代与版本局限

- 文档是 2026 年快速演进截面，C#、Python、Go 的 checkpoint 与 Durable 能力并不对称；实施前必须核对目标 SDK、包版本和当前官方托管支持。
- 官方示例多为 happy path，没有提供任意外部系统的 exactly-once、跨区域灾备、schema 演进和完整业务补偿实现。
- Durable Task 降低跨 worker 恢复成本，但会引入调度服务、历史增长、序列化兼容、运维和供应商基础设施约束；不是所有长任务都应升级。
- 标准 checkpoint 与 Durable 都不能证明 LLM 语义确定；恢复后的模型输出仍需 schema、业务不变量和可接受非确定性测试。

### 容易混淆的邻近方法论

- checkpoint 的**形成时点和重放窗口**依赖 superstep 语义；checkpoint 与 Durable 的**故障域选型**才属于本 skill。
- HITL 的 request/response 状态机与承载它的恢复层是两个决策；跨天审批通常组合 v11 与本 skill，但不能相互替代。
- 状态安全治理回答“是否允许从这份状态恢复”；本 skill 回答“所选基础设施是否能跨目标故障继续执行”。
- Durable Agent 中保留 thread/session 只证明会话上下文连续；Durable Workflow history 才负责执行和调度恢复，两者应分别验收。

---

## 相关 skills

- `depends-on` [`reason-about-superstep-barriers`](../reason-about-superstep-barriers/SKILL.md)：标准 checkpoint 的故障域选型必须建立在 superstep 末一致性边界与重放窗口已被正确理解的基础上。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f20、f21、p28；案例 c03、c21、c22、c23；反例 ce25、ce26、ce27；术语 g08、g16、g18、g22
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
