---
name: assemble-open-ended-task-harness
description: |
  当任务“目标明确但路径开放”、需长时间多步推进时调用：如“让 agent 自主完成整夜研究/重构”“assemble a harness for a long-running open-ended task”。用于组装 Plan/Todo、预算、历史持久化、审批、最小工具面与真实完成门；固定业务顺序、不可重复副作用或跨进程/worker 可靠恢复应改用 Workflow/Durable，不调用本 skill。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Agent Harness（原文 2944–3114 行）
tags: [agent-harness, long-running-task, planning, approval, observability, maf]
related_skills:
  - slug: choose-minimum-sufficient-agent-architecture
    relation: depends-on
  - slug: control-agent-history-compaction-loss
    relation: composes-with
  - slug: design-or-migrate-typed-agent-workflows
    relation: contrasts-with
---

# 为长期开放任务组装可控 Harness

## R — 原文（Reading）

> A harness drives the agent: it runs the loop that calls the model and executes the tools the model asks for, manages conversation history and context so the model stays within its limits, applies approval and safety policies before actions are taken, and keeps the agent progressing toward task completion. Coding assistants and autonomous agents are all built on some form of harness — it's the engine wrapped around the model.
>
> 中文翻译：Harness 驱动 Agent：它运行模型调用与工具执行循环，管理历史和上下文以守住模型限制，在动作发生前应用审批与安全策略，并持续推动任务达到完成状态。编码助手和自治 Agent 都建立在某种 Harness 之上；它是包裹模型的运行引擎。
>
> — Microsoft Agent Framework，Agent Harness，原文 2948–2952 行

---

## I — 方法论骨架（Interpretation）

Harness 不是新模型，也不是固定业务流程图，而是包裹开放式 Agent 的运行纪律组合。
它适合“目标清楚、路径需边做边决定”的长任务；先确认该前提，再决定是否采用。
组装时先写完成判据、预算和 Plan/Todo，再选择历史、文件、Shell、Web、审批、遥测与后台 Agent。
默认能力只是起点，不是安全基线；每项能力都要按任务必要性和威胁模型保留或关闭。
Session/History 的逐调用持久化用于跨轮连续、检查与有限崩溃恢复，但不等于跨进程或跨 worker 的 Durable execution。
跨轮硬约束应写入结构化状态或文件，不能只依赖不断增长、可能被压缩的对话。
Shell 工作目录约束和 deny-list 只减少误操作；deny-list 是 UX 预过滤，不是沙箱。
每轮都要以真实测试、产物、预算和剩余 Todo 判断进度，不能接受模型自报“完成”。
固定发布顺序、不可重复副作用和可靠跨 worker 恢复分别交给显式 Workflow、业务幂等与 Durable 层。

---

## A1 — 书中的应用（Past Application）

### 案例：Harness 规划西雅图周末旅行（c07）

- **问题**：`Plan a weekend trip to Seattle.` 的目标清楚，但需要搜索、比较、规划和多步推进，路径不能预先写死。
- **方法论的使用**：官方从任意 `IChatClient` 构造 `HarnessAgent`，让运行壳提供工具循环、Todo、Plan/Execute、历史持久化、压缩、文件能力和默认 Web Search 等脚手架。
- **结论**：此类开放式、多步骤任务可由 Harness 自主推进，无须先画固定 Workflow 图。
- **结果**：应用只需提交旅行目标即可启动运行；案例证明 Harness 的适用性和默认组合，但没有证明跨进程恢复、后台委派、审批策略及完成门都已达到生产级验证。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 用户要求 Agent 在较长时间内自主完成研究、编码、分析或资料整理，且**目标明确、路径开放**。
2. 用户问如何为长任务组合 Plan/Todo、上下文持久化、文件记忆、审批、遥测、Shell 或后台 Agent。
3. 用户担心长任务失控、越权、超预算或“自称完成”，需要设计能力最小化与可验证 completion loop。

**中文语言信号**：
- “给这个长期开放任务组装 Harness”
- “让 agent 跑一夜，但要有计划、预算、审批和真实完成门”
- “怎么限制这个 autonomous agent 的文件、Shell、Web 和后台代理能力”

### Exact English triggers

1. The user has a **clear goal but an open execution path** for long-running research, coding, analysis, or automation.
2. The user asks to assemble planning, todos, history persistence, file memory, approvals, telemetry, shell access, or background agents into one runtime harness.
3. The user needs budget limits and evidence-based completion checks so an autonomous agent cannot merely claim success.

**English language signals**:
- “assemble a harness for this long-running open-ended task”
- “let the agent work overnight with a plan, budget, approvals, and real completion gates”
- “control file, shell, web, and background-agent capabilities for an autonomous agent”

### 与相邻 skill 的最终区分与负触发

- 若尚未确定任务应该使用函数、Agent、Skill、Workflow 还是 Harness，**不触发本 skill**；先用 `choose-minimum-sufficient-agent-architecture`。
- 若只需设计 Trigger、Target、损失顺序与 MessageGroup 原子性，**不触发本 skill**；改用 `control-agent-history-compaction-loss`。
- 若业务路径、分支与责任边界必须由代码显式控制，**不触发本 skill**；改用 `design-or-migrate-typed-agent-workflows`。Harness 与 typed Workflow 在“开放自主路径”与“显式固定数据流”上构成情境对比。
- 若核心要求是跨进程、跨 worker、跨天等待或可靠恢复，**不触发本 skill**；改用 `choose-workflow-recovery-layer`。

