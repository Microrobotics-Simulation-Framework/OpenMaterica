# Workflows

`ci.yml` checks every change. Its opening comment says why it is shaped as it is; this table says what runs,
and `tests/unit/test_ci_workflows.py` holds its jobs and shards to `ci.yml`, with what each pytest command
selects; no job or step carries on after a failure (`continue-on-error`).
`pages.yml` deploys `site/` to openmaterica.org on a push to main that touches it.
`repeat.yml` runs one test many times, each run under a seed of its own, when dispatched by hand (below).

| Job | Runs | When |
|---|---|---|
| `gate` | the sign-off check (`scripts/check_signoff.py`) on a pull request, and the confidentiality scan; decides which jobs run: on a pull request from the paths it touched, otherwise every job (no other job with `fuzz_only`) | always |
| `static` | ruff, mypy and pyright; `uv build` and the wheel check; the consumer snippet against the installed wheel, and its control | a pull request that changes code, which is any path the gate lists neither as documentation (`docs_paths` in its step) nor as the site's (`site_paths`: `site/`, `assets/`), and any Python file wherever it sits (`python_paths`), since ruff reads it; every merge to main; weekly; manual |
| `generated` | every generator of `scripts/` with `--check`: the vocabulary, the reader schema, the typed shapes; on Python 3.11 | as `static` |
| `tests` | `uv run pytest -n auto`, property tests at the `dev` profile, but the mutant searches and the audit controls (`--property-controls none`) | as `static`; Python 3.11 to 3.15, in parallel |
| `controls` | the mutant searches and the audit controls alone (`--property-controls only`), which run at the `ci` profile's examples whatever the profile, so cost about as much as a Python's other tests: on the supported range's ends, the oldest Python and the newest, which bracket the versions between, each in a job beside that Python's `tests` job, so that neither is the longest | as `static`; Python 3.11 and 3.15 |
| `hypothesis` | the property tests and mutants at the `ci` profile, or `deep` weekly and on a manual run, in six shards side by side (`json`, `records`, `writer`, `agreement`, `step8_mutants`, `conditions`), each with its own example database; on Python 3.15, a worker per vCPU | a pull request that changes any path but the documentation and those no part of the job reads (`hypothesis_free` in the gate's step), any test included; every merge to main; weekly; manual |
| `site` | the site staged exactly as `pages.yml` stages it (its step, word for word), which fails where a file it copies is missing; then `scripts/check_site.py` on the copy: every local link, image and icon of each page and of the web manifest resolves, every page keeps one content security policy, before anything it loads, that lets nothing load from elsewhere, nothing loads from elsewhere, and the README's images name files of the tree; on the runner's Python, seconds long | a pull request that changes any path but documentation alone, `site/` and `assets/` included, which run this job and no code job; every merge to main; weekly; manual |
| `commit` | each commit of a pull request but its head, checked out on its own: the site job's steps, ruff, mypy and pyright, `uv build` and the wheel check, every generator's `--check` (on Python 3.11, as `generated`), and the whole suite at the `dev` profile, the mutant searches and audit controls included, on Python 3.15 under `--dist worksteal`; at most six at once; a commit whose tree passed the same checks earlier in the pull request (kept in the cache under its tree, `ci.yml`'s blob and the runner's image version) is not checked again | a pull request of two commits or more: each commit before the head that changes code, as the gate counts it for `static` |
| `site_commit` | each commit of a pull request but its head that changes the site alone (beside documentation or not), checked out on its own: the site job's steps, word for word; at most six at once | a pull request of two commits or more with such a commit before the head |
| `fuzz` | after `hypothesis`, from the union of the shards' example databases: the Atheris targets of `tests/fuzz/`, after a control with seeded faults, for `fuzz_seconds` each; then the property tests, to replay and shrink what was found; on Python 3.14 | weekly; manual, alone with `fuzz_only` |
| `result` | fails unless every job the gate asked for succeeded (a job skipped by its `if` reports success), and when any job failed or was cancelled: the one check the ruleset on main requires | always |

The `tests` and `commit` jobs run the properties at `dev` on random draws, as a laptop does (since #38), so an
audit can fail a sound property by chance: about once in 2,000 runs of the whole suite (5e-4,
`tests/property/audits.py`). With five `tests` jobs a push, that makes a push red by chance about once in 400
(2.5e-3), and the `commit` job adds 5e-4 for each earlier commit it checks: about once in 220 for a pull request
of five commits (4.5e-3). The `hypothesis` job at `ci` adds about 2e-6, and the `controls` job, whose searches
and controls are derandomised, nothing. Such a failure names the seed that draws its run again, and `repeat.yml`
tells chance from a fault (`tests/property/README.md`, "Audits").

Each pytest job but `commit`, which runs on each earlier commit the suite the head's jobs run, writes a JUnit
report, summarised on the run's page (`scripts/report_test_durations.py`: the tests in each band of wall time, the
slowest tests and files, and the total, wall time and CPU time, the tests' own and their child processes') and kept
90 days as the artifact `durations-<job>-<Python or shard>`, whenever pytest ran.
pytest runs under `timeout --signal=INT`, three minutes before its job's timeout, so that a run out of time stops,
writes the report of the tests that finished and fails, rather than be cancelled without one (`ci.yml` says why).
No duration fails a job.

Every action is pinned to a commit, uv to one version (`UV_VERSION`), and every job of every workflow to the runner
image `ubuntu-24.04` (`ci.yml` says why, above its jobs); `uv sync --locked` fails on a lock file out of date with
`pyproject.toml`.

## Repeat runs (`repeat.yml`)

Run by hand alone (`workflow_dispatch`), never on a push or a pull request: one pytest node, a test, a file or a
directory under `tests/`, run many times in parallel jobs, each run under a seed of its own, to measure how often
it fails (maintainer, 2026-10-17). `tests/README.md`, "Repeat runs on CI", says how to ask for one and how to read
its summary. Its inputs: the node; the profile, one of `tests/conftest.py`'s (`dev`, `ci`, `deep`; `ci` by
default); the jobs, 1 to 20, and the runs in each, 1 to 25; the first seed, 0 to 999999999; the Python, one of
the test matrix's; and extra pytest arguments, `--shard` and `--property-controls` alone.

