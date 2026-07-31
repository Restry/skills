---
name: control-agent-history-compaction-loss
description: |
  当自管历史 Agent 因 token、成本或延迟需要压缩对话时调用：如“设计 compaction trigger/target”“summarize without breaking tool history”。必须量化 Trigger 与 Target；收益不足或权威事实无法外置时不压缩。用 Trigger—Target—Strategy 和 MessageGroup 原子性控制损失；service-managed context、整个 Harness 组装或关键业务状态存储不调用。API 当前为 experimental。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Conversations & Memory · Compaction（原文 4529–4787 行）
tags: [compaction, context-window, trigger-target, message-group, information-loss, maf]
related_skills: []
---

# 用 Trigger—Target—Strategy 控制 Agent 历史压缩损失

## R — 原文（Reading）

> Every strategy has two predicates: Trigger — Controls when compaction begins. If the trigger returns false, the strategy is skipped entirely. Target — Controls when compaction stops. Strategies incrementally exclude groups and reevaluate the target after each step, stopping as soon as the target returns true. Each strategy preserves system messages and respects a MinimumPreserved floor that protects the most-recent non-system groups from removal. Strategies execute in order, so put the gentlest strategies first.
>
> 中文翻译：每个策略都有两个谓词：Trigger 控制何时开始；若为假则完全跳过。Target 控制何时停止；策略逐步排除消息组，每一步后重评 Target，一旦满足就停止。每个策略都保留系统消息，并遵守保护最近非系统组的 MinimumPreserved 下限。策略按顺序执行，因此应把最温和的策略放在前面。
>
> — Microsoft Agent Framework，Compaction，原文 4590–4593、4596–4597、4669 行

---

## I — 方法论骨架（Interpretation）

压缩不是单一“把旧消息总结掉”的动作，而是对何时开始、压到哪里、以何种损失路径进行的三段控制。
先确认 Agent 自己维护并在每次模型调用时发送完整历史；服务端托管上下文时，本地 compaction strategy 不生效。
Target 应先于 Trigger 设计：它必须低于硬上下文上限，并为输出、工具 schema、安全指令和运行时附加内容预留空间。
Trigger 决定何时值得付出压缩成本，优先依据 token 与可折叠消息组，而不是只看轮数。
Strategy 按信息损失从低到高排列：旧工具结果折叠、旧跨度摘要、滑动窗口、硬截断。
每一步执行后重新计算 Target；一旦满足就停止，不继续进行更激进的损失。
裁剪的最小单位是 MessageGroup，尤其 tool call 与对应 result 必须共同保留或共同删除。
系统消息和最近消息要受保护；未关闭事务、关键事实和业务约束应另存结构化状态或文件。
摘要由模型生成，可能遗漏或改写事实，因此压缩后必须做事实与协议完整性回归。

---

## A1 — 书中的应用（Past Application）

### 案例：从温和到激进的四层 Agent 历史压缩管线（c26，强制正向案例）

- **问题**：自管历史的长对话不断累积完整工具调用和结果，导致 token 上限、成本与延迟压力；又不能拆坏工具协议历史。
- **方法论的使用**：官方把 `ToolResultCompactionStrategy`、`SummarizationCompactionStrategy`、`SlidingWindowCompactionStrategy`、`TruncationCompactionStrategy` 依次串联。每个子策略独立检查 Trigger，并在每次排除 MessageGroup 后重评 Target；tool call 与对应 tool result 被当作原子组。
- **结论**：先回收冗长旧工具结果，再摘要旧对话；仍超预算才丢弃旧轮次，最后用硬截断做紧急 backstop。损失必须逐级升级，而不是一次跳到截断。
- **结果**：管线既能逐步降低上下文体积，又保护系统消息、最近消息和工具协议完整性；文档同时明确 Compaction 当前为 experimental，且摘要质量不是事实完整性的保证。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 自管历史 Agent 每轮发送完整对话，已接近上下文上限、成本或延迟阈值，需要设计压缩策略。
2. 用户要把压缩的开始条件和停止条件分开，或询问 Trigger、Target、MinimumPreserved 如何设定。
3. 用户要在工具结果折叠、摘要、滑窗和硬截断之间排序，并避免拆开 tool call/result。

**中文语言信号**：
- “给 Agent 历史设计 Trigger—Target—Strategy 压缩管线”
- “历史超 token 了，但别丢关键决策和未完成工具调用”
- “先折叠工具结果，再摘要、滑窗，最后才截断”

### Exact English triggers

1. A self-managed-history agent sends the full message list on every LLM call and is approaching token, cost, or latency limits.
2. The user asks to separate the compaction **trigger** from its stopping **target**, including reserved headroom or `MinimumPreserved`.
3. The user needs a gentle-to-aggressive strategy pipeline while preserving tool-call/result atomicity.

**English language signals**:
- “design a Trigger–Target–Strategy compaction pipeline for agent history”
- “summarize old history without breaking tool-call/result pairs”
- “collapse tool results first, then summarize, window, and truncate only as a backstop”

### 与相邻 skill 的最终区分与负触发