---

## E — 可执行步骤（Execution）

1. **确认 Harness 适用性**
   - 把目标、开放判断、确定步骤、外部副作用和等待点列成表。
   - **完成标准**：能明确写出“目标清楚但路径开放”；若路径固定或普通函数足够，停止并转函数/Workflow，不继续组装 Harness。

2. **建立计划、预算与完成契约**
   - 创建 Plan/Todo；设置最大 token、时间、费用、并发、循环次数与输出预算；为每个 Todo 绑定产物或测试。
   - **完成标准**：每个 Todo 都有可检查证据，且所有预算都有数值上限和超限停止动作。

3. **按最小权限裁剪能力面**
   - 逐项审查 Web、文件读写、Shell、Skills provider、自动审批、遥测与后台 Agent；不需要即关闭。
   - **完成标准**：形成“能力—必要性—权限—审批—数据去向”清单，无未解释的默认开启项。

4. **配置边界、审批与隔离**
   - 限定工作目录与运行身份；对安装、删除、发送、发布等高风险动作逐次审批；需要强隔离时使用沙箱/容器/最小权限账户。
   - **完成标准**：Shell deny-list 被标注为“仅 UX 预过滤、非安全边界”，并有独立强隔离和副作用控制；不得把 deny-list 描述为沙箱。

5. **配置连续性与委派纪律**
   - 每次模型调用后持久化到配置的 Session/History；把跨轮硬约束、决策和产物索引写入结构化状态或文件；后台 Agent 只接收相互独立、边界清楚的子任务。
   - **完成标准**：中断后可从所选存储恢复必要上下文，关键约束不只存在于可压缩聊天中，后台任务有输入、输出和汇合规则；文档明确“不承诺跨进程/worker Durable”。

6. **运行证据化 completion loop 并升级不适合部分**
   - 每轮检查真实构建、测试、静态检查、产物、预算和剩余 Todo；固定发布段或不可重复副作用移交 Workflow，并补幂等键/补偿；跨 worker 恢复转 Durable。
   - **完成标准**：只有所有门禁通过且 Todo 清零才结束；否则继续、降级或停止，不接受纯文本完成声明。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 普通函数或规则可可靠完成的短任务：Harness 只会增加不确定性与运维成本。
- 路径、分支和责任边界必须由代码固定的业务流程：使用显式 Workflow。
- 需要跨进程/worker、跨重启或长等待可靠恢复：使用 Durable 基础设施；Harness 的逐调用持久化不能宣称为 Durable execution。
- 主要问题仅是历史如何有损压缩：调用 `control-agent-history-compaction-loss`。

### 反例与失败模式

- **默认能力全开（ce12）**：Web Search、文件访问、启发式自动审批和遥测可能超出任务需要；“batteries-included”不等于最小权限。
- **把 deny-list 当沙箱（ce13）**：等价命令、解释器、脚本、路径技巧及宿主权限仍可产生副作用；deny-list 只能做 UX 预过滤。
- **未设置资源上限（ce19）**：框架不会替业务自动限制输入、输出、速率和费用；必须显式设定。
- **默认值随版本漂移（ce30）**：遥测等能力可能在升级后从显式开启变成默认开启，应固定版本并回归能力清单与数据流。
- **模型自报完成**：没有真实构建、测试、产物和 Todo 核验时，completion marker 或 AI judge 都不能单独作为交付证据。

### 局限与预览/版本边界

- c07 是适用性教程，不是崩溃恢复、后台 Agent、审批和停止门的生产验证。
- 文档是 2026 年快速演进快照；Harness 章节未像 Compaction 一样明确标注 experimental，但包、默认值和语言能力仍可能变化。实施前必须核对当前官方文档、包版本与功能矩阵，不能把本文 API 名称当永久契约。
- C#、Python、Go 能力不对称；不得把某语言的 Harness 功能无验证地外推到另一语言。
- 文件/历史持久化只保存状态；外部支付、邮件、发布等副作用仍需要业务幂等键、补偿和审计。

---

## 相关 skills

- `depends-on` [`choose-minimum-sufficient-agent-architecture`](../choose-minimum-sufficient-agent-architecture/SKILL.md)：必须先证明目标明确但路径开放，且普通函数或显式 Workflow 不足。
- 与 [`control-agent-history-compaction-loss`](../control-agent-history-compaction-loss/SKILL.md) `composes-with`：Harness 负责接入压缩能力，后者负责 Trigger—Target—Strategy 与 MessageGroup 原子性。
- 与 [`design-or-migrate-typed-agent-workflows`](../design-or-migrate-typed-agent-workflows/SKILL.md) `contrasts-with`：开放自主路径选 Harness；路径、路由与责任需代码显式控制时选 typed Workflow，复杂系统也可分段采用两者。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f08；案例 c07；反例 ce12、ce13、ce19、ce30
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
