# 实施方案 HTML 配方(v0 plan doc · 每任务可执行)

**触发场景**: 用户讨论完一套技术方案后说"落地一份方案 / 让团队能派活的实施方案 / 每个任务谁做、多久做、要交什么"。产物要能扔给 PM / 后端 lead / DevOps 各自认领而不需要开会解释。

**区别于其他 HTML skill**:
- `html-report-anthropic-warm`: 分析报告(读取现状 + 分析 + 汇报),没有可派活的任务卡
- `recap-site-mvp-deployer`: 对外汇报站(H1 战报 / 学习历程),story-first
- `family-decision-html-report`: 决策对比(择校 / 医疗),3-column trade-off
- **本 recipe**: 3-4 phase × N 任务 · 每任务包含 owner + 时长 + 依赖 + 输入输出 + 验收标准,团队直接派活

---

## 一、结构骨架(顶层 section 序)

标准 9-10 段:

```
Hero          总目标 + n phase 概览预览卡(圆圈+名字+时长+任务数)
TOC           4 列可点击目录(锚点跳)
§0 · Goal     一句话目标 + 4 铁律 grid + phase summary table
§1 · Phase 0  任务卡(P0.1-P0.n)+ 底部总验收 sage 卡
§2 · Phase 1  同上
§3 · Phase 2  同上
§4 · [补强]   review 发现的盲点补章(如 version management,可选)
§5 · Milestones  timeline(圆圈 + 周次 + Gate 说明框)
§6 · Decisions  6-8 决策表(D1-Dn · 触发时机 + 决策人 + 影响)
§7 · Risks    7-8 风险表(R1-Rn · 概率/影响 pill 三色 + 应对)
§8 · Appendix 2×2 附录卡(路径速查 / 老代码黑名单 / 决策对比 / 边界说明)
TL;DR         "老板直接看这段" · 6 label × body grid
Footer
CTA(可选)     跳去业务对比 HTML 的 back-link
```

## 二、任务卡的关键结构

这是 plan HTML 的核心 unit。CSS:

```css
.task-card { background:var(--surface); border-radius:12px; padding:22px 26px;
             box-shadow:0 0 0 1px var(--border-warm); border-left:3px solid var(--brand); }
.task-card.p0 { border-left-color:var(--brand); }
.task-card.p1 { border-left-color:var(--gold); }
.task-card.p2 { border-left-color:var(--sage); }

.task-head { display:flex; align-items:baseline; justify-content:space-between;
             gap:16px; margin-bottom:14px; padding-bottom:12px;
             border-bottom:1px dashed var(--border-warm); flex-wrap:wrap; }
.task-id    { font-family:mono; font-size:11.5px; color:var(--brand); font-weight:500; }
.task-title { font-family:serif; font-size:19px; flex:1; padding:0 12px; }
.task-tag   { padding:4px 11px; border-radius:999px; font-family:mono; font-size:10.5px; }
.task-tag.owner { background:var(--steel-soft); color:var(--steel); }
.task-tag.time  { background:var(--gold-soft); color:var(--gold); }
.task-tag.dep   { background:var(--sand-2); color:var(--text-3); }

.task-body { display:grid; grid-template-columns:150px 1fr; gap:8px 20px; font-size:13px; }
.task-body-label   { font-family:mono; font-size:10.5px; letter-spacing:0.1em;
                     text-transform:uppercase; padding-top:6px; }
.task-body-content { color:var(--text-2); line-height:1.65; padding:4px 0; }
```

HTML 示例:

