# design-or-migrate-typed-agent-workflows — Pressure Test Results

## Final result

- **Final pass rate**: 8/8 (100%)
- **should_trigger**: 4/4
- **should_not_trigger**: 3/3
- **edge_case**: 1/1
- **Lure tolerance**: 0 failures
- **Method**: clean sub-agent blind routing against all 14 name+description entries, followed by independent action-quality grading
- **Date**: 2026-07-22

## Evidence

- Selection agents could not read test type, expected behavior, notes, private mappings, or other results.
- Action graders compared the chosen skill/action against expected behavior independently.
- All structural checks, JSON checks, sibling-skill lure checks, and 3–7 step checks passed.

## Routing adjudication
- B026：主选本 Skill 并明确下一步组合 Superstep 分析，满足先静态后运行时顺序。

## Audit paths

- `../../pressure/` — blind inputs, raw selections, grader outputs, and adjudication
- `test-prompts.json` — current ratcheting test set
