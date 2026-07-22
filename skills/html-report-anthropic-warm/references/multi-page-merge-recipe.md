# Multi-page Merge Recipe(把 N 个子页合并成 K 个附录)

**反向操作** of split。当你已经有 N 个独立 HTML 附录页,发现「文件太多 / 导航不一致 / 内部叙事顺序不合理」,需要 6→3 或 5→2 收敛时用这套。2026-07-10 AZ PIKE-RAG 实战验证(6 → 3 · 517KB → 430KB)。

## 何时合并(触发信号)

- 附录数 ≥ 5,主报告 TOC / sticky nav / 底部 child-cards 已经视觉过载
- 某些附录**从来没进过 TOC** 或 sticky nav(游离孤儿页 —— 100% 触发合并)
- 附录之间**叙事顺序反了**:B(bug)→C(接入),但读者需要先接入再看 bug
- 附录内容强重叠:附录 A 后半 = 附录 C 前半的续集
- 用户明确说「合并 / 整理 / 不啰嗦 / 由浅到深」

## 合并前必做:摸清共享 shell 对齐度

多子页能干净合并的前提是**它们共享同一 head/style shell**。先扫一遍:

```bash
# 每个候选文件的 head/body/footer 结构行数一致吗?
for f in <files>; do
  echo "==== $f ===="
  grep -nE '^<body>|^</body>|<div class="wrap">|<div class="child-nav">|<div class="child-hero">|<style|</style>' "$f"
done
```

判断力表:

| 观测 | 含义 | 合并策略 |
|---|---|---|
| 3 个 file 的 `<style>` 起止行**完全相同**(如都是 8-566) | 共享同一 base CSS | 用其中一个的完整 head + 抠出其他文件独有的 style 段 |
| body 起始行、child-nav 起始行**都对齐** | 共享 shell 模板 | shell cat 直接拼即可,无需重排结构 |
| 只有一个 file 多出一段 `<style>` | 该 file 独有样式(表格/bug-card) | 追加它的独有 style 段到 head |
| head 完全不一致(不同 hero 类 / 独立 CSS 变量) | shell 未对齐 | 需先做「shell 归一化」pass,或者只加导航层 |

## 合并策略选择

| 情况 | 策略 |
|---|---|
| 3+ 附录 shell 完全对齐 · 内容有叙事线 | **物理合并**(shell cat 拼接) + **叙事重排**(Part I/II/III 分隔条) |
| 附录 shell 不对齐 · 但主报告导航一团糟 | **保留原文件不动 · 只补导航层**(改 sticky nav + TOC 让所有页可达) |
| 附录之间强重叠(内容 70%+ 相似) | 保留一个 · 删其他(不要合并 · 会两倍冗余) |

## 物理合并 · 4 步走(shell cat 模式)

### Step 1 · 摸清各文件 body 内容的精确边界行

```bash
for f in <files>; do
  echo "==== $f ===="
  grep -nE 'class="child-hero"|<div class="footer"|</body>' "$f" | head -8
done
```

记下每个文件的**内容区**行范围(如:live-findings 主内容 L590-782)。

### Step 2 · 用 sed 抠出各段到 /tmp

```bash
# base head + 关键 style(第一个文件)
sed -n '1,576p' base-file.html > /tmp/merged-head.html

# 其他文件的独有 style
sed -n '594,615p' extra-file.html > /tmp/merged-extra-style.html

# 各文件的主内容区
sed -n '590,781p' file-a.html > /tmp/merged-body-a.html
sed -n '590,741p' file-b.html > /tmp/merged-body-b.html
sed -n '590,782p' file-c.html > /tmp/merged-body-c.html
```

### Step 3 · 用 write_file 构造 hero + 分隔条 + footer

**新 hero + 顶部目录**(告诉读者这是几合一 · Part I/II/III 讲什么):

```html
<div class="child-hero">
  <div class="eyebrow"><span class="dot"></span>APPENDIX TWO · LIVE VERIFICATION</div>
  <h1>实测记录 · 从冷启动到端到端跑通</h1>
  <p>本页记录 XX-XX 到 XX-XX 两天的完整实测过程,分三个阶段:...</p>
  <div style="margin-top:24px;padding:20px 26px;background:var(--surface-2);border-radius:12px;
              border:1px solid var(--border-warm);font-family:'JetBrains Mono',monospace;
              font-size:12.5px;line-height:2;color:var(--text-2);">
    <div style="font-size:11px;letter-spacing:0.14em;color:var(--brand);text-transform:uppercase;margin-bottom:12px;">📋 三阶段 · 按时间线</div>
    <div><b style="color:var(--brand);">Part I · 起点</b> — <a href="#part-1" style="color:var(--brand);text-decoration:none;">副标题</a></div>
    <div><b style="color:var(--brand);">Part II · 跑起来</b> — <a href="#part-2" style="color:var(--brand);text-decoration:none;">副标题</a></div>
    <div><b style="color:var(--brand);">Part III · 一路的坑</b> — <a href="#part-3" style="color:var(--brand);text-decoration:none;">副标题</a></div>
  </div>
</div>
```

