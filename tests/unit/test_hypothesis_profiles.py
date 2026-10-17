# SPDX-License-Identifier: Apache-2.0
"""A runner's environment changes no setting of the Hypothesis profiles, and a seed decides what a property
draws.

Hypothesis loads its built-in `ci` profile at import wherever `CI` is set, as it is on GitHub's runners, and a
profile registered without a parent inherits the one loaded. Until the profiles took Hypothesis's defaults as
their parent, every CI run inherited `derandomize=True`, which Hypothesis applies before `--hypothesis-seed`,
and drew one fixed set of examples. Each check runs the text of `tests/conftest.py` in fresh processes, with
and without the variables a runner sets; the controls run the same checks on the registration as it was and
with `derandomize` put back.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, TypedDict

import pytest

from tests.conftest import EXAMPLES

REPOSITORY = Path(__file__).resolve().parents[2]
CONFTEST = REPOSITORY / "tests" / "conftest.py"
# What a GitHub runner sets; Hypothesis takes either for a CI.
RUNNER = {"CI": "true", "GITHUB_ACTIONS": "true"}
# The conftest's text is loaded from a copy of this name, so that the controls' faulty copies run alike.
COPY = "profiles"

SHOW_SETTINGS = f"""
import json
from hypothesis import settings

before = settings.get_current_profile_name()
import {COPY}

print(json.dumps({{
    "loaded_by_hypothesis": before,
    "loaded": settings.get_current_profile_name(),
    "settings": repr(settings.default),
    "profiles": {{name: repr(settings.get_profile(name)) for name in {COPY}.EXAMPLES}},
    "derandomized": [name for name in {COPY}.EXAMPLES if settings.get_profile(name).derandomize],
}}))
"""

# A property that writes down what it draws. It keeps no example database, so that no example an earlier run
# stored is replayed first.
DRAWING = """
import os

from hypothesis import given, settings, strategies


@settings(database=None)
@given(strategies.binary())
def test_draws(value):
    with open(os.environ["DRAWS"], "a", encoding="utf-8") as drawn:
        drawn.write(value.hex() + "\\n")
"""


class Shown(TypedDict):
    loaded_by_hypothesis: str
    loaded: str
    settings: str
    profiles: dict[str, str]
    derandomized: list[str]


def environment(tmp_path: Path, *, runner: bool, profile: str) -> dict[str, str]:
    """This process's environment without the variables a runner sets, pytest's or the repository's, with the
    profile chosen, the runner's variables if asked, and the conftest's copy importable."""
    kept = {
        name: value
        for name, value in os.environ.items()
        if name not in RUNNER and not name.startswith(("PYTEST_", "MATERICA_"))
    }
    return {
        **kept,
        **(RUNNER if runner else {}),
        "MATERICA_HYPOTHESIS_PROFILE": profile,
        "PYTHONPATH": os.pathsep.join([str(tmp_path), str(REPOSITORY)]),
    }


def copied(tmp_path: Path, conftest: str) -> Path:
    (tmp_path / f"{COPY}.py").write_text(conftest, encoding="utf-8")
    return tmp_path


def shown(tmp_path: Path, *, runner: bool, profile: str) -> Shown:
    ran = subprocess.run(
        [sys.executable, "-c", SHOW_SETTINGS],
        cwd=tmp_path,
        env=environment(tmp_path, runner=runner, profile=profile),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    settings: Shown = json.loads(ran.stdout)
    # The two processes differ as a runner and a laptop do, or the comparison shows nothing.
    assert settings["loaded_by_hypothesis"] == ("ci" if runner else "default"), settings
    assert settings["loaded"] == profile, settings
    return settings


def settings_problems(tmp_path: Path, conftest: str, profile: str) -> list[str]:
    """Each setting a runner's environment changes, with `profile` loaded, and each profile derandomized."""
    copied(tmp_path, conftest)
    bare = shown(tmp_path, runner=False, profile=profile)
    on_a_runner = shown(tmp_path, runner=True, profile=profile)
    problems: list[str] = []
    if on_a_runner["settings"] != bare["settings"]:
        problems.append(
            f"loaded `{profile}`: {on_a_runner['settings']} on a runner, {bare['settings']} off it"
        )
    for name, setting in bare["profiles"].items():
        if on_a_runner["profiles"][name] != setting:
            problems.append(f"profile `{name}` differs on a runner")
    for where, settings in (("off a runner", bare), ("on a runner", on_a_runner)):
        problems.extend(f"profile `{name}` is derandomized {where}" for name in settings["derandomized"])
    return problems


