# Autonomous Loops: `/goal` vs `/loop` vs Stop hooks vs auto-mode

CC 自主跑多轮的四种方式对比 + 实战。**何时加载**:要让 CC 不停手跑到收敛、定时轮询外部状态、用 Stop hook 接管循环判定时。

Three approaches let CC keep running between prompts. Pick by **what triggers the next turn** and **what stops it**:

| Approach | Next turn starts when | Stops when |
|---|---|---|
| `/goal <condition>` | Previous turn finishes | A fast judge model confirms the condition is met |
| `/loop [interval]` | Time interval elapses | You stop it, OR Claude decides work is done |
| `Stop` hook | Custom logic | Custom logic (hook decides) |
| auto-mode | Classifier picks | Classifier picks |

## `/goal` — Goal-conditioned autonomous run

**Set a verifiable end-state. CC keeps working without prompting until a small fast model judges the condition true.**

Official examples:
- Migrate a module to a new API → until every call site compiles + tests pass
- Implement a design doc → until all acceptance criteria hold
- Split a large file into modules → until each is under a size budget
- Work through an issue backlog → until the queue is empty

**Usage** (interactive only — no print-mode flag for it):
```
/goal All Python files in src/ pass mypy --strict and pytest exits 0.
```

CC then:
1. Runs a turn (edits, runs commands, etc.)
2. Fast judge model checks: "is the condition met?"
3. If no → CC starts another turn automatically (no human prompt)
4. If yes → goal clears, control returns to you

**Status / clear**:
- `/goal` (no args, while one is active) → check status
- `/goal clear` → abort early

**Effective conditions** must be **verifiable by reading code/output**, not vague:
- ❌ "Make the code clean" (subjective, never converges)
- ✅ "ruff check . exits 0 and all files in src/ are < 300 lines"
- ✅ "All TODO comments in lib/auth/ have been resolved or moved to GitHub issues"

**Hermes orchestration tip**: For long autonomous goals, use interactive mode in tmux + monitor pane periodically. `/goal` is **not currently exposed as a print-mode CLI flag** — it's a slash command, so you need a TUI session.

## `/loop [interval]` — Time-triggered re-run

**Re-trigger CC on a schedule (e.g., every 5 min) until you stop it or CC declares done.**

Use when:
- Polling for an external state change (CI passing, deployment ready)
- Iteratively improving something that benefits from "sleep on it" cycles
- Periodic monitoring tasks within a single session

Usage:
```
/loop 300   # re-trigger every 300 seconds
/loop       # default interval
```

Stop with `Ctrl+C` or by CC declaring the work done.

## Hermes Recipe — Run `/goal` autonomously in tmux

```
# Start tmux + CC interactive session
terminal(command="tmux new-session -d -s goal -x 140 -y 40")
terminal(command="tmux send-keys -t goal 'cd /path/to/repo && claude --dangerously-skip-permissions' Enter")
# trust dialog
terminal(command="sleep 4 && tmux send-keys -t goal Enter")
# permissions dialog
terminal(command="sleep 3 && tmux send-keys -t goal Down && sleep 0.3 && tmux send-keys -t goal Enter")
# Set the goal
terminal(command="sleep 5 && tmux send-keys -t goal '/goal All tests in tests/ pass and coverage >= 90%' Enter")
# Monitor periodically (CC will keep iterating without you)
terminal(command="sleep 300 && tmux capture-pane -t goal -p -S -80")
```

## Pitfalls

1. **Verifiable conditions only** — `/goal` evaluator is a small fast model. Vague conditions never converge and burn tokens.
2. **No print-mode equivalent** — `/goal` and `/loop` are slash commands. Headless use requires interactive TUI in tmux.
3. **Cost discipline** — autonomous loops can rack up spend. Set a budget hint in the goal itself ("...within 20 turns") or monitor `/cost` between turns.
4. **Goal evaluator can be fooled** — if your condition is "tests pass" and CC writes `pytest --collect-only` aliases or skips, it may declare victory. Pair conditions: "tests pass AND `git diff --stat` shows real changes to src/".
