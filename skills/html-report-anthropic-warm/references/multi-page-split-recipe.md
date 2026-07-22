# Multi-page Split Recipe

把一个长 HTML 报告拆成 2-3 页 + sticky nav 互链。2026-06-05 实战验证。

## 何时拆分

- 单页 > 100KB
- Dad 主动提"拆两个页面" / "一页太重"
- 内容自然分组:精华(性能 + 改动) vs 细节(完整数据 + 画像)

## 拆分原则

1. **每页独立完整** — head/body/footer 全在
2. **共享 hero** — 任何页进来都能看到核心数字
3. **共享 head 块** — 字体、CSS 都一样
4. **不要超过 3 页** — 否则导航疲劳

## Sticky Nav CSS(粘贴即用)

```html
<style>
  .page-nav {
    display: flex;
    gap: 10px;
    padding: 14px 22px;
    background: rgba(250, 249, 245, 0.94);
    border: 2px solid var(--border-warm, #e8e6dc);
    border-radius: 14px;
    margin-bottom: 40px;
    align-items: center;
    font-size: 14px;
    box-shadow: 0 2px 8px rgba(20,20,19,0.04);
    position: sticky;
    top: 16px;
    z-index: 50;
    backdrop-filter: blur(8px);
  }
  .page-nav .lbl {
    color: var(--text-3, #87867f);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    margin-right: 8px;
    font-weight: 600;
  }
  .page-nav a {
    padding: 8px 16px;
    border-radius: 10px;
    text-decoration: none;
    color: var(--text-2, #4d4c48);
    font-weight: 500;
    transition: all .15s;
    border: 1.5px solid transparent;
  }
  .page-nav a:hover {
    background: var(--bg-tint, #f0eee5);
    color: var(--brand, #c96442);
    border-color: var(--border-warm, #e8e6dc);
  }
  .page-nav a.cur {
    background: var(--brand, #c96442);
    color: #fff;
    border-color: var(--brand, #c96442);
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(201, 100, 66, 0.3);
  }
  .page-nav .sep { color: var(--border-warm, #e8e6dc); margin: 0 4px; font-weight: 300; }
  .page-nav .spacer { flex: 1; }
  .page-nav .meta {
    color: var(--text-3, #87867f);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.5px;
  }
</style>
```

## Nav HTML 结构

每页生成时 current 项无 href + `class="cur"`,其它项有 href:

```html
<!-- 在 page 1 上 -->
<nav class="page-nav">
  <span class="lbl">PAGE</span>
  <a class="cur">① 性能 · 代码</a>
  <span class="sep">·</span>
  <a href="report-details.html">② 记忆 · 画像 · 分类</a>
  <span class="spacer"></span>
  <span class="meta">v7 · 2026-06-05 · ML/DS 归档</span>
</nav>

<!-- 在 page 2 上 -->
<nav class="page-nav">
  <span class="lbl">PAGE</span>
  <a href="report.html">① 性能 · 代码</a>
  <span class="sep">·</span>
  <a class="cur">② 记忆 · 画像 · 分类</a>
  <span class="spacer"></span>
  <span class="meta">v7 · 2026-06-05 · ML/DS 归档</span>
</nav>
```

## 拆分脚本(从单 HTML 切出来)

