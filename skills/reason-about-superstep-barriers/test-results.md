# reason-about-superstep-barriers — Pressure Test Results

## Final result

- **Final pass rate**: 9/9 (100%)
- **should_trigger**: 4/4
- **should_not_trigger**: 3/3
- **edge_case**: 2/2
- **Lure tolerance**: 0 failures
- **Method**: clean sub-agent blind routing against all 14 name+description entries, followed by independent action-quality grading
- **Date**: 2026-07-22

## Evidence

- Selection agents could not read test type, expected behavior, notes, private mappings, or other results.
- Action graders compared the chosen skill/action against expected behavior independently.
- All structural checks, JSON checks, sibling-skill lure checks, and 3–7 step checks passed.

## Remediation and regression
- B027 初轮只给公式未代入数值；加硬后 E002 输出 40.0s→40.2s→40.4s 时间线并通过。

## Audit paths

- `../../pressure/` — blind inputs, raw selections, grader outputs, and adjudication
- `test-prompts.json` — current ratcheting test set
