# Hermes Prompt Recipe — 派 CC 实战骨架

爸爸验证过的 prompt 模板 + 8 条关键经验 + 反模式表 + 配套技能。**何时加载**:开始写新 prompt 派 CC 跑 milestone / hotfix / 多文件改动时,先看这个再动笔。

写给 CC 的 prompt 用 `write_file` 存到 `/tmp/<project>_<phase>_prompt.md`，再 `cat ... | claude --print ...` 喂。**不要把 prompt 直接拼进 shell 命令**——多行 + 中文 + 反引号会被 zsh 吃。

prompt 文件骨架（`MAX_THINKING_TOKENS=10000` + opus-4.7 medium 实测稳定，10k+ token 单 prompt 跑 ~3-10 分钟，单 commit 推完）：

```markdown
# 项目名 — 阶段名: 一句话目标

Repo: `/abs/path`, branch `main`. HEAD = `<上一个 commit hash>`.
读 `docs/<相关 spec>.md`，了解上下文。**不要改 `prototype/` / `docs/`**。

---

## 范围

✅ 做：
- 具体功能 1（带文件路径）
- 具体功能 2

❌ **不做**（下个阶段的事，今天不要碰）：
- 邻近功能 X（很容易顺手做）
- 邻近功能 Y

---

## 实现规范

- 用 [包名] 不要装新依赖
- API 错误统一 `{ error: { code, message } }`
- DB 改动用 `npx prisma migrate dev --name xxx`，不要手写 SQL

---

## 验收

1. `npm run build` 0 error
2. README 加本阶段节
3. 单 commit：`<conventional commit msg>`
4. push origin main，输出 `git log --oneline -3`

## 不动的（重点防越界）

- prisma schema（绝对不要改）
- lib/auth/* 现有签名
- 上阶段已通过 e2e 的接口
```

## 关键经验（每条都踩过坑）

1. **❌ 清单比 ✅ 清单更重要** —— 多 milestone 项目里 CC 经常顺手把"邻近功能"也做了，导致单 commit 巨大、review 困难、回滚成本高。明确 ❌ 是 contract。
2. **每片任务串一个 commit hash** —— prompt 开头写 `HEAD = <hash>`，结尾要求 `git log --oneline -3` 输出，方便 controller agent 验证 CC 跑的是不是上一片刚 push 的代码。
3. **指明禁用** —— `不要 npm run dev`（让 controller 部署+e2e 验）、`不要 playwright/puppeteer`、`不要在 CI 里跑真实 API 调用`。CC 默认会做这些"贴心"操作。
4. **要求输出 hash 验证** —— 末尾 `输出 git log --oneline -3` 让 CC 主动报 commit。controller 看到 hash 就知道 push 成功。
5. **指明用 `--no-save`** —— CC 装 native binding（lightningcss-darwin-arm64 之类）解决环境差异时容易污染 package.json，prompt 里说明"用 `npm i --no-save`"。
6. **后台跑 + watch_patterns** —— 用 hermes 的 `terminal(background=True, notify_on_complete=True, watch_patterns=["fatal", "400 "])` 派遣，用户可以同时聊别的，CC 完事自动通知。
7. **遇到根因不明的 5xx，先看 PM2 日志再写 hotfix prompt** —— 不要让 CC 盲改。日志里 `Azure 401` 这种线索，你先定位再喂 prompt 比 CC 自己摸索快 10 倍。
8. **hotfix prompt 短小** —— 单文件改动用 `--max-turns 80` 即可，不需要 400。

## 反模式

| ❌ | ✅ |
|---|---|
| 把整个 monorepo 一锅 prompt | 切 4-6 片，每片 5-10k token prompt + 1 commit |
| prompt 里只写"做什么"不写"不做什么" | 双清单 ✅/❌ |
| 让 CC 自己 deploy + e2e | controller 接管部署/验证，CC 只负责代码 |
| 让 CC 通过 UI 操作 debug | CC 读代码加 log，UI 验证 controller 用截图 + vision 干 |
| 报错就 fallback `--model sonnet` | 先加 `MAX_THINKING_TOKENS=10000`，95% 情况 opus 加 env 就好 |

## 配套技能

- 多 milestone MVP 节奏：见 `subagent-driven-development` 的 "Hermes-as-Controller 模式"
- 验证侧：`headless-chrome-screenshot-verify`
