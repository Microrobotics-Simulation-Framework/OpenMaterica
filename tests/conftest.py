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


# Here rather than in `conformance/`, so that it runs where pytest-xdist's controller, which collects nothing,
# writes the summary.
def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """After a run of the conformance tests, which case files ran and which did not, and why."""
    reports = [report for key in ("passed", "failed") for report in terminalreporter.stats.get(key, [])]
    if not any(str(getattr(report, "nodeid", "")).startswith("tests/conformance/") for report in reports):
        return
    runs = runner.run_all(runner.discover(), claimed=runner.CLAIMED, executors=runner.EXECUTORS)
    outcomes = Counter(case_run.outcome for case_run in runs)
    terminalreporter.section("conformance cases")
    terminalreporter.write_line(f"{len(runs)} case files, claiming {', '.join(sorted(runner.CLAIMED))}")
    for outcome in runner.Outcome:
        line = f"  {outcomes[outcome]:4d} {outcome.value}"
        operations = Counter(case_run.case_file.operation for case_run in runs if case_run.outcome is outcome)
        if operations:
            line += " (" + ", ".join(f"{name} {count}" for name, count in sorted(operations.items())) + ")"
        terminalreporter.write_line(line)
