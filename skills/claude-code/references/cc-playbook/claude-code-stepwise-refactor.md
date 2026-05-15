---
name: claude-code-stepwise-refactor
description: Orchestrate large multi-file refactors by relaying numbered steps to Claude Code (`claude -c --print < /tmp/cc-*.md`), with each step producing an independent commit + explicit verification checklist + mandatory browser-agent E2E. Use when executing a pre-approved plan document (first-principles / deletion-heavy refactor) across 5+ discrete changes that need human gating between steps.
version: 1.0.0
author: Hermes
metadata:
  hermes:
    tags: [Refactor, Claude-Code, First-Principles, Orchestration, E2E, Stepwise]
    related_skills: [claude-code, first-principles-musk, subagent-driven-development]
---

# Claude Code Stepwise Refactor

Pattern for executing a multi-step refactor plan (typically first-principles deletions) by relaying each step to Claude Code via `claude -c --dangerously-skip-permissions --print < /tmp/cc-stepN.md`. Hermes does NOT run code itself — Claude Code is the executor; Hermes is the orchestrator that translates user decisions into precise step prompts and summarizes raw output back.

## When to use

- You have a written execution plan document (e.g., `docs/prd/*-plan.md`) with numbered deletion/change items (D1..DN)
- User wants independent commits per step, gated by verification, not a single big-bang PR
- Changes span multiple repos / require server restarts / require UI verification
- User has authorized autonomous execution within guardrails but wants compact progress reports

## Core loop

```
for each step N:
  1. write_file /tmp/cc-stepN.md  # precise prompt
  2. terminal background: zsh -ic 'cd <repo> && claude -c --dangerously-skip-permissions --print < /tmp/cc-stepN.md'
     + notify_on_complete=true
  3. wait for system notification of completion
  4. relay Claude's raw output back to user (preserve structure)
  5. wait for user approval → write next step file → repeat
```

## Step prompt template

Every `/tmp/cc-stepN.md` MUST contain these sections:

```markdown
# Step N · <short title>

## Target
<1-line physical goal>

## Scope
<numbered list of exact files + line ranges or symbols to change; reference the plan doc's section for specifics>

## Constraints (first-principles red lines)
- No new null checks / retries / fallbacks / monitoring — violations stop immediately
- 10% ADD-BACK warning: if any addition beyond planned ADD-BACKs is needed, STOP and report
- No scope expansion — only this step's D-items

## Verification (all mandatory)

### REL regression
- `make test-reliability` → REL-01/02/03 PASS (or whichever are active)

### Baseline sampling
- 5+ specific test case IDs (e.g., API-CHAT-01, MA-01, THREAD-01)

### UI E2E (browser-agent skill @ http://localhost:4026)
- **Required for ALL business-logic changes**, not just UI changes
- List specific user flows to walk through

### Code-level grep checks
- `grep -n "<symbol>" <file>` → 0 hits confirmations

## Commit
<repo> repo: `[reliability-v2] D<n>: <imperative summary>`
Push to origin/dev.

## Hard stop conditions
- Any REL FAIL → stop
- Any UI E2E FAIL → stop
- Unexpected NPE / crash → stop
- Need to expand ADD-BACK beyond plan → stop and report

## Report format
【Step N 完成】
commit: <sha> (<repo>)
文件改动: -X / +Y
验收: <per-item PASS/FAIL>
REL-*: <status>
baseline 抽样: <list>
下一步: Step N+1 <title>
问题/警告: <如有>
```

## Critical rules

### 1. Never let Claude Code decide scope
Every step is scoped in advance. If Claude discovers something during execution (e.g., a read-path dependency not in the plan), it MUST stop and ask — not improvise. Put this explicitly in the prompt: **"没有自己继续推进"** (do not self-advance).

### 2. Temporary compromises must be tagged
If a step leaves a temporary guard that a later step will remove (e.g., Step 3's `c.ws &&` null check pending Step 5's structural split), the commit message AND code comment MUST say `// temporary: pending D<later>`. The later step prompt explicitly requires removing it.

### 3. ADD-BACK accounting
Track `new_lines / deleted_lines`. Musk's 10% rule: if >10% added back, deletion wasn't enough — stop and re-examine. Surface this ratio in every step report.

### 4. E2E is not optional for business logic
User's rule (learned the hard way): **all business-logic changes** require browser-agent skill verification on real UI, not just API-layer curl/wscat/SQL. Only pure doc changes and pure log deletion can skip UI verification.