**Part 分隔条**(每个 Part 起点插入,给读者阶段感):

```html
<div id="part-1" style="margin-top:48px;padding:28px 32px;
     background:linear-gradient(90deg,rgba(201,100,66,0.08),rgba(201,100,66,0.02));
     border-radius:14px;border-left:5px solid var(--brand);">
  <div style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.16em;
              color:var(--brand);text-transform:uppercase;margin-bottom:8px;">PART I · <TAG></div>
  <h2 style="margin:0;font-size:32px;">Part 标题</h2>
  <p style="margin-top:12px;color:var(--text-2);font-size:14.5px;line-height:1.7;">Part 描述</p>
</div>
```

**Footer + 姐妹页互链**(附录之间也能跳转,不只是回主报告):

```html
<div class="child-nav" style="margin-top:56px;">
  <div>← <a href="pike-rag-report.html">返回主报告</a> · <a href="sister-appendix.html" style="color:var(--brand);">附录 X · 姐妹页 →</a></div>
  <div style="color:var(--text-3);">附录 Y · 副标 · 生成于 YYYY-MM-DD</div>
</div>
```

### Step 4 · shell `cat` 拼接 + 验证

```bash
cat /tmp/head.html /tmp/extra-style.html /tmp/hero-and-part1-header.html \
    /tmp/body-a.html /tmp/part2-divider.html /tmp/body-b.html \
    /tmp/part3-divider.html /tmp/body-c.html /tmp/footer.html > merged.html
wc -l merged.html

# 快速结构验证
grep -oE '<(h[1-3])[^>]*>[^<]{2,}</\1>' merged.html | sed 's/<[^>]*>//g' | head -20
grep -c '<style' merged.html
grep -c 'id="part-' merged.html
```

## 叙事重排(合并的 UX 价值所在)

**关键洞察**:如果原来 A/B/C 是**时间倒序**创建的(最新在前),合并时不要保留原顺序 —— 用**时间正序**重排:

| 原顺序(创建时间倒序) | 新顺序(叙事正序) |
|---|---|
| A · 端到端测试(最新 · 07-10) | Part I · 基础设施接入(07-09 下午) |
| B · Bug 清单(07-09 全天) | Part II · 端到端测试(07-10) |
| C · Mock→Real 接入(07-09 下午) | Part III · 一路的 Bug(全线) |

读者从上到下读 = 从早到晚跟着项目走 · 因果链自然。用户明确要求「由浅到深、清晰易懂」时几乎必做。

## 配套改主报告(3 处必改 · 一处漏了就穿帮)

合并子页只是一半的活 · 主报告 3 处入口必须同步:

| 位置 | 原状 | 改成 |
|---|---|---|
| **Sticky nav** · `class="child"` 链接 | 3 个旧附录链接 | 2 个新附录链接 |
| **TOC 卡片** · `class="toc-item external"` | 3 张卡指向旧 | 2 张卡指向新 · description 重写 |
| **底部 child-cards** | 3 张 `<a class="child-card">` | 2 张 · title/desc/eyebrow 全改 |
| **中途引用**(如 SECTION-X 后的深度阅读卡) | 单独指向某旧子页 | 指向新合并后的姐妹页 |

一次性 `grep` 列全所有旧 URL 再统一改:

```bash
grep -n 'old-a\|old-b\|old-c\|old-d\|old-e' main-report.html
# 每处都改,改完再 grep 一遍确认零残留
grep -n '<old-file-names>' main-report.html  # 应该空
grep -n '<new-file-names>' main-report.html  # 应该 N 条
```

## 部署 · 双端清理

**本地 rm ≠ 服务器 rm**。合并后:

```bash
# 1. 本地删旧子页
rm old-a.html old-b.html old-c.html

# 2. 上传新合并页 + 修改后的主报告
scp merged-a.html merged-b.html main-report.html user@server:/deploy/path/

# 3. 服务器上 ssh rm 旧文件(否则旧 URL 还能访问,用户点了迷惑)
ssh user@server 'cd /deploy/path && rm old-a.html old-b.html old-c.html'

# 4. curl 验证:新 URL 200 · 旧 URL 404
for u in <new-urls>; do
  curl -sk -o /dev/null -w "%{http_code} %{size_download}  $u\n" "$u"
done
for u in <old-urls>; do
  curl -sk -o /dev/null -w "%{http_code}  $u\n" "$u"
done
```

