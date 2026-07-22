---
name: html-report-anthropic-warm
description: HTML 报告、项目分析、架构图、流程图、PR review、方案对比、时间线、仪表盘与体验草图的唯一入口。以 Anthropic 暖色报告工艺为母体，按轻量草图、结构化可视化、正式报告三档输出；多维内容必须提供有意义的内联 JavaScript 交互，如筛选、展开、视图切换、搜索或对比，而不是只做静态长页。
version: 2.0.0
metadata:
  hermes:
    tags: [html, report, design, anthropic, visualization, interactive]
    related_skills: [claude-design, popular-web-designs, publish-html]
---

# Dad 的 HTML 报告标准工艺

## 唯一入口与三档模式

本 skill 已吸收原 `html-artifact-output` 与 `html-visualizer`。不要再加载另外两个近义入口；所有 HTML 交付先在这里选择主模式：

| 用户意图 | 主模式 | 默认形态 |
|---|---|---|
| “草图 / 看看体验 / 一起拍板 / 示意一下” | **轻量草图** | 1 页、1–3 个核心 mock 或 before/after；不堆满规格章节 |
| 对比、模块图、流程、PR review、时间线、看板等关系型内容 | **结构化可视化** | 匹配信息形状的 grid / timeline / annotated diff / inline SVG，并提供探索交互 |
| “正式报告 / 管理层总结 / 项目分析 / 性能报告 / 完整介绍” | **Anthropic 暖色正式报告** | Hero + 真实 KPI + 分节叙事 + 图表 + 交互 + 浏览器/vision 收口 |

冲突时：草图语义优先于“报告”字样；正式管理层报告是主容器，内部模块图使用结构化可视化；用户明确要 Markdown、纯文本、代码或 Mermaid 时遵循用户格式，不强制 HTML。

## 交互是 HTML 的核心，不是装饰

当页面包含多个时间点、项目、状态、方案或证据层级时，**只做锚点导航和静态卡片不算完成**。至少选择一种能降低认知负担的真实交互；正式报告和多维可视化通常应组合 2–4 种：

- **筛选**：按项目、状态、日期、风险或负责人过滤；
- **视图切换**：总览 / 时间线 / 项目 / 决策，或图 / 表 / 明细；
- **展开与抽屉**：卡片点击查看证据、结果、下一步；
- **搜索 / 排序**：条目较多时提供关键词、优先级或日期排序；
- **对比切换**：before/after、方案 A/B/C、当前/目标；
- **状态联动**：KPI、筛选器和可见卡片数量同步更新；
- **URL 状态**：Tab 或视图写入 hash/query，刷新和分享后仍能回到同一状态。

交互必须满足：

1. Vanilla JavaScript 内联，不依赖构建工具；
2. 鼠标、键盘和触屏都能使用；
3. 有清晰 active / hover / focus 状态；
4. 页面关闭 JS 后核心事实仍可阅读；
5. 不为“动起来”而加无意义动画、轮播或 hover gimmick；
6. 浏览器验收必须真实点击非默认视图、筛选器和详情，并确认 Console 0 error。

轻量草图如果只有一个核心画面，可以不加交互；但必须明确这是有意保持轻量，而不是忘了 JavaScript。

## 触发条件

任一即触发,**默认走本工艺,不要自由发挥**:

- "用 html 把 X 表达出来"
- "做个 html 报告/介绍/总结/讲一下 Y"
- "性能报告"/"功能介绍页"/"项目总结"
- 任何要交付一个静态 HTML 文件展示信息的场景

## 🛑 反触发：用户问"体验/感觉/草图"时

Dad 明确表达过"看着都很头疼"。**不要把所有"画一下"请求都升级到 1620px Anthropic warm 工艺**。先判断意图：

| Dad 说什么 | 该做什么 | 不该做什么 |
|---|---|---|
| "做个 html 报告 / 性能报告 / 项目总结" | 全套 Anthropic warm 工艺 | — |
| "用 html 把 X 表达出来" | 全套工艺 | — |
| "**画个草图** / 想法看看效果" | 1 页轻量 HTML，1 列布局，无 SVG 流程图，无 SQLite schema 表，无多 section | 全套架构 spec |
| "**做好之后我的体验是啥样**" | 1 张 before/after 对照，2 屏内说完 | 7 个 section 完整架构稿 |
| "**给我看一下流程**" | 简单流程图 / 一段叙述 | 完整设计文档 |
| "随便给我个 mock" | sketch 风格，2-3 个简陋方案 | 单变体高质量收口 |

**踩过的坑**（2026-06-08，Watchtower 项目）：
- Dad 说"画一张完整草图，咱们一起拍板" → 我做了 25KB 7-section 报告（hero+决策矩阵+SVG泳道图+状态机表+SQLite schema+卡片预览+路线图+风险矩阵）+ headless 截图 + vision 2 轮复审 + i.dora 部署
- Dad 反馈："其实你说了这么多，我觉得看着都很头疼"
- **根因**：把所有 HTML 请求都"满规格执行"，没问"这是草图还是定稿"

**纪律**：要交付 HTML 时**先在心里跑一遍**：
1. Dad 说的是"草图/体验/想法" → **轻量模式**（800-1100px、1 column、纯散文+1-2 张卡 mock、无 SVG 流程图、无大量数据表）
2. Dad 说的是"报告/总结/介绍" → 全套工艺
3. 拿不准 → **先做轻量版给他看，再问"要不要展开"**，不要默认升级

**轻量模式骨架**（800-1100px、单列、Anthropic 暖色仍保留）：
- Hero 标题 + 1 句副文
- 1-3 个核心 mock / 对照块
- 1 段"一句话"收口
- 不要：SVG 流程图、状态机表、schema、风险矩阵、roadmap
- 不要：vision 多轮迭代（草图重 idea 不重像素完美）

