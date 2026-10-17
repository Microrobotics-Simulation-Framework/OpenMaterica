# SPDX-License-Identifier: Apache-2.0
"""A repeat run's request, each run's record, and the sum of the runs, for `.github/workflows/repeat.yml`.

The workflow runs one pytest node, a test, a file or a directory under `tests/`, many times in parallel jobs,
each run under a seed of its own (`--hypothesis-seed`), to measure how often it fails. The profile is one of
the repository's own (`tests/conftest.py`), and no input reaches the example counts it sets. Standard library
only, so that it runs on the runner's Python before anything is installed.

- `request` checks the dispatch's inputs, read from the environment, and writes them, checked, as the step's
  outputs: the node a path under `tests/` that exists, in printable ASCII; the profile and the Python one of
  those listed here; the counts and the first seed plain whole numbers within their bounds; the extra pytest
  arguments from a closed list. It refuses anything else, and gives every reason.
- `seeds` prints the seeds of one job, one a line: job `j` of `r` runs from the first seed `s` runs the seeds
  `s + (j - 1) r` to `s + j r - 1`, so that no two runs of a request share one.
- `record SEED STATUS REPORT` prints one run's record, a line of JSON: its seed, pytest's exit status, the
  outcome, the number of tests, and for each test that failed its node id, its message and each failing
  example Hypothesis reported.
- `summary DIRECTORY` sums the records under `DIRECTORY`, a `results.jsonl` for each job and each attempt
  of it: the runs, the failures and their seeds and examples, and the failure rate with its one-sided 95 %
  upper bound, appended to the step summary. It exits 1 where a run failed or did not finish, a seed has no
  record or two, the runs' jobs did not all succeed, or the run's attempt (`ATTEMPT`) is not its first. Of a
  seed's two records, as from a job run again, the one that did not pass is counted, so that no later record
  hides a failure.
"""

import argparse
import html
import json
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple
from xml.etree import ElementTree

# The repository's Hypothesis profiles (`EXAMPLES` in tests/conftest.py) and the Pythons CI tests (ci.yml's
# test matrix): tests/unit/test_ci_workflows.py holds these, and the workflow's choices, to both.
PROFILES = ("dev", "ci", "deep")
PYTHONS = ("3.11", "3.12", "3.13", "3.14", "3.15")
MAX_JOBS = 20
MAX_RUNS = 25
MAX_FIRST_SEED = 999_999_999
# The extra pytest arguments a request may give, each at most once, by the pattern of its value. pytest
# refuses a value its option does not list (`choices` in tests/conftest.py) when the request job collects the
# node.
OPTIONS = {"--shard": re.compile(r"[a-z0-9_]+"), "--property-controls": re.compile(r"[a-z]+")}
# A path pytest is given: `tests`, or a path under it, by parts of these characters. A node's part after
# `::` may hold any printable ASCII, as pytest writes a parametrised test's id; no part of a request may hold
# a line break, which would write an output of its own.
NODE_PATH = re.compile(r"tests(?:/[A-Za-z0-9_.-]+)*/?")
PRINTABLE = re.compile(r"[\x20-\x7e]+")
WHOLE_NUMBER = re.compile(r"0|[1-9][0-9]*")

# pytest's exit statuses, and `timeout`'s once it has interrupted pytest; a run that recorded a failed test
# failed, whatever its status.
OUTCOMES = {0: "passed", 1: "failed", 5: "no test ran", 124: "interrupted"}
PASSED, FAILED = "passed", "failed"
# The first line of each failing example Hypothesis reports: "Failing test case" since 6.x's later releases,
# "Falsifying example" before, and "explicit" for an `@example`.
EXAMPLE_HEAD = re.compile(r"(?:Falsifying|Failing)(?: explicit)? (?:example|test case)\b")
EXAMPLE_END = "@reproduce_failure("
MAX_EXAMPLE_LINES = 60
MAX_MESSAGE = 2_000
# The failing seeds the summary shows with their examples; the others it lists by seed.
SHOWN_FAILURES = 20
CONFIDENCE = 0.95


class Request(NamedTuple):
    node: str
    profile: str
    python: str
    jobs: int
    runs: int
    first_seed: int
    extra: tuple[str, ...]


