# Daddy's HTML design preferences (learned 2026-06-01)

爸爸对 HTML artifact 输出有几条硬偏好，违反任何一条都会被立刻打回。每次画 HTML
（汇报、deck、landing、prototype）前先过这张清单。

## 1. 图标 — 禁用 emoji，必须线图标

**emoji 显得低级**（原话）。任何场合 — header / 卡片 / 按钮 / footer / bullet
prefix — 都不要用 🎯 📊 🚀 这种。

**正确做法：用第三方线图标库 CDN**。首选 Lucide（开源、MIT、跟 shadcn/Vercel
同一套视觉语言）：

```html
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<i data-lucide="calendar-days"></i>
<script>lucide.createIcons();</script>
```

样式建议：`stroke-width:1.5; color:currentColor`（继承父色，方便强调色统一）。

**不要尝试 inline SVG sprite（`<symbol id="i-foo">` + `<use href="#i-foo">`）**
作为 emoji 的替代 — 头痛但更具体的原因：自己手画的 24×24 SVG path 经常在
headless Chrome 截图里渲染成实心黑块 / 错位 / 看不清，vision_analyze 会直接报
"黑块 / 占位方框"。Lucide 是已经被无数项目验证过的 SVG，避免重新发明这套坑。

备选：Heroicons / Phosphor / Tabler，都是 stroke-based 线图标库，CDN 都有。
**禁用** FontAwesome（不是线图标语言、太重）、emoji 字体回退、Material Icons
filled（实心，不是线图标）。

## 2. Bento grid 禁止"为了不对称而不对称"

5 个目录入口卡 = 5 个同级章节。栅格宽度必须反映**内容权重**，不能反映"我想做
得有节奏感"。

**反面案例（本次首版做错的）**：
- 01 占 8 列、02 占 4 列同行（信息密度其实 1:1.1，伪不对称生硬）
- 04 / 05 各占 6 列（每张只两行字，撑得稀稀拉拉，卡片虚胖）
- 整体节拍 8/4/6/6/? 完全没必要，同级内容用不同栅格 = 暗示主次但实际没主次

**正面做法（同级目录默认）**：
- 5 张 = 一行 5 列均分；或 2 + 3 / 3 + 2 两行同尺寸
- 4 张 = 一行 4 列 或 2 × 2
- 真要做 8+4，左边必须是富媒体（大图、列表、缩略图、metrics 块），不能只是两行字

判定线：**写完描述抓 word count，5 张差异 ≤ 20%，就用均分栅格**。

## 3. Anthropic 暖米色风是默认 palette

无明确品牌指令时，爸爸自家 menshen-ui / 自创内容默认走这套：

```css
--cream:#f5f1ea;          /* 背景 */
--cream-2:#ece6db;        /* 次级背景 */
--ink:#2b2620;            /* 正文 */
--ink-soft:#5b544a;
--muted:#8a8378;
--line:#d9d2c4;
--accent:#cc785c;         /* Anthropic 同款 */
--accent-soft:#e8c4b3;
```

字体：`Source Serif 4` / `Source Han Serif SC` 衬线打主标，`Inter` /
`PingFang SC` 走 sans-serif 辅助（nav、metrics 数字、code label），
`JetBrains Mono` 走代码 / 序号。

卡片：**暖白 `#fbf7f0`**（不要纯白 `#fff`，跟米色背景色温冲突，vision 会
报"边缘发脏"）+ 1px `rgba(0,0,0,.06)` 描边 + 极淡阴影。

## 4. 验证流程（headless screenshot 必跑）

写完 HTML **必须**先 headless Chrome 截图 + `vision_analyze` 自检 **再**
给爸爸看。重点问：

- 图标是否正确渲染（不是黑块 / 不是占位方框 / 不是 tofu）
- 卡片栅格是否生硬 / 撑得太开 / 节奏断裂
- 配色色温是否冲突
- 标题断行是否合理

CDN 图标库（Lucide 等）首次截图要给 `--virtual-time-budget=8000` 留够 JS
加载和 `createIcons()` 渲染时间，给 3000 ms 会拍到 `<i>` 还没替换的空标签。

## 5. 不要随便加 emoji 头像 / 装饰符

- 爸爸名字加前缀也不用 emoji（"🍟 小薯条" → 直接 "小薯条"，或 nav brand 用
  terminal 线图标）
- footer / 签名块不要 ✨ ✅ 🎉
- 按钮也不要 emoji，配 Lucide arrow-right / check / x

唯一例外：**飞书 / 微信消息**（卡片 header / quick-reply 按钮 / IM 消息）
可以保留少量 emoji 因为是 IM 语境。**HTML artifact 一律线图标。**
