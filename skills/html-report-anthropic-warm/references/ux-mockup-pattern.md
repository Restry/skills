# UX Mockup Pattern (Phone + Before/After + Feeling)

When user asks **"对我什么体验" / "我用这个是啥感觉" / "我会看到啥"** about a system / tool / feature, use this pattern. Validated 2026-06-08 on Watchtower UX deliverable — Dad's first reaction to the architecture version was "看着都很头疼"; switched to this UX pattern and got "看起来就清晰多了".

## Layout structure

```
┌─────────────────────────────────────────────────┐
│  H1: "用了 X 之后 / 装了 Y 之后" headline       │
│  Subtitle: "不讲架构、不讲代码，只讲体验"      │
├──────────────────────┬──────────────────────────┤
│ [现在] red tag       │ [装了之后] green tag     │
│ 栏标题 + 副标题      │ 栏标题 + 副标题          │
│ Phone mock #1        │ Phone mock #2            │
│ - iOS chat header    │ - iOS chat header        │
│ - 一堆乱糟糟消息     │ - 几张干净的卡片         │
│ - 工具调用灰行       │ - 状态徽章 + 摘要        │
│ - 末尾"还在跑..."    │ - 不同时间分隔条         │
├──────────────────────┼──────────────────────────┤
│ 😩 红底 feel box     │ 😌 绿底 feel box         │
│ 用户引号 punchline   │ 用户引号 punchline       │
│ 解释为什么烦         │ 解释为什么省心           │
├──────────────────────┴──────────────────────────┤
│  TLDR 一句话 + 4 条 bullets「不用 X / 不用 Y」 │
└─────────────────────────────────────────────────┘
```

## CSS 关键变量

```css
:root {
  --phone-bg: #ecebe5;  /* 手机外壳灰 */
  /* 复用 html-report-anthropic-warm 主调色板 */
}

.phone {
  background: var(--phone-bg);
  border-radius: 36px;
  padding: 18px;
  box-shadow: 0 4px 30px rgba(0,0,0,0.06), 0 0 0 1px var(--border-warm);
}
.phone-inner {
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  min-height: 1080px;  /* 接近真实手机长宽比 */
}

/* iOS-style chat header */
.chathd {
  background: #f7f7f5;
  padding: 16px 18px;
  border-bottom: 1px solid #eeece4;
  display: flex; align-items: center; gap: 12px;
}
.chathd .avtr {
  width: 36px; height: 36px;
  border-radius: 50%;
  /* 头像渐变 — 不同 bot 用不同渐变区分 */
  background: linear-gradient(135deg, #d97757, #c96442);
}

/* Chat bubble */
.bubble {
  padding: 9px 12px;
  border-radius: 14px;  /* iOS-ish */
  font-size: 13.5px;
  line-height: 1.55;
}
.msg.bot .bubble {
  background: #fff;
  border: 1px solid #eeece4;
  border-bottom-left-radius: 4px;
}
.msg.me .bubble {
  background: #cee2ff;  /* iMessage blue */
  border-bottom-right-radius: 4px;
  color: #0e2c5c;
}

/* tool-call 灰胶囊 — 模拟 agent 工具调用的视觉污染 */
.bubble .tool {
  color: #9090a8;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
}
.bubble .tool::before { content: "› "; color: #bbb; }

/* Time separator inside chat */
.timesep {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 0 4px;
  color: #aaa; font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase; letter-spacing: 0.12em;
}
.timesep::before, .timesep::after {
  content: ""; flex: 1; height: 1px; background: #e6e4dc;
}

/* Feeling block — 强对比但 muted */
.feel.bad  { background: rgba(181,51,51,0.05); border: 1px solid rgba(181,51,51,0.15); }
.feel.good { background: rgba(106,142,78,0.06); border: 1px solid rgba(106,142,78,0.15); }
.feel-emoji { font-size: 42px; line-height: 1; }
.feel-ti {
  font-family: 'Source Serif 4', serif;
  font-size: 22px; font-weight: 500;  /* punchline 用 serif */
}
```

## 工艺细节

