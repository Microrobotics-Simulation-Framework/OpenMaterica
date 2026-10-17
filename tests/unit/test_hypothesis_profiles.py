# SPDX-License-Identifier: Apache-2.0
"""A runner's environment changes no setting of the Hypothesis profiles, a seed decides what a property
draws, and the profiles keep the settings the maintainer fixed.

Hypothesis loads its built-in `ci` profile at import wherever `CI` is set, as it is on GitHub's runners, and a
profile registered without a parent inherits the one loaded. Until the profiles took Hypothesis's defaults as
their parent, every CI run inherited `derandomize=True`, which Hypothesis applies before `--hypothesis-seed`,
and drew one fixed set of examples. Each check runs the text of `tests/conftest.py` in fresh processes, with
and without the variables a runner sets: imported as a module, for every profile it registers, and as
pytest's plugin, for the settings a property runs under once pytest's hooks have run. The controls run the
same checks on faulty copies: the registration as it was, `derandomize` put back, each pinned setting
changed, and a setting changed in a hook on a runner alone.
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

# The example counts the maintainer fixed: rigour is fixed, and a change to any needs the maintainer. Every
# profile also has no deadline and suppresses the `too_slow` health check alone, since neither the timing nor
# a slow draw on a loaded runner is a fault of the code; prints the blob that replays a failure without the
# database; keeps its examples in the repository's `.hypothesis/examples` whatever the working directory; and
# runs every phase (review of #38, L1, L4 and Q3).
FIXED_EXAMPLES = {"dev": 200, "ci": 2_000, "deep": 20_000}

# What the checks read of a `settings`, in the processes they run.
FACTS = """
from hypothesis import Phase


def facts(setting):
    return {
        "max_examples": setting.max_examples,
        "derandomize": setting.derandomize,
        "deadline": repr(setting.deadline),
        "suppressed": sorted(check.name for check in setting.suppress_health_check),
        "print_blob": setting.print_blob,
        "missing_phases": sorted(phase.name for phase in Phase if phase not in setting.phases),
        "database": str(getattr(setting.database, "path", repr(setting.database))),
    }
"""

SHOW_SETTINGS = (
    FACTS
    + f"""
import json
from hypothesis import settings

before = settings.get_current_profile_name()
import {COPY}

print(json.dumps({{
    "loaded_by_hypothesis": before,
    "loaded": settings.get_current_profile_name(),
    "settings": repr(settings.default),
    "profiles": {{name: repr(settings.get_profile(name)) for name in {COPY}.EXAMPLES}},
    "facts": {{name: facts(settings.get_profile(name)) for name in {COPY}.EXAMPLES}},
}}))
"""
)

# A property that writes down the settings it runs under, after every hook of pytest's and of the copy's.
IN_EFFECT = (
    FACTS
    + """
import json
import os

from hypothesis import given, settings, strategies


@given(strategies.none())
def test_settings_in_effect(_):
    with open(os.environ["SHOWN"], "w", encoding="utf-8") as shown:
        json.dump({"settings": repr(settings.default), "facts": facts(settings.default)}, shown)