## 🚫 反触发 — 草图 / 讨论阶段不走全套工艺

明确说"**草图 / 想法 / 讨论 / 聊聊 / 一起拍板 / 示意一下 / 随便画画**" + HTML 关键词时，**绝对不要默认走全套工艺**。这类语境下用户要的是\"我们一起看一眼对不对\"，不是\"出张成品\"。

| 触发词 | 该走法 |
|---|---|
| "你画一张草图" / "我们聊聊" / "讨论一下" / "一起拍板" | 单 HTML ≤ 5KB；跳过 vision critique 多轮、跳过 i.dora 部署、跳过飞书 MEDIA 三件套 |
| "用 html 把这个体验示意一下" / "随便画画" | 一页对比图或简单插画即可 |
| 头脑风暴 / grill 阶段的中间产物 | 不要全套渲染，markdown / 一句话回复也行 |
| 报告刚画完用户说"看着头疼/太复杂/简化" | **当场删 90% 重做**，不是迭代调整 — 用户已经在表达\"全套工艺不对路\" |

判定公式：
- 用户**话里有"草图/想法/讨论/拍板/示意/聊聊/随便"** + 当前对话**还在头脑风暴未拍板** + 你预估输出 < 5KB → 走简化路径
- 等 Dad 明确说"**开干 / 出方案 / 部署 / 正式做 / 上线 / 交付**"才走全套工艺

### 真踩 — 2026-06-08 Watchtower

Grill-me 6 轮拍板后 Dad 说"画一张完整草图，一起拍板"，我自动加载全套工艺：1620px + KPI grid + SVG 泳道 + 状态机表 + SQLite schema + 风险矩阵 + i.dora 部署 + headless 截图 + vision 复审 2 轮 + 飞书 MEDIA 三件套，**25KB HTML 干了 3KB markdown 能干完的事**。

Dad 原话："**我觉得看着都很头疼**"，"**为什么会这么费劲呢**"。

后续两次需求（UX 示意图 / 多任务场景图）改成单 HTML 截图 + 几个 anno block + 1-2 轮 vision，Dad 立刻说"清晰多了"。所以阶段不同 = 工艺不同：**讨论阶段 = 一张图说明问题，拍板阶段才上全套**。

每次接到含 "HTML" 关键词的请求，先自检 5 秒：现在是\"我们一起看\"还是\"出张正式的\"？看不准 → 用最少工艺试一版给用户看，等用户说\"再正式点\"再升级。**宁可两次小工艺，不要一次走全套被打回。**

## 必装技能依赖

加载本 skill 不等于必须出 1620px / KPI grid / SVG 泳道 / 状态机表 / 风险矩阵 / vision 多轮迭代 / i.dora 部署的全套。**先匹配用户实际诉求的 scope**,再决定走哪档工艺。

| Dad 的话 | 真实 scope | 该出什么 |
|---|---|---|
| "聊聊 / 头脑风暴 / 想法" | 对话 / 探讨 | 文字 + 卡片,不出 HTML |
| "画个草图 / 一起拍板再写代码" | **轻量示意** | 1 张 HTML(单 section · 几个框 · 一张流程图) · 不超 5KB · 不 vision |
| "出个体验示意 / 给我看看用了之后什么样" | **UX 对照**(不是架构) | 2 列 phone mock · 一两段感受 · **绝不画系统架构** |
| "做个完整报告 / 项目总结 / 性能分析 / 介绍页" | 完整交付物 | 走全套 5 步工艺 + vision 迭代 |
| "出 PRD / 实施计划" | 文档 | markdown 即可,不要 HTML(Dad 用 IDE 看 .md) |

**踩过的坑(2026-06-08 Watchtower 项目)**:Dad 说"画一张完整草图,一起拍板再写代码",我加载本 skill 后**满规格执行** — 出了 1620px 7-section 25KB 的架构 spec(hero + 决策表 + SVG 泳道 + 状态机表 + SQLite schema + 路线图 + 风险矩阵 + i.dora 部署 + vision 2 轮 + 飞书 MEDIA 三件套)。Dad 反问"为什么这么费劲" + "我只想知道用了之后是什么样的体验" — 说明:① 草图档应该出 5KB 的轻量示意,不是 25KB 的甲方 proposal;② **\"架构\" ≠ \"体验\"** — 我画的是给工程师看的架构,Dad 想看的是给用户看的体验(同一个项目至少要分两张图:UX 示意 + 系统架构,二者**不能合一**)。

### Scope 不清楚就反问,不要默认走最重

如果用户的措辞落在「草图 / 示意 / 看看 / 想法 / 头脑风暴 / 拍板」这些**探讨语义**的词上,**先确认范围再开工**:"草图档(单 HTML 5 个框,5 分钟出) 还是完整稿(全套工艺 30 分钟出)?" — 一句话 clarify 比白干 30 分钟好。

落在「报告 / 总结 / 分析 / 介绍 / 性能」这些**交付语义**的词上,默认走全套。

### "体验 / UX" 类需求是独立档,不要混进架构图

当 Dad 问"用了之后是什么体验" / "用户看到啥" / "感受是啥",**禁止画**:
- ❌ 系统架构 / 数据流 SVG
- ❌ 状态机表 / SQLite schema
- ❌ 部署方案 / 风险矩阵
- ❌ 路线图 / Phase 1/2/3

**只画**:
- ✅ 手机/浏览器 mock 截图(对照"现在 vs 装了之后")
- ✅ 短句心情("看着 60 条 vs 看一眼绿色卡片")
- ✅ TLDR 一句话 punchline
- ✅ Persona / 用户视角的 before-after

体验图最多 1 屏 + 1 个对照 + 1 个 TLDR,**不超 16KB**。如果你的体验图开始出现"sender_id"/"task_id"/"cron"这类工程词,你在画错档。

## 必装技能依赖

