# model-recoverable-human-decisions — Pressure Test Results

## Final result

- **Final pass rate**: 8/8 (100%)
- **should_trigger**: 3/3
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
- C001 初轮遗漏当前医生身份、tenant 与病历权限复验；加硬后 E003 通过。
- C003 初轮遗漏当前操作者实时授权复验；加硬后 E004 通过。

## Audit paths

- `../../pressure/` — blind inputs, raw selections, grader outputs, and adjudication
- `test-prompts.json` — current ratcheting test set
