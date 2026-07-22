# 🏗️ 项目架构 HTML 报告 · 跨项目复用 recipe

> 触发: 爸爸让"给 X 项目画一个 HTML 架构图" / "给 X 也写一个 (用同样方式)" / "用这个模板给 Y 项目也来一版"
>
> 2026-06-28 实战 2 张 (mafu · clawline) 收敛出的可复用骨架, 一份数据换一个报告, 60-90 min 一张。

## 何时用本 recipe

- **项目性 = 有明确产品/工具边界** (mafu / clawline / wingman / cockpit / pi-yunzhan 等)
- **架构性 = 有多组件 + 多流程 + 多状态** (SVG 拓扑值得画)
- **给爸爸看全貌** — 不是设计 mockup / 不是 UX 示意 / 不是 dashboard / 不是短说明
- 内容量 30-40KB, 7-8 section

**不适用**:
- 单组件深挖 → markdown 或 architecture-diagram skill
- UI/UX 体验示意 → html-report-anthropic-warm 的 ux-mockup 分支
- 一次性草图 → sketch skill
- 家庭决策 → family-decision-html-report

## 骨架 (7-8 section 标准配)

**按顺序**, 任一 section 数据不足可省略但顺序保持:

```
Hero
  ├─ 左: 项目名 · Slogan (h1 72px Source Serif) · 一句话价值
  └─ 右: 3 KPI (hero-metric span-2 + 2 小)
       - 主 metric = 项目最大规模 (mission 数 / 组件数 / 服务数)
       - 副 metric = 关键指标 (成熟度 / 成本 / tick 节拍)

01 · 核心流程 / 整体拓扑  ← SVG · 必有 · 最花时间
  ├─ 大 SVG (viewBox 1500×600-720) 一次画完全景
  ├─ 分 stage label (1 · 触发 / 2 · 门控 / 3 · 落档 ...)
  ├─ 节点风格 3 档: n-box(灰边) / n-brand(橙 · 强调) / n-sage(绿 · 结束/成功)
  └─ 连线 2 档: conn(橙实 · 主流量) / conn-sage(绿虚 · 隧道/事件)

02 · 关键概念对比 · 2 列
  ├─ 例: 直连 vs 中继(clawline) / silent vs escalate vs stop(mafu)
  └─ mode-box 两个并排, 各带 tag + desc + code block

03 · 组件/子系统清单 · 3x2 grid
  ├─ 例: 6 大组件 (SDK / Gateway / Channel / Web+Tauri / WeChat / Browser Agent)
  ├─ card 上部 card-tag(mono uppercase) + h3(serif 20px) + card-desc
  └─ 下部 card-meta (端口 / repo / 关键约束, 用 border-top 分隔)

04 · 详细规格表格 (可选, API/endpoints/mission log 类)
  ├─ 例: mafu 6 mission 表 / clawline 15 REST + 2 WS
  ├─ ep-table 带分组行 (背景 rgba(201,100,66,0.06) · uppercase mono)
  └─ 标签 tag-inline (admin 红 / user 绿 / open 灰)

05 · 评分 / 成熟度 · 3x3 grid (可选)
  ├─ score-card 左侧 4px 竖条 (score-bar crimson/amber/sage)
  ├─ 数字大 (Source Serif 40px) + "/10" 小
  └─ 顶部 domain (uppercase mono 10.5) + 底部 score-note
  ├─ 综合项放最后一格 (background transparent · box-shadow none)

06 · 踩坑清单 · 2xN grid (可选, 有 skill 沉淀的项目必有)
  ├─ pit-card 左侧 3px 红条 · title(serif 15) + desc + fix(mono sage 11)
  └─ 每张卡 40-60 字, 讲根因 + 一句话 fix

07 · Repo 结构 (可选, 代码项目必有)
  ├─ repo-tree = 一段 <pre> (JetBrains Mono 12.5)
  ├─ 高亮 dir(橙) / repo-name(深黑) / cmt(灰)
  └─ 独立 repo / monorepo 区分标注

Footer
  ├─ 左: 项目名 · 版本 · 关键里程碑日期
  └─ 右: skills 清单 (mono · gray)
```

## Design tokens (原样复制, Anthropic 暖色)

```css
:root {
  --bg: #f5f4ed;          /* parchment 底色 */
  --surface: #faf9f5;     /* ivory 卡面 */
  --surface-2: #ffffff;
  --sand: #e8e6dc;        /* 分组行 / 合计行背景 */
  --border: #f0eee6;
  --border-warm: #e8e6dc;
  --ink: #141413;         /* 主文本 */
  --text: #4d4c48;
  --text-2: #5e5d59;
  --text-3: #87867f;      /* 副文本 / label */
  --brand: #c96442;       /* terracotta 强调 */
  --brand-2: #d97757;
  --sage: #6a8e4e;        /* 绿, 成功/结束 */
  --crimson: #b53333;     /* 红, 危险/失败 */
  --amber: #b78324;       /* 橙, 警告 */
}
```

**字体三件套** (Google Fonts, 一定用这三个):