```html
<div class="task-card p0">
  <div class="task-head">
    <div class="task-id">P0.3</div>
    <h3 class="task-title" style="margin:0;">JSON → YAML 转换 · 补齐 7 段</h3>
    <div class="task-meta">
      <span class="task-tag owner"><svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-4 3-6 7-6s6.2 2 7 6"/></svg>后端</span>
      <span class="task-tag time"><svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>1d</span>
      <span class="task-tag dep"><svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="6" cy="5" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10M8 10c5 0 4-3 8-3"/></svg>依赖 P0.2</span>
    </div>
  </div>
  <div class="task-body">
    <div class="task-body-label">输出</div>
    <div class="task-body-content">11 个 YAML 填充完整 ...</div>
    <div class="task-body-label">验收</div>
    <div class="task-body-content">
      <ul class="check-list">
        <li>11 YAML 全部有完整 7 段</li>
        <li>与生产 prompt 内容逐字节一致</li>
      </ul>
    </div>
  </div>
</div>
```

**验收 check-list ::before 陷阱** —— 不要用 `content:'☐'`(dingbat 会被 emoji scanner 抓),用 CSS 几何方框:

```css
.check-list li::before {
  content:''; width:12px; height:12px;
  border:1.5px solid var(--text-4); border-radius:3px;
  display:inline-block; transform:translateY(2px);
}
```

## 三、Milestone timeline

```css
.ms-line { position:relative; }
.ms-line::before {
  content:''; position:absolute; left:22px; top:22px; bottom:22px;
  width:2px; background:linear-gradient(180deg, var(--brand), var(--amber), var(--sage)); opacity:0.35;
}
.ms-item { display:grid; grid-template-columns:44px 90px 1fr 200px;
           gap:20px; align-items:center; padding:18px 0; }
.ms-dot  { width:44px; height:44px; border-radius:50%;
           background:var(--surface); border:3px solid var(--brand);
           display:flex; align-items:center; justify-content:center;
           font-family:mono; font-size:12px; color:var(--brand); z-index:1; }
```

每行 4 列 grid: 圆圈 M0/M1/... · 周次 W0/W1/... · 主标题+deliver · 灰色 Gate 说明框。渐变竖线穿过所有圆圈(z-index -1 效果)。

## 四、Admin UI mockup(如 version management 章节需要)

模拟浏览器窗口内嵌一张表:

```html
<div class="vm-admin">
  <div class="vm-admin-chrome">
    <div style="width:11px;height:11px;border-radius:50%;background:#f4695f;"></div>
    <div style="width:11px;height:11px;border-radius:50%;background:#fbc02c;"></div>
    <div style="width:11px;height:11px;border-radius:50%;background:#61d16b;"></div>
    <div class="vm-admin-chrome-url">packhorizon.com/admin/agent-versions</div>
  </div>
  <div class="vm-admin-body">
    <table class="vm-admin-tbl">
      <thead><tr><th>Agent</th><th>当前版本</th>...</tr></thead>
      <tbody>
        <tr>
          <td>brand-strategy</td>
          <td><span class="vm-admin-v rolled">v3 (rolled back)</span></td>
          ...
          <td class="vm-admin-actions">
            <span class="vm-admin-mini-btn hist">History</span>
            <span class="vm-admin-mini-btn gray">Diff</span>
            <span class="vm-admin-mini-btn rb">Rollback</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

pill 颜色语义: `current` sage / `pending` gold(A/B 中)/ `rolled` brand。Rollback mini-button 用 `crimson-soft` 底色显眼。

## 五、决策 + 风险表

决策表 5 列: `# / 决策点 / 触发时机 / 决策人 / 影响`
风险表 5 列: `# / 风险 / 概率 / 影响 / 应对`

概率/影响用 pill 三色分级:

```css
.prob-pill.h, .impact-pill.h { background:var(--crimson-soft); color:var(--crimson); }
.prob-pill.m, .impact-pill.m { background:var(--amber-soft);   color:var(--amber); }
.prob-pill.l, .impact-pill.l { background:var(--sage-soft);    color:var(--sage); }
```

## 六、附录 2×2 grid

- 左上:关键文件路径速查(每行 `<code>路径</code>` + 描述)
- 右上:老代码黑名单(左 crimson 边线 + 短横 marker `::before` 画的短线段,禁止用 ✕)
- 左下:关键决策对比 mini-table(A/B 选项对比)
- 右下:与其他 skill / 项目的边界说明