```python
"""拆 1 个 HTML 成 2 页,基于 <!-- BEGIN: X --> ... <!-- END: X --> 标记"""
import re

with open('/home/resley/report.html', encoding='utf-8') as f:
    html = f.read()

# 提 head + <body><div class="wrap">
header_match = re.search(r'^(.*?<div class="wrap">)', html, re.DOTALL)
head_block = header_match.group(1)

# 提 footer + close
footer_match = re.search(r'(</div>\s*<!-- BEGIN: FOOTER -->.*$)', html, re.DOTALL)
footer_block = footer_match.group(1)

def extract(name):
    m = re.search(rf'<!-- BEGIN: {name} -->(.*?)<!-- END: {name} -->', html, re.DOTALL)
    return m.group(0) if m else ''

hero = extract('HERO')
sec01 = extract('SECTION-01')  # 性能
sec02 = extract('SECTION-02')  # 代码改动
sec00 = extract('SECTION-00')  # memory
sec00b = extract('SECTION-00B')  # persona
sec03 = extract('SECTION-03')  # coverage

# nav css 在 _nav_css 字符串里(从 references/multi-page-split-recipe.md 复制)
nav_css = """..."""

def nav(current):
    p1 = '<a class="cur">① 性能 · 代码</a>' if current == 1 else '<a href="report.html">① 性能 · 代码</a>'
    p2 = '<a class="cur">② 记忆 · 画像 · 分类</a>' if current == 2 else '<a href="report-details.html">② 记忆 · 画像 · 分类</a>'
    return f'''<nav class="page-nav">
  <span class="lbl">PAGE</span>
  {p1}<span class="sep">·</span>{p2}
  <span class="spacer"></span>
  <span class="meta">v7 · 日期 · 副标</span>
</nav>'''

# Title 注入 nav css
head_p1 = head_block.replace('<title>原标题</title>',
                              '<title>① 性能 · 代码 — 报告 v7</title>') \
                     .replace('</style>\n</head>', '</style>\n' + nav_css + '\n</head>')
head_p2 = head_block.replace('<title>原标题</title>',
                              '<title>② 记忆 · 画像 · 分类 — 报告 v7</title>') \
                     .replace('</style>\n</head>', '</style>\n' + nav_css + '\n</head>')

page1 = head_p1 + '\n\n' + nav(1) + '\n\n' + hero + '\n\n' + sec01 + '\n\n' + sec02 + '\n' + footer_block
page2 = head_p2 + '\n\n' + nav(2) + '\n\n' + hero + '\n\n' + sec00 + '\n\n' + sec00b + '\n\n' + sec03 + '\n' + footer_block

with open('/home/resley/report.html', 'w', encoding='utf-8') as f: f.write(page1)
with open('/home/resley/report-details.html', 'w', encoding='utf-8') as f: f.write(page2)

print(f"page1: {len(page1):,} chars")
print(f"page2: {len(page2):,} chars")
```

## Pitfalls

- **nav 不加 sticky → 用户滚到底找不到回页 1 的入口**。`position: sticky; top: 16px; z-index: 50` 必加
- **nav 不加 backdrop-blur → sticky 后跟下面内容糊在一起**。`backdrop-filter: blur(8px)` + 半透明 bg 必加
- **nav 偏弱:激活态光看颜色不够** → 加 `box-shadow: 0 1px 4px rgba(brand, 0.3)` 让激活按钮"浮起来"
- **2 页用同 hero,但数字变了忘了同步** → 拆完 grep 一遍核心数字,两页要一致
- **page 2 多余内容(归档的分类提及)忘了删** — 如:删 mlops 后 persona 卡片里 "TIER 2 · ML 研究" 那张卡要整张删,不是改字
- **footer 写死 v6 → 拆完仍是 v6** — 拆前先把 footer 改到最新版本,否则两页都带旧 footer
- **共享 head 块时,`<title>` 替换要精确** — head 里有多处 `<title>`(meta, og:tag, twitter:tag)别都改成第一页标题。只改 `<title>...</title>` 那一个,og/twitter tag 保持通用

## 发布与验证

两页都通过 `integration/publish-html` 发布到同一项目目录：

- 主页：`https://www.nexora.restry.cn/static/<project>/report.html`
- 详情：`https://www.nexora.restry.cn/static/<project>/report-details.html`

覆盖前备份；临时上传后原子替换；逐页核对 SHA-256、HTTP 200、标题、导航激活态、跨页链接与 JavaScript 交互。两页都要用真实浏览器打开，并点击非默认导航。