## Git 层收尾(利用 rename 检测保留历史)

**关键机制**:如果新合并页的内容有 ≥50% 继承自某一个旧子页,直接 `git add` 新文件 + `git add` 旧文件(已删),git 会自动识别为 rename,而不是「删一个新加一个」。历史通过 `git log --follow` 可以追踪。

```bash
# 直接一起 git add · 让 git 自己识别 rename
git add old-a.html old-b.html old-c.html   # 已删的 · git 会 stage 成 D 或 R
git add new-merged-a.html new-merged-b.html

# status 应该看到 R(rename)+ D(delete)+ A(add)+ M(modify)混合
git status --short
# 示例输出:
#  D  old-b.html
#  R  old-a.html -> new-merged-a.html   ← 内容 50%+ 继承的
#  R  old-c.html -> new-merged-b.html
#  M  main-report.html
```

commit message 建议格式:

```
docs: consolidate N analysis HTMLs into K (main + <appendix1> + <appendix2>)

Consolidation pass to reduce redundancy and improve reading flow.

Changes:
- NEW <appendix1>.html (XKB, merged from <src-a> + <src-b>)
  Part I: ...
  Part II: ...
- NEW <appendix2>.html (YKB, merged from <src-c> + <src-d> + <src-e>)
  Part I: ...
  Part II: ...
  Part III: ...
- MODIFY main.html: sticky nav N→K links, TOC A→B items, bottom cards N→K
- REMOVED: <src-a>, <src-b>, <src-c>, <src-d>, <src-e>

Result: N→K files, XKB→YKB (dedup), all navigation cross-linked.

Local checkpoint only. NOT pushed.
```

**用户明确说「不要 push 到远程」时**:

- 先 `git branch --show-current` 确认在纯本地分支(如 `analysis-report-local`)
- `git status -sb` 输出后**没有** `[ahead N]` / `origin/xxx` 标记 = 分支不追踪任何 remote,`git push` 也 push 不出去
- **不要**用 `git commit --amend` 到已经 push 过的分支
- **不要**在有 `origin` 追踪的分支上 commit —— 先 `git checkout -b <local-only-branch>` 切走

## Pitfalls(实战教训)

- **不要用 `execute_code`** 抠内容 —— cron_mode 环境下会触发 approvals 拦截(2026-07-10 触发)。用 shell `sed -n` + `write_file` + `cat` 完全够用
- **合并前先浏览一遍所有子页的 h2/h3 大纲**(`grep -oE '<h[1-3][^>]*>[^<]*</h[1-3]>'`)—— 摸清哪些子页内容单薄不足独立成页(< 5 个 h3 的通常应该合并到姐妹页)
- **保留 hero 高度**:合并后新 hero 要加**顶部目录**(Part I/II/III 各自 anchor 链接),不然合成的大页读者不知道有几段
- **每个 Part 用同款分隔条**(渐变 bg + 品牌色左边框 + eyebrow + h2 + lede)—— 视觉一致性,读者一眼看出「新章节」
- **Part 内部保留原子页的 h3 层级**:不要为了「统一」把原 h3 提为 h2 —— 破坏原文语义 + 目录结构乱
- **姐妹页互链**:每个附录 footer 都要「返回主报告 · 姐妹附录 →」链接,让读者在两个附录间横向跳,不必回主报告
- **别删 backup**:主报告的 `.backup.html` 保留 —— 万一用户说「回滚上一版」有救
- **配套改主报告一次性做完**:sticky nav + TOC + 底部卡片 + 中途引用一次 patch 全改完,分次改容易漏 · 一漏就穿帮
- **git rename 阈值**:git 默认 rename similarity 阈值 50%。如果合并页内容有 60%+ 是从某一个旧子页继承,git 会自动识别成 rename。如果 <50%,git 会显示成「delete + add」—— 这时也 OK,`git log --all --oneline` 依然能追到旧文件的历史,不会丢
- **shell 中 `&&` 有时被误判为 backgrounding**:多条命令串联时如果 terminal 拒绝 · 用 `;` 或者拆成多个 terminal 调用(2026-07-10 触发)

## 何时不要走合并 · 保留独立子页更好

- **每个子页会单独发给不同同事**(QA 看测试 / Ops 看部署 / Dev 看接入)—— 合并成大页后同事得滚屏找自己关心的段落
- **各子页更新周期不同步**(测试报告每周更 · bug 清单持续追加)—— 合并后你改一段要重新推整个大页
- **子页规模都 > 60KB 且各有独立读者**—— 合并后单页 200KB+ 加载慢 · 反而伤 UX

规则:能保留独立就保留 · 只有当「文件多到主报告导航讲不清 / 叙事顺序乱 / 内容重叠」时才合并。**默认保守**。
