---
name: design-or-migrate-typed-agent-workflows
description: |
  当用户要新建 typed Agent Workflow，或把广播/transition/target activation 的旧图迁移为强类型 dataflow 时调用；信号包括“设计 Edge/Fan-out/Fan-in”“migrate GraphFlow”“build-time type validation”。输出 Executor I/O、路由基数、最小消息契约、Join/暂停结构与等价回归。若只问 superstep 时间、状态可见性或 checkpoint 边界，不调用本 skill。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflows · Edges / Workflow Builder · Validation / AutoGen Migration · GraphFlow vs Workflow（原文 6982–7008、8206–8242、18403–18578 行）
tags: [workflow, typed-dataflow, edge-routing, migration, build-validation, maf]
related_skills:
  - slug: choose-minimum-sufficient-agent-architecture
    relation: depends-on
---

# 设计或迁移强类型 Agent Workflow

## R — 原文（Reading）

> GraphFlow: Control-flow based where edges are transitions and messages are broadcast to all agents; transitions are conditioned on broadcasted message content. Workflow: Data-flow based where messages are routed through specific edges and executors are activated by edges, with support for concurrent execution.
>
> 中文翻译：GraphFlow 以控制流为中心，Edge 表示 transition，消息广播给所有 Agent，再按广播内容决定转移；Workflow 以数据流为中心，消息经特定 Edge 路由，Executor 由 Edge 激活，并支持并发执行。
>
> — Microsoft Agent Framework，AutoGen Migration · GraphFlow vs Workflow，原文 18403–18412 行

---

## I — 方法论骨架（Interpretation）

强类型 Workflow 的起点不是“画几个 Agent 节点”，而是逐个声明处理单元真正消费和产生的数据。
Executor 可以是 Agent、确定性函数或子 Workflow；只有开放判断才需要 Agent，不能把所有节点都模型化。
Edge 是消息路由契约：先判定 1→1、one-of-N、1→many 或 many→1，再选择 Direct、Conditional/Switch、Fan-out 或 Fan-in/aggregator。
每条 Edge 只传目标所需的最小 typed message；Agent 的自然语言或结构化输出在进入路由前仍须校验。
新建入口从业务数据依赖推导图；迁移入口先盘点旧系统的广播订阅、transition、target activation、Join、暂停和隐含共享上下文。
迁移不是类名替换：广播自筛选要改成显式 target，控制转移要改成 typed dataflow，目标端激活要改成 edge-based activation。
ANY/ALL Join 的完成条件和动态参与者集合必须成为 receiving Executor 的显式状态，不能依赖“所有人应该都回了”的暗示。
外部等待用强类型 Request/Response 建模；子图只经真实 input/output type 进出，不跨层广播。
最后用 build-time 类型、连通、binding 与 Edge 校验锁住结构，再用路由、Join、暂停、可见数据和副作用回归证明行为等价。
本方法只回答静态数据流结构；superstep 的时间、状态可见性和 checkpoint 一致性由另一方法处理。

---

## A1 — 书中的应用（Past Application）

### 案例 1：垃圾邮件检测结果驱动强类型条件路由（c09）

- **问题**：邮件处理既需要 Agent 理解自由文本，又要求垃圾邮件和正常邮件走不同、可审计的确定路径，不能靠下游 Agent 看全文后各自决定是否行动。
- **方法论的使用**：官方让 spam detection Agent 输出结构化 `DetectionResult`，其中包含 `IsSpam` 等路由字段；Workflow 用条件 Edge 把结果显式送到“标记垃圾邮件”或“生成专业回复”分支，原始邮件则通过共享状态供被选中的下游读取。
- **结论**：开放式语义分类留给 Agent，分支控制交给 typed message 与确定性 Edge；未被选中的 Executor 不会因广播而自行筛选。
- **结果**：垃圾邮件样例进入标记路径并附带原因；换成正常跟进邮件后，同一图进入回复和发送路径。案例真实展示了结构化 Agent 输出驱动的 typed routing，而不是仅有概念图。

