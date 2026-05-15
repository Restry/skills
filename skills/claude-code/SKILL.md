---
name: claude-code
description: Delegate coding tasks to Claude Code (Anthropic's CLI agent). Use for building features, refactoring, PR reviews, and iterative coding. Requires the claude CLI installed.
version: 2.4.0
author: Hermes Agent + Teknium
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Anthropic, Code-Review, Refactoring, PTY, Automation]
    related_skills: [codex, hermes-agent, opencode]
---

# Claude Code — Hermes Orchestration Guide

派 CC 干活前先看本文铁律 + Pitfalls，细节按 References 表按需 `skill_view` 加载。

## 🔐 凭据 = 门神（vault）

所有 token / API key / DB 密码 / OAuth secret 走门神。**禁止读 `~/.credentials/.env`**（已废弃）。

```bash
vault project show <slug>     # 看项目所有 secret
vault export -p <slug>        # 导成 .env 格式
vault inject template > out   # 渲染 vault://path 模板
vault get <slug>/<KEY>        # 单值
```

环境后缀：无后缀=prod / `__local`=本地 dev / `__test` `__remote` `__cloud`=其他。

## ⭐ 默认参数（爸爸不明说就照用）

```
--model claude-opus-4.7-1m-internal --effort high --dangerously-skip-permissions
```

- 一律全名 `claude-opus-4.7-1m-internal`，**禁用 `--model opus` alias**（解析到非 internal 通道，只支持 `effort=medium`）。
- 用户说"用 sonnet"才换 sonnet。
- 长任务 `--max-turns 200~300` + `notify_on_complete=true` 后台跑。

## Prerequisites

`npm install -g @anthropic-ai/claude-code` → `claude` 首次浏览器登录 → `claude doctor` 自检。

## Two Orchestration Modes

### Mode 1: Print (`-p`) — 首选

```
terminal(command="claude -p '<task>' --model claude-opus-4.7-1m-internal --effort high --dangerously-skip-permissions --max-turns 50", workdir="/path", timeout=600)
```

一次性跑完即退，无对话框。详见 `references/print-mode.md`（JSON / schema / bare / session continuation）。

### Mode 2: Interactive PTY via tmux — 多轮

需 tmux 编排（`send-keys` + `capture-pane`）。详见 `references/interactive-tmux.md`。

## 📚 Prompt Playbook

派 CC 卡住时按需 grep `references/cc-playbook/`：

- `cc-anti-procrastination-prompt.md` — 治拖延 / 返问 / sub-delegating
- `cc-frontend-e2e-pitfalls.md` — browser-agent 4822 testing
- `cc-prompt-explicit-export-commands.md` — shell-ready `export X="$(vault get ...)"`
- `cc-prompt-grep-and-verify.md` — grep + 机器可验收
- `cc-review-verify-fix-loop.md` — review → 独立验证 → fix
- `claude-code-stepwise-refactor.md` — 大型多文件 refactor 切分中继

## Top Pitfalls

1. **Print 模式开放问题=静默退出** —— prompt 留任何"A 还是 B?需要 X 吗?"CC 一行不改就退只回疑问。**末尾必加** `**禁止返问**，所有方案选择已在上面，有歧义自己拍板写进 commit message`。
2. **CC 报"根因/回滚"别盲信** —— 派 CC 前 `git stash -u` 无关改动；CC 报根因前必须独立 query prod / curl 验。
3. **`--max-turns` 仅 print 模式生效**；`--max-budget-usd` 最小 ~$0.05。
4. **Context > 70% 质量明显掉** —— `/context` 查，`/compact` 或 `/clear` 救。
5. **CLAUDE.md trap** —— CC 默认加载 `./CLAUDE.md` + `~/.claude/CLAUDE.md`，纯净 prompt 用 `--bare`。
6. **后台 tmux 会一直在** —— 完事 `tmux kill-session -t <name>`。

完整 14 条见 `references/cost-and-pitfalls.md`。

## References（按需加载，不要一次全读）

| 文件 | 何时加载 |
|---|---|
| `references/cli-reference.md` | 查具体 flag / subcommand / env vars |
| `references/print-mode.md` | `-p` 跑 JSON / streaming / schema / session continuation |
| `references/interactive-tmux.md` | tmux 启动 / dialog 处理 / worktree / 并发 |
| `references/slash-commands.md` | `/compact` `/review` `/model` 等 + 快捷键 |
| `references/autonomous-loops.md` | `/goal` `/loop` Stop hook auto-mode |
| `references/hooks.md` | 8 类 hook + 安全模板 |
| `references/mcp.md` | 接 MCP server (GitHub/Postgres/Puppeteer) |
| `references/claude-md-and-rules.md` | CLAUDE.md / `.claude/rules/` / 自定义 subagent |
| `references/cost-and-pitfalls.md` | 省钱 11 条 + 完整 14 条 pitfalls |
| `references/hermes-prompt-recipe.md` | **派 CC 前必看**：prompt 骨架 + 反模式 |
| `references/cc-playbook/*.md` | 拖延/幻觉/忽略凭据时按情况查 6 个模板 |
| `references/cc-pushback-syndrome.md` | CC 推回任务的反模式识别 |
| `references/hermes-orchestration-gotchas.md` | 其他派 CC 踩坑细节 |
