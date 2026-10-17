# Workflows

`ci.yml` checks every change. Its opening comment says why it is shaped as it is; this table says what runs,
and `tests/unit/test_ci_workflows.py` holds its jobs and shards to `ci.yml`, with what each pytest command
selects; no job or step carries on after a failure (`continue-on-error`).
`pages.yml` deploys `site/` to openmaterica.org on a push to main that touches it.

| Job | Runs | When |
|---|---|---|
| `gate` | the sign-off check (`scripts/check_signoff.py`) on a pull request, and the confidentiality scan; decides which jobs run: on a pull request from the paths it touched, otherwise every job (no other job with `fuzz_only`) | always |
| `static` | ruff, mypy and pyright; `uv build` and the wheel check; the consumer snippet against the installed wheel, and its control | a pull request that changes code, which is any path the gate lists neither as documentation (`docs_paths` in its step) nor as the site's (`site_paths`: `site/`, `assets/`), and any Python file wherever it sits (`python_paths`), since ruff reads it; every merge to main; weekly; manual |
| `generated` | every generator of `scripts/` with `--check`: the vocabulary, the reader schema, the typed shapes; on Python 3.11 | as `static` |
| `tests` | `uv run pytest -n auto`, property tests at the `dev` profile, but the mutant searches and the audit controls (`--property-controls none`) | as `static`; Python 3.11 to 3.15, in parallel |
| `controls` | the mutant searches and the audit controls alone (`--property-controls only`), which run at the `ci` profile's examples whatever the profile, so cost about as much as a Python's other tests: on the supported range's ends, the oldest Python and the newest, which bracket the versions between, each in a job beside that Python's `tests` job, so that neither is the longest | as `static`; Python 3.11 and 3.15 |
| `hypothesis` | the property tests and mutants at the `ci` profile, or `deep` weekly and on a manual run, in six shards side by side (`json`, `records`, `writer`, `agreement`, `step8_mutants`, `conditions`), each with its own example database; on Python 3.15, a worker per vCPU | a pull request that changes any path but the documentation and those no part of the job reads (`hypothesis_free` in the gate's step), any test included; every merge to main; weekly; manual |
| `site` | the site staged exactly as `pages.yml` stages it (its step, word for word), which fails where a file it copies is missing; then `scripts/check_site.py` on the copy: every local link, image and icon of each page and of the web manifest resolves, every page keeps one content security policy, before anything it loads, that lets nothing load from elsewhere, nothing loads from elsewhere, and the README's images name files of the tree; on the runner's Python, seconds long | a pull request that changes any path but documentation alone, `site/` and `assets/` included, which run this job and no code job; every merge to main; weekly; manual |
| `commit` | each commit of a pull request but its head, checked out on its own: ruff, mypy and pyright, `uv build` and the wheel check, every generator's `--check` (on Python 3.11, as `generated`), and the whole suite at the `dev` profile, the mutant searches and audit controls included, on Python 3.15 under `--dist worksteal`; at most six at once; a commit whose tree passed the same checks earlier in the pull request (kept in the cache under its tree, `ci.yml`'s blob and the runner's image version) is not checked again | a pull request of two commits or more: each commit before the head that changes code, as the gate counts it for `static` |
| `fuzz` | after `hypothesis`, from the union of the shards' example databases: the Atheris targets of `tests/fuzz/`, after a control with seeded faults, for `fuzz_seconds` each; then the property tests, to replay and shrink what was found; on Python 3.14 | weekly; manual, alone with `fuzz_only` |
| `result` | fails unless every job the gate asked for succeeded (a job skipped by its `if` reports success), and when any job failed or was cancelled: the one check the ruleset on main requires | always |

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