| 信号 | 处理 |
|---|---|
| "草图"/"聊聊"/"想法"/"画给我看看"/"先看看"/"差不多就行" | **轻量交付**：单 section、800px 内、可无 header、不调 vision critique、不部署 i.dora（除非用户后续要"发出来"） |
| 用户在 brainstorming（还没拍板做不做） | 同上轻量。**宁可分两步交付**：先 3-5 句话 + 1 张草图 → 用户拍板 → 再升级到完整报告 |
| 用户问"对我什么体验"/"我用这个会看到啥" | 见下节"受众视角选择"——这是 UX mock 题，不是架构报告题 |

**症状你做过头了**：
- 用户说"看着都很头疼" / "为什么这么费劲" / "我只想知道 X" / "怎么跟我理解的有点差别"
- 输出已经 25K+ chars 还没拿到用户反馈
- 一口气堆了 5+ section + KPI grid + SVG 图 + 状态表 + 风险矩阵 + 路线图

立刻收：回到 3-5 句话的核心 + 1 张图。**满规格执行 ≠ 高质量交付**——给用户头疼是 0 分而不是负分。Dad 2026-06-08 实战教训：watchtower 第一版照本宣科出了 7 section 架构报告，Dad 当场说"看着头疼"。

## 🎯 受众视角选择：用户视角 vs 建造者视角

报告主题是"一个东西 / 系统 / 工具 / 功能"时，先问自己：**用户想看什么视角？**

| 用户问法 | 该画什么 | 不要画 |
|---|---|---|
| "做完之后对我什么体验" / "我用这个是啥感觉" / "我会看到啥" | **用户视角 UX mock**（手机/界面 mock + before/after + 用户感受 emoji + TLDR） | 架构图 / 数据流 / 状态机 / SQLite schema |
| "怎么实现" / "架构怎么样" / "技术方案" / "怎么搭" | 架构图 / 数据流 / 状态机 / 路线图 / schema | 用户界面 mock |
| "做完是啥样" / "demo 一下" | UX mock 为主 + 1 段技术说明兜底 | 一上来就讲实现细节 |
| 没明说 | **默认用户视角**。跟 Dad memory 里"汇报：业务语言 / 禁黑话 / 禁 PR 号 / 禁文件名"一脉相承 |

**UX mock 标准模式**（已实战验证好用，2026-06-08 watchtower）：phone mock + before/after 双栏 + tag pill（现在红 / 之后绿）+ 感受 block（emoji + 引号 punchline + 解释）+ TLDR 收尾。详见 `references/ux-mockup-pattern.md`。

**自检**：要画的内容里数一下"用户看得见的东西" vs "系统内部的东西"。**只要 ≥ 1 个是 schema / state machine / API / cron 这种"用户看不见的"，先问自己"用户问的是体验还是实现"**——问体验就别画那些。

## 必装技能依赖

```
creative/claude-design  # 必装 — 工艺纪律:context→system→variant→verify
```

加载:`skill_view('claude-design')` 看流程 + 反 AI slop 红线。

**可选参考**:`creative/popular-web-designs/templates/claude.md` — 原始 Anthropic tokens 来源。**本 skill 已内嵌完整 tokens**(下面"强制约束 · 色板/字体"节),不装也能跑。只在想看 popular-web-designs 完整 catalog 或对比别的 brand 模板时加载。

## 强制约束

| 维度 | 必做 | 禁做 |
|---|---|---|
| 色板 | Anthropic 暖色:`#f5f4ed` parchment + `#c96442` terracotta + `#6a8e4e` sage + `#faf9f5` ivory | 暗色 / Linear 黑 / 终端绿 / 玻璃拟态 / 渐变滥用 |
| 字体 | `Source Serif 4` 标题 weight 500 + `Inter` body + `JetBrains Mono` code | Anthropic Serif 是付费字体,只能用 Source Serif 4 替代 |
| 图标 | **inline SVG line icons**(24x24 viewBox, stroke=currentColor, stroke-width=1.5, fill=none, Lucide/Feather 风格) | **彩色 emoji**(🎒 ✂️ 🤖 🎨 等),违者 Dad 立即否 |
| 宽度 | **1620px** 主容器(Dad 大屏看) | 1080 / 1280 太窄 |
| 变体 | **单变体收口**(不再 A/B/C spam) | 多版本对比浪费时间 |
| 验证 | headless chrome 截图 → `vision_analyze` critique 2-3 轮 | 写完就交付 |
| 数据 | 真实测量、能跑出来的数字 | 编造、约数、"大约几百" |

## 工作流程(5 步)

### 1. 数据准备

把要展示的数据先全部跑出来,**写到 `/tmp/*.json` 文件**,不要边写 HTML 边算。

实测优先 — 比如折叠 token 数字就跑 prompt_builder 真测,不要拍脑袋估算。

**🚨 数据新鲜度自检(必做)** — 如果你正在画"系统当前状态"类报告(skill 清单、PR 列表、文件统计、folder 状态、配置盘点),**绝对不要复用上次会话的 `/tmp/*.json` 缓存**:

- 数据源现在可能已变(skill 增删了 / PR 合了 / 文件移了)
- Dad 的直觉很准 —— "我怎么感觉太少了" 这种问句出现就是数据已经过期
- **重新跑实时探测**,即便上一会话刚跑过

自检清单(画前确认):
1. 数据源是否在本会话刚生成?如果不是 → 重跑
2. 你能不能跑一个 1-line 命令验证总数和报告里的数字一致?(`find ~/.hermes/skills -name SKILL.md | wc -l` 对应 "N skills")
3. 报告里出现的"分类列表"是否和 `skills_list()` 当前输出一致?

如果三项有任何一项答不上来,先重新跑数据。一份数字对不上的报告,Dad 五秒内识破,**比晚交付十分钟还伤信任**。