1. **左右栏 align 同一起点** — 左栏用户气泡时间戳（22:34），右栏对应时间分隔条同一时间，让"对照"在视觉上一眼成立。

2. **碎碎念真实感** — 左栏要堆够 10+ 条 bot 消息（含 `tool_name: "..."` 灰胶囊行），最后 fade 成 `还在跑...` 之类，让烦躁感成立。"少而精"在左栏会失败 — 烦躁感本身就要靠数量堆。

3. **同一张卡演化** — 右栏用"+1 分钟 / +3 分钟 / 完事"分隔条切片展示同一张卡的不同状态。timeline 行数自然递增（0 → 2 → 4 行），让"同一张卡在长大"的叙事直观。

4. **多状态视觉权重必须对得上语义** — RUNNING 橙满色 / DONE 绿沉灰 / ERROR 红满色 / STUCK 黄满色。**"需要用户看见的"必须满色，"已完成不打扰的"才褪色**。混淆 = 产品价值主张崩塌（watchtower v1 把 ERROR 也褪色了，vision critique 立刻抓到："这是产品定位崩塌不是审美问题"）。

5. **Feeling block 用 muted 对比** — 不要饱和红/绿暴力撞色，用透明度 5-8% 的底色 + 同色描边。Anthropic warm 调性要求"克制的强对比"。

6. **TLDR 收尾** — 一句话定义动作（"60 条 → 1 张卡"），关键时刻（变绿那一刻），用户收益（不用盯也不会漏）。**三拍 punchline**。

## 反 anti-pattern

- **不要画架构图穿插进 UX mock** — 架构图是另一类报告（见 SKILL.md 主体），混在 UX 里破坏叙事
- **不要给 mock 里的 bot 消息加真实链接 / 真实 message_id** — 这是示意不是产品截图
- **不要在 UX mock 报告里讲技术细节** — 想讲就在 TLDR 后加一行 "技术细节见 [架构报告链接]"
- **不要默认两个手机都让用户在里面发消息** — 比如 Watchtower：用户在 Fries 那 chat 发，但**在 Dora 这 chat 从没说过话**（Dora 单方面冒卡片）。把"两个 chat 物理分开"的产品语义画错就毁了核心叙事
- **多任务场景至少展示 1 张 STUCK 卡 + 1 张 ERROR 卡** — 不然图例画了 4 种状态实际只 demo 2 种，vision 会抓

## 自检 checklist（发图前必跑）

```
[ ] 左右栏起点时间对齐
[ ] 左栏 ≥ 10 条消息 + 至少 3 条 tool 调用灰行 + 末尾 fade "还在跑..."
[ ] 右栏 ≥ 3 张卡，至少 1 张展示"同卡 edit"语义（时间分隔条注明"同一张卡被改"）
[ ] 4 种状态颜色对得上语义：RUNNING/ERROR/STUCK 都满色，只有 DONE 是灰
[ ] feeling block emoji 是 😩/😌/🤔/🙄 等强情绪，不是中性 😀
[ ] TLDR 是 punchline 不是 summary（动作 + 关键时刻 + 用户收益三拍）
[ ] 整张图 0 处提到 SQLite/cron/API/schema/state machine 等技术词
[ ] 如果产品有多 chat / 多 surface 区分（如 Watchtower 派活 chat vs 监听 chat），mock 里这个区分必须看得见
```

## 历史交付

- **2026-06-08 watchtower-ux.html / watchtower-multi.html**（https://i.dora.restry.cn/share/）
  - 教训：第一版当成架构报告画了 7 section + SVG 数据流 + SQLite schema + 风险矩阵，Dad 反馈"看着都很头疼" "我只想知道对我啥体验"
  - 转 UX mock 模式后立刻"清晰多了"
  - 关键迭代：①第一版画错 chat 归属（让用户在 Dora 这边发消息）→ Dad 纠正"Dora 是单向监听，用户不发"→ 删掉用户气泡，加灰色叙述 ②补充多任务场景：1 张图 6 张卡 = 1 DONE 灰 + 1 ERROR 红 + 3 RUNNING 橙 + 1 STUCK 黄，证明状态系统在并行场景下站得住
