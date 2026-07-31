---
name: model-recoverable-human-decisions
description: |
  当 Workflow 等待人工审批、补件、签核等异步决定，并要求跨 UI 断线、重启、超时后继续时调用。必须在响应与恢复时复验当前身份、tenant、对象权限和版本；correlation ID 不是授权。信号包括“HITL/request-response/pending approval/恢复重发/late response”。不用于判断哪些操作该审批或只选择恢复层。
source_book: Microsoft Agent Framework（Microsoft Learn 文档集，2026 固定副本）
source_chapter: Workflows · Human-in-the-Loop（原文 8459–8570 行）；Durable Extension · Human-in-the-loop orchestrations（原文 12303–12369 行）
tags: [hitl, request-response, pending-state, checkpoint, timeout, idempotency, maf]
related_skills:
  - slug: design-or-migrate-typed-agent-workflows
    relation: depends-on
  - slug: choose-workflow-recovery-layer
    relation: composes-with
---

# 把人类决定建模为可恢复请求—响应状态

## R — 原文（Reading）

> A RequestPort is a communication channel that allows executors to send requests and receive responses. When an executor sends a message to a RequestPort, the request port emits a RequestInfoEvent that contains the details of the request. External systems can listen for these events, process the requests, and send responses back to the workflow. The framework automatically routes the responses back to the appropriate executor based on the original request.
>
> 中文翻译：RequestPort 是 Executor 发送请求并接收响应的通信通道。请求进入后，它会发出包含请求详情的 RequestInfoEvent；外部系统可监听、处理并回送响应，框架再依据原请求自动把响应路由回正确的 Executor。
>
> — Microsoft Agent Framework，Human-in-the-Loop，原文 8467–8473 行

> When a checkpoint is created, pending requests are also saved as part of the checkpoint state. When you restore from a checkpoint, any pending requests will be re-emitted as RequestInfoEvent objects, allowing you to capture and respond to them.
>
> 中文翻译：创建 checkpoint 时，待处理请求也会作为 checkpoint 状态保存；从 checkpoint 恢复时，这些请求会重新以 RequestInfoEvent 发出，以便外部系统重新捕获并响应。
>
> — Microsoft Agent Framework，Checkpoints and Requests，原文 8563–8567 行

---

## I — 方法论骨架（Interpretation）

HITL 不是“模型准备调用高风险工具时弹一个确认框”，而是一个由人参与的异步、强类型状态机。
Workflow 必须发出明确的 request 类型，也只接受明确的 response 联合类型；自由文本、布尔值或 UI 会话不能充当业务契约。
请求发出后进入 `Pending`，请求 ID、correlation ID、业务对象及版本、允许动作、截止时间和继续执行所需上下文必须进入 checkpoint 或 Durable state。
浏览器、SSE 和操作员当前在线状态只是投递表面，不是等待的耐久载体；连接断开不应丢失审批。
响应到达时要重新验证登录主体、tenant、对象权限、请求仍有效且对象版本未过期；correlation ID 只负责关联，不负责授权。
恢复同一 run 时，pending request 应重新发出或与恢复调用一并提交响应；重发必须可去重，不能新建第二个业务请求。
超时、升级、撤销、替代请求与迟到响应都要有显式终态和合法转换；迟到响应默认拒绝，不能把已升级或已取消的运行重新打开。
审批通过也不等于外部副作用 exactly-once；发布、付款、写病历等动作仍需业务幂等键、outbox 或补偿。

---

## A1 — 书中的应用（Past Application）

### 案例 1：猜数字的强类型 RequestPort 循环（c12）

- **问题**：Workflow 必须反复向外部人类索取数字，并根据“高了、低了、猜中”继续推进，而不是把输入绑在同步控制台调用上。
- **方法论的使用**：官方创建 `RequestPort<NumberSignal, int>`；`NumberSignal` 是请求类型，`int` 是响应类型。端口发出 `RequestInfoEvent`，外部系统用原请求创建 response，框架自动路由回 `JudgeExecutor`。
- **结论**：人类输入与 Workflow 内部 Executor 解耦，输入协议、关联关系与回送路径均显式化。
- **结果**：猜错后 Workflow 再次请求，猜中 42 后输出尝试次数；这是可重复的人机循环，不是一次性的 UI 确认。

### 案例 2：生产部署审批后再由 QA 验证（c16）

- **问题**：Agent 可以自动检查 staging，但生产部署不能默认执行，并且部署后还要进入独立验证步骤。
- **方法论的使用**：`DeployToProduction` 被包装为 `ApprovalRequiredAIFunction`；Agent 请求调用时 Workflow 暂停并发出含 `ToolApprovalRequestContent` 的 `RequestInfoEvent`，外部操作员回送强类型批准响应。
- **结论**：审批是顺序工作流中的暂停—响应状态，而不是提示词里的一句“请先获得同意”。
- **结果**：只有批准后才执行生产部署，随后路由到 `VerifyAgent`；普通工具默认不会自动获得这种审批语义。