class RequestError(Exception):
    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def whole_number(name: str, text: str, low: int, high: int, problems: list[str]) -> int:
    """`text` as a whole number from `low` to `high`, written in ASCII digits without a sign or a leading zero
    (bash reads `010` as eight); otherwise a problem, and `low`."""
    if not WHOLE_NUMBER.fullmatch(text):
        problems.append(f"{name} {text!r} is not a whole number in plain digits")
        return low
    value = int(text)
    if not low <= value <= high:
        problems.append(f"{name} {value} is not from {low} to {high}")
        return low
    return value


def node_problems(node: str, root: Path) -> list[str]:
    if not PRINTABLE.fullmatch(node):
        return [f"the node {node!r} is empty or holds a character other than printable ASCII"]
    path, separator, rest = node.partition("::")
    if not NODE_PATH.fullmatch(path) or any(part in {".", ".."} for part in path.split("/")):
        return [
            f"the node's path {path!r} is not `tests` or a path under it, by parts of letters, digits, `_`, "
            "`.` and `-`, none of them `.` or `..`"
        ]
    if separator and not rest:
        return [f"the node {node!r} names nothing after `::`"]
    tests = (root / "tests").resolve()
    found = (root / path).resolve()
    if not found.exists() or not found.is_relative_to(tests):
        return [f"the node's path {path!r} is no file or directory under tests/"]
    return []


def extra_arguments(text: str, problems: list[str]) -> tuple[str, ...]:
    """The extra arguments, each as `--option=value`: an option of `OPTIONS` at most once, its value given
    after `=` or as the next word."""
    if text and not PRINTABLE.fullmatch(text):
        problems.append(f"the extra arguments {text!r} hold a character other than printable ASCII")
        return ()
    words = text.split(" ")
    words = [word for word in words if word]
    arguments: dict[str, str] = {}
    index = 0
    while index < len(words):
        option, equals, value = words[index].partition("=")
        index += 1
        if option not in OPTIONS:
            problems.append(f"the extra argument {words[index - 1]!r} is not one of {', '.join(OPTIONS)}")
            continue
        if not equals:
            value = words[index] if index < len(words) else ""
            index += 1
        if option in arguments:
            problems.append(f"the extra argument {option} is given twice")
        elif not OPTIONS[option].fullmatch(value):
            problems.append(f"the extra argument {option} has the value {value!r}, not one of its form")
        else:
            arguments[option] = value
    return tuple(f"{option}={value}" for option, value in arguments.items())


def checked_request(environment: Mapping[str, str], root: Path) -> Request:
    """The request the environment gives, checked against the tree at `root`."""
    problems: list[str] = []
    node = environment.get("NODE", "")
    problems += node_problems(node, root)
    profile = environment.get("PROFILE", "")
    if profile not in PROFILES:
        problems.append(f"the profile {profile!r} is not one of {', '.join(PROFILES)}")
    python = environment.get("PYTHON_VERSION", "")
    if python not in PYTHONS:
        problems.append(f"the Python {python!r} is not one of {', '.join(PYTHONS)}")
    jobs = whole_number("the number of jobs", environment.get("JOBS", ""), 1, MAX_JOBS, problems)
    runs = whole_number("the number of runs a job", environment.get("RUNS", ""), 1, MAX_RUNS, problems)
    first_seed = whole_number(
        "the first seed", environment.get("FIRST_SEED", ""), 0, MAX_FIRST_SEED, problems
    )
    extra = extra_arguments(environment.get("EXTRA", ""), problems)
    if problems:
        raise RequestError(problems)
    return Request(node, profile, python, jobs, runs, first_seed, extra)


def outputs(request: Request) -> dict[str, str]:
    return {
        "node": request.node,
        "profile": request.profile,
        "python": request.python,
        "jobs": str(request.jobs),
        "matrix": json.dumps(list(range(1, request.jobs + 1))),
        "runs": str(request.runs),
        "first_seed": str(request.first_seed),
        "extra": " ".join(request.extra),
    }


