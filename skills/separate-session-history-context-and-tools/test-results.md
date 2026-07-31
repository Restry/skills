# separate-session-history-context-and-tools — Pressure Test Results

## Final result

- **Final pass rate**: 7/7 (100%)
- **should_trigger**: 3/3
- **should_not_trigger**: 2/2
- **edge_case**: 2/2
- **Lure tolerance**: 0 failures
- **Method**: clean sub-agent blind routing against all 14 name+description entries, followed by independent action-quality grading
- **Date**: 2026-07-22

## Evidence

- Selection agents could not read test type, expected behavior, notes, private mappings, or other results.
- Action graders compared the chosen skill/action against expected behavior independently.
- All structural checks, JSON checks, sibling-skill lure checks, and 3–7 step checks passed.

## Routing adjudication
- A014：原正例存在真实双入口歧义，改为 edge_case；状态生命周期为合理主选，动作正确。
- D001：新增纯净正例，精准命中本 Skill。

## Audit paths

- `../../pressure/` — blind inputs, raw selections, grader outputs, and adjudication
- `test-prompts.json` — current ratcheting test set
