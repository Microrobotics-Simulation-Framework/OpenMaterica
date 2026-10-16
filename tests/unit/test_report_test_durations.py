# SPDX-License-Identifier: Apache-2.0
"""The durations report reads what pytest writes, each test's CPU time included, and refuses a report with
nothing to summarise."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import report_test_durations
from scripts.report_test_durations import ReportError, Timing, bands, read_report, summary

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
    assert [test.nodeid for test in tests if test.cpu is None] == []


def test_without_the_conftest_no_test_has_a_cpu_time(tmp_path: Path) -> None:
    """The control: the CPU times above come from `tests/conftest.py`, not from pytest."""
    report = tmp_path / "report.xml"
    ran = run_pytest(SAMPLE, "--noconftest", f"--junitxml={report}")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    tests = read_report(report)
    assert tests
    assert all(test.cpu is None for test in tests)


# Two tests, run in this order in one process: one that spins for `SPIN` seconds of its own CPU time, and one
# that waits as long. Each test's CPU time is its own only if the waiting test's is near nothing and the
# spinning test's is at least `SPIN` and hardly more than its wall time (pytest's own work between a test's
# phases is in its CPU time and not in its wall time: about 0.01 s here).
SPIN = 0.3
SPINS_THEN_WAITS = f"""\
import time


def test_spins():
    end = time.process_time() + {SPIN}
    while time.process_time() < end:
        pass


def test_waits():
    time.sleep({SPIN})
"""
CONFTEST = REPOSITORY / "tests" / "conftest.py"


def recorded(tmp_path: Path, conftest: str) -> dict[str, Timing]:
    """Each test of `SPINS_THEN_WAITS` by name, as `conftest`, loaded as a plugin, records its times."""
    (tmp_path / "recording.py").write_text(conftest, encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(SPINS_THEN_WAITS, encoding="utf-8")
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


def recording_problems(tests: dict[str, Timing]) -> list[str]:
    spins, waits = tests["test_spins"], tests["test_waits"]
    problems: list[str] = []
    if spins.cpu is None or spins.cpu < 0.95 * SPIN:
        problems.append(f"the spinning test recorded {spins.cpu} s of CPU time for its {SPIN} s")
    if spins.cpu is not None and spins.cpu > spins.wall + SPIN / 2:
        problems.append(f"the spinning test recorded {spins.cpu} s of CPU time in {spins.wall} s")
    if waits.cpu is None or waits.cpu >= SPIN / 3:
        problems.append(f"the waiting test recorded {waits.cpu} s of CPU time")
    return problems


def test_each_test_records_its_own_cpu_time(tmp_path: Path) -> None:
    assert recording_problems(recorded(tmp_path, CONFTEST.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("time.process_time()", "time.perf_counter()", "the waiting test recorded"),
        (
            "time.process_time() - item.stash[CPU_AT_SETUP]",
            "time.process_time()",
            "the spinning test recorded",
        ),
    ],
    ids=["wall-time", "the-workers-running-total"],
)
def test_the_cpu_time_check_can_fail(tmp_path: Path, old: str, new: str, problem: str) -> None:
    """The conftest with one fault: wall time recorded as CPU time, or the process's running total."""
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
    name: str, time: str = "0.5", file: str | None = "tests/unit/test_x.py", cpu: str | None = "0.4"
) -> str:
    module = "tests.unit.test_x"
    attributes = f'classname="{module}" name="{name}" time="{time}"' + (
        "" if file is None else f' file="{file}"'
    )
    properties = (
        "" if cpu is None else f'<properties><property name="cpu_seconds" value="{cpu}"/></properties>'
    )
    return f"<testcase {attributes}>{properties}</testcase>"


COLLECTION_FAILURE = (
    '<testcase classname="" name="tests.unit.test_x"><error message="collection failure"/></testcase>'
)


def written(tmp_path: Path, text: str) -> Path:
    report = tmp_path / "report.xml"
    report.write_text(text, encoding="utf-8")
    return report


def test_a_test_case_is_read_with_its_node_id_wall_and_cpu_time(tmp_path: Path) -> None:
    classed = case("test_b[1-x]").replace(
        'classname="tests.unit.test_x"', 'classname="tests.unit.test_x.TestB"'
    )
    other = case("test_a", time="2.25", cpu=None, file="tests/unit/test_y.py").replace("test_x", "test_y")
    tests = read_report(written(tmp_path, junit(classed, other)))
    assert tests == [
        Timing("tests/unit/test_x.py::TestB::test_b[1-x]", "tests/unit/test_x.py", 0.5, 0.4),
        Timing("tests/unit/test_y.py::test_a", "tests/unit/test_y.py", 2.25, None),
    ]


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
        Timing("a.py::fast", "a.py", 0.5, 0.25),
        Timing("a.py::slow", "a.py", 30.0, 20.0),
        Timing("b.py::middling", "b.py", 6.0, 5.0),
        Timing("c.py::untimed", "c.py", 2.0, None),
    ]
    text = summary(tests, "Test durations, Python 3.11", slowest_tests=2, slowest_files=2)
    assert text.startswith("## Test durations, Python 3.11\n")
    assert "4 tests: 38.50 s of wall time and 25.25 s of CPU time" in text
    assert "Tests that recorded no CPU time: 1." in text
    assert "| under 1 s | 1 | 0.50 s | 0.25 s | 1% |" in text
    assert "| 20 to 60 s | 1 | 30.00 s | 20.00 s | 78% |" in text
    assert "| 60 s or more | 0 | 0.00 s | 0.00 s | 0% |" in text
    slowest = text.partition("### The 2 slowest tests")[2].partition("###")[0]
    assert slowest.index("`a.py::slow`") < slowest.index("`b.py::middling`")
    assert "fast" not in slowest
    assert "untimed" not in slowest
    files = text.partition("### The 2 slowest files")[2]
    assert "| 30.50 s | 20.25 s | 2 | `a.py` |" in files
    assert "| 6.00 s | 5.00 s | 1 | `b.py` |" in files
    assert "c.py" not in files


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (None, "no such report"),
        ("<testsuites><testsuite>", "not XML"),
        (junit(), "no test ran"),
        (junit(COLLECTION_FAILURE), "no test ran"),
        (junit(case("test_a", file=None)), 'junit_family = "xunit1"'),
        (junit(case("test_a", time="soon")), "an unreadable time"),
        (junit(case("test_a", cpu="lots")), "an unreadable time"),
    ],
    ids=["missing", "not-xml", "no-test-case", "only-a-collection-failure", "xunit2", "wall", "cpu"],
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