- 若问题是组装整个长期任务运行壳，包括 Plan/Todo、权限、审批、预算与完成门，**不触发本 skill**；改用 `assemble-open-ended-task-harness`。
- 若问题是 Session、History Provider、主动 Context 与按需 Tool 的责任归属，**不触发本 skill**；改用 `separate-session-history-context-and-tools`。
- 若需要保存法律、财务、权限、交易或未完成事项的权威状态，**不触发本 skill**；先用 `govern-agent-state-lifecycles` 设计可信持久状态，不能把有损摘要当账本。

---

## E — 可执行步骤（Execution）

1. **确认适用面与历史 owner**
   - 检查 Agent 是否自行维护内存消息列表，并在每次 LLM 调用时发送完整历史。
   - **完成标准**：确认是 self-managed history；若为 Foundry、Responses API store 或 Copilot Studio 等 service-managed context，停止本地策略设计并转服务端能力。

2. **测量预算并先定义 Target**
   - 统计当前 token、消息组和工具结果体积；从模型硬上限中扣除预期输出、工具 schema、安全指令与运行时余量。
   - **完成标准**：得到可计算的 Target（如 `included_tokens <= N`）和余量明细，且 Target 明显低于硬上限。

3. **定义可量化的 Trigger 与不压缩门**
   - 以 token 超阈值为主，可与 `HasToolCalls`、group 数、每轮成本或延迟条件组合；不要只按轮数触发。先估算预计节省与额外摘要成本，收益不足、关键事实无法外置或回归无法通过时，让 Trigger 保持 false。
   - **完成标准**：Trigger 由可测指标和数值阈值判定，写明预计节省、摘要成本与最低净收益；同时存在明确的“不压缩”判停条件。

4. **按损失强度组装策略**
   - 顺序固定为：旧工具结果折叠 → 旧跨度摘要 → 滑动窗口 → 最旧组硬截断；为每层设置独立 Trigger、Target 或保护下限。
   - **完成标准**：每个策略标注损失级别、触发条件、保护范围和失败后下一层；截断仅作为 emergency backstop。

5. **强制 MessageGroup 原子性并逐步判停**
   - 任何裁剪都按 MessageGroup 操作；tool call 与对应 result 成组保留或删除；保护系统消息、最近组和未关闭操作。每一步后重算 Target。
   - **完成标准**：不存在孤立 tool call/result；一旦 Target 满足立即停止，不执行后续更激进策略。

6. **外置关键事实并做回归验证**
   - 将关键业务状态、决策、未完成事项和权限另存结构化状态/文件；对压缩前后做事实抽样、未关闭事项、工具协议与预算回归。
   - **完成标准**：关键事实有权威外部来源，压缩后协议有效、Target 达标、关键事实/未关闭事项检查通过；否则调低损失或停止上线。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 历史由推理服务或 Agent 服务托管：本地 strategy 无效，应使用对应服务的上下文管理能力。
- 问题是整个长任务的 Plan/Todo、权限、审批、后台 Agent 与完成门：调用 `assemble-open-ended-task-harness`。
- 需要保存法律、财务、权限、交易或未完成业务状态的权威记录：使用结构化数据库/事件日志，不得依赖有损摘要。
- 对话尚未形成 token、成本或延迟压力：避免为“可能会长”而过早引入摘要成本和信息损失。

### 反例与失败模式

- **只按轮数截断**：不同轮次 token 差异巨大，可能过早丢失重要长轮，也可能太晚才触发。
- **一步跳到硬截断**：跳过工具结果折叠和摘要，会造成不必要的信息损失。
- **拆散工具组**：单独删除 assistant tool call 或 tool result 会破坏 LLM API 协议历史并引发错误。
- **把摘要当事实库**：摘要模型可能遗漏、合并或改写数字、承诺和未关闭事项；关键状态必须外置并回归。
- **误信框架自动限额（ce19）**：框架不会替业务自动设置输入、输出、速率和费用限制；Target 之外仍需 API/应用资源护栏。
- **注册层级混淆**：通过 `ChatClientBuilder` 注册可只压缩 in-flight tool-loop 上下文；通过 Agent options 注册时，合成摘要可能进入持久历史。必须先决定是否改写存储账本。

### 局限与预览/版本边界

- **明确实验性**：固定副本原文 4547–4549 行说明 Compaction framework 当前为 experimental，需禁用 `MAAI001` 警告才能使用；API、行为和注册语义可能变化。
- c26 是官方设计示例，不是对所有模型、语言和业务历史的保真率证明；摘要模型、提示与领域会显著影响遗漏率。
- `MinimumPreserved`、默认阈值与可用策略是版本相关实现细节；上线前必须核对当前官方文档、包版本并用真实历史回放。
- 工具结果折叠保留的是可读痕迹而非完整结果；审计或合规需要原始工具输出的独立不可变存储。
- 本方法控制的是上下文损失，不保证外部副作用 exactly-once，也不提供跨进程 Durable execution。

---

## 相关 skills

本 skill 不声明出边；它作为 [`assemble-open-ended-task-harness`](../assemble-open-ended-task-harness/SKILL.md) 的 `composes-with` 目标，为 Harness 或普通自管历史 Agent 提供独立的有损压缩策略。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f09、p20；正向案例 c26；反例 ce19
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