### 2. 加载工艺技能

```python
skill_view('claude-design')  # 流程 + 反 AI slop 纪律
skill_view('popular-web-designs', 'templates/claude.md')  # design tokens
```

### 3. 单变体高质量 HTML

骨架:

```html
<!doctype html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1620, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #f5f4ed;       /* parchment */
    --surface: #faf9f5;  /* ivory card */
    --surface-2: #ffffff;
    --sand: #e8e6dc;
    --border: #f0eee6;
    --border-warm: #e8e6dc;
    --ink: #141413;       /* warm near-black */
    --text: #4d4c48;
    --text-2: #5e5d59;
    --text-3: #87867f;
    --brand: #c96442;     /* terracotta */
    --brand-2: #d97757;
    --sage: #6a8e4e;
    --crimson: #b53333;
  }
  body { min-width: 1620px; background: var(--bg); font-family: 'Inter', system-ui, sans-serif; }
  .wrap { max-width: 1620px; margin: 0 auto; padding: 80px 72px 96px; }
  h1, h2, h3, .serif { font-family: 'Source Serif 4', Georgia, serif; font-weight: 500; }
  .mono { font-family: 'JetBrains Mono', monospace; }
</style>
</head>
<body><div class="wrap">
  <!-- hero · sections · cards · footer -->
</div></body>
</html>
```

布局模式(已验证好用):

- **Hero**:左大标题(Source Serif 4 · 56-72px · -0.02em letter-spacing)+ 右 2×2 KPI grid
- **Section**:`sec-num`(mono · uppercase · brand color) + h2(serif 44px) + lede(17px 76ch max)
- **Dashboard cards**:`grid-template-columns: repeat(4, 1fr); gap: 20px` + `border-radius: 16px` + `box-shadow: 0 0 0 1px var(--border-warm)` ring shadow
- **Hero metric**:`grid-column: span 2` + 88px 大数字
- **Compare strip**:before/after 两栏 + 中间橙色 → 箭头
- **Money cells**:`border-left: 3px solid var(--sage)` 强调正面收益
- **交互卡片**:click 展开 drawer 显示明细(SKILL_DATA 内嵌 JSON,vanilla JS)
- **流程图**:inline SVG + `<marker>` 箭头,纯文字节点不画图标
- **Persona / 画像 grid**(4×2 八卡):每张卡 `emoji 28px → h3 Source Serif 19px → p 13px line-height 1.65 min-height 100px → tag chips`,tag 是圆角胶囊 mono 11px,warn 类用 crimson rgba 8% bg。适合"机器是谁 / 项目画像 / 角色卡"类内容
- **Long-text inline display**(memory/persona/原文清单类):**禁用 drawer/preview-only 模式**。用 `mem-entry`:`grid 26px+1fr+100px+200px` head(icon + title + char count + relative bar)+ 完整原文 block(JetBrains Mono 13.5px / line-height 1.7 / `white-space: pre-wrap` / bg `--bg`)。**bar 长度按"绝对字符数 / 全列最大字符数"算**,直观体现哪条最长

### 4. headless 截图 + 重试

```bash
google-chrome --headless --disable-gpu --no-sandbox \
  --window-size=1700,4000 --hide-scrollbars \
  --screenshot=/tmp/report.png \
  file:///home/resley/report.html
```

宽度:`window-size width` 比 body min-width 多 80px(留滚动条余地)。
高度:**预估 + 50% headroom**,首截若 footer 缺失 → **直接翻倍重截**(浪费字节比浪费 round trip 便宜)。

### 5. Vision critique 2-3 轮

```python
vision_analyze('/tmp/report.png', question='这是 X 报告。检查 (1) 整体宽屏布局 (2) Hero 数字 (3) 各 section 元素重叠/截断/压字 (4) Footer 完整 (5) SVG 流程图压字。报告 P0+P1+noise。')
```

修 P0 → 重截 → 复审,直到 vision 返回"no hard issues"。

## 反 AI slop 红线

| 别做 | 为什么 |
|---|---|
| 编造 metrics / fake dashboard 数字 | Dad 一眼识破立刻不信任全篇 |
| 大段填充段落凑版面 | "every element must earn its place" |
| 通用 SaaS 卡片网格 + icon 阵 | 没有信息密度 = slop |
| 左边框 accent callout card | 烂大街 AI 设计陷阱 |
| 0 值 chip / 空行 grid | "为啥要折叠?" 立刻打脸 |
| 同行 3 EN + 1 ZH 标签 | 视觉破碎,统一一种语言 |
| 弧度太大圆角凑形 | Anthropic 是 ring shadow,不是圆角党 |

## 大文件防超时 / 防丢参

HTML 60K+ chars **主 agent 自己 read→write**,**别派 delegate_task**(易 600s 超时,产物丢)。
SVG 内嵌大块也算 — 用 `<svg viewBox>` 让浏览器自伸缩,源码尽量精简。

**🚨 write_file dropped-arg trap**(2026-06-08 实战踩坑两次): 写超大 HTML(>30K chars)时 `write_file` 调用偶尔会**只传 `path` 不传 `content`** — Hermes 直接拦下报 `"missing required field 'content' — almost always a dropped-arg bug under context pressure"`。**不是工具坏,是你自己的 tool call 在 context 重压下丢了参数**。

Recovery pattern(无 execute_code 兜底场景):
1. **先 `write_file` 一个小骨架** — 完整 HTML5 框架 + style + 空 `<div class="wrap">` + `</body></html>`,只有 base structure 没内容,通常 5-15K chars
2. **然后用 `patch` 工具逐 section 塞内容** — `old_string` 锁 `</div>\n</body>` 或上一个 section 的 END marker,`new_string` 加新 section + 重新闭合
3. 每次 patch payload 限在 10-20K chars 以内,丢参概率几乎为零
4. section 用 `<!-- BEGIN: NAME --> ... <!-- END: NAME -->` 注释边界 — 既符合本 skill 的 section markers 规范,又方便后续 patch 定位