## 七、TL;DR 一页纸

`grid-template-columns: 120px 1fr` label-body 双列。label 是 mono 全大写 (`做什么 / 为什么 / 怎么做 / 关键约束 / 总周期 / 下一步`),body 是衬线大字。整体渐变底 `linear-gradient(135deg, var(--surface) 0%, #fbeee5 100%)`。

## 八、多 HTML 交叉引用(方案 + 业务对比 双向导航)

如果同项目有多份 HTML 报告(业务对比 + 实施方案 + 分析报告),互相加导航:

**主 HTML 尾部加 CTA 卡片**跳去方案 HTML:

```html
<section class="blk">
  <div class="cta-plan">
    <div>
      <div class="cta-plan-eyebrow">Next Step · 深入方案</div>
      <h2 class="cta-plan-title">已经形成一份可直接派活的实施方案</h2>
      <p class="cta-plan-desc">每个任务含 Owner / 时长 / 依赖 / 输入 / 输出 / 验收标准 ...</p>
    </div>
    <a href="packhorizon-agent-migration-plan.html" class="cta-plan-btn">
      查看完整实施方案 <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12h14M14 7l5 5-5 5"/></svg>
    </a>
  </div>
</section>
```

**方案 HTML 顶部加 back-link 胶囊**:

```html
<a href="packhorizon-workflow-vs-agent-business.html" class="back-link">
  <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M19 12H5M10 7l-5 5 5 5"/></svg> 返回 · 现在 vs Agent 化 业务对比
</a>
```

放在 `<div class="wrap">` 最前 · 用户点开方案能一键回主页面。

## 九、review 一遍 = gap-hunt(用户偏好)

用户说 "review 一遍,是否有 X 功能" 时,不是让你确认现有内容没问题,是**让你找出方案里少了什么**。默认操作序列:

1. 查方案里"多版本 / 回滚 / 权限 / 观测 / 灰度 / 迁移"这些常被漏的横切面有没有覆盖
2. 交叉检查生产已有的能力(比如 DB 里有没有 version 表 / 回滚机制),对比方案要新建什么
3. 找到缺口就补一整个 section,不是加两行文字
4. 更新 TOC / 后续 sec-num +1 / 决策表加一条 / 风险表加一条

**别把 "review" 当成 "看着好不好"** —— 用户抛这个词是等你主动挑刺。这一轮做完 gap-hunt 才算完成。

## 十、Count-from-source 铁律

任何 "阶段数 / 步骤数 / 版本数" 依赖生产事实的图表(timeline / agent list / feed events / progress labels),**必须从 source of truth 拉一次**,不能靠记忆:

- 阶段数 → 从 `db-dumps/prompts-current-*.json` 数 stages 数组
- prompt drift 数 → 从 diff 报告数
- commit 数 → 从 `git log ORIGIN..HEAD --oneline | wc -l`

**2026-07-08 packhorizon 栽的一次**: 画 timeline "10 步" 是我从 agent-pivot 分析 md 里记忆的数字,生产实际 11 stage(含 intake-dialogue)。用户扫一眼数了列表(1-2-3-...-11)就发现缺一个。**画 stage-count 依赖图之前先跑一次 count query 确认**。

## 十一、迭代扩展 · 不是重新生成

用户在方案 HTML 上会不停加要求("补上 X" "把 Y 也画进来" "review 有没有 Z"),写法:

1. 用 `<!-- BEGIN: SEC-NAME -->` / `<!-- END: SEC-NAME -->` marker 分块
2. `patch` mode 精准替换 marker 内容
3. 新加 section 时:补 CSS + 插新 section marker + 更 TOC + 后续 sec-num 全 +1
4. 每次改完跑 emoji scanner 再 scp(见 `html-report-emoji-to-lucide-hardening`)

**别删已有 section 重写**,永远只加。80KB → 100KB 是正常演化。
