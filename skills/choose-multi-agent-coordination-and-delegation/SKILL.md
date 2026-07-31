---
name: choose-multi-agent-coordination-and-delegation
description: |
  当用户要判断是否需要多 Agent，或在 Sequential/Concurrent/Group Chat/Magentic、Agent-as-Tool/Handoff/A2A 间选择时调用；按依赖、协作方式、任务所有权、上下文可见性与部署边界给出最小拓扑。若只需 typed Edge/Join、superstep、恢复层或单 Agent 内部设计，不调用本 skill。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflows · Orchestrations / Agents as Tools / Agent-to-Agent（原文 8303–8449、10503–11308、17331–17482、17573–17585 行）
tags: [multi-agent, orchestration, delegation, task-ownership, a2a, maf]
related_skills:
  - slug: choose-minimum-sufficient-agent-architecture
    relation: depends-on
  - slug: design-or-migrate-typed-agent-workflows
    relation: composes-with
---

# 选择多 Agent 协作、委派所有权与部署边界

## R — 原文（Reading）

> In handoff orchestration, control is explicitly passed between agents based on defined rules. Each agent can decide to hand off the entire task to another agent. In contrast, agent-as-tools involves a primary agent that delegates sub tasks to other agents and once the agent completes the sub task, control returns to the primary agent.
>
> 中文翻译：在 Handoff 编排中，控制权按规则显式转交，Agent 可把完整任务交给另一个 Agent；Agent-as-Tool 则由主 Agent 委派子任务，子 Agent 完成后，控制权返回主 Agent。
>
> — Microsoft Agent Framework，Orchestrations · Handoff，原文 10624–10631 行

---

## I — 方法论骨架（Interpretation）

多 Agent 不是默认答案；先证明单 Agent、普通函数或确定性 Executor 无法清楚承载不同指令、工具、模型或责任边界。
选型分三层，不能把七种术语当作同一层的互斥菜单。
第一层是协作拓扑：固定前后依赖用 Sequential；互不依赖且需要并行多视角用 Concurrent；需看完整共享历史并多轮互评用 Group Chat；路径未知且确需计划、进度账本、停滞检测和重规划时才用 Magentic。
第二层是任务所有权：主 Agent 保留总责、只要子结论时用 Agent-as-Tool；接收方应接管完整任务和后续会话时用 Handoff。
第三层是部署边界：同进程、同团队优先本地组合；跨进程、服务、团队、组织或语言且需要独立演进时，才用 A2A。
上下文可见性是硬约束：Agent-as-Tool 默认只收显式参数并返回最终结果；Handoff 同步会话；Group Chat 让参与者每轮看到完整对话；A2A 只暴露协议响应，远端状态由远端拥有。
这三层可以组合：远端专家可通过 A2A 通信，但“远端”并不自动表示它接管会话；A2A 也不提供 Handoff、Workflow 或 Durable 语义。
最后以满足需求的最小混合拓扑收口，并为每条边定义上下文、聚合、超时、重试、版本与观测责任。

---

## A1 — 书中的应用（Past Application）

### 案例 1：同一翻译任务的 Sequential 与 Concurrent 对照（c11、c17）

- **问题**：多语言翻译既可能要求后一步消费前一步结果，也可能要求多个翻译者独立处理同一输入。
- **方法论的使用**：法语→西班牙语→英语教程用 Sequential 连接三个 Agent；三语言独立翻译教程则让三个 Agent Concurrent 处理同一句输入并自动聚合。
- **结论**：Agent 数量相同不决定拓扑；真正的分界是数据依赖。后一步必须建立在前一步输出上才串行，互不依赖才并行。
- **结果**：顺序案例中 `Hello World!` 依次流经三种语言；并发案例同时产出法语、西班牙语和英语结果列表。（原文 8303–8449、10503–10605 行）

### 案例 2：专家接管与共享历史互评（c18、c19）

- **问题**：作业助手要在数学、历史专家间切换；电动车文案则需要写作者与审稿者反复改进同一稿件。
- **方法论的使用**：导师案例让 triage 把完整会话 Handoff 给领域专家，专家也可交回；文案案例由 Group Chat manager 选择 speaker，让所有参与者看到完整历史并迭代。
- **结论**：需要“谁继续负责用户会话”时选 Handoff；所有角色仍共同拥有同一产物、需要轮流评审时选 Group Chat。
- **结果**：导师对话随数学/历史问题切换负责人；口号从 “Green Dreams, Zero Emissions” 经反馈改为获批的 “Pure Power, Zero Impact”。（原文 10610–10929 行）

### 案例 3：动态经理与跨服务协议分别解决不同问题（c20、c08）