def drawn(tmp_path: Path, *, runner: bool, seed: int) -> list[str]:
    """What the property drew at the `dev` profile, under `seed`."""
    draws = tmp_path / f"draws-{'runner' if runner else 'bare'}-{seed}.txt"
    ran = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            COPY,
            "-q",
            "test_drawing.py",
            f"--hypothesis-seed={seed}",
        ],
        cwd=tmp_path,
        env=environment(tmp_path, runner=runner, profile="dev") | {"DRAWS": str(draws)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    examples = draws.read_text(encoding="utf-8").splitlines()
    assert len(examples) == EXAMPLES["dev"], len(examples)
    return examples


def seed_problems(tmp_path: Path, conftest: str) -> list[str]:
    """Whether, on a runner, two seeds draw alike, or a seed draws other examples than off a runner."""
    copied(tmp_path, conftest)
    (tmp_path / "test_drawing.py").write_text(DRAWING, encoding="utf-8")
    first = drawn(tmp_path, runner=True, seed=1)
    problems: list[str] = []
    if drawn(tmp_path, runner=True, seed=2) == first:
        problems.append(f"on a runner, seeds 1 and 2 drew the same {len(first)} examples")
    if drawn(tmp_path, runner=False, seed=1) != first:
        problems.append("seed 1 drew other examples on a runner than off it")
    return problems


def conftest_text() -> str:
    return CONFTEST.read_text(encoding="utf-8")


@pytest.mark.parametrize("profile", EXAMPLES)
def test_a_runner_changes_no_setting_and_no_profile_is_derandomized(tmp_path: Path, profile: str) -> None:
    assert settings_problems(tmp_path, conftest_text(), profile) == []


def test_on_a_runner_the_seed_decides_what_a_property_draws(tmp_path: Path) -> None:
    assert seed_problems(tmp_path, conftest_text()) == []


PARENT = '        parent=settings.get_profile("default"),\n'
TOO_SLOW = "        suppress_health_check=[HealthCheck.too_slow],\n"


class Fault(NamedTuple):
    replacements: tuple[tuple[str, str], ...]
    # What each check must report, in part.
    settings: tuple[str, ...]
    seeds: tuple[str, ...]


FAULTS = {
    # The registration from 2026-10-14 to 2026-10-17: no parent, and `too_slow` from Hypothesis's profile.
    "no-parent": Fault(
        ((PARENT, ""), (TOO_SLOW, "")),
        settings=(
            "loaded `ci`:",
            "profile `dev` differs on a runner",
            "profile `deep` is derandomized on a runner",
        ),
        seeds=("seeds 1 and 2 drew the same", "seed 1 drew other examples on a runner than off it"),
    ),
    "derandomize-put-back": Fault(
        # As a parent: `derandomize=True` beside the database would be refused.
        ((PARENT, '        parent=settings(settings.get_profile("default"), derandomize=True),\n'),),
        settings=("profile `dev` is derandomized off a runner", "profile `deep` is derandomized on a runner"),
        seeds=("seeds 1 and 2 drew the same",),
    ),
}


def faulty(fault: str) -> str:
    conftest = conftest_text()
    for old, new in FAULTS[fault].replacements:
        assert conftest.count(old) == 1
        conftest = conftest.replace(old, new)
    return conftest


def reported(expected: tuple[str, ...], found: list[str]) -> bool:
    return all(any(part in problem for problem in found) for part in expected)


@pytest.mark.parametrize("fault", FAULTS)
def test_the_settings_check_can_fail(tmp_path: Path, fault: str) -> None:
    """The control: the registration as it was, or with `derandomize` put back."""
    found = settings_problems(tmp_path, faulty(fault), "ci")
    assert reported(FAULTS[fault].settings, found), found


@pytest.mark.parametrize("fault", FAULTS)
def test_the_seed_check_can_fail(tmp_path: Path, fault: str) -> None:
    """The control: on a runner, the registration as it was, or with `derandomize` put back, draws alike under
    every seed."""
    found = seed_problems(tmp_path, faulty(fault))
    assert reported(FAULTS[fault].seeds, found), found
