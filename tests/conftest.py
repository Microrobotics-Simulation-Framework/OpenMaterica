# SPDX-License-Identifier: Apache-2.0
"""Hypothesis profiles for every property test, chosen with `MATERICA_HYPOTHESIS_PROFILE`.

`dev` (the default) for a local run and the test matrix, `ci` for CI's Hypothesis job, and `deep` for its
weekly run. A property never sets its own example count, which would override the profile.
"""

import os
import sys
import time
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis.database import DirectoryBasedExampleDatabase

from tests import harvested_constants
from tests.conformance import runner

if sys.platform != "win32":
    import resource

# One example database at a fixed path, whatever the working directory, so that a local run and CI's cached
# copy are the same directory: an example that failed once is replayed first on the next run. `.hypothesis/`
# is git-ignored.
HYPOTHESIS_DATABASE = Path(__file__).resolve().parent.parent / ".hypothesis" / "examples"

# The maintainer's counts: rigour is fixed. `tests/unit/test_hypothesis_profiles.py` holds them, and the
# settings below, to their values, and its controls find these lines by their text.
EXAMPLES = {"dev": 200, "ci": 2_000, "deep": 20_000}

for profile, examples in EXAMPLES.items():
    settings.register_profile(
        profile,
        # Hypothesis's own defaults, not whatever profile is loaded: where `CI` is set, as on GitHub's
        # runners, that is Hypothesis's built-in `ci` profile, whose `derandomize=True` draws the same
        # examples on every run whatever `--hypothesis-seed` says. So no machine's environment changes a
        # setting (`tests/unit/test_hypothesis_profiles.py`).
        parent=settings.get_profile("default"),
        max_examples=examples,
        # Timing on a loaded runner is not a property of the code.
        deadline=None,
        # A CI failure can then be replayed on a machine without the database.
        print_blob=True,
        database=DirectoryBasedExampleDatabase(HYPOTHESIS_DATABASE),
        # Nor is a slow draw on a loaded runner; CI had this from Hypothesis's `ci` profile, and every machine
        # has it now.
        suppress_health_check=[HealthCheck.too_slow],
    )

PROFILE = os.environ.get("MATERICA_HYPOTHESIS_PROFILE", "dev")
if PROFILE not in EXAMPLES:
    raise RuntimeError(f"MATERICA_HYPOTHESIS_PROFILE={PROFILE!r}: expected one of {sorted(EXAMPLES)}")
settings.load_profile(PROFILE)

# Every derandomized run, the mutant searches and the audit controls among them, draws none of the constants
# Hypothesis harvests from the loaded modules, so that what it draws depends on the code alone
# (`harvested_constants.py`).
harvested_constants.pin()


# CI's Hypothesis job runs the property modules in six shards side by side, `--shard json`, `--shard
# records`, `--shard writer`, `--shard agreement`, `--shard step8_mutants` and `--shard conditions`;
# `tests/unit/test_source_files.py` checks that each module is in exactly one.
SHARDS = {
    "json": (
        "test_jsonio_properties",
        "test_canonical_properties",
        "test_hashing_properties",
        "test_slip_properties",
        "test_mutants",
        "test_mutant_view",
    ),
    "records": (
        "test_envelope_properties",
        "test_version_properties",
        "test_read_properties",
        "test_record_mutants",
        "test_value_field_properties",
    ),
    "writer": ("test_writer_properties", "test_writer_mutants", "test_writer_mutant_table"),
    # The two JSON Schema libraries' agreement, whose drawn properties run python-jsonschema on every example
    # and were the writer shard's longest tests; and the anomaly check's YAML reader's agreement with PyYAML.
    "agreement": ("test_validators_agree", "test_anomaly_reader_properties"),
    # Step 8's mutant searches, the longest part of the records shard, and their table's check; they keep no
    # example database.
    "step8_mutants": ("test_value_field_mutants", "test_value_field_mutant_table"),
    # Steps 9 and 10's properties and the result's (S2a-4: HP1, HP2, HP6 and HP11), which read records end to
    # end, their mutant searches, which take seconds and set no example database, so the shard's restored one
    # is harmless to them, and their tables' checks.
    "conditions": (
        "test_condition_properties",
        "test_condition_mutants",
        "test_condition_mutant_table",
        "test_result_properties",
        "test_result_mutants",
        "test_result_mutant_table",
    ),
}


# The mutant searches and the audit controls, which show that the properties and their feature audits can
# fail, by module. They run at the `ci` profile's examples whatever the profile. CI's test matrix runs them on
# the supported range's ends alone, in jobs of their own (`--property-controls only`), and everything else on
# every Python (`--property-controls none`); `tests/unit/test_ci_workflows.py` checks that together the jobs
# leave nothing out. A run without the option runs both.
PROPERTY_CONTROLS = ("test_*mutants*", "test_audit_controls*")


def is_property_control(module: Path) -> bool:
    return any(fnmatch(module.stem, pattern) for pattern in PROPERTY_CONTROLS)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--shard", choices=sorted(SHARDS), help="run only the property modules of this shard")
    parser.addoption(
        "--property-controls",
        choices=["only", "none"],
        help="run only the mutant searches and the audit controls, or none of them",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    shard = config.getoption("--shard")
    controls = config.getoption("--property-controls")

    def kept(item: pytest.Item) -> bool:
        in_shard = shard is None or item.path.stem in SHARDS[shard]
        return in_shard and (controls is None or is_property_control(item.path) == (controls == "only"))

    config.hook.pytest_deselected(items=[item for item in items if not kept(item)])
    items[:] = [item for item in items if kept(item)]


# Each test's CPU time, written beside the wall time in the JUnit XML that CI's durations report reads
# (`scripts/report_test_durations.py`). The xdist workers share a runner's cores, so a test's wall time partly
# measures the others; its CPU time much less. `cpu_seconds` is the CPU time of the test's own process, its
# xdist worker, and `children_cpu_seconds` that of the processes it started and waited for, which the first
# leaves out: a test that runs pytest or git in a subprocess spends its time there. Both span setup, call and
# teardown.
CPU_AT_SETUP = pytest.StashKey[tuple[float, float | None]]()


def children_cpu() -> float | None:
    """The CPU time of the processes this one started that have ended and been waited for; None where Python
    cannot tell (Windows)."""
    if sys.platform == "win32":
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    item.stash[CPU_AT_SETUP] = (time.process_time(), children_cpu())


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    # What `record_property` does, at the last moment it can: the XML takes a test's properties from its
    # teardown report, which is made after the teardown and copies them when made.
    if call.when == "teardown" and CPU_AT_SETUP in item.stash:
        own, children = item.stash[CPU_AT_SETUP]
        item.user_properties.append(("cpu_seconds", f"{time.process_time() - own:.3f}"))
        children_now = children_cpu()
        if children is not None and children_now is not None:
            item.user_properties.append(("children_cpu_seconds", f"{children_now - children:.3f}"))


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
