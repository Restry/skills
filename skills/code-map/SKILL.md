---
name: code-map
description: 「代码地图」——用 gitnexus 把项目代码索引成知识图谱，改代码前先看影响面（谁调用了它、改了会炸哪里）。触发词：「代码地图」「上代码地图」「建代码地图」「给 XX 项目索引」「改之前看影响」「这函数被谁调用」「blast radius」「影响分析」「impact」「派 CC 改 X 之前」「新项目接 gitnexus」。爸爸说"上代码地图 / 给 XX 上代码地图"=本 skill。
---

# 代码地图（gitnexus）

把项目代码索引成图（函数/类/调用关系），改代码前先查"动这里会炸什么"。比 grep 准、比读代码快。

## 什么时候触发

爸爸说这些话时**必加载本 skill**：
- "给 XXX 项目建代码地图 / 上代码地图 / 索引一下"
- "改这个之前先看影响 / 看 blast radius / 看调用链"
- "派 CC 改 XXX，让它先看影响面"
- "这函数被谁调用？/ 这个改了会影响啥？"
- "新项目怎么接 gitnexus"

## 给新项目建地图（3 步）

```bash
# ① 首次索引（在仓库根目录）
zsh -ic 'nvm use 20.18 >/dev/null && cd ~/projects/<项目> && gitnexus analyze --embeddings --skills --force'
# 输出 "X nodes | Y edges | Z clusters | W flows" = 成功

# ② 验证（随便挑个核心函数）
zsh -ic 'nvm use 20.18 >/dev/null && cd ~/projects/<项目> && gitnexus impact <函数名>'

# ③ 加 .gitignore
echo '.gitnexus/' >> ~/projects/<项目>/.gitignore
```

CC 那边 MCP 已经全局注册（user scope），任何 repo 里启动 CC 自动认当前 cwd 的 `.gitnexus/`。索引完直接派 CC 就能用，无需重新 setup。

## 派 CC 时的 prompt 加料

```
改 <target> 前，先调 mcp gitnexus.impact <name>：
- HIGH risk 或 affected_processes > 5 → 先回报方案等我确认
- LOW/MEDIUM → 直接改，commit message 里列 affected files
```

## Hermes 自己用（cli）

```bash
# 影响面（最常用）
gitnexus impact <函数名>            # blast radius，HIGH/MED/LOW

# 调用关系
gitnexus context <函数名>           # 谁调它 / 它调谁

# git diff 影响
gitnexus detect-changes             # 改完代码看哪些 flow 中招

# 语义/模糊搜索（1.6.4-rc.71 起可用，要 --embeddings 索引过）
gitnexus query "user binding finalize" -r <repo>
# ⚠️ query 局限实测:
#   - 中文 query 全 0(嵌入模型 all-MiniLM 是英文)
#   - 永远夹带 selftest.py / *-selftest.mjs 噪声
#   - 强关键词英文(如 "oauth callback")带不带 emb 打平,bm25 够用
#   - 真受益:半语义("user binding repo")+ 精确符号名("upsertBinding")
#   - 不要替代 impact/context 算 blast radius——query 是模糊的

# 精确查询（cypher）
gitnexus cypher 'MATCH (f:Function) WHERE f.name CONTAINS "finalize" RETURN f.name, f.filePath LIMIT 10'
```

> **每条命令前必须 `nvm use 20.18`**。爸爸 zshrc 默认 Node 22，22/25 上 native 模块段错误。

## Linux 远端机安装（爸爸的 192.168.1.235 等）

macOS brew/nvm 一把梭，**Linux 远端常踩 3 个连环坑**（2026-05-07 在 192.168.1.235 实战）。
前提：node 20.18 已就绪（先按官方文档装 nvm + `nvm install 20.18`）。

```bash
# ① 切官方 npm 源 — 远端常配 npmmirror（淘宝镜像），audit endpoint 返回 404
#    导致 npm 整个 install 流程 exit 7
npm config set registry https://registry.npmjs.org/

# ② 装 gitnexus 必须 --ignore-scripts
#    onnxruntime-node postinstall 去 api.nuget.org 下 native，国内/受限网络
#    ECONNRESET，整体失败
npm i -g gitnexus@1.6.4-rc.71 --no-audit --no-fund --ignore-scripts

# ③ ②跳了所有 postinstall，但 @ladybugdb/core 的 native 是必须的
#    不重建 → 运行报 ERR_DLOPEN_FAILED（impact/context/cypher 全挂）
GN_DIR=$(npm root -g)/gitnexus
cd $GN_DIR && npm rebuild @ladybugdb/core
```

**已知限制**：`gitnexus analyze --embeddings` 在 Linux 上不可用（onnxruntime native 没构建）。
但 `impact` / `context` / `cypher` / `detect-changes` 全部可用，已覆盖 80% 场景（爸爸日常只用 impact）。

## 坑 / 铁律

> **调试 gitnexus 输出**:进度条用 `\r` 重写,`tail` 看不到真错。必用 `script -q /tmp/gn.log gitnexus ...` 或 `2>&1 \| tr '\r' '\n'` 录。stderr 经常空,真错混在 stdout 进度条里。"EXIT=1 + 无 meta.json" 一般是嵌入到 99.7% 静默崩。

