---
name: design-and-govern-executable-agent-skills
description: |
  当用户要设计、打包、引入或审计可执行 Agent Skill，涉及“advertise/load/read/run”“progressive disclosure”“Skill 脚本能否执行”“load/read/run 如何审批”“第三方 Skill 供应链、沙箱或租户缓存”时调用。不要把四级披露当成自动权限升级，也不用于一般 Agent 数据流安全或固定业务 Workflow 编排。
source_book: 《Microsoft Agent Framework》 Microsoft
author: Microsoft
source_chapter: Agent Skills · Progressive disclosure；Code-defined skills；MCP-based skills；Tool approval；Security best practices
source_lines: 2063-2080, 2230-2235, 2456-2458, 2486-2492, 2653-2689, 2873-2881, 2915-2933, 17022-17038
tags: [agent-skills, progressive-disclosure, supply-chain, sandbox, approval, governance, maf]
related_skills:
  - slug: preserve-trust-across-agent-dataflows
    relation: composes-with
---

# 设计并治理可执行 Agent Skill

## R — 原文（Reading）

> “Agent Skills use a four-stage progressive disclosure pattern to minimize context usage: 1. Advertise (~100 tokens per skill) … 2. Load (< 5000 tokens recommended) … 3. Read resources (as needed) … 4. Run scripts (as needed) … This pattern keeps the agent's context window lean while giving it access to deep domain knowledge on demand.”
>
> — Microsoft, *Agent Skills · Progressive disclosure*, 原文第 2063–2080 行

自行翻译：Agent Skill 用四级渐进披露减少上下文占用：先以约百 token 广告名称与描述；任务匹配后加载建议少于 5000 token 的说明；需要时再读取资源；需要时再运行脚本。这样能保持上下文精简，同时按需取得深入领域知识。

> **关键校正**：这四级描述的是**内容装载顺序**，不是自动的信任等级或权限升级链。`advertise`、`load`、`read`、`run` 的授权必须独立判断；“已发现/已读取”绝不推出“已信任/可执行”。

---

## I — 方法论骨架（Interpretation）

1. Agent Skill 是可移植能力包，不只是 prompt：它可包含触发描述、执行说明、参考资源、模板和脚本。
2. 常驻层只 advertise 窄名称、用途与精确触发，让大量 Skill 可发现而不挤满上下文。
3. 命中后才 load 核心步骤；长文档、模板与资产在真正需要时 read；确定性计算或校验才考虑 run script。
4. 渐进披露只优化“何时装载什么”，并不自动授予更高权限；加载轴与信任/授权轴必须并行治理。
5. 第三方 Skill 同时进入提示供应链和代码供应链，部署前必须固定来源、版本并审阅全部内容。
6. 远程 archive 的资源可发现不等于其中脚本可信；未知远程脚本默认保持不可执行。
7. `load_skill`、`read_skill_resource` 与 `run_skill_script` 风险不同，只读豁免不能扩张为脚本自动批准。
8. 生产脚本 runner 必须具备隔离、文件/网络限制、CPU/内存/时限、脚本与参数白名单及审计。
9. 多租户发现与缓存需要 tenant isolation key 和刷新策略，避免 Skill 集合跨租户泄漏或权限长期陈旧。
10. 失败治理还要记录版本、脚本哈希、参数、输出和脱敏错误，并对恶意输入与来源漂移 fail closed。

---

## A1 — 书中的应用（Past Application）

### 案例：可渐进加载的员工报销 Skill（唯一绑定案例 c06）
- **问题**：员工报销既需要清晰触发与操作步骤，也依赖政策 FAQ、模板和确定性校验，但不应把全部内容常驻每次 Agent 调用。
- **方法论的使用**：官方把 `SKILL.md` 用于触发描述和步骤，把政策 FAQ 放 `references`、模板放 `assets`、校验程序放 `scripts`。
- **结论**：能力按 advertise → load instructions → read resources → run scripts 分层打包，说明与大资源/可执行物分离。
- **结果**：Agent 先只看到约百 token 的名称和描述，命中后才加载正文，并仅在需要时读取政策或运行校验脚本。
- **证据边界**：c06 证明结构与按需装载，不是完整生产安全成功案例；它没有证明沙箱、供应链审计、租户缓存隔离或审批策略已经通过生产验证。

