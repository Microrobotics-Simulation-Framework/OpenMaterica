# Conformance cases

`runner.py` runs the case files under `src/materica/data/conformance/` by the rules of
`docs/specification/README.md` ("Case files", "Variants", "Claims", "Operations"). Those rules hold wherever
this file differs.

## How a case file is counted

The implementation runs under several configurations of claims (`CONFIGURATIONS` in `runner.py`): plain read
and the hash suite, as a read claims by default; plain read alone, as a reader without the hash suite; and
with the fits and reference data suite too, whose `want`s step 0 then accepts. A read under the last ends by
step 10 or raises, and steps 1 to 10 check the same under it as without it, so that claim gives no answer a
step not built yet could change. `materica` claims no table evaluation (TE): the last configuration, the TE suite
alone, is the test-only reference evaluator's (`tests/reference/table_evaluator.py`, the S3 design's S3Q15),
which runs each TE file four times, in `binary64` and `binary32`, declaring each side (`EVALUATOR_CLAIMS`).
Each case file runs under every configuration that claims its suite and agrees with every claim it states, and
gets one outcome, decided in this order:

1. **not yet runnable**: no executor exists for its operation (`EXECUTORS` in `runner.py`), or a step of the
   implementation its arm needs is not done: `tests/spec_sync/case_steps.json` maps each case file to the step
   whose code first runs it (S2 and S3 in their pieces, `S2a-1` to `S2b-2` and `S3-te` to `S3c`, then `S4`,
   or a list of pieces where their order is not fixed), and lists the steps done;
2. **not run**: no configuration claims its suite and agrees with its `claims`;
3. **passed**, **verified** or **failed**: each result compared with `expected`; it fails if one run fails,
   and says under which claims. An executor that raises fails the case, as no read may raise (PR-300). A TE
   file that fails nowhere is **verified against the reference evaluator**, never passed, and the summary
   reports it on its own line.

A case, all its variants together, passes, or is verified, only when at least one variant ran and none
failed; a case none of whose variants ran is never counted as passed. Only files that run become pytest items,
so nothing that did not run can show as a pass or a skip. `test_cases.py` asserts the counts, and
`tests/conftest.py` prints them after every run that includes these tests:

