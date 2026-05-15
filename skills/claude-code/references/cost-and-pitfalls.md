# Cost & Performance Tips + Pitfalls & Gotchas

省钱 / 调速 11 条 + 踩坑 14 条。**何时加载**:派任务前 sanity check、debug 怪现象、被 budget / max-turns / dialog 卡住时翻这里。

## Cost & Performance Tips

1. **Use `--max-turns`** in print mode to prevent runaway loops. Start with 5-10 for most tasks.
2. **Use `--max-budget-usd`** for cost caps. Note: minimum ~$0.05 for system prompt cache creation.
3. **Use `--effort low`** for simple tasks (faster, cheaper). `high` or `max` for complex reasoning.
4. **Use `--bare`** for CI/scripting to skip plugin/hook discovery overhead.
5. **Use `--allowedTools`** to restrict to only what's needed (e.g., `Read` only for reviews).
6. **Use `/compact`** in interactive sessions when context gets large.
7. **Pipe input** instead of having Claude read files when you just need analysis of known content.
8. **Use `--model haiku`** for simple tasks (cheaper) and `--model opus` for complex multi-step work.
9. **Use `--fallback-model haiku`** in print mode to gracefully handle model overload.
10. **Start new sessions for distinct tasks** — sessions last 5 hours; fresh context is more efficient.
11. **Use `--no-session-persistence`** in CI to avoid accumulating saved sessions on disk.

## Pitfalls & Gotchas

1. **Interactive mode REQUIRES tmux** — Claude Code is a full TUI app. Using `pty=true` alone in Hermes terminal works but tmux gives you `capture-pane` for monitoring and `send-keys` for input, which is essential for orchestration.
2. **`--dangerously-skip-permissions` dialog defaults to "No, exit"** — you must send Down then Enter to accept. Print mode (`-p`) skips this entirely.
3. **`--max-budget-usd` minimum is ~$0.05** — system prompt cache creation alone costs this much. Setting lower will error immediately.
4. **`--max-turns` is print-mode only** — ignored in interactive sessions.
5. **Claude may use `python` instead of `python3`** — on systems without a `python` symlink, Claude's bash commands will fail on first try but it self-corrects.
6. **Session resumption requires same directory** — `--continue` finds the most recent session for the current working directory.
7. **`--json-schema` needs enough `--max-turns`** — Claude must read files before producing structured output, which takes multiple turns.
8. **Trust dialog only appears once per directory** — first-time only, then cached.
9. **Background tmux sessions persist** — always clean up with `tmux kill-session -t <name>` when done.
10. **Slash commands (like `/commit`) only work in interactive mode** — in `-p` mode, describe the task in natural language instead.
11. **`--bare` skips OAuth** — requires `ANTHROPIC_API_KEY` env var or an `apiKeyHelper` in settings.
12. **Context degradation is real** — AI output quality measurably degrades above 70% context window usage. Monitor with `/context` and proactively `/compact`.
14. **CC 报"部署回滚 / smoke fail / 根因 X"时别盲信，独立验 prod** —— 2026-05-13 派 selftest cleanup,CC zip 整个 working tree(含 11 个未 commit 文件)部署→回滚→回报"prod DB 缺 `requireProfileCompletion` 列导致 P2022→502"。实际两实例 prod DB 都有该列。CC 看到 dirty working tree 就脑补根因停手不验。**修法 A**:CC 报根因前 controller 必须独立 query prod DB / curl prod endpoint 验一遍。**修法 B**:派 CC 前 `git stash -u` 无关 working tree 改动,zip 只带 git HEAD 干净版本(或自己写 deploy 脚本绕开 CC),避免 CC zip 进未提交文件混淆 diagnosis。

13. **`--print` mode 静默"问一句就退"** —— 如果 prompt 里留了任何开放性方案选择(如"走 A 还是 B?"、"是否需要 X?"、"请确认..."),CC 经常**一行都不改**就退,只回一句 "请确认走哪条路" exit 0 看着像成功但 git status 干净。`--print` 模式还会把这一行问题当作"最终输出"覆盖掉前面所有思考过程，log 文件只剩末尾那一句疑问。**修法**:派 CC 时 prompt 末尾必须明令 `**禁止返问**，所有方案选择已在上面给出，有歧义自己拍板把决定写进 commit message`。即使 prompt 里给了方案 A，CC 仍可能"礼貌确认一下"。爸爸 2026-05-12 派 INTERNAL_TOKEN_SECRET 合并任务踩过两次,第三次加铁律才一条龙跑完。
