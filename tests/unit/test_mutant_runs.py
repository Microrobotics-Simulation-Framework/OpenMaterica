# SPDX-License-Identifier: Apache-2.0
"""The mutant table's script never gives a broken mutant as killed, refuses a request it cannot run as asked,
and reads a record only as its job writes one. tests/unit/test_ci_workflows.py runs the workflow's steps with
it, the patches' refusals among them."""

import itertools
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts import mutant_runs
from scripts.mutant_runs import BROKEN, KILLED, SURVIVED, UNDECIDED, Request, RequestError
from tests.unit.throwaway_git import throwaway_repository

FAILED = [{"test": "tests/test_x.py::test_y", "message": "assert 1 == 2"}]
STAGES = ("applied", "imports", "collected")


def every_record() -> list[dict[str, Any]]:
    """A record of each combination of facts a job can write, and some it cannot: each stage passed, failed or
    not reached, refused or not, each exit status pytest or `timeout` gives and one never given, and no
    failure, a named one, or one that is not a failure's shape."""
    records: list[dict[str, Any]] = []
    for applied, imports, collected, refused, status, failures in itertools.product(
        (True, False, None),
        (True, False, None),
        (True, False, None),
        ([], ["a reason"]),
        (None, 0, 1, 2, 3, 4, 5, 124, 7),
        ([], FAILED, [{"name": "x"}]),
    ):
        records.append(
            {
                "mutant": "m",
                "refused": refused,
                "applied": applied,
                "imports": imports,
                "collected": collected,
                "tests": 3,
                "status": status,
                "failures": failures,
                "message": "why",
            }
        )
    return records


def verdict_problems(verdict: Callable[[Mapping[str, Any]], tuple[str, str]]) -> list[str]:
    """Each record of `every_record` to which `verdict` gives another outcome than its facts allow: killed
    only where nothing was refused, every stage passed, and pytest failed (1, or 2 where `-x` stopped it under
    pytest-xdist) at a named test, which it gives; broken wherever, nothing refused, a stage failed; survived
    only where every stage passed and pytest passed naming no failure; undecided otherwise."""
    problems: list[str] = []
    for record in every_record():
        found = verdict(record)
        stages = [record[stage] for stage in STAGES]
        failures = record["failures"]
        if record["refused"]:
            expected = UNDECIDED
        elif False in stages:
            expected = BROKEN
        elif stages != [True, True, True]:
            expected = UNDECIDED
        elif record["status"] == 0 and not failures:
            expected = SURVIVED
        elif record["status"] in (1, 2) and failures == FAILED:
            expected = KILLED
        else:
            expected = UNDECIDED
        if found[0] != expected or (expected == KILLED and found[1] != FAILED[0]["test"]):
            problems.append(f"{record} is {found}, not {expected}")
    return problems


def test_no_record_is_given_an_outcome_its_facts_do_not_allow() -> None:
    assert verdict_problems(mutant_runs.verdict) == []


def test_the_verdict_check_can_fail() -> None:
    """The control: a verdict that reads the failures before the stages gives a broken mutant as killed."""

    def failures_first(record: Mapping[str, Any]) -> tuple[str, str]:
        if record["failures"] == FAILED and record["status"] in (1, 2):
            return KILLED, FAILED[0]["test"]
        return mutant_runs.verdict(record)

    problems = verdict_problems(failures_first)
    assert any(
        "'applied': False" in line and "('killed'" in line and "not broken" in line for line in problems
    )


