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
machine's environment changes them, and the property shards (`--shard`), keeps every derandomized run from
drawing the constants Hypothesis harvests from the loaded modules (`harvested_constants.py`), selects the
mutant searches and the audit controls (`--property-controls only`) or every other test (`none`), as CI's test
matrix splits them, records each test's CPU time, its own and its child processes', for a JUnit report
(`--junitxml`, which CI's durations report reads), and prints the count of conformance case files after a run
that included them.

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
as any machine. Until #38 it drew the same examples on every run of the same code, whatever the seed: GitHub
sets `CI`, on which Hypothesis loads its own derandomised `ci` profile, and the profiles inherited it
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
`dev`, 120 at `ci`, 360 at `deep`), and more jobs for more runs. At most `REPEAT_MAX_PARALLEL` jobs run at once,
a repository variable, 10 where it is unset, and more queue inside the run: the organisation's 60 concurrent jobs
(its plan's) are shared by this repository's CI and MIME's and MADDENING's (`.github/workflows/README.md`, "Jobs
at once", says when to change it).

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
what else varies between runs. For a derandomized test that is nothing it draws: it draws none of the constants
Hypothesis harvests from the loaded modules (`harvested_constants.py`), so its examples, and a mutant's kill
count, depend on the code alone. A test under `@seed` still draws them, so its examples also change with the
modules outside `tests/` that the process has loaded. The request job says so: where the node collects a test in
a module that `--property-controls only` selects, or whose own code sets `derandomize=True` or runs
`property/support.py`'s `MUTANT_SEARCH`, it warns, naming the modules, and runs the request all the same (#43's
review, L7), since repeating such a test on a head and on its base is still a valid comparison. A module that
runs another module's search through a function it imports (`property/test_validators_agree.py`) is not found.

Two limits of that pin, neither met by a test here (the review measured both; details in
`harvested_constants.py`): a search run inside the body of another that draws with `st.data()`, derandomized in
one and random in the other, leaks the pool into the derandomized draws or takes it from the random ones (81
of 6,000 draws, and 106 to 0); and a derandomized test that calls `settings.load_profile` in its body draws
the pool afterwards (14 of 2,400). A test that does either is outside the pin's guarantee.

Until the profiles stopped inheriting Hypothesis's own `ci` profile (above, "Running"), so did every test on
GitHub's runners: every run of a repeat run drew the same examples whatever its seed.

## Mutant tables on CI

To show that a branch's tests kill its hand mutants, run the mutants on CI, not one after another here
(maintainer, 2026-10-18): one review's run of the suite against its mutants took about five hours on the
shared laptop. The workflow `mutants.yml` runs each mutant in a job of its own, ten at a time by default,
beside the branch as it is, and writes one table (`.github/workflows/README.md` says what each job does and
what it refuses). It runs on a pushed ref: a reviewer, or an agent through the main session, commits the
mutants to a branch of their own, which is never merged, and dispatches the workflow on it.

1. Branch from the head under review, and write each mutant as a patch of the tree, one file each, under
   `mutants/`, named by letters, digits, `_` and `-` (for a new file, `git add -N` it before `git diff`).
   After each, the line that writes its patch takes the edit out of the index and the tree, a file it added
   too, so that the next patch holds the next mutant alone (`git checkout` alone would leave a file added
   with `git add -N` in both, and every later patch would carry it); add any other directory the mutant
   touched beside `src tests`:

   ```sh
   git switch -c mutants/<review> <head> && mkdir -p mutants
   # make the mutant's edit, then
   git diff > mutants/m01.patch && git reset -q && git checkout -- src tests && git clean -fdq -- src tests
   git add mutants && git commit -s -m "mutants for <review>"     # the patches alone, never the edits
   git push -u origin mutants/<review>
   ```

   A patch is the tree's own `git diff`: edits, new files and deleted files of source or tests, never a
   rename, in any form, a link, binary data, `.github/`, `mutants/`, a path git ignores (`.venv/`,
   `.hypothesis/`), `scripts/mutant_runs.py`, or what decides what uv installs or how it runs
   (`pyproject.toml`, `uv.lock`, `uv.toml`, `.python-version`, `.python-versions`). The request checks every
   patch it names before any mutant runs, and refuses the run for any other.
2. Dispatch, and wait:

   ```sh
   gh workflow run mutants.yml --ref mutants/<review> -f selection=tests      # every patch in mutants/
   gh workflow run mutants.yml --ref mutants/<review> -f mutants="m01 m07" \
     -f selection="tests/unit/test_read.py tests/property/test_read_properties.py" -f profile=dev
   gh run list --workflow mutants.yml --limit 3     # the run's id
   gh run watch <id> --exit-status                  # exits non-zero unless every mutant was killed
   ```

3. Read the table, on the run's page or as a file:

   ```sh
   gh run view <id> --web
   gh run download <id> -n mutant-table-1           # table.md and table.json
   ```

The inputs: `mutants`, the names, space-separated, or none for every patch committed in `mutants/`;
`selection`, paths or nodes under `tests/`, space-separated (`tests` by default, the whole suite); `profile`,
`dev` (the default, a local run's), `ci` or `deep`, whose example counts are `tests/conftest.py`'s and nothing
else's; `python`, 3.11 to 3.15 (default 3.15); `seed`, the one Hypothesis seed every run draws under, or none
for one drawn at random, which the table gives; and `extra`, of `--shard NAME` and
`--property-controls only|none` alone. At most `MUTANT_MAX_PARALLEL` mutants run at once, a repository
variable, 10 where it is unset (`.github/workflows/README.md`, "Jobs at once").

The table has a row for the baseline, the branch as it is, and one for each mutant, with the paths its patch
touches: **killed**, with the test
that failed first, always one the collect step listed; **survived**, every selected test passed; **broken**,
the patch does not apply, or the code does not import or the selection does not collect, in one process or
under pytest-xdist (whose report then names a module or a worker, such as `gw0`, where a test should be),
with why; or **undecided**, with why (the job ran out of
time, pytest stopped another way, or the record is missing or doubled). Where the baseline did not pass, no
mutant counts as killed. The run passes only when the baseline passed and every mutant was killed; a mutant
that survives because it changes nothing (an equivalent mutant) leaves it red, and the reviewer says so where
the table is cited. A run stops at its first failure, so a killed mutant's row names one killer, not all of
them. A kill by a patch that edits the tests or pytest's settings (anything under `tests/`, a `conftest.py`,
a `pytest.ini`, `tox.ini`, `setup.cfg` or `pyproject.toml` beside the tests, or `sitecustomize.py`) is
marked, in its row and in the verdict: the edit, not the code, may have failed the test, so read the patch
before citing it.

A mutant's run replays here with the same examples when it runs the same selection, the table's line:

```sh
git apply mutants/<name>.patch
MATERICA_HYPOTHESIS_PROFILE=<profile> uv run pytest -x <the selection> <the extra arguments> \
  --hypothesis-seed=<the table's seed>
```

A run of the failed test alone loads fewer modules and may draw other examples under the same seed: Hypothesis
draws constants from the modules outside `tests/` that are loaded (`tests/property/audits.py`, lines 83-84,
`replay`; `tests/unit/test_audit_replay.py` holds it). For the same reason the one seed makes a chance failure of
the baseline's draws one of a mutant's only where the mutant leaves the constants of every module it loads
outside `tests/` alone: a mutant that changes a literal draws examples of its own. Both hold for the tests
Hypothesis draws at random; a derandomized test draws none of those constants (`harvested_constants.py`), so it
replays alone, and draws the same examples under every mutant.

Never re-run a mutant table's jobs: dispatch it anew, as the table fails on any attempt but the first.

## The whole suite on CI

A branch's whole suite runs on CI without a run here. Once the main session has pushed a branch as a draft
pull request, `ci.yml` runs the suite at `dev` on its head (the `tests` and `controls` jobs, on every Python,
the mutant searches and audit controls on the range's ends) and on each earlier commit (the `commit` job), and
the Hypothesis job at `ci`; `gh pr checks <number>` shows their result. A pushed branch with no pull request
runs it through `repeat.yml`, the whole suite once under one seed:

```sh
gh workflow run repeat.yml --ref <branch> -f node=tests -f profile=dev -f jobs=1 -f runs=1
```

Each job runs a worker per vCPU, four on GitHub's runner, which it has to itself; `-n 8` and `-n 12` here are
about sharing this machine (`.github/workflows/README.md`, "The whole suite on CI").

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