---

## A2 — 触发场景（Future Trigger）★

### 正向 Trigger / Positive triggers

1. 要把某个领域流程打包成 `SKILL.md + resources/assets + scripts`，并控制常驻上下文成本。
2. 要审计、安装或上线来自 Git、MCP、供应商或内部团队的第三方 Agent Skill。
3. 正在决定 `load_skill`、`read_skill_resource`、`run_skill_script` 的审批与只读自动豁免范围。
4. 要让 Skill 脚本进入生产，需要设计容器/沙箱、资源上限、文件网络权限、白名单与审计。
5. 多租户系统动态发现和缓存 Skill，需要避免跨租户缓存污染及内容长期不过期。

### 精确语言信号 / Exact language signals

- 中文：`怎么设计 Agent Skill？`、`SKILL.md、references 和 scripts 怎么拆？`、`第三方 Skill 上线前怎么审计？`、`run_skill_script 能自动批准吗？`、`远程 MCP Skill 脚本能执行吗？`、`Skill 缓存怎么按租户隔离？`
- English: `design an executable agent skill`, `progressive disclosure for skills`, `advertise load read run`, `govern run_skill_script`, `audit a third-party skill`, `sandbox skill scripts`, `tenant-isolated skill cache`.

### Negative triggers（出现时不应调用）

- 只是要在 Session、History、Context Provider 与 Tool 之间放置会话信息：应转上下文分层 skill。
- 只是沿用户/RAG/LLM/Tool/AG-UI 追踪数据来源与 prompt injection：应转 Agent 数据流信任 skill。
- 只是判断应使用 Skill 还是固定 Workflow，尤其涉及不可重复副作用：应先转最低充分架构选型；本 skill 仅在确认采用 Skill 后治理其包与执行面。
- 只是设计 CodeAct 与 direct tools 的逐操作审批：应转 CodeAct/直接工具选型，不因出现“脚本”二字就调用本 skill。

### 与相邻 skill 的最终区分与负触发

- 若只是决定会话状态、消息历史、主动 Context 与按需 Tool 的归属，**不触发本 skill**；改用 `separate-session-history-context-and-tools`。
- 若是一般 Agent 数据流、角色、工具参数、第三方协议或输出 sink 的信任审计，**不触发本 skill**；改用 `preserve-trust-across-agent-dataflows`。
- 若尚未证明应该使用 Agent Skill，仍在 Skill、Workflow、函数或 Agent 之间选型，**不触发本 skill**；先用 `choose-minimum-sufficient-agent-architecture`。
- 若问题是把多次工具调用折进 CodeAct，或保持 direct tools 的逐操作审批，**不触发本 skill**；改用 `choose-codeact-or-direct-tools-by-risk`。

---

## E — 可执行步骤（Execution）

1. **收窄领域与触发契约**
   - 写出单一领域、3–5 个正向触发、至少 3 个 negative trigger，并使名称与描述可辨别相邻 Skill。
   - **完成标准**：广告层只含名称、用途、触发/禁用条件；不存在“everything-about-X”式大而全范围。
   - **判停条件**：若任务有固定路径、不可重复副作用、多 Agent 或必须逐步恢复，先转 Workflow/架构选型，不继续包装成单 turn Skill。

2. **按装载成本拆包**
   - 核心步骤放 `SKILL.md`；长政策和 API 细节放 `references`；模板/静态文件放 `assets`；可确定执行的最小程序放 `scripts`。
   - **完成标准**：每个文件都有唯一用途；`SKILL.md` 保持简洁，资源与脚本只在任务需要时装载。

3. **建立来源与全内容审计**
   - 固定来源、维护者、版本/commit、内容哈希；审阅指令、资源、脚本及声明—行为一致性，检查外传、配置修改和对抗性指令。
   - **完成标准**：形成可复核审计记录；任何未审阅文件、来源漂移或行为不符都阻止上线。

4. **分离加载轴与授权轴**
   - 为 advertise、load、read、run 分别定义允许主体、审批规则和审计；只对已验证的低风险只读 load/read 做窄豁免。
   - **完成标准**：`run_skill_script` 没有因“已发现/已加载/已读取”而自动获批；不存在全量 auto-approve 覆盖未知脚本。

