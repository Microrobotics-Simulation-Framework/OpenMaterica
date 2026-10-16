# SPDX-License-Identifier: Apache-2.0
"""`case_steps.json` maps every case file, variants included, to the implementation step whose code first runs
it, and every case file of a step done passes.

The map is how a step is known to be done: its cases run and pass, under the claims each states. A step is one
of the code design's S1 to S13, with S2 in its pieces, S2a-1 to S2a-4, then S2b-1 and S2b-2 in either order,
S3 in its pieces, S3-te, S3a, S3b-1, S3b-2 and S3c, in that order, and S4 in its pieces, S4a, built ahead of
S3's code (maintainer, 2026-10-19), then S4b and S4c. A case file that needs pieces whose order is not fixed
names them all, as a list, and runs once all are done; until its steps are done, the runner reports it as not
yet runnable (`tests/conformance/runner.py`).
"""

import json
from pathlib import Path

from tests.conformance import runner
from tests.conformance.runner import CONFIGURATIONS, EXECUTORS

STEPS = json.loads((Path(__file__).parent / "case_steps.json").read_text(encoding="utf-8"))
CASE_FILES = runner.discover()
PIECES = (
    "S2a-1",
    "S2a-2",
    "S2a-3",
    "S2a-4",
    "S2b-1",
    "S2b-2",
    "S3-te",
    "S3a",
    "S3b-1",
    "S3b-2",
    "S3c",
    "S4a",
    "S4b",
    "S4c",
)
KNOWN = {"S1", *PIECES} | {f"S{number}" for number in range(3, 14)}


def test_every_case_file_has_its_steps() -> None:
    assert sorted(STEPS["case_files"]) == sorted(case_file.path.name for case_file in CASE_FILES)
    for name, entry in STEPS["case_files"].items():
        if isinstance(entry, str):
            assert entry in KNOWN, name
        else:
            assert len(set(entry)) == len(entry) >= 2, name
            assert set(entry) <= KNOWN, name
    assert set(STEPS["done"]) <= KNOWN


def test_every_case_file_of_a_step_done_passes() -> None:
    """Passes, or, for a table evaluation case, which the reference evaluator runs, is verified against it."""
    done = [case_file for case_file in CASE_FILES if runner.step_done(case_file)]
    runs = runner.run_all(done, configurations=CONFIGURATIONS, executors=EXECUTORS)
    assert {case_run.case_file.path.name: case_run.outcome for case_run in runs} == {
        case_file.path.name: runner.passing_outcome(case_file) for case_file in done
    }