def job_seeds(environment: Mapping[str, str]) -> list[int]:
    problems: list[str] = []
    job = whole_number("the job", environment.get("JOB", ""), 1, MAX_JOBS, problems)
    runs = whole_number("the number of runs a job", environment.get("RUNS", ""), 1, MAX_RUNS, problems)
    first_seed = whole_number(
        "the first seed", environment.get("FIRST_SEED", ""), 0, MAX_FIRST_SEED, problems
    )
    if problems:
        raise RequestError(problems)
    start = first_seed + (job - 1) * runs
    return list(range(start, start + runs))


def failing_examples(text: str) -> list[str]:
    """Each failing example Hypothesis reported in a failure's text, from its first line to its
    `@reproduce_failure` line: the lines after the first that carry the same prefix before its column
    (pytest's `E`, or an exception group's `|`), without it."""
    lines = text.splitlines()
    examples: list[str] = []
    index = 0
    while index < len(lines):
        head = EXAMPLE_HEAD.search(lines[index])
        if head is None:
            index += 1
            continue
        column = head.start()
        prefix = lines[index][:column].rstrip()
        block = [lines[index][column:]]
        index += 1
        while index < len(lines) and len(block) < MAX_EXAMPLE_LINES and EXAMPLE_END not in block[-1]:
            line = lines[index]
            if line[:column].rstrip() != prefix or EXAMPLE_HEAD.search(line):
                break
            block.append(line[column:])
            index += 1
        while block and not block[-1].strip():
            block.pop()
        examples.append("\n".join(block))
    return examples


def node_id(case: ElementTree.Element) -> str:
    """A test case's pytest node id, from its file (`junit_family = "xunit1"` in pyproject.toml), any classes,
    and its name."""
    file = case.get("file", "")
    module = file.removesuffix(".py").replace("/", ".")
    classname = case.get("classname", "")
    classes = classname.removeprefix(module + ".").split(".") if classname.startswith(module + ".") else []
    return "::".join([file or classname, *classes, case.get("name", "")])


def record(seed: int, status: int, report: Path) -> dict[str, Any]:
    """One run's record. A report that is missing or unreadable, as from a run stopped before pytest wrote
    it, gives no count of tests and no failures."""
    try:
        cases = list(ElementTree.parse(report).getroot().iter("testcase"))
    except (OSError, ElementTree.ParseError):
        cases = None
    tests: set[str] = set()
    failures: list[dict[str, Any]] = []
    for case in cases or []:
        # A test an interrupt stopped is written with a time alone (scripts/report_test_durations.py).
        if not any(case.get(attribute) for attribute in ("name", "classname", "file")):
            continue
        tests.add(node_id(case))
        for found in case:
            if found.tag in {"failure", "error"}:
                message = found.get("message", "")
                failure = {
                    "test": node_id(case),
                    "message": message[:MAX_MESSAGE],
                    "examples": failing_examples(found.text or message),
                }
                if failure not in failures:
                    failures.append(failure)
    if status == 0:
        outcome = PASSED
    elif failures or status == 1:
        outcome = FAILED
    else:
        outcome = OUTCOMES.get(status, "error")
    counted = None if cases is None else len(tests)
    return {"seed": seed, "status": status, "outcome": outcome, "tests": counted, "failures": failures}


def upper_bound(failed: int, runs: int, confidence: float = CONFIDENCE) -> float:
    """The exact one-sided upper confidence bound of a failure rate, from `failed` failures in `runs` runs
    (Clopper and Pearson): the rate at which `failed` failures or fewer have the chance `1 - confidence`. With
    none failed it is `1 - (1 - confidence) ** (1 / runs)`, about 3 / `runs` at 95 %."""
    if failed >= runs:
        return 1.0
    chance = 1 - confidence

    def at_most(rate: float) -> float:
        return sum(math.comb(runs, k) * rate**k * (1 - rate) ** (runs - k) for k in range(failed + 1))

    low, high = failed / runs, 1.0
    for _ in range(200):
        middle = (low + high) / 2
        if at_most(middle) > chance:
            low = middle
        else:
            high = middle
    return high


def seed_ranges(seeds: Sequence[int]) -> str:
    """`[1, 2, 3, 5]` as `1 to 3, 5`."""
    spans: list[list[int]] = []
    for seed in sorted(seeds):
        if spans and seed == spans[-1][1] + 1:
            spans[-1][1] = seed
        else:
            spans.append([seed, seed])
    return ", ".join(str(low) if low == high else f"{low} to {high}" for low, high in spans)


