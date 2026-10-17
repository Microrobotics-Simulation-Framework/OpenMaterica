# SPDX-License-Identifier: Apache-2.0
"""An audit that fails a run Hypothesis drew at random names the seed that draws the run again.

An audit fails after Hypothesis's run has passed, so Hypothesis itself prints no seed and stores no example
(review of #38, M1). Here the audits' hook (`tests/property/conftest.py`) runs as pytest's plugin, in fresh
processes with a runner's variables and the `dev` profile, as on CI's test matrix, on a property whose feature
audit always fails and which writes down what it draws.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tests.conftest import EXAMPLES
from tests.property import audits

REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = {"CI": "true", "GITHUB_ACTIONS": "true"}

FAILING_AUDIT = """
import json
import os

import pytest
from hypothesis import given, seed, settings, strategies

from tests.property.support import feature


@pytest.mark.features(shown=0.9)
@settings(database=None)
@given(strategies.integers(), strategies.text(max_size=8))
def test_never_shows_its_feature(number, text):
    with open(os.environ["DRAWS"], "a", encoding="utf-8") as drawn:
        drawn.write(json.dumps([number, text]) + "\\n")
    feature("shown", False)


if "AT_SEED" in os.environ:
    test_never_shows_its_feature = seed(int(os.environ["AT_SEED"]))(test_never_shows_its_feature)
"""

# A module outside `tests/`, whose constants Hypothesis adds to those it draws from once it is loaded.
MORE_CONSTANTS = """
VALUES = [918273645, -55512, 77777, 31337, 424242, "zebra", "quokka", "lorem", 2.718281828]
"""


def audited(tmp_path: Path, run: str, *arguments: str, at_seed: str | None = None) -> tuple[str, list[str]]:
    """The report and the draws of a run of the failing audit."""
    draws = tmp_path / f"draws-{run}.jsonl"
    kept = {
        name: value
        for name, value in os.environ.items()
        if name not in RUNNER and not name.startswith(("PYTEST_", "MATERICA_", "HYPOTHESIS_"))
    }
    ran = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.property.conftest",
            "-q",
            "--tb=line",
            *arguments,
            "test_failing_audit.py",
        ],
        cwd=tmp_path,
        env={
            **kept,
            **RUNNER,
            "MATERICA_HYPOTHESIS_PROFILE": "dev",
            "PYTHONPATH": os.pathsep.join([str(tmp_path), str(REPOSITORY)]),
            "DRAWS": str(draws),
            **({} if at_seed is None else {"AT_SEED": at_seed}),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    report = ran.stdout + ran.stderr
    assert ran.returncode == 1, report
    assert f"feature audit: feature 'shown' in 0.0% of {EXAMPLES['dev']} examples" in report, report
    examples = [json.dumps(json.loads(line)) for line in draws.read_text(encoding="utf-8").splitlines()]
    assert len(examples) == EXAMPLES["dev"], len(examples)
    return report, examples


def test_a_failing_audit_names_the_seed_that_draws_its_run_again(tmp_path: Path) -> None:
    (tmp_path / "test_failing_audit.py").write_text(FAILING_AUDIT, encoding="utf-8")
    report, first = audited(tmp_path, "first")
    seeds = set(re.findall(r"@seed\((\d+)\)", report))
    assert len(seeds) == 1, (
        f"the audit's failure names no seed, or several: has Hypothesis moved `{audits.GENERATED_SEED}`?\n"
        + report
    )
    (seed,) = seeds
    for named in (
        "MATERICA_HYPOTHESIS_PROFILE=dev",
        f"-k test_never_shows_its_feature --hypothesis-seed={seed}",
        "a run that collects less",
    ):
        assert named in report, (named, report)

    forced_report, forced = audited(
        tmp_path, "forced", "-k", "test_never_shows_its_feature", f"--hypothesis-seed={seed}"
    )
    assert forced == first
    _, at_seed = audited(tmp_path, "at-seed", at_seed=seed)
    assert at_seed == first
    # A run Hypothesis did not draw at random claims no seed of its own.
    assert "@seed(" not in forced_report, forced_report

    # The controls. An unseeded run draws other examples, so the replays' sameness is the seed's doing; and
    # under the seed, a run that loads one more module outside `tests/` draws other examples too, which is why
    # the message asks for the same command.
    _, other = audited(tmp_path, "other")
    assert other != first
    (tmp_path / "more_constants.py").write_text(MORE_CONSTANTS, encoding="utf-8")
    _, with_more = audited(tmp_path, "more", "-p", "more_constants", f"--hypothesis-seed={seed}")
    assert with_more != first