**适用阈值**:单次 write content > 30K chars 且 context 已经累计了 ≥ 50K tokens(长会话 + 多 skill load)。短会话第一次 write 大概率没事,但有疑虑就走 skeleton+patch。

### 🚨 主 agent 自己 write 也会出事:dropped-arg under context pressure

发生场景:会话已积累 ~80K+ token 上下文 + 你正要 `write_file(path=..., content=<60K HTML>)` 一次梭出。**content 字段会被静默吞掉**,Hermes 立刻拦下:

```
write_file: missing required field 'content'. ... this is almost always a
dropped-arg bug under context pressure. Re-emit the tool call with the full
content payload, or use execute_code with hermes_tools.write_file() for very large files.
```

这不是 Hermes 坏了,是模型在巨长参数列表里直接漏写了字段。recover 路径两条:

| 方案 | 何时用 |
|---|---|
| **A. 重新 emit `write_file` 把 content 真填上** | 偶发一次,内容已经在脑子里 |
| **B. 改走 `execute_code` + `hermes_tools.write_file(path, content)`** | 反复掉 / 内容 > 50K / 想顺便做模板插值 |

**预防式拆分**(更稳):写 60K+ HTML 时,**先 `write_file` 写骨架 + 占位注释 `<!-- SECTION-XX placeholder -->`**(< 5K),然后**逐 section `patch` 把占位换成真内容**(每次 patch 也别太大,8-15K 一段)。这样既绕开 dropped-arg、又借 marker 边界天然适配 form ① 的后续迭代。

**别把这当 \"工具坏了\" 写进 memory** —— 这是上下文压力下的概率事件,环境恢复(新会话 / context 清掉)就没了。是\"写 HTML 时的工艺选择\",所以归在本 skill。

历史触发(2026-06-08): grill 多轮后准备出 watchtower 架构图,直接 `write_file(path='/home/resley/watchtower-design.html')` 单 call 一气呵成 → content 没了 → Hermes 拦截。当时正确做法应是先写骨架。

## 验证

每次交付前发 MEDIA: 给 Dad **两个**附件:
1. HTML 文件:`MEDIA:/home/resley/<name>.html`
2. 截图 PNG:`MEDIA:/tmp/<name>.png`

Dad 在 Feishu 上能直接看截图,点 HTML 在浏览器开。

## 🏗️ 架构选择:单 HTML / 多页 / Python build(按复杂度递增)

**Dad 的默认偏好**:**单 HTML 文件,section 边界用 HTML 注释标记**。能改就直接 patch HTML,不要搞 Python build 系统(2026-06-05 Dad 明令:"我之前说让你分模块,只是让你分 HTML 的模块,不是让你分成这种编译式的。现在改一个东西特别费劲")。

### 选择矩阵

| 形态 | 何时用 | 怎么改 |
|---|---|---|
| **① 单 HTML(section markers)** | **默认** — 几乎所有场景 | 直接 `patch` HTML 文件,标记定位 section 范围 |
| **② 两页 / 多页 + sticky nav** | 单页太长(>100KB)、内容自然分组(精华 vs 细节)、Dad 嫌"一页太重"或主动提"拆两个页面" | 共用 `<head>` / nav css / footer;每页有完整 hero;详见 `references/multi-page-split-recipe.md` |
| **③ Python build 系统**(`sections/*.py` + `build.py`) | **几乎从不** — 只有当 Dad 明确说"以后会频繁迭代,且 section 数 ≥ 8 + 每个 section 内容超复杂"才考虑 | 编辑 `sections/sXX.py` → `python3 build.py` → 部署 |

### 形态 ① 单 HTML + section markers(主力)

每个 section 用 HTML 注释包围:

```html
<!-- BEGIN: SECTION-00 -->
<section>...</section>
<!-- END: SECTION-00 -->

<!-- BEGIN: SECTION-01 -->
<section>...</section>
<!-- END: SECTION-01 -->
```

改一个 section 就用 `patch` 的 old_string/new_string 操作；`<!-- BEGIN: X -->` 到 `<!-- END: X -->` 是局部边界。改完仍按 `integration/publish-html` 的备份、临时上传、原子替换和公网验收流程发布。

加新 section:在合适位置插一对新 marker + 内容,就这样。

### 形态 ② 多页拆分(2026-06-05 引入)

单 HTML 长到 100KB+ 或 Dad 嫌一页太重时,拆 2-3 页 + sticky nav 互链。

**整体规则:**
- 每页都是**完整独立 HTML**(head + body + footer 都全)
- 共享同一 `<head>` 块、同一 nav CSS、同一 footer
- 每页都保留同一个 Hero(让用户从任何页进来都看到全局上下文)
- nav 用 `position: sticky; top: 16px; z-index: 50; backdrop-filter: blur(8px)` 让滚动时一直可见
- 当前页 tab 用品牌色 + 加粗 + box-shadow 高亮

**最低拆分粒度:2 页**(① 主体精华 / ② 细节深挖)。3 页以上要 Dad 明确要求,否则导航疲劳。

**部署文件名规则**:主页 `<name>.html`,详情页 `<name>-details.html`(或 `-data.html` / `-appendix.html`)。Dad 习惯从主页进。

详细脚手架:`skill_view('html-report-anthropic-warm', file_path='references/multi-page-split-recipe.md')`

### 形态 ③ Python build 系统(谨慎)

**Dad 明确不喜欢**。只在以下情况考虑:
- 报告 8+ 个 section,每个 section 内容超 200 行
- 真正需要 partial rebuild(改一段不重建其它)
- Dad 主动说"做个模板,以后好改"

走这条时必须在具体项目内建立并实跑自己的生成器；本合并 Skill 不附带未经验证的模块化脚手架。