- **问题**：能耗研究的解题路径未知，需要研究与计算反复配合；量子密码学分析则由独立远端 Agent 执行长任务。
- **方法论的使用**：能耗案例使用 Magentic manager 建计划、选下一 Agent、记录进度、检测停滞并重规划；远端分析案例把 A2A 端点包装成统一 `AIAgent`，通过 continuation token 轮询到完成。
- **结论**：Magentic 解决运行时动态协作，A2A 解决跨服务通信；两者不是替代关系，也不因使用 A2A 就自动拥有动态规划。
- **结果**：Magentic 教程真实展示计划、进度与重规划事件，但未给固定数值结论；A2A 教程跨框架调用远端 Agent 并取得最终响应。（原文 6570–6609、10993–11308 行）

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 用户怀疑一个方案是否真的需要多个 Agent，希望先允许结论为“单 Agent/函数足够”。
2. 用户在 Sequential、Concurrent、Group Chat、Magentic 之间选协作方式，或要混合固定依赖、独立并行、共享历史互评与动态探索。
3. 用户在 Agent-as-Tool 与 Handoff 之间摇摆，不清楚主 Agent 是否保留总责、接收方是否接管后续会话。
4. 用户因跨进程、团队、组织、语言或独立发布周期考虑 A2A，并需要区分协议边界与所有权语义。
5. 用户要为多 Agent 方案明确各角色能看到哪些上下文，以及谁负责聚合、超时、重试、版本和观测。

**中文语言信号**：
- “这个需求真的需要多 Agent 吗？需要的话选顺序、并发、群聊还是 Magentic？”
- “主 Agent 应该把专家当工具，还是把整个会话 handoff 给专家？”
- “跨团队的远端 Agent 要上 A2A 吗？A2A 和 Handoff 是一回事吗？”

### Exact English triggers

- “Do we need multiple agents, and should coordination be sequential, concurrent, group chat, or Magentic?”
- “Should the primary agent retain ownership via agent-as-tool, or hand off the whole conversation?”
- “Does this cross-service/team boundary justify A2A, and what context should cross it?”

### 与相邻 skill 的最终区分与负触发

- 若尚未出现真实的多个职责候选，只需在函数、单 Agent、Skill、Workflow、Harness 与人审间做全局抽象选型，**不触发本 skill**；先用 `choose-minimum-sufficient-agent-architecture`。
- 若组织与所有权语义已经确定，只需定义 Executor I/O、typed Edge、Join 与构建期校验，**不触发本 skill**；改用 `design-or-migrate-typed-agent-workflows`。
- 若只分析既定 Workflow 的 superstep 尾延迟、屏障、状态可见性或 checkpoint 时点，**不触发本 skill**；改用 `reason-about-superstep-barriers`。
- 若只选择标准 checkpoint 或跨进程/worker Durable Task，**不触发本 skill**；改用 `choose-workflow-recovery-layer`；A2A 不是恢复层。

---

## E — 可执行步骤（Execution）

1. **先证明多 Agent 的必要性**
   - 列出候选角色及其输入、输出、指令、工具、模型、权限和责任；检查它们是否只是同一 Agent 的普通步骤或可由确定性函数完成。
   - **完成标准**：每个保留的 Agent 至少有一项不可用普通函数/同一指令集清楚替代的专门边界；若没有，明确输出“无需多 Agent”，给出单 Agent/函数方案并停止。

2. **按依赖与协作方式选择拓扑**
   - 画任务依赖图：后一步必须消费前一步产物选 Sequential；任务彼此独立且只需最终聚合选 Concurrent；参与者需看共享历史并多轮互评选 Group Chat；只有路径无法预先确定且需要动态计划、进度账本、停滞检测和重规划时选 Magentic。
   - **完成标准**：每条任务边都有“依赖/独立/共享迭代/动态探索”之一的证据，并定义聚合或终止条件；固定流程不得仅因“复杂”升级 Magentic。

3. **按任务所有权选择 Agent-as-Tool 或 Handoff**
   - 主 Agent 保留总责、子 Agent 只完成窄任务并返回结果时选 Agent-as-Tool；接收方要取得完整任务、继续面向用户决策并可再次转交时选 Handoff。
   - **完成标准**：每次委派都写明委派前 owner、委派后 owner、控制权返回条件；不存在“只是查一个子结论却交出整段会话”或“声称接管却只返回工具结果”。