### 5. Test infrastructure early
Schedule test-infra (Makefile + mock-backend + regression suite) as Step 2 or 3, BEFORE the risky structural changes. It must exist by the time you hit the core rewrite step so every subsequent step has automated regression gates.

### 6. Test gateway gets its own port
Never share port with dev instance. If dev runs on :19180, test runs on :19181, mock backend connects to :19181. Otherwise test teardown kills dev services user is watching.

### 7. Grant Supabase + service-restart authority up front
Don't ask every step whether Claude can touch Supabase or restart the gateway/OpenClaw. Put blanket authorization in the step prompt once, revokable only for destructive ops (DROP TABLE, tiger-host production, etc.).

## Orchestration tools

| Task | Tool |
|------|------|
| Write step prompt | `write_file /tmp/cc-stepN.md` |
| Launch Claude Code | `terminal` with `background=true` + `notify_on_complete=true` + `zsh -ic 'claude -c --dangerously-skip-permissions --print < /tmp/cc-stepN.md'` |
| `-c` flag | continues most recent session in cwd → full context preserved across steps |
| Long prompts | Always via stdin file; direct `--print "..."` hits `zsh: file name too long` at ~3KB |
| Session not found fallback | If specific `--resume <id>` fails, use `-c` |

## When user interrupts mid-run

Common pattern: user sends a small UI fix / preference (e.g., "persist Get Started dismissal in localStorage") while Step N is running.

**Correct response:**
1. Acknowledge in one line
2. Note which later step will absorb it (usually the client-web / UI cleanup step)
3. Do NOT kill the running step
4. Do NOT send a new Claude Code job mid-stream (claude -c would mutate context the running job depends on)

## When user doubts progress

If user asks "is this actually doing anything meaningful" mid-refactor:
- Be honest about which steps are **cleanup/prep** vs. which actually fix symptoms
- Map steps to the user's verbatim pain points ("刷新就没了" → D6; "NPE 补丁" → D1+D2)
- Don't oversell preparation work as the fix itself
- Offer: (a) wait until visible fix, (b) skip ahead to the symptom-curing step

## Example: skeleton for a 10-step plan

| Step | Type | Purpose | E2E needed |
|------|------|---------|-----------|
| 1 | Pure deletion | Remove dead code + one-line logs | No (grep suffices) |
| 2 | Test infra | Makefile + mock + regression suite | No (but REL must run) |
| 3 | Refactor | Collapse duplicate logic; leave null guards tagged | Yes |
| 4 | Deletion | Remove stale state maps; preserve one explicit trigger | Yes |
| 5 | **Core rewrite** | Structural split that obsoletes prior patches; strip tagged guards | Yes + soak |
| 6 | **Inversion** | Change a core ordering (e.g., persist-after-ack) + related ADD-BACKs | Yes |
| 7..N | Domain cleanups | Schema/index changes; cross-repo follow-ups | Yes per step |
| Last | Docs | PRD update; no code | No |

## Pitfalls

