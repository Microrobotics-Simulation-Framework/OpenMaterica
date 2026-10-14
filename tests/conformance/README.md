# Conformance cases

`runner.py` runs the case files under `src/materica/data/conformance/` by the rules of
`docs/specification/README.md` ("Case files", "Variants", "Claims", "Operations"). Those rules hold wherever
this file differs.

## How a case file is counted

Each case file gets one outcome, decided in this order:

1. **not yet runnable**: no executor exists for its operation (`EXECUTORS` in `runner.py`);
2. **not run**: its suite, or its `claims`, disagree with the suites claimed (`CLAIMED`);
3. **passed** or **failed**: its result compared with `expected`.

A case, all its variants together, passes only when at least one variant ran and none failed; a case none of
whose variants ran is never counted as passed. Only files that run become pytest items, so nothing that did
not run can show as a pass or a skip. `test_cases.py` asserts the counts, and `tests/conftest.py` prints them
after every run that includes these tests:

| Operation | Case files | Outcome today |
|---|---|---|
| `content_hash` (HS-001 to HS-003) | 51 | run, passed |
| reads (plain read, HS-010, HS-011) | 340 | not yet runnable |
| `list_records` | 25 | not yet runnable |

## How a result is compared

`compare` in `runner.py` compares only the members a case's `compare.members` names. Reasons are a multiset of
`(code, condition)`, and `detail` is never compared. `labels` are a set, absent counting as empty, with
`hash_not_checked` compared only when the case's `claims` names `hash`. A member named but not expected must be
absent from the result. Numbers compare by `relative_tolerance` or bit for bit under `exact`; a case that
compares a number with neither is a defect in the case (`CaseFileError`), never a pass. A `list_records` value
is a set.

## Adding a case

Add the case file and its inputs by the conformance tree's own `README.md` ("Changing a case"); the runner
finds it. If its operation has an executor, it runs; if not, it is not yet runnable, and the counts in
`test_cases.py` change with it. A new operation needs an executor in `EXECUTORS`, and a broken
implementation in `test_runner_can_fail.py` that one of its cases catches.
