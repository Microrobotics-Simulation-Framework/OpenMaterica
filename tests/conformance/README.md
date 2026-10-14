# Conformance cases

`runner.py` runs the case files under `src/materica/data/conformance/` by the rules of
`docs/specification/README.md` ("Case files", "Variants", "Claims", "Operations"). Those rules hold wherever
this file differs.

## How a case file is counted

The implementation runs under several configurations of claims (`CONFIGURATIONS` in `runner.py`): plain read
and the hash suite, as a read claims by default; plain read alone, as a reader without the hash suite; and
with the fits and reference data suite too, whose `want`s step 0 then accepts. A read under the last ends by
step 5 or raises, so that claim gives no answer a step not built yet could change. Each case file runs under
every configuration that claims its suite and agrees with every claim it states, and gets one outcome, decided
in this order:

1. **not yet runnable**: no executor exists for its operation (`EXECUTORS` in `runner.py`);
2. **not run**: no configuration claims its suite and agrees with its `claims`;
3. **passed** or **failed**: each result compared with `expected`; it fails if one run fails, and says under
   which claims. An executor that raises fails the case, as no read may raise (PR-300).

A case, all its variants together, passes only when at least one variant ran and none failed; a case none of
whose variants ran is never counted as passed. Only files that run become pytest items, so nothing that did
not run can show as a pass or a skip. `test_cases.py` asserts the counts, and `tests/conftest.py` prints them
after every run that includes these tests:

| Operation | Case files | Outcome today |
|---|---|---|
| `content_hash` (HS-001 to HS-003) | 51 | run, passed |
| reads (plain read, HS-010, HS-011) | 341 | run, passed |
| `list_records` | 25 | run, passed |

Of the 417 case files, 409 run under plain read and the hash suite, 347 under plain read alone, and 408 with
the fits and reference data suite too.

A read executor reads the case's request, or the file `inputs.request` names, among the files `inputs.records`
names (`materica.load_records`), and passes its result through JSON text, as a consumer would receive it.

## How a result is compared

`compare` in `runner.py` compares only the members a case's `compare.members` names. Reasons are a multiset of
`(code, condition)`, and `detail` is never compared. `labels` are a set, absent counting as empty, with
`hash_not_checked` compared only when the case's `claims` names `hash`. A member named but not expected must be
absent from the result. Numbers compare by `relative_tolerance` or bit for bit under `exact`; a case that
compares a number with neither is a defect in the case (`CaseFileError`), never a pass. A `list_records` value
is a set.

## The case files themselves

The runner reads case files with `jsonio.parse`, the reader under test. So `test_case_files.py` reads every
case file, and every input, again with the reference reader (`reference_reader.py`), the standard library's
json with hooks that refuse exactly the faults `record_format.md` section 1 item 6 lists, which shares no code
with it: each must read alike, numbers bit for bit, or be refused by both. It also validates each case file
against `schema/0.1/case.json`.

## Adding a case

Add the case file and its inputs by the conformance tree's own `README.md` ("Changing a case"), its row in the
suite's `CASES.md`, and its step in `tests/spec_sync/case_steps.json`; the runner finds it. If its operation has
an executor, it runs; if not, it is not yet runnable, and the counts in `test_cases.py` change with it. A new
operation needs an executor in `EXECUTORS`, and a broken implementation in `test_runner_can_fail.py` that one
of its cases catches.