### 案例 2：保留真实类型的子 Workflow 边界（c25）

- **问题**：父 Workflow 需要复用多步文本处理或多 Agent 分析链，但不应了解子图内部节点，也不应跨层广播上下文。
- **方法论的使用**：官方用 `BindAsExecutor` 把 uppercase→reverse→append 的强类型流水线嵌入父图，或用 `AsAIAgent` 包装 specialist 分析链；父图只经子图声明的 input/output type 交互。
- **结论**：子图是有真实消息契约的 Executor，不是绕过类型系统的黑盒广播容器。
- **结果**：父图把完整子流程当作单一步骤，接收其 typed output 后继续路由，同时保持内部结构与状态隔离。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 用户从零设计 Agent Workflow，需要把业务依赖落成 Executor、typed message、Edge、Join 和 Request/Response。
2. 用户要把 AutoGen GraphFlow、广播消息总线、条件 transition 或 target-side activation 迁到 Agent Framework typed dataflow。
3. 用户遇到广播过度暴露、下游自筛选、Join 条件隐式、类型错到运行期才发现，想建立 build-time gate 与行为等价回归。
4. 用户要把子 Workflow 嵌进父图，同时保留真实输入输出类型和边界。

**中文语言信号**：
- “把这个广播式多 Agent 图迁成 typed Workflow”
- “这里该用 Direct、Switch、Fan-out 还是 Fan-in”
- “给每个 Executor 和 Edge 定义输入输出类型，并在 build 时校验”

### Exact English triggers

1. “Design a typed agent workflow with explicit executor inputs, outputs, and edge contracts.”
2. “Migrate this broadcast/transition-based GraphFlow to typed dataflow and edge-based activation.”
3. “Choose Direct, Switch, fan-out, fan-in, and explicit Join state, then add build-time validation.”

### 双入口 / Two entry paths

- **新建设计入口**：从业务数据依赖和消息基数推导最小 typed graph，不先照搬组织结构或 Agent 名单。
- **迁移入口**：先记录旧图真实行为，再逐项重建广播订阅、transition、activation、Join、暂停与共享上下文，最后做等价回归。

### 与相邻 skill 的最终区分与负触发

- 若尚未证明需要 Workflow，仍在函数、Agent、Skill、Harness 与人审之间选型，**不触发本 skill**；先用 `choose-minimum-sufficient-agent-architecture`。
- 若静态图已确定，只问慢分支屏障、下一步状态可见性或 checkpoint 时点，**不触发本 skill**；改用 `reason-about-superstep-barriers`。
- 若还在 Sequential/Concurrent/Group Chat/Magentic、Agent-as-Tool/Handoff/A2A 之间选择组织语义，**不触发本 skill**；改用 `choose-multi-agent-coordination-and-delegation`。
- 若只设计一笔审批的身份、版本、Pending、超时、迟到响应与恢复重发，**不触发本 skill**；改用 `model-recoverable-human-decisions`。

---

## E — 可执行步骤（Execution）

1. **选择入口并建立行为基线**
   - 新建：列出业务输入、输出、依赖、开放判断、确定逻辑、外部等待和副作用。
   - 迁移：额外盘点旧广播订阅、transition 条件、target activation、ANY/ALL Join、暂停、隐含共享上下文及副作用顺序。
   - **完成标准**：每项旧行为或新需求都有唯一编号，且能区分“数据依赖”与“控制转移”；迁移场景已有可回放基线。

2. **定义 Executor 与真实 I/O**
   - 每个单元写明 input type、output type、是否 Agent、是否持有 Join state；确定性逻辑优先普通 Executor。
   - Agent 输出必须先解析并验证结构，再作为 Edge 判定输入。
   - **完成标准**：没有“接收整个上下文再自行判断”的模糊 Executor；每个端口都有 schema、必填字段和验证失败路径。

