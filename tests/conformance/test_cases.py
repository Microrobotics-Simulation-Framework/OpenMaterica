# SPDX-License-Identifier: Apache-2.0
"""Every conformance case file: those this implementation runs must pass, and the rest are counted.

A case file that is not run is never a pytest item, so it cannot read as a pass or a skip; the counts below
and the terminal summary (`conftest.py`) account for it.
"""

from collections import Counter

import pytest

from tests.conformance import runner
from tests.conformance.runner import CLAIMED, EXECUTORS, CaseFile, Outcome

CASE_FILES = runner.discover()
RUN = [
    case_file
    for case_file in CASE_FILES
    if runner.not_run_because(case_file, claimed=CLAIMED, executors=EXECUTORS) is None
]


@pytest.mark.parametrize("case_file", RUN, ids=[case_file.path.name for case_file in RUN])
def test_case_file(case_file: CaseFile) -> None:
    case_run = runner.run(case_file, claimed=CLAIMED, executors=EXECUTORS)
    assert case_run.outcome is Outcome.PASSED, "\n".join(case_run.differences)


def test_every_case_file_is_counted() -> None:
    runs = runner.run_all(CASE_FILES, claimed=CLAIMED, executors=EXECUTORS)
    assert len(runs) == 416
    assert Counter(case_run.outcome for case_run in runs) == {
        Outcome.PASSED: 51,
        Outcome.NOT_YET_RUNNABLE: 365,
    }
    not_run = Counter(
        case_run.case_file.operation for case_run in runs if case_run.outcome is not Outcome.PASSED
    )
    assert not_run == {"read": 340, "list_records": 25}


def test_a_case_passes_only_where_a_variant_ran() -> None:
    outcomes = runner.case_outcomes(runner.run_all(CASE_FILES, claimed=CLAIMED, executors=EXECUTORS))
    passed = {case for case, outcome in outcomes.items() if outcome is Outcome.PASSED}
    assert passed == {"HS-001", "HS-002", "HS-003"}
    assert {outcomes[case] for case in outcomes.keys() - passed} == {Outcome.NOT_YET_RUNNABLE}
