---
name: sync-skill
tags: [meta, sync, infrastructure]
description: Use this skill when the user asks to sync, pull, publish, list, or check the status of agent skills shared across machines. Triggers on phrases like "同步技能", "拉一下技能", "把这个技能发布出去", "看看有哪些技能可以装", "sync my skills", "publish this skill". This skill installs/updates SKILL.md trees under ~/.claude/skills/ from a central GitHub repo and reports back to a small server so a Web dashboard can show which machines have which skills.
---

# sync-skill

You orchestrate skill synchronization across machines. The user has a GitHub repo of skills and a backend service; this skill is the agent-side client.

## When to use

- "同步一下技能" / "sync skills" / "pull skills" → run `pull` (all) or `pull <name>` (specific)
- "看看有什么新技能" / "list skills" → run `list`
- "把这个技能发布出去" / "publish this skill <path>" → run `publish <path>`
- "本地装了哪些" / "skill status" → run `status`
- First time on a new machine, no config exists → run `init`

## Prerequisites — check first

Before running any subcommand, verify config exists:

```bash
test -f ~/.config/sync-skill/config.toml && echo OK || echo NEED_INIT
```

If `NEED_INIT`, ask the user for:
1. Backend server URL (e.g. `http://skills.example:8000/api`)
2. GitHub repo URL of the skills (e.g. `https://github.com/user/skills.git`)
3. Runtime name on this machine (`claude` / `openclaw` / `hermes`)

Then run `init` (see below).

## Subcommands

All scripts live in this skill directory. Invoke them with Bash. Use `$CLAUDE_SKILL_DIR` if your runtime exposes it, otherwise expand `~/.claude/skills/sync-skill/scripts/`.

```bash
SCRIPTS=~/.claude/skills/sync-skill/scripts

# First-time setup
python3 $SCRIPTS/init.py --server <url> --repo <git-url> --runtime claude

# Day-to-day
python3 $SCRIPTS/list.py                       # list available skills
python3 $SCRIPTS/pull.py                       # install ALL skills
python3 $SCRIPTS/pull.py my-skill other-skill  # install specific ones
python3 $SCRIPTS/status.py                     # local state + staleness
python3 $SCRIPTS/publish.py /path/to/skill-dir # publish a local skill dir
```

Each script prints human-readable lines to stdout. Surface them to the user verbatim; do not summarize away skill names or counts.

## Behavior

- All scripts use only Python stdlib — no `pip install` needed on the target machine.
- Configuration is at `~/.config/sync-skill/config.toml`.
- A working clone of the skill repo is kept at `~/.cache/sync-skill/repo/` and used for both `pull` and `publish` (single source for git operations).
- Skills are installed into the `target_dir` from config (defaults to `~/.claude/skills`).
- After every successful `pull`, a heartbeat is sent to the backend so the Web dashboard sees this machine's current installed list.
- `publish` copies the user-pointed directory into `<clone>/skills/<dirname>/`, commits with message `publish <name>`, pushes to `origin`, and pokes `POST /api/refresh` so the backend reindexes immediately.

## Error handling

If any script exits non-zero, show stderr to the user — don't retry blindly. Common cases:

- `git push` rejected → likely the user needs to authenticate to the GitHub repo on this machine. Tell them, don't try to fix it.
- Backend unreachable → `status` still works using local state; `pull` and `publish` partially work (`pull` can still install from the local clone; the heartbeat just fails). Tell the user.
- `init` and config already exists → use `--force` only if the user confirms.

## Do NOT

- Do not edit `~/.config/sync-skill/config.toml` by hand — re-run `init --force`.
- Do not write skills directly into `~/.claude/skills/`; always go through `pull`.
- Do not call the backend API directly with curl unless debugging; the scripts handle it.
