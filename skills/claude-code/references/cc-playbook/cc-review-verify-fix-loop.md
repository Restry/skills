---
name: cc-review-verify-fix-loop
description: 派 CC 做完 code review 后，**先派独立 CC 实证验证**每条 P0/P1 是真问题还是静态分析脑补，再派 CC 修。三段式：review → verify → fix。用于任何 CC review 输出的 bug 清单，特别是涉及 DB 约束、并发竞态、隐私串台这种"读代码以为有问题"高发场景。
---

# CC Review → Verify → Fix 三段式

## 何时用
- CC code review 给出一堆 P0/P1 bug 清单
- 用户/爸爸问"这些都是真的吗？"
- 准备进入修复阶段，担心修了误报浪费时间或漏修真问题
- review 涉及 DB 约束 / 并发 / 隐私 / 协议这种"可能被别处兜底"的领域

## 核心：static analysis ≠ 真实 bug
CC review 是看代码推理，常见误报模式：
- "这里没去重" → 实际上层有去重
- "字符串 substring(7) 只剩 0-4 字符" → 实际 5-7 字符（脑内算错）
- "fanOut 会广播给所有 sink" → 实际 fanOut 有过滤，但**部分场景**确实会
- "性能瓶颈 P1" → 实际未 await 不阻塞

实证一次：**0 完全误报，但 3/9 描述不准/严重程度夸大**。误报率不高，但盲修会浪费 ROI。

## 流程

### Step 1: 派 review
派 CC 做专项 code review。**限定范围**（不要泛泛），输出标准格式（P0/P1/P2 + 文件:行号 + 触发场景 + 严重程度 + 建议修法，不要写代码）。强制不超过 1500 字。

### Step 2: 派**独立 CC** 实证验证
关键：**不要让 review 那个 CC 自己验**，要起新 CC。任务模板：

```
对 review 报告中每个 P0/P1，独立验证：
1. 读完整上下文（周围 50 行），确认没被别处兜底
2. 构造能复现的最小测试（Node 脚本/curl/SQL 查询）
3. 必要时直接查 DB / 跑真实环境
4. 判定：真 / 假 / 部分真（写明哪里描述不准）

禁止：重新做 review、修复 bug、用 puppeteer/mock。
输出表格：ID | 原结论 | 验证结果 | 复现证据 | 备注
最后给 ROI 重排的修复优先级。
```

### Step 3: 派 CC 按 ROI 修
基于**验证后**的优先级（不是 review 原始优先级）派 CC 修。Prompt 必须包含：
- 每个 fix 的真实根因（从 verify 报告取，不要再让 CC 重新分析）
- 每个 fix 的真实严重程度（部分真的要改 prompt 反映窄场景）
- 每个 fix 的回归测试要求
- 修完真实环境端到端验证（不要 mock）

## 关键反模式
- ❌ Review 完直接派修 → 修了误报浪费 token + 引入新 bug
- ❌ Review 那个 CC 自己验自己 → 一致性偏差，发现不了脑补
- ❌ Verify 阶段允许"读代码觉得没问题就当假" → 必须有实证（DB 查询 / 复现脚本）
- ❌ Verify 报告写"P0-1 假" 没解释为什么 → 必须写"被 X 机制兜底"或"实测输出 Y"

## 验证证据模板（verify CC 必须给）
- DB 类问题 → `select` 查询 + 真实输出
- 并发类问题 → 复现脚本 + 真实运行 log
- 协议类问题 → curl/wscat + 真实响应
- 性能类问题 → 真实 latency 数据 + 是否在 hot path

## 实战教训
- Review 报告"P2-3 substring 只剩 0-4 字符" → verify 实测 5-7 字符 → **回头 review 报告全面打分**
- Review 报告"P0-2 群发串台" → verify 发现真实危害是"覆盖 DOA"而非"群发" → 修法不同（去重 vs 隔离 sink）
- Verify 阶段经常发现 review **方向对、细节错** → fix prompt 要按 verify 报告写，别照抄 review

## 何时跳过
- 改动只有 1-2 行简单 lint/typo 修复
- review 全是 P2 风格建议（无正确性问题）
- 时间紧迫且爸爸明确说"先修了再说"
