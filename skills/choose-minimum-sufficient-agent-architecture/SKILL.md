---
name: choose-minimum-sufficient-agent-architecture
description: |
  当用户在函数、Agent、Agent Skill、Workflow 或人审之间选型，或询问“谁来决定下一步 / minimum sufficient architecture / agent vs workflow”时调用；按确定性、开放判断、重试粒度与副作用分配控制权。不用于设计 Middleware 运行面、Session/Context 分层、typed Edge 或 Harness 内部机制。
source_book: 《Microsoft Agent Framework》 Microsoft
source_chapter: Get started · When to use agents vs workflows（原文 33–37 行）；Agent Skills · When to use skills vs. workflows（2915–2933 行）
tags: [architecture-selection, agent, workflow, control-boundary, side-effects, maf]
related_skills: []
---

# 选择最低充分的 Agent 架构与控制权

## R — 原文 (Reading)

> “Use an agent when… Use a workflow when… The task is open-ended or conversational The process has well-defined steps You need autonomous tool use and planning You need explicit control over execution order A single LLM call (possibly with tools) suffices Multiple agents or functions must coordinate. If you can write a function to handle the task, do that instead of using an AI agent.”
>
> 自译：任务开放、对话性强，或需要自主使用工具与规划时用 Agent；流程步骤明确、执行顺序必须显式控制，或多个 Agent/函数需要协调时用 Workflow。若普通函数足以处理，就不要使用 AI Agent。
>
> — Microsoft, *Get started · When to use agents vs workflows*, 原文 33–37 行

---

## I — 方法论骨架 (Interpretation)

1. 先把问题拆成输入、判断、动作和外部副作用，不要先选框架组件。
2. 对每一步先问普通函数、规则或固定状态机是否足够；足够就停止升级。
3. 只有开放式理解、对话、规划或工具选择才交给 Agent。
4. 结果可机械验证的部分留给代码，涉及责任与授权的判断留给人。
5. 多步骤业务路径若要求固定顺序、分支、协调或恢复，应由 Workflow 显式控制。
6. 封装单 Agent 能力时，再按控制权、整体重试成本、副作用与协调复杂度选择 Skill 或 Workflow。
7. 最终架构可以混合函数、Agent、Skill、Workflow 与人审，不必把整个系统二分成“全 AI”或“全代码”。
8. 用故障重放检查控制边界：若顺序只能靠模型记住，或整体重试会重复副作用，就把该段升级为显式 Workflow，并另做业务幂等。

---

## A1 — 书中的应用 (Past Application)

### 案例 1：为 Agent 添加天气函数工具（c01）
- **问题**：教程需要让对话式 Agent 回答阿姆斯特丹天气，但天气查询本身是确定性应用逻辑。
- **方法论的使用**：开放式理解与工具选择留给 Agent；实际天气查询保留为带参数描述的 `GetWeather` 函数。
- **结论**：无需把查询实现改造成另一个 Agent；单 Agent 加普通函数已是充分架构。
- **结果**：官方教程记录，相关请求会让 Agent 自动选择并调用 `GetWeather`，而应用继续持有确定性的天气查询逻辑。（原文 149–186 行）

### 案例 2：垃圾邮件检测与专业回复的条件路由（c09）
- **问题**：邮件语义分类需要模型判断，但垃圾/正常邮件之后必须走不同且可审计的固定路径。
- **方法论的使用**：Agent 输出结构化 `DetectionResult`；条件 Edge 根据 `IsSpam` 确定路由，垃圾邮件进入标记处理器，正常邮件进入回复 Agent 与发送处理器。
- **结论**：智能判断可以局部嵌入 Workflow，路由控制不必交给模型自由决定。
- **结果**：官方示例中，垃圾邮件被标记并附理由；改为正常跟进邮件后，同一图走回复生成与发送路径。（原文 7014–7321 行）

### 案例 3：Researcher→Writer→Editor 声明式内容流水线（c14）
- **问题**：内容生产需要三个专业 Agent 协作，且业务要求固定的研究、写作、编辑顺序。
- **方法论的使用**：每个开放式子任务由专职 Agent 完成，执行次序则由声明式 Workflow 规定。
- **结论**：多 Agent 不等于让 Agent 自行协商控制流；固定业务路径应显式编排。
- **结果**：文档示例把研究结果按固定顺序传入草稿和编辑阶段，而不是让单一 Agent 自主决定全部步骤。（原文 9806–9859 行）

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?

1. 方案在普通函数、单 Agent、Agent Skill、Workflow、Harness 或人审之间摇摆，不知道该停在哪一层。
2. 现有设计把全部步骤都交给模型，团队担心顺序、重试、成本或副作用不可控。
3. 一个系统同时含自由文本判断、硬规则、外部写操作与责任审批，需要切分决策权。
4. 用户要评审“是不是过度 Agent 化”，或希望得到最低充分架构而非组件堆叠。

### 语言信号 (用户的话里出现这些就应激活)

- “这个需求到底该用函数、Agent 还是 Workflow？” / “agent vs workflow?”
- “帮我选 minimum sufficient architecture / 最低充分架构。”
- “Who should decide the next step: model, code, or human?” / “下一步该由模型、代码还是人决定？”
- “失败后能不能整体重试？会不会重复扣款/发信？” / “retry granularity and side effects”

### 明确不触发

- 已经选定 Agent，只是在问日志、重试、request-id 或参数校验应放哪层 Middleware。
- 只是在设计 `Edge`、fan-out/fan-in、Join、类型契约或 superstep 的具体 Workflow 图。
- 只是在设计 Session、History、RAG、Context Provider 与 Tool 的状态和上下文分层。

### 与相邻 skill 的最终区分与负触发

- 若问题已确定使用 Agent，只需定位日志、重试、request-id 或工具参数校验的执行面，**不触发本 skill**；改用 `place-agent-runtime-surfaces`。
- 若问题已确定使用 Workflow，只需定义 Executor I/O、typed Edge、Fan-out/Fan-in 或 Join，**不触发本 skill**；改用 `design-or-migrate-typed-agent-workflows`。
- 若问题已确定是长期开放任务，只需配置 Plan/Todo、预算、审批、能力面和完成门，**不触发本 skill**；改用 `assemble-open-ended-task-harness`。
- 若问题已证明需要多个 Agent，只需选择协作拓扑、任务所有权或 A2A 边界，**不触发本 skill**；改用 `choose-multi-agent-coordination-and-delegation`。

---

## E — 可执行步骤 (Execution)

当 skill 被激活后，agent 应按以下步骤执行：

1. **拆出决策与副作用清单**
   - 把任务列成“输入 → 判断 → 动作 → 外部副作用”，并标出每步是否可机械验证、是否可逆。
   - 完成标准：每个业务步骤都有输入、输出、决策性质和副作用四项记录，不再以整块“AI 流程”描述。

2. **从普通函数开始逐步升级**
   - 逐步检查纯函数、规则或固定状态机能否可靠完成；能完成的步骤立即固定为确定性实现。
   - 完成标准：每一步都有“函数/规则足够”或“为何必须开放判断”的书面理由。
   - 判停条件：若全部步骤均可确定实现，则输出普通程序/状态机方案并停止，不引入 Agent。

3. **分配模型、代码与人的控制权**
   - 将开放理解、规划和工具选择交给 Agent；将约束、计算、验证与路由交给代码；将责任、授权和高风险决策交给人。
   - 完成标准：形成逐步骤责任矩阵，且没有仅靠提示词保证的硬规则或审批。

4. **选择 Skill、Workflow 或组合**
   - 单 Agent 可自主解释、整体重试安全、操作幂等或低风险时选 Skill；固定顺序、多方协调、步骤级恢复或不可重复副作用时选 Workflow；需要领域说明又要固定控制流时用 Skill-in-Workflow。
   - 完成标准：选型表至少覆盖控制权、失败粒度、副作用、协调复杂度四列，并给出最终组件边界。

5. **用故障重放验证最低充分性**
   - 模拟模型误判、步骤中断、重复执行和人审拒绝；检查路径是否仍受控，外部动作是否具备幂等键、outbox 或补偿。
   - 完成标准：每个失败场景都有可观察结果与恢复策略；若顺序依赖模型记忆或副作用会重复，则已把相应段升级为 Workflow，并明确 checkpoint 不等于 exactly-once。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用此 skill

- 已确定使用 Workflow，只需设计消息类型、Edge、Join 或迁移等价性；应转向 typed Workflow 方法。
- 已确定使用 Agent，只需决定 Middleware 或 Runtime Context 的具体落点；应转向运行面定位方法。
- 需要解决跨 worker 的持久执行、长期等待或 Durable Task 选型；这不是抽象阶梯本身能回答的问题。

### 作者在书中警告的失败模式

- **ce01**：本可由普通函数确定执行的任务仍使用 Agent，会把可测试逻辑变成概率性路径，增加成本、延迟与安全面。
- **ce11**：把发信、扣款等不可幂等副作用放进单次 Skill，后半段失败后整体重试会重复已完成动作。
- **ce25**：Workflow checkpoint 只保存框架内状态；在 checkpoint 落盘前已提交的外部副作用，恢复后仍可能重放，不能宣称 exactly-once。

### 作者的盲点 / 时代局限

- 官方文档偏向展示 Azure/Foundry 体系内的可组合性，较少量化组件叠加后的上下文成本、调试复杂度和供应商费用。
- 教程以 happy path 为主；多租户隔离、幂等键、补偿、灾难恢复和成本保护仍需应用自行设计。
- “typed graph + superstep 更可理解”是设计主张，不是对所有业务都优于普通状态机、队列或事件系统的证明。

### 版本边界

- 本方法基于 2026-07-10 左右的文档截面；具体 SDK API、语言能力和预览状态必须现场核对。
- C#、Python、Go 能力并不对称；概念层选型不能被误写成所有语言已有相同组件。

### 容易混淆的邻近方法论

- 选择 Workflow 不等于已经设计好 typed Edge，也不自动获得外部副作用 exactly-once。
- 提到人类控制权不等于框架会自动插入审批；普通 Agent 工具默认可能直接执行。
- 本 skill 负责实现前的抽象与控制权切分，不负责 Harness 运行纪律、多 Agent 拓扑或 Middleware 落点。

---

## 相关 skills

本 skill 不声明出边；它是架构门禁基础节点。`assemble-open-ended-task-harness`、`design-or-migrate-typed-agent-workflows` 与 `choose-multi-agent-coordination-and-delegation` 均将其作为 `depends-on` 目标，先证明更高抽象确有必要。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定案例**：c01 / c09 / c14（均来自 verified v01 的允许集合）
- **绑定反例**：ce01 / ce11 / ce25
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
