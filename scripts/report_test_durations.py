# SPDX-License-Identifier: Apache-2.0
"""Where a pytest run's time went, from the JUnit XML it wrote: a Markdown summary for CI's run page.

Every pytest job of `ci.yml` (each Python of the test matrix, each Hypothesis shard) writes one report:
pytest-xdist's controller writes a single file for all its workers. Each test case holds its wall time (setup,
call and teardown) and, from `tests/conftest.py`, two CPU times over the same span: its own process's (the
property `cpu_seconds`, its xdist worker's) and that of the processes it started and waited for
(`children_cpu_seconds`). The workers share the runner's cores, so a test's wall time partly measures the
others; its CPU time much less. A test that runs pytest or git in a subprocess spends its time in its
children. The summary gives the tests in each band of wall time, the slowest tests, the slowest files, and the
total.

It reports and never judges: no duration fails a job. It exits 2 when there is nothing to report: a report
missing or not XML, a test case without the file pytest writes under `junit_family = "xunit1"`
(`pyproject.toml`), or no test that ran.
"""

import argparse
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

CPU_PROPERTY = "cpu_seconds"
CHILDREN_CPU_PROPERTY = "children_cpu_seconds"
# The message pytest gives a test file that failed to import: no test of the run ran.
COLLECTION_FAILURE = "collection failure"
# The upper edges of the bands of wall time, in seconds; the last band has none.
BAND_EDGES = (1.0, 5.0, 20.0, 60.0)
SLOWEST_TESTS = 30
SLOWEST_FILES = 15


class Timing(NamedTuple):
    nodeid: str
    file: str
    wall: float
    cpu: float | None  # None where the run recorded none
    children_cpu: float | None = None


class ReportError(Exception):
    """A report with nothing to summarise."""


def nodeid(case: ElementTree.Element, file: str) -> str:
    """The test's pytest node id: its file, any classes (what `classname` holds beyond the module's dotted
    path), and its name."""
    module = file.removesuffix(".py").replace("/", ".")
    classname = case.get("classname", "")
    classes = classname.removeprefix(module + ".").split(".") if classname.startswith(module + ".") else []
    return "::".join([file, *classes, case.get("name", "")])


def seconds(value: str | None) -> float | None:
    return None if value is None else float(value)


def read_report(path: Path) -> list[Timing]:
    if not path.is_file():
        raise ReportError(
            f"{path}: no such report (pytest writes it with --junitxml as its run ends, which a run its "
            "job's timeout cancelled never reaches)"
        )
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        raise ReportError(f"{path}: not XML ({error})") from error
    tests: list[Timing] = []
    for case in root.iter("testcase"):
        failure = case.find("error")
        if failure is not None and failure.get("message") == COLLECTION_FAILURE:
            continue
        file = case.get("file")
        if not file:
            raise ReportError(
                f'{path}: a test case has no file; pytest writes one with junit_family = "xunit1"'
            )
        properties = {item.get("name"): item.get("value") for item in case.iter("property")}
        try:
            tests.append(
                Timing(
                    nodeid(case, file),
                    file,
                    float(case.get("time", "0")),
                    seconds(properties.get(CPU_PROPERTY)),
                    seconds(properties.get(CHILDREN_CPU_PROPERTY)),
                )
            )
        except ValueError as error:
            raise ReportError(f"{path}: an unreadable time ({error})") from error
    if not tests:
        raise ReportError(f"{path}: no test ran")
    return tests


def duration(seconds: float) -> str:
    return f"{seconds:.2f} s" if seconds < 60 else f"{seconds / 60:.1f} min"


def wall(tests: Sequence[Timing]) -> float:
    return sum(test.wall for test in tests)


def cpu(tests: Sequence[Timing]) -> float:
    return sum(test.cpu for test in tests if test.cpu is not None)


def children_cpu(tests: Sequence[Timing]) -> float:
    return sum(test.children_cpu for test in tests if test.children_cpu is not None)


def optional(seconds: float | None) -> str:
    return "" if seconds is None else duration(seconds)


def bands(tests: Sequence[Timing]) -> list[tuple[str, list[Timing]]]:
    """The tests in each band of wall time, from the shortest band."""
    lower = [0.0, *BAND_EDGES]
    upper = [*BAND_EDGES, float("inf")]
    labels = [f"under {upper[0]:g} s"]
    labels += [f"{low:g} to {high:g} s" for low, high in zip(lower[1:-1], upper[1:-1], strict=True)]
    labels += [f"{lower[-1]:g} s or more"]
    return [
        (label, [test for test in tests if low <= test.wall < high])
        for label, low, high in zip(labels, lower, upper, strict=True)
    ]


def summary(
    tests: Sequence[Timing],
    title: str,
    slowest_tests: int = SLOWEST_TESTS,
    slowest_files: int = SLOWEST_FILES,
) -> str:
    total = wall(tests)
    lines = [
        f"## {title}",
        "",
        f"{len(tests)} tests: {duration(total)} of wall time, {duration(cpu(tests))} of CPU time in the test "
        f"processes and {duration(children_cpu(tests))} in the processes they started, summed over the tests "
        "(setup, call and teardown; collection and start-up left out). A test's CPU time is its own "
        "process's, its xdist worker's; its children's, that of the processes it started and waited for.",
    ]
    without_cpu = sum(test.cpu is None for test in tests)
    if without_cpu:
        lines.append(f"Tests that recorded no CPU time: {without_cpu}.")
    lines += [
        "",
        "| Wall time | Tests | Wall | CPU | Children's CPU | Share of the wall time |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, members in bands(tests):
        share = f"{wall(members) / total:.0%}" if total else ""
        lines.append(
            f"| {label} | {len(members)} | {duration(wall(members))} | {duration(cpu(members))} "
            f"| {duration(children_cpu(members))} | {share} |"
        )
    ranked = sorted(tests, key=lambda test: test.wall, reverse=True)[:slowest_tests]
    lines += [
        "",
        f"### The {len(ranked)} slowest tests",
        "",
        "| Wall | CPU | Children's CPU | Test |",
        "|---:|---:|---:|---|",
    ]
    for test in ranked:
        cpus = f"{optional(test.cpu)} | {optional(test.children_cpu)}"
        lines.append(f"| {duration(test.wall)} | {cpus} | `{test.nodeid}` |")
    files: defaultdict[str, list[Timing]] = defaultdict(list)
    for test in tests:
        files[test.file].append(test)
    slowest = sorted(files.items(), key=lambda item: wall(item[1]), reverse=True)[:slowest_files]
    lines += [
        "",
        f"### The {len(slowest)} slowest files",
        "",
        "| Wall | CPU | Children's CPU | Tests | File |",
        "|---:|---:|---:|---:|---|",
    ]
    for file, members in slowest:
        lines.append(
            f"| {duration(wall(members))} | {duration(cpu(members))} | {duration(children_cpu(members))} "
            f"| {len(members)} | `{file}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument("report", type=Path, help="the JUnit XML pytest wrote with --junitxml")
    parser.add_argument("--title", default="Test durations", help="the summary's heading")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path(summary_file) if summary_file else None,
        help="the file the summary is appended to (default: $GITHUB_STEP_SUMMARY, or standard output)",
    )
    arguments = parser.parse_args(argv)
    try:
        tests = read_report(arguments.report)
    except ReportError as error:
        print(f"::error title=Test durations::{error}")
        return 2
    text = summary(tests, arguments.title)
    if arguments.markdown is None:
        print(text, end="")
    else:
        with arguments.markdown.open("a", encoding="utf-8") as markdown:
            markdown.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