"""
)

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


class Facts(TypedDict):
    max_examples: int
    derandomize: bool
    deadline: str
    suppressed: list[str]
    print_blob: bool
    missing_phases: list[str]
    database: str


class Shown(TypedDict):
    loaded_by_hypothesis: str
    loaded: str
    settings: str
    profiles: dict[str, str]
    facts: dict[str, Facts]


class InEffect(TypedDict):
    settings: str
    facts: Facts


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


def database_of_the_copy(tmp_path: Path) -> str:
    """The repository's example database as the copy sees it: the copy stands one level below its root, as
    `tests/conftest.py` does."""
    return str(tmp_path.resolve().parent / ".hypothesis" / "examples")


def unfixed(name: str, facts: Facts, database: str) -> list[str]:
    """Each setting of profile `name` that differs from the one fixed, but `derandomize`."""
    problems: list[str] = []
    if facts["max_examples"] != FIXED_EXAMPLES.get(name):
        problems.append(
            f"draws {facts['max_examples']} examples, not the {FIXED_EXAMPLES.get(name)} the maintainer fixed"
        )
    if facts["deadline"] != "None":
        problems.append(f"has a deadline, {facts['deadline']}")
    if "too_slow" not in facts["suppressed"]:
        problems.append("runs the `too_slow` health check")
    if others := [check for check in facts["suppressed"] if check != "too_slow"]:
        problems.append(f"suppresses {others} besides `too_slow`")
    if not facts["print_blob"]:
        problems.append("prints no blob")
    if facts["missing_phases"]:
        problems.append(f"leaves out the phases {facts['missing_phases']}")
    if facts["database"] != database:
        problems.append(f"keeps its examples in {facts['database']}, not {database}")
    return problems


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
    """Each setting a runner's environment changes, with `profile` loaded, each profile derandomized, and
    each setting of a profile not the one fixed."""
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
    if sorted(bare["facts"]) != sorted(FIXED_EXAMPLES):
        problems.append(
            f"the profiles are {sorted(bare['facts'])}, not the maintainer's {sorted(FIXED_EXAMPLES)}"
        )
    database = database_of_the_copy(tmp_path)
    for where, settings in (("off a runner", bare), ("on a runner", on_a_runner)):
        for name, facts in settings["facts"].items():
            if facts["derandomize"]:
                problems.append(f"profile `{name}` is derandomized {where}")
            problems.extend(
                f"profile `{name}` {problem} ({where})" for problem in unfixed(name, facts, database)
            )
    return problems


def in_effect(tmp_path: Path, *, runner: bool, profile: str) -> InEffect:
    """The settings the property runs under at `profile`, the copy loaded as pytest's plugin."""
    written = tmp_path / f"in-effect-{'runner' if runner else 'bare'}.json"
    ran = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", COPY, "-q", "test_in_effect.py"],
        cwd=tmp_path,
        env=environment(tmp_path, runner=runner, profile=profile) | {"SHOWN": str(written)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    settings: InEffect = json.loads(written.read_text(encoding="utf-8"))
    return settings


def hook_problems(tmp_path: Path, conftest: str, profile: str) -> list[str]:
    """Each setting a property runs under, at `profile`, that a runner's environment changes or that is not
    the one fixed. The settings check imports the conftest and runs none of pytest's hooks, where a setting
    can change too (review of #38, I6, mutant 22); this check runs them. Its arms are the settings check's,
    whose processes show that Hypothesis loads its `ci` profile in one and not the other."""
    copied(tmp_path, conftest)
    (tmp_path / "test_in_effect.py").write_text(IN_EFFECT, encoding="utf-8")
    bare = in_effect(tmp_path, runner=False, profile=profile)
    on_a_runner = in_effect(tmp_path, runner=True, profile=profile)
    problems: list[str] = []
    if on_a_runner["settings"] != bare["settings"]:
        problems.append(
            f"a property at `{profile}` runs under {on_a_runner['settings']} on a runner, "
            f"{bare['settings']} off it"
        )
    database = database_of_the_copy(tmp_path)
    for where, settings in (("off a runner", bare), ("on a runner", on_a_runner)):
        if settings["facts"]["derandomize"]:
            problems.append(f"a property at `{profile}` is derandomized {where}")
        problems.extend(
            f"a property at `{profile}` {problem} ({where})"
            for problem in unfixed(profile, settings["facts"], database)
        )
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
def test_a_runner_changes_no_setting_and_each_profile_keeps_those_fixed(tmp_path: Path, profile: str) -> None:
    problems = settings_problems(tmp_path, conftest_text(), profile)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("profile", EXAMPLES)
def test_after_pytest_s_hooks_a_property_runs_under_the_same_settings_on_a_runner(
    tmp_path: Path, profile: str
) -> None:
    problems = hook_problems(tmp_path, conftest_text(), profile)
    assert not problems, "\n".join(problems)


def test_on_a_runner_the_seed_decides_what_a_property_draws(tmp_path: Path) -> None:
    problems = seed_problems(tmp_path, conftest_text())
    assert not problems, "\n".join(problems)


# The lines of `tests/conftest.py` the controls change, each found by its text.
PARENT = '        parent=settings.get_profile("default"),\n'
TOO_SLOW = "        suppress_health_check=[HealthCheck.too_slow],\n"
COUNTS = 'EXAMPLES = {"dev": 200, "ci": 2_000, "deep": 20_000}\n'
DEADLINE = "        deadline=None,\n"
BLOB = "        print_blob=True,\n"
DATABASE = "        database=DirectoryBasedExampleDatabase(HYPOTHESIS_DATABASE),\n"
IMPORTS = "from hypothesis import HealthCheck, settings\n"
LOADED = "settings.load_profile(PROFILE)\n"
# The review's mutant 22: a deadline on a runner alone, set in a hook after the conftest is imported.
DEADLINE_IN_A_HOOK = """

@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    if os.environ.get("CI"):
        settings.register_profile(PROFILE, settings(settings.get_profile(PROFILE), deadline=200))
        settings.load_profile(PROFILE)
"""


class Fault(NamedTuple):
    replacements: tuple[tuple[str, str], ...]
    # What each check must report, in part; a check given nothing is not run on the fault.
    settings: tuple[str, ...] = ()
    seeds: tuple[str, ...] = ()
    hooks: tuple[str, ...] = ()


FAULTS = {
    # The registration from 2026-10-14 until #38: no parent, and `too_slow` from Hypothesis's profile.
    "no-parent": Fault(
        ((PARENT, ""), (TOO_SLOW, "")),
        settings=(
            "loaded `ci`:",
            "profile `dev` differs on a runner",
            "profile `deep` is derandomized on a runner",
            "profile `dev` runs the `too_slow` health check (off a runner)",
        ),
        seeds=("seeds 1 and 2 drew the same", "seed 1 drew other examples on a runner than off it"),
    ),
    "derandomize-put-back": Fault(
        # As a parent: `derandomize=True` beside the database would be refused.
        ((PARENT, '        parent=settings(settings.get_profile("default"), derandomize=True),\n'),),
        settings=("profile `dev` is derandomized off a runner", "profile `deep` is derandomized on a runner"),
        seeds=("seeds 1 and 2 drew the same",),
    ),
    "too-slow-dropped": Fault(
        ((TOO_SLOW, ""),),
        settings=(
            "profile `dev` runs the `too_slow` health check (off a runner)",
            "profile `deep` runs the `too_slow` health check (on a runner)",
        ),
    ),
    "every-health-check-suppressed": Fault(
        ((TOO_SLOW, "        suppress_health_check=list(HealthCheck),\n"),),
        settings=("profile `ci` suppresses ['data_too_large',",),
    ),
    "examples-halved": Fault(
        ((COUNTS, 'EXAMPLES = {"dev": 100, "ci": 1_000, "deep": 20_000}\n'),),
        settings=(
            "profile `dev` draws 100 examples, not the 200 the maintainer fixed",
            "profile `ci` draws 1000 examples, not the 2000 the maintainer fixed",
        ),
    ),
    "deadline-set": Fault(
        ((DEADLINE, "        deadline=200,\n"),),
        settings=("profile `dev` has a deadline, timedelta(milliseconds=200) (off a runner)",),
    ),
    "no-blob": Fault(((BLOB, ""),), settings=("profile `deep` prints no blob (on a runner)",)),
    "database-left-to-hypothesis": Fault(
        ((DATABASE, ""),),
        settings=("profile `ci` keeps its examples in",),
    ),
    "no-shrink": Fault(
        (
            (IMPORTS, "from hypothesis import HealthCheck, Phase, settings\n"),
            (
                TOO_SLOW,
                TOO_SLOW + "        phases=[phase for phase in Phase if phase is not Phase.shrink],\n",
            ),
        ),
        settings=("profile `dev` leaves out the phases ['shrink'] (off a runner)",),
    ),
    "deadline-in-a-hook-on-a-runner": Fault(
        ((LOADED, LOADED + DEADLINE_IN_A_HOOK),),
        hooks=(
            "a property at `ci` runs under",
            "a property at `ci` has a deadline, timedelta(milliseconds=200) (on a runner)",
        ),
    ),
}


def faulty(fault: str, conftest: str | None = None) -> str:
    """The conftest's text, or `conftest`, with `fault`'s replacements made."""
    text = conftest_text() if conftest is None else conftest
    for old, new in FAULTS[fault].replacements:
        assert text.count(old) == 1, (
            f"the control {fault!r} no longer applies to tests/conftest.py: {old!r} is not in it once; "
            "update FAULTS with the conftest"
        )
        text = text.replace(old, new)
    return text


def reported(expected: tuple[str, ...], found: list[str]) -> bool:
    return all(any(part in problem for problem in found) for part in expected)


def faults_of(check: str) -> list[str]:
    return [name for name, fault in FAULTS.items() if getattr(fault, check)]


@pytest.mark.parametrize("fault", faults_of("settings"))
def test_the_settings_check_can_fail(tmp_path: Path, fault: str) -> None:
    """The control: the registration as it was, `derandomize` put back, or a pinned setting changed."""
    found = settings_problems(tmp_path, faulty(fault), "ci")
    assert reported(FAULTS[fault].settings, found), found


@pytest.mark.parametrize("fault", faults_of("seeds"))
def test_the_seed_check_can_fail(tmp_path: Path, fault: str) -> None:
    """The control: on a runner, the registration as it was, or with `derandomize` put back, draws alike under
    every seed."""
    found = seed_problems(tmp_path, faulty(fault))
    assert reported(FAULTS[fault].seeds, found), found


@pytest.mark.parametrize("fault", faults_of("hooks"))
def test_the_hook_check_can_fail(tmp_path: Path, fault: str) -> None:
    """The control: a deadline set on a runner alone, in a hook, which the settings check cannot see."""
    assert settings_problems(tmp_path, faulty(fault), "ci") == []
    found = hook_problems(tmp_path, faulty(fault), "ci")
    assert reported(FAULTS[fault].hooks, found), found


def test_a_control_whose_line_is_gone_says_so() -> None:
    """A rewrite of the conftest that leaves a control nothing to replace fails it with what to do, not a bare
    `assert 0 == 1` (review of #38, L2)."""
    assert faulty("no-parent") != conftest_text()
    reflowed = conftest_text().replace(
        PARENT, '        parent=settings.get_profile(\n            "default"),\n'
    )
    with pytest.raises(
        AssertionError, match=r"the control 'no-parent' no longer applies to tests/conftest\.py: "
    ):
        faulty("no-parent", reflowed)
    with pytest.raises(AssertionError, match="update FAULTS with the conftest"):
        faulty("no-parent", reflowed)
