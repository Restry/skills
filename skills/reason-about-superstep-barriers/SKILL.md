---
name: reason-about-superstep-barriers
description: |
  当 typed Workflow 图已确定，用户要推理 BSP/superstep 的启动时间、慢分支屏障、状态可见性或 checkpoint 边界时调用；若给出节点时长，必须输出逐 superstep 的实际最早启动时间线，不只讲公式。只处理时间、可见性与 superstep 末 checkpoint；Edge/Fan-out/Fan-in 业务语义设计、跨 worker Durable 选型不调用。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflow Builder & Execution · Supersteps / Synchronization Barrier / Workflows · State / Checkpoints（原文 8243–8285、8592–8600、8733–8750 行）
tags: [workflow, superstep, bsp, synchronization-barrier, checkpoint, maf]
related_skills:
  - slug: design-or-migrate-typed-agent-workflows
    relation: depends-on
---

# 用 Superstep 屏障推理 Workflow 时间、状态与恢复边界

## R — 原文（Reading）

> Within a single superstep, all triggered executors run in parallel, but the workflow does not advance to the next superstep until every executor completes. If you need truly independent parallel paths that don't block each other, consolidate sequential steps into a single executor.
>
> 中文翻译：同一 superstep 内所有被触发的 Executor 并行运行，但只有全部完成后 Workflow 才推进到下一 superstep。若需要互不阻塞的真正独立路径，可把连续步骤合并进一个 Executor。
>
> — Microsoft Agent Framework，Workflow Builder & Execution · Synchronization Barrier，原文 8272–8285 行

---

## I — 方法论骨架（Interpretation）

Superstep 是 BSP/Pregel 风格的一轮：收集上一轮消息、按既定 Edge 路由、并发执行本轮目标、等待全体完成，再让新消息进入下一轮。
因此“步内并行”不等于“每条分支独立推进”；同一步最慢 Executor 是所有分支共同的时间屏障。
一条短分支若包含多个 Executor，它每走一段都要等待全局步结束；增加线程只能帮助步内执行，不能绕过步间屏障。
性能估算必须先给图标出 superstep，再按每一步最长时长累加，而不是只对单条路径求和。
若一串短操作无须分别观测、恢复或形成边界，可合并到一个 Executor，使它们在同一调用中推进；若确需独立进度，则应拆离共享屏障或选择另一执行结构。
共享状态的写入者可立即看到自己的更新；其他 Executor 要到下一 superstep 才能观察到该值，不能把同一步并发写读当作即时共享内存。
Checkpoint 只在整个 superstep 完成后形成，捕获 Executor 状态、下一轮消息、待处理请求/响应和共享状态；不存在框架承诺的“一半分支完成”一致 checkpoint。
BSP 让消息推进顺序可推理，但 Agent Executor 内的 LLM 输出语义仍然非确定，不能据此宣称同输入必得同结果。
Checkpoint 提供框架内恢复点，不与支付、邮件、发布等外部系统原子提交，因此绝不等于外部副作用 exactly-once。
本方法不重新决定 Direct、Switch、Fan-out、Fan-in 或 Join 的业务语义；那些属于静态 typed Edge 设计。

---

## A1 — 书中的应用（Past Application）

### 案例 1：并行三语言翻译与屏障汇聚（c17）

- **问题**：法语、西班牙语和英语三个 Agent 要独立处理同一输入并统一汇总，需要理解并发何时开始、何时允许进入聚合。
- **方法论的使用**：三个翻译 Agent 在同一执行阶段并发运行；Workflow 等待这一阶段的参与者完成后，再把结果交给聚合输出。
- **结论**：总延迟受该 superstep 最慢翻译 Agent 约束；先完成的翻译不会独自越过屏障进入下一轮。
- **结果**：最终结果同时包含三种语言输出。该案例展示并发与汇聚，但不证明 LLM 翻译文本语义确定，也不提供外部副作用 exactly-once 保证。

