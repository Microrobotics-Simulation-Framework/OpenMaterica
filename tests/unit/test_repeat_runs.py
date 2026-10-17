# SPDX-License-Identifier: Apache-2.0
"""The repeat run's script refuses a request it cannot run as asked, finds the failing examples Hypothesis
reports, and fails a summary where any run failed, did not finish or left no record."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import repeat_runs
from scripts.repeat_runs import Request, RequestError, Sum

# A failing example of each kind Hypothesis reports, and a test that fails without one.
FAILING_TESTS = """
from hypothesis import example, given, settings, strategies as st

ALONE = settings(database=None, print_blob=True, deadline=None)


@ALONE
@given(st.integers())
def test_one_bug(x):
    assert x < 1000


@ALONE
@given(st.integers())
@example(5000)
def test_an_explicit_example(x):
    assert x < 1000


@ALONE
@given(st.integers())
def test_two_bugs(x):
    if x > 1000:
        raise ValueError("above")
    if x < -1000:
        raise KeyError("below")


def test_without_hypothesis():
    raise RuntimeError("no example here")
"""
PASSING_TESTS = """
from hypothesis import given, strategies as st


@given(st.integers())
def test_passes(x):
    assert isinstance(x, int)
"""


def run_pytest(directory: Path, source: str) -> tuple[int, Path]:
    """`source` run by pytest under xdist and a seed, as the workflow runs a node, outside this repository's
    configuration but for its JUnit family: the exit status and the report."""
    (directory / "test_sample.py").write_text(source, encoding="utf-8")
    report = directory / "report.xml"
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    ran = subprocess.run(
        [
            *(sys.executable, "-m", "pytest", "test_sample.py"),
            *("-p", "no:cacheprovider", "-o", "junit_family=xunit1"),
            *("-n", "2", "--hypothesis-seed=3", f"--junitxml={report}"),
        ],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return ran.returncode, report


def failures_by_test(found: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {failure["test"].rpartition("::")[2]: failure for failure in found["failures"]}


def test_each_failing_example_hypothesis_reports_is_recorded(tmp_path: Path) -> None:
    status, report = run_pytest(tmp_path, FAILING_TESTS)
    found = repeat_runs.record(3, status, report)
    assert (found["seed"], found["status"], found["outcome"], found["tests"]) == (3, 1, "failed", 4)
    failures = failures_by_test(found)
    assert sorted(failures) == [
        "test_an_explicit_example",
        "test_one_bug",
        "test_two_bugs",
        "test_without_hypothesis",
    ]
    [one] = failures["test_one_bug"]["examples"]
    assert repeat_runs.EXAMPLE_HEAD.match(one), one
    assert "x=1000," in one, one
    assert one.splitlines()[-1].lstrip().startswith("You can reproduce"), one
    assert "@reproduce_failure(" in one, one
    [explicit] = failures["test_an_explicit_example"]["examples"]
    assert "explicit" in explicit, explicit
    assert "x=5000," in explicit, explicit
    two = failures["test_two_bugs"]["examples"]
    assert sorted("x=1001," in each for each in two) == [False, True], two
    assert sorted("x=-1001," in each for each in two) == [False, True], two
    assert all("@reproduce_failure(" in each and "+---" not in each for each in two), two
    plain = failures["test_without_hypothesis"]
    assert plain["examples"] == []
    assert "no example here" in plain["message"]


def test_a_passing_run_records_no_failure(tmp_path: Path) -> None:
    """The control: the failures above are the report's, not the reading's."""
    status, report = run_pytest(tmp_path, PASSING_TESTS)
    assert repeat_runs.record(5, status, report) == {
        "seed": 5,
        "status": 0,
        "outcome": "passed",
        "tests": 1,
        "failures": [],
    }


@pytest.mark.parametrize(
    ("status", "outcome"),
    [(1, "failed"), (2, "error"), (4, "error"), (5, "no test ran"), (124, "interrupted")],
)
def test_a_run_without_a_report_is_recorded_by_its_status(tmp_path: Path, status: int, outcome: str) -> None:
    assert repeat_runs.record(9, status, tmp_path / "none.xml") == {
        "seed": 9,
        "status": status,
        "outcome": outcome,
        "tests": None,
        "failures": [],
    }


def test_a_run_interrupted_after_a_failure_failed(tmp_path: Path) -> None:
    _, report = run_pytest(tmp_path, FAILING_TESTS)
    assert repeat_runs.record(3, 124, report)["outcome"] == "failed"


def test_an_example_ends_at_its_reproduce_line_or_where_its_prefix_does() -> None:
    text = "\n".join(
        [
            "E   assert 1000 < 1000",
            "E   Falsifying example: test_x(",
            "E       x=1000,",
            "E   )",
            "E   ",
            "E   You can reproduce this example by temporarily adding @reproduce_failure('6.1', b'AA') as a "
            "decorator",
            "E   after the example",
            "tests/test_x.py:3: AssertionError",
        ]
    )
    assert repeat_runs.failing_examples(text) == [
        "Falsifying example: test_x(\n    x=1000,\n)\n\n"
        "You can reproduce this example by temporarily adding @reproduce_failure('6.1', b'AA') as a decorator"
    ]
    assert repeat_runs.failing_examples(text.replace("@reproduce_failure", "reproduce")) == [
        "Falsifying example: test_x(\n    x=1000,\n)\n\n"
        "You can reproduce this example by temporarily adding reproduce('6.1', b'AA') as a decorator\n"
        "after the example"
    ]
    assert repeat_runs.failing_examples("E   assert False\ntests/test_x.py:3: AssertionError") == []


# A tree holding a test file, a directory of tests, and a link under tests/ to a file outside it.
@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "tests" / "property").mkdir(parents=True)
    (tmp_path / "tests" / "property" / "test_sample.py").write_text("", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "outside.py").symlink_to(tmp_path / "src" / "module.py")
    return tmp_path


GOOD = {
    "NODE": "tests/property/test_sample.py::test_x[a b-c, d=1]",
    "PROFILE": "ci",
    "PYTHON_VERSION": "3.15",
    "JOBS": "20",
    "RUNS": "25",
    "FIRST_SEED": "0",
    "EXTRA": "--shard records  --property-controls=none",
}


def test_a_request_within_its_bounds_is_written_as_its_outputs(tree: Path) -> None:
    request = repeat_runs.checked_request(GOOD, tree)
    assert repeat_runs.outputs(request) == {
        "node": "tests/property/test_sample.py::test_x[a b-c, d=1]",
        "profile": "ci",
        "python": "3.15",
        "jobs": "20",
        "matrix": json.dumps(list(range(1, 21))),
        "runs": "25",
        "first_seed": "0",
        "extra": "--shard=records --property-controls=none",
    }


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("NODE", "tests"),
        ("NODE", "tests/property/"),
        ("NODE", "tests/property/test_sample.py"),
        ("EXTRA", ""),
        ("EXTRA", "--property-controls only"),
        ("FIRST_SEED", "999999999"),
        ("JOBS", "1"),
        ("RUNS", "1"),
        ("PROFILE", "deep"),
        ("PYTHON_VERSION", "3.11"),
    ],
)
def test_each_input_at_its_edge_is_taken(tree: Path, name: str, value: str) -> None:
    assert repeat_runs.checked_request(GOOD | {name: value}, tree)


TWO_WORDS = {"-p no:hypothesispytest", "-o addopts=", "-c other.toml", "-k slow", "-n 1"}


@pytest.mark.parametrize(
    ("name", "value", "problem"),
    [
        ("NODE", "", "is empty"),
        ("NODE", "src/module.py", "is not `tests` or a path under it"),
        ("NODE", "/etc/passwd", "is not `tests` or a path under it"),
        ("NODE", "tests/../src/module.py", "none of them `.` or `..`"),
        ("NODE", "tests/./property", "none of them `.` or `..`"),
        ("NODE", "testsuite/x.py", "is not `tests` or a path under it"),
        ("NODE", "-p no:hypothesispytest", "is not `tests` or a path under it"),
        ("NODE", "tests/property/test_missing.py", "no file or directory under tests/"),
        ("NODE", "tests/outside.py", "no file or directory under tests/"),
        ("NODE", "tests/property/test_sample.py::", "names nothing after `::`"),
        ("NODE", "tests/property/test_sample.py\njobs=[1]", "printable ASCII"),
        ("NODE", "tests/property/test_sample.py::test_é", "printable ASCII"),
        ("NODE", "tests/property/test sample.py", "is not `tests` or a path under it"),
        ("PROFILE", "default", "the profile 'default' is not one of dev, ci, deep"),
        ("PROFILE", "CI", "the profile 'CI'"),
        ("PYTHON_VERSION", "3.10", "the Python '3.10'"),
        ("PYTHON_VERSION", "3.16", "the Python '3.16'"),
        ("JOBS", "0", "the number of jobs 0 is not from 1 to 20"),
        ("JOBS", "21", "the number of jobs 21 is not from 1 to 20"),
        ("JOBS", "05", "not a whole number in plain digits"),
        ("JOBS", "٣", "not a whole number in plain digits"),
        ("JOBS", "2.0", "not a whole number in plain digits"),
        ("JOBS", " 2", "not a whole number in plain digits"),
        ("JOBS", "", "not a whole number in plain digits"),
        ("RUNS", "26", "the number of runs a job 26 is not from 1 to 25"),
        ("RUNS", "a[$(id)]", "not a whole number in plain digits"),
        ("FIRST_SEED", "-1", "not a whole number in plain digits"),
        ("FIRST_SEED", "1000000000", "the first seed 1000000000 is not from 0 to 999999999"),
        ("FIRST_SEED", "1e3", "not a whole number in plain digits"),
        ("EXTRA", "--hypothesis-profile=default", "'--hypothesis-profile=default' is not one of"),
        ("EXTRA", "--hypothesis-seed=1", "'--hypothesis-seed=1' is not one of"),
        ("EXTRA", "--hypothesis-verbosity=quiet", "is not one of"),
        ("EXTRA", "-p no:hypothesispytest", "'-p' is not one of"),
        ("EXTRA", "-o addopts=", "'-o' is not one of"),
        ("EXTRA", "--override-ini=xfail_strict=false", "is not one of"),
        ("EXTRA", "-c other.toml", "'-c' is not one of"),
        ("EXTRA", "--noconftest", "'--noconftest' is not one of"),
        ("EXTRA", "--confcutdir=tests/unit", "is not one of"),
        ("EXTRA", "-k slow", "'-k' is not one of"),
        ("EXTRA", "--deselect=tests/property", "is not one of"),
        ("EXTRA", "-x", "'-x' is not one of"),
        ("EXTRA", "-n 1", "'-n' is not one of"),
        ("EXTRA", "--shar=records", "'--shar=records' is not one of"),
        ("EXTRA", "--shard", "--shard has the value '', not one of its form"),
        ("EXTRA", "--shard=records --shard=json", "--shard is given twice"),
        ("EXTRA", "--shard=Records", "--shard has the value 'Records'"),
        ("EXTRA", "--property-controls=only;true", "--property-controls has the value 'only;true'"),
        ("EXTRA", "--shard\trecords", "printable ASCII"),
        ("EXTRA", "--shard=records\n--noconftest", "printable ASCII"),
    ],
)
def test_each_input_out_of_bounds_is_refused(tree: Path, name: str, value: str, problem: str) -> None:
    with pytest.raises(RequestError) as refused:
        repeat_runs.checked_request(GOOD | {name: value}, tree)
    # An option off the list with its value as the next word is refused twice: the value is a word of its own.
    assert len(refused.value.problems) == (2 if name == "EXTRA" and value in TWO_WORDS else 1)
    assert problem in refused.value.problems[0], refused.value.problems


def test_every_problem_is_given_at_once(tree: Path) -> None:
    bad = {"NODE": "src", "PROFILE": "x", "PYTHON_VERSION": "x", "JOBS": "x", "RUNS": "x", "FIRST_SEED": "x"}
    with pytest.raises(RequestError) as refused:
        repeat_runs.checked_request(bad | {"EXTRA": "-x"}, tree)
    assert len(refused.value.problems) == 7


def test_the_jobs_seeds_are_the_requests_each_once() -> None:
    seeds = [
        seed
        for job in range(1, 4)
        for seed in repeat_runs.job_seeds({"JOB": str(job), "RUNS": "4", "FIRST_SEED": "7"})
    ]
    assert seeds == list(range(7, 19))


@pytest.mark.parametrize(
    "environment",
    [
        {"JOB": "0", "RUNS": "4", "FIRST_SEED": "7"},
        {"JOB": "1", "RUNS": "04", "FIRST_SEED": "7"},
        {"JOB": "1", "RUNS": "4", "FIRST_SEED": "a[$(id)]"},
    ],
)
def test_the_seeds_of_a_job_out_of_bounds_are_refused(environment: dict[str, str]) -> None:
    with pytest.raises(RequestError):
        repeat_runs.job_seeds(environment)


@pytest.mark.parametrize("runs", [1, 2, 10, 200, 500])
def test_with_none_failed_the_bound_is_the_closed_form(runs: int) -> None:
    assert math.isclose(repeat_runs.upper_bound(0, runs), 1 - 0.05 ** (1 / runs), rel_tol=1e-9)


@pytest.mark.parametrize(("failed", "runs"), [(1, 10), (3, 200), (40, 500), (499, 500)])
def test_the_bound_is_the_rate_at_which_so_few_failures_have_a_five_percent_chance(
    failed: int, runs: int
) -> None:
    bound = repeat_runs.upper_bound(failed, runs)
    chance = sum(math.comb(runs, k) * bound**k * (1 - bound) ** (runs - k) for k in range(failed + 1))
    assert math.isclose(chance, 0.05, rel_tol=1e-6)
    assert failed / runs < bound < repeat_runs.upper_bound(failed + 1, runs)


def test_with_every_run_failed_the_bound_is_one() -> None:
    assert repeat_runs.upper_bound(7, 7) == 1.0
    assert math.isclose(repeat_runs.upper_bound(1, 10), 0.3942, abs_tol=1e-4)


REQUEST = Request("tests/property/test_x.py::test_y", "ci", "3.15", 2, 3, 10, ("--shard=records",))


def records(outcomes: dict[int, str]) -> dict[int, dict[str, Any]]:
    statuses = {"passed": 0, "failed": 1, "interrupted": 124}
    example = (
        "Failing test case: test_y(\n    x=1000,\n)\n\nYou can reproduce ... @reproduce_failure('6', b'<A>')"
    )
    return {
        seed: {
            "seed": seed,
            "status": statuses[outcome],
            "outcome": outcome,
            "tests": 1,
            "failures": [{"test": "tests/property/test_x.py::test_y", "message": "m", "examples": [example]}]
            if outcome == "failed"
            else [],
        }
        for seed, outcome in outcomes.items()
    }


ALL_PASSED = dict.fromkeys(range(10, 16), "passed")


def test_a_summary_of_runs_that_all_passed_passes_with_its_bound() -> None:
    text, verdict, ok = repeat_runs.summary(REQUEST, Sum(records(ALL_PASSED), [], []), "success", "a" * 40)
    assert ok
    assert verdict == "no run of 6 failed: the failure rate is at most 39.3 % (one-sided 95%)"
    assert "| 6 | 6 | 0 | 0 | 0 |" in text
    assert "seeds 10 to 15" in text
    assert "<code>--shard=records</code>" in text
    assert "a" * 12 in text


@pytest.mark.parametrize(
    ("found", "runs_result", "says"),
    [
        (Sum(records(ALL_PASSED | {12: "failed"}), [], []), "failure", "1 of 6 runs failed (16.7 %)"),
        (Sum(records(ALL_PASSED | {12: "failed"}), [], []), "success", "1 of 6 runs failed"),
        (Sum(records(ALL_PASSED | {15: "interrupted"}), [], []), "success", "1 of 6 runs did not finish"),
        (
            Sum(records({seed: "passed" for seed in range(10, 13)}), [13, 14, 15], []),
            "success",
            "3 of 6 runs",
        ),
        (Sum(records(ALL_PASSED), [], ["seed 12 has two records"]), "success", "no run of 6 failed"),
        (Sum(records(ALL_PASSED), [], []), "failure", "the runs' jobs ended in 'failure'"),
        (Sum(records(ALL_PASSED), [], []), "cancelled", "the runs' jobs ended in 'cancelled'"),
        (Sum({}, list(range(10, 16)), []), "skipped", "no run passed or failed"),
    ],
    ids=[
        "failed",
        "failed-jobs-succeeded",
        "interrupted",
        "missing",
        "unreadable",
        "jobs-failed",
        "cancelled",
        "none",
    ],
)
def test_a_summary_fails_where_any_run_failed_or_did_not_finish(
    found: Sum, runs_result: str, says: str
) -> None:
    text, verdict, ok = repeat_runs.summary(REQUEST, found, runs_result)
    assert not ok
    assert says in verdict, verdict
    if found.seeds("failed"):
        assert "### Failing seeds: 12" in text
        assert "&lt;A&gt;" in text
        assert "<A>" not in text


def write_records(directory: Path, job: int, lines: list[str]) -> None:
    (directory / f"runs-{job}").mkdir(parents=True)
    (directory / f"runs-{job}" / "results.jsonl").write_text("".join(f"{line}\n" for line in lines), "utf-8")


def test_the_records_of_every_job_are_read_and_each_seed_counted_once(tmp_path: Path) -> None:
    found = records(ALL_PASSED)
    write_records(tmp_path, 1, [json.dumps(found[seed]) for seed in (10, 11, 12)])
    write_records(
        tmp_path, 2, [json.dumps(found[seed]) for seed in (13, 15)] + [json.dumps(found[13]), "{", "[]"]
    )
    write_records(tmp_path, 3, [json.dumps(found[10] | {"seed": 99}), json.dumps(found[11] | {"seed": True})])
    read = repeat_runs.read_records(tmp_path, REQUEST)
    assert sorted(read.records) == [10, 11, 12, 13, 15]
    assert read.missing == [14]
    assert read.problems == [
        "seed 13 has two records (runs-2/results.jsonl:3)",
        "runs-2/results.jsonl:4 is not a run's record",
        "runs-2/results.jsonl:5 is not a run's record",
        "runs-3/results.jsonl:2 is not a run's record",
        "seeds outside the request have records: 99",
    ]


SUMMED = {
    "NODE": REQUEST.node,
    "PROFILE": "ci",
    "PYTHON_VERSION": "3.15",
    "JOBS": "2",
    "RUNS": "3",
    "FIRST_SEED": "10",
    "EXTRA": "--shard=records",
}


@pytest.mark.parametrize(("outcomes", "status"), [(ALL_PASSED, 0), (ALL_PASSED | {11: "failed"}, 1)])
def test_the_summary_command_writes_the_step_summary_and_exits_by_its_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcomes: dict[int, str], status: int
) -> None:
    found = records(outcomes)
    write_records(tmp_path / "runs", 1, [json.dumps(each) for each in found.values()])
    for name, value in (SUMMED | {"RUNS_RESULT": "success" if status == 0 else "failure"}).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    assert repeat_runs.main(["summary", str(tmp_path / "runs")]) == status
    assert (
        (tmp_path / "summary.md")
        .read_text(encoding="utf-8")
        .startswith("## Repeat runs of <code>tests/property/test_x.py::test_y</code>")
    )
