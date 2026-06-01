---
name: recap-site-mvp-deployer
description: 把一份 markdown 汇报/简报变成多页 HTML SPA 站点(Anthropic 暖米色风 + Lucide 线图标 + 杂志列表式目录),本地 headless chrome 自检视觉,zip 上线 mvp-deployer。专治"老板要一份既好看又能点的汇报站"。爸爸 `~/Desktop/AI-半年汇报-2026H1.md` → `https://recap.mvp.restry.cn` 的实操套路。
metadata:
  hermes:
    tags: [html, deck, recap, presentation, claude-design, mvp-deployer, anthropic-style]
    related_skills: [claude-design, html-artifact-output, mvp-deployer, headless-chrome-screenshot-verify, sync-skill]
---

# recap-site-mvp-deployer

把长 markdown 汇报变成多页 HTML SPA 站,部署到 `*.mvp.restry.cn`。爸爸 2026-06-01 用这套出了 `recap.mvp.restry.cn`(7 页 + 1 个项目详情,40KB)。

## 触发条件

- 爸爸说"把这个汇报做成 HTML / 网页 / 站点"
- 要"既能点又好看",要分页/带导航/能切换
- 老板汇报场景,需要发链接而不是发文件
- 已经有 markdown 草稿想升级展示形态

## 设计基调(都是踩过坑后定下来的)

| 维度 | 默认 | 为什么 |
|---|---|---|
| 风格 | **Anthropic 暖米色** (cream `#f5f1ea` + ink `#2b2620` + accent `#cc785c`) | 跟爸爸的 menshen-ui 一致,统一品牌 |
| 字体 | Source Serif 4(中文回退 Source Han Serif SC)+ Inter(标签/导航)+ JetBrains Mono(代码) | 杂志感 / 严肃 / 不像 SaaS |
| 图标 | **Lucide CDN**(`unpkg.com/lucide@latest`)`<i data-lucide="name"></i>` + `lucide.createIcons()` | 千万别用 emoji(被爸爸骂过"太低级"),也别手写 SVG sprite(渲染成黑块) |
| 目录页 | **杂志列表式**(序号 / 标题 / 描述 / 跳转 四列),禁用 bento 卡片网格 | 8/4/6/6 不对称栅格内容跟不上会"虚胖",列表式干净 |
| 卡片内信息密度 | 每条 ≥ 名字 + 描述 + chips(链接 + 标签)。**chips 区分**:实线=链接,虚线=元信息 | 单条只有一句话会显得空 |
| 高亮事件 | 单独 `.highlight` class + 半透明背景色块 | 让 Hermes 迁移 / 飞书桥这种里程碑跳出来 |

## 站点骨架(标配 6+N 页)

```
index.html      首页 hero + 杂志列表目录(5 章)
timeline.html   时间线,三段时期(苔绿/橙红/远山蓝) + 圆点节点
projects.html   项目矩阵,主力分两组 + 实验紧凑表
stories.html    名场面,引文 + 沉淀框(两色 blockquote 区分爸爸 vs AI)
way.html        工作方式,演化流程 + 5 步法 + N 条铁律
data.html       数据基底,大数字 + 数据源表 + 排行表
project-<name>.html  项目详情(下钻),Hero+CTA + 5 抽象 + 技术栈 + Milestone + Commit 表
```

## 实操步骤

### 1. 准备工作目录 + 配色变量

```bash
mkdir -p /tmp/recap-site && cd /tmp/recap-site
```

每个 HTML 文件顶部统一这套 CSS root vars:

```css
:root{
  --cream:#f5f1ea; --cream-2:#ece6db;
  --ink:#2b2620; --ink-soft:#5b544a; --muted:#8a8378;
  --line:#d9d2c4; --accent:#cc785c; --accent-soft:#e8c4b3;
  --era-1:#7a8a6b;  /* 苔绿 */
  --era-2:#cc785c;  /* 橙红 */
  --era-3:#6f7d99;  /* 远山蓝 */
}
```

### 2. 全站统一 nav(每页复制粘贴)

```html
<nav class="top">
  <div class="inner">
    <a href="index.html" class="brand">
      <i data-lucide="terminal"></i>小薯条<span style="color:var(--accent)">.</span>
    </a>
    <ul class="sans">
      <li><a href="index.html">首页</a></li>
      <li><a href="timeline.html">时间线</a></li>
      ...
    </ul>
  </div>
</nav>
<!-- 页尾必加 -->
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<script>lucide.createIcons();</script>
```

`active` class 切换高亮当前页。

### 3. 写每页 → headless screenshot → vision 自检 → 给爸爸看

不要憋大招一次性出全站。**每页一轮:写 → 截图 → 自检 → 爸爸确认**。

```bash
# 单页截图(用于内容确认)
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --headless --disable-gpu --hide-scrollbars \
  --window-size=1440,1400 \
  --screenshot=/tmp/recap-site/_shot_page.png \
  --virtual-time-budget=8000 \
  file:///tmp/recap-site/page.html

# 全页长截图(用于整体节奏)
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --headless --disable-gpu --hide-scrollbars \
  --window-size=1440,5500 \
  --screenshot=/tmp/recap-site/_shot_page_full.png \
  --virtual-time-budget=8000 \
  file:///tmp/recap-site/page.html

# 压缩成 jpg(vision_analyze 喜欢小图,< 8000px 长边)
sips -Z 1600 -s format jpeg -s formatOptions 75 \
  /tmp/recap-site/_shot_page_full.png \
  --out /tmp/recap-site/_shot_page_full.jpg

# 给爸爸看
# MEDIA:/tmp/recap-site/_shot_page_full.jpg
```

