# SPDX-License-Identifier: Apache-2.0
"""Hypothesis profiles for every property test, chosen with `MATERICA_HYPOTHESIS_PROFILE`.

`dev` (the default) for a local run and the test matrix, `ci` for CI's Hypothesis job, and `deep` for its
weekly run. A property never sets its own example count, which would override the profile.
"""

import os
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

from tests.conformance import runner

# One example database at a fixed path, whatever the working directory, so that a local run and CI's cached
# copy are the same directory: an example that failed once is replayed first on the next run. `.hypothesis/`
# is git-ignored.
HYPOTHESIS_DATABASE = Path(__file__).resolve().parent.parent / ".hypothesis" / "examples"

EXAMPLES = {"dev": 200, "ci": 2_000, "deep": 20_000}

for profile, examples in EXAMPLES.items():
    settings.register_profile(
        profile,
        max_examples=examples,
        # Timing on a loaded runner is not a property of the code.
        deadline=None,
        # A CI failure can then be replayed on a machine without the database.
        print_blob=True,
        database=DirectoryBasedExampleDatabase(HYPOTHESIS_DATABASE),
    )

PROFILE = os.environ.get("MATERICA_HYPOTHESIS_PROFILE", "dev")
if PROFILE not in EXAMPLES:
    raise RuntimeError(f"MATERICA_HYPOTHESIS_PROFILE={PROFILE!r}: expected one of {sorted(EXAMPLES)}")
settings.load_profile(PROFILE)


# CI's Hypothesis job runs the property modules in two shards side by side, `--shard json` and `--shard
# records`; `tests/unit/test_source_files.py` checks that each module is in exactly one.
SHARDS = {
    "json": (
        "test_jsonio_properties",
        "test_canonical_properties",
        "test_hashing_properties",
        "test_mutants",
    ),
    "records": (
        "test_envelope_properties",
        "test_version_properties",
        "test_read_properties",
        "test_record_mutants",
    ),
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--shard", choices=sorted(SHARDS), help="run only the property modules of this shard")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    shard = config.getoption("--shard")
    if shard is not None:
        dropped = [item for item in items if item.path.stem not in SHARDS[shard]]
        config.hook.pytest_deselected(items=dropped)
        items[:] = [item for item in items if item.path.stem in SHARDS[shard]]


# Here rather than in `conformance/`, so that it runs where pytest-xdist's controller, which collects nothing,
# writes the summary.
def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """After a run of the conformance tests, which case files ran and which did not, and why."""
    reports = [report for key in ("passed", "failed") for report in terminalreporter.stats.get(key, [])]
    if not any(str(getattr(report, "nodeid", "")).startswith("tests/conformance/") for report in reports):
        return
    runs = runner.run_all(runner.discover(), configurations=runner.CONFIGURATIONS, executors=runner.EXECUTORS)
    outcomes = Counter(case_run.outcome for case_run in runs)
    terminalreporter.section("conformance cases")
    claims = "; ".join(", ".join(sorted(claimed)) for claimed in runner.CONFIGURATIONS)
    terminalreporter.write_line(
        f"{len(runs)} case files, each under every one of these claims it agrees with: {claims}"
    )
    for outcome in runner.Outcome:
        line = f"  {outcomes[outcome]:4d} {outcome.value}"
        operations = Counter(case_run.case_file.operation for case_run in runs if case_run.outcome is outcome)
        if operations:
            line += " (" + ", ".join(f"{name} {count}" for name, count in sorted(operations.items())) + ")"
        terminalreporter.write_line(line)
        if outcome is runner.Outcome.NOT_YET_RUNNABLE and outcomes[outcome]:
            steps = Counter(
                "+".join(runner.steps(case_run.case_file)) or "no executor"
                for case_run in runs
                if case_run.outcome is outcome
            )
            terminalreporter.write_line(
                "       by step: " + ", ".join(f"{step} {count}" for step, count in sorted(steps.items()))
            )
