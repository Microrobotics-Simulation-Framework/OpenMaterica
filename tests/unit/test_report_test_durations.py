# SPDX-License-Identifier: Apache-2.0
"""The durations report reads what pytest writes, each test's CPU time included, and refuses a report with
nothing to summarise."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import report_test_durations
from scripts.report_test_durations import ReportError, Timing, bands, code, read_report, stopped, summary

REPOSITORY = Path(__file__).resolve().parents[2]
# A file of quick tests, some of them parametrised.
SAMPLE = "tests/unit/test_python_versions.py"


def run_pytest(*arguments: str) -> subprocess.CompletedProcess[str]:
    """pytest in a fresh process at the repository's root, as CI runs it, free of this run's options."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *arguments],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_report_written_under_xdist_gives_each_test_its_node_id_and_cpu_time(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    ran = run_pytest(SAMPLE, "-n", "2", f"--junitxml={report}")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    collected = run_pytest(SAMPLE, "--collect-only", "-q")
    nodeids = [line for line in collected.stdout.splitlines() if line.startswith(SAMPLE + "::")]
    tests = read_report(report)
    assert sorted(test.nodeid for test in tests) == sorted(nodeids)
    assert [test.nodeid for test in tests if test.cpu is None or test.children_cpu is None] == []


def test_without_the_conftest_no_test_has_a_cpu_time(tmp_path: Path) -> None:
    """The control: the CPU times above come from `tests/conftest.py`, not from pytest."""
    report = tmp_path / "report.xml"
    ran = run_pytest(SAMPLE, "--noconftest", f"--junitxml={report}")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    tests = read_report(report)
    assert tests
    assert all(test.cpu is None and test.children_cpu is None for test in tests)


# Three tests, run in this order in one process: one that spins for `SPIN` seconds of its own CPU time, one
# that starts a process that spins as long, and one that waits as long. Each test's CPU times are its own only
# if the spinning test's own is at least `SPIN` and hardly more than its wall time (pytest's own work between
# a test's phases is in its CPU time and not in its wall time: about 0.01 s here), the other two's own near
# nothing, and only the test that starts a process has its children's.
SPIN = 0.3
SPINNING = f"""
import time
end = time.process_time() + {SPIN}
while time.process_time() < end:
    pass
"""
SAMPLE_TIMES = f"""\
import subprocess
import sys
import time

SPINNING = {SPINNING!r}


def test_spins():
    exec(SPINNING)


def test_starts_a_process_that_spins():
    subprocess.run([sys.executable, "-c", SPINNING], check=True)


def test_waits():
    time.sleep({SPIN})
"""
CONFTEST = REPOSITORY / "tests" / "conftest.py"


