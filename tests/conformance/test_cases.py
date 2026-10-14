# SPDX-License-Identifier: Apache-2.0
"""Every conformance case file: those this implementation runs must pass, and the rest are counted.

A case file that is not run is never a pytest item, so it cannot read as a pass or a skip; the counts below
and the terminal summary (`conftest.py`) account for it.
"""

from collections import Counter

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
    assert len(runs) == 417
    assert Counter(case_run.outcome for case_run in runs) == {Outcome.PASSED: 417}
    passed = Counter(case_run.case_file.operation for case_run in runs)
    assert passed == {"content_hash": 51, "read": 341, "list_records": 25}


def test_each_configuration_runs_every_case_file_that_holds_for_it() -> None:
    claims = Counter(
        claimed for case_file in CASE_FILES for claimed in runner.agreeing(case_file, CONFIGURATIONS)
    )
    assert claims == {CONFIGURATIONS[0]: 409, CONFIGURATIONS[1]: 347, CONFIGURATIONS[2]: 408}


def test_a_case_passes_only_where_a_variant_ran() -> None:
    outcomes = runner.case_outcomes(
        runner.run_all(CASE_FILES, configurations=CONFIGURATIONS, executors=EXECUTORS)
    )
    assert len(outcomes) == 25
    assert set(outcomes.values()) == {Outcome.PASSED}
