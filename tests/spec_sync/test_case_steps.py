# SPDX-License-Identifier: Apache-2.0
"""`case_steps.json` maps every case file, variants included, to the implementation step whose code first runs
it, and every case file of a step done passes.

The map is how a step is known to be done: its cases run and pass, under the claims each states.
"""

import json
from pathlib import Path

from tests.conformance import runner
from tests.conformance.runner import CONFIGURATIONS, EXECUTORS, Outcome

STEPS = json.loads((Path(__file__).parent / "case_steps.json").read_text(encoding="utf-8"))
CASE_FILES = runner.discover()


def test_every_case_file_has_one_step() -> None:
    assert sorted(STEPS["case_files"]) == sorted(case_file.path.name for case_file in CASE_FILES)
    assert set(STEPS["case_files"].values()) <= {f"S{number}" for number in range(1, 14)}


def test_every_case_file_of_a_step_done_passes() -> None:
    done = [
        case_file for case_file in CASE_FILES if STEPS["case_files"][case_file.path.name] in STEPS["done"]
    ]
    runs = runner.run_all(done, configurations=CONFIGURATIONS, executors=EXECUTORS)
    assert {case_run.case_file.path.name: case_run.outcome for case_run in runs} == {
        case_file.path.name: Outcome.PASSED for case_file in done
    }