**反面教训**(2026-06-05): 给一个 5-section / 100KB 的报告搞 Python build,Dad 说"改一个东西特别费劲" — 因为他要改的是单行文字,却得 `cd ~/skills-report && vim sections/sXX.py && python3 build.py && cp ...`,4 步操作做 1 行替换。**这种规模该单 HTML 直接 patch**。

### 数据驱动 persona / 画像类 section(任何形态都适用)

**画像 section 必须从数据反推,不要写主观描述**(避免 AI slop)。
角色字段 `{tier, icon, title, skill_count, text, cats:[], asks}`,数字和分类标签从当前分类清单(`skills_list()` 或 categories.json)实时反查。skill 数变了,画像数字自动同步。

## 📊 数据源选择(关键陷阱)

报告里的"总数"类数字(分类数 / skill 数 / 折叠数)**必须来自**该数字对应的**真实底层枚举**,不能复用之前 build 步骤过滤掉的子集:

| 你要报的数字 | 错误源 | 正确源 |
|---|---|---|
| "系统有 N 个分类" | `categories.json`(你之前 build 时已经过滤掉空壳/单 skill 等) | `find ~/.hermes/skills -maxdepth 1 -type d -not -name '.*'` 实时枚举 |
| "系统有 M 个 skill" | `categories.json` 累加 | `find -L ~/.hermes/skills -name SKILL.md -not -path '*/.archive/*' \| wc -l`(注意 `-L` 跟符号链接) |
| "实测 token 数" | 上次 build 缓存 | 直接调 `build_skills_system_prompt()` + `tiktoken.encoding_for_model('gpt-4').encode()` |

**categories.json 是渲染层的"展示子集"** — 它可能过滤掉空壳分类、apple 归档前的快照等。**真"系统状态"数字必须穿透到文件系统**。

具体到 Hermes skills 实测:`python3 -m venv` 之外要装 `tiktoken` 进 hermes-agent 自己的 venv 才能直接调 prompt_builder(`/home/resley/.hermes/hermes-agent/venv/bin/python -m ensurepip --default-pip && pip install tiktoken`)。

## 🔄 整体审计:一个数字变了,所有依赖它的地方都要查

当核心数字(分类数 / skill 数 / 折叠数 / token 节省 / 成本)改了一个,**整体扫一遍报告所有引用**,不要只改你想到的地方。

Dad 2026-06-05 原话:"归档了这么多东西,是不是还有别的章节也要更新啊?比如压缩的记忆可能压得更多了之类的,你要**整体来看**。"

**审计清单**(对每个变化的数字跑一遍):
```bash
# 单 HTML 形态
grep -n "<old_number>" ~/report.html | grep -v "^[^:]*:[0-9]*:[[:space:]]*//"  # 排除注释

# 模块化形态(若有)
grep -rn "<old_number>" sections/ data/meta.json
```

**典型陷阱位置**(数字常分散于这些地方,容易漏):
- `meta.json` lede(开头一段话引述了数字)
- `meta.json` hero KPI 4 格
- `meta.json` subtitle / footer_left / footer_right
- `s01` performance section 的 sec-sub 副标
- `s01` Before/After cmp-meta 描述
- `s02` SVG `<text>` 节点里的数字(流程图节点 token 数)
- `s03` coverage section 的 h2 标题(经常硬编码"N 个分类")
- 任何 CSS 内 `width: X%` 计算了百分比

漏一处 vision 一定抓到,白白多一轮迭代。**改前先 `grep` 列清单再批量改**。

## 📤 公网发布（唯一入口）

所有最终 HTML 加载 `integration/publish-html`，发布到：

`https://www.nexora.restry.cn/static/<project>/<name>.html`

必须按项目子目录归类；已有同主题默认覆盖 canonical URL。覆盖前远端备份，先上传临时文件再原子 `mv`，最后核对本地/远端 SHA-256、HTTP 200、标题和关键 section，并在真实公网页面点击非默认视图、筛选器和详情弹窗，Console 必须 0 error。

禁止继续发布到旧 i.dora 路径，也禁止新造发布脚本、Hook 或托管服务。

## 历史参考

2026-06-05 `~/skills-report/`(skills 折叠机制性能报告 v6 终版,模块化重构)— ~100KB 输出,5 个 section:
- Section 00 · MEMORY(long-text inline 模式,USER PROFILE 10 条 + MEMORY 8 条全文展示,带 char-count bar)
- Section 00B · MACHINE PERSONA(4×2 persona grid,身份/沟通风格/工作模式/技能栈/铁律/审美/家族/在线状态)
- Section 01 · 性能影响(perf grid / compare strip / money strip / bar chart / Lost-in-the-Middle 卡)
- Section 02 · 代码改动(3 改动卡 + 4 步 SVG 流程图)
- Section 03 · 完整覆盖(coverage 分布条 + 三子节:15 折叠 / 8 单 skill / 4 历史顶层 chip)

迭代经历: v1(drawer-only memory cards)→ Dad 驳"展示太少" → v2(full inline) + 加 persona section。期间 4 次数据修正(skill 数据陈旧 / mlops/research 折叠反负收益 / 顶层 skill 挪入分类)。

## 支持文件

- `references/hermes-internals-data-probes.md` — Hermes 系统类报告的实时数据探针
- `references/multi-page-split-recipe.md` / `references/multi-page-merge-recipe.md` — 多页拆分与合并
- `references/ux-mockup-pattern.md` — 用户视角 UX mock
- `references/layout-pattern-playbook.md` — module map、annotated diff、comparison、timeline 等结构化模式
- `references/implementation-plan-html-recipe.md` — 可派活实施方案
- `references/project-architecture-report-recipe.md` — 项目架构报告
- `references/dynamic-plan-driven-agent-workflow.md` — 动态 Agent Workflow 方案
- `references/hub-edge-worker-product-pattern.md` — Hub / Edge / Worker 拓扑
- `references/conversation-to-architecture-baseline.md` — 多轮对话收敛为架构基线
- `references/conversation-to-product-plan-html.md` — 多轮对话收敛为产品执行方案

## Pitfalls(实战教训)

- **不要先开始写 HTML 才想数据** — 数据齐了再动手,否则会一边写一边返工
- **🚨 不要复用上次会话的 `/tmp/*.json` 数据快照** — 状态类报告必须实时重跑,Dad "我怎么感觉太少了" = 数据过期信号
- **"我怎么感觉太少了" 信号的两种含义** — (a) 数据**陈旧**:复用了旧缓存 → 重跑数据源;(b) 数据**枚举不全**:跑的探测命令只覆盖了一部分(比如只列了 `collapsed: true` 的分类却没列全部分类) → **检查枚举源是否覆盖完整**。具体到 hermes skills:`skills_list()` 是完整源,`find ~/.hermes/skills -mindepth 1 -maxdepth 1 -type d` 才是顶级真实分类清单,**不要只看你已经标记的子集**
- **drawer/preview-only 模式不适合"长期 context"展示** — Memory / USER PROFILE / 角色画像 / 原文清单类内容,Dad 期望**全文 inline 直接看到**,不是 preview + 点击展开。symptom:Dad 说"展示得太少"/"全部都展示出来"。Drawer 适合"分类列表 + 钻取子项"(skills_list 风格),不适合"我脑子里记着的东西"
- **bar 长度的最大值不要钉死 100%** — 用 max-saved scaling 让最长条铺满,其他按比例
- **vision 说"section X 看不见"先看截图够不够高** — 不是 bug,是截短了。判断:页面有 N 个 section 估 N×800px,加 40% headroom。失败两次必须翻倍。**第三次失败 / 切段后仍报缺失** → 用 `browser_navigate(file://...)` 读 accessibility snapshot,DOM 里能看到 section 标题(h2/h3 都列出来)就说明 HTML 是对的,vision 只是切错了。**不要因为 vision 三次报"缺失"就跑去改 HTML 数据**(2026-06-05 险些把 ③ 顶层 SKILL.md 子节删掉,实际只是 PNG 切到 9000px 把它压在了交界处)
- **drawer 内 JSON 用 `</` → `<\/` 转义** — 否则 `</script>` 提前关闭脚本块
- **memory 满载时把工艺写成 skill,memory 只留一行 trigger 指向 skill** — 单条 memory 不够装完整 SOP
- **bulk-folding 前先实测一遍 delta** — 长 cat_desc(>120 字)+ 单 skill 分类,折叠后 1 行 summary 比展开 2 行还长。规则:n_skills × short_skill_line < cat_desc_len + boilerplate(~80字)就不要折。具体做法看下面"折叠收益预测"小节
- **vision_analyze 拒收 > 8000px 图** — 用 Pillow 切多段: `python3.10 -c "from PIL import Image; img=Image.open('x.png'); img.crop((0,0,1700,4500)).save('top.png'); img.crop((0,4000,1700,7900)).save('bot.png')"`。**段间必须重叠 ≥ 500px**(`crop(0,0,1700,4500)` + `crop(0,4000,...)` = 500px 重叠),否则 section 标题或卡片会刚好切在两段交界处,vision 在两段里都看不全那个 section 就误报"缺失"(2026-06-05 触发 3 次)。3500-4500px 段长是甜区。注意 host 的 pip 可能装到 python3.10 而 `python3` 是 3.11 — 用 `python3.10` 直接调,别盯着 `ModuleNotFoundError: No module named 'PIL'` 死磕 `pip install`(已经装了)
- **patch HTML 字面金额/数字时要带 HTML 上下文** — `'$1.82'` 字面 grep 匹配会失败,因为前面有 `</span>` 紧贴。用完整片段 `'<span class="pre">$</span>1.82'` 替换,patch 才能定位。所有 inline-`<span>` 包裹的数字都有这毛病
- **跨多数据修正后,口径要全场扫一遍** — 改了一个数字(如 16→15 折叠),后面所有依赖它的地方都要同步:hero KPI / section subtitle / coverage bar / 段落叙述文字 / flow diagram step / footer / sub-pill 计数 / DATA JSON。漏一处 Vision 一定抓到。建议改前先 `grep -n "16" file.html | grep -v css` 列清单
- **物理结构变了不要立刻删原区块** — 当系统状态变化(skill 挪走 / 分类合并 / 4 个顶层 SKILL.md → 全归类),报告里对应那块的处理顺序:① 加 "moved → 现归宿" 标记保留为**历史快照** + 副标改"已挪入分类 · 历史快照" + 数字归零(`0 cats now · 4 was`)+ count bar 改 0% width。② **不要直接整块删掉**(信息丢失,Dad 可能想看历史)。等下一份报告再用模块化清掉空块。这是 2026-06-05 处理 4 个顶层裸 skill 归类的方式
- **禁 emoji 用 line icon**(Dad 明确要求 2026-06-05) — 任何 emoji(🎒 ✂️ 🤖 🎨 🏢 ⚒️ 🎩 📋 🔬 🎬 🧰 🎯)都要换成 inline SVG line icon。建一个 `_icons.py` 装 SVG 库,每个图标 `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">...</svg>`,通过 `icon(name, size)` helper 注入。CSS `color: var(--brand)` 自动着色。**不要用 fill="currentColor"**(实心) — 必须 stroke-only,Vision 一眼看出区别。**例外**: memory 原文里 Dad 自己写的 emoji(比如"Reactions · emoji over text"内容里的 👍 ❤️ 😂)是引用内容,不算 UI 图标,保留
- **dingbats 也要换!**(2026-06-05 二次踩) — SVG `<text>` 节点里的 `✓` `✗` `⚠` `★` `→` `←` `↑` `↓` `♥` 这类 dingbat 字符(Unicode U+2700-27BF + 部分 U+2600-26FF)和 emoji 一个范畴,**Vision 一样把它们当 emoji 扣分**。具体场景:流程图节点底部 `<text>✓ done</text>` 这种最容易漏 — 看起来"才一个小钩子无害",但 stroke-only 报告里它就是异类。换成 inline SVG path,比如 checkmark:`<polyline points="0,4 4,8 12,0" fill="none" stroke="#6a8e4e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`。箭头用 `<marker>` + `<line>`。星号用 SVG path。**搜索清单别只搜彩色 emoji,要包含 dingbat range**
- **emoji 清扫的扫描公式**(强制最后一步) — 每次 `python3 build.py` 后跑一遍:
  ```python
  import re
  with open(OUT_PATH, encoding='utf-8') as f: html = f.read()
  # 1. 切掉原文引用区(memory + data desc),那里的 emoji 是引用不动
  for sec in ['SECTION-00', 'SECTION-03']:  # 按报告实际 section 名调整
      m = re.search(rf'<!-- BEGIN: {sec} -->(.*?)<!-- END: {sec} -->', html, re.DOTALL)
      if m: html = html.replace(m.group(1), '')
  # 2. 全 emoji + dingbat 范围扫
  hits = re.findall(r'[\U0001F300-\U0001F9FF\u2600-\u27BF]', html)
  assert len(hits) == 0, f'UI emoji 残留: {hits[:10]}'
  ```
  Vision 截图前先跑这个,本地零容忍。漏一个 Vision 一定抓到,白白多一轮迭代