| Operation | Case files | Outcome today |
|---|---|---|
| `content_hash` (HS-001 to HS-003) | 51 | run, passed |
| reads S1 runs, which end by step 5 (plain read, HS-010, HS-011) | 341 | run, passed |
| `list_records` | 25 | run, passed |
| S2's reads that end at step 0, 7 or 8 (plain read) | 169 | run, passed |
| S2's reads that end at step 9 or 10, or at step 0 on an implied condition (plain read) | 58 | run, passed |
| S2's reads that go on to steps 11 to 13 for a constant, or end at step 7 on alternatives as far as S4's decision 12 lets S2 go, or at step 0 on an implied value holding a member of the other kind of condition's shape (plain read) | 166 | run, passed |
| S2's reads of an interval or a composition, to their bounds or components, or ending at step 8 on their own member, or at step 7 over alternatives that hold one (plain read) | 54 | run, passed |
| S2's reads of evidence, and reads under a nominal or an acceptance a read does not take, to the value or ending at step 0, 8 or 13 (plain read) | 69 | run, passed |
| reads S3's pieces run (plain read): tables, and reads under an extrapolation | 180 | not yet runnable: the step that runs each is not done |
| S4a's reads over alternatives with no pick and no overlay: each alternative set aside, kept or refusing the field, and the outcome (plain read) | 24 | run, passed |
| reads S4's later pieces run (plain read): over alternatives with a pick or a table, or through an overlay | 135 | not yet runnable: S4, which runs each, is not done |
| `evaluate` (TE-002 to TE-012) | 35 | run, verified against the reference evaluator under each of its four configurations |
| record checks (`check`: RC-031, RC-032, RC-220 to RC-226) and `quote_sha256` (RC-033's vectors) | 164 and 13 | not yet runnable: no executor; C2, with S5's record checks, adds them |

Each read is counted by the step whose code runs it (`case_steps.json`), not by what it reads:
`PR-044.alternatives_beside_value` holds alternatives and is S2a-4's, and `PR-007.target_is_overlay` ends at
step 5 and is S4's. Two arms S4's decision 12 gives S2a-4, `PR-044.entry_holds_alternatives` (the shape of
`alternatives`) and `PR-336.want_mismatch_over_alternatives_no_hs` (step 7's `want_mismatch`), are S2a-4's
since its fix round. So are the two arms of the maintainer's token ruling, which end at step 0
(`PR-330.implied_token_for_numeric_condition`, `PR-330.implied_unit_for_token_condition`): S2a-3's step 0
ignored each member, and S2a-4's fix round refuses it. The six arms of the ruling on a record's condition
holding the other kind's member (`PR-045.numeric_condition_holding_token`,
`PR-045.numeric_condition_holding_token_status`, `PR-045.token_condition_holding_value`,
`PR-045.token_condition_holding_value_null`, `PR-030.near_typo_token_on_numeric_condition`,
`PR-301.other_kind_beside_unknown_basis`) are S2a-2's, whose step 8 checks a condition's shape: it ignored each
member until that ruling (2026-10-19), and refuses it since.

Of the 1504 case files, 1257 agree with plain read and the hash suite, 1199 with plain read alone, and 1257
with the fits and reference data suite too; the 35 of the table evaluation suite agree with the reference
evaluator's configuration alone, since this implementation claims no evaluator, and the 197 of the
record-check suite agree with none, since it claims no record checks.

A read executor reads the case's request, or the file `inputs.request` names, among the files `inputs.records`
names (`materica.load_records`), and passes its result through JSON text, as a consumer would receive it. Each
result of a case file that runs, a table evaluation case's excepted, validates against `read_result.json` too (`test_cases.py`, with a control), so
the published schema takes what the implementation returns, not only each case file's expected answer. The
`evaluate` executor evaluates the case's table at each of its axis values, once under each precision and side
the evaluator claims, and holds one run per claim; its numbers stay Python floats, since a refusal may return
NaN, which JSON text cannot hold. An evaluator may raise its refusal in place of reporting it, since "a raised
refusal counts as reported" (`read_side_contract.md` section 7 item 7): the executor adapts a raised `Refusal`
(`runner.py`) to the refusal reported, at that axis value. It adapts no other exception, which fails the case
as any executor's does, so that a crash never passes as a refusal.

## How a result is compared

`compare` in `runner.py` compares only the members a case's `compare.members` names. Reasons are a multiset of
`(code, condition, alternative)`, as the specification compares them (`docs/specification/README.md`, "Case
files"), and `detail` is never compared. An `alternative` is an index, compared exactly: bit for bit under
`exact`, so `-0` is not `0`, and by value under a relative tolerance, which never applies to one; a bool is
never an index, and a case that compares one with neither is a defect (`CaseFileError`). Only S4's case files
expect a reason with `alternative`, so the runs of earlier steps are unchanged; `test_comparator.py` drops the
indexes from every such file's expected answer and shows that each then fails.
`labels` are a set, absent counting as empty, with `hash_not_checked` compared only when the case's `claims`
names `hash`. A member named but not expected must be absent from the result. Numbers compare by
`relative_tolerance` or bit for bit under `exact`; a case that compares a number with neither is a defect in
the case (`CaseFileError`), never a pass. A `list_records` value is a set. `conditions` is a set keyed by
`name`: each name once, in any order, so a reader that sorts its entries passes, and a missing, extra or
repeated entry fails. `alternative_values` is compared in stored order, entry by entry, each entry's `labels`
and `conditions` as the result's.

A TE case is compared run by run, entry by entry in order, by the rules of the specification's README ("Case
files"): an entry compares only the members it holds and whether a refusal is reported; a refused entry passes
only where the refusal is reported and each number is absent or NaN, and any other only where none is; the
derivative is compared by the side the run declares, `"none"` passes only absent or NaN, and outside the
readable range each number may be absent or NaN; an expected derivative of 0 passes only at zero, of either
sign; and numbers are compared at the tolerance of the run's precision. A JSON `null` in place of a number is
no number returned, and reads as absent everywhere, beside a refusal too. `test_comparator.py` feeds this
comparison wrong answers of each kind.

## The case files themselves

The runner reads case files with `jsonio.parse`, the reader under test. So `test_case_files.py` reads every
case file, and every input, again with the reference reader (`reference_reader.py`), the standard library's
json with hooks that refuse exactly the faults `record_format.md` section 1 item 6 lists, which shares no code
with it: each must read alike, numbers bit for bit, or be refused by both. It also validates each case file
against `schema/0.1/case.json`.

## Adding a case

Add the case file and its inputs by the conformance tree's own `README.md` ("Changing a case"), its row in the
suite's `CASES.md`, and its step in `tests/spec_sync/case_steps.json`; the runner finds it. If its operation has
an executor and its step is done, it runs; if not, it is not yet runnable, and the counts in `test_cases.py`
change with it. When a step is done, add it to `done`: its case files then run and must pass. A new operation
needs an executor in `EXECUTORS`, and a broken implementation in `test_runner_can_fail.py` that one of its cases
catches. The broken evaluators there are the S3 design's section 6.4, the further ones the TE suite's README
names, and two more the text supports. Each must fail the TE file named beside it under every precision and
side it claims, by the difference named beside it, and never by raising. And each must still fail one of the
files named beside it with that file's `binary32` tolerance ten times as wide: the specification README's cap
on a file's tolerance, restated per broken evaluator (maintainer, 2026-10-17).
