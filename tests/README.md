# Tests

| Directory | What it checks | Its README says |
|---|---|---|
| `conformance/` | the specification's conformance cases, run by a runner that counts what it cannot run; the case files themselves | how cases are counted and compared; adding a case |
| `spec_sync/` | what is written in two places: the specification's tables and the schemas, the envelope checks and the reader schema, `CASES.md` and the case files, the cases and the steps that run them, the specification's references and what they name | what each test holds together |
| `property/` | Hypothesis properties of the reader, the canonical form, the hash, the one-slip relation, the envelope checks, versions, the read and its step 8, of the writer schema's value fields, and the mutants they kill | the profiles and sizes, the shards, the mutants, the audits; adding a property |
| `unit/` | examples at the edges, the rules over source files, and the scripts in `scripts/` | what belongs there |
| `typing/` | a consumer's code, type-checked by CI against the built wheel | how CI runs it |
| `fuzz/` | Atheris targets: raw bytes into the JSON reader, and the properties driven by Atheris | running them; the control |

`conftest.py` here registers the Hypothesis profiles for every test and the property shards (`--shard`), selects
the mutant searches and the audit controls (`--property-controls only`) or every other test (`none`), as CI's
test matrix splits them, records each test's CPU time for a JUnit report (`--junitxml`, which CI's durations
report reads), and prints the count of conformance case files after a run that included them.

## Running

```sh
uv sync
uv run pytest                                                   # everything, properties at `dev`
MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest tests/property --shard records -n auto --dist worksteal   # one shard of CI's Hypothesis job
```

## Every check can fail

A check that cannot fail is not a check. So each kind here comes with tests in which it must fail:

- the conformance runner: broken implementations, one fault each (`conformance/test_runner_can_fail.py`), and
  a comparator fed wrong answers (`conformance/test_comparator.py`);
- each property: mutants of the core, or of the writer schema, one fault each, that it must kill at both tree
  sizes, a writer mutant at the assertion it names (`property/test_mutants.py`,
  `property/test_record_mutants.py`, `property/test_value_field_mutants.py`, `property/test_writer_mutants.py`),
  and a feature audit that fails when its examples stop reaching what the specification distinguishes;
- the `CASES.md` check: a case file changed after its row (`spec_sync/test_cases_md.py`);
- the value-field checks: a member table, a status row or a quote changed, the schema changed, and a binding
  of the vocabulary changed or no longer applied (`spec_sync/test_value_fields.py`);
- the name-overlap check: a reused name or a slip seeded into a schema, the vocabulary or an example, and its
  allowlist broken (`spec_sync/test_name_overlaps.py`);
- the unknown-member positions: an unknown member refused, a slip ignored in a record and in a request, a row's
  verdict wrong, a dead row, a lost quote and a missing row (`spec_sync/test_unknown_member_positions.py`);
- T1, step 8 against the writer schema and the reader `$defs`: a step 8 that refuses what the writer accepts,
  what the reader accepts, or accepts what the reader refuses, reader `$defs` that check a derivation beside
  every origin, and an exception missing, stale, listed twice, listed by name where a case file reads it, or
  unreasoned (`spec_sync/test_t1.py`);
  allowlist broken, a safeguard or the maintainer's flag missing, an entry pending once the maintainer has
  answered, and a deferred safeguard come due among them (`spec_sync/test_name_overlaps.py`); its safeguards:
  a place opened to another meaning, and a place no entry lists (`spec_sync/test_name_overlap_safeguards.py`);
- the reason-step check: the table given a step its text lacks or lacking one (step 6 for an overlay among
  them), a code added to a step's text or a passage it hands its checks to, a code constructed at another step
  however the call is written or in a module no list names, and a step-0 function seeded to give `absent`
  (`spec_sync/test_reason_steps.py`);
- the released-schema check, on a copy of the tree with 0.1 frozen: a file changed, added or removed, the
  directory gone, and an `$id` frozen wrong (`spec_sync/test_released_schemas.py`);
- the reference, case-tag and list-number checks: a broken reference of each form, an uncited row, a tag with
  no row and a repeated item (`spec_sync/test_references.py`);
- the draw-rejection audit, the import, layer and SPDX rules and the scripts, generators included: inputs they
  must refuse (`unit/`);
- the consumer snippet: CI deletes `py.typed` from the installed wheel and requires the snippet then to fail;
  and it removes `ReadOnly` from the installed `shapes.pyi` and requires both checkers then to report the
  ignore on the snippet's write into a result as unused (pyright by a setting in the snippet's first line).