| Job | Runs | When |
|---|---|---|
| `request` | checks the inputs (`scripts/repeat_runs.py request`, on the runner's Python) and writes them, checked, as its outputs, which the jobs after it read in place of the inputs; then collects the node with the extra arguments, so that a test that does not exist or a value pytest does not list fails before any run starts | every dispatch |
| `runs` | each job its runs one after another, each under its own seed (`--hypothesis-seed`; job `j` of `r` runs from the first seed `s` takes the seeds `s + (j - 1) r` to `s + j r - 1`), `.hypothesis/` removed before each, as CI's test jobs run pytest; each run's record, with its failing examples, kept 90 days as the artifact `runs-<job>-<attempt>`, so that a job run again keeps its records beside its first attempt's; fails where any run failed or did not finish | after `request`, the jobs side by side, ten at most at once (`max-parallel`), none cancelled by another's failure (`fail-fast: false`) |
| `summary` | sums every job's records on the run's page: the runs, the failures with their seeds and failing examples, and the failure rate with its exact one-sided 95 % upper bound (`scripts/repeat_runs.py summary`); fails where a run failed or did not finish, a seed has no record or two, a job of runs did not succeed, or the run is on an attempt but its first | after the runs, whatever their result, once the request was checked |

No input reaches a profile's example count, deadline or health checks: the profile is chosen from
`tests/conftest.py`'s own, each input reaches a step through its environment alone and is checked before any job
reads it, and no extra argument but the two listed is taken. A job of runs starts no run, and interrupts the one
running (`uv run timeout --signal=INT`, as `ci.yml`'s jobs do), three minutes before its timeout: 60 minutes at
`dev`, 120 at `ci`, 360 at `deep`. The workflow reads the repository alone (`contents: read`), reads no secret,
and restores the uv cache CI saved but saves none. A dispatch waits behind a running one of the same inputs on the
same ref, whose seeds it would repeat; one of other inputs runs beside it, and none is cancelled.
Each run draws what its seed draws on any machine. Until `tests/conftest.py`'s profiles stopped inheriting
Hypothesis's own `ci` profile, which `CI=true` loads on every runner and which sets `derandomize=True`, every run
drew the same examples whatever its seed (`tests/README.md`, "Repeat runs on CI").
`tests/unit/test_ci_workflows.py` holds it to each of these, running its steps as written.