### 案例 2：Durable Fan-out/Fan-in 时间线（c23）

- **问题**：主 Agent 的回答需并发送给法语和西班牙语翻译 Agent，再组合为统一 JSON。
- **方法论的使用**：主回答产生后触发两个并行翻译，汇合点等待二者完成；DTS 仪表板展示主步骤、并行步骤和各自耗时。
- **结论**：下一聚合阶段的最早启动时间由并行翻译中的慢者决定，而不是任一先完成者。
- **结果**：实例返回 original/french/spanish；Durable 层记录进度，但这不改变 BSP 屏障语义，也不能推出外部 API exactly-once。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. Workflow 图和 Edge 已经确定，用户要估算每个 superstep 及端到端最早启动/完成时间。
2. fan-out 中长短分支时长悬殊，用户问为什么短链不能继续、为什么增加 worker/线程没有解除阻塞。
3. 用户要判断共享状态在同一步还是下一步对其他 Executor 可见，或排查同一步读到旧值。
4. 用户要定位 checkpoint 形成时点、superstep 中途崩溃后的重放窗口，以及外部副作用重复风险。

**中文语言信号**：
- “为什么短分支被同一步的慢 Executor 卡住”
- “把这张图标成 superstep，算最早启动时间”
- “状态写完后别的 Executor 什么时候能看到，checkpoint 在哪一刻”

### Exact English triggers

1. “Map this workflow into BSP supersteps and compute the earliest start time of each executor.”
2. “Why can’t the short branch advance while a straggler is still running in the same superstep?”
3. “When do other executors observe shared-state updates, and what is captured at the checkpoint boundary?”

### 与相邻 skill 的最终区分与负触发

- 若仍需选择 Direct/Switch/Fan-out/Fan-in、消息类型、目标或 Join 业务语义，**不触发本 skill**；先用 `design-or-migrate-typed-agent-workflows` 冻结静态图。
- 若问题是标准 checkpoint 能否跨进程、worker、重启或跨天等待，**不触发本 skill**；改用 `choose-workflow-recovery-layer`。
- 若问题是跨 run 实例复用、fresh/reset/restore、owner/tenant 或存储完整性，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。

---

## E — 可执行步骤（Execution）

1. **冻结静态图并收集时长**
   - 以已确认的 Executor、Edge、触发条件和 Join 为输入；为每个 Executor 记录预计时长、超时、是否写共享状态、是否有外部副作用。
   - **完成标准**：静态路由没有未决项；若仍在争论消息该送给谁或用何种 Edge，停止并转 v09。

2. **把消息传播标成 superstep**
   - `S0` 标记入口消息；每个 `Sn` 列出由上一轮消息触发的所有 Executor，以及它们本轮产生但只能供 `Sn+1` 使用的消息。
   - **完成标准**：每个 Executor 都有唯一的最早 superstep；没有把本轮新消息错误地在同一轮继续传播。

3. **计算屏障时间与实际最早启动时刻**
   - 对每步计算 `duration(Sn) = max(该步所有已触发 Executor 时长)`；下一步最早启动为此前各步 duration 之和，加上调度开销。题目给出时长时，必须代入数值逐节点计算，不能只复述公式。
   - **完成标准**：产出带实际数值的“superstep—参与者—最长时长—屏障释放—每个下游最早启动”表，并明确指出 straggler；无时长数据时才允许输出符号表达式并列出缺失测量值。
   - **判停条件**：增加线程/worker 后若 straggler 本身不变，不得声称屏障已解除。

4. **评估是否合并短链或拆离屏障**
   - 仅当连续短步骤不需要独立观测、独立重试、状态可见点或 checkpoint 边界时，才建议合并为单个 Executor；真正独立推进需求则拆到不共享屏障的结构。
   - **完成标准**：每个合并建议都有“失去哪些观测/恢复边界”的说明；Edge 业务语义保持不变，不用性能理由偷换路由。

