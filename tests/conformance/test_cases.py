# SPDX-License-Identifier: Apache-2.0
"""Every conformance case file: those this implementation runs must pass, and the rest are counted.

A case file that is not run is never a pytest item, so it cannot read as a pass or a skip; the counts below
and the terminal summary (`conftest.py`) account for it. A case file is not yet runnable while its operation
has no executor or a step it needs is not done (`tests/spec_sync/case_steps.json`).
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from tests.conformance import runner
from tests.conformance.runner import CONFIGURATIONS, EXECUTORS, CaseFile, Outcome

CASE_FILES = runner.discover()
RUN = [
    case_file
    for case_file in CASE_FILES
    if runner.not_run_because(case_file, configurations=CONFIGURATIONS, executors=EXECUTORS) is None
]


@pytest.mark.parametrize("case_file", RUN, ids=[case_file.path.name for case_file in RUN])
def test_case_file(case_file: CaseFile) -> None:
    case_run = runner.run(case_file, configurations=CONFIGURATIONS, executors=EXECUTORS)
    assert case_run.outcome is Outcome.PASSED, "\n".join(case_run.differences)


def test_every_case_file_is_counted() -> None:
    runs = runner.run_all(CASE_FILES, configurations=CONFIGURATIONS, executors=EXECUTORS)
    assert len(runs) == 1258
    assert Counter(case_run.outcome for case_run in runs) == {
        Outcome.PASSED: 637,
        Outcome.NOT_YET_RUNNABLE: 621,
    }
    by_operation = Counter((case_run.outcome, case_run.case_file.operation) for case_run in runs)
    assert by_operation == {
        (Outcome.PASSED, "content_hash"): 51,
        (Outcome.PASSED, "read"): 561,
        (Outcome.PASSED, "list_records"): 25,
        (Outcome.NOT_YET_RUNNABLE, "read"): 586,
        (Outcome.NOT_YET_RUNNABLE, "evaluate"): 35,
    }


def test_each_configuration_runs_every_case_file_that_holds_for_it() -> None:
    claims = Counter(
        claimed for case_file in CASE_FILES for claimed in runner.agreeing(case_file, CONFIGURATIONS)
    )
    assert claims == {CONFIGURATIONS[0]: 1208, CONFIGURATIONS[1]: 1150, CONFIGURATIONS[2]: 1208}


def test_a_case_passes_only_where_a_variant_ran() -> None:
    outcomes = runner.case_outcomes(
        runner.run_all(CASE_FILES, configurations=CONFIGURATIONS, executors=EXECUTORS)
    )
    assert len(outcomes) == 116
    assert Counter(outcomes.values()) == {Outcome.PASSED: 55, Outcome.NOT_YET_RUNNABLE: 61}


def test_a_case_file_runs_once_every_step_it_needs_is_done(tmp_path: Path) -> None:
    case_file = next(case_file for case_file in CASE_FILES if case_file.path.name == "PR-310.absent.json")
    entries: list[tuple[str | list[str] | None, bool]] = [
        ("S1", True),
        ("S3", False),
        (["S1", "S3"], False),
        (None, True),
    ]
    for number, (entry, done) in enumerate(entries):
        case_steps = tmp_path / f"case_steps_{number}.json"  # one file each: the runner reads each path once
        mapped = {} if entry is None else {case_file.path.name: entry}
        case_steps.write_text(json.dumps({"done": ["S1"], "case_files": mapped}), encoding="utf-8")
        assert runner.step_done(case_file, case_steps) is done, entry
