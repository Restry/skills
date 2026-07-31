# place-agent-runtime-surfaces — Pressure Test Results

## Final result

- **Final pass rate**: 6/6 (100%)
- **should_trigger**: 3/3
- **should_not_trigger**: 2/2
- **edge_case**: 1/1
- **Lure tolerance**: 0 failures
- **Method**: clean sub-agent blind routing against all 14 name+description entries, followed by independent action-quality grading
- **Date**: 2026-07-22

## Evidence

- Selection agents could not read test type, expected behavior, notes, private mappings, or other results.
- Action graders compared the chosen skill/action against expected behavior independently.
- All structural checks, JSON checks, sibling-skill lure checks, and 3–7 step checks passed.

## Routing adjudication
- A012：组合边界题，主选本 Skill，兄弟 Skill 作为次选，动作正确。

## Audit paths

- `../../pressure/` — blind inputs, raw selections, grader outputs, and adjudication
- `test-prompts.json` — current ratcheting test set