def test_a_rename_in_git_diffs_form_gives_both_its_paths() -> None:
    assert mutant_runs.numstat_paths("1\t1\tsrc/a.py\x00-\t-\tb.bin\x00") == (["src/a.py", "b.bin"], True)
    assert mutant_runs.numstat_paths("0\t0\t\x00src/a.py\x00src/b.py\x00") == (
        ["src/a.py", "src/b.py"],
        False,
    )
    assert mutant_runs.numstat_paths("") == ([], False)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A committed tree holding a test file and two patches in mutants/, one of them a plain edit."""
    root = throwaway_repository(tmp_path, monkeypatch)
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_y():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "t"], check=True)
    (root / "tests" / "test_x.py").write_text("def test_y():\n    assert False\n", encoding="utf-8")
    patch = subprocess.run(["git", "diff"], check=True, capture_output=True, text=True).stdout
    subprocess.run(["git", "checkout", "-q", "--", "tests"], check=True)
    (root / "mutants").mkdir()
    for name in ("b", "a"):
        (root / "mutants" / f"{name}.patch").write_text(patch, encoding="utf-8")
    (root / "mutants" / "README.md").write_text("notes\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "m"], check=True)
    return root


GOOD = {
    "MUTANTS": "a b",
    "SELECTION": "tests/test_x.py::test_y tests",
    "PROFILE": "ci",
    "PYTHON_VERSION": "3.12",
    "SEED": "0",
    "EXTRA": "--shard records  --property-controls=none",
}


def test_a_request_within_its_bounds_is_written_as_its_outputs(repository: Path) -> None:
    request = mutant_runs.checked_request(GOOD, repository)
    assert mutant_runs.outputs(request) == {
        "mutants": "a b",
        "matrix": json.dumps(["", "a", "b"]),
        "selection": "tests/test_x.py::test_y tests",
        "profile": "ci",
        "python": "3.12",
        "seed": "0",
        "extra": "--shard=records --property-controls=none",
    }


def test_no_mutant_named_runs_every_committed_patch_and_no_seed_one_drawn(repository: Path) -> None:
    drawn: list[int] = []

    def draw(below: int) -> int:
        drawn.append(below)
        return 123

    request = mutant_runs.checked_request(GOOD | {"MUTANTS": "", "SEED": ""}, repository, draw)
    assert (request.mutants, request.seed, drawn) == (("a", "b"), 123, [mutant_runs.MAX_SEED + 1])


@pytest.mark.parametrize(
    ("name", "value", "problem"),
    [
        ("MUTANTS", "a a", "the mutant a is named twice"),
        ("MUTANTS", "a\tb", "MUTANTS 'a\\tb' holds a character other than printable ASCII"),
        ("MUTANTS", " ".join(f"m{index}" for index in range(201)), "201 mutants, more than 200"),
        ("SELECTION", "", "the selection is empty"),
        ("SELECTION", "src", "the selection's path 'src' is not `tests` or a path under it"),
        ("SELECTION", "tests/../src", "is not `tests` or a path under it"),
        ("SELECTION", "tests/test_missing.py", "is no file or directory under tests/"),
        ("SELECTION", "tests::", "names nothing after `::`"),
        ("SELECTION", " ".join(["tests"] * 21), "names 21 paths or nodes, more than 20"),
        ("PROFILE", "default", "the profile 'default' is not one of dev, ci, deep"),
        ("PYTHON_VERSION", "3.10", "the Python '3.10' is not one of"),
        ("SEED", "-1", "the seed '-1' is not a whole number"),
        ("SEED", "1000000000", "the seed 1000000000 is not from 0 to 999999999"),
        ("SEED", "010", "the seed '010' is not a whole number"),
        ("EXTRA", "--hypothesis-seed=5", "is not one of --shard, --property-controls"),
        ("EXTRA", "--shard a --shard b", "the extra argument --shard is given twice"),
    ],
)
def test_a_request_out_of_its_bounds_is_refused_with_every_reason(
    repository: Path, name: str, value: str, problem: str
) -> None:
    with pytest.raises(RequestError) as refused:
        mutant_runs.checked_request(GOOD | {name: value}, repository)
    assert any(problem in line for line in refused.value.problems), refused.value.problems


def test_no_patch_committed_and_none_named_is_refused(repository: Path) -> None:
    subprocess.run(["git", "rm", "-q", "mutants/a.patch", "mutants/b.patch"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "none"], check=True)
    with pytest.raises(RequestError, match="no mutant is named, and no patch is committed in mutants/"):
        mutant_runs.checked_request(GOOD | {"MUTANTS": ""}, repository)


def record(mutant: str, **facts: object) -> dict[str, object]:
    found: dict[str, object] = {
        "mutant": mutant,
        "refused": [],
        "applied": True,
        "imports": True,
        "collected": True,
        "tests": 3,
        "status": 0,
        "failures": [],
        "message": "",
    }
    return found | facts


def kept(directory: Path, *records: object) -> Path:
    for index, each in enumerate(records):
        where = directory / "records" / f"record-{index}"
        where.mkdir(parents=True)
        (where / mutant_runs.RECORD).write_text(json.dumps(each), encoding="utf-8")
    return directory / "records"


REQUEST = Request(("a", "b"), ("tests",), "dev", "3.15", 7, ())


def test_a_table_passes_where_the_baseline_passed_and_every_mutant_was_killed(tmp_path: Path) -> None:
    records = kept(
        tmp_path, record(""), record("a", status=2, failures=FAILED), record("b", status=1, failures=FAILED)
    )
    text, rows, verdict, ok = mutant_runs.table(REQUEST, records, "success", 1, "f" * 40)
    assert ok, verdict
    assert [row.outcome for row in rows] == [SURVIVED, KILLED, KILLED]
    assert "2 of 2 mutants killed, 0 survived, 0 broken, 0 undecided" == verdict
    assert "| <code>a</code> | killed | <code>tests/test_x.py::test_y</code> |" in text
    assert "seed 7" in text
    assert "<code>ffffffffffff</code>" in text


@pytest.mark.parametrize(
    ("records", "result", "attempt", "problem"),
    [
        ([record(""), record("a", status=2, failures=FAILED)], "success", 1, "1 undecided"),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in ("a", "b", "b")]],
            "success",
            1,
            "1 undecided",
        ),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in ("a", "b", "c")]],
            "success",
            1,
            "problems with the records: 1",
        ),
        ([record(""), *[record(name, status=2, failures=FAILED) for name in "ab"]], "failure", 1, "ended in"),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in "ab"]],
            "success",
            2,
            "attempt 2",
        ),
        (
            [
                record("", status=2, failures=FAILED),
                *[record(name, status=2, failures=FAILED) for name in "ab"],
            ],
            "success",
            1,
            "0 of 2 mutants killed, 0 survived, 0 broken, 2 undecided; the baseline did not pass",
        ),
        (
            [record(""), record("a", status=True), record("b", status=2, failures=FAILED)],
            "success",
            1,
            "problems",
        ),
        ([record(""), record("a", failures=[{"test": 1}]), record("b")], "success", 1, "problems"),
        ([record(""), {"mutant": "a"}, record("b")], "success", 1, "problems"),
        ([record(""), record("a", outcome="killed"), record("b")], "success", 1, "problems"),
    ],
    ids=[
        "a-record-missing",
        "two-records",
        "a-record-of-another",
        "a-job-failed",
        "a-second-attempt",
        "the-baseline-failed",
        "a-bool-for-a-status",
        "a-failure-of-another-shape",
        "fields-missing",
        "an-outcome-written-in",
    ],
)
def test_a_table_fails_unless_every_record_is_there_once_and_every_mutant_killed(
    tmp_path: Path, records: list[object], result: str, attempt: int, problem: str
) -> None:
    text, _, verdict, ok = mutant_runs.table(REQUEST, kept(tmp_path, *records), result, attempt)
    assert not ok
    assert problem in verdict, verdict
    assert verdict in text


def test_a_table_escapes_what_a_record_says() -> None:
    assert mutant_runs.cell("a | <b>") == "a &#124; &lt;b&gt;"
    assert mutant_runs.code("x|y") == "<code>x&#124;y</code>"


def test_each_failed_test_is_read_from_the_report_in_its_order(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_x" name="test_ok" file="tests/test_x.py"/>'
        '<testcase classname="tests.test_x.TestC" name="test_b" file="tests/test_x.py">'
        '<failure message="first line&#10;second">t</failure></testcase>'
        '<testcase classname="tests.test_x" name="test_a" file="tests/test_x.py"><error message="e">t</error>'
        "</testcase><testcase time='1.0'/></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert mutant_runs.reported_failures(report) == [
        {"test": "tests/test_x.py::TestC::test_b", "message": "first line"},
        {"test": "tests/test_x.py::test_a", "message": "e"},
    ]
    assert mutant_runs.reported_failures(tmp_path / "missing.xml") == []


def imported_in_a_fresh_process(root: Path, *paths: str) -> list[str]:
    """`import_problems` run as the job runs it: in a fresh Python, the checkout's `src/` on its path."""
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1] + '/src'); "
        f"sys.path.insert(0, {str(Path(mutant_runs.__file__).parent)!r}); import mutant_runs; "
        "print('\\n'.join(mutant_runs.import_problems(Path(sys.argv[1]), sys.argv[2:])))"
    )
    ran = subprocess.run(
        [sys.executable, "-I", "-c", script, str(root), *paths], capture_output=True, text=True, check=True
    )
    return [line for line in ran.stdout.splitlines() if line]


