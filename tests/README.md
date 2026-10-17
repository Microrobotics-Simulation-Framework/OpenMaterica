# Tests

| Directory | What it checks | Its README says |
|---|---|---|
| `conformance/` | the specification's conformance cases, run by a runner that counts what it cannot run; the case files themselves | how cases are counted and compared; adding a case |
| `spec_sync/` | what is written in two places: the specification's tables and the schemas, the envelope checks and the reader schema, `CASES.md` and the case files, the cases and the steps that run them, the specification's references and what they name | what each test holds together |
| `property/` | Hypothesis properties of the reader, the canonical form, the hash, the one-slip relation, the envelope checks, versions, the read and its steps 8 to 10, of the writer schema's value fields, and the mutants they kill | the profiles and sizes, the shards, the mutants, the audits; adding a property |
| `unit/` | examples at the edges, the rules over source files, and the scripts in `scripts/` | what belongs there |
| `typing/` | a consumer's code, type-checked by CI against the built wheel | how CI runs it |
| `fuzz/` | Atheris targets: raw bytes into the JSON reader, and the properties driven by Atheris | running them; the control |

`conftest.py` here registers the Hypothesis profiles for every test, on Hypothesis's own defaults, so that no
machine's environment changes them, and the property shards (`--shard`), selects the mutant searches and the
audit controls (`--property-controls only`) or every other test (`none`), as CI's test matrix splits them,
records each test's CPU time, its own and its child processes', for a JUnit report (`--junitxml`, which CI's
durations report reads), and prints the count of conformance case files after a run that included them.

## Running

```sh
uv sync
uv run pytest -n 12 --dist worksteal                            # everything, properties at `dev`
MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest tests/property --shard records -n auto --dist worksteal   # one shard of CI's Hypothesis job
```

`-n 12` is for a whole run on a machine like the maintainer's (8 performance cores, 24 threads); use `-n 8`
when two such jobs share it. Use `--dist worksteal`, not xdist's default `load`, which hands each worker a
file's tests in blocks, so that a file's slow tests (the audit controls, T1's shares) pile onto one worker
while the others idle. There, at `dev` (2026-10-16): 6 workers took 6.0 minutes under `load` and 4.0 under
`worksteal`, and 12 took 2.9 under `worksteal`; more than 12 gained nothing.

CI draws as a local run does: new examples on every run, and under one `--hypothesis-seed` the same examples
as any machine. Until 2026-10-17 it drew the same examples on every run of the same code, whatever the seed:
GitHub sets `CI`, on which Hypothesis loads its own derandomised `ci` profile, and the profiles inherited it
(`property/README.md`, "Profiles and sizes").

## Repeat runs on CI

To show how often a test fails, run it many times on CI, not in a loop here (maintainer, 2026-10-17): GitHub's
runners are free for this public repository, so a few hundred runs, ten jobs at a time, take minutes rather than
hours, with the same examples. The workflow `repeat.yml` runs a node, a test, a file
or a directory under `tests/`, under many seeds in parallel jobs (`.github/workflows/README.md` says what each job
does). It runs on a pushed ref: an agent asks the main session to dispatch it on its pushed draft and waits on the
result.

```sh
gh workflow run repeat.yml --ref <branch> -f node=tests/property/test_x.py::test_y -f profile=ci \
  -f jobs=10 -f runs=20 -f first_seed=1          # 200 runs, seeds 1 to 200
gh run list --workflow repeat.yml --limit 3      # the run's id
gh run watch <id> --exit-status                  # waits; exits non-zero where any run failed
gh run view <id>                                 # the verdict, among the annotations
gh run download <id> -n runs-3-1                 # job 3's records: results.jsonl and each run's JUnit report
```

The inputs: `node`, required; `profile`, `dev`, `ci` (the default) or `deep`, whose example counts are
`tests/conftest.py`'s and nothing else's; `jobs`, 1 to 20 (default 10), and `runs` in each, 1 to 25 (default 20);
`first_seed`, 0 to 999999999 (default 1), the runs taking the seeds from it to `first_seed + jobs × runs − 1`;
`python`, 3.11 to 3.15 (default 3.15); and `extra`, of `--shard NAME` and `--property-controls only|none` alone.
A request out of bounds, or a node pytest cannot collect with those arguments, fails the `request` job, and no
run starts. A run takes about as long as the same tests in CI's jobs at that profile, and at `deep`, with ten
times the examples, about ten times as long as at `ci`: choose the runs a job to fit its timeout (60 minutes at
`dev`, 120 at `ci`, 360 at `deep`), and more jobs for more runs. At most ten jobs run at once, and more queue
inside the run: the organisation's 60 concurrent jobs (its plan's) are shared by this repository's CI and MIME's
and MADDENING's.

