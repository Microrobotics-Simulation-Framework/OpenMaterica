# Workflows

`ci.yml` is the one workflow. Its opening comment says why it is shaped as it is; this table says what runs.

| Job | Runs | When |
|---|---|---|
| `gate` | the sign-off check (`scripts/check_signoff.py`) on a pull request; finds the paths a change touched | always |
| `static` | ruff, mypy and pyright; `uv build` and the wheel check; the consumer snippet against the installed wheel, and its control | a change to code: `src/`, `tests/`, `scripts/`, `docs/specification/`, `pyproject.toml`, `uv.lock`, `ci.yml` |
| `tests` | `uv run pytest`, property tests at the `dev` profile | as `static`; pull requests on Python 3.11 and 3.15, otherwise 3.11 to 3.15 |
| `hypothesis` | the property tests and mutants at the `ci` profile, or `deep` weekly and on a manual run; on Python 3.15, a worker per vCPU | a change to `src/materica/core/`, `tests/property/`, `tests/conftest.py` or the configuration; every code change to main; weekly; manual |

Every action is pinned to a commit, and uv to one version (`UV_VERSION`); `uv sync --locked` fails on a lock
file out of date with `pyproject.toml`.