```
Source Serif 4 (opsz 8..60, wght 400/500/600) — h1/h2/h3/serif class/数字
Inter (wght 300-600) — body 正文
JetBrains Mono (wght 400/500) — code / kpi label / mono class
```

## SVG 拓扑绘制心法

**先摊平画在纸上/白板/mermaid**, 再翻译到 SVG 坐标, 别直接在 SVG 里想布局。

`viewBox="0 0 1500 620"` 是甜区宽度; 高度按 stage 数 × 100-150。

**节点尺寸**:
- 小节点 (次要 / 图例): 200-240 × 80
- 大节点 (核心 stage): 240-400 × 100-130
- 超大节点 (中心网关 / 主 pipeline): 240-400 × 300-400 (装子模块)

**连线**:
- 直线 + `marker-end="url(#arr)"` 最常用
- 弯线 (path Q/C) 只在避让节点时用, 别炫技
- 虚线 `stroke-dasharray="5 3"` 或 `"6 3"` 表示隧道/事件流/异步

**Stage 数甜区**: 4-7
- clawline: 4 stage (客户端 → gateway → 持久化 → channel)
- mafu: 7 stage (触发 → 门控 → 落档 → tick → 5 路 → 收尾 → 简报)

## 数据准备 (画前必备, 禁边写边算)

**先跑数据到 `/tmp/*.json`**, 再动 HTML:

```bash
# 例: mafu 数据
python3 -c "
import json
d = json.load(open('/Users/leway/.hermes/mafu-missions.json'))
hist = d.get('history', [])
real = [m for m in hist if not m['mission_id'].startswith(('test-', 'escalate-test-'))]
total_ticks = sum(len(m.get('tick_log',[])) for m in real)
print(json.dumps({'real': len(real), 'total_ticks': total_ticks}))
" > /tmp/mafu-stats.json
```

**数据源清单** (按项目选):
- 现有 skill 数据 (`skill_view` 相关 skill 拿状态)
- 项目根 README + `docs/*.md`
- 项目 `.hermes/memory.md` (如有)
- 运行时状态 (JSON state files / API `/healthz`)
- git log 关键 commit
- ssh 远端 portal 现状 (`ssh claw@192.168.1.235 "ls /home/claw/lobster-platform/portal/static/<project>/"`)

## 部署 (走 publish-html skill)

```bash
PROJECT=<项目 kebab-case>          # wingman / clawline / mafu / pi-yunzhan
NAME=<name-architecture>
ssh claw@192.168.1.235 "mkdir -p /home/claw/lobster-platform/portal/static/$PROJECT"
scp /tmp/${NAME}.html claw@192.168.1.235:/home/claw/lobster-platform/portal/static/$PROJECT/${NAME}.html
curl -sS -o /dev/null -w 'status=%{http_code}  size=%{size_download}\n' \
  https://www.nexora.restry.cn/static/$PROJECT/${NAME}.html
```

发给爸爸: **裸 URL 单行**, 禁 code block 包 (飞书才 auto-link)。

## Vision 验证节奏

1. 首截 `--window-size=1700,3200` 试水
2. 不够高就 `1700,6500-6800`
3. 上下切 `top.png` (0-4000) + `bot.png` (3500-最底), Pillow crop, 段间必 500px 重叠
4. `vision_analyze` 分别问 P0+P1
5. 修 → 重截 → 复审, 直到 no hard issues

**headless chrome CJK 字体 fallback 缺字** = 已知问题, 截图上看到"字符异常" (方块 / 缺笔画) 时先在真浏览器打开验证是不是 chrome 问题, 是就发, 不是就补 font-family fallback。

## 已实战案例

- 2026-06-28 mafu-architecture (7 section · 29KB · https://www.nexora.restry.cn/static/wingman/mafu-architecture.html)
- 2026-06-28 clawline-architecture (7 section · 38KB · https://www.nexora.restry.cn/static/clawline/clawline-architecture.html)

## 反面清单

- ❌ **不要**在架构报告里画 UI mockup / 用户视角 phone mock (那是 UX 图, 别混)
- ❌ **不要**堆无信息卡 (通用 SaaS 4-icon grid = slop, 每个 card 必须有 tag/数字/独一细节)
- ❌ **不要**用彩色 emoji (🚀 🎯 💡 ...) → 内嵌 SVG line icon 或直接不用
- ❌ **不要**用 dingbats (✓ ✗ ⚠ ★ → ← ↑ ↓) 在 SVG `<text>` 里, vision 一律扣分, 换 inline SVG path
- ❌ **不要**编数字 (KPI / mission 数 / commit hash 一定要跑数据出来, 别拍脑袋)
- ❌ **不要**发 markdown code block 包 URL 给爸爸 → 飞书不 auto-link, 爸爸点不动

## 关系

- **本文档** = `html-report-anthropic-warm` 唯一入口下的项目架构报告 recipe
- `html-report-anthropic-warm` 主文件负责判断三档模式；选中正式架构报告后再进入本文
- `integration/publish-html` = 发布到 portal 的唯一最后一公里