| 症状 | 原因 | 修 |
|---|---|---|
| `analyze --embeddings` 在 **1.6.3** EXIT=1 没 meta.json | 1.6.3 ladybugdb 提交事务 bug，**和节点数无关** | **升 `gitnexus@1.6.4-rc.71`**(已实测 wx-gateway/5min-ai 都跑通 embeddings + query)。装法：`zsh -ic 'nvm use 20.18 && npm i -g gitnexus@1.6.4-rc.71'` |
| `gitnexus query` 报 `Corrupted wal file` | 上一次 embedding 崩溃留下半写 WAL → FTS 扩展加载失败 | `rm -rf .gitnexus/` 重跑无 embeddings 的 `analyze --force` |
| `gitnexus query/impact` 报 `Multiple repositories indexed` | 全局 registry 有多个同名/重名 repo | 加 `-r <name>`，`gitnexus list` 看可用名 |
| `dlopen ... incompatible architecture` | 系统 node v25 加载 v20 编译的 native | nvm use 20.18 |
| `status` 说未索引但 `.gitnexus/lbug` 存在 | embeddings 崩，meta.json 没写 | 不加 embeddings 重跑 |
| 个别 .py 文件报 `scope extraction failed: Invalid argument` | tree-sitter 偶发 | 忽略，不影响整体 |
| 改完代码不用重索引 | gitnexus 读 git diff | `detect-changes` 即可 |
| 真要重建 | 覆盖 `.gitnexus/` | `gitnexus analyze --force` |

## CC MCP 配置（已做，新机器迁移参考）

`gitnexus setup` 默认 shebang 走系统 node 会爆架构错。手动用绝对路径注册：

```bash
claude mcp remove gitnexus -s user 2>/dev/null
claude mcp add gitnexus -s user -- \
  /Users/leway/.nvm/versions/node/v20.18.3/bin/node \
  /Users/leway/.nvm/versions/node/v20.18.3/lib/node_modules/gitnexus/dist/cli/index.js mcp
claude mcp list | grep gitnexus  # 应 ✓ Connected
```

`~/.claude/settings.json` 里 `gitnexus-hook.cjs` 的 PreToolUse/PostToolUse `command` 也得手动改成 `/Users/leway/.nvm/versions/node/v20.18.3/bin/node ...`，否则 hook 静默失败。

CC 那边 `gitnexus setup` 已自动装了 7 个 `gitnexus-*` skill 到 `~/.claude/skills/`，CC 自己会查，prompt 里点名"用 gitnexus impact"就行。

## embeddings 实测收益（A/B 对比，wx-gateway）

带 vs 不带 `--embeddings`，5 类 query 命中:

- **精确符号**(`upsertBinding`): 带 emb top-1 命中,不带要翻到第 3 — **明显提升**
- **半语义**(`user binding repo`): 不带完全跑偏到 selftest,带 emb 第 2 命中 — **明显提升**
- **强关键词英文**(`wechat oauth callback handler`): 打平,bm25 已经够
- **中文 query**: **两种状态全 0 结果**(嵌入模型是英文 all-MiniLM)

**结论**: embeddings 值得开(索引时间 4s → 55s 一次性成本),但别指望它读中文。改代码前算 blast radius 必须用确定性的 `impact`/`context`，`query` 只是模糊匹配。

## 当前已索引项目

- `~/projects/clawline/platform` — 7305 / 14675 / 308 / 300
- `~/projects/wx-gateway` — 2638 / 5098 / 51 / 225
- `~/projects/PackHorizon` — 3469 / 5459 / 65 / 226
- `~/projects/nexora-loop` — 2098 / 3637 / 47 / 175
- `~/projects/5min-ai` — 4 / 109 / 5 / 5
- `~/projects/image-studio` — 2470 / 3976 / 76 / 106

(格式: nodes / edges / clusters / flows，全部带 embeddings + skills)

## 版本

`gitnexus@1.6.4-rc.71`（macOS arm64 + Node 20.18）。**不要降回 1.6.3**——embeddings 在 1.6.3 必崩。

新建项目后在这里追加一行。

## 在新机器（特别是 Linux / 内网）装 gitnexus 的踩坑顺序

按这个顺序一把过，**少一步必报错**。完整命令见 `references/install-on-new-machine.md`。

**4 个连锁坑**（缺哪步炸哪步，已实战验证 Ubuntu 24.04 内网）：
1. **npmmirror audit endpoint 404** → npm exit 7。**修**：切官方源 `npm config set registry https://registry.npmjs.org/` + `--no-audit`
2. **`onnxruntime-node` postinstall 拉 `api.nuget.org` native，国内/内网必 ECONNRESET** → 包装到一半崩。**修**：`--ignore-scripts`
3. **`--ignore-scripts` 把 ladybugdb 的 native 也跳了** → 运行时 `ERR_DLOPEN_FAILED`。**修**：`cd $(npm root -g)/gitnexus && npm rebuild @ladybugdb/core`（这个国内能装）
4. **系统已有 npm global prefix** → nvm warning。**修**：`nvm use --delete-prefix 20.18`

**已知限制**：跳了 onnxruntime → embeddings (`analyze --embeddings` / `query`) 用不了。但 **`impact` / `context` / `cypher` / `detect-changes` 全可用**——这才是核心功能，足够派 CC 做 blast radius 分析。要 embeddings 需单独从能装机拷 `node_modules/onnxruntime-node/bin/napi-v3/<os>/<arch>/*.node`（未实战验证）。