3. **按消息基数选择 Edge，不混入时间推理**
   - 1→1 用 Direct；one-of-N 用 Conditional/Switch 并定义 default；1→many 用 Multi-Selection/Fan-out；many→1 用 Fan-in/aggregator。
   - **完成标准**：每条边标注 source type、target type、基数、条件和 default；此步不以 superstep 性能为理由改 Edge 语义。

4. **收窄消息并显式化 Join/等待/子图**
   - 每个目标只收完成职责所需字段；把 ANY/ALL、动态 expected/completed 集合放入 receiving Executor；外部等待用 typed Request/Response；子图保留真实 input/output type。
   - **完成标准**：不存在广播自筛选、跨层广播或隐式“等所有人”；动态 Join 能说明参与者如何登记、完成和取消。

5. **通过构建期结构门禁**
   - 执行类型兼容、图连通、Executor binding、重复/非法 Edge、Switch default 和不可达分支校验。
   - **完成标准**：图能成功 build；故意注入类型不匹配、缺 binding、非法 Edge 和无 default 分支时均能在运行前失败。

6. **执行迁移/设计回归**
   - 比较每类输入的路由目标、Join 完成条件、暂停/恢复位置、各 Executor 可见字段和外部副作用序列；对 Agent 结构化输出加入无效 schema 测试。
   - **完成标准**：需求编号全部被测试覆盖；迁移场景除经批准的差异外行为等价，且未扩大数据可见性。
   - **判停条件**：若失败只涉及“何时推进、慢分支、下一步状态可见性或 checkpoint 时点”，停止修改 Edge，转 `reason-about-superstep-barriers`。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 只需要推理 superstep 延迟、同步屏障、共享状态下一步可见性或 checkpoint 边界：调用 `reason-about-superstep-barriers`。
- 尚未证明需要 Workflow，普通函数或单次 Agent 已足够：先做最低充分架构选型。
- 问题是多 Agent 的组织、所有权或跨进程协议选择，而非 typed message 落图：使用 v14。
- 问题是跨进程/worker 的 Durable 恢复层选择，而非静态数据流：使用 v13。

### 作者在书中警告的失败模式

- **Agent 取代确定性函数（ce01）**：所有 Executor 都做成 Agent，会把可测试逻辑变成概率性执行；Executor 不等于 Agent。
- **广播迁移只换类名**：若仍把全文发给所有节点并让目标自筛选，就没有完成 control-flow → typed dataflow 的语义迁移。
- **把步内并行当独立流水线（ce23）**：这是运行时 BSP 误解；不得靠随意更换 Edge 类型掩盖，应转 v10 处理时间结构。
- **只比较最终文本**：最终答案相同不能证明路由、Join、暂停、可见数据或副作用等价。

### 作者的盲点 / 时代局限

- 文档是 2026 年快速演进截面，API 名称、语言支持和预览状态可能变化；实施前必须核对目标 SDK 当前文档与版本。
- typed graph 能把类型和路由错误前移，但未证明它对所有复杂协作都优于普通状态机或事件系统；简单需求应回退到更低抽象。
- build-time 类型与连通性正确不保证 Agent 语义正确；LLM 输出非确定，仍需 schema、范围、业务规则和多样本评估。

### 容易混淆的邻近方法论

- Edge/Fan-out/Fan-in 决定**静态数据流**；Superstep 决定**运行时推进与屏障**。前者属于本 skill，后者属于 v10。
- Handoff 是会话所有权转移，不是 typed Edge 消息路由。
- Checkpoint/Durable 是恢复层，不是 Edge 设计的替代品。

---

## 相关 skills

- `depends-on` [`choose-minimum-sufficient-agent-architecture`](../choose-minimum-sufficient-agent-architecture/SKILL.md)：只有先证明需要显式 Workflow，才进入 Executor、typed Edge、Join 与构建期校验设计。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f15、p23、f16；案例 c09、c10、c11、c15、c25；反例 ce01、ce23
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