5. **标注共享状态可见性**
   - 对每个写入注明：写入者本步可见；其他 Executor 最早在下一 superstep 可见。列出同一步读旧值的风险与修正后的消息/步依赖。
   - **完成标准**：每个跨 Executor 读都有明确的最早可见 superstep；不存在依赖同一步并发即时可见的正确性假设。

6. **标注 checkpoint 与崩溃窗口**
   - 只在全步完成后标 checkpoint；列出快照中的 Executor 状态、下一轮消息、pending request/response 和 shared state，并模拟屏障前崩溃。
   - **完成标准**：恢复预期写明从哪个完整 checkpoint 重放哪些工作；所有支付、邮件、发布等外部副作用另有幂等键、outbox 或补偿，且文档明确“checkpoint ≠ exactly-once”。

7. **验证确定性声明的边界**
   - 区分“BSP 消息推进顺序可推理”与“LLM 语义输出非确定”；为 Agent 输出做 schema/业务验证和重复样本测试。
   - **完成标准**：没有把执行顺序确定写成结果语义确定；性能测试包含时长悬殊 fan-out，恢复测试包含 checkpoint 前崩溃与副作用重放窗口。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 需要选择 Direct、Conditional/Switch、Fan-out、Fan-in，定义 typed message、目标或 Join 业务语义：调用 `design-or-migrate-typed-agent-workflows`。
- 需要把广播/transition 图迁成 typed dataflow：这是 v09 的迁移入口，不属于 BSP 时间分析。
- 需要判断标准 checkpoint 还是 Durable Task 才能跨进程、worker、重启或长等待：调用 v13。
- 只是一般线程池、async I/O 或数据库锁性能问题，且不受 Agent Framework superstep 调度：不调用本 skill。

### 作者在书中警告的失败模式

- **把步内并行当独立流水线（ce23）**：短分支即使先完成，也不能越过尚未完成的同一步慢分支；多级短链会反复等待屏障。
- **把 checkpoint 当 exactly-once（ce25）**：外部扣款或发信可能已成功，但 superstep 末 checkpoint 尚未落盘；恢复会重放，必须有业务幂等/outbox/补偿。
- **用加线程解除逻辑屏障**：线程增加可能缩短 Executor 本身耗时，但不会改变“全体完成才进下一步”的调度规则。
- **同一步读取他人最新状态**：其他 Executor 在下一 superstep 才看到本步更新；依赖即时可见会造成旧值与竞态假设。

### 作者的盲点 / 时代局限

- 文档给出执行语义与示例，但没有为所有拓扑提供真实调度开销、队列争用和供应商延迟模型；生产估算必须用实测分布而非单点平均值。
- 文档是 2026 年快速演进截面，执行模式和 SDK API 可能变化；必须用目标版本做时间线与故障注入验证。
- BSP 执行顺序确定不代表 LLM 语义确定；模型、工具和外部服务仍可能产生非确定结果。
- 标准 checkpoint 是框架内一致性边界，不是外部系统分布式事务，也不提供外部副作用 exactly-once。

### 容易混淆的邻近方法论

- Fan-out/Fan-in 是 Edge 的**静态路由与汇聚语义**，属于 v09；屏障是这些节点运行时的**时间推进规则**，属于本 skill。
- Checkpoint 时点分析属于本 skill；Checkpoint 与 Durable 的故障域选型属于 v13。
- 状态“何时可见”属于本 skill；状态“归谁、能否跨任务复用、存储是否可信”属于 v12。

---

## 相关 skills

- `depends-on` [`design-or-migrate-typed-agent-workflows`](../design-or-migrate-typed-agent-workflows/SKILL.md)：必须先冻结 Executor、Edge、触发与 Join 语义，才能可靠计算 superstep 时间、状态可见性和 checkpoint 边界。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f17、p24；案例 c10、c17、c23；反例 ce23、ce25
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