The summary, on the run's page, gives the runs that passed, failed, did not finish or have no record, and a
verdict: "no run of 200 failed: the failure rate is at most 1.49 % (one-sided 95%)", or, with three failures,
"3 of 200 runs failed (1.5 %); the failure rate is at most 3.83 % (one-sided 95%)" (the exact Clopper-Pearson
bound; with none failed in `n` runs it is about `3 / n`). It shows each failing seed with its failing example
and the `@reproduce_failure` line Hypothesis printed, and fails the run where any run failed or did not finish.
Never re-run a repeat run's jobs: dispatch the request anew. Each attempt keeps its records under a name of its
own (`runs-<job>-<attempt>`). The summary counts every record it finds, and of a seed recorded twice the record
that did not pass, but fails on any attempt but the first.
A failing seed replays here with the same examples, whatever the machine:
`MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest <node> --hypothesis-seed=<seed>`, as does its `@reproduce_failure`
line. A run under a seed neither reads nor saves the example database, and `.hypothesis/` is removed before each
run.

A seed changes what a test draws only where Hypothesis draws at random. A derandomized test, which Hypothesis
runs the same whatever `--hypothesis-seed` says (6.169 reads `derandomize=True` first), runs the same examples
under every seed: the mutant searches (`MUTANT_SEARCH` in `property/support.py`), the audit controls
(`unit/test_audit_controls.py`), which are what `--property-controls only` selects, and some tests of
`unit/test_audits.py`. So does a test under `@seed`, and a test without Hypothesis. Repeating those measures only
what else varies between runs.

Until the profiles stopped inheriting Hypothesis's own `ci` profile (above, "Running"), so did every test on
GitHub's runners: every run of a repeat run drew the same examples whatever its seed.

## Schema verdicts

Every verdict the tests take from the package's JSON Schemas comes from jsonschema-rs (`verdicts.py`), alone
in loops and beside python-jsonschema's elsewhere (`spec_sync/schemas.py`); python-jsonschema prints the
messages of a failure and, a second implementation, is held to the same verdicts
(`property/test_validators_agree.py`, the Hypothesis job's `agreement` shard). The switch cut the CPU time the
tests take, measured back to back on a shared machine (2026-10-16): the whole suite on 8 workers from 2,617 s
to 1,620 s, and the writer shard at `ci` on 4 from 2,956 s to 1,477 s. `spec_sync/test_t1.py` alone, on 4
workers, ran about 25 times faster: 221 s before, 9.4 s and 7.8 s after (2026-10-17). On CI the writer shard's
tests went from 649 s to 338 s (runs 38906952291 and 38963555727). Wall time on this machine moves by about a
quarter between runs in a way load does not explain: the same pair of trees took 357 s and 294 s in one pass,
363 s and 233 s in another. With the agreement's later checks and its own shard (2026-10-17, load 2 to 7), the
whole suite on 8 workers took 111 s, 726 s of CPU; the writer shard at `ci` on 4, 151 s, 521 s of CPU; the
agreement shard at `ci` on 4, 241 s, 480 s of CPU.

## Every check can fail

A check that cannot fail is not a check. So each kind here comes with tests in which it must fail:

- the conformance runner: broken implementations, one fault each (`conformance/test_runner_can_fail.py`), and
  a comparator fed wrong answers (`conformance/test_comparator.py`);
- each property: mutants of the core, or of the writer schema, one fault each, that it must kill at both tree
  sizes, a writer mutant at the assertion it names (`property/test_mutants.py`,
  `property/test_record_mutants.py`, `property/test_value_field_mutants.py`, `property/test_condition_mutants.py`,
  `property/test_writer_mutants.py`),
  and a feature audit that fails when its examples stop reaching what the specification distinguishes;
- the two validators' agreement: writer and reader mutants given to one side, each of the 12 writer mutants
  the drawn faults had missed among them; a pattern the two regex dialects read differently given to both; the
  pairs the properties use held to both libraries; and a module that takes jsonschema-rs's verdict alone
  without being listed (`property/test_validators_agree.py`); a disagreement in a test's own verdict, and a
  schema that declares another draft (`unit/test_verdicts.py`); and a pattern or keyword the two could read
  differently (`spec_sync/test_schemas.py`);
- the `CASES.md` check: a case file changed after its row (`spec_sync/test_cases_md.py`);
- the value-field checks: a member table, a status row or a quote changed, the schema changed, and a binding
  of the vocabulary changed or no longer applied (`spec_sync/test_value_fields.py`);
- the name-overlap check: a reused name or a slip seeded into a schema, the vocabulary or an example, and its
  allowlist broken (`spec_sync/test_name_overlaps.py`);
- the unknown-member positions: an unknown member refused, a slip ignored in a record and in a request, a row's
  verdict wrong, a dead row, a lost quote, a missing row, and an implied condition's member dropped from a row
  or from the read (`spec_sync/test_unknown_member_positions.py`);
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