5. **硬化脚本 runner 与缓存**
   - 在隔离环境限制文件、网络、凭据、CPU、内存和 wall-clock；允许脚本和参数白名单；多租户缓存设置 isolation key 与 refresh interval。
   - **完成标准**：默认拒绝未列脚本/参数/网络目标；两个租户看不到对方 Skill 集，权限变更能在规定时间内刷新。

6. **记录与压力测试 fail closed**
   - 记录 Skill 版本、脚本哈希、审批者、参数、输出摘要与脱敏错误；测试远程 archive、恶意异常、typosquatting、缓存串租户和全量 auto-approve。
   - **完成标准**：所有未验证脚本均不执行，错误不向模型泄露秘密或注入指令，审计记录可还原一次执行。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 普通函数或固定状态机已足够：不要为了复用而引入 Agent Skill 的模型选择与提示供应链。
- 任务依赖固定顺序、步骤级 checkpoint、付款/发信等不可幂等副作用：优先 Workflow，并补业务幂等；Skill 整体重试不提供步骤级恢复。
- 需求只是读取一段短、稳定、每轮必需的政策：可能直接使用可信 Context Provider，而不是制造 Skill 包。
- 一般 Agent 数据流或 AG-UI 安全审计不应被缩减成 Skill 供应链审计。

### 必须吸收的绑定反例

- **ce06：直接执行远程 MCP archive 脚本**。远程资源可发现不等于代码可信；archive 脚本默认不执行，确需执行应内化、审阅并进入隔离 runner。
- **ce07：缓存未按租户隔离且默认不过期**。必须设置 tenant isolation key 和刷新策略，不能让所有调用者共享永久缓存桶。
- **ce08：全量自动批准 Skill 工具**。只读 load/read 豁免不能扩张到 `run_skill_script`；未知或高风险脚本保留逐次审批。
- **ce09：原始异常回灌模型**。异常可能泄露连接串、路径和服务名，也可携带 prompt injection；只返回脱敏、结构化错误。
- **ce10：把 Skill 当无害提示词**。必须同时审阅 `SKILL.md`、资源和脚本，核对来源、版本及声明—行为一致性。
- **ce11：单次 Skill 承载不可幂等副作用**。Skill 失败通常整体重试，发信、扣款等可能重复；转 Workflow 并使用幂等键/outbox/补偿。

### 阶段 0 局限与作者盲点

- 四级渐进披露首先是上下文装载优化，**不是自动权限升级模型**，也不保证权限随层级天然单调；每层信任与授权必须独立定义。
- c06 只是设计示例，不能声称已验证生产脚本安全、审批、人审可恢复性、缓存隔离或供应链治理。
- 文档是 2026 年中的快速演进截面，多个包仍为 prerelease/preview，各语言 SDK 的 Skill、MCP 与脚本能力不对称；实现前必须核对当前官方版本。
- 官方没有量化大量 Skill 聚合后的触发退化、上下文成本、延迟和供应商费用；需要在自己的规模与模型上测量。
- 官方 happy path 较多，多租户隔离、配额/成本保护、灾难恢复和跨版本迁移仍由应用方负责。
- Provider-neutral 只描述抽象，不代表不同部署、鉴权、托管工具和运维能力等价。

### 容易混淆的邻近方法论

- advertise/load/read/run 是**内容何时进入上下文或执行面**；approval/sandbox/provenance 是**是否允许以及以何权限执行**。两条轴不能合并。
- “脚本在容器内”不代表安全完成：宿主凭据、网络、文件映射、参数与错误回传仍需分别收窄。
- Skill 的结构治理不能替代先做 Skill-vs-Workflow 选型；不可重复副作用不能靠渐进披露解决。

---

## 相关 skills

- 与 [`preserve-trust-across-agent-dataflows`](../preserve-trust-across-agent-dataflows/SKILL.md) `composes-with`：Skill 的提示与代码供应链治理需叠加一般数据流的 provenance、参数校验、第三方出境与输出 sink 控制。

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **绑定候选**：f06, p05, p06, p07, p08, p09
- **绑定案例**：c06（仅此一例）
- **绑定反例**：ce06, ce07, ce08, ce09, ce10, ce11
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