def percent(rate: float) -> str:
    return f"{100 * rate:.3g} %"


def code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


class Sum(NamedTuple):
    records: dict[int, dict[str, Any]]
    missing: list[int]
    problems: list[str]

    def seeds(self, *outcomes: str) -> list[int]:
        return [seed for seed, found in sorted(self.records.items()) if found["outcome"] in outcomes]


def read_records(directory: Path, request: Request) -> Sum:
    records: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    for path in sorted(directory.rglob("results.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{path.relative_to(directory)}:{number}"
            try:
                found = json.loads(line)
                seed = found["seed"]
                if not (
                    type(seed) is int and type(found["status"]) is int and isinstance(found["outcome"], str)
                ):
                    raise TypeError
                if not isinstance(found["failures"], list):
                    raise TypeError
            except (ValueError, KeyError, TypeError):
                problems.append(f"{where} is not a run's record")
                continue
            if seed in records:
                problems.append(f"seed {seed} has two records ({where})")
                if records[seed]["outcome"] != PASSED:
                    continue
            records[seed] = found
    expected = range(request.first_seed, request.first_seed + request.jobs * request.runs)
    unexpected = sorted(set(records) - set(expected))
    if unexpected:
        problems.append(f"seeds outside the request have records: {seed_ranges(unexpected)}")
    missing = sorted(set(expected) - set(records))
    return Sum({seed: found for seed, found in records.items() if seed in expected}, missing, problems)


def failure_details(found: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for failure in found["failures"]:
        shown = failure.get("examples") or [failure.get("message", "")]
        lines += [f"{code(str(failure.get('test', '')))}:", ""]
        lines += [f"<pre>{html.escape(str(text))}</pre>\n" for text in shown]
    return lines or ["No test is named: the report is missing or holds no failure.", ""]


def summary(
    request: Request, found: Sum, runs_result: str, commit: str = "", attempt: int = 1
) -> tuple[str, str, bool]:
    """The step summary's Markdown, its one-line verdict, and whether the request passed: never on an attempt
    of the run but the first, whose records a job run again would add to its first attempt's or replace."""
    passed, failed = found.seeds(PASSED), found.seeds(FAILED)
    unfinished = [
        seed for seed, each in sorted(found.records.items()) if each["outcome"] not in {PASSED, FAILED}
    ]
    decided = len(passed) + len(failed)
    total = request.jobs * request.runs
    last_seed = request.first_seed + total - 1
    extra = ", ".join(code(argument) for argument in request.extra) or "none"
    at = f", at {code(commit[:12])}" if commit else ""
    lines = [
        f"## Repeat runs of {code(request.node)}",
        "",
        f"Profile {code(request.profile)}, Python {request.python}, extra arguments: {extra}{at}. "
        f"{request.jobs} jobs of {request.runs} runs, {total} in all, seeds {request.first_seed} to "
        f"{last_seed}.",
        "",
        "| Runs | Passed | Failed | Did not finish | No record |",
        "|---:|---:|---:|---:|---:|",
        f"| {total} | {len(passed)} | {len(failed)} | {len(unfinished)} | {len(found.missing)} |",
        "",
    ]
    if decided:
        bound = f"at most {percent(upper_bound(len(failed), decided))} (one-sided {CONFIDENCE:.0%})"
        if failed:
            share = percent(len(failed) / decided)
            verdict = f"{len(failed)} of {decided} runs failed ({share}); the failure rate is {bound}"
        else:
            verdict = f"no run of {decided} failed: the failure rate is {bound}"
    else:
        verdict = "no run passed or failed"
    if decided < total:
        verdict += f"; {total - decided} of {total} runs did not finish or have no record"
    if found.problems:
        verdict += f"; problems with the records: {len(found.problems)} (below)"
    if runs_result != "success":
        verdict += f"; the runs' jobs ended in {runs_result!r}"
    if attempt != 1:
        verdict += (
            f"; this is attempt {attempt} of the run, which counts only a first: dispatch the request anew"
        )
    lines += [f"**{verdict[0].upper()}{verdict[1:]}.**", ""]
    if failed:
        lines += [f"### Failing seeds: {seed_ranges(failed)}", ""]
        for seed in failed[:SHOWN_FAILURES]:
            lines += [f"#### Seed {seed}", "", *failure_details(found.records[seed])]
        if len(failed) > SHOWN_FAILURES:
            lines += [
                f"The examples of the other {len(failed) - SHOWN_FAILURES} are in their jobs' records.",
                "",
            ]
    if unfinished:
        lines += ["### Runs that did not finish", ""]
        for seed in unfinished:
            each = found.records[seed]
            lines.append(f"- seed {seed}: {each['outcome']} (exit {each['status']})")
        lines.append("")
    if found.missing:
        lines += [
            f"### Seeds with no record: {seed_ranges(found.missing)}",
            "",
            "Their job stopped before it ran them, was cancelled, or kept no record (its log says which).",
            "",
        ]
    if found.problems:
        lines += [
            "### Records that cannot be read",
            "",
            *[f"- {html.escape(problem)}" for problem in found.problems],
            "",
        ]
    ok = (
        not (failed or unfinished or found.missing or found.problems)
        and runs_result == "success"
        and attempt == 1
    )
    return "\n".join(lines), verdict, ok


def annotation(text: str) -> str:
    """`text` as a workflow command's message: `%`, carriage return and line feed escaped."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def write_outputs(values: Mapping[str, str]) -> None:
    lines = "".join(f"{name}={value}\n" for name, value in values.items())
    if target := os.environ.get("GITHUB_OUTPUT"):
        with Path(target).open("a", encoding="utf-8") as output:
            output.write(lines)
    else:
        print(lines, end="")


def summed_request(environment: Mapping[str, str]) -> Request:
    """The request as the request job wrote it: its counts read again, its text as given."""
    problems: list[str] = []
    jobs = whole_number("the number of jobs", environment.get("JOBS", ""), 1, MAX_JOBS, problems)
    runs = whole_number("the number of runs a job", environment.get("RUNS", ""), 1, MAX_RUNS, problems)
    first_seed = whole_number(
        "the first seed", environment.get("FIRST_SEED", ""), 0, MAX_FIRST_SEED, problems
    )
    if problems:
        raise RequestError(problems)
    extra = tuple(word for word in environment.get("EXTRA", "").split(" ") if word)
    return Request(
        environment.get("NODE", ""),
        environment.get("PROFILE", ""),
        environment.get("PYTHON_VERSION", ""),
        jobs,
        runs,
        first_seed,
        extra,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("request", help="check the request in the environment and write it as outputs")
    commands.add_parser("seeds", help="print the seeds of the job JOB, one a line")
    recording = commands.add_parser("record", help="print one run's record as a line of JSON")
    recording.add_argument("seed", type=int)
    recording.add_argument("status", type=int)
    recording.add_argument("report", type=Path, help="the JUnit XML the run wrote")
    summing = commands.add_parser("summary", help="sum the records under DIRECTORY")
    summing.add_argument("directory", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "request":
            request = checked_request(os.environ, Path.cwd())
            write_outputs(outputs(request))
            print(f"The request, checked: {request}")
        elif arguments.command == "seeds":
            print("\n".join(str(seed) for seed in job_seeds(os.environ)))
        elif arguments.command == "record":
            print(json.dumps(record(arguments.seed, arguments.status, arguments.report)))
        else:
            request = summed_request(os.environ)
            problems: list[str] = []
            attempt = whole_number(
                "the run's attempt", os.environ.get("ATTEMPT", ""), 1, sys.maxsize, problems
            )
            if problems:
                raise RequestError(problems)
            text, verdict, ok = summary(
                request,
                read_records(arguments.directory, request),
                os.environ.get("RUNS_RESULT", ""),
                os.environ.get("GITHUB_SHA", ""),
                attempt,
            )
            print(text)
            if target := os.environ.get("GITHUB_STEP_SUMMARY"):
                with Path(target).open("a", encoding="utf-8") as markdown:
                    markdown.write(text + "\n")
            print(f"::{'notice' if ok else 'error'} title=Repeat runs::{annotation(verdict)}")
            return 0 if ok else 1
    except RequestError as error:
        for problem in error.problems:
            print(f"::error title=Repeat request::{annotation(problem)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