def recorded(tmp_path: Path, conftest: str) -> dict[str, Timing]:
    """Each test of `SAMPLE_TIMES` by name, as `conftest`, loaded as a plugin, records its times."""
    (tmp_path / "recording.py").write_text(conftest, encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(SAMPLE_TIMES, encoding="utf-8")
    report = tmp_path / "report.xml"
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    environment["PYTHONPATH"] = os.pathsep.join([str(tmp_path), str(REPOSITORY)])
    pytest_with_the_plugin = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "recording"]
    ran = subprocess.run(
        [*pytest_with_the_plugin, "-o", "junit_family=xunit1", f"--junitxml={report}", "test_sample.py"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return {test.nodeid.rpartition("::")[2]: test for test in read_report(report)}


def spent(seconds: float | None) -> bool:
    """Whether a test recorded the CPU time of a spin."""
    return seconds is not None and seconds >= 0.95 * SPIN


def idle(seconds: float | None) -> bool:
    return seconds is not None and seconds < SPIN / 3


# What each test must record: of its own CPU time, and of its children's.
WANTED = {
    "test_spins": (spent, idle),
    "test_starts_a_process_that_spins": (idle, spent),
    "test_waits": (idle, idle),
}


def recording_problems(tests: dict[str, Timing]) -> list[str]:
    problems: list[str] = []
    for name, (own, children) in WANTED.items():
        test = tests[name]
        if not own(test.cpu):
            problems.append(f"{name}: its own CPU time, {test.cpu} s")
        if not children(test.children_cpu):
            problems.append(f"{name}: its children's CPU time, {test.children_cpu} s")
    spins = tests["test_spins"]
    if spins.cpu is not None and spins.cpu > spins.wall + SPIN / 2:
        problems.append(f"test_spins: its own CPU time, {spins.cpu} s, in {spins.wall} s")
    return problems


def test_each_test_records_its_own_cpu_time_and_its_childrens(tmp_path: Path) -> None:
    assert recording_problems(recorded(tmp_path, CONFTEST.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("time.process_time()", "time.perf_counter()", "test_waits: its own CPU time"),
        ("time.process_time() - own", "time.process_time()", "test_spins: its own CPU time"),
        ("children_now - children", "children_now", "test_waits: its children's CPU time"),
        ("RUSAGE_CHILDREN", "RUSAGE_SELF", "test_starts_a_process_that_spins: its children's CPU time"),
    ],
    ids=["wall-time", "the-workers-running-total", "the-childrens-running-total", "the-workers-own"],
)
def test_the_cpu_time_check_can_fail(tmp_path: Path, old: str, new: str, problem: str) -> None:
    """The conftest with one fault: wall time recorded as CPU time, the process's running total, its
    children's running total, or its own CPU time as its children's."""
    conftest = CONFTEST.read_text(encoding="utf-8")
    assert old in conftest
    found = recording_problems(recorded(tmp_path, conftest.replace(old, new)))
    assert any(problem in line for line in found), found


def junit(*cases: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite>'
        + "".join(cases)
        + "</testsuite></testsuites>"
    )


def case(
    name: str,
    time: str = "0.5",
    file: str | None = "tests/unit/test_x.py",
    cpu: str | None = "0.4",
    children_cpu: str | None = "0.125",
) -> str:
    module = "tests.unit.test_x"
    attributes = f'classname="{module}" name="{name}" time="{time}"' + (
        "" if file is None else f' file="{file}"'
    )
    recorded = {"cpu_seconds": cpu, "children_cpu_seconds": children_cpu}
    properties = "".join(
        f'<property name="{key}" value="{value}"/>' for key, value in recorded.items() if value is not None
    )
    return f"<testcase {attributes}><properties>{properties}</properties></testcase>"


COLLECTION_FAILURE = (
    '<testcase classname="" name="tests.unit.test_x"><error message="collection failure"/></testcase>'
)
# What pytest-xdist writes for a test still running when ci.yml's interrupt stops the run.
STOPPED = '<testcase time="0.000" />'


def written(tmp_path: Path, text: str) -> Path:
    report = tmp_path / "report.xml"
    report.write_text(text, encoding="utf-8")
    return report


def test_a_test_case_is_read_with_its_node_id_wall_and_cpu_time(tmp_path: Path) -> None:
    classed = case("test_b[1-x]").replace(
        'classname="tests.unit.test_x"', 'classname="tests.unit.test_x.TestB"'
    )
    other = case("test_a", time="2.25", cpu=None, children_cpu=None, file="tests/unit/test_y.py")
    tests = read_report(written(tmp_path, junit(classed, other.replace("test_x", "test_y"))))
    assert tests == [
        Timing("tests/unit/test_x.py::TestB::test_b[1-x]", "tests/unit/test_x.py", 0.5, 0.4, 0.125),
        Timing("tests/unit/test_y.py::test_a", "tests/unit/test_y.py", 2.25, None, None),
    ]


def test_a_test_that_fails_and_then_errors_in_its_teardown_is_one_test(tmp_path: Path) -> None:
    """pytest writes it as two test cases, the first without the properties the teardown records."""
    failed = case("test_a", time="0.25", cpu=None, children_cpu=None)
    torn_down = case("test_a", time="0.125", cpu="0.5", children_cpu="0.0625")
    tests = read_report(written(tmp_path, junit(failed, torn_down, case("test_b"))))
    assert tests == [
        Timing("tests/unit/test_x.py::test_a", "tests/unit/test_x.py", 0.375, 0.5, 0.0625),
        Timing("tests/unit/test_x.py::test_b", "tests/unit/test_x.py", 0.5, 0.4, 0.125),
    ]


def test_the_tests_an_interrupt_stopped_are_counted_and_left_out(tmp_path: Path) -> None:
    report = written(tmp_path, junit(case("test_a"), STOPPED, STOPPED))
    assert [test.nodeid for test in read_report(report)] == ["tests/unit/test_x.py::test_a"]
    assert stopped(report) == 2
    text = summary(read_report(report), "Durations", stopped_tests=2)
    assert "Tests stopped by the interrupt before the job's timeout, which the report does not name" in text
    assert "are left out: 2." in text
    assert "stopped" not in summary(read_report(report), "Durations")


# Two quick tests, then tests that would run for minutes: on two workers, the quick ones end, and a slow one
# is running on each worker when the interrupt comes.
INTERRUPTED_SAMPLE = """
import time

import pytest


@pytest.mark.parametrize("n", range(6))
def test_one(n):
    time.sleep(0.2 if n < 2 else 300)
"""


def test_a_run_interrupted_as_ci_interrupts_it_writes_a_report_that_is_read(tmp_path: Path) -> None:
    """`timeout --signal=INT`, as ci.yml runs each pytest command, sends SIGINT to pytest and then to its
    whole process group, xdist's workers included: pytest writes the report of the tests that ended, and one
    test case holding a time alone for each test still running."""
    (tmp_path / "test_sample.py").write_text(INTERRUPTED_SAMPLE, encoding="utf-8")
    report = tmp_path / "report.xml"
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    pytest_run = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-n",
        "2",
        "-o",
        "junit_family=xunit1",
    ]
    ran = subprocess.run(
        ["timeout", "--signal=INT", "10s", *pytest_run, f"--junitxml={report}", "test_sample.py"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 124, ran.stdout + ran.stderr
    assert sorted(test.nodeid for test in read_report(report)) == [
        "test_sample.py::test_one[0]",
        "test_sample.py::test_one[1]",
    ]
    assert stopped(report) == 2


@pytest.mark.parametrize(
    ("text", "written_as"),
    [
        ("a.py::test[x]", "`a.py::test[x]`"),
        ("a.py::test[c|d]", "`a.py::test[c\\|d]`"),
        ("a.py::test[e`f]", "``a.py::test[e`f]``"),
        ("a.py::test[``]", "```a.py::test[``]```"),
        ("`a.py", "`` `a.py ``"),
    ],
)
def test_a_node_id_is_code_whatever_it_holds(text: str, written_as: str) -> None:
    assert code(text) == written_as


def cells(row: str) -> list[str]:
    """A Markdown table row's cells, split at each `|` not escaped."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)[1:-1]]


def test_a_node_id_with_a_pipe_keeps_the_tables_columns() -> None:
    text = summary([Timing("a|b.py::test[c|d]", "a|b.py", 1.0, 0.5, 0.0)], "Durations")
    slowest_test = next(line for line in text.splitlines() if "test[c" in line)
    slowest_file = text.splitlines()[-1]
    assert cells(slowest_test) == ["1.00 s", "0.50 s", "0.00 s", "`a\\|b.py::test[c\\|d]`"]
    assert cells(slowest_file) == ["1.00 s", "0.50 s", "0.00 s", "1", "`a\\|b.py`"]


def test_each_test_falls_in_one_band_its_lower_edge_included() -> None:
    walls = [0.0, 0.99, 1.0, 4.99, 5.0, 19.99, 20.0, 59.99, 60.0, 600.0]
    tests = [Timing(f"t{index}", "f", wall, None) for index, wall in enumerate(walls)]
    assert [(label, [test.wall for test in members]) for label, members in bands(tests)] == [
        ("under 1 s", [0.0, 0.99]),
        ("1 to 5 s", [1.0, 4.99]),
        ("5 to 20 s", [5.0, 19.99]),
        ("20 to 60 s", [20.0, 59.99]),
        ("60 s or more", [60.0, 600.0]),
    ]


def test_the_summary_gives_the_bands_the_slowest_tests_and_files_and_the_total() -> None:
    tests = [
        Timing("a.py::fast", "a.py", 0.5, 0.25, 0.0),
        Timing("a.py::slow", "a.py", 30.0, 20.0, 1.5),
        Timing("b.py::middling", "b.py", 6.0, 0.5, 5.0),
        Timing("c.py::untimed", "c.py", 2.0, None, None),
    ]
    text = summary(tests, "Test durations, Python 3.11", slowest_tests=2, slowest_files=2)
    assert text.startswith("## Test durations, Python 3.11\n")
    assert "4 tests: 38.50 s of wall time, 20.75 s of CPU time in the test processes and 6.50 s" in text
    assert "Tests that recorded no CPU time: 1." in text
    assert "| under 1 s | 1 | 0.50 s | 0.25 s | 0.00 s | 1% |" in text
    assert "| 20 to 60 s | 1 | 30.00 s | 20.00 s | 1.50 s | 78% |" in text
    assert "| 60 s or more | 0 | 0.00 s | 0.00 s | 0.00 s | 0% |" in text
    slowest = text.partition("### The 2 slowest tests")[2].partition("###")[0]
    assert "| 30.00 s | 20.00 s | 1.50 s | `a.py::slow` |" in slowest
    assert slowest.index("`a.py::slow`") < slowest.index("`b.py::middling`")
    assert "fast" not in slowest
    assert "untimed" not in slowest
    files = text.partition("### The 2 slowest files")[2]
    assert "| 30.50 s | 20.25 s | 1.50 s | 2 | `a.py` |" in files
    assert "| 6.00 s | 0.50 s | 5.00 s | 1 | `b.py` |" in files
    assert "c.py" not in files


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (None, "no such report"),
        ("<testsuites><testsuite>", "not XML"),
        (junit(), "no test ran"),
        (junit(COLLECTION_FAILURE), "no test ran"),
        (junit(case("test_a", file=None)), 'junit_family = "xunit1"'),
        (junit(STOPPED, STOPPED), r"no test ran to its end \(2 stopped by an interrupt\)"),
        (
            junit(case("test_a", file=None).replace('classname="tests.unit.test_x" name="test_a" ', "")),
            'junit_family = "xunit1"',
        ),
        (junit(case("test_a", time="soon")), "an unreadable time"),
        (junit(case("test_a", cpu="lots")), "an unreadable time"),
    ],
    ids=[
        "missing",
        "not-xml",
        "no-test-case",
        "only-a-collection-failure",
        "xunit2",
        "only-stopped",
        "no-name-but-properties",
        "wall",
        "cpu",
    ],
)
def test_a_report_with_nothing_to_summarise_is_refused(
    tmp_path: Path, text: str | None, message: str
) -> None:
    report = tmp_path / "report.xml" if text is None else written(tmp_path, text)
    with pytest.raises(ReportError, match=message):
        read_report(report)


def test_main_appends_the_summary_to_the_step_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step_summary = tmp_path / "summary.md"
    step_summary.write_text("before\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
    report = written(tmp_path, junit(case("test_a")))
    assert report_test_durations.main([str(report), "--title", "Durations, json"]) == 0
    assert step_summary.read_text(encoding="utf-8").startswith("before\n## Durations, json\n")


def test_main_exits_2_on_a_report_with_nothing_to_summarise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        report_test_durations.main([str(tmp_path / "missing.xml"), "--markdown", str(tmp_path / "s.md")]) == 2
    )
    assert capsys.readouterr().out.startswith("::error title=Test durations::")
    assert not (tmp_path / "s.md").exists()