4. **定义最小上下文可见性**
   - Sequential 只传下游所需产物；Concurrent 分支独立运行、在 aggregator 前不互看；Group Chat 同步完整对话并设置 speaker/轮次/终止；Magentic 维护计划与进度账本；Agent-as-Tool 只给显式参数；Handoff 同步继续会话所需历史；A2A 只传协议契约允许的数据。
   - **完成标准**：形成“边—可见字段—状态 owner—保留期”矩阵；任何全历史广播都有协作必要性，敏感字段和工具内部过程不会因方便而默认扩散。

5. **按部署与演进边界决定是否使用 A2A**
   - 同进程、同团队、同发布周期优先本地编排或 Agent-as-Tool；跨进程/服务、团队/组织、语言/框架或独立发布周期时才采用 A2A，并单独叠加所需的 Agent-as-Tool 或 Handoff 所有权语义。
   - **完成标准**：每个 A2A 边都有真实边界理由，以及 endpoint/discovery、认证授权、schema/version、timeout/retry、幂等、状态丢失和观测责任；文档明确 A2A ≠ Handoff ≠ Durable。

6. **做复杂度回退与故障验证**
   - 依次测试：固定流程误上 Magentic、独立任务误串行、局部子任务误 Handoff、同进程误 A2A、远端超时/重试、共享历史泄漏、manager 不终止与聚合缺失。
   - **完成标准**：每项都有可观察失败和回退方案；移除任一 Agent 或协议层后若仍满足要求，就回退到更简单结构；最终输出最小混合拓扑、所有权表、上下文矩阵与远端运行契约。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 用户只需在函数、单 Agent、Skill、Workflow、Harness 或人审间做全局抽象选型，尚未出现真实多 Agent 职责：优先使用 v01。
- 多 Agent 组织语义已经确定，只需设计 typed Edge、Join、消息 schema 或构建期校验：使用 v09。
- 只需分析 superstep 尾延迟、同步屏障、状态可见性或 checkpoint 时点：使用 v10。
- 只需选择标准 checkpoint 或跨进程/worker Durable Task：使用 v13；A2A 不是恢复层。

### 作者在书中警告的失败模式

- **ce01：不需要 Agent 仍引入 Agent**。若普通函数或单 Agent 已足够，多 Agent 只会增加不确定性、成本、延迟、上下文同步和故障面。
- **ce02：把第三方接入误当成可信边界**。A2A 只提供协议，不继承第三方许可、地域、数据保留、授权或费用边界；跨组织数据必须重新审计。
- **固定流程误用 Magentic**：文档明确简单协调应优先 Group Chat；固定依赖应使用 Sequential/Concurrent 等更简单模式。
- **把 Handoff 当 Agent-as-Tool**：前者转移完整任务所有权与会话，后者由主 Agent 保留责任并只接收子结果；混用会造成 owner 不清或上下文过度暴露。
- **同进程误用 A2A**：同一应用、同一团队内 Agent-as-Tool 更简单；无真实边界时上 A2A 会平白引入网络延迟、发现、失败、重试和版本治理。

### 作者的盲点 / 时代局限

- Magentic 类型与部分工具在文档截面仍标记 experimental；官方明确指出其超出原始 Magentic-One 任务域的表现未经充分验证。
- 案例多为小规模 happy path，没有证明共享全历史在大量 Agent/长会话下的 token 成本、隐私暴露与质量退化可接受。
- A2A 互操作不等于远端可靠：远端 Agent 若重启丢失 context ID 对应状态，会话仍可能中断；应用需另行设计恢复与业务幂等。
- C#、Python、Go 的编排能力和默认值可能不对称；实施前必须核对目标 SDK 的当前官方文档与版本。

### 容易混淆的邻近方法论

- Sequential/Concurrent/Group Chat/Magentic 回答“怎样协作”；Agent-as-Tool/Handoff 回答“谁拥有任务”；A2A 回答“跨什么部署边界通信”。三层可以组合，但不能互相替代。
- Handoff 是会话所有权转移，不是 typed Edge 的同义词；A2A 是协议，不是 Handoff，也不是 Durable execution。
- Group Chat 的 manager 主要选择 speaker 和控制对话；只有确需计划、停滞检测与重规划时才升级 Magentic。

---

## 相关 skills

- `depends-on` [`choose-minimum-sufficient-agent-architecture`](../choose-minimum-sufficient-agent-architecture/SKILL.md)：先证明多个 Agent 的职责、工具、模型或责任边界确实不可由更简单结构承担。
- 与 [`design-or-migrate-typed-agent-workflows`](../design-or-migrate-typed-agent-workflows/SKILL.md) `composes-with`：先确定协作拓扑、任务所有权与部署边界，再把需要显式控制的部分落成 Executor、typed Edge 与 Join。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f23、f24；案例 c08、c11、c17、c18、c19、c20；反例 ce01、ce02
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
