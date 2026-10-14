# Tests

| Directory | What it checks | Its README says |
|---|---|---|
| `conformance/` | the specification's conformance cases, run by a runner that counts what it cannot run; the case files themselves | how cases are counted and compared; adding a case |
| `spec_sync/` | what is written in two places: the specification's tables and the schemas, the envelope checks and the reader schema, `CASES.md` and the case files, the cases and the steps that run them, the specification's references and what they name | what each test holds together |
| `property/` | Hypothesis properties of the reader, the canonical form, the hash, the envelope checks, versions and the read, and the mutants they kill | the profiles and sizes, the shards, the mutants, the audits; adding a property |
| `unit/` | examples at the edges, the rules over source files, and the scripts in `scripts/` | what belongs there |
| `typing/` | a consumer's code, type-checked by CI against the built wheel | how CI runs it |
| `fuzz/` | Atheris targets: raw bytes into the JSON reader, and the properties driven by Atheris | running them; the control |

`conftest.py` here registers the Hypothesis profiles for every test and the property shards (`--shard`), and
prints the count of conformance case files after a run that included them.

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
- each property: mutants of the core, one fault each, that it must kill at both tree sizes
  (`property/test_mutants.py`, `property/test_record_mutants.py`), and a feature audit that fails when its
  examples stop reaching what the specification distinguishes;
- the `CASES.md` check: a case file changed after its row (`spec_sync/test_cases_md.py`);
- the reference, case-tag and list-number checks: a broken reference of each form, an uncited row, a tag with
  no row and a repeated item (`spec_sync/test_references.py`);
- the draw-rejection audit, the import, layer and SPDX rules and the scripts, generators included: inputs they
  must refuse (`unit/`);
- the consumer snippet: CI deletes `py.typed` from the installed wheel and requires the snippet then to fail;
  and it removes `ReadOnly` from the installed `shapes.pyi` and requires both checkers then to report the
  ignore on the snippet's write into a result as unused (pyright by a setting in the snippet's first line).
