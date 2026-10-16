# Workflows

`ci.yml` checks every change. Its opening comment says why it is shaped as it is; this table says what runs.
`pages.yml` deploys `site/` to openmaterica.org on a push to main that touches it.

| Job | Runs | When |
|---|---|---|
| `gate` | the sign-off check (`scripts/check_signoff.py`) on a pull request; finds the paths a change touched | always |
| `static` | ruff, mypy and pyright; `uv build` and the wheel check; the consumer snippet against the installed wheel, and its control | a change to code: `src/`, `tests/`, `scripts/`, `docs/specification/`, `pyproject.toml`, `uv.lock`, `ci.yml` |
| `generated` | every generator of `scripts/` with `--check`: the vocabulary, the reader schema, the typed shapes; on Python 3.11 | as `static` |
| `tests` | `uv run pytest -n auto`, property tests at the `dev` profile | as `static`; Python 3.11 to 3.15, in parallel |
| `hypothesis` | the property tests and mutants at the `ci` profile, or `deep` weekly and on a manual run, in three shards side by side (`json`, `records`, `writer`), each with its own example database; on Python 3.15, a worker per vCPU | a change to `src/materica/core/`, `schema/` (the vocabulary included), the shapes, `tests/property/`, `tests/conftest.py`, `tests/spec_sync/schemas.py` or the configuration; every code change to main; weekly; manual |
| `fuzz` | after `hypothesis`, from the union of the shards' example databases: the Atheris targets of `tests/fuzz/`, after a control with seeded faults, for `fuzz_seconds` each; then the property tests, to replay and shrink what was found; on Python 3.14 | weekly; manual, alone with `fuzz_only` |
| `result` | fails when a job it needs failed or was cancelled: the one check the ruleset on main requires | always |

Each pytest job writes a JUnit report, summarised on the run's page (`scripts/report_test_durations.py`: the tests
in each band of wall time, the slowest tests and files, and the total, wall and CPU time) and kept 90 days as
the artifact `durations-<job>-<Python or shard>`. No duration fails a job.

Every action is pinned to a commit, uv to one version (`UV_VERSION`), and every job of every workflow to the runner
image `ubuntu-24.04` (`ci.yml` says why, above its jobs); `uv sync --locked` fails on a lock file out of date with
`pyproject.toml`.