def test_a_module_that_does_not_compile_or_import_is_found(tmp_path: Path) -> None:
    package = tmp_path / "src" / "materica"
    (package / "core").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core" / "__init__.py").write_text("", encoding="utf-8")
    (package / "core" / "good.py").write_text("X = 1\n", encoding="utf-8")
    assert imported_in_a_fresh_process(tmp_path) == []
    (package / "core" / "bad.py").write_text("raise RuntimeError('at import')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_z.py").write_text("def f(:\n", encoding="utf-8")
    problems = imported_in_a_fresh_process(tmp_path, "tests/test_z.py", "tests/gone.py", "notes.md")
    assert len(problems) == 2, problems
    assert problems[0].startswith("tests/test_z.py does not compile: "), problems
    assert problems[1] == "materica.core.bad does not import: RuntimeError: at import", problems


def test_a_package_imported_from_elsewhere_is_found(tmp_path: Path) -> None:
    """The control of the walk above: a module of the checkout's that another copy of the package gives."""
    elsewhere = tmp_path / "elsewhere" / "src" / "materica"
    elsewhere.mkdir(parents=True)
    (elsewhere / "__init__.py").write_text("", encoding="utf-8")
    checkout = tmp_path / "checkout" / "src" / "materica"
    checkout.mkdir(parents=True)
    (checkout / "__init__.py").write_text("", encoding="utf-8")
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[2] + '/src'); "
        f"sys.path.insert(0, {str(Path(mutant_runs.__file__).parent)!r}); import mutant_runs; "
        "print('\\n'.join(mutant_runs.import_problems(Path(sys.argv[1]), [])))"
    )
    ran = subprocess.run(
        [sys.executable, "-I", "-c", script, str(checkout.parents[1]), str(elsewhere.parents[1])],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "materica is imported from" in ran.stdout
    assert "not from the checkout" in ran.stdout
