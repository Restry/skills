# 动态 Plan 驱动的 Agent Workflow 方案与工作包拆解

适用于这类架构讨论：用户需求高度变化，但最终交付物有固定契约；方案需要先由用户 Review，再派执行 Agent 开工。

## 核心建模

不要把用户的具体诉求（换 Logo、换颜色、局部重做等）提前写成多个固定场景或固定 Workflow。产品入口只保留少量稳定的业务类型，具体需求通过对话收集。

推荐链路：

1. **Harness 收集需求**：无论业务类型，都先多轮对话、读取附件、补齐缺项。
2. **需求卡片确认**：把事实、目标、保留项、可修改项、附件和待确认项结构化；用户确认后冻结版本。
3. **Harness 生成 PlanSpec**：输出任务、依赖、并行组、Skill 提示、Tool 白名单、交付物类型和验收标准。
4. **Plan Validator**：先做确定性结构与业务完整性校验，不合格则返回结构化错误给 Harness 修正。
5. **Functional Workflow 执行**：用稳定代码解释动态 Plan，通过条件、循环、并行、Step 与 checkpoint 执行。
6. **确定性交付 Gate**：固定输出契约不能由 Planner 取消；只有所有产物真实存在并通过校验才发布。

准确术语是“**动态 Plan 驱动的 Functional Workflow**”，不是“LLM 每次生成并执行新的 Python Workflow 代码”。

## PlanSpec 最低质量要求

每个任务至少包含：

- 稳定任务 ID
- objective
- inputs
- dependsOn
- parallelGroup（可选）
- skillHints
- allowedTools
- deliverableType / requiredFields
- acceptanceCriteria

Plan Validator 至少检查：

- ID 唯一、依赖存在、无循环
- 输入输出类型可衔接
- 并行关系安全
- Skill 与 Tool 属于激活版本和白名单
- 固定交付目标可达
- 必须任务未被 Planner 省略

Plan 通过后必须保存为不可变版本。checkpoint 恢复使用同一 Plan；需求变化时创建 Plan v2 或 Amendment，不得静默重排旧 Plan。

## 质量责任边界

- 需求卡片决定“理解是否准确”。
- Plan 决定“是否做对事情、顺序是否正确”。
- Functional Workflow 决定“是否按计划稳定执行和恢复”。
- Skills 决定“专业方法是否合格”。
- Tools 决定“真实动作是否成功”。
- Gate 决定“错误产物能否被拦住”。

Todo 完成、模型声明完成或 LLM Judge 单独通过，都不能替代确定性产物验收。

## Review-first 工作包拆解

架构方案确认后，不要立刻给执行 Agent 一条大任务。先把工作包加入 HTML 供用户 Review。推荐顺序：

- WP0：技术探针与 Stop / Go
- WP1：领域契约与持久化
- WP2：需求收集与确认卡片
- WP3：动态 Planner 与 Plan Validator
- WP4：Functional Workflow 执行引擎
- WP5：Skills、Tools 与版本治理
- WP6：固定交付物与最终 Gate
- WP7：用户区与管理区
- WP8：DevUI、可观察性与真实 E2E

每个工作包必须写清：目标、交付物、依赖、估算、验收、停止条件（如适用）。

## 派活纪律

1. 先发布“架构 + 工作包”HTML，并明确标记“尚未派发”。
2. 用户 Review 通过后，只先派 WP0。
3. WP0 需要真实运行证据；核心组合能力不通则停止后续完整建设。
4. 每个工作包验收后再派下一个，避免一次性大改掩盖架构偏差。
5. 给执行 Agent 的提示使用业务目标、规则和验收语言；不要替它指定文件、函数、表名和行号。

## CC MCP 编排建议

当用户明确要求“用 CC MCP 后台干活、支持并行，但先把方案 Review 完”时，方案 HTML 应增加一小块协作说明：

1. **最小任务闭环**：`mcp__cc__claude_run` 派出 → 立即 `status` 防早夭 → 运行中用 `status` 或 `wait(from_seq)` → 同工作包续轮传 `session_id` → 新会话独立验真。
2. **主实现通道**：一次只派一个可独立验收的工作包；同一工作树保持单写者。
3. **并行只读 Review**：工作包完成后，默认可并行三路新会话做战略对齐、行为验收、健壮性/安全检查；均只读且不继承主实现上下文。
4. **隔离开发通道**：只有契约冻结且任务真正独立时，才允许在独立 worktree 并行写；禁止同一 `session_id` 并发 resume，禁止多个写任务共享 worktree。
5. **完成证据**：CC 自报不算完成；必须复核工作树、构建/测试、真实用户路径/API/数据、UI 截图与独立 reviewer 结论。
6. **Review 与 Fix 分离**：先把 review verdict 给用户，用户确认后再派修复或下一包。

HTML 中建议画出“派出任务 → 确认启动 → 后台执行 → 连续续轮 → 独立验真”五步，并列出主要 MCP 工具及其角色。公开页面不要放 chat_id、凭据、内部端口或绝对私有路径。

## HTML 呈现建议

- 架构基线保留为 v1；加入大量工作包时发布 v2，避免破坏原始决策快照。
- 工作包章节先放摘要数字和依赖图，再放任务卡。
- 任务卡统一字段，Owner / 时长 / 依赖做轻量 pill。
- 最后列出 4-6 个“派发前确认点”，让用户能直接 Review 范围、契约、风险和派发顺序。
- 数量与总估算必须从任务卡现算，不能凭印象填写。