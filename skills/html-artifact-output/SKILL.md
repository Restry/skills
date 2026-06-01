---
name: html-artifact-output
description: 当用户要"输出 / 整理 / 给我一份 / 写一个 X"，且 X 涉及对比、空间布局、交互体验、数据流、设计令牌、PR review、实施计划、流程图、决策树等内容时，**优先用单文件 self-contained .html 而非 markdown**。HTML 给 agent 一支真笔（CSS + 内联 SVG + 少量 JS），把"会被 skim 的散文"换成"会被真读的页面"。触发词：实施计划 / PR review / 设计稿 / 流程图 / 对比方案 / 模块图 / 选型 / 接入文档 / 演示稿 / 评审 / 报告。
---

# html-artifact-output — 输出 HTML 工件而非 markdown

灵感来源：[The unreasonable effectiveness of HTML](https://thariqs.github.io/html-effectiveness/) by Thariq Shihipar (2026)。

## 何时触发（决策树）

| 任务类型 | 默认输出 | 为什么 |
|---|---|---|
| **方案对比 / 技术选型** | HTML（并排卡片+inline trade-off） | markdown 三段散文要读者自己脑补对比 |
| **PR review / code review** | HTML（带 severity tag、jump link、margin notes） | diff 是空间信息 |
| **实施计划 / roadmap** | HTML（timeline + 数据流图 + 风险表 + 关键代码片段） | 多维信息一页可见 |
| **设计稿 / mockup** | HTML（活的色板、组件变体表） | HTML 本来就是设计的运行时 |
| **架构 / 模块图** | HTML（SVG 框图 + 热点路径高亮） | mermaid 字符画太弱 |
| **流程图 / 部署管线** | HTML（可点击节点 + 失败路径） | 静态 PNG 不可探索 |
| **演示稿 / slides** | HTML（`<section>` + 20 行 JS 方向键翻页） | 不用 Keynote、双击即看 |
| **报告 / 复盘** | HTML（图+表+inline 数据） | 比纯文 markdown 友好 |
| **接入文档 / SDK demo** | HTML（curl/code 标签页 + 实时响应） | 真能跑的样例 |
| **快速对比/选项让用户挑** | HTML | 5 秒能选 vs 5 分钟读散文 |

| 任务类型 | 默认输出 | 为什么 |
|---|---|---|
| **简短回答 / 单段说明** | 直接消息 | HTML 太重 |
| **代码本身**（不是 review） | 代码文件 | 别套壳 |
| **聊天对话** | 直接消息 | 别强行 |

## 产物规范

### 1. **单文件 self-contained**
- 一个 `.html`，**所有 CSS / SVG / JS 内联**，无外链 CDN
- 双击 = 浏览器直接渲染
- 路径放 `~/Desktop/<topic>-<date>.html`，发回用户用 Discord 附件 / `MEDIA:` 协议

### 2. **dark theme 默认**（爸爸偏好）
```css
body { background: #0a0a0a; color: #e4e4e7; font: 14px/1.6 -apple-system, "SF Pro Text", system-ui, sans-serif; }
code { background: #1a1a1a; padding: 2px 6px; border-radius: 4px; color: #f59e0b; }
```

### 3. **基础排版**
- max-width 760px 居中（PR review / 实施计划 / 报告）
- 大块 SVG / mockup 解锁全宽
- 章节用大号编号 `01 / 02 / 03`（左侧 6xl 字号灰色）
- code 用等宽字体 + 浅色容器
- 风险/严重度用色标：`HIGH` 红、`MED` 橙、`LOW` 灰

### 4. **必备结构元素**（按场景挑）
- **timeline**（实施计划）：横排里程碑卡，`Week N · 周几` + 任务名 + 涉及包标签
- **data flow**（架构图）：内联 SVG，optimistic 用实线、fan-out 用虚线
- **risk table**（实施计划/PR review）：3 列 `Risk | Sev | Mitigation`
- **annotated diff**（PR review）：左 diff、右 margin notes，notes 标 `Blocking / Nit / Question`
- **mockup**（设计/前端）：用 div+CSS 画粗略真图，**不用 Lorem ipsum**——用真业务文案
- **trade-off cards**（方案对比）：3 张并列卡，每张顶部"适合 / 不适合"
- **swatch grid**（设计系统）：色值 + hex + 用途三栏
- **slide**（决策汇报）：`<section>` + 方向键 JS

### 5. **inline SVG 用法**
- 框图节点用圆角 rect (`rx=8`)，stroke 1.5px
- arrow marker 自定义（默认 marker 难看）
- 文字用 `<text>` 不用 image-text

```html
<svg viewBox="0 0 800 400" style="width:100%; max-width:760px">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10" fill="#a3a3a3"/>
    </marker>
  </defs>
  <rect x="20" y="20" width="160" height="60" rx="8" fill="#1a1a1a" stroke="#71717a"/>
  <text x="100" y="55" text-anchor="middle" fill="#e4e4e7" font-size="13">Composer</text>
  <line x1="180" y1="50" x2="280" y2="50" stroke="#71717a" marker-end="url(#arr)"/>
</svg>
```

### 6. **JS 极简**
- 演示稿翻页：~20 行
- 任务列表 checkbox 状态：5 行 `localStorage`
- **不引 React/Vue/任何框架**——纯 vanilla
- 互动只在"加分"时加，不为加而加

## 输出流程

1. **判断**：用户的请求是否在上面"决策树触发场景"里？不在就走 markdown / 直接消息
2. **写 HTML 到 `~/Desktop/<topic>-YYYY-MM-DD>.html`**：用 `write_file` 工具，单次 ≤ 8KB；超大的拆成多步 patch
3. **简报 + 附件**：消息回 1-2 行说明 + `MEDIA:/Users/leway/Desktop/xxx.html`
4. **可选预览**：用 `headless-chrome-screenshot-verify` skill 截图发 PNG（如果 Discord 直接打开 .html 不方便）

## 反模式（别犯）

- ❌ 给爸爸发巨大的 markdown wall——他会扫一眼就关
- ❌ 用 mermaid ASCII 框图代替 SVG（终端勉强，浏览器丑）
- ❌ HTML 里塞 React + bundler——不是 self-contained
- ❌ 强行给所有任务 HTML 化（"你好" 也 HTML 就过了）
- ❌ 用 placeholder Lorem ipsum——爸爸要看真业务文案

## 9 大场景模板（按需展开）

来源 demo（参考阅读，不重复实现）：
- 01-exploration-code-approaches.html — 三方案并排
- 02-exploration-visual-designs.html — 视觉方向对比
- 16-implementation-plan.html — 实施计划完整范例 ⭐
- 03-code-review-pr.html — annotated PR ⭐
- 17-pr-writeup.html — PR 作者侧 writeup
- 04-code-understanding.html — 模块图
- 05-design-system.html — 活的设计系统
- 06-component-variants.html — 组件变体表
- 07-prototype-animation.html — 动画 sandbox
- 08-prototype-interaction.html — 4 屏点击流
- 09-slide-deck.html — 方向键 slides
- 10-svg-illustrations.html — SVG 配图集
- 13-flowchart-diagram.html — 可点击流程图
- + 7 个 research/reports/editors

具体 demo 可在线查看：https://thariqs.github.io/html-effectiveness/

## 关联 skills
- `creative/architecture-diagram` — 暗色 SVG 图（架构）
- `creative/popular-web-designs` — 设计风格库
- `software-development/headless-chrome-screenshot-verify` — 截图预览
- `creative/excalidraw` — 手绘风替代方案
