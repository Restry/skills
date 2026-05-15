---
name: claude-code
description: Delegate coding tasks to Claude Code (Anthropic's CLI agent). Use for building features, refactoring, PR reviews, and iterative coding. Requires the claude CLI installed.
version: 2.3.0
author: Hermes Agent + Teknium
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Anthropic, Code-Review, Refactoring, PTY, Automation]
    related_skills: [codex, hermes-agent, opencode]
---

# Claude Code — Hermes Orchestration Guide

Delegate coding tasks to [Claude Code](https://code.claude.com/docs/en/cli-reference) (Anthropic's autonomous coding agent CLI) via the Hermes terminal. Claude Code v2.x can read files, write code, run shell commands, spawn subagents, and manage git workflows autonomously.

**用法**:派任务前先看本文铁律(凭据/默认参数/Two Modes/Pitfalls/Rules),需要细节按下面 References 表按需 `skill_view` 加载,**不要一次全读**。

## 🔐 凭据 = 门神（vault）

本流程涉及的所有 token / API key / DB 密码 / OAuth secret 都在门神。**禁止读 `~/.credentials/.env`**（已废弃）。

```bash
vault project show <slug>     # 看项目所有 secret + 严重度
vault export -p <slug>        # 导成 .env 格式
vault inject template > out   # 渲染 vault://path 模板
vault get <slug>/<KEY>        # 单值
```

环境约定：
- **prod 默认值**（无后缀）= 部署到 mvp-deployer / 生产 host 用
- **`__local` 后缀** = 本地 dev（如 192.168.1.235 局域网 PG）
- **`__test` / `__remote` / `__cloud`** = 其他环境

## ⭐ Daddy 默认参数（除非用户明确说别的，一律照用）

```
--model claude-opus-4.7-1m-internal --effort high --dangerously-skip-permissions
```

**模型选择**：
- **首选 `claude-opus-4.7-1m-internal`**（1M context，internal 通道）。effort 全档位放开：`low` / `medium` / `high` / `xhigh` / `max` 全部能跑（实测 2026-04-29 一遍过）。**唯一不支持 `auto`**——CLI 直接拒：`option '--effort <level>' argument 'auto' is invalid`。
- **慎用 `claude-opus-4-7`**（非 internal）：只允许 `--effort medium`，传别的 Vertex `400 invalid_reasoning_effort`；且 medium 还会偶发 `thinking: Input tag 'adaptive' ...`，需 `MAX_THINKING_TOKENS=10000` 强制 enabled。爸爸不明说就别用这个。

**铁律**：
- 默认档位 `high`；爸爸说"思考最深/最强"才上 `xhigh` 或 `max`；快速验证用 `low`/`medium`。
- 用户说"用 sonnet 跑"才换 sonnet；说"快点/便宜点"再考虑 haiku。
- 长任务用 `--max-turns 200~300`，配 `notify_on_complete=true` 后台跑。

## Prerequisites

- **Install:** `npm install -g @anthropic-ai/claude-code`
- **Auth:** run `claude` once to log in (browser OAuth for Pro/Max, or set `ANTHROPIC_API_KEY`)
- **Console auth:** `claude auth login --console` / **SSO:** `claude auth login --sso`
- **Check:** `claude auth status` · `claude doctor` · `claude --version` (v2.x+) · `claude update`

## Two Orchestration Modes

Hermes 与 CC 有两种根本不同的交互方式。按任务选:

### Mode 1: Print Mode (`-p`) — Non-Interactive (PREFERRED)

一次性跑完即退,无 PTY 无对话框,自动化首选。

```
terminal(command="claude -p 'Add error handling to all API calls in src/' --allowedTools 'Read,Edit' --max-turns 10", workdir="/path/to/project", timeout=120)
```

**用于**:一次性编码 / CI / `--json-schema` 结构化抽取 / 管道输入 / 不需要多轮对话。

详见 `references/print-mode.md` (JSON / streaming / bidirectional / session continuation / bare / fallback)。

### Mode 2: Interactive PTY via tmux — Multi-Turn

完整对话 REPL,可用 slash commands,**必须 tmux 编排**(`send-keys` 输入 + `capture-pane` 监控)。两个对话框要专门处理:trust 直接 Enter,permissions 需 Down→Enter。

```
terminal(command="tmux new-session -d -s claude-work -x 140 -y 40")
terminal(command="tmux send-keys -t claude-work 'cd /path && claude --dangerously-skip-permissions \"your task\"' Enter")
terminal(command="sleep 4 && tmux send-keys -t claude-work Enter")          # trust
terminal(command="sleep 3 && tmux send-keys -t claude-work Down && sleep 0.3 && tmux send-keys -t claude-work Enter")  # permissions
terminal(command="sleep 15 && tmux capture-pane -t claude-work -p -S -50")
```

详见 `references/interactive-tmux.md` (完整 dialog 处理 / worktree / parallel sessions / TUI 状态读法)。

## 📚 Prompt Playbook（派 CC 心法集合）

派 CC 卡住时(拖延/幻觉根因/忽略凭据)按需 grep `references/cc-playbook/`,6 个 battle-tested 模板:

- `cc-anti-procrastination-prompt.md` — defeat CC 拖延 / 返问 / sub-delegating
- `cc-frontend-e2e-pitfalls.md` — browser-agent 4822 testing pitfalls
- `cc-prompt-explicit-export-commands.md` — 给 shell-ready `export X="$(vault get ...)"`,别写散文
- `cc-prompt-grep-and-verify.md` — grep + 机器可验收 > 文件清单 + commit msg
- `cc-review-verify-fix-loop.md` — review → 独立验证 → fix (防 static-analysis 幻觉)
- `claude-code-stepwise-refactor.md` — 大型多文件 refactor 切分中继

按需加载:`skill_view('claude-code', file_path='references/cc-playbook/<file>')`。

## 关键 Pitfalls(高优先级,详细见 cost-and-pitfalls.md)

1. **`--print` 模式静默"问一句就退"** —— prompt 里留任何开放性选择(走 A 还是 B?是否需要 X?请确认)CC 经常一行不改就退,只回一句疑问且会覆盖前面所有 thinking log。**修法**:prompt 末尾必须明令 `**禁止返问**，所有方案选择已在上面给出，有歧义自己拍板把决定写进 commit message`。2026-05-12 INTERNAL_TOKEN_SECRET 合并任务踩过两次。
2. **CC 报"根因 X / smoke fail / 回滚"时别盲信,独立验 prod** —— 2026-05-13 派 selftest cleanup,CC zip 整个 working tree(含 11 个未 commit 文件)→回滚→脑补"prod DB 缺列",实际两实例 prod DB 都有该列。**修法 A**:CC 报根因前 controller 必须独立 query prod DB / curl prod 验。**修法 B**:派 CC 前 `git stash -u` 无关改动,zip 只带 git HEAD 干净版本。
3. **`--dangerously-skip-permissions` 对话框默认 "No, exit"** —— 必须 Down→Enter。print 模式 (`-p`) 直接跳过该对话框。
4. **`--max-turns` 仅 print 模式生效**,interactive 忽略。`--max-budget-usd` 最小 ~$0.05(system prompt cache 创建成本)。
5. **interactive 模式必须 tmux** —— 单 `pty=true` 能跑但无法监控/插入,失去 orchestration 能力。
6. **`--json-schema` 必须给够 `--max-turns`** —— CC 要先读文件再产 schema,多轮才行。
7. **Context > 70% 输出质量明显掉** —— `/context` 查,`/compact` 或 `/clear` 救。
8. **CLAUDE.md trap** —— `--bare` 跳过 CLAUDE.md 加载;反之 CC 默认会加载 `./CLAUDE.md` + `~/.claude/CLAUDE.md`,可能与本次 prompt 冲突。需要纯净 prompt 用 `--bare`。
9. **slash commands 仅 interactive** —— `-p` 模式里描述自然语言任务,不要写 `/commit`。
10. **后台 tmux 会一直在** —— 完事 `tmux kill-session -t <name>`,别堆。

## Rules for Hermes Agents

1. **Prefer print mode (`-p`) for single tasks** — cleaner, no dialog handling, structured output
2. **Use tmux for multi-turn interactive work** — the only reliable way to orchestrate the TUI
3. **Always set `workdir`** — keep Claude focused on the right project directory
4. **Set `--max-turns` in print mode** — prevents infinite loops and runaway costs
5. **Monitor tmux sessions** — use `tmux capture-pane -t <session> -p -S -50` to check progress
6. **Look for the `❯` prompt** — indicates Claude is waiting for input (done or asking a question)
7. **Clean up tmux sessions** — kill them when done to avoid resource leaks
8. **Report results to user** — after completion, summarize what Claude did and what changed
9. **Don't kill slow sessions** — Claude may be doing multi-step work; check progress instead
10. **Use `--allowedTools`** — restrict capabilities to what the task actually needs

## References(按需加载,**不要一次全读**)

| 文件 | 何时加载 |
|---|---|
| `references/cli-reference.md` | 查具体 flag / subcommand / tool 通配语法 / env vars |
| `references/print-mode.md` | 用 `-p` 跑 JSON / streaming / schema / bare / fallback / session continuation / PR review |
| `references/interactive-tmux.md` | tmux 启动 / dialog 完整处理 / worktree / 并发 parallel claude / TUI 状态读法 |
| `references/slash-commands.md` | 交互里要用 `/compact` `/review` `/model` 等;键盘快捷键;输入前缀(`!@#/`) |
| `references/autonomous-loops.md` | `/goal` `/loop` Stop hook auto-mode 对比 + tmux 跑 `/goal` recipe |
| `references/hooks.md` | 8 类 hook + env vars + 安全 hook 模板(阻止 rm -rf / force push) |
| `references/mcp.md` | 接 MCP server(GitHub/Postgres/Puppeteer)+ scope + CI 模式 + 输出 token 上限 |
| `references/claude-md-and-rules.md` | CLAUDE.md / `.claude/rules/` / auto-memory 限额 / 自定义 subagent |
| `references/cost-and-pitfalls.md` | 省钱 11 条 + 完整 14 条 pitfalls(本 SKILL.md 只列 top 10) |
| `references/hermes-prompt-recipe.md` | **派 CC 前必看**:实战 prompt 骨架 + 8 经验 + 反模式表 |
| `references/cc-playbook/*.md` | 派 CC 卡住时(拖延/幻觉/忽略凭据)按情况查 6 个模板 |
| `references/cc-pushback-syndrome.md` | CC 推回任务的反模式识别与破解 |
| `references/hermes-orchestration-gotchas.md` | Hermes 派 CC 的其他踩坑(原始细节,补充本文) |