### 案例 3：24 小时内容审批、超时升级与发布（c21）

- **问题**：审稿人可能隔天响应，运行会经历故障或重启，24 小时未响应还必须升级。
- **方法论的使用**：Durable orchestration 等待强类型 `HumanApprovalResponse` 外部事件，并设置 24 小时 timeout；批准、拒绝和超时分别进入发布、结束与升级分支。
- **结论**：长时间人工等待应是持久化外部事件状态，不能占住线程或依赖常驻浏览器连接。
- **结果**：等待期间不消耗计算；响应到达后恢复完整会话与执行状态，超时则转人工升级路径。

---

## A2 — 触发场景（Future Trigger）★

### 中文精确触发

1. 审批、医生签核、法务复核、补件或人工分类可能等待数小时/数天，并要求断线、重启后继续。
2. 用户要设计强类型 request/response、`Pending` 状态、correlation、恢复重发、timeout/escalation 或 late response 规则。
3. 已有审批 UI，但担心刷新页面、服务重启、重复通知或迟到批准会造成丢单、重复执行与越权。
4. tool approval 已能暂停，却还没有响应/恢复时的当前身份、tenant、对象权限与版本复验，也缺去重和批准后副作用幂等策略。

**中文语言信号**：
- “把 HITL 做成可恢复的 request/response，不要靠弹窗”
- “pending approval 要进 checkpoint，恢复后怎么重发？”
- “审批超时升级后，迟到响应应该怎么处理？”
- “医生换班、页面重启后还能继续同一笔签核吗？”

### Exact English triggers

- “model HITL as a typed asynchronous request/response state machine”
- “persist pending approvals and re-emit them after checkpoint restore”
- “handle timeout, escalation, duplicate delivery, and late approval responses”
- “the UI may disconnect while the workflow waits for human input”

### 与相邻 skill 的最终区分与负触发

- 若尚未决定哪些动作需要审批、是否必须逐操作可见，**不触发本 skill**；先用 `choose-codeact-or-direct-tools-by-risk` 做风险与审批粒度判断。
- 若只需在 continuation token、Session、标准 checkpoint 与 Durable Task 之间选择故障域，**不触发本 skill**；改用 `choose-workflow-recovery-layer`。
- 若只治理整个 Workflow/Session/Checkpoint 状态包的 fresh/reset/restore、owner、tenant 与完整性，**不触发本 skill**；改用 `govern-agent-state-lifecycles`。
- 若只是短连接内可安全取消、无需恢复的同步确认框，**不触发本 skill**；使用普通同步确认即可。

---

## E — 可执行步骤（Execution）

1. **固定审批边界与业务对象**
   - 写明等待的是批准、拒绝、补件、签核还是人工分类；标出被审对象、对象版本、批准后动作与可能副作用。
   - **完成标准**：存在一张“请求 → 允许决定 → 后续状态/动作”表；每个决定都有唯一业务语义，没有模糊的“确认/OK”。

2. **定义强类型 request/response 契约**
   - Request 至少包含 `request_id`、`correlation_id`、`workflow/run_id`、`object_id`、`object_version`、允许动作、最小展示数据、`created_at`、`expires_at`；Response 使用带判别字段的联合类型，如 `Approve`、`Reject`、`RequestChanges`，并包含 `request_id`、决定者和响应版本。
   - 不把 correlation ID、前端隐藏字段或自由文本当身份凭证；敏感显示数据按最小披露设计。
   - **完成标准**：schema 可做构建/运行时校验；未知动作、缺字段、错误类型和超版本响应均 fail closed。

3. **画出 pending 状态机与合法转换**
   - 最少定义 `Pending → Approved/Rejected/ChangesRequested/TimedOut/Cancelled/Superseded`；`TimedOut` 可再触发新的升级请求，但原请求保持终态。
   - 为重复响应、撤销、替代请求、并发审批者和迟到响应定义决胜规则；终态不可被旧响应重新打开。
   - **完成标准**：有可执行的状态转换表，列明前置状态、事件、校验、下一状态和副作用；每个事件在不合法状态下都有明确拒绝结果。

4. **通过 RequestPort 或外部事件发出并暂停**
   - 使用强类型 `RequestPort<Request, Response>`、tool approval request 或 Durable external event；将 UI/SSE/邮件仅作为通知与输入渠道。
   - 先让请求进入持久 `Pending`，再可靠投递通知；通知可能重复时以 `request_id` 去重，必要时使用 outbox。
   - **完成标准**：断开 UI、关闭浏览器或释放 worker 后，服务端仍能查询同一 pending request；没有靠进程内 Promise、线程或 socket 保存等待。