- **模块化报告 OUT_PATH 改了别忘删旧文件** — `build.py` 顶部 `OUT_PATH = ...` 改了路径,旧位置的单体 HTML 不会自动消失,容易把 Dad 引到旧版本。模块化首次发布时 `rm` 掉旧 monolith 或重命名为 `_v6_monolith_backup.html`
- **改一个核心数字 → 全报告 grep 同步**(2026-06-05 Dad 原话:"你要整体来看") — 数字改了一处(分类数 / skill 数 / 折叠数 / token / 成本)别只改你想到的地方。改前 `grep -n "<old_number>" file.html` 列清单,改后再 grep 确认零残留。典型漏点:hero KPI / lede / sec-sub / SVG `<text>` 节点 / footer / coverage h2 标题 / CSS `width: X%`
- **categories.json 不是真"系统状态"** — 它是渲染层的展示子集(已过滤空壳分类、单 skill 分类、归档前快照等)。报"系统有 N 个分类 / M 个 skill"时**必须穿透到文件系统**:`find ~/.hermes/skills -maxdepth 1 -type d -not -name '.*'` 数分类,`find -L ... -name SKILL.md -not -path '*/.archive/*' \| wc -l` 数 skill(`-L` 跟符号链接,lark 等子目录全是软链)。一旦报告里数字跟实测对不上,Dad 立刻不信任全篇
- **prompt token 实测必须直接调 `build_skills_system_prompt()`** — 自己模拟渲染(`desc[:60]` 截断、近似公式)会跟实际差 30%+。真实做法:`/home/resley/.hermes/hermes-agent/venv/bin/python -m ensurepip --default-pip && pip install tiktoken`,然后从 `agent.prompt_builder` import 函数,清 `_SKILLS_PROMPT_CACHE` 后调用,用 `tiktoken.encoding_for_model('gpt-4')` 算 token。临时改 `collapsed: true/false` 对比时记得跑完恢复
- **Python build 系统反例** — 一个 5-section / 100KB 报告搞 Python build,Dad 改单行文字要 `vim sections/sXX.py && python3 build.py && cp ...` 4 步,他炸了。规则:能 patch 单 HTML 就别 build。形态 ③ 的门槛是 8+ section + 真正频繁迭代 + Dad 主动要"模板化"
- **旧 i.dora 路径已废弃** — 所有 HTML 统一加载 `integration/publish-html`，发布到 `https://www.nexora.restry.cn/static/<project>/<name>.html`。
- **拆多页时旧内容跨页残留要清** — 主页 + 详情页 2 页拆完,如果 mlops/data-science 之类已归档分类还在详情页的 persona 卡 / 单 skill 杂学卡里被列名(skill 数 8 → 应该 7),要手动 patch 删掉。Dad 看到"data-science(Jupyter)"还在,但实际 hermes 已经不加载它了 → 不一致 = 不信任
- **Dad 说"分模块"= 拆 HTML 视觉模块,不是 Python build**(2026-06-05 真踩) — 听到"重构成模块化分块/以后改一块只重建对应 section"**先确认范围**,默认实现是阶梯 ① 单 HTML + section marker 注释边界。Dad 原话纠正:"我之前说让你分模块,只是让你分 HTML 的模块,不是让你分成这种编译式的"。任何 Python build 必须 Dad 明说"写个生成器/脚本"才能上,否则越层
- **拆页面收尾必查清单** — `[ ]` 两页 footer 是否同步到最新版本 `[ ]` 删了的内容(归档分类)在 persona 卡 / hero / sec subtitle 是否都删干净 `[ ]` 共享 hero 数字两页一致 `[ ]` `<title>` 各页独立 `[ ]` 部署后 vision_analyze 两页都看一次 nav 激活态 `[ ]` 旧 monolith / 测试备份 / `.modular-archive/` 都 `rm`
- **HTML byte size ≠ char count** — `python3 build.py` 报 116K chars,`ls -la` 报 133K bytes,这是 UTF-8 中文多字节,**不是 build bug**。判 size 看 `wc -c` / `ls -la`,判内容长度看 char count。Dad 问"为啥变大"先解释这个再查实质