**Lucide 加载要时间**:`--virtual-time-budget=8000`(8 秒)足够,低了会拍到没 icon 的页。

### 4. 部署:zip + mvp-deployer + node type + python http.server

✅ **可工作的 manifest**(踩过 3 次坑总结):

```json
{
  "project": "recap",
  "type": "node",
  "port": 3815,
  "host": "recap.mvp.restry.cn",
  "run": "python3 -m http.server 3815",
  "preserveData": false,
  "smokeDisabled": true
}
```

❌ **不要这样**:
- `type:"static"` → mvp-deployer 不起 web server,Caddy 反代到空端口 → 502
- `type:"python"` → 强行用 `.venv/bin/python3`,不存在 → PM2 启动失败
- `smoke` 默认开 → 新 host SSL 证书签发期内会 EPROTO,拿 `smokeDisabled:true` 绕开
- 端口要避开 inventory `used` 列表,先 `curl /api/inventory` 取 `next_suggested`

部署命令:

```bash
set -a; source ~/.credentials/.env 2>/dev/null; set +a   # 加载 MVP_DEPLOYER__TOKEN

cd /tmp/recap-site && rm -f _shot_*  # 截图别打包进去
zip -rq /tmp/recap.zip . -x '_shot*' '.*'

MANIFEST='{"project":"recap","type":"node","port":3815,"host":"recap.mvp.restry.cn","run":"python3 -m http.server 3815","preserveData":false,"smokeDisabled":true}'
curl -sS -X POST https://deploy.mvp.restry.cn/api/deploy \
  -H "Authorization: Bearer $MVP_DEPLOYER__TOKEN" \
  -F "file=@/tmp/recap.zip" \
  -F "manifest=$MANIFEST"
```

返回 `{taskId}`,轮询 `/api/deploy/tasks/<id>` 直到 `status:succeeded`。再 `curl https://<host>/` 验 200。

### 5. 后续增量更新 / 加数据源(本 skill 的核心价值)

爸爸加新数据源后(新 cron 输出 / 新项目 / 新对话指标 / 新名场面):

1. 抓新数据(SQL / git log / API / 飞书)
2. 找对应页面 patch(`timeline.html` 新加一条 / `projects.html` 新加一项 / `data.html` 更数字)
3. 跑 step 3 的 screenshot + vision 自检
4. **同一个 manifest 重发** → `POST /api/deploy` 覆盖。`preserveData:false` 不留旧文件。
5. 域名不变,URL 稳定可继续转发给老板

**别每次重写整站**。增量改 + 重发,Lucide CDN 不动,改的只是内容块。

## chips 的统一规范

```html
<!-- 实线 = 跳转链接 -->
<a class="chip" href="..." target="_blank">
  <i data-lucide="external-link"></i>外站
</a>
<a class="chip" href="project-x.html">
  <i data-lucide="arrow-right"></i>详情
</a>

<!-- 虚线 = 元信息标签 -->
<span class="chip kind">
  <i data-lucide="zap"></i>195 commits
</span>

<!-- 主 CTA(只在详情页 Hero 用一次) -->
<a class="chip primary" href="..." target="_blank">
  <i data-lucide="external-link"></i>访问生产
</a>
```

## 引文区分(stories.html 专用)

```css
/* 默认 = 爸爸说,橙色边 */
blockquote{border-left:3px solid var(--accent);background:rgba(204,120,92,.04)}
/* .bot = AI 说,灰色边 */
blockquote.bot{border-left-color:var(--ink-soft);background:rgba(43,38,32,.04)}
.speaker{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
```

## 必踩的坑

| 症状 | 根因 | 修 |
|---|---|---|
| 图标变黑块 / □ 占位框 | 用 emoji 或手写 SVG sprite | 换 Lucide CDN |
| 5 张同级卡片虚胖 | 8/4 + 6/6 不对称栅格 + 内容只两行字 | 改杂志列表式(grid: 56px 1fr 1.4fr auto) |
| vision 报 "缺失/空白" | virtual-time-budget 太低,Lucide 没加载完 | 拉到 8000ms |
| vision 拒绝长截图 | 长边 > 8000px | `sips -Z 1600` 缩到 ≤ 1600 |
| 部署 502 | type:static 不起服务 | type:node + run python http.server |
| 部署 PM2 .venv 找不到 | type:python | 同上 |
| 部署 smoke 失败 EPROTO | 新 host SSL 还没签 | smokeDisabled:true |

## 截图给爸爸看的标准格式

> 单页结构 + 详细截图同时给:
>
> MEDIA:/tmp/recap-site/_shot_page_top.jpg
> (顶部首屏 - 短描述)
>
> MEDIA:/tmp/recap-site/_shot_page_full.jpg
> (完整长截图 - 短描述)
>
> 结构:三行总结这页有什么
>
> A:满意,继续画下一页
> B:调整(说哪里)
> C:换风格

## 不要做的

- ❌ 不要 emoji 当图标(被骂过)
- ❌ 不要 bento grid(8/4/6/6 这种不对称栅格在同级内容上会塌)
- ❌ 不要憋大招一次出全站,逐页确认
- ❌ 不要每次重写整站,增量 patch + 重发
- ❌ 不要忘记 `lucide.createIcons()` 调用(纯 HTML 加载 lucide 不会自动渲染)
- ❌ chips / 标题 / 描述都贴满,不要稀稀拉拉