1. **Forgetting `notify_on_complete=true`** → you're polling blindly. Always set it.
2. **Forgetting the `cd <repo> &&` in the `-ic` shell** → Claude Code runs in wrong cwd → `-c` finds wrong session.
3. **Skipping browser-agent E2E for "just a server-side change"** → bites you when a subtle protocol frame change breaks UI rendering. User explicitly corrected this expectation. Always E2E for business logic.
4. **Letting Claude Code chain 3 steps without stopping** → one silent failure cascades. Every step ends with a hard stop → user approval → next prompt.
5. **Not showing raw Claude output** → user loses audit trail. Always relay the report block, add your own assessment below it, not instead of it.
6. **Asking the user "要不要派 Claude Code 去？"** → user has standing instruction: ALL code investigation/modification/review goes to Claude Code automatically. Never ask for permission to delegate code work; only ask for direction on scope or trade-offs. Saved in memory.
7. **`claude --print < /tmp/file.txt` in background zsh silently drops stdin** → exit 0, empty log, no commits, no changes. The background shell closes stdin before Claude reads it. **Fix: always pass via `"$(cat /tmp/file.txt)"` as a positional arg**, not stdin redirection. Signal: log contains `Warning: no stdin data received in 3s, proceeding without it.`
8. **Adding reverse-proxy / infra config without checking what's actually deployed** → Claude added security headers to `nginx.conf`, but production was Caddy (`Caddyfile.app`), nginx.conf was a dead file. Always instruct Claude to grep Dockerfile / docker-compose.yml / deploy scripts **before** editing any reverse-proxy or webserver config to confirm which file the deploy pipeline actually consumes. Dead config files in the repo are landmines.
9. **Testing on wrong port / wrong origin** → When user says "E2E on http://localhost:4026", that port may be occupied by another project's Vite. Always instruct Claude to `curl http://localhost:PORT` and assert the response identifies the target app (`<title>` or a known string) before running any UI assertions. Same trap applies to browser-agent: verify `window.location.origin` + a distinctive DOM element before trusting any PASS.
10. **Skipping the post-completion orphan sweep** → After all batches succeed and CC reports "thread refs = 0", Hermes should still run a cross-batch sweep itself: (a) `rg -i <concept>` across full repo with build-product excludes, (b) `gitnexus analyze && cypher "MATCH (n) WHERE toLower(n.name) CONTAINS '<concept>' RETURN ..."` for symbol-level residue, (c) eyeball largest source files for orphan capability flags / feature toggles (e.g. `threads: false` in a capabilities object — grep-clean but semantically dead). User explicitly asks "看看还有没有什么垃圾东西可以删" — be ready with an answer, don't claim victory at "compiles + 0 grep hits". The capability-flag class of orphan is the most common miss: each batch's CC sees only its own scope and won't delete a flag defined in another package.\n\n11. **Letting Claude self-gate on policy-level decisions mid-run** → Claude paused mid-refactor asking "should A1/A2 create a new permission subsystem?" — but the plan doc already specified "tighten permission points on existing model, do not redesign". Step prompts must explicitly say: **"清单里写啥就做啥。如果发现需求本身有错，指出并停；否则不要反问。"** Otherwise Claude self-stops on ambiguity the plan already resolved.

## Bug-list triage pattern (before dispatching batches)

When user shares a third-party test report / bug list with 10+ items, do NOT immediately batch to Claude Code. First:

1. Extract titles only (P1/P2/P3 grouped), relay as numbered list, ask "which ones to skip".
2. User will mark some as "design, don't fix" → record the strike-out set explicitly in the dispatch prompt so Claude never touches those files.
3. Group remaining items into thematic batches (权限 / 通知 / 展示 / 安全基线 etc.), 5-6 per batch, not by original P-level.
4. For each batch with a trade-off (e.g., "forgot password: add real flow vs just change copy"), offer a default and state it; if user says "go" without picking, use the default — don't block on clarification.
5. Dispatch one Claude Code session for the whole list, instructing independent commits per batch.

This prevents the "派出去发现用户其实不想改某几条" waste.

## Bug-report-driven workflow (variant of the stepwise pattern)

When the user reports concrete bugs (not a pre-written plan), use this 4-phase loop with a single Claude Code dispatch per phase. Do NOT ask "want me to dispatch Claude Code?" — just do it.

### Phase 1: Review-first
Dispatch Claude Code to **investigate root causes only, no fixes**. Prompt requires:
- Locate root cause for each reported bug (file:line + call path)
- Extend to code-quality review of recently-changed files in the same area
- Explicit anti-pattern audit: count null-checks/retries/defensive code that mask deletable parts (Musk step ②)
- Output structured report; **do not modify any file**

### Phase 2: User-gated summary
Relay raw output **and** produce a ≤200-char plain-language summary on demand. The user often wants the short version, not the full review. Always offer both.

### Phase 3: Fix-with-guardrails
Dispatch Claude Code to fix, with the prompt enforcing:
- ❌ No new null checks / try-catch / retries / defensive coding
- ❌ No double-write / double-read / double-fetch transitions
- ✅ Delete more than you add (Musk's "if you don't add 10% back, you didn't delete enough")
- ✅ Converge multi-path writes to a single function with id-based dedup
- ✅ Self-Code-Review **inside the same Claude Code session** before declaring done; if self-audit fails, redo (don't ship to user)
- ✅ Browser-agent E2E required for business-logic changes, not just UI
- ✅ Commit but **DO NOT push** — user gates the push

### Phase 4: User decides push
Present 3 options after Claude Code reports:
1. Push as-is (lock in confirmed wins, defer unfixed items)
2. Send Claude Code back for the unfixed items
3. User manually validates first, then iterates

Push only after explicit user approval. `git push` is the user's ratification, not Claude Code's.

### Critical: don't gold-plate the report
User explicitly said "代码 review 看起来头疼，给我 200 字总结". Default to compact summaries; expand only on request. Long structured reviews are for the audit trail, not the conversation surface.