5. **把继续执行所需状态纳入恢复点**
   - 保存 request/response schema 版本、pending 状态、业务对象版本、下一步、截止时间和必要上下文；标准 Workflow 依靠 checkpoint，跨重启/worker/长等待时接入选定的 Durable 层。
   - **完成标准**：检查 checkpoint/Durable state 可还原“正在等谁对哪个版本做什么决定，以及收到决定后走哪条边”；Executor 私有状态若必需，已实现 save/restore hook。

6. **在响应入口重新认证、授权与校验**
   - 根据当前登录主体解析 owner/tenant 和业务权限；核对 request 仍为 `Pending`、未过期、对象版本未变化、response 类型允许；对重复投递返回同一结果。
   - **完成标准**：他租户响应、无权限审批者、过期/撤销请求、旧对象版本、未知动作和篡改 payload 均被拒绝并审计；合法重试不会产生第二次转换。

7. **实现恢复重发、超时、迟到响应与副作用防重**
   - Restore 同一 run 后重新监听 re-emitted `RequestInfoEvent`，或在恢复调用中提交响应；重发沿用原 `request_id`，不能复制成新审批。
   - 到期时以持久定时器触发 `TimedOut`，再升级或创建显式 successor request；迟到响应先查状态，默认返回“已超时/已替代”而不推进旧流程。
   - 发布、扣款、发信、写病历等动作使用由 `run_id + request_id + action` 派生的幂等键，或用 outbox/补偿；记录 request、决定者、版本、转换和动作结果。
   - **完成标准**：恢复重放只产生一个逻辑 pending request；timeout 与 response 竞态有确定胜者；迟到批准不能绕过升级后的新审批者或对象版本。发出后崩溃、响应重复、批准后外部成功但 checkpoint 未落盘等测试全部通过，外部副作用至多产生一个业务效果或可被可靠补偿。

---

## B — 边界（Boundary）★

### 不要在以下情况使用

- 只是决定某个工具是否高风险、是否该要求审批：调用 `choose-codeact-or-direct-tools-by-risk`，不要先设计等待状态机。
- 只是判断标准 checkpoint 还是跨 worker Durable Task：调用 `choose-workflow-recovery-layer`；本 skill 不替代故障域选型。
- 一个短暂、可取消、无恢复需求的本地确认，断线后从头重做也完全安全：同步确认更简单。
- 想用“有人批准了”替代服务端授权、输入校验、对象版本检查或副作用幂等：审批不是这些控制的替代品。

### 真实反例与失败模式

- **普通工具默认无审批（ce15）**：注册写操作不代表框架会自动询问；必须显式包装 approval-required tool 或建立 RequestPort。
- **CodeAct 吞掉逐操作审批（ce14）**：一次批准 `execute_code` 可能包含多个敏感动作，操作员无法分别拒绝；需逐项可见的动作保留 direct tools。
- **把 checkpoint 当 exactly-once（ce25）**：批准后外部系统已写入，但 superstep checkpoint 前崩溃，恢复会重放；必须有业务幂等键/outbox/补偿。
- **只靠浏览器 pending**：页面刷新或 SSE 断开后请求消失，Workflow 却仍在等待；服务端无法恢复或审计。
- **correlation ID 当授权**：拿到链接或 ID 的人即可批准，造成越权；响应入口必须重新认证并按 tenant/对象授权。
- **迟到批准复活旧请求**：超时升级或对象已更新后仍接受旧批准，绕过新审查和版本控制。

### 作者的盲点 / 时代与版本局限

- 官方 c12 与 c16 主要展示 happy path，没有完整示范多审批者竞态、撤销、替代请求、迟到响应和业务幂等；这些是从恢复语义与反例推导出的生产必需项。
- 标准 Workflow 的 pending request checkpoint 与 Durable external event 处于不同故障域；“可恢复请求”不自动证明能跨进程/worker，必须另做 v13 选型。
- C#、Python、Go 的 RequestPort、tool approval 与 Durable API 形态和成熟度不对称；实施前应核对当前官方文档和包版本。
- 文档强调等待期间不占计算，但通知可靠性、审批队列运营、值班交接和合规留痕仍由应用方设计。

---

## 相关 skills

- `depends-on` [`design-or-migrate-typed-agent-workflows`](../design-or-migrate-typed-agent-workflows/SKILL.md)：可恢复人审建立在显式 Workflow 的 typed Request/Response 与暂停边界上。
- 与 [`choose-workflow-recovery-layer`](../choose-workflow-recovery-layer/SKILL.md) `composes-with`：本 skill 定义 Pending 状态机；后者按故障域决定这些状态由标准 checkpoint 还是 Durable Task 承载。

---

## 审计信息

- **验证通过**：V1 ✓ / V2 ✓ / V3 ✓
- **证据单元**：f18、p25；案例 c12、c16、c21；反例 ce14、ce15、ce25；术语 g17、g18、g22
- **测试通过率**：100%（独立盲测；详见 [test-results.md](./test-results.md)）
- **蒸馏时间**：2026-07-22
