# Tests

| Directory | What it checks | Its README says |
|---|---|---|
| `conformance/` | the specification's conformance cases, run by a runner that counts what it cannot run yet | how cases are counted and compared; adding a case |
| `property/` | Hypothesis properties of the reader, the canonical form and the hash, and the mutants they kill | the profiles and sizes, the mutants, the audits; adding a property |
| `unit/` | examples at the edges, the rules over source files, and the checks in `scripts/` | what belongs there |
| `typing/` | a consumer's code, type-checked by CI against the built wheel | how CI runs it |

`conftest.py` here registers the Hypothesis profiles for every test, and prints the count of conformance case
files after a run that included them.

## Running

```sh
uv sync
uv run pytest                                                   # everything, properties at `dev`
MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest tests/property -n auto --dist worksteal   # as CI's Hypothesis job
```

## Every check can fail

A check that cannot fail is not a check. So each kind here comes with tests in which it must fail:

- the conformance runner: broken implementations, one fault each (`conformance/test_runner_can_fail.py`), and
  a comparator fed wrong answers (`conformance/test_comparator.py`);
- each property: mutants of the core, one fault each, that it must kill at both tree sizes
  (`property/test_mutants.py`), and a feature audit that fails when its examples stop reaching what the
  specification distinguishes;
- the draw-rejection audit, the import and SPDX rules and both scripts: inputs they must refuse (`unit/`);
- the consumer snippet: CI deletes `py.typed` from the installed wheel and requires the snippet then to fail.
