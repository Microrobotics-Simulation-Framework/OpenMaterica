# SPDX-License-Identifier: Apache-2.0
"""The workflows do what their comments say.

A workflow that runs less than it claims still goes green, so each test here holds one thing nothing else
would notice breaking, and each has a control in which the check must fail.
"""

import ast
import copy
import fnmatch
import functools
import glob
import itertools
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence, Set
from pathlib import Path
from typing import Any, NamedTuple, cast

import pytest
import yaml

from scripts import check_confidential, mutant_runs, repeat_runs, schema_index
from tests.unit.test_report_test_durations import INTERRUPT_AS_CI
from tests.unit.throwaway_git import throwaway_repository

REPOSITORY = Path(__file__).resolve().parents[2]
WORKFLOWS = REPOSITORY / ".github" / "workflows"

# The image every job runs on (ci.yml says why, above its jobs).
RUNNER_IMAGE = "ubuntu-24.04"

# A workflow as PyYAML reads it.
Workflow = dict[str, Any]

# The gate's step that finds what a change touched, and the result's step that reads every job.
GATE_STEP, GATE_STEP_ID = "Changed paths", "paths"
RESULT_STEP = "Every job the gate asked for succeeded, and none failed or was cancelled"
# Each job the gate decides, by the output that decides it.
GATED = {
    "static": "code",
    "generated": "code",
    "tests": "code",
    "controls": "code",
    "hypothesis": "hypothesis",
    "site": "site",
    "commit": "commits",
    "site_commit": "site_commits",
}
# How each output runs its jobs: `code`, `hypothesis` and `site` when true, `commits` and `site_commits` when
# it lists one.
RUNS_WHEN = {
    "code": "== 'true'",
    "hypothesis": "== 'true'",
    "site": "== 'true'",
    "commits": "!= '[]'",
    "site_commits": "!= '[]'",
}
# Jobs the gate does not decide: the gate itself, the result, and the weekly and manual fuzz job.
UNGATED = {"gate", "result", "fuzz"}
# A path of each kind the gate calls documentation, as its tests commit them in a throwaway repository.
DOCUMENTATION_EXAMPLES = (
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/regulatory/intended_use.md",
    "docs/validation/known_anomalies.yaml",
    ".github/ISSUE_TEMPLATE/anomaly.yml",
    ".github/pull_request_template.md",
)


def workflow(name: str) -> Workflow:
    """The workflow as PyYAML reads it, each file parsed once: each caller gets a deep copy of its own, since
    callers change what they get."""
    return copy.deepcopy(_parsed_workflow(WORKFLOWS / name))


@functools.cache
def _parsed_workflow(path: Path) -> Workflow:
    loaded: Workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def unpinned_jobs(workflows: dict[str, Workflow]) -> list[str]:
    """Each job, by workflow, that does not run on `RUNNER_IMAGE`."""
    return [
        f"{name}: {job_id} runs on {job.get('runs-on')!r}"
        for name, loaded in workflows.items()
        for job_id, job in loaded["jobs"].items()
        if job.get("runs-on") != RUNNER_IMAGE
    ]


def workflow_names(directory: Path = WORKFLOWS) -> list[str]:
    """The name of each workflow's file: GitHub reads `.yml` and `.yaml` alike."""
    return sorted(path.name for pattern in ("*.yml", "*.yaml") for path in directory.glob(pattern))


def workflows() -> dict[str, Workflow]:
    """Every workflow, by its file's name."""
    names = workflow_names()
    assert {"ci.yml", "pages.yml", "release.yml"} <= set(names)
    return {name: workflow(name) for name in names}


def test_a_workflow_is_found_by_either_extension(tmp_path: Path) -> None:
    for name in ("a.yml", "b.yaml", "README.md", "c.yml.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert workflow_names(tmp_path) == ["a.yml", "b.yaml"]


def test_every_job_of_every_workflow_runs_on_the_pinned_image() -> None:
    assert unpinned_jobs(workflows()) == []


def test_the_image_check_can_fail() -> None:
    workflows: dict[str, Workflow] = {
        "ci.yml": {"jobs": {"gate": {"runs-on": "ubuntu-latest"}, "static": {"runs-on": RUNNER_IMAGE}}},
        "pages.yml": {"jobs": {"deploy": {}}},
    }
    assert unpinned_jobs(workflows) == [
        "ci.yml: gate runs on 'ubuntu-latest'",
        "pages.yml: deploy runs on None",
    ]


def step(job: dict[str, Any], name: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [step for step in job["steps"] if step.get("name") == name]
    assert len(found) == 1, f"{len(found)} steps named {name!r}"
    return found[0]


# GitHub's expressions as far as the workflows use them: strings, numbers, true, false and null, context paths
# (`github.event_name`), the status functions (`success()`), `fromJSON(...)`, `!`, `==`, `!=`, `&&`, `||` and
# parentheses. Anything else fails the test, rather than be guessed.
EXPRESSION_TOKEN = re.compile(
    r"\s*('(?:[^']|'')*'|\d+(?:\.\d+)?|[A-Za-z_][\w.-]*(?:\(\))?|==|!=|&&|\|\||[!()])"
)
STATUS_FUNCTION = re.compile(r"\b(?:success|failure|cancelled|always)\(\)")
# The functions of one argument the workflows call, as GitHub computes them. Python's JSON parser and GitHub's
# differ at the edges (`010`, `NaN`), which no test here reaches: each value it parses is checked first.
FUNCTIONS: dict[str, Callable[[object], object]] = {"fromJSON": lambda value: json.loads(as_text(value))}


def as_number(value: object) -> float:
    """A value as GitHub's `==` compares it with one of another type."""
    if value is None:
        return 0.0
    if isinstance(value, bool | int | float):
        return float(value)
    try:
        return float(str(value).strip() or 0)
    except ValueError:
        return math.nan


def truthy(value: object) -> bool:
    return value not in (None, False, 0, "") and not (isinstance(value, float) and math.isnan(value))


def equal(left: object, right: object) -> bool:
    """GitHub's `==`: strings ignoring case, and values of two types as numbers."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    if type(left) is type(right):
        return left == right
    return as_number(left) == as_number(right)


def as_text(value: object) -> str:
    """A value as GitHub writes it into text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def evaluated(expression: str, context: Mapping[str, object]) -> object:
    """The value of `expression`, each context path and status function in it as `context` gives it."""
    tokens: list[str] = []
    position, end = 0, len(expression.rstrip())
    while position < end:
        found = EXPRESSION_TOKEN.match(expression, position)
        assert found, f"the test cannot read {expression[position:]!r} in {expression!r}"
        tokens.append(found[1])
        position = found.end()
    tokens.append("")
    at = 0

    def take(*expected: str) -> str | None:
        nonlocal at
        if tokens[at] not in expected:
            return None
        at += 1
        return tokens[at - 1]

    def either() -> object:
        value = both()
        while take("||"):
            right = both()
            value = value if truthy(value) else right
        return value

    def both() -> object:
        value = comparison()
        while take("&&"):
            right = comparison()
            value = right if truthy(value) else value
        return value

    def comparison() -> object:
        value = negation()
        while operator := take("==", "!="):
            value = equal(value, negation()) == (operator == "==")
        return value

    def negation() -> object:
        return not truthy(negation()) if take("!") else operand()

    def operand() -> object:
        nonlocal at
        token = tokens[at]
        at += 1
        if token == "(":
            value = either()
            assert take(")"), f"a parenthesis left open in {expression!r}"
            return value
        if token in FUNCTIONS and take("("):
            argument = either()
            assert take(")"), f"a call left open in {expression!r}"
            return FUNCTIONS[token](argument)
        if token.startswith("'"):
            return token[1:-1].replace("''", "'")
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            return float(token)
        literals: dict[str, object] = {"true": True, "false": False, "null": None}
        if token in literals:
            return literals[token]
        assert token in context, f"the test does not know {token!r}, in {expression!r}"
        return context[token]

    value = either()
    assert tokens[at] == "", f"the test cannot read {expression!r} from {tokens[at]!r}"
    return value


def rendered(text: str, context: Mapping[str, object]) -> str:
    """`text` with each `${{ expression }}` replaced by its value; an expression the test cannot evaluate
    fails it, rather than run the step with a guess."""
    return re.sub(r"\$\{\{(.*?)\}\}", lambda match: as_text(evaluated(match[1], context)), text)


def condition(found: Mapping[str, Any]) -> str:
    """A job's or step's `if` as GitHub evaluates it: `success()` where there is none, and `success() &&`
    before one that calls no status function."""
    written = found.get("if", "success()")
    text = as_text(written) if isinstance(written, bool) else str(written)
    if wrapped := re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", text, re.S):
        text = wrapped[1]
    return text if STATUS_FUNCTION.search(text) else f"success() && ({text})"


def test_the_expressions_are_evaluated_as_github_evaluates_them() -> None:
    context = {
        "github.event_name": "push",
        "github.run_id": "7",
        "matrix.python": "3.15",
        "vars.cap": "",
        "vars.other": "10",
    }
    cases = {
        "github.event_name == 'PUSH'": True,
        "github.event_name != 'push'": False,
        "github.event_name == 'pull_request' && 'cancel' || github.run_id": "7",
        "github.event_name == 'push' && 'push' || github.run_id": "push",
        "!(matrix.python == '3.15') || null": None,
        "github.run_id == 7": True,
        "'it''s'": "it's",
        "fromJSON(vars.cap || '6')": 6,
        "fromJSON(vars.other || '6')": 10,
        "fromJSON('[\"a\", 2]')": ["a", 2],
    }
    assert {expression: evaluated(expression, context) for expression in cases} == cases
    assert condition({"if": "matrix.python != '3.15'"}) == "success() && (matrix.python != '3.15')"
    assert condition({"if": "${{ always() }}"}) == " always() "
    assert condition({}) == "success()"
    with pytest.raises(AssertionError, match=r"does not know 'github\.ref'"):
        evaluated("github.ref == 'refs/heads/main'", context)


# GitHub's command for a step's script under `shell: bash`, which each workflow sets as its default, the
# script's file last ("Workflow syntax for GitHub Actions", `jobs.<job_id>.steps[*].shell`).
GITHUB_BASH = ("bash", "--noprofile", "--norc", "-eo", "pipefail")


def github_outputs(text: str) -> tuple[dict[str, str], bool]:
    """The outputs a step wrote to `GITHUB_OUTPUT`, as the runner reads them on Linux, and whether it read
    them all. It splits at `\n` alone, skips an empty line, and sets each `name=value` in turn; at a line of
    another form it stops, keeping those it set, and fails the step (actions/runner, `EnvFileKeyValuePairs`).
    The heredoc form, `name<<delimiter`, which no workflow here writes, stops it here too, rather than be
    guessed."""
    outputs: dict[str, str] = {}
    for line in text.split("\n"):
        if not line:
            continue
        if "=" not in line or "<<" in line.split("=", 1)[0]:
            return outputs, False
        name, value = line.split("=", 1)
        outputs[name] = value
    return outputs, True


def test_the_outputs_are_read_as_the_runner_reads_them() -> None:
    assert github_outputs("a=1\n\nb=x=y\rz\n") == ({"a": "1", "b": "x=y\rz"}, True)
    assert github_outputs("a=1\n::warning::x\nb=2\n") == ({"a": "1"}, False)
    assert github_outputs("a<<EOF\n1\nEOF\n") == ({}, False)


def run_step(
    found: dict[str, Any],
    context: Mapping[str, object],
    cwd: Path,
    base: Mapping[str, str] = os.environ,
    scratch: Path | None = None,
) -> tuple[int, dict[str, str], str]:
    """The step's script run in `cwd` as GitHub runs it, from a file, with `GITHUB_BASH`, in the environment
    `base` with the step's own: its exit status, what it wrote to `GITHUB_OUTPUT`, and what it printed. The
    script and the outputs' file go in `scratch`, or beside `cwd`. Outputs the runner cannot read fail the
    step, as on GitHub (`github_outputs`)."""
    scratch = cwd.parent if scratch is None else scratch
    script = scratch / f"{cwd.name}.step.sh"
    script.write_text(rendered(found["run"], context), encoding="utf-8")
    outputs = scratch / f"{cwd.name}.github_output"
    outputs.write_text("", encoding="utf-8")
    environment = dict(base, GITHUB_OUTPUT=str(outputs))
    environment |= {name: rendered(str(value), context) for name, value in found.get("env", {}).items()}
    ran = subprocess.run(
        [*GITHUB_BASH, str(script)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    written, read = github_outputs(outputs.read_text(encoding="utf-8"))
    if not read:
        return ran.returncode or 1, written, f"{ran.stdout}{ran.stderr}\nthe runner cannot read GITHUB_OUTPUT"
    return ran.returncode, written, ran.stdout + ran.stderr


def shell_problems(loaded: dict[str, Workflow]) -> list[str]:
    """Where a workflow does not run its steps under `shell: bash`, the shell `run_step` runs them with."""
    problems: list[str] = []
    for name, found in loaded.items():
        if found.get("defaults") != {"run": {"shell": "bash"}}:
            problems.append(f"{name} has the defaults {found.get('defaults')!r}")
        for job_id, job in found["jobs"].items():
            if "defaults" in job:
                problems.append(f"{name}: {job_id} has defaults of its own")
            problems += [
                f"{name}: a step of {job_id} runs under {each['shell']!r}"
                for each in job.get("steps", [])
                if "shell" in each
            ]
    return problems


def test_every_step_runs_under_bash_with_pipefail(tmp_path: Path) -> None:
    assert shell_problems(workflows()) == []
    (tmp_path / "step").mkdir()
    status, _, _ = run_step({"run": "false | true"}, {}, tmp_path / "step")
    assert status == 1


@pytest.mark.parametrize(
    ("place", "problem"),
    [
        ("workflow", "pages.yml has the defaults None"),
        ("job", "ci.yml: static has defaults of its own"),
        ("step", "release.yml: a step of build runs under 'sh'"),
    ],
)
def test_the_shell_check_can_fail(place: str, problem: str) -> None:
    loaded = copy.deepcopy(workflows())
    if place == "workflow":
        del loaded["pages.yml"]["defaults"]
    elif place == "job":
        loaded["ci.yml"]["jobs"]["static"]["defaults"] = {"run": {"shell": "sh"}}
    else:
        loaded["release.yml"]["jobs"]["build"]["steps"][1]["shell"] = "sh"
    assert shell_problems(loaded) == [problem]


def gate_context(event: str, base: str = "", head: str = "", fuzz_only: str = "") -> dict[str, str]:
    return {
        "github.event_name": event,
        "inputs.fuzz_only": fuzz_only,
        "github.event.pull_request.base.sha": base,
        "github.event.pull_request.head.sha": head,
    }


def commit(*paths: str) -> str:
    """A commit that changes each of `paths`, or none."""
    for path in paths:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("a", encoding="utf-8") as changed:
            changed.write("changed\n")
        subprocess.run(["git", "add", path], check=True)
    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    subprocess.run(["git", *identity, "commit", "-q", "--allow-empty", "-m", "change"], check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def gate_outputs(
    repository: Path, context: dict[str, str], gate: dict[str, Any] | None = None
) -> dict[str, str]:
    """The gate's outputs that decide the jobs, once its workflow's blob is checked: on a pull request, that
    of the checkout's `ci.yml`, which the per-commit job's key carries; otherwise none."""
    status, outputs, printed = run_step(
        gate or step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP), context, repository
    )
    assert status == 0, printed
    blob = outputs.pop("workflow_blob")
    if context["github.event_name"] == "pull_request":
        written = subprocess.run(
            ["git", "hash-object", ".github/workflows/ci.yml"], capture_output=True, text=True, check=True
        )
        assert blob == written.stdout.strip()
    else:
        assert blob == ""
    return outputs


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "repository").mkdir()
    root = throwaway_repository(tmp_path / "repository", monkeypatch)
    commit("src/materica/core/read.py", "README.md", "CHANGELOG.md", ".github/workflows/ci.yml")
    return root


@pytest.mark.parametrize(
    ("event", "fuzz_only"),
    [("push", ""), ("schedule", ""), ("workflow_dispatch", "false")],
)
def test_a_merge_to_main_and_every_run_but_a_pull_request_run_every_job(
    repository: Path, event: str, fuzz_only: str
) -> None:
    """Whatever the merge changed: its diff says nothing of an earlier merge whose run did not finish."""
    commit("CHANGELOG.md")
    assert gate_outputs(repository, gate_context(event, fuzz_only=fuzz_only)) == {
        "code": "true",
        "hypothesis": "true",
        "site": "true",
        "commits": "[]",
        "site_commits": "[]",
    }


def test_a_manual_run_of_the_fuzz_job_alone_runs_no_other_job(repository: Path) -> None:
    assert gate_outputs(repository, gate_context("workflow_dispatch", fuzz_only="true")) == {
        "code": "false",
        "hypothesis": "false",
        "site": "false",
        "commits": "[]",
        "site_commits": "[]",
    }


@pytest.mark.parametrize(
    ("paths", "code", "hypothesis", "site"),
    [
        pytest.param(list(DOCUMENTATION_EXAMPLES), "false", "false", "false", id="documentation"),
        # Code, though written as documentation: what the wheel, the type checkers, the spec-sync tests and
        # the Pages workflow read. The Hypothesis job builds the wheel's metadata, and its properties read the
        # specification.
        (["README.md"], "true", "true", "true"),
        (["LICENSE"], "true", "true", "true"),
        (["typings/atheris/__init__.pyi"], "true", "false", "true"),
        (["docs/specification/README.md"], "true", "true", "true"),
        # The freeze manifest is code: the site job's index writer reads it, so the freezing commit, which
        # changes it alone, runs the site job beside the code's.
        (["tests/spec_sync/released_schemas.json"], "true", "true", "true"),
        # The site's own paths: the site job alone, beside documentation too; with code, every job.
        (["site/index.html"], "false", "false", "true"),
        (["assets/images/logo.png", "CHANGELOG.md"], "false", "false", "true"),
        (["site/index.html", "scripts/schema_index.py"], "true", "false", "true"),
        (["design/ARCHITECTURE_DRAFT.md", ".github/workflows/pages.yml"], "true", "false", "true"),
        (["scripts/pre-push", "scripts/check_confidential.py"], "true", "false", "true"),
        # A path nobody listed is code, and runs the Hypothesis job; one path of either makes a change so.
        (["notes/plan.txt"], "true", "true", "true"),
        (["CHANGELOG.md", "scripts/check_wheel.py"], "true", "false", "true"),
        (["scripts/check_wheel.py", "scripts/new_tool.py"], "true", "true", "true"),
        # A Python file is code wherever it sits, since ruff reads it; no part of the Hypothesis job does. The
        # site job runs too, as for any change but documentation alone.
        (["docs/validation/make_table.py"], "true", "false", "true"),
        (["CHANGELOG.md", ".github/ISSUE_TEMPLATE/form.pyi"], "true", "false", "true"),
        (["site/make_icons.py"], "true", "false", "true"),
        (["assets/images/make.pyi", "site/index.html"], "true", "false", "true"),
        # A diff with no path at all, as if the diff had gone wrong: the safe side.
        ([], "true", "true", "true"),
        # What the Hypothesis job reads, though no property: the conformance runner, the read's modules, a
        # generator, its durations step's script, and any test, whose source one property test reads.
        (["tests/conformance/runner.py"], "true", "true", "true"),
        (["src/materica/io/plain.py"], "true", "true", "true"),
        (["scripts/gen_reader_schema.py"], "true", "true", "true"),
        (["scripts/report_test_durations.py"], "true", "true", "true"),
        (["tests/unit/test_read.py"], "true", "true", "true"),
        (["src/materica/core/read.py"], "true", "true", "true"),
    ],
    ids=lambda value: "+".join(cast(list[str], value)) or "nothing" if isinstance(value, list) else None,
)
def test_a_pull_request_runs_the_jobs_its_paths_need(
    repository: Path, paths: list[str], code: str, hypothesis: str, site: str
) -> None:
    base = commit()
    head = commit(*paths)
    assert gate_outputs(repository, gate_context("pull_request", base, head)) == {
        "code": code,
        "hypothesis": hypothesis,
        "site": site,
        "commits": "[]",
        "site_commits": "[]",
    }


HYPOTHESIS_LINE = 'if [ -n "$changed" ] && ! grep -qvxE "$docs_paths|$hypothesis_free" <<< "$changed"; then'


def test_without_failing_closed_the_gate_skips_the_hypothesis_job_for_a_path_it_does_not_name(
    repository: Path,
) -> None:
    """The control of the cases above: the gate as it was, a list of what reaches a property, skips the job
    for the conformance runner, which every shard loads, and for a path nobody listed."""
    gate = copy.deepcopy(step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP))
    assert gate["run"].count(HYPOTHESIS_LINE) == 1
    listing_code = "src/materica/core/|tests/property/"
    gate["run"] = gate["run"].replace(
        HYPOTHESIS_LINE, f'if ! grep -qE "^({listing_code})" <<< "$changed"; then'
    )
    for paths in (["tests/conformance/runner.py"], ["notes/plan.txt"]):
        base = commit()
        head = commit(*paths)
        assert (
            gate_outputs(repository, gate_context("pull_request", base, head), gate)["hypothesis"] == "false"
        )
    base = commit()
    head = commit("src/materica/core/read.py")
    assert gate_outputs(repository, gate_context("pull_request", base, head), gate)["hypothesis"] == "true"


@pytest.mark.parametrize(
    ("source", "destination", "also", "hypothesis"),
    [
        ("src/materica/core/read.py", "docs/regulatory/read.py", (), "true"),
        ("src/materica/core/read.py", "docs/validation/read.py", ("CHANGELOG.md",), "true"),
        ("tests/unit/test_read.py", "docs/validation/test_read.py", (), "true"),
        ("tests/unit/test_read.py", ".github/ISSUE_TEMPLATE/test_read.py", (), "true"),
        ("src/materica/core/read.py", "site/read.py", (), "true"),
    ],
    ids=[
        "core-into-regulatory",
        "core-into-validation-beside-the-changelog",
        "test-into-validation",
        "test-into-the-issue-templates",
        "core-into-the-site",
    ],
)
def test_a_pull_request_that_moves_code_into_documentation_runs_the_jobs_of_the_code(
    repository: Path, source: str, destination: str, also: tuple[str, ...], hypothesis: str
) -> None:
    """git gives a file moved whole as a rename, under where it went alone: a module moved into a path the
    gate lists is still code taken away."""
    base = commit(source)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", source, destination], check=True)
    head = commit(*also)
    assert gate_outputs(repository, gate_context("pull_request", base, head)) == {
        "code": "true",
        "hypothesis": hypothesis,
        "site": "true",
        "commits": "[]",
        "site_commits": "[]",
    }


def listed(repository: Path, base: str, head: str) -> list[str]:
    """The commits the gate gives the per-commit job for a pull request from `base` to `head`."""
    commits: list[str] = json.loads(
        gate_outputs(repository, gate_context("pull_request", base, head))["commits"]
    )
    return commits


def test_each_commit_but_the_head_is_listed_oldest_first(repository: Path) -> None:
    """Code that is not Python too, which the Python rule does not list."""
    base = commit()
    first = commit("src/materica/core/read.py")
    second = commit("tests/unit/test_read.py")
    third = commit("src/materica/schema/0.1/record.writer.json")
    head = commit("scripts/check_wheel.py")
    assert listed(repository, base, head) == [first, second, third]


def test_a_pull_request_of_one_commit_lists_none(repository: Path) -> None:
    base = commit()
    head = commit("src/materica/core/read.py")
    assert listed(repository, base, head) == []


def test_a_commit_that_changes_documentation_or_the_site_alone_is_not_listed(repository: Path) -> None:
    """Its tree is its parent's but for paths no test reads; README.md is code. One that changes the site is
    listed for the site's checks alone."""
    base = commit()
    commit("CHANGELOG.md", "docs/regulatory/intended_use.md")
    code = commit("README.md")
    beside = commit("CONTRIBUTING.md", "site/index.html")
    alone = commit("assets/images/logo.png")
    python = commit("site/make_icons.py")
    head = commit("CHANGELOG.md")
    outputs = gate_outputs(repository, gate_context("pull_request", base, head))
    assert (json.loads(outputs["commits"]), json.loads(outputs["site_commits"])) == (
        [code, python],
        [beside, alone],
    )


def test_a_commit_that_adds_a_python_file_to_documentation_is_listed(repository: Path) -> None:
    """ruff reads it, as every Python file."""
    base = commit()
    python = commit("docs/validation/make_table.py")
    head = commit("CHANGELOG.md")
    assert listed(repository, base, head) == [python]


def test_without_its_python_rule_the_gate_skips_the_code_jobs_for_a_python_file_in_documentation(
    repository: Path,
) -> None:
    """The control of the cases above: the gate without `python_paths` calls the file documentation."""
    gate = copy.deepcopy(step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP))
    python_rules = (
        '! grep -qxE "$python_paths" <<< "$changed" && ',
        'grep -qxE "$python_paths" <<< "$own" || ',
    )
    for rule in python_rules:
        assert rule in gate["run"]
        gate["run"] = gate["run"].replace(rule, "")
    base = commit()
    head = commit("docs/validation/make_table.py")
    outputs = gate_outputs(repository, gate_context("pull_request", base, head), gate)
    assert outputs["code"] == "false"


RUFF_INCLUDE = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"][
    "include"
]


def python_problems(include: list[str], pattern: str) -> list[str]:
    """Where a file ruff's `include` matches, at the root or in a directory the gate lists, is not code to the
    gate."""
    places = sorted(
        {f"{Path(example).parent.as_posix()}/".removeprefix("./") for example in DOCUMENTATION_EXAMPLES}
    )
    return [
        f"ruff reads {place}{glob}, which the gate's python_paths does not match"
        for glob in include
        for place in places
        if not re.fullmatch(pattern, place + glob.replace("*", "x"))
    ]


def test_every_file_ruff_reads_is_code_to_the_gate() -> None:
    assert python_problems(RUFF_INCLUDE, gate_pattern("python_paths")) == []


def test_the_python_check_can_fail() -> None:
    assert python_problems([*RUFF_INCLUDE, "*.ipynb"], gate_pattern("python_paths"))[0] == (
        "ruff reads *.ipynb, which the gate's python_paths does not match"
    )


def test_a_commit_that_changes_nothing_is_listed(repository: Path) -> None:
    """As a diff that names no path is code."""
    base = commit()
    empty = commit()
    head = commit("CHANGELOG.md")
    assert listed(repository, base, head) == [empty]


def test_a_commit_of_code_the_pull_request_undoes_is_listed_though_its_diff_is_documentation(
    repository: Path,
) -> None:
    """The pull request's diff runs no job, yet the commit that added code would land with it."""
    base = commit()
    added = commit("src/materica/core/new.py", "CHANGELOG.md")
    subprocess.run(["git", "rm", "-q", "src/materica/core/new.py"], check=True)
    head = commit()
    outputs = gate_outputs(repository, gate_context("pull_request", base, head))
    decided = (outputs["code"], outputs["hypothesis"], outputs["site"], json.loads(outputs["commits"]))
    assert decided == ("false", "false", "false", [added])


def test_after_a_force_push_the_commits_the_branch_holds_now_are_listed(repository: Path) -> None:
    base = commit()
    first = commit("src/materica/core/a.py")
    commit("src/materica/core/b.py")
    commit("src/materica/core/c.py")
    subprocess.run(["git", "reset", "-q", "--hard", first], check=True)
    rewritten = commit("src/materica/core/b.py")
    head = commit("src/materica/core/c.py")
    assert listed(repository, base, head) == [first, rewritten]


def test_more_site_commits_than_a_matrix_holds_fail_the_gate(repository: Path) -> None:
    base = commit()
    for _ in range(257):
        commit("site/index.html")
    head = commit()
    gate = step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP)
    status, _, printed = run_step(gate, gate_context("pull_request", base, head), repository)
    assert status == 1
    assert (
        "::error::257 commits to check on their own in one job, more than the 256 jobs of a matrix" in printed
    )


def test_more_commits_than_a_matrix_holds_fail_the_gate(repository: Path) -> None:
    """GitHub makes at most 256 jobs of a matrix; a run that left commits out would pass without them."""
    base = commit()
    for _ in range(256):
        commit()
    head = commit()
    assert len(listed(repository, base, head)) == 256
    head = commit()
    gate = step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP)
    status, _, printed = run_step(gate, gate_context("pull_request", base, head), repository)
    assert status == 1
    assert (
        "::error::257 commits to check on their own in one job, more than the 256 jobs of a matrix" in printed
    )


def printed_with_commands_stopped(printed: str, name: str) -> bool:
    """Whether `name` is printed with GitHub's workflow commands stopped, by a token that is not guessed."""
    lines = printed.splitlines()
    at = lines.index(name)
    stopped = re.fullmatch(r"::stop-commands::(\w{32,})", lines[at - 1]) if at else None
    return stopped is not None and f"::{stopped[1]}::" in lines[at + 1 :]


def test_the_gate_prints_the_paths_of_a_pull_request_with_workflow_commands_stopped(repository: Path) -> None:
    """A path a pull request names, printed as it is, would be read as a workflow command (`::error::...`)."""
    base = commit()
    head = commit("./::warning::a name.md")  # `./`, or git reads `:` as the start of a pathspec's magic
    gate = step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP)
    status, _, printed = run_step(gate, gate_context("pull_request", base, head), repository)
    assert status == 0, printed
    assert printed_with_commands_stopped(printed, "::warning::a name.md"), printed
    # The control: the same step without its two lines that stop and restart the commands.
    gate["run"], removed = re.subn(r'.*echo "::(stop-commands::)?\$stop(::)?"\n', "", gate["run"])
    assert removed == 2
    _, _, printed_unstopped = run_step(gate, gate_context("pull_request", base, head), repository)
    assert not printed_with_commands_stopped(printed_unstopped, "::warning::a name.md"), printed_unstopped


SCAN_STEP = "No private name or path in the tracked files or the commit messages"


@pytest.mark.parametrize(("branch", "status"), [("zorblax-support", 1), ("docs-fix", 0)])
def test_the_gate_scans_a_pull_requests_branch_name(repository: Path, branch: str, status: int) -> None:
    """A branch's name is public from its push, and no tracked file or message holds it. The gate's scan, run
    as GitHub runs it, with the repository's scan, a scratch key and a scratch term, refuses a branch that
    names the term; the control, a plain name, passes."""
    key = bytes(range(32))
    Path("scripts").mkdir()
    shutil.copy(REPOSITORY / "scripts" / "check_confidential.py", "scripts/check_confidential.py")
    Path("scripts/confidential_digests.txt").write_text(
        check_confidential.digest_file(key, ["Zorblax"]), encoding="utf-8"
    )
    subprocess.run(["git", "add", "scripts"], check=True)
    base = commit()
    head = commit("src/materica/core/read.py")
    context = gate_context("pull_request", base, head) | {
        "secrets.CONFIDENTIAL_SCAN_KEY": key.hex(),
        "github.event.before": "",
        "github.sha": head,
        "github.head_ref": branch,
    }
    ran, _, printed = run_step(step(workflow("ci.yml")["jobs"]["gate"], SCAN_STEP), context, repository)
    assert ran == status, printed
    assert ("ref zorblax-support:1: a confidential term (z..., 7 characters)" in printed) == bool(status)


def gate_pattern(variable: str, ci: Workflow | None = None) -> str:
    """A pattern of paths the gate's step sets, as the step's shell variable `variable`, matched whole."""
    gate = step((ci or workflow("ci.yml"))["jobs"]["gate"], GATE_STEP)
    found = re.search(rf"^ *{variable}='([^']+)'$", gate["run"], re.M)
    assert found, f"the gate's step sets no {variable}"
    return found[1]


def documentation_pattern() -> str:
    """The gate's pattern of the paths that are documentation only (`docs_paths`), matched whole."""
    return gate_pattern("docs_paths")


def checkout_files() -> list[str]:
    """Every file of the checkout but those of git and of the virtual environment: an export of a commit has
    no `.git/` to list the tracked files."""
    files: list[str] = []
    for directory, subdirectories, names in os.walk(REPOSITORY):
        subdirectories[:] = [name for name in subdirectories if name not in {".git", ".venv"}]
        files += [(Path(directory) / name).relative_to(REPOSITORY).as_posix() for name in names]
    return files


# The wildcards of a glob, as `Path.glob` reads them.
WILDCARD = re.compile(r"(\*\*/|\*\*|\*|\?|\[[^\]]*\])")
GLOBBING = {"glob", "rglob", "iglob"}


def named_paths(source: str) -> set[str]:
    """What a Python module could name a path by: each string, each run of strings joined by `/`, as in
    `REPOSITORY / "docs" / "specification"`, and each glob a call of `glob` or `rglob` is given, as in
    `ROOT.glob("*.md")`; a string with wildcards that no glob is given is a pattern of another kind.

    Each source is parsed once: each caller gets a set of its own, since callers change it."""
    return set(_named_paths(source))


@functools.cache
def _named_paths(source: str) -> frozenset[str]:
    names: set[str] = set()
    in_a_join: set[int] = set()
    globs: set[int] = set()

    def operands(node: ast.expr) -> list[ast.expr]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            in_a_join.add(id(node))
            return operands(node.left) + operands(node.right)
        return [node]

    # ast.walk reaches a join before its parts, so that a part joined is not also taken alone, and a call
    # before its arguments.
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and node.args:
            if isinstance(node.func, ast.Attribute) and node.func.attr in GLOBBING:
                globs.add(id(node.args[0]))
            if isinstance(node.func, ast.Name) and node.func.id in GLOBBING:
                globs.add(id(node.args[0]))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and id(node) not in in_a_join:
            run: list[str] = []
            for operand in [*operands(node), None]:
                if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                    in_a_join.add(id(operand))
                    run.append(operand.value)
                elif run:
                    names.add("/".join(run))
                    run = []
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in in_a_join:
            if id(node) in globs or not WILDCARD.search(node.value):
                names.add(node.value)
    return frozenset(names)


def strings(value: object) -> set[str]:
    """Every string in a parsed TOML document."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return strings(list(cast(dict[str, object], value).values()))
    if isinstance(value, list):
        return {found for item in cast(list[object], value) for found in strings(item)}
    return set()


def readers() -> dict[str, set[str]]:
    """What each test and script, and the build (`pyproject.toml`), could name a path by."""
    modules = sorted(
        path for directory in ("tests", "scripts") for path in (REPOSITORY / directory).rglob("*.py")
    )
    found = {
        path.relative_to(REPOSITORY).as_posix(): named_paths(path.read_text("utf-8")) for path in modules
    }
    found["pyproject.toml"] = strings(tomllib.loads((REPOSITORY / "pyproject.toml").read_text("utf-8")))
    return found


def names(name: str, path: str) -> bool:
    """Whether `name` can mean `path`: the path, its end (`intended_use.md`), or a directory it is in; and a
    glob (`*.md`), each path it matches from any directory, since a glob's directory is not in the string."""
    name = name.removeprefix("./").strip("/")
    if WILDCARD.search(name):
        wildcards = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*", "?": "[^/]"}
        pieces = [
            wildcards.get(piece, "[^/]" if piece.startswith("[") else re.escape(piece))
            for piece in WILDCARD.split(name)
        ]
        return re.search("(?:^|/)" + "".join(pieces) + "$", path) is not None
    return bool(name) and (path == name or path.endswith(f"/{name}") or path.startswith(f"{name}/"))


# Where a test or script names documentation without reading it, and why.
NAMED_NOT_READ = {
    (
        "scripts/check_confidential.py",
        "CLAUDE.md",
    ): "the gate runs the scan on every change, documentation included",
    (
        "tests/unit/test_check_confidential.py",
        "CLAUDE.md",
    ): "a key of the scan's allowed paths, over text it writes",
    # Globs, each in a directory that holds no documentation.
    (
        "scripts/pre_review.py",
        "CHANGELOG.md",
    ): "the lines a branch adds to it, read from git for the counts they state; no test takes it as input",
    (
        "tests/unit/test_pre_review.py",
        "CHANGELOG.md",
    ): "a path the selection tests pass as a changed file, and one a throwaway repository commits",
    (
        "tests/unit/test_pre_review.py",
        "CONTRIBUTING.md",
    ): "a path the selection tests pass as a changed file, as the gate's tests do",
    ("scripts/check_wheel.py", "*"): "the files of the wheel it unpacks",
    ("scripts/freeze_schema.py", "*"): "the files of a schema version",
    ("scripts/schema_index.py", "*"): "the directories of the published schemas",
    ("tests/unit/test_freeze_schema.py", "*"): "the files of a frozen schema version",
    ("tests/unit/test_schema_index.py", "*"): "the schema directory",
    ("tests/spec_sync/name_overlaps.py", "*.md"): "the specification's documents, in docs/specification/",
    ("tests/spec_sync/test_references.py", "*.md"): "the specification's documents, in docs/specification/",
    # The directory a patch may not touch, in the script's list of them and in this exemption's own key.
    ("scripts/mutant_runs.py", ".github"): "a patch that touches it is refused; nothing there is read",
    ("tests/unit/test_ci_workflows.py", ".github"): "the key of the exemption above",
} | {
    ("tests/unit/test_ci_workflows.py", example): "a path the gate's tests commit in a throwaway repository"
    for example in DOCUMENTATION_EXAMPLES
}


def documentation_named(
    pattern: str,
    files: list[str],
    named: dict[str, set[str]],
    exempt: Mapping[tuple[str, str], str] = NAMED_NOT_READ,
    kind: str = "documentation",
) -> list[str]:
    """Each place a test, a script or the build names a path that `pattern` calls `kind`, but those `exempt`
    gives; and each of those it no longer finds."""
    documentation = [path for path in files if re.fullmatch(pattern, path)]
    found = {
        (reader, name, path)
        for reader, names_there in named.items()
        for name in names_there
        for path in documentation
        if names(name, path)
    }
    problems = [
        f"{reader} names {path} as {name!r}, and the gate calls it {kind}"
        for reader, name, path in sorted(found)
        if (reader, name) not in exempt
    ]
    still_named = {(reader, name) for reader, name, _ in found}
    return problems + [
        f"{reader} no longer names {name!r}" for reader, name in sorted(exempt.keys() - still_named)
    ]


def test_no_test_or_script_names_a_path_the_gate_calls_documentation() -> None:
    """A change to a path the gate calls documentation runs no test: so no test may read it."""
    assert documentation_named(documentation_pattern(), checkout_files(), readers()) == []


@pytest.mark.parametrize(
    ("listed", "reader", "source", "problem"),
    [
        # Documentation the code reads: the wheel's readme, and the specification by its parts.
        ("|README\\.md", None, None, "pyproject.toml names README.md as 'README.md'"),
        ("|docs/specification/.+", None, None, "scripts/gen_vocabulary.py names docs/specification/"),
        # A test or script that reads a path the gate lists.
        ("", "scripts/notes.py", 'Path("CHANGELOG.md").read_text()', "scripts/notes.py names CHANGELOG.md"),
        (
            "",
            "tests/unit/test_notes.py",
            'ROOT / "docs" / "regulatory"',
            "names docs/regulatory/intended_use.md",
        ),
        (
            "",
            "tests/unit/test_notes.py",
            'f"{ROOT}/SECURITY.md"',
            "tests/unit/test_notes.py names SECURITY.md",
        ),
        ("", "tests/unit/test_notes.py", 'ROOT.glob("*.md")', "test_notes.py names CHANGELOG.md as '*.md'"),
        (
            "",
            "scripts/notes.py",
            'sorted(ROOT.rglob("**/*.yaml"))',
            "scripts/notes.py names docs/validation/known_anomalies.yaml as '**/*.yaml'",
        ),
    ],
    ids=[
        "readme",
        "specification",
        "a-script",
        "a-joined-directory",
        "an-f-string",
        "a-glob",
        "a-recursive-glob",
    ],
)
def test_the_documentation_check_can_fail(
    listed: str, reader: str | None, source: str | None, problem: str
) -> None:
    named = readers()
    if reader is not None and source is not None:
        named[reader] = named_paths(source)
    found = documentation_named(documentation_pattern() + listed, checkout_files(), named)
    assert any(problem in line for line in found), found


def test_the_documentation_check_finds_an_exemption_gone_stale() -> None:
    named = readers()
    named["scripts/check_confidential.py"].discard("CLAUDE.md")
    assert documentation_named(documentation_pattern(), checkout_files(), named) == [
        "scripts/check_confidential.py no longer names 'CLAUDE.md'"
    ]


# Where a test or script names a path of the site's own (`site_paths`), which no code job reads, and why: the
# site job runs whatever reads them, and the gate runs it on every change to them.
SITE_NAMED_NOT_READ = {
    ("scripts/check_site.py", "site"): "the name of its argument, the staged copy it checks",
    ("scripts/check_site.py", "index.html"): "a directory's page, in the staged copy it checks",
    ("scripts/schema_index.py", "index.html"): "the pages it writes into the staged schemas, for Pages",
    ("tests/unit/test_check_site.py", "site"): "a copy of a site it writes in tmp_path",
    ("tests/unit/test_check_site.py", "logo.png"): "an image of a copy it writes in tmp_path",
    ("tests/unit/test_schema_index.py", "index.html"): "the pages schema_index.py writes in tmp_path",
    ("tests/unit/test_ci_workflows.py", "site"): "the site job's name",
    ("tests/unit/test_ci_workflows.py", "index.html"): "a name in this table",
    ("tests/unit/test_ci_workflows.py", "logo.png"): "a name in this table",
    (
        "tests/unit/test_ci_workflows.py",
        "site/index.html",
    ): "a path the gate's tests commit in a throwaway repository",
    ("tests/unit/test_ci_workflows.py", "assets/images/logo.png"): (
        "a path the gate's tests commit in a throwaway repository"
    ),
} | {
    # Globs, each in a directory that holds no path of the site, as for the documentation.
    (reader, name): reason
    for (reader, name), reason in NAMED_NOT_READ.items()
    if name == "*"
}


def site_named(pattern: str, named: dict[str, set[str]]) -> list[str]:
    return documentation_named(pattern, checkout_files(), named, SITE_NAMED_NOT_READ, "the site's")


def test_no_test_or_script_names_a_path_of_the_site_but_those_the_site_job_runs() -> None:
    """A change to the site alone runs the site job and no test: so no test may read the site, and only the
    site check and the Pages workflow's index writer, which the site job runs, name its paths."""
    assert site_named(gate_pattern("site_paths"), readers()) == []


@pytest.mark.parametrize(
    ("reader", "source", "problem"),
    [
        ("scripts/notes.py", 'Path("site/index.html").read_text()', "scripts/notes.py names site/index.html"),
        (
            "tests/unit/test_notes.py",
            'ROOT / "assets" / "images"',
            "names assets/images/logo.png as 'assets/images'",
        ),
        ("tests/unit/test_notes.py", 'ROOT.glob("*.html")', "test_notes.py names site/404.html as '*.html'"),
    ],
    ids=["a-page", "a-joined-directory", "a-glob"],
)
def test_the_site_check_of_the_gate_can_fail(reader: str, source: str, problem: str) -> None:
    named = readers() | {reader: named_paths(source)}
    found = site_named(gate_pattern("site_paths"), named)
    assert any(problem in line for line in found), found


def test_the_site_check_of_the_gate_finds_an_exemption_gone_stale() -> None:
    named = readers()
    named["scripts/schema_index.py"].discard("index.html")
    assert site_named(gate_pattern("site_paths"), named) == [
        "scripts/schema_index.py no longer names 'index.html'"
    ]


# Collecting the property tests as CI's Hypothesis job does, the files of every module then loaded.
LOADED_MODULES_PLUGIN = """
import json, os, sys


def pytest_collection_finish(session):
    files = {getattr(module, "__file__", None) for module in list(sys.modules.values())}
    with open(os.environ["LOADED_MODULES"], "w", encoding="utf-8") as written:
        json.dump(sorted(name for name in files if name), written)
"""
COLLECTING_PLUGINS = ("-p", "no:cacheprovider", "-p", "loaded_modules")
# Where the repository's modules are imported from: the root (`tests`, `scripts`) and `src/` (`materica`).
IMPORT_ROOTS = (REPOSITORY, REPOSITORY / "src")


def module_files(name: str) -> set[str]:
    """The repository's files that importing the module `name` runs: each package's `__init__.py` on the way,
    and the module's own file."""
    found: set[str] = set()
    parts = name.split(".")
    for root in IMPORT_ROOTS:
        for end in range(1, len(parts) + 1):
            base = root.joinpath(*parts[:end])
            for candidate in (base / "__init__.py", base.with_suffix(".py")):
                if candidate.is_file():
                    found.add(candidate.relative_to(REPOSITORY).as_posix())
    return found


def imported(path: str, source: str) -> set[str]:
    """The repository's files that `source`, the module at `path`, imports anywhere in it, a function's body
    included, each `from` import tried as a module too, since `from package import name` may import one."""
    package = list(Path(path).parent.parts)
    if package[:1] == ["src"]:
        package = package[1:]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found |= module_files(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            module = ".".join([*base, *([node.module] if node.module else [])])
            found |= module_files(module)
            for alias in node.names:
                found |= module_files(f"{module}.{alias.name}" if module else alias.name)
    return found


def with_imports(sources: dict[str, str]) -> dict[str, str]:
    """`sources`, the modules by path, with every module of the repository they import, however deep, read
    from the checkout."""
    found = dict(sources)
    unread = list(found)
    while unread:
        path = unread.pop()
        for module in sorted(imported(path, found[path]) - found.keys()):
            found[module] = (REPOSITORY / module).read_text("utf-8")
            unread.append(module)
    return found


def hypothesis_job_modules(tmp_path: Path) -> dict[str, str]:
    """Each module of the repository that the Hypothesis job runs, by path: those its collection of the
    property tests loads, and every module they import, wherever in them, which a test may import late."""
    (tmp_path / "loaded_modules.py").write_text(LOADED_MODULES_PLUGIN, encoding="utf-8")
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    environment["PYTHONPATH"] = os.pathsep.join([str(tmp_path), environment.get("PYTHONPATH", "")])
    environment["LOADED_MODULES"] = str(tmp_path / "loaded.json")
    ran = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/property", "--collect-only", "-q", *COLLECTING_PLUGINS],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, (ran.stdout + ran.stderr)[-3000:]
    loaded = [Path(name).resolve() for name in json.loads((tmp_path / "loaded.json").read_text("utf-8"))]
    return with_imports(
        {
            path.relative_to(REPOSITORY).as_posix(): path.read_text("utf-8")
            for path in loaded
            if path.is_relative_to(REPOSITORY) and ".venv" not in path.relative_to(REPOSITORY).parts
        }
    )


def step_words(job: dict[str, Any]) -> set[str]:
    """What a job's steps could name a path by: each word of their scripts and of their actions' inputs that
    holds a `/` or a `.`."""
    texts = [str(found.get("run", "")) for found in job["steps"]]
    texts += [str(value) for found in job["steps"] for value in found.get("with", {}).values()]
    return {
        word.strip("\"'") for text in texts for word in re.split(r"[\s=]+", text) if re.search(r"[/.]", word)
    }


def build_reads(path: str) -> bool:
    """Whether `uv sync` reads `path` to install the project: pyproject.toml, its readme and licence files,
    the lock file, or the package's sources."""
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text("utf-8"))["project"]
    files = {"pyproject.toml", "uv.lock", project["readme"], *project["license-files"]}
    return path in files or path.startswith("src/")


# Where a module the Hypothesis job runs names a path the gate lets it skip, but does not read it, and why.
HYPOTHESIS_NAMED_NOT_READ = {
    (
        "tests/property/test_validators_agree.py",
        "*.py",
    ): "a glob over tests/, for the modules that take a verdict from one JSON Schema library alone",
    # Loaded through tests/property/test_condition_mutants.py, which takes two of its tables.
    ("tests/unit/test_read.py", "*.py"): "a glob over src/materica/core/, for the core's modules",
}


def hypothesis_reads(pattern: str, files: list[str], modules: dict[str, str], ci: Workflow) -> list[str]:
    """Each path that `pattern` lets the Hypothesis job skip, but which the job reads: a module it runs, a
    path such a module names (but those `HYPOTHESIS_NAMED_NOT_READ` gives), a path its steps name, its build's
    inputs or this workflow; and each exemption no longer found."""
    listed = [path for path in files if re.fullmatch(pattern, path)]
    problems = [
        f"the Hypothesis job runs {path}, which the gate lets it skip"
        for path in sorted(modules)
        if path in listed
    ]
    found = {
        (module, name, path)
        for module, source in sorted(modules.items())
        for name in named_paths(source)
        for path in listed
        if names(name, path)
    }
    problems += [
        f"{module}, which the Hypothesis job runs, names {path} as {name!r}, which the gate lets it skip"
        for module, name, path in sorted(found)
        if (module, name) not in HYPOTHESIS_NAMED_NOT_READ
    ]
    still = {(module, name) for module, name, _ in found}
    problems += [
        f"{module} no longer names {name!r}"
        for module, name in sorted(HYPOTHESIS_NAMED_NOT_READ.keys() - still)
    ]
    problems += [
        f"the Hypothesis job's steps name {path} as {word!r}, which the gate lets it skip"
        for word in sorted(step_words(ci["jobs"]["hypothesis"]))
        for path in listed
        if names(word, path)
    ]
    problems += [
        f"the Hypothesis job's build reads {path}, which the gate lets it skip"
        for path in listed
        if build_reads(path)
    ]
    if re.fullmatch(pattern, ".github/workflows/ci.yml"):
        problems.append("the gate lets the Hypothesis job skip a change to its own workflow")
    return problems


@pytest.fixture(scope="module")
def hypothesis_modules(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return hypothesis_job_modules(tmp_path_factory.mktemp("hypothesis_modules"))


def hypothesis_pattern(ci: Workflow, also: str = "") -> str:
    """The paths the gate lets the Hypothesis job skip: the documentation, and those it lists beside."""
    return f"{documentation_pattern()}|{gate_pattern('hypothesis_free', ci)}{also}"


def test_no_path_the_gate_lets_the_hypothesis_job_skip_is_one_it_reads(
    hypothesis_modules: dict[str, str],
) -> None:
    """The gate skips the Hypothesis job only for paths it lists, and so must list none the job reads."""
    ci = workflow("ci.yml")
    assert hypothesis_reads(hypothesis_pattern(ci), checkout_files(), hypothesis_modules, ci) == []
    # The modules are found: the property tests', and those they load though no property.
    assert {
        "tests/property/test_writer_properties.py",
        "tests/conformance/runner.py",
        "scripts/gen_reader_schema.py",
        "src/materica/io/plain.py",
    } <= hypothesis_modules.keys()


@pytest.mark.parametrize(
    ("listed", "problem"),
    [
        ("tests/conformance/.+", "the Hypothesis job runs tests/conformance/runner.py"),
        ("scripts/gen_vocabulary\\.py", "the Hypothesis job runs scripts/gen_vocabulary.py"),
        (
            "docs/specification/.+",
            "value_fields.py, which the Hypothesis job runs, names docs/specification/",
        ),
        (
            "tests/spec_sync/case_steps\\.json",
            "runner.py, which the Hypothesis job runs, names tests/spec_sync/case_steps.json",
        ),
        (
            "scripts/report_test_durations\\.py",
            "the Hypothesis job's steps name scripts/report_test_durations.py",
        ),
        ("README\\.md", "the Hypothesis job's build reads README.md"),
        ("LICENSE", "the Hypothesis job's build reads LICENSE"),
        ("src/materica/schema/.+", "the Hypothesis job's build reads src/materica/schema/"),
        ("\\.github/workflows/ci\\.yml", "skip a change to its own workflow"),
    ],
    ids=[
        "a-loaded-module",
        "an-imported-script",
        "a-named-document",
        "a-named-file",
        "a-steps-script",
        "the-readme",
        "the-licence",
        "the-package",
        "the-workflow",
    ],
)
def test_the_hypothesis_check_can_fail(hypothesis_modules: dict[str, str], listed: str, problem: str) -> None:
    ci = workflow("ci.yml")
    found = hypothesis_reads(hypothesis_pattern(ci, f"|{listed}"), checkout_files(), hypothesis_modules, ci)
    assert any(problem in line for line in found), found


def test_the_hypothesis_check_finds_a_module_imported_late(hypothesis_modules: dict[str, str]) -> None:
    """The control of the imports: a property module that imports, in a test's body, a script the gate lets
    the job skip, which collecting the module does not load; and each form of import."""
    late = "def test_later():\n    from scripts import check_wheel\n"
    modules = with_imports(hypothesis_modules | {"tests/property/test_late.py": late})
    ci = workflow("ci.yml")
    found = hypothesis_reads(hypothesis_pattern(ci), checkout_files(), modules, ci)
    assert "the Hypothesis job runs scripts/check_wheel.py, which the gate lets it skip" in found, found
    forms = "import scripts.freeze_schema\nfrom . import strategies\nfrom ..conformance import runner\n"
    assert imported("tests/property/test_late.py", forms) == {
        "scripts/__init__.py",
        "scripts/freeze_schema.py",
        "tests/__init__.py",
        "tests/property/__init__.py",
        "tests/property/strategies.py",
        "tests/conformance/__init__.py",
        "tests/conformance/runner.py",
    }


def test_the_hypothesis_check_finds_an_exemption_gone_stale(hypothesis_modules: dict[str, str]) -> None:
    ci = workflow("ci.yml")
    modules = {path: source for path, source in hypothesis_modules.items() if "validators_agree" not in path}
    assert hypothesis_reads(hypothesis_pattern(ci), checkout_files(), modules, ci) == [
        "tests/property/test_validators_agree.py no longer names '*.py'"
    ]


SITE_STEP = "Stage site/, with the logo and favicons at its root and the schemas at /schema/"


def staging_step(name: str, job: str) -> dict[str, Any]:
    return step(workflow(name)["jobs"][job], SITE_STEP)


def test_the_site_job_stages_the_site_as_the_pages_workflow_does() -> None:
    """Word for word, so that what the site job checks is what Pages will serve."""
    assert staging_step("ci.yml", "site") == staging_step("pages.yml", "deploy")


def test_the_staging_check_can_fail() -> None:
    pages = copy.deepcopy(staging_step("pages.yml", "deploy"))
    pages["run"] = pages["run"].replace('cp -R site "$RUNNER_TEMP/site"', 'cp -R site/. "$RUNNER_TEMP/site"')
    assert pages != staging_step("ci.yml", "site")


def copied(script: str) -> list[str]:
    """What the staging step's commands at its top level copy, as `cp` names them: each source but the
    destination, its options left out."""
    sources: list[str] = []
    for line in script.splitlines():
        if line.startswith("cp "):
            words = [word for word in shlex.split(line)[1:] if not word.startswith("-")]
            sources += words[:-1]
    return sources


def staged(tree: Path, script: str) -> tuple[int, str]:
    found = {"run": script, "env": {"RUNNER_TEMP": str(tree.parent / "runner")}}
    (tree.parent / "runner").mkdir(exist_ok=True)
    status, _, printed = run_step(found, {}, tree)
    return status, printed


def test_every_file_the_staging_step_copies_must_exist(tmp_path: Path) -> None:
    """The site job's first check: the staging step runs under `bash -eo pipefail`, so a `cp` of a missing
    file fails it. A tree that holds each source the step copies stages; without any one of them, it fails.
    The tree is built from the step's own text, and holds no schema, which the step copies only if present."""
    script = staging_step("ci.yml", "site")["run"]
    sources = copied(script)
    assert len(sources) >= 3, sources

    def tree_without(left_out: str | None, name: str) -> Path:
        root = tmp_path / name
        for source in sources:
            path = root / source.removesuffix("/*")
            if source.endswith("/*"):
                # Left out, the directory is there and empty: the glob then matches no file.
                path.mkdir(parents=True, exist_ok=True)
                if source != left_out:
                    (path / "one").write_text("", encoding="utf-8")
            elif source == left_out:
                continue
            elif "." in Path(source).name:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / "page.html").write_text("", encoding="utf-8")
        return root

    status, printed = staged(tree_without(None, "whole"), script)
    assert status == 0, printed
    for number, source in enumerate(sources):
        status, printed = staged(tree_without(source, f"without-{number}"), script)
        assert status != 0, f"the step staged a tree without {source}: {printed}"


SITE_CHECK_STEP = (
    "Every local link, image and icon resolves, every page keeps its policy, the README's images exist"
)
POLICY_META = """<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'">"""


def site_tree(root: Path, readme_image: str | None = None, load: str = "") -> Path:
    """A tree that holds what the site job reads, built from the staging step's own sources (so that it names
    no path of the site): each directory source holds a page with a policy, which loads `load` if given, each
    file source a file, and the README names an image, the first file source unless `readme_image` is given;
    no schema, which the step stages only if present; and the site check."""
    sources = copied(staging_step("ci.yml", "site")["run"])
    files = [source for source in sources if "." in Path(source).name]
    for source in sources:
        path = root / source.removesuffix("/*")
        if source.endswith("/*"):
            path.mkdir(parents=True, exist_ok=True)
            (path / "one").write_text("", encoding="utf-8")
        elif source in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x89PNG")
        else:
            path.mkdir(parents=True, exist_ok=True)
            body = f'<img src="{load}" alt="">' if load else "<p>A page.</p>"
            (path / "page.html").write_text(
                f"<!doctype html><html><head>{POLICY_META}<title>p</title></head><body>{body}</body></html>",
                encoding="utf-8",
            )
    (root / "README.md").write_text(f"![logo]({readme_image or files[0]})\n", encoding="utf-8")
    (root / "scripts").mkdir()
    shutil.copy(REPOSITORY / "scripts" / "check_site.py", root / "scripts" / "check_site.py")
    return root


def job_status(job: dict[str, Any], tree: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    """The job's steps that run a command, run in order in `tree` as GitHub runs them, to the first that
    fails: its status and what it printed."""
    runner = tree.parent / f"{tree.name}-runner"
    runner.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    for found in job["steps"]:
        if "run" in found:
            status, _, printed = run_step(found, {}, tree)
            if status:
                return status, printed
    return 0, ""


@pytest.mark.parametrize("job_id", ["site", "site_commit"])
def test_the_site_jobs_steps_as_written_fail_a_broken_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, job_id: str
) -> None:
    """The job's steps, run as written, on a tree that passes, then on one whose README names an image the
    tree does not hold, and on one whose page loads from elsewhere: the job must fail on each fault. So the
    check step must be there, run after the staging step, with `--readme`."""
    job = workflow("ci.yml")["jobs"][job_id]
    assert job_status(job, site_tree(tmp_path / "clean"), monkeypatch) == (0, "")
    status, printed = job_status(job, site_tree(tmp_path / "readme", readme_image="missing.png"), monkeypatch)
    assert status != 0
    assert "README.md: its image 'missing.png' names missing.png, which the tree does not hold" in printed
    loading = site_tree(tmp_path / "loading", load="https://elsewhere.example/x.png")
    status, printed = job_status(job, loading, monkeypatch)
    assert status != 0
    assert "<img src> loads 'https://elsewhere.example/x.png' from elsewhere" in printed


def without_the_check(job: dict[str, Any]) -> None:
    job["steps"] = [found for found in job["steps"] if found.get("name") != SITE_CHECK_STEP]


def without_the_readme(job: dict[str, Any]) -> None:
    found = step(job, SITE_CHECK_STEP)
    found["run"] = found["run"].replace(" --readme README.md", "")


def the_check_first(job: dict[str, Any]) -> None:
    check = step(job, SITE_CHECK_STEP)
    job["steps"].remove(check)
    job["steps"].insert(1, check)


@pytest.mark.parametrize(
    "fault", [without_the_check, without_the_readme, the_check_first], ids=lambda fault: fault.__name__
)
def test_the_site_jobs_run_check_can_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: Callable[[dict[str, Any]], None]
) -> None:
    """The controls: the job without its check step, without `--readme`, or with the check before the
    staging, passes a fault or fails the clean tree."""
    job = copy.deepcopy(workflow("ci.yml")["jobs"]["site"])
    fault(job)
    outcomes = [
        job_status(job, site_tree(tmp_path / "clean"), monkeypatch)[0] == 0,
        job_status(job, site_tree(tmp_path / "readme", readme_image="missing.png"), monkeypatch)[0] != 0,
        job_status(job, site_tree(tmp_path / "loading", load="https://elsewhere.example/x.png"), monkeypatch)[
            0
        ]
        != 0,
    ]
    assert not all(outcomes), outcomes


def site_commit_problems(ci: Workflow) -> list[str]:
    """Where the site-commit job, or the per-commit job, does not run the site job's checks on each commit
    it is given, checked out as it is."""
    jobs = ci["jobs"]
    site_steps = [step(jobs["site"], SITE_STEP), step(jobs["site"], SITE_CHECK_STEP)]
    job = jobs["site_commit"]
    problems: list[str] = []
    strategy = job.get("strategy", {})
    if strategy != {
        "fail-fast": False,
        "max-parallel": cap_expression(CAPS[1]),
        "matrix": {"sha": "${{ fromJSON(needs.gate.outputs.site_commits) }}"},
    }:
        problems.append(f"the site-commit job's strategy is {strategy!r}")
    problems += cap_problems(ci, CAPS[1])
    checkout = {
        **jobs["site"]["steps"][0],
        "with": {"ref": "${{ matrix.sha }}", **jobs["site"]["steps"][0]["with"]},
    }
    if job["steps"] != [checkout, *site_steps]:
        problems.append("the site-commit job's steps are not its commit's checkout and the site job's steps")
    commit_steps = [
        {key: value for key, value in found.items() if key != "if"}
        for found in jobs["commit"]["steps"]
        if found.get("name") in (SITE_STEP, SITE_CHECK_STEP)
    ]
    if commit_steps != site_steps:
        problems.append("the per-commit job does not run the site job's steps")
    return problems


def test_each_commit_gets_the_site_jobs_checks() -> None:
    assert site_commit_problems(workflow("ci.yml")) == []


def site_commit_on_the_merge(ci: Workflow) -> None:
    del ci["jobs"]["site_commit"]["steps"][0]["with"]["ref"]


def site_commit_without_the_readme(ci: Workflow) -> None:
    found = step(ci["jobs"]["site_commit"], SITE_CHECK_STEP)
    found["run"] = found["run"].replace(" --readme README.md", "")


def site_commit_of_the_code_commits(ci: Workflow) -> None:
    ci["jobs"]["site_commit"]["strategy"]["matrix"]["sha"] = "${{ fromJSON(needs.gate.outputs.commits) }}"


def site_commit_uncapped(ci: Workflow) -> None:
    del ci["jobs"]["site_commit"]["strategy"]["max-parallel"]


def site_commit_capped_by_the_variable(ci: Workflow) -> None:
    """The variable read again, where the gate's check no longer holds it."""
    ci["jobs"]["site_commit"]["strategy"]["max-parallel"] = (
        "${{ fromJSON(vars.PER_COMMIT_MAX_PARALLEL || '6') }}"
    )


def site_commit_capped_by_another_output(ci: Workflow) -> None:
    ci["jobs"]["site_commit"]["strategy"]["max-parallel"] = "${{ fromJSON(needs.gate.outputs.commits) }}"


def site_commit_capped_by_a_string(ci: Workflow) -> None:
    ci["jobs"]["site_commit"]["strategy"]["max-parallel"] = (
        "${{ needs.gate.outputs.per_commit_max_parallel }}"
    )


def site_commit_capped_at_six(ci: Workflow) -> None:
    ci["jobs"]["site_commit"]["strategy"]["max-parallel"] = 6


def commit_job_without_the_site_check(ci: Workflow) -> None:
    ci["jobs"]["commit"]["steps"] = [
        found for found in ci["jobs"]["commit"]["steps"] if found.get("name") != SITE_CHECK_STEP
    ]


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (site_commit_on_the_merge, "the site-commit job's steps are not"),
        (site_commit_without_the_readme, "the site-commit job's steps are not"),
        (site_commit_of_the_code_commits, "the site-commit job's strategy is"),
        (site_commit_uncapped, "the site_commit job runs None at once"),
        (
            site_commit_capped_by_the_variable,
            "the site_commit job runs \"${{ fromJSON(vars.PER_COMMIT_MAX_PARALLEL || '6') }}\" at once",
        ),
        (
            site_commit_capped_by_another_output,
            "the site_commit job runs '${{ fromJSON(needs.gate.outputs.commits) }}' at once",
        ),
        (
            site_commit_capped_by_a_string,
            "the site_commit job runs '${{ needs.gate.outputs.per_commit_max_parallel }}' at once",
        ),
        (site_commit_capped_at_six, "the site_commit job runs 6 at once"),
        (commit_job_without_the_site_check, "the per-commit job does not run the site job's steps"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_site_commit_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = site_commit_problems(ci)
    assert any(problem in line for line in found), found


# What Pages deploys: pages.yml's job checks out the tree as the site job does, stages it with the step the
# site job runs and nothing else around it, and uploads the staged directory, which the site job checks.
PAGES_ACTIONS = (
    "actions/checkout",
    "actions/configure-pages",
    None,
    "actions/upload-pages-artifact",
    "actions/deploy-pages",
)
STAGED = "${{ runner.temp }}/site"


def pages_problems(pages: Workflow, ci: Workflow) -> list[str]:
    """Where pages.yml's job could deploy other than what the site job checks."""
    steps: list[dict[str, Any]] = pages["jobs"]["deploy"]["steps"]
    kinds = tuple(str(found["uses"]).partition("@")[0] if "uses" in found else None for found in steps)
    if kinds != PAGES_ACTIONS:
        return [f"pages.yml's job runs {kinds}, not {PAGES_ACTIONS}"]
    problems: list[str] = []
    site_checkout = ci["jobs"]["site"]["steps"][0]
    if steps[0].get("with") != site_checkout.get("with"):
        problems.append(
            f"pages.yml checks out with {steps[0].get('with')}, the site job with {site_checkout.get('with')}"
        )
    if steps[2] != step(ci["jobs"]["site"], SITE_STEP):
        problems.append(
            "pages.yml's step between configure-pages and the upload is not the site job's staging step"
        )
    if steps[3].get("with") != {"path": STAGED}:
        problems.append(f"pages.yml uploads {steps[3].get('with')}, not the staged directory {STAGED}")
    if '"$RUNNER_TEMP/site"' not in step(ci["jobs"]["site"], SITE_CHECK_STEP)["run"]:
        problems.append("the site job checks another directory than the one pages.yml uploads")
    return problems


def test_pages_deploys_what_the_site_job_checks() -> None:
    assert pages_problems(workflow("pages.yml"), workflow("ci.yml")) == []


def a_step_after_the_staging(pages: Workflow) -> None:
    steps = pages["jobs"]["deploy"]["steps"]
    steps.insert(3, {"name": "Prune", "run": 'rm "$RUNNER_TEMP/site/logo.png"'})


def a_step_before_the_staging(pages: Workflow) -> None:
    pages["jobs"]["deploy"]["steps"].insert(1, {"run": "rm site/index.html"})


def another_directory_uploaded(pages: Workflow) -> None:
    pages["jobs"]["deploy"]["steps"][3]["with"]["path"] = "${{ runner.temp }}/site/schema"


def submodules_checked_out(pages: Workflow) -> None:
    pages["jobs"]["deploy"]["steps"][0]["with"]["submodules"] = "recursive"


def another_staging(pages: Workflow) -> None:
    staging = pages["jobs"]["deploy"]["steps"][2]
    staging["run"] = staging["run"].replace(
        'cp -R site "$RUNNER_TEMP/site"', 'cp -RL site "$RUNNER_TEMP/site"'
    )


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_step_after_the_staging, "pages.yml's job runs"),
        (a_step_before_the_staging, "pages.yml's job runs"),
        (another_directory_uploaded, "pages.yml uploads {'path': '${{ runner.temp }}/site/schema'}"),
        (submodules_checked_out, "pages.yml checks out with"),
        (another_staging, "is not the site job's staging step"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_pages_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    pages = copy.deepcopy(workflow("pages.yml"))
    fault(pages)
    found = pages_problems(pages, workflow("ci.yml"))
    assert any(problem in line for line in found), found


def path_filter_matches(pattern: str, path: str) -> bool:
    """GitHub's filter patterns for paths: `*` is any run of characters but `/`, `**` any run of them."""
    regex = "".join(
        ".*" if part == "**" else "[^/]*" if part == "*" else re.escape(part)
        for part in re.split(r"(\*\*|\*)", pattern)
    )
    return re.fullmatch(regex, path) is not None


def push_paths(pages: Workflow) -> list[str]:
    """The `paths` of a workflow's push trigger, which PyYAML reads under the key `True`, for `on`."""
    triggers = cast(dict[object, Any], pages)[True]
    paths: list[str] = triggers["push"]["paths"]
    return paths


def pages_trigger_problems(pages: Workflow) -> list[str]:
    """Each input of the deployed site that a push to main could change without the Pages workflow running.

    The inputs are the staging step's: `site/`, the logo and favicons, every file of the schema tree, the
    index writer, and the manifest it reads to decide which version's page carries the draft note. The
    workflow itself is an input too. The freezing commit changes the manifest alone, so without its line the
    note would stay on the live page of a version that is frozen."""
    patterns = push_paths(pages)
    schema = REPOSITORY / "src" / "materica" / "schema"
    inputs = [
        "site/index.html",
        "assets/images/logo.png",
        *(
            (Path(where) / name).relative_to(REPOSITORY).as_posix()
            for where, _, names in os.walk(schema)
            for name in names
        ),
        "src/materica/schema/0.2-dev/a_new_file.json",
        Path(schema_index.__file__).relative_to(REPOSITORY).as_posix(),
        schema_index.MANIFEST.relative_to(REPOSITORY).as_posix(),
        ".github/workflows/pages.yml",
    ]
    return [
        f"a push that changes {path} does not run pages.yml"
        for path in inputs
        if not any(path_filter_matches(pattern, path) for pattern in patterns)
    ]


def test_pages_runs_when_any_input_of_the_deployed_site_changes() -> None:
    assert pages_trigger_problems(workflow("pages.yml")) == []


def test_the_path_filter_matches_as_github_does() -> None:
    assert path_filter_matches("src/materica/schema/**", "src/materica/schema/0.1/vocabulary/a.json")
    assert path_filter_matches(
        "tests/spec_sync/released_schemas.json", "tests/spec_sync/released_schemas.json"
    )
    assert path_filter_matches("assets/images/*.png", "assets/images/logo.png")
    assert not path_filter_matches("assets/images/*.png", "assets/images/favicon/a.png")
    assert not path_filter_matches("scripts/schema_index.py", "scripts/schema_index_py")
    assert not path_filter_matches("site/**", "sites/index.html")


@pytest.mark.parametrize("line", push_paths(workflow("pages.yml")))
def test_the_pages_trigger_check_can_fail(line: str) -> None:
    """The control: with any one line of the filter removed, an input no longer runs the workflow."""
    pages = copy.deepcopy(workflow("pages.yml"))
    push_paths(pages).remove(line)
    assert pages_trigger_problems(pages)


def test_the_pages_trigger_check_names_the_manifest_where_its_line_is_removed() -> None:
    pages = copy.deepcopy(workflow("pages.yml"))
    push_paths(pages).remove("tests/spec_sync/released_schemas.json")
    assert pages_trigger_problems(pages) == [
        "a push that changes tests/spec_sync/released_schemas.json does not run pages.yml"
    ]


def result_status(
    gate: str,
    code: str,
    hypothesis: str,
    jobs: dict[str, str],
    tmp_path: Path,
    ci: Workflow | None = None,
    commits: str = "[]",
    site: str | None = None,
    site_commits: str = "[]",
) -> int:
    """The result step's exit status, for the gate's result and outputs and each other job's result; the
    site's output as the code's where it is not given, as the gate gives it but for a change to the site or
    to code undone."""
    context = {
        "needs.gate.result": gate,
        "needs.gate.outputs.code": code,
        "needs.gate.outputs.hypothesis": hypothesis,
        "needs.gate.outputs.site": code if site is None else site,
        "needs.gate.outputs.commits": commits,
        "needs.gate.outputs.site_commits": site_commits,
    } | {f"needs.{job}.result": result for job, result in jobs.items()}
    found = step((ci or workflow("ci.yml"))["jobs"]["result"], RESULT_STEP)
    status, _, _ = run_step(found, context, tmp_path)
    return status


def all_jobs(result: str, **others: str) -> dict[str, str]:
    return {job: others.get(job, result) for job in GATED}


@pytest.mark.parametrize(
    ("gate", "code", "hypothesis", "jobs"),
    [
        ("success", "true", "true", all_jobs("success")),
        ("success", "true", "false", all_jobs("success", hypothesis="skipped")),
        ("success", "false", "false", all_jobs("skipped")),
    ],
    ids=["everything", "no-hypothesis", "docs-only"],
)
def test_the_result_passes_when_every_job_the_gate_asked_for_succeeded(
    tmp_path: Path, gate: str, code: str, hypothesis: str, jobs: dict[str, str]
) -> None:
    assert result_status(gate, code, hypothesis, jobs, tmp_path) == 0


@pytest.mark.parametrize(
    ("gate", "code", "hypothesis", "jobs"),
    [
        ("success", "true", "true", all_jobs("success", tests="skipped")),
        ("success", "true", "false", all_jobs("success", controls="skipped", hypothesis="skipped")),
        ("success", "true", "true", all_jobs("success", hypothesis="skipped")),
        ("success", "true", "false", all_jobs("success", static="cancelled", hypothesis="skipped")),
        ("success", "", "", all_jobs("skipped")),
        ("failure", "", "", all_jobs("skipped")),
        ("failure", "false", "false", all_jobs("skipped")),
        ("success", "false", "false", all_jobs("skipped", tests="failure")),
    ],
    ids=[
        "asked-for-and-skipped",
        "controls-asked-for-and-skipped",
        "hypothesis-asked-for-and-skipped",
        "asked-for-and-cancelled",
        "outputs-empty",
        "gate-failed",
        "gate-failed-with-its-outputs",
        "not-asked-for-and-failed",
    ],
)
def test_the_result_fails_when_a_job_the_gate_asked_for_did_not_succeed(
    tmp_path: Path, gate: str, code: str, hypothesis: str, jobs: dict[str, str]
) -> None:
    """A skipped job reports success to a required check: a gate whose outputs are empty or wrong would skip
    every job, and a result that looked only for failures would pass."""
    assert result_status(gate, code, hypothesis, jobs, tmp_path) == 1


@pytest.mark.parametrize(
    ("site", "jobs", "status"),
    [
        ("true", all_jobs("skipped", site="success"), 0),
        ("true", all_jobs("skipped"), 1),
        ("true", all_jobs("skipped", site="failure"), 1),
        ("false", all_jobs("skipped", site="failure"), 1),
        ("", all_jobs("skipped"), 1),
    ],
    ids=[
        "checked",
        "asked-for-and-skipped",
        "asked-for-and-failed",
        "not-asked-for-and-failed",
        "output-empty",
    ],
)
def test_the_result_requires_the_site_job_when_the_gate_asks_for_it(
    tmp_path: Path, site: str, jobs: dict[str, str], status: int
) -> None:
    """A change to the site alone: no code job, the site job alone."""
    assert result_status("success", "false", "false", jobs, tmp_path, site=site) == status


TWO_COMMITS = json.dumps(["a" * 40, "b" * 40])


@pytest.mark.parametrize(
    ("commits", "commit_job", "status"),
    [
        ("[]", "skipped", 0),
        (TWO_COMMITS, "success", 0),
        (TWO_COMMITS, "skipped", 1),
        (TWO_COMMITS, "failure", 1),
        (TWO_COMMITS, "cancelled", 1),
        ("[]", "failure", 1),
        ("", "skipped", 1),
        ("a list", "skipped", 1),
    ],
    ids=[
        "none-to-check",
        "checked",
        "asked-for-and-skipped",
        "asked-for-and-failed",
        "asked-for-and-cancelled",
        "not-asked-for-and-failed",
        "output-empty",
        "output-no-list",
    ],
)
def test_the_result_requires_the_per_commit_job_when_the_gate_lists_commits(
    tmp_path: Path, commits: str, commit_job: str, status: int
) -> None:
    jobs = all_jobs("success", commit=commit_job)
    assert result_status("success", "true", "true", jobs, tmp_path, commits=commits) == status


@pytest.mark.parametrize(
    ("site_commits", "site_commit_job", "status"),
    [
        ("[]", "skipped", 0),
        (TWO_COMMITS, "success", 0),
        (TWO_COMMITS, "skipped", 1),
        (TWO_COMMITS, "failure", 1),
        ("[]", "cancelled", 1),
        ("", "skipped", 1),
    ],
    ids=[
        "none-to-check",
        "checked",
        "asked-for-and-skipped",
        "asked-for-and-failed",
        "not-asked-for-and-cancelled",
        "output-empty",
    ],
)
def test_the_result_requires_the_site_commit_job_when_the_gate_lists_site_commits(
    tmp_path: Path, site_commits: str, site_commit_job: str, status: int
) -> None:
    jobs = all_jobs("skipped", site="success", site_commit=site_commit_job)
    assert (
        result_status("success", "false", "false", jobs, tmp_path, site="true", site_commits=site_commits)
        == status
    )


def test_without_its_check_of_the_gate_the_result_passes_a_failed_gate_with_outputs(tmp_path: Path) -> None:
    """The control of `gate-failed-with-its-outputs`: no line but the gate's own check fails that case. A
    failed gate has no outputs today, since its sign-off and scan run first; this holds if they move."""
    ci = copy.deepcopy(workflow("ci.yml"))
    found = step(ci["jobs"]["result"], RESULT_STEP)
    line = """[ "$GATE" = success ] || fail "the gate ended in '$GATE'"\n"""
    assert found["run"].count(line) == 1
    found["run"] = found["run"].replace(line, "")
    assert result_status("failure", "false", "false", all_jobs("skipped"), tmp_path, ci) == 0


def wiring_problems(ci: Workflow) -> list[str]:
    """Where a job is not run by exactly the gate's output, or the result does not read each job and the
    gate's outputs. GitHub reports a job skipped by its `if` as a success: a wrong condition hides a job."""
    jobs: dict[str, Any] = ci["jobs"]
    gate = jobs["gate"]
    problems = [
        f"a job neither gated nor ungated: {job_id}" for job_id in sorted(set(jobs) - set(GATED) - UNGATED)
    ]
    if [found.get("id") for found in gate["steps"]].count(GATE_STEP_ID) != 1:
        problems.append(f"the gate has no single step with the id {GATE_STEP_ID!r}")
    if step(gate, GATE_STEP).get("id") != GATE_STEP_ID:
        problems.append(f"the step {GATE_STEP!r} has not the id {GATE_STEP_ID!r}")
    for output in sorted(set(GATED.values())):
        if gate["outputs"].get(output) != f"${{{{ steps.{GATE_STEP_ID}.outputs.{output} }}}}":
            problems.append(f"the gate's output {output} is {gate['outputs'].get(output)!r}")
    for job_id, output in GATED.items():
        job = jobs.get(job_id, {})
        if job.get("needs") != "gate":
            problems.append(f"{job_id} needs {job.get('needs')!r}, not the gate alone")
        if job.get("if") != f"needs.gate.outputs.{output} {RUNS_WHEN[output]}":
            problems.append(f"{job_id} runs if {job.get('if')!r}")
    result = jobs["result"]
    if result.get("needs") != ["gate", *GATED] or result.get("if") != "always()":
        problems.append(f"the result needs {result.get('needs')!r} if {result.get('if')!r}")
    read = set(re.findall(r"\$\{\{ (needs\.[\w.-]+) \}\}", str(step(result, RESULT_STEP).get("env"))))
    wanted = {"needs.gate.result"} | {f"needs.gate.outputs.{output}" for output in set(GATED.values())}
    wanted |= {f"needs.{job_id}.result" for job_id in GATED}
    problems += [f"the result does not read {expression}" for expression in sorted(wanted - read)]
    return problems


def test_each_job_runs_by_exactly_the_gates_output_and_the_result_reads_them_all() -> None:
    assert wiring_problems(workflow("ci.yml")) == []


def renamed_gate_step(ci: Workflow) -> None:
    step(ci["jobs"]["gate"], GATE_STEP)["id"] = "changed"


def rewired_output(ci: Workflow) -> None:
    ci["jobs"]["gate"]["outputs"]["code"] = "${{ steps.changed.outputs.code }}"


def condition_without_comparison(ci: Workflow) -> None:
    ci["jobs"]["tests"]["if"] = "needs.gate.outputs.code"


def condition_on_another_output(ci: Workflow) -> None:
    ci["jobs"]["hypothesis"]["if"] = "needs.gate.outputs.code == 'true'"


def result_without_a_job(ci: Workflow) -> None:
    ci["jobs"]["result"]["needs"].remove("tests")


def result_reading_no_job(ci: Workflow) -> None:
    del step(ci["jobs"]["result"], RESULT_STEP)["env"]["TESTS_JOB"]


def job_nobody_gated(ci: Workflow) -> None:
    ci["jobs"]["lint"] = {"needs": "gate"}


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (renamed_gate_step, "has not the id 'paths'"),
        (rewired_output, "the gate's output code"),
        (condition_without_comparison, "tests runs if"),
        (condition_on_another_output, "hypothesis runs if"),
        (result_without_a_job, "the result needs"),
        (result_reading_no_job, "does not read needs.tests.result"),
        (job_nobody_gated, "neither gated nor ungated: lint"),
    ],
)
def test_the_wiring_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = wiring_problems(ci)
    assert any(problem in line for line in found), found


# Runs of ci.yml, each as the context its concurrency settings read: two pushes to main, the weekly run, a
# manual run on main, two pushes to one pull request and one to another.
RUNS = [
    {"github.event_name": "push", "github.ref": "refs/heads/main", "github.run_id": "101"},
    {"github.event_name": "push", "github.ref": "refs/heads/main", "github.run_id": "102"},
    {"github.event_name": "schedule", "github.ref": "refs/heads/main", "github.run_id": "103"},
    {"github.event_name": "workflow_dispatch", "github.ref": "refs/heads/main", "github.run_id": "104"},
    {"github.event_name": "pull_request", "github.ref": "refs/pull/7/merge", "github.run_id": "105"},
    {"github.event_name": "pull_request", "github.ref": "refs/pull/7/merge", "github.run_id": "106"},
    {"github.event_name": "pull_request", "github.ref": "refs/pull/8/merge", "github.run_id": "107"},
]


def setting(value: object, context: Mapping[str, object]) -> object:
    """A setting's value: its expression's, where it is one whole, its text with each expression filled in,
    or the value as written."""
    if not isinstance(value, str):
        return value
    whole = re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", value, re.S)
    return evaluated(whole[1], context) if whole and "${{" not in whole[1] else rendered(value, context)


def described(run: Mapping[str, str]) -> str:
    return f"{run['github.run_id']} ({run['github.event_name']})"


def concurrency_problems(ci: Workflow) -> list[str]:
    """Where a run other than a pull request's could cancel another or be replaced, or a newer push to a pull
    request would not cancel the run of the older one."""
    concurrency: dict[str, Any] = ci.get("concurrency", {})
    problems = [
        f"the job {job_id} sets concurrency" for job_id, job in ci["jobs"].items() if "concurrency" in job
    ]
    runs = [run | {"github.workflow": ci["name"]} for run in RUNS]
    for run in runs:
        event = run["github.event_name"]
        cancels = truthy(setting(concurrency.get("cancel-in-progress", False), run))
        if cancels != (event == "pull_request"):
            verb = "cancels" if cancels else "does not cancel"
            problems.append(f"a {event} run {verb} the one in its group")
    grouped = [(run, setting(concurrency.get("group", ""), run)) for run in runs]
    for (first, first_group), (second, second_group) in itertools.combinations(grouped, 2):
        one_pull_request = first["github.event_name"] == second["github.event_name"] == "pull_request" and (
            first["github.ref"] == second["github.ref"]
        )
        shared = first_group == second_group
        if shared != one_pull_request:
            problems.append(
                f"runs {described(first)} and {described(second)} {'share' if shared else 'do not share'} "
                f"a group: {first_group!r}, {second_group!r}"
            )
    return problems


def test_only_a_newer_push_to_a_pull_request_cancels_a_run() -> None:
    """A run on main is never cancelled or replaced: each merge is tested whole, and the weekly run never
    waits behind a push that could replace it."""
    assert concurrency_problems(workflow("ci.yml")) == []


@pytest.mark.parametrize(
    ("concurrency", "problem"),
    [
        (
            {"group": "${{ github.workflow }}-${{ github.ref }}", "cancel-in-progress": False},
            "runs 101 (push) and 103 (schedule) share a group",
        ),
        (
            {"group": "${{ github.workflow }}-${{ github.run_id }}", "cancel-in-progress": True},
            "a push run cancels the one in its group",
        ),
        (
            {"group": "${{ github.workflow }}-${{ github.run_id }}"},
            "runs 105 (pull_request) and 106 (pull_request) do not share a group",
        ),
    ],
    ids=["a-group-per-ref", "every-run-cancels", "a-group-per-run"],
)
def test_the_concurrency_check_can_fail(concurrency: dict[str, object], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    ci["concurrency"] = concurrency
    found = concurrency_problems(ci)
    assert any(problem in line for line in found), found


def test_the_concurrency_check_finds_a_jobs_own_group() -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    ci["jobs"]["hypothesis"]["concurrency"] = {"group": "hypothesis", "cancel-in-progress": True}
    assert concurrency_problems(ci) == ["the job hypothesis sets concurrency"]


def pytest_commands(job: dict[str, Any]) -> list[list[str]]:
    """Each pytest command of the job, its arguments as the shell splits them, up to the end of the command;
    an expression `${{ ... }}` is kept as one word."""
    commands: list[list[str]] = []
    for found in job.get("steps", []):
        script = re.sub(r"\\\n", " ", str(found.get("run", "")))
        for line in script.splitlines():
            line = re.sub(r"\$\{\{(.*?)\}\}", lambda match: "${{" + match[1].replace(" ", "") + "}}", line)
            lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            words = list(lexer)
            for start, word in enumerate(words):
                if word == "pytest":
                    rest = words[start + 1 :]
                    ends = [index for index, rest_word in enumerate(rest) if set(rest_word) <= set("();<>|&")]
                    commands.append(rest[: ends[0]] if ends else rest)
    return commands


def property_controls(job: dict[str, Any]) -> str | None:
    """What the job's one pytest command gives `--property-controls`, or None."""
    [command] = pytest_commands(job)
    if "--property-controls" in command:
        return command[command.index("--property-controls") + 1]
    return None


# The mutant searches and the audit controls, by the test's name: a mutant search tests that a mutant is
# killed or dies, an audit control that a property fails its feature audit. CI selects them by module
# instead (`--property-controls`, `PROPERTY_CONTROLS` in tests/conftest.py), so a new module of either is
# selected unedited, and the matrix check finds any other test such a module holds, which would run on the
# range's ends alone.
MUTANT_SEARCH = re.compile(r"test_\w*mutant\w*_(?:is_killed|dies)\w*")
AUDIT_CONTROL = re.compile(r"test_\w*_fails_the_audit\w*")


def function(test: str) -> str:
    """The name of the test function a node id names."""
    return test.partition("[")[0].rpartition("::")[2]


def is_control(test: str) -> bool:
    return bool(MUTANT_SEARCH.fullmatch(function(test)) or AUDIT_CONTROL.fullmatch(function(test)))


def version(python: str) -> tuple[int, ...]:
    return tuple(int(part) for part in python.split("."))


def combinations(matrix: object) -> list[dict[str, object]]:
    """The jobs a matrix makes, as GitHub makes them: each combination of its lists but those an `exclude`
    entry matches; then each `include` entry added to every combination whose own values it leaves alone, or,
    where it fits none, a combination of its own."""
    assert isinstance(matrix, dict), f"a matrix the test cannot expand: {matrix!r}"
    entries = cast(dict[str, Any], matrix)
    axes = {key: values for key, values in entries.items() if key not in ("include", "exclude")}
    assert all(isinstance(values, list) for values in axes.values()), (
        f"a matrix the test cannot expand: {matrix}"
    )
    made = [dict(zip(axes, values, strict=True)) for values in itertools.product(*axes.values())]
    kept = [
        combination
        for combination in made
        if not any(
            all(combination.get(key) == value for key, value in excluded.items())
            for excluded in entries.get("exclude", [])
        )
    ]
    added: list[dict[str, object]] = []
    for included in entries.get("include", []):
        fitting = [
            combination
            for combination in kept
            if all(combination[key] == value for key, value in included.items() if key in axes)
        ]
        for combination in fitting:
            combination.update(included)
        if not fitting:
            added.append(dict(included))
    return kept + added


def test_a_matrix_is_expanded_as_github_expands_it() -> None:
    matrix = {
        "python": ["3.11", "3.12"],
        "os": ["a", "b"],
        "exclude": [{"python": "3.12", "os": "b"}],
        "include": [{"python": "3.11", "extra": "x"}, {"python": "3.12", "os": "b", "extra": "y"}],
    }
    assert combinations(matrix) == [
        {"python": "3.11", "os": "a", "extra": "x"},
        {"python": "3.11", "os": "b", "extra": "x"},
        {"python": "3.12", "os": "a"},
        {"python": "3.12", "os": "b", "extra": "y"},
    ]


def pytest_step(job: dict[str, Any]) -> dict[str, Any]:
    """The job's one step that runs pytest."""
    [found] = [found for found in job["steps"] if pytest_commands({"steps": [found]})]
    return cast(dict[str, Any], found)


# The events that run the test matrix, and the status functions as a step finds them when every step before it
# succeeded.
EVENTS = ("pull_request", "push", "schedule", "workflow_dispatch")
SO_FAR_SUCCEEDED = {"success()": True, "failure()": False, "cancelled()": False, "always()": True}


def matrix_problems(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> list[str]:
    """Where the test matrix's jobs, together, leave a test out on a Python: any test on the supported
    range's ends, any but the mutant searches and the audit controls between them, which run there.
    `selected` gives the tests that each value of `--property-controls` selects, None for a run without it.
    What a job runs is computed as GitHub runs it: its matrix after `exclude` and `include`, the Python each
    combination installs, and whether its pytest step's `if` skips it there, on any event."""
    every = selected[None]
    controls = {test for test in every if is_control(test)}
    # The supported range, which tests/unit/test_python_versions.py holds to pyproject.toml.
    pythons: list[str] = ci["jobs"]["tests"]["strategy"]["matrix"]["python"]
    ends = {min(pythons, key=version), max(pythons, key=version)}
    run: dict[str, set[str]] = {python: set() for python in pythons}
    problems: list[str] = []
    for job_id in ("tests", "controls"):
        job = ci["jobs"][job_id]
        installed = [
            found.get("with", {}).get("python-version")
            for found in job["steps"]
            if str(found.get("uses", "")).startswith("astral-sh/setup-uv@")
        ]
        if installed != ["${{ matrix.python }}"]:
            problems.append(f"{job_id} installs Python {installed}, not the matrix's")
        runs_pytest = pytest_step(job)
        for combination in combinations(job["strategy"]["matrix"]):
            python = combination.get("python")
            if not isinstance(python, str):
                problems.append(f"{job_id} has a combination with no Python: {combination}")
                continue
            context = {f"matrix.{key}": value for key, value in combination.items()} | SO_FAR_SUCCEEDED
            skipped = [
                event
                for event in EVENTS
                if not truthy(evaluated(condition(runs_pytest), context | {"github.event_name": event}))
            ]
            if skipped:
                problems.append(
                    f"{job_id}'s pytest step is skipped on Python {python} ({', '.join(skipped)}): "
                    f"if {runs_pytest.get('if')!r}"
                )
                continue
            run.setdefault(python, set()).update(selected[property_controls(job)])

    def by_file(tests: Set[str]) -> str:
        files = Counter(test.partition("::")[0] for test in tests)
        return ", ".join(f"{count} of {file}" for file, count in sorted(files.items()))

    if others := selected["only"] - controls:
        problems.append(f"the controls' modules hold {by_file(others)}: no mutant search or audit control")
    for python in sorted(run, key=version):
        wanted = every if python in ends else every - controls
        if wanted - run[python]:
            problems.append(f"Python {python} leaves out {by_file(wanted - run[python])}")
        if run[python] - wanted:
            problems.append(f"Python {python} runs {by_file(run[python] - wanted)}")
    return problems


def collected(options: list[str | None]) -> dict[str | None, frozenset[str]]:
    """The tests that a run of the whole suite collects with each value of `--property-controls`, collected
    side by side."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    runs = {
        option: subprocess.Popen(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
            + (["--property-controls", option] if option else []),
            cwd=REPOSITORY,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for option in options
    }
    found: dict[str | None, frozenset[str]] = {}
    for option, run in runs.items():
        printed, _ = run.communicate()
        assert run.returncode == 0, printed[-3000:]
        found[option] = frozenset(line for line in printed.splitlines() if "::" in line)
    return found


def test_the_mutant_searches_and_audit_controls_run_at_the_range_ends_and_nothing_else_is_left_out() -> None:
    selected = collected([None, "none", "only"])
    # Every test module is collected, so that none is out of every job unseen; and the names find both kinds.
    on_disk = {path.relative_to(REPOSITORY).as_posix() for path in (REPOSITORY / "tests").rglob("test_*.py")}
    assert on_disk - {test.partition("::")[0] for test in selected[None]} == set()
    functions = {function(test) for test in selected["only"]}
    assert any(MUTANT_SEARCH.fullmatch(name) for name in functions)
    assert any(AUDIT_CONTROL.fullmatch(name) for name in functions)
    assert matrix_problems(workflow("ci.yml"), selected) == []


READ = "tests/unit/test_read.py::test_reads"
AUDIT = "tests/unit/test_audit_controls.py::test_a_generator_fails_the_audit_at_ci[a]"
MUTANTS = "tests/property/test_mutants.py::test_the_mutant_is_killed[b-small]"
WRITER_MUTANTS = "tests/property/test_writer_mutants.py::test_the_writer_mutant_is_killed_at_its_assertion[c]"
EVERY = frozenset({READ, AUDIT, MUTANTS, WRITER_MUTANTS})
SELECTED: dict[str | None, frozenset[str]] = {None: EVERY, "none": frozenset({READ}), "only": EVERY - {READ}}


def test_the_matrix_check_passes_the_selection_meant() -> None:
    assert matrix_problems(workflow("ci.yml"), SELECTED) == []


def test_the_matrix_check_takes_a_new_module_of_mutant_searches_or_audit_controls_unedited() -> None:
    new = {
        "tests/unit/test_cli_mutants.py::test_a_cli_mutant_dies",
        "tests/unit/test_audit_controls_writer.py::test_a_writer_generator_fails_the_audit_at_ci[d]",
    }
    selected = SELECTED | {None: EVERY | new, "only": SELECTED["only"] | new}
    assert matrix_problems(workflow("ci.yml"), selected) == []


def controls_on_3_11_alone(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["strategy"]["matrix"]["python"] = ["3.11"]


def controls_job_running_none(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["steps"][3]["run"] = ci["jobs"]["controls"]["steps"][3]["run"].replace(
        "only", "none"
    )


def a_mutant_module_left_unselected(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    selected["only"] = selected["only"] - {WRITER_MUTANTS}


def a_plain_test_in_a_mutants_module(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    plain = "tests/property/test_record_mutants.py::test_the_reader_round_trips"
    selected[None] |= {plain}
    selected["only"] |= {plain}


def another_test_deselected(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    selected["none"] = frozenset()
    selected["only"] = EVERY


def plain_job_without_the_option(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["tests"]["steps"][3]["run"] = ci["jobs"]["tests"]["steps"][3]["run"].replace(
        " --property-controls none", ""
    )


def controls_excluding_3_15(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["strategy"]["matrix"]["exclude"] = [{"python": "3.15"}]


def the_tests_job_excluding_3_13(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["tests"]["strategy"]["matrix"]["exclude"] = [{"python": "3.13"}]


def controls_including_3_12(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["strategy"]["matrix"]["include"] = [{"python": "3.12"}]


def controls_step_skipped_on_3_15(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    pytest_step(ci["jobs"]["controls"])["if"] = "matrix.python != '3.15'"


def pull_requests_skipping_the_tests_step(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    pytest_step(ci["jobs"]["tests"])["if"] = "${{ github.event_name != 'pull_request' }}"


def controls_on_one_python(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["steps"][1]["with"]["python-version"] = "3.11"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (controls_on_3_11_alone, "Python 3.15 leaves out 1 of tests/property/test_mutants.py"),
        (controls_job_running_none, "Python 3.11 leaves out 1 of tests/property/test_mutants.py"),
        (
            a_mutant_module_left_unselected,
            "Python 3.15 leaves out 1 of tests/property/test_writer_mutants.py",
        ),
        (another_test_deselected, "Python 3.13 leaves out 1 of tests/unit/test_read.py"),
        (
            a_plain_test_in_a_mutants_module,
            "the controls' modules hold 1 of tests/property/test_record_mutants.py: no mutant search",
        ),
        (plain_job_without_the_option, "Python 3.12 runs 1 of tests/property/test_mutants.py"),
        (controls_excluding_3_15, "Python 3.15 leaves out 1 of tests/property/test_mutants.py"),
        (the_tests_job_excluding_3_13, "Python 3.13 leaves out 1 of tests/unit/test_read.py"),
        (controls_including_3_12, "Python 3.12 runs 1 of tests/property/test_mutants.py"),
        (
            controls_step_skipped_on_3_15,
            "controls's pytest step is skipped on Python 3.15 (pull_request, push",
        ),
        (
            pull_requests_skipping_the_tests_step,
            "tests's pytest step is skipped on Python 3.11 (pull_request)",
        ),
        (controls_on_one_python, "controls installs Python ['3.11'], not the matrix's"),
    ],
)
def test_the_matrix_check_can_fail(
    fault: Callable[[Workflow, dict[str | None, frozenset[str]]], None], problem: str
) -> None:
    ci, selected = copy.deepcopy(workflow("ci.yml")), dict(SELECTED)
    fault(ci, selected)
    found = matrix_problems(ci, selected)
    assert any(problem in line for line in found), found


# What each job's pytest commands select, in order, as the comment above each says: every argument that is
# not in `NOT_SELECTING`. A stray `-k`, `-m`, `--ignore`, plugin (`-p`, which can deselect anything) or other
# argument fails the check until it is written here too, beside the comment that gives its reason.
SELECTIONS: dict[str, list[list[str]]] = {
    # Every test but the mutant searches and the audit controls.
    "tests": [["--property-controls", "none"]],
    # The mutant searches and the audit controls alone.
    "controls": [["--property-controls", "only"]],
    # The property tests of one shard.
    "hypothesis": [["tests/property", "--shard", "${{matrix.shard}}"]],
    # Each commit before a pull request's head: the whole suite.
    "commit": [[]],
    "fuzz": [
        # The control's replay: the properties of the faults seeded in parse and in the read, which a plugin
        # seeds.
        [
            "-p",
            "tests.fuzz.seeded_fault",
            "tests/property/test_jsonio_properties.py",
            "tests/property/test_canonical_properties.py",
            "tests/property/test_hashing_properties.py",
            "tests/property/test_read_properties.py",
        ],
        # The replay: the property tests, but the writer schema's and the two JSON Schema libraries'
        # agreement, no fuzz target, and the mutant tables, which keep no example database.
        [
            "tests/property",
            "--ignore=tests/property/test_writer_properties.py",
            "--ignore=tests/property/test_writer_mutants.py",
            "--ignore=tests/property/test_validators_agree.py",
            "--ignore=tests/property/test_mutants.py",
            "--ignore=tests/property/test_record_mutants.py",
            "--ignore=tests/property/test_value_field_mutants.py",
            "--ignore=tests/property/test_condition_mutants.py",
        ],
    ],
}
# Arguments that choose no test: each with the value it takes, if any.
NOT_SELECTING = {
    "-n": 1,
    "--dist": 1,
    "-q": 0,
    "-ra": 0,
    "--strict-markers": 0,
    "--strict-config": 0,
    "--hypothesis-show-statistics": 0,
}
# What pytest reads options and plugins from, beside its command line.
PYTEST_ENVIRONMENT = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")


def selecting(command: list[str]) -> list[str]:
    """The arguments of a pytest command that may choose its tests."""
    found: list[str] = []
    words = iter(command)
    for word in words:
        if word in NOT_SELECTING:
            for _ in range(NOT_SELECTING[word]):
                next(words)
        elif not word.startswith("--junitxml="):
            found.append(word)
    return found


def keys(value: object) -> set[str]:
    """Every mapping key in a parsed workflow, at any depth."""
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return set(mapping) | {found for item in mapping.values() for found in keys(item)}
    if isinstance(value, list):
        return {found for item in cast(list[object], value) for found in keys(item)}
    return set()


def selection_problems(ci: Workflow) -> list[str]:
    """Where a job carries on after a failure, pytest takes options from the environment, or a pytest command
    selects other than `SELECTIONS` says."""
    problems: list[str] = []
    if "continue-on-error" in keys(ci):
        problems.append("ci.yml sets continue-on-error")
    problems += [f"ci.yml sets {name}" for name in PYTEST_ENVIRONMENT if name in keys(ci) or name in str(ci)]
    for job_id, job in ci["jobs"].items():
        commands = [selecting(command) for command in pytest_commands(job)]
        if commands != SELECTIONS.get(job_id, []):
            problems.append(f"{job_id}'s pytest commands select {commands}, not {SELECTIONS.get(job_id, [])}")
    return problems


def test_each_pytest_command_selects_what_its_comment_says() -> None:
    assert selection_problems(workflow("ci.yml")) == []


def run_of(ci: Workflow, job_id: str, words: str) -> dict[str, Any]:
    """The step of the job that runs the command holding `words`."""
    [found] = [found for found in ci["jobs"][job_id]["steps"] if words in str(found.get("run", ""))]
    return cast(dict[str, Any], found)


def a_keyword(ci: Workflow) -> None:
    run_of(ci, "tests", "pytest")["run"] += " -k 'not slow'"


def a_marker(ci: Workflow) -> None:
    found = run_of(ci, "hypothesis", "pytest")
    found["run"] = found["run"].replace("--shard", "-m 'not slow' --shard")


def another_ignore(ci: Workflow) -> None:
    found = run_of(ci, "fuzz", "--ignore")
    found["run"] = found["run"].replace(
        "tests/property ", "tests/property --ignore=tests/property/test_read_properties.py "
    )


def options_from_the_step(ci: Workflow) -> None:
    run_of(ci, "controls", "pytest")["env"]["PYTEST_ADDOPTS"] = "-x"


def options_from_the_workflow(ci: Workflow) -> None:
    ci["env"]["PYTEST_ADDOPTS"] = "--deselect tests/unit"


def options_exported(ci: Workflow) -> None:
    found = run_of(ci, "tests", "pytest")
    found["run"] = "export PYTEST_ADDOPTS=-x; " + found["run"]


def a_job_that_carries_on(ci: Workflow) -> None:
    ci["jobs"]["controls"]["continue-on-error"] = True


def a_step_that_carries_on(ci: Workflow) -> None:
    run_of(ci, "hypothesis", "pytest")["continue-on-error"] = True


def pytest_in_another_job(ci: Workflow) -> None:
    ci["jobs"]["static"]["steps"].append({"run": "uv run pytest tests/unit"})


def a_plugin(ci: Workflow) -> None:
    found = run_of(ci, "tests", "pytest")
    found["run"] = found["run"].replace("--property-controls none", "--property-controls none -p tests.drop")


def plugins_from_the_step(ci: Workflow) -> None:
    run_of(ci, "tests", "pytest")["env"]["PYTEST_PLUGINS"] = "tests.drop"


def plugins_exported(ci: Workflow) -> None:
    found = run_of(ci, "controls", "pytest")
    found["run"] = "export PYTEST_PLUGINS=tests.drop; " + found["run"]


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_keyword, "tests's pytest commands select"),
        (a_marker, "hypothesis's pytest commands select"),
        (another_ignore, "fuzz's pytest commands select"),
        (options_from_the_step, "sets PYTEST_ADDOPTS"),
        (options_from_the_workflow, "sets PYTEST_ADDOPTS"),
        (options_exported, "sets PYTEST_ADDOPTS"),
        (a_job_that_carries_on, "sets continue-on-error"),
        (a_step_that_carries_on, "sets continue-on-error"),
        (pytest_in_another_job, "static's pytest commands select [['tests/unit']]"),
        (a_plugin, "tests's pytest commands select [['--property-controls', 'none', '-p', 'tests.drop']]"),
        (plugins_from_the_step, "sets PYTEST_PLUGINS"),
        (plugins_exported, "sets PYTEST_PLUGINS"),
    ],
)
def test_the_selection_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = selection_problems(ci)
    assert any(problem in line for line in found), found


# Where a pytest job can stand when its durations steps come: the status functions there, the pytest step's
# outcome, and whether the steps must run, which is whenever pytest ran.
DURATIONS_STEPS = ("Test durations", "Keep the durations")
PASSED = {"success()": True, "failure()": False, "cancelled()": False, "always()": True}
FAILED = {"success()": False, "failure()": True, "cancelled()": False, "always()": True}
CANCELLED = {"success()": False, "failure()": False, "cancelled()": True, "always()": True}
STANDINGS = {
    "pytest passed": (PASSED, "success", True),
    "pytest failed": (FAILED, "failure", True),
    "the timeout cancelled pytest": (CANCELLED, "cancelled", True),
    "the checkout failed": (FAILED, "skipped", False),
    "a cancel came before pytest": (CANCELLED, "skipped", False),
}


def report_problems(ci: Workflow) -> list[str]:
    """Where a job whose pytest writes a JUnit report would not report its durations whenever pytest ran, or
    would where a failed checkout skipped pytest."""
    problems: list[str] = []
    for job_id, job in ci["jobs"].items():
        if not any(word.startswith("--junitxml=") for command in pytest_commands(job) for word in command):
            continue
        outcome = f"steps.{pytest_step(job).get('id')}.outcome"
        matrices = [
            {f"matrix.{key}": value for key, value in combination.items()}
            for combination in combinations(job["strategy"]["matrix"])
        ]
        for name, (standing, (status, pytest_outcome, wanted)) in itertools.product(
            DURATIONS_STEPS, STANDINGS.items()
        ):
            found = step(job, name)
            context = status | {outcome: pytest_outcome}
            if {truthy(evaluated(condition(found), matrix | context)) for matrix in matrices} != {wanted}:
                verb = "does not run" if wanted else "runs"
                problems.append(f"{job_id}'s step {name!r} {verb} when {standing}: if {found.get('if')!r}")
    return problems


def test_each_job_reports_its_durations_whenever_pytest_ran() -> None:
    assert report_problems(workflow("ci.yml")) == []


@pytest.mark.parametrize(
    ("written", "problem"),
    [
        ("success() || failure()", "'Test durations' does not run when the timeout cancelled pytest"),
        ("always()", "'Test durations' runs when the checkout failed"),
    ],
    ids=["not-after-a-cancel", "after-a-failed-checkout"],
)
def test_the_durations_check_can_fail(written: str, problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    step(ci["jobs"]["controls"], "Test durations")["if"] = written
    found = report_problems(ci)
    assert any(problem in line for line in found), found


def test_the_durations_check_fails_on_another_steps_outcome() -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    pytest_step(ci["jobs"]["hypothesis"])["id"] = "properties"
    with pytest.raises(AssertionError, match=r"does not know 'steps\.pytest\.outcome'"):
        report_problems(ci)


# How each pytest command starts: sent one SIGINT three minutes before its job's timeout, so that it writes
# the report of the tests that finished, with uv outside `timeout` (ci.yml says why, above the tests job's
# pytest step). `--foreground` is what makes it one: without it `timeout` signals its child and then its whole
# process group, and a second SIGINT in pytest-xdist's controller can end the run in an internal error.
# `JOB_MINUTES` repeats the job's `timeout-minutes`, which a step cannot read.
INTERRUPTED = 'uv run timeout --foreground --signal=INT "$((JOB_MINUTES - 3))m" pytest '
# Jobs whose pytest commands run without the interrupt, and why.
NOT_INTERRUPTED = {
    "fuzz": "its pytest commands write no report, and start late among the job's many steps",
}


def matrix_contexts(job: dict[str, Any]) -> list[dict[str, object]]:
    """The context of each combination of a job's matrix, for each event that runs the workflow; a list that
    an expression computes (`fromJSON(...)`) stands as one value, its text."""
    matrix = job.get("strategy", {}).get("matrix")
    if isinstance(matrix, dict):
        written = cast(dict[str, object], matrix)
        matrix = {key: [value] if isinstance(value, str) else value for key, value in written.items()}
    combinations_there: list[dict[str, object]] = combinations(matrix) if matrix is not None else [{}]
    return [
        {f"matrix.{key}": value for key, value in combination.items()} | {"github.event_name": event}
        for combination in combinations_there
        for event in EVENTS
    ]


def interrupt_problems(ci: Workflow) -> list[str]:
    """Where a job's pytest command does not run under the interrupt, or the minutes it is set from are not
    the job's timeout, on some event and combination."""
    problems: list[str] = []
    for job_id, job in ci["jobs"].items():
        if not pytest_commands(job) or job_id in NOT_INTERRUPTED:
            continue
        for found in job["steps"]:
            script = " ".join(str(found.get("run", "")).split()) + " "
            if len(pytest_commands({"steps": [found]})) != script.count(INTERRUPTED):
                problems.append(f"{job_id} runs pytest without {INTERRUPTED.strip()!r}: {script.strip()!r}")
        minutes = pytest_step(job).get("env", {}).get("JOB_MINUTES", job.get("env", {}).get("JOB_MINUTES"))
        for context in matrix_contexts(job):
            limit = setting(job.get("timeout-minutes"), context)
            interrupt = setting(minutes, context)
            where = ", ".join(f"{key} {value}" for key, value in context.items())
            if not equal(limit, interrupt):
                problems.append(
                    f"{job_id} times out at {limit!r} minutes, its JOB_MINUTES are {interrupt!r} ({where})"
                )
            elif as_number(limit) <= 3:
                problems.append(
                    f"{job_id} times out at {limit!r} minutes, no time for the interrupt ({where})"
                )
    return problems


def test_each_pytest_command_is_interrupted_three_minutes_before_its_job_times_out() -> None:
    assert interrupt_problems(workflow("ci.yml")) == []


def interrupt_by_another_signal(ci: Workflow) -> None:
    found = pytest_step(ci["jobs"]["controls"])
    found["run"] = found["run"].replace("--signal=INT", "--signal=TERM")


def no_interrupt(ci: Workflow) -> None:
    found = pytest_step(ci["jobs"]["tests"])
    found["run"] = found["run"].replace(' timeout --foreground --signal=INT "$((JOB_MINUTES - 3))m"', "")


def uv_in_the_group(ci: Workflow) -> None:
    found = pytest_step(ci["jobs"]["controls"])
    found["run"] = found["run"].replace(
        'uv run timeout --foreground --signal=INT "$((JOB_MINUTES - 3))m" pytest',
        'timeout --foreground --signal=INT "$((JOB_MINUTES - 3))m" uv run pytest',
    )


def interrupted_jobs(ci: Workflow) -> list[str]:
    """The jobs whose pytest commands run under the interrupt."""
    return [
        job_id for job_id, job in ci["jobs"].items() if pytest_commands(job) and job_id not in NOT_INTERRUPTED
    ]


def the_group_signalled_in(job_id: str) -> Callable[[Workflow], None]:
    """A fault: `--foreground` dropped from every pytest command of one job."""

    def fault(ci: Workflow) -> None:
        for found in ci["jobs"][job_id]["steps"]:
            if "run" in found:
                found["run"] = found["run"].replace(" --foreground", "")

    return fault


def a_second_command_without_it(ci: Workflow) -> None:
    found = pytest_step(ci["jobs"]["hypothesis"])
    found["run"] += " && uv run pytest tests/property --shard json"


def minutes_of_another_job(ci: Workflow) -> None:
    ci["jobs"]["controls"]["env"]["JOB_MINUTES"] = 30


def minutes_of_another_shard(ci: Workflow) -> None:
    hypothesis = ci["jobs"]["hypothesis"]
    hypothesis["env"]["JOB_MINUTES"] = hypothesis["env"]["JOB_MINUTES"].replace(
        "'agreement' && 360", "'agreement' && 350"
    )


def minutes_unset(ci: Workflow) -> None:
    del ci["jobs"]["tests"]["env"]["JOB_MINUTES"]


def a_timeout_with_no_room(ci: Workflow) -> None:
    ci["jobs"]["controls"]["timeout-minutes"] = ci["jobs"]["controls"]["env"]["JOB_MINUTES"] = 3


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (interrupt_by_another_signal, "controls runs pytest without"),
        (no_interrupt, "tests runs pytest without"),
        (uv_in_the_group, "controls runs pytest without"),
        (a_second_command_without_it, "hypothesis runs pytest without"),
        (minutes_of_another_job, "controls times out at 40 minutes, its JOB_MINUTES are 30"),
        (
            minutes_of_another_shard,
            "hypothesis times out at 360.0 minutes, its JOB_MINUTES are 350.0 (matrix.shard agreement, "
            "github.event_name schedule)",
        ),
        (minutes_unset, "tests times out at 40 minutes, its JOB_MINUTES are None"),
        (a_timeout_with_no_room, "controls times out at 3 minutes, no time for the interrupt"),
    ],
)
def test_the_interrupt_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = interrupt_problems(ci)
    assert any(problem in line for line in found), found


# The variable that makes the trace test of tests/unit/test_pre_review.py run. That test runs the whole suite
# once, so ci.yml sets it in one job of a run, not in each job that runs tests/unit (each per-commit job too).
TRACE_VARIABLE = "MATERICA_TRACE_SELECTION"
TRACE_TEST_FILE = REPOSITORY / "tests" / "unit" / "test_pre_review.py"


def trace_setters(ci: Workflow, event: str) -> list[str]:
    """The jobs, each combination of a matrix apart, that set the trace variable to `1` on `event`: in the
    workflow's, the job's or a step's environment, or by naming it in a script (an `export`, a prefix)."""
    setters: list[str] = []
    for job_id, job in ci["jobs"].items():
        steps: list[dict[str, Any]] = job.get("steps", [])
        environments = [ci.get("env", {}), job.get("env", {}), *(found.get("env", {}) for found in steps)]
        for context in matrix_contexts(job):
            if context["github.event_name"] != event:
                continue
            sets = any(
                as_text(setting(environment[TRACE_VARIABLE], context)) == "1"
                for environment in environments
                if TRACE_VARIABLE in environment
            ) or any(TRACE_VARIABLE in str(found.get("run", "")) for found in steps)
            if sets:
                where = ", ".join(
                    f"{key[len('matrix.') :]} {value}"
                    for key, value in context.items()
                    if key.startswith("matrix.")
                )
                setters.append(f"{job_id} ({where})" if where else job_id)
    return setters


def trace_problems(ci: Workflow, test_file: str) -> list[str]:
    """Where a run of ci.yml does not set the trace variable in exactly one job, on any event; or that job is
    not the `tests` job on the newest Python of its matrix, which the test's skip reason names."""
    problems: list[str] = []
    pythons: list[str] = ci["jobs"]["tests"]["strategy"]["matrix"]["python"]
    newest = max(pythons, key=lambda version: tuple(map(int, version.split("."))))
    for event in EVENTS:
        setters = trace_setters(ci, event)
        if not setters:
            problems.append(f"on {event} no job sets {TRACE_VARIABLE}, so the trace test never runs")
        elif len(setters) > 1:
            problems.append(f"on {event} {len(setters)} jobs set {TRACE_VARIABLE}, not one: {setters}")
        elif setters != [f"tests (python {newest})"]:
            problems.append(
                f"on {event} {setters} sets {TRACE_VARIABLE}, not the tests job on Python {newest}"
            )
    named = f"`tests` job on Python {newest}"
    if named not in test_file:
        problems.append(f"the trace test's skip reason does not name the {named}")
    return problems


def test_exactly_one_job_of_a_run_sets_the_variable_that_runs_the_trace_test() -> None:
    assert trace_problems(workflow("ci.yml"), TRACE_TEST_FILE.read_text(encoding="utf-8")) == []


def trace_set_nowhere(ci: Workflow) -> None:
    del pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE]


def trace_set_to_zero(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE] = "0"


def trace_set_in_a_second_job(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["controls"])["env"][TRACE_VARIABLE] = "1"


def trace_set_in_the_per_commit_job(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["commit"])["env"][TRACE_VARIABLE] = "1"


def trace_set_on_every_python(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE] = "1"


def trace_set_on_two_pythons(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE] = "${{ matrix.python != '3.13' && '1' || '' }}"


def trace_set_by_the_workflow(ci: Workflow) -> None:
    ci.setdefault("env", {})[TRACE_VARIABLE] = "1"


def trace_set_by_a_script(ci: Workflow) -> None:
    ci["jobs"]["static"]["steps"].append({"run": f"{TRACE_VARIABLE}=1 uv run pytest"})


def trace_set_on_another_python(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE] = "${{ matrix.python == '3.13' && '1' || '' }}"


def trace_set_in_the_controls_job_alone(ci: Workflow) -> None:
    del pytest_step(ci["jobs"]["tests"])["env"][TRACE_VARIABLE]
    pytest_step(ci["jobs"]["controls"])["env"][TRACE_VARIABLE] = "${{ matrix.python == '3.15' && '1' || '' }}"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (trace_set_nowhere, "on pull_request no job sets MATERICA_TRACE_SELECTION"),
        (trace_set_to_zero, "on pull_request no job sets MATERICA_TRACE_SELECTION"),
        (trace_set_in_a_second_job, "3 jobs set MATERICA_TRACE_SELECTION, not one"),
        (trace_set_in_the_per_commit_job, "2 jobs set MATERICA_TRACE_SELECTION, not one"),
        (trace_set_on_every_python, "5 jobs set MATERICA_TRACE_SELECTION, not one"),
        (trace_set_on_two_pythons, "4 jobs set MATERICA_TRACE_SELECTION, not one"),
        (trace_set_by_the_workflow, "jobs set MATERICA_TRACE_SELECTION, not one"),
        (
            trace_set_by_a_script,
            "2 jobs set MATERICA_TRACE_SELECTION, not one: ['static', 'tests (python 3.15)']",
        ),
        (trace_set_on_another_python, "not the tests job on Python 3.15"),
        (trace_set_in_the_controls_job_alone, "not the tests job on Python 3.15"),
    ],
)
def test_the_trace_variable_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = trace_problems(ci, TRACE_TEST_FILE.read_text(encoding="utf-8"))
    assert any(problem in line for line in found), found


def test_the_trace_variable_check_finds_a_skip_reason_that_names_another_job() -> None:
    text = TRACE_TEST_FILE.read_text(encoding="utf-8")
    assert "`tests` job on Python 3.15" in text
    found = trace_problems(workflow("ci.yml"), text.replace("`tests` job on Python 3.15", "`tests` job"))
    assert any("skip reason does not name the `tests` job on Python 3.15" in line for line in found), found


def interrupt_drift(words: Sequence[str]) -> bool:
    """Whether a test that interrupts pytest with `words` interrupts it otherwise than the workflows do."""
    return f"uv run {' '.join(words)} " not in INTERRUPTED


@pytest.mark.parametrize(
    ("words", "drifts"),
    [
        (INTERRUPT_AS_CI, False),
        (tuple(word for word in INTERRUPT_AS_CI if word != "--foreground"), True),
        (("timeout", "--signal=INT"), True),
        (("timeout", "--foreground", "--signal=TERM"), True),
    ],
    ids=["as-the-test-does", "without-foreground", "the-old-words", "another-signal"],
)
def test_the_interrupted_run_test_interrupts_as_the_workflows_do(words: Sequence[str], drifts: bool) -> None:
    """tests/unit/test_report_test_durations.py interrupts a sample run with `INTERRUPT_AS_CI`; the first
    case holds those words to the workflows' (`INTERRUPTED`), the others that the comparison can fail."""
    assert interrupt_drift(words) is drifts


def test_every_pytest_job_with_the_interrupt_is_one_the_foreground_control_drops_it_from() -> None:
    """The control below runs once per job that has the interrupt; this holds it to every such job, so that a
    job added later is dropped from too, and there are jobs to drop it from."""
    assert interrupted_jobs(workflow("ci.yml")) == ["tests", "controls", "hypothesis", "commit"]


@pytest.mark.parametrize("job_id", interrupted_jobs(workflow("ci.yml")))
def test_a_job_whose_timeout_signals_the_group_fails_the_interrupt_check(job_id: str) -> None:
    """Without `--foreground`, `timeout` signals pytest and then its process group, and the controller of
    pytest-xdist can meet the second SIGINT inside a lock: dropped from any one job, the check names it."""
    ci = copy.deepcopy(workflow("ci.yml"))
    the_group_signalled_in(job_id)(ci)
    found = interrupt_problems(ci)
    assert [line for line in found if line.startswith(f"{job_id} runs pytest without")], found
    assert [line for line in found if not line.startswith(f"{job_id} ")] == [], found


# The slowest run of each Hypothesis shard measured on CI, in minutes, by profile, with the five shards of
# today's map (ci.yml, above the job): at `ci` in run 39002323592, at `deep` in manual run 39002750375, both
# 2026-10-17. A shard not measured yet is not held.
MEASURED_ON_CI = {
    "ci": {"agreement": 5.93, "writer": 5.17, "records": 2.48, "json": 1.62, "step8_mutants": 1.62},
    "deep": {"writer": 63.63, "agreement": 47.02, "records": 31.40, "json": 14.13, "step8_mutants": 1.55},
}
PROFILE_EVENTS = {"ci": "pull_request", "deep": "schedule"}


def margin_problems(ci: Workflow) -> list[str]:
    """Where a Hypothesis shard's interrupt, three minutes before its timeout, leaves less than twice its
    slowest run measured on CI: a runner half as fast would lose the run."""
    job = ci["jobs"]["hypothesis"]
    problems: list[str] = []
    for profile, measured in MEASURED_ON_CI.items():
        for shard, minutes in measured.items():
            context = {"github.event_name": PROFILE_EVENTS[profile], "matrix.shard": shard}
            interrupt = as_number(setting(job["timeout-minutes"], context)) - 3
            if interrupt < 2 * minutes:
                problems.append(
                    f"hypothesis ({profile}, {shard}) is interrupted at {interrupt:g} minutes, less than "
                    f"twice its {minutes:g} measured on CI"
                )
    shards = set(job["strategy"]["matrix"]["shard"])
    problems += [
        f"a measured shard the matrix no longer has: {shard}"
        for profile in MEASURED_ON_CI.values()
        for shard in sorted(profile.keys() - shards)
    ]
    return problems


def test_each_hypothesis_shard_has_twice_its_slowest_run_on_ci() -> None:
    assert margin_problems(workflow("ci.yml")) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (
            "matrix.shard == 'records' && 90 || 45",
            "45",
            "hypothesis (deep, records) is interrupted at 42 minutes, less than twice its 31.4 ",
        ),
        (
            "matrix.shard == 'writer' && 75",
            "matrix.shard == 'writer' && 12",
            "hypothesis (ci, writer) is interrupted at 9 minutes, less than twice its 5.17",
        ),
    ],
    ids=["records-deep-at-45", "writer-ci-at-12"],
)
def test_the_margin_check_can_fail(old: str, new: str, problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    job = ci["jobs"]["hypothesis"]
    assert job["timeout-minutes"].count(old) == 1
    job["timeout-minutes"] = job["timeout-minutes"].replace(old, new)
    found = margin_problems(ci)
    assert any(problem in line for line in found), found


def test_the_margin_check_finds_a_measured_shard_gone() -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    ci["jobs"]["hypothesis"]["strategy"]["matrix"]["shard"].remove("json")
    assert "a measured shard the matrix no longer has: json" in margin_problems(ci)


# The caps of jobs at once (maintainer, 2026-10-17). A step of the job a capped job needs checks a repository
# variable, or the workflow's default where it is unset, on every run, fails where it is not a whole number
# from 1 to 20, and writes the value it took as an output of that job, which the capped job's `max-parallel`
# parses: the variable is read once, by the check, so that a value changed after it, or before failed jobs
# are re-run, does not reach a capped job. GitHub documents no bound on `max-parallel`, nor what it does with
# 0, a negative number or a fraction, so a capped job is given no value the check refuses.
CAP_STEP, CAP_STEP_ID = "The cap of jobs at once is a whole number from 1 to 20", "cap"
CAP_REFUSAL = "::error title=Runner cap::the repository variable {variable} is "
# The cap step's output, which its job gives as its own.
CAP_STEP_OUTPUT = "max_parallel"
CAP_OUTPUT = f"${{{{ steps.{CAP_STEP_ID}.outputs.{CAP_STEP_OUTPUT} }}}}"


class Cap(NamedTuple):
    """A capped job of a workflow, the job that checks its cap and the output it gives it by, the variable
    and its default."""

    workflow: str
    job: str
    checker: str
    output: str
    variable: str
    default: str


CAPS = (
    Cap("ci.yml", "commit", "gate", "per_commit_max_parallel", "PER_COMMIT_MAX_PARALLEL", "6"),
    Cap("ci.yml", "site_commit", "gate", "per_commit_max_parallel", "PER_COMMIT_MAX_PARALLEL", "6"),
    Cap("repeat.yml", "runs", "request", "max_parallel", "REPEAT_MAX_PARALLEL", "10"),
    Cap("mutants.yml", "mutants", "request", "max_parallel", "MUTANT_MAX_PARALLEL", "10"),
)
# Values of a cap's variable the check takes, beside its being unset, and values it refuses: out of range;
# written otherwise than plainly as a whole number, which fromJSON may still parse (`6.0`, `1e1`, ` 6`); not a
# number; a command; a line break and a workflow command, which a refusal that printed the value as it is
# would give the runner as a command of its own (`workflow_commands`); or a digit of another script, which a
# range such as `[1-9]` takes in a locale that collates it there (`CAP_LOCALES`), and fromJSON cannot parse.
CAPS_TAKEN = ("1", "9", "10", "19", "20")
CAPS_REFUSED = (
    "0",
    "-1",
    "21",
    "100",
    "6.0",
    "1e1",
    "010",
    "+6",
    "0x6",
    " 6",
    "6 ",
    "6\n",
    "six",
    "true",
    "null",
    "[6]",
    '"6"',
    "$(touch ran)",
    "a[$(touch ran)]",
    "6;touch ran",
    "6\n::warning title=injected::x",
    "6\r::notice::x",
    "6\n##[warning]x",
    "\u0666",
    "\uff16",
    "\u00b2",
)
# The locales each check runs under: GitHub's runner's, and one whose collation puts other scripts' digits in
# bash's ranges (glibc's en_US.UTF-8 takes `\u0666`, ARABIC-INDIC DIGIT SIX, in `[1-9]`).
CAP_LOCALES = ("C.UTF-8", "en_US.UTF-8")


def workflow_commands(printed: str) -> list[str]:
    """The lines of a step's output that GitHub's runner reads as workflow commands. It splits the output at
    `\r\n`, `\r` and `\n`, and takes a line that starts with `::` once its leading space is trimmed, or one
    that holds the legacy `##[` anywhere (actions/runner, `ActionCommand.TryParseV2` and `TryParse`)."""
    lines = re.split(r"\r\n|\r|\n", printed)
    return [line for line in lines if line.lstrip().startswith("::") or "##[" in line]


def test_the_runner_reads_these_lines_as_workflow_commands() -> None:
    printed = "a\r::x::1\n  ::y::2\r\nb ::z\nc ##[warning]w\r\n\n::\nd # [e]"
    assert workflow_commands(printed) == ["::x::1", "  ::y::2", "c ##[warning]w", "::"]


def cap_expression(cap: Cap) -> str:
    """A capped job's `max-parallel`: its checker's output, parsed."""
    return f"${{{{ fromJSON(needs.{cap.checker}.outputs.{cap.output}) }}}}"


def cap_checked(variable: str, default: str) -> str:
    """The value the cap step checks: the variable, or the default where it is unset."""
    return f"${{{{ vars.{variable} || '{default}' }}}}"


def cap_problems(found: Workflow, cap: Cap) -> list[str]:
    """Where the capped job's `max-parallel` is not its checker's output, parsed, exactly; it can start
    though the job that checks its cap failed; or that job does not check the variable, with its default, in
    one step, on every run, carries on after the check failed, or gives as its output another value than the
    step's.

    A capped job starts on its checker's success alone: on GitHub's implicit `success()`, so it calls no
    status function, `success()` included, since `success() || ...` starts it after a failure too. Nor does
    the checker or its cap step set `continue-on-error`, with which the job, or the step, passes though the
    check failed."""
    job = found["jobs"][cap.job]
    problems: list[str] = []
    expected = cap_expression(cap)
    written = job.get("strategy", {}).get("max-parallel")
    if written != expected:
        problems.append(f"the {cap.job} job runs {written!r} at once, not {expected}")
    needs = job.get("needs", [])
    if cap.checker not in ([needs] if isinstance(needs, str) else needs) or STATUS_FUNCTION.search(
        str(job.get("if", ""))
    ):
        problems.append(
            f"the {cap.job} job can start without {cap.checker}, which checks its cap, succeeding"
        )
    checks = [each for each in found["jobs"][cap.checker]["steps"] if each.get("name") == CAP_STEP]
    if len(checks) != 1:
        return [*problems, f"{cap.checker} checks the cap in {len(checks)} steps"]
    checked = {"VARIABLE": cap.variable, "MAX_PARALLEL": cap_checked(cap.variable, cap.default)}
    if checks[0].get("env") != checked:
        problems.append(f"{cap.checker} checks {checks[0].get('env')!r}, not {checked}")
    if "if" in checks[0]:
        problems.append(f"{cap.checker} checks the cap only if {checks[0]['if']!r}")
    if checks[0].get("id") != CAP_STEP_ID:
        problems.append(f"{cap.checker}'s cap step has the id {checks[0].get('id')!r}, not {CAP_STEP_ID!r}")
    gives = found["jobs"][cap.checker].get("outputs", {}).get(cap.output)
    if gives != CAP_OUTPUT:
        problems.append(f"{cap.checker}'s output {cap.output} is {gives!r}, not {CAP_OUTPUT}")
    for where, setting in (
        (f"the {cap.checker} job", found["jobs"][cap.checker]),
        (f"the {cap.checker} job's cap step", checks[0]),
    ):
        if "continue-on-error" in setting:
            problems.append(f"{where} carries on after the cap check fails: {setting['continue-on-error']!r}")
    return problems


def cap_used(written: object, context: Mapping[str, object]) -> object:
    """A `max-parallel` as GitHub computes it in `context`."""
    if isinstance(written, str) and (inner := re.fullmatch(r"\$\{\{(.*)\}\}", written, re.S)):
        return evaluated(inner[1], context)
    return written


def cap_check_problems(
    found: Workflow, cap: Cap, directory: Path, locales: Sequence[str] = CAP_LOCALES
) -> list[str]:
    """Where the cap step, run as written under each of `locales`, takes a value of the variable outside 1
    to 20 or refuses one inside, lets a value run a command, refuses one without naming the variable or with
    a workflow command beside its own, or takes one that the capped job computes as another number, the
    variable unset included, from the output the step writes, which it writes for no value it refuses; or
    where a locale is not installed, so that the check would run under bash's fallback instead."""
    check = step(found["jobs"][cap.checker], CAP_STEP)
    written = found["jobs"][cap.job].get("strategy", {}).get("max-parallel")
    tree = directory / "tree"
    tree.mkdir(exist_ok=True)
    problems: list[str] = []
    cases = [
        ("", True),
        *((value, True) for value in CAPS_TAKEN),
        *((value, False) for value in CAPS_REFUSED),
    ]
    for (value, taken), locale in itertools.product(cases, locales):
        context = {f"vars.{cap.variable}": value}
        base = dict(os.environ, LANG=locale, LC_ALL=locale)
        status, outputs, printed = run_step(check, context, tree, base=base, scratch=directory)
        if "setlocale" in printed:
            problems.append(f"the locale {locale} is not installed here, so the check is not run under it")
            continue
        if (tree / "ran").exists():
            problems.append(f"{cap.variable} {value!r} ran a command")
            (tree / "ran").unlink()
        if not taken:
            if status == 0:
                problems.append(f"the check takes {cap.variable} {value!r} under {locale}")
            elif CAP_REFUSAL.format(variable=cap.variable) not in printed:
                problems.append(f"the check refuses {cap.variable} {value!r} without naming it: {printed!r}")
            elif len(commands := workflow_commands(printed)) != 1 or not commands[0].startswith(
                CAP_REFUSAL.format(variable=cap.variable)
            ):
                problems.append(
                    f"the check's refusal of {cap.variable} {value!r} prints {len(commands)} workflow "
                    f"commands: {commands!r}"
                )
            if outputs:
                problems.append(f"the check refuses {cap.variable} {value!r} but writes {outputs!r}")
        elif status != 0:
            problems.append(f"the check refuses {cap.variable} {value!r} under {locale}")
        else:
            took = rendered(str(check.get("env", {}).get("MAX_PARALLEL")), context)
            given = context | {f"needs.{cap.checker}.outputs.{cap.output}": outputs.get(CAP_STEP_OUTPUT)}
            try:
                used = cap_used(written, given)
            except ValueError as error:
                used = f"nothing ({error})"
            if not re.fullmatch(r"[0-9]+", took) or type(used) is not int or used != int(took):
                problems.append(f"the {cap.job} job runs {used!r} at once where the check took {took!r}")
    return problems


@pytest.mark.parametrize("cap", CAPS, ids=lambda cap: cap.job)
def test_each_cap_is_a_whole_number_from_1_to_20_or_its_check_fails(cap: Cap, tmp_path: Path) -> None:
    assert cap_problems(workflow(cap.workflow), cap) == []
    assert cap_check_problems(workflow(cap.workflow), cap, tmp_path) == []


def the_cap_check_left_out(found: Workflow, cap: Cap) -> None:
    job = found["jobs"][cap.checker]
    job["steps"] = [each for each in job["steps"] if each.get("name") != CAP_STEP]


def another_default_checked(found: Workflow, cap: Cap) -> None:
    step(found["jobs"][cap.checker], CAP_STEP)["env"]["MAX_PARALLEL"] = cap_checked(cap.variable, "20")


def another_variable_checked(found: Workflow, cap: Cap) -> None:
    step(found["jobs"][cap.checker], CAP_STEP)["env"] = {
        "VARIABLE": "MAX_PARALLEL",
        "MAX_PARALLEL": cap_checked("MAX_PARALLEL", cap.default),
    }


def the_check_on_a_push_alone(found: Workflow, cap: Cap) -> None:
    step(found["jobs"][cap.checker], CAP_STEP)["if"] = "github.event_name == 'push'"


def the_job_started_whatever_the_check(found: Workflow, cap: Cap) -> None:
    job = found["jobs"][cap.job]
    job["if"] = f"always() && ({job['if']})" if "if" in job else "always()"


def the_job_needing_no_check(found: Workflow, cap: Cap) -> None:
    found["jobs"][cap.job]["needs"] = []


def the_job_started_on_a_failed_check(found: Workflow, cap: Cap) -> None:
    """No `always()`, `failure()` or `cancelled()`, but a status function, so no implicit `success()`."""
    found["jobs"][cap.job]["if"] = f"success() || needs.{cap.checker}.result == 'failure'"


def the_check_carrying_on(found: Workflow, cap: Cap) -> None:
    step(found["jobs"][cap.checker], CAP_STEP)["continue-on-error"] = True


def the_checker_carrying_on(found: Workflow, cap: Cap) -> None:
    found["jobs"][cap.checker]["continue-on-error"] = True


def the_cap_given_by_another_step(found: Workflow, cap: Cap) -> None:
    found["jobs"][cap.checker]["outputs"][cap.output] = "${{ steps.other.outputs.max_parallel }}"


def the_cap_not_given(found: Workflow, cap: Cap) -> None:
    del found["jobs"][cap.checker]["outputs"][cap.output]


def the_check_without_its_id(found: Workflow, cap: Cap) -> None:
    del step(found["jobs"][cap.checker], CAP_STEP)["id"]


@pytest.mark.parametrize("cap", CAPS, ids=lambda cap: cap.job)
@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (the_cap_check_left_out, "checks the cap in 0 steps"),
        (another_default_checked, "|| '20' }}"),
        (another_variable_checked, "vars.MAX_PARALLEL"),
        (the_check_on_a_push_alone, "checks the cap only if"),
        (the_job_started_whatever_the_check, "can start without"),
        (the_job_needing_no_check, "can start without"),
        (the_job_started_on_a_failed_check, "can start without"),
        (the_check_carrying_on, "job's cap step carries on after the cap check fails: True"),
        (the_checker_carrying_on, "job carries on after the cap check fails: True"),
        (the_cap_given_by_another_step, "is '${{ steps.other.outputs.max_parallel }}', not"),
        (the_cap_not_given, "is None, not ${{ steps.cap.outputs.max_parallel }}"),
        (the_check_without_its_id, "cap step has the id None"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_cap_check_can_fail(fault: Callable[[Workflow, Cap], None], problem: str, cap: Cap) -> None:
    found = copy.deepcopy(workflow(cap.workflow))
    fault(found, cap)
    problems = cap_problems(found, cap)
    assert any(problem in line for line in problems), problems


CAP_CONDITION = '[[ ! "$MAX_PARALLEL" =~ ^([123456789]|1[0123456789]|20)$ ]]'


@pytest.mark.parametrize("cap", CAPS, ids=lambda cap: cap.job)
@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("|20)$", "|2[0123456789])$", "the check takes {variable} '21'"),
        ("^([123456789]|", "^([0123456789]|", "the check takes {variable} '0'"),
        (
            "^([123456789]|1[0123456789]|20)$",
            "([123456789]|1[0123456789]|20)",
            "the check takes {variable} '6.0'",
        ),
        (
            "^([123456789]|1[0123456789]|20)$",
            "^([1-9]|1[0-9]|20)$",
            "the check takes {variable} '\u0666' under en_US.UTF-8",
        ),
        (
            CAP_CONDITION,
            "(( MAX_PARALLEL < 1 || MAX_PARALLEL > 20 ))",
            "{variable} 'a[$(touch ran)]' ran a command",
        ),
        ("exit 1", "exit 0", "the check takes {variable} '0'"),
        (
            "the repository variable $VARIABLE is",
            "the cap is",
            "the check refuses {variable} '0' without naming it",
        ),
        (
            "printf -v shown '%q' \"$MAX_PARALLEL\"",
            'shown="$MAX_PARALLEL"',
            "the check's refusal of {variable} '6\\n::warning title=injected::x' prints 2 workflow commands",
        ),
        (
            'if [[ ! "$MAX_PARALLEL"',
            'echo "$VARIABLE: at most $MAX_PARALLEL jobs at once"\nif [[ ! "$MAX_PARALLEL"',
            "the check's refusal of {variable} '6\\r::notice::x' prints 2 workflow commands",
        ),
        (
            'if [[ ! "$MAX_PARALLEL"',
            'echo "max_parallel=$MAX_PARALLEL" >> "$GITHUB_OUTPUT"\nif [[ ! "$MAX_PARALLEL"',
            "the check refuses {variable} '0' but writes {{'max_parallel': '0'}}",
        ),
    ],
    ids=[
        "a-ceiling-raised",
        "zero-taken",
        "unanchored",
        "ranges",
        "bash-arithmetic",
        "refusal-ignored",
        "refusal-unnamed",
        "refusal-unescaped",
        "value-printed-first",
        "written-before-the-check",
    ],
)
def test_the_cap_check_as_run_can_fail(old: str, new: str, problem: str, cap: Cap, tmp_path: Path) -> None:
    found = copy.deepcopy(workflow(cap.workflow))
    check = step(found["jobs"][cap.checker], CAP_STEP)
    assert check["run"].count(old) == 1
    check["run"] = check["run"].replace(old, new)
    problems = cap_check_problems(found, cap, tmp_path)
    assert any(problem.format(variable=cap.variable) in line for line in problems), problems


@pytest.mark.parametrize("cap", CAPS, ids=lambda cap: cap.job)
def test_the_cap_check_finds_a_locale_not_installed(cap: Cap, tmp_path: Path) -> None:
    """So that a runner without one of `CAP_LOCALES` fails the check, rather than run it under bash's
    fallback, the C locale, and pass without trying the other."""
    problems = cap_check_problems(workflow(cap.workflow), cap, tmp_path, ("C.UTF-8", "xx_XX.UTF-8"))
    assert "the locale xx_XX.UTF-8 is not installed here, so the check is not run under it" in problems
    assert not [line for line in problems if "xx_XX" not in line], problems


def test_the_cap_check_finds_a_job_that_computes_another_cap(tmp_path: Path) -> None:
    """A job that reads the variable again, of another default; a check that writes another value than it
    took; a job that runs a constant; and one that reads the output as a string: each disagrees with the
    check on some value it takes."""
    cap = CAPS[0]
    found = copy.deepcopy(workflow(cap.workflow))
    found["jobs"][cap.job]["strategy"]["max-parallel"] = f"${{{{ fromJSON(vars.{cap.variable} || '20') }}}}"
    assert "the commit job runs 20 at once where the check took '6'" in cap_check_problems(
        found, cap, tmp_path
    )
    found = copy.deepcopy(workflow(cap.workflow))
    check = step(found["jobs"][cap.checker], CAP_STEP)
    assert check["run"].count("max_parallel=$MAX_PARALLEL") == 1
    check["run"] = check["run"].replace("max_parallel=$MAX_PARALLEL", "max_parallel=6")
    assert "the commit job runs 6 at once where the check took '10'" in cap_check_problems(
        found, cap, tmp_path
    )
    found = copy.deepcopy(workflow(cap.workflow))
    found["jobs"][cap.job]["strategy"]["max-parallel"] = 6
    assert "the commit job runs 6 at once where the check took '10'" in cap_check_problems(
        found, cap, tmp_path
    )
    found["jobs"][cap.job]["strategy"]["max-parallel"] = (
        f"${{{{ needs.{cap.checker}.outputs.{cap.output} }}}}"
    )
    assert "the commit job runs '10' at once where the check took '10'" in cap_check_problems(
        found, cap, tmp_path
    )


# A repository variable, as any of GitHub's expressions reads it: `vars.NAME`, `vars['NAME']` or `vars` whole.
VARIABLE_READ = re.compile(r"\bvars\b")


def unchecked_variables(loaded: dict[str, Workflow]) -> list[str]:
    """Where a workflow reads a repository variable but in the step that checks a cap of it (`CAPS`), as
    `cap_checked` gives it. The capped jobs read the checked value from that step's output, so a variable read
    anywhere else, a new cap's or a capped job's own, is read unchecked. An `if` is read as an expression
    whole, anything else for what its `${{ }}` hold."""
    checked: set[tuple[str, tuple[str, ...], str]] = set()
    for cap in CAPS:
        steps = loaded.get(cap.workflow, {}).get("jobs", {}).get(cap.checker, {}).get("steps", [])
        value = cap_checked(cap.variable, cap.default)
        checked |= {
            (cap.workflow, ("jobs", cap.checker, "steps", str(index), "env", "MAX_PARALLEL"), value)
            for index, found in enumerate(steps)
            if found.get("name") == CAP_STEP
        }
    problems: list[str] = []
    for name, found in loaded.items():
        for at, text in places(found):
            expressions = re.findall(r"\$\{\{(.*?)\}\}", text, re.S) + ([text] if at[-1:] == ("if",) else [])
            if any(VARIABLE_READ.search(each) for each in expressions) and (name, at, text) not in checked:
                problems.append(f"{name} reads a repository variable at {'.'.join(at)}: {text!r}")
    return problems


def test_every_variable_a_workflow_reads_is_read_by_a_cap_check() -> None:
    assert unchecked_variables(workflows()) == []


def a_new_cap_unchecked(loaded: dict[str, Workflow]) -> None:
    strategy = loaded["ci.yml"]["jobs"]["tests"]["strategy"]
    strategy["max-parallel"] = "${{ fromJSON(vars.TESTS_MAX_PARALLEL || '5') }}"


def a_capped_job_reading_its_variable(loaded: dict[str, Workflow]) -> None:
    strategy = loaded["repeat.yml"]["jobs"]["runs"]["strategy"]
    strategy["max-parallel"] = "${{ fromJSON(vars.REPEAT_MAX_PARALLEL || '10') }}"


def a_job_run_by_a_variable(loaded: dict[str, Workflow]) -> None:
    loaded["pages.yml"]["jobs"]["deploy"]["if"] = "vars['DEPLOY'] == 'true'"


def the_variable_in_the_checks_script(loaded: dict[str, Workflow]) -> None:
    check = step(loaded["ci.yml"]["jobs"]["gate"], CAP_STEP)
    check["run"] = check["run"].replace('"$MAX_PARALLEL" =~', '"${{ vars.PER_COMMIT_MAX_PARALLEL }}" =~', 1)


def another_default_checked_too(loaded: dict[str, Workflow]) -> None:
    step(loaded["repeat.yml"]["jobs"]["request"], CAP_STEP)["env"]["MAX_PARALLEL"] = cap_checked(
        "REPEAT_MAX_PARALLEL", "20"
    )


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_new_cap_unchecked, "ci.yml reads a repository variable at jobs.tests.strategy.max-parallel"),
        (a_capped_job_reading_its_variable, "repeat.yml reads a repository variable at jobs.runs.strategy"),
        (a_job_run_by_a_variable, "pages.yml reads a repository variable at jobs.deploy.if"),
        (the_variable_in_the_checks_script, "ci.yml reads a repository variable at jobs.gate.steps.1.run"),
        (another_default_checked_too, "repeat.yml reads a repository variable at jobs.request.steps.5.env"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_variable_check_can_fail(fault: Callable[[dict[str, Workflow]], None], problem: str) -> None:
    loaded = copy.deepcopy(workflows())
    fault(loaded)
    problems = unchecked_variables(loaded)
    assert [line for line in problems if problem in line] == problems != [], problems


# The per-commit job (ci.yml says why, above it): the checks an agent runs on a commit locally, every
# commit but a pull request's head on its own, at most PER_COMMIT_MAX_PARALLEL at once (`CAPS`), and a pass
# kept under the commit's tree and the workflow's blob, so that a tree passed under the same checks is not
# checked again.
PER_COMMIT_FAST_CHECKS = ("uv run ruff check", "uv run ruff format --check", "uv run mypy", "uv run pyright")
CACHE_HIT = "steps.passed.outputs.cache-hit"
# The steps that make the key of a pass and write the pass, which check nothing.
KEYING = {"tree", "keep"}


def commands(job: dict[str, Any]) -> list[str]:
    """Each line of the job's scripts, with `uv run`'s choice of lock and Python left out."""
    return [
        re.sub(r"^uv run (--locked )?(--python [\d.]+ )?", "uv run ", line.strip())
        for found in job["steps"]
        for line in str(found.get("run", "")).splitlines()
        if line.strip()
    ]


def uses(found: dict[str, Any], action: str) -> bool:
    return str(found.get("uses", "")).startswith(f"{action}@")


def per_commit_problems(ci: Workflow) -> list[str]:
    """Where the per-commit job does not check each listed commit on its own, as an agent does locally, or
    could take a pass under other checks, or of another tree, for this one's."""
    job = ci["jobs"]["commit"]
    steps: list[dict[str, Any]] = job["steps"]
    problems: list[str] = []
    strategy = job.get("strategy", {})
    if strategy.get("matrix") != {"sha": "${{ fromJSON(needs.gate.outputs.commits) }}"}:
        problems.append(f"the per-commit job's matrix is {strategy.get('matrix')!r}")
    if strategy.get("fail-fast") is not False:
        problems.append(f"the per-commit job's fail-fast is {strategy.get('fail-fast')!r}")
    problems += cap_problems(ci, CAPS[0])
    if not uses(steps[0], "actions/checkout") or steps[0].get("with", {}).get("ref") != "${{ matrix.sha }}":
        problems.append("the per-commit job does not check its commit out first")
    pythons = [
        found.get("with", {}).get("python-version") for found in steps if uses(found, "astral-sh/setup-uv")
    ]
    if pythons != ["3.15"]:
        problems.append(f"the per-commit job installs Python {pythons}")
    ran = commands(job)
    generators = [line for line in commands(ci["jobs"]["generated"]) if "scripts/gen_" in line]
    wheel = [
        line for line in commands(ci["jobs"]["static"]) if line == "uv build" or "check_wheel.py" in line
    ]
    if len(wheel) != 2:
        problems.append(f"the static job builds and checks the wheel by {wheel!r}")
    problems += [
        f"the per-commit job does not run {line!r}"
        for line in [*PER_COMMIT_FAST_CHECKS, *generators, *wheel]
        if line not in ran
    ]
    if pytest_step(job).get("env", {}).get("MATERICA_HYPOTHESIS_PROFILE") != "dev":
        problems.append("the per-commit job's pytest does not run at the `dev` profile")
    if (
        ci["jobs"]["gate"]["outputs"].get("workflow_blob")
        != f"${{{{ steps.{GATE_STEP_ID}.outputs.workflow_blob }}}}"
    ):
        problems.append("the gate does not give its workflow's blob")
    lookups = [index for index, found in enumerate(steps) if uses(found, "actions/cache/restore")]
    saves = [index for index, found in enumerate(steps) if uses(found, "actions/cache/save")]
    if len(lookups) != 1 or len(saves) != 1:
        return [
            *problems,
            f"the per-commit job looks a pass up {len(lookups)} times and keeps it {len(saves)}",
        ]
    lookup, save = steps[lookups[0]], steps[saves[0]]
    if lookup.get("id") != "passed" or lookup.get("with", {}).get("lookup-only") is not True:
        problems.append("the per-commit job's lookup is not `passed`, looking up only")
    if {key: lookup["with"].get(key) for key in ("key", "path")} != {
        key: save["with"].get(key) for key in ("key", "path")
    }:
        problems.append("the per-commit job keeps a pass under another key or path than it looks up")
    # Every step that runs a command, but the key's and the one that writes the pass, is a check: each comes
    # after the lookup and before the pass is written and kept.
    written = [index for index, found in enumerate(steps) if found.get("id") == "keep"]
    checks = [index for index, found in enumerate(steps) if "run" in found and found.get("id") not in KEYING]
    if len(written) != 1 or not all(lookups[0] < index < written[0] < saves[0] for index in checks):
        problems.append("the per-commit job checks something outside its lookup and its keeping of the pass")
    for index, found in enumerate(steps[lookups[0] + 1 :], lookups[0] + 1):
        context = SO_FAR_SUCCEEDED | {"matrix.sha": "0" * 40}
        on_hit = truthy(evaluated(condition(found), context | {CACHE_HIT: "true"}))
        misses = [truthy(evaluated(condition(found), context | {CACHE_HIT: miss})) for miss in ("false", "")]
        if on_hit or not all(misses):
            runs = "on a pass found" if on_hit else "not on a miss"
            problems.append(f"the per-commit job's step {index} runs {runs}: if {found.get('if')!r}")
    failed = {"success()": False, "failure()": True, "cancelled()": False, "always()": True, CACHE_HIT: ""}
    if truthy(evaluated(condition(save), failed | {"matrix.sha": "0" * 40})):
        problems.append(f"the per-commit job keeps a pass after a failure: if {save.get('if')!r}")
    return problems


def test_the_per_commit_job_checks_each_listed_commit_as_an_agent_does_locally() -> None:
    assert per_commit_problems(workflow("ci.yml")) == []


KEY_STEP = "The key of a pass, from the commit's tree, this workflow's blob and the runner's image"


def test_the_per_commit_jobs_key_names_the_tree_the_workflow_and_the_image(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key step, run as GitHub runs it: the commit's tree, the workflow's blob and the runner's image
    version, which GitHub changes weekly under the same label; and a failure where the gate gave no blob or
    the runner no image version, rather than a key that two workflows or two images share."""
    head = commit("src/materica/core/read.py")
    tree = subprocess.run(
        ["git", "rev-parse", f"{head}^{{tree}}"], capture_output=True, text=True, check=True
    )
    found = step(workflow("ci.yml")["jobs"]["commit"], KEY_STEP)
    monkeypatch.setenv("ImageVersion", "20261012.1.0")
    status, outputs, printed = run_step(found, {"needs.gate.outputs.workflow_blob": "f" * 40}, repository)
    assert status == 0, printed
    assert outputs == {"key": f"commit-passed-{tree.stdout.strip()}-{'f' * 40}-20261012.1.0"}
    status, _, printed = run_step(found, {"needs.gate.outputs.workflow_blob": ""}, repository)
    assert status == 1
    assert "::error::the gate gave no workflow_blob" in printed
    monkeypatch.delenv("ImageVersion")
    status, _, printed = run_step(found, {"needs.gate.outputs.workflow_blob": "f" * 40}, repository)
    assert status == 1
    assert "::error::the runner gives no ImageVersion" in printed


def matrix_of_one(ci: Workflow) -> None:
    ci["jobs"]["commit"]["strategy"]["matrix"] = {"sha": ["${{ github.sha }}"]}


def fail_fast(ci: Workflow) -> None:
    ci["jobs"]["commit"]["strategy"]["fail-fast"] = True


def no_cap(ci: Workflow) -> None:
    del ci["jobs"]["commit"]["strategy"]["max-parallel"]


def a_cap_read_from_the_variable(ci: Workflow) -> None:
    """The variable read again, where the gate's check no longer holds it."""
    ci["jobs"]["commit"]["strategy"]["max-parallel"] = "${{ fromJSON(vars.PER_COMMIT_MAX_PARALLEL || '6') }}"


def a_cap_of_another_output(ci: Workflow) -> None:
    ci["jobs"]["commit"]["strategy"]["max-parallel"] = "${{ fromJSON(needs.gate.outputs.commits) }}"


def a_cap_of_a_string(ci: Workflow) -> None:
    ci["jobs"]["commit"]["strategy"]["max-parallel"] = "${{ needs.gate.outputs.per_commit_max_parallel }}"


def a_cap_of_six_always(ci: Workflow) -> None:
    ci["jobs"]["commit"]["strategy"]["max-parallel"] = 6


def the_merge_checked_out(ci: Workflow) -> None:
    del ci["jobs"]["commit"]["steps"][0]["with"]["ref"]


def on_python_3_11(ci: Workflow) -> None:
    [setup] = [found for found in ci["jobs"]["commit"]["steps"] if uses(found, "astral-sh/setup-uv")]
    setup["with"]["python-version"] = "3.11"


def without_pyright(ci: Workflow) -> None:
    ci["jobs"]["commit"]["steps"] = [
        found for found in ci["jobs"]["commit"]["steps"] if found.get("run") != "uv run pyright"
    ]


def without_the_wheel_check(ci: Workflow) -> None:
    ci["jobs"]["commit"]["steps"] = [
        found for found in ci["jobs"]["commit"]["steps"] if "check_wheel.py" not in str(found.get("run"))
    ]


def without_a_generator(ci: Workflow) -> None:
    found = step(ci["jobs"]["commit"], "Every generator's check, on Python 3.11")
    found["run"] = found["run"].replace("gen_shapes.py --check", "gen_shapes.py")


def at_the_ci_profile(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["commit"])["env"]["MATERICA_HYPOTHESIS_PROFILE"] = "ci"


def no_blob_from_the_gate(ci: Workflow) -> None:
    del ci["jobs"]["gate"]["outputs"]["workflow_blob"]


def kept_under_another_key(ci: Workflow) -> None:
    [save] = [found for found in ci["jobs"]["commit"]["steps"] if uses(found, "actions/cache/save")]
    save["with"]["key"] = "commit-passed-${{ matrix.sha }}"


def a_lookup_that_restores(ci: Workflow) -> None:
    [lookup] = [found for found in ci["jobs"]["commit"]["steps"] if uses(found, "actions/cache/restore")]
    del lookup["with"]["lookup-only"]


def a_check_run_on_a_pass_found(ci: Workflow) -> None:
    pytest_step(ci["jobs"]["commit"]).pop("if")


def kept_after_a_failure(ci: Workflow) -> None:
    [save] = [found for found in ci["jobs"]["commit"]["steps"] if uses(found, "actions/cache/save")]
    save["if"] = "always() && steps.passed.outputs.cache-hit != 'true'"


def a_check_after_the_pass_is_kept(ci: Workflow) -> None:
    ci["jobs"]["commit"]["steps"].append(
        {"if": "steps.passed.outputs.cache-hit != 'true'", "run": "uv run mypy"}
    )


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (matrix_of_one, "the per-commit job's matrix is"),
        (fail_fast, "the per-commit job's fail-fast is True"),
        (no_cap, "the commit job runs None at once"),
        (
            a_cap_read_from_the_variable,
            "the commit job runs \"${{ fromJSON(vars.PER_COMMIT_MAX_PARALLEL || '6') }}\" at once",
        ),
        (
            a_cap_of_another_output,
            "the commit job runs '${{ fromJSON(needs.gate.outputs.commits) }}' at once",
        ),
        (
            a_cap_of_a_string,
            "the commit job runs '${{ needs.gate.outputs.per_commit_max_parallel }}' at once",
        ),
        (a_cap_of_six_always, "the commit job runs 6 at once"),
        (the_merge_checked_out, "does not check its commit out first"),
        (on_python_3_11, "installs Python ['3.11']"),
        (without_pyright, "does not run 'uv run pyright'"),
        (without_a_generator, "does not run 'uv run python scripts/gen_shapes.py --check'"),
        (without_the_wheel_check, "does not run 'uv run python scripts/check_wheel.py dist/*.whl'"),
        (at_the_ci_profile, "not run at the `dev` profile"),
        (no_blob_from_the_gate, "the gate does not give its workflow's blob"),
        (kept_under_another_key, "keeps a pass under another key or path"),
        (a_lookup_that_restores, "looking up only"),
        (a_check_run_on_a_pass_found, "runs on a pass found"),
        (kept_after_a_failure, "keeps a pass after a failure"),
        (a_check_after_the_pass_is_kept, "checks something outside its lookup"),
    ],
)
def test_the_per_commit_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    ci = copy.deepcopy(workflow("ci.yml"))
    fault(ci)
    found = per_commit_problems(ci)
    assert any(problem in line for line in found), found


# pytest's settings in pyproject.toml that choose no test. Every job's pytest reads them, and so does the
# matrix check's own collection, which could not see a test they moved out of every job.
PYTEST_SETTINGS = {"testpaths", "addopts", "junit_family", "xfail_strict", "markers", "filterwarnings"}


def settings_problems(settings: dict[str, Any]) -> list[str]:
    """Where pyproject.toml's pytest settings may choose tests: a setting not in `PYTEST_SETTINGS`, test paths
    other than `tests`, or an option in `addopts` not in `NOT_SELECTING`."""
    problems = [f"pyproject.toml sets {name}" for name in sorted(settings.keys() - PYTEST_SETTINGS)]
    if settings.get("testpaths") != ["tests"]:
        problems.append(f"pyproject.toml's testpaths are {settings.get('testpaths')!r}")
    options = settings.get("addopts", [])
    chosen = selecting(shlex.split(options) if isinstance(options, str) else options)
    if chosen:
        problems.append(f"pyproject.toml's addopts select {chosen}")
    return problems


def pytest_settings() -> dict[str, Any]:
    loaded: dict[str, Any] = tomllib.loads((REPOSITORY / "pyproject.toml").read_text("utf-8"))
    return cast(dict[str, Any], loaded["tool"]["pytest"]["ini_options"])


def test_no_pytest_setting_in_pyproject_chooses_tests() -> None:
    assert settings_problems(pytest_settings()) == []


@pytest.mark.parametrize(
    ("name", "value", "problem"),
    [
        ("addopts", ["-ra", "--ignore=tests/spec_sync"], "addopts select ['--ignore=tests/spec_sync']"),
        ("addopts", ["-ra", "--deselect", "tests/unit"], "addopts select ['--deselect', 'tests/unit']"),
        ("addopts", "-ra -k 'not slow'", "addopts select ['-k', 'not slow']"),
        ("addopts", ["-m", "not slow", "-ra"], "addopts select ['-m', 'not slow']"),
        ("addopts", ["-ra", "-p", "tests.drop"], "addopts select ['-p', 'tests.drop']"),
        ("testpaths", ["tests/unit"], "testpaths are ['tests/unit']"),
        ("python_files", "test_read*.py", "pyproject.toml sets python_files"),
    ],
    ids=["ignore", "deselect", "keyword", "marker", "plugin", "testpaths", "python-files"],
)
def test_the_settings_check_can_fail(name: str, value: object, problem: str) -> None:
    found = settings_problems(pytest_settings() | {name: value})
    assert any(problem in line for line in found), found


NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}


def table_problems(readme: str, ci: Workflow) -> list[str]:
    """Where the workflows README's table, before its first section, names other jobs than `ci.yml` has, or
    other Hypothesis shards."""
    readme = readme.partition("\n## ")[0]
    rows = {found[1]: found[2] for found in re.finditer(r"^\| `([\w-]+)` \|(.*)$", readme, re.M)}
    problems: list[str] = []
    if sorted(rows) != sorted(ci["jobs"]):
        problems.append(f"the table's jobs are {sorted(rows)}, ci.yml's {sorted(ci['jobs'])}")
    shards: list[str] = ci["jobs"]["hypothesis"]["strategy"]["matrix"]["shard"]
    found = re.search(r"in (\w+) shards side by side \(([^)]*)\)", rows.get("hypothesis", ""))
    if found is None:
        problems.append("the table's hypothesis row names no shards side by side")
    elif NUMBERS.get(found[1]) != len(shards) or re.findall(r"`(\w+)`", found[2]) != shards:
        problems.append(f"the table's shards are {found[1]}, {found[2]}; ci.yml's {shards}")
    return problems


def test_the_workflows_readme_names_the_jobs_and_shards_of_ci() -> None:
    readme = (WORKFLOWS / "README.md").read_text(encoding="utf-8")
    assert table_problems(readme, workflow("ci.yml")) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("| `controls` |", "| `mutants` |", "the table's jobs are"),
        ("six shards side by side", "five shards side by side", "the table's shards are five"),
        (", `conditions`)", ")", "the table's shards are six"),
        ("shards side by side", "shards", "names no shards"),
    ],
    ids=["a-job-renamed", "a-count-wrong", "a-shard-missing", "no-shards"],
)
def test_the_table_check_can_fail(old: str, new: str, problem: str) -> None:
    readme = (WORKFLOWS / "README.md").read_text(encoding="utf-8")
    assert readme.count(old) == 1
    found = table_problems(readme.replace(old, new), workflow("ci.yml"))
    assert any(problem in line for line in found), found


# The repeat workflow, `repeat.yml`: one pytest node run many times, each run under a seed of its own, when
# dispatched by hand. Its steps run here as written: the request's check in a checkout holding a copy of its
# script, the collect step on this repository, and the runs and the summary with a stub `uv` in place of
# pytest, which records what each run was given and fails the seeds it is told to.
REPEAT = "repeat.yml"
# The workflows run by hand alone, which the safety check holds to the others' pins.
BY_HAND = (REPEAT, "mutants.yml")
CHECK_STEP, COLLECT_STEP = "The inputs, checked", "The node collects a test"
RUNS_STEP, KEEP_STEP = "Run the node under each seed", "Keep the records"
FETCH_STEP, SUM_STEP = "Fetch the records", "Sum the runs"
REPEAT_SCRIPT = REPOSITORY / "scripts" / "repeat_runs.py"
# A request as a dispatch gives it, each input as text, and its outputs once the request job has checked it.
REQUESTED = {
    "node": "tests/property/test_sample.py::test_x[a b]",
    "profile": "ci",
    "python": "3.15",
    "jobs": "10",
    "runs": "20",
    "first_seed": "1",
    "extra": "--shard records --property-controls=none",
}
CHECKED = REQUESTED | {
    "extra": "--shard=records --property-controls=none",
    "matrix": json.dumps(list(range(1, 11))),
}
# Where an input may be read but in the check step's environment: the run's name and the concurrency group,
# which no shell reads.
INPUTS_READ_AT = (("run-name",), ("concurrency", "group"))
INPUT = re.compile(r"\$\{\{[^}]*\binputs\.")
# The checked profile, as the request job's steps and the jobs after it read it.
PROFILE_SOURCES = ("${{ steps.checked.outputs.profile }}", "${{ needs.request.outputs.profile }}")
# The routes by which a job reads the checked request: the request job's steps after the check from the
# check's outputs, and the jobs after it from the request job's.
CHECKED_IN_REQUEST, CHECKED_AFTER = "steps.checked.outputs.", "needs.request.outputs."


def dispatch(found: Workflow) -> dict[str, Any]:
    """The workflow's triggers: PyYAML reads the key `on` as True."""
    triggers = cast(dict[object, Any], found).get(True)
    return cast(dict[str, Any], triggers) if isinstance(triggers, dict) else {}


def checked_route(job_id: str) -> tuple[str, str]:
    """The route by which the job `job_id` reads the checked request, and the route it cannot."""
    return (CHECKED_IN_REQUEST, CHECKED_AFTER) if job_id == "request" else (CHECKED_AFTER, CHECKED_IN_REQUEST)


def job_context(job_id: str, outputs: Mapping[str, str]) -> dict[str, object]:
    """The context of a step of the job `job_id` after the request's check, as GitHub gives it: the dispatch's
    inputs, which every job can read; the checked request by the job's own route (`checked_route`); and null
    by the other, as GitHub gives a step or a job that the job does not have, which renders empty."""
    context: dict[str, object] = {f"inputs.{name}": value for name, value in REQUESTED.items()}
    own, other = checked_route(job_id)
    for name, value in outputs.items():
        context[own + name], context[other + name] = value, None
    return context


def runner(directory: Path, uv: str) -> dict[str, str]:
    """An environment as a runner's: `python3` the Python running these tests and `uv` a Python program,
    first on the path; `RUNNER_TEMP`; a step summary of its own; and no variable of pytest's, Hypothesis's,
    the profiles' or GitHub's from this run's own, so that a step run here on CI neither reads this run's
    attempt or commit nor writes to its job's summary."""
    tools = directory / "bin"
    tools.mkdir(parents=True, exist_ok=True)
    (directory / "uv.py").write_text(uv, encoding="utf-8")
    python = shlex.quote(sys.executable)
    for name, command in (("python3", python), ("uv", f"{python} {shlex.quote(str(directory / 'uv.py'))}")):
        (tools / name).write_text(f'#!/bin/sh\nexec {command} "$@"\n', encoding="utf-8")
        (tools / name).chmod(0o755)
    (directory / "runner").mkdir(exist_ok=True)
    own = ("PYTEST_", "HYPOTHESIS_", "MATERICA_", "GITHUB_")
    environment = {name: value for name, value in os.environ.items() if not name.startswith(own)}
    return environment | {
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(directory / "runner"),
        "GITHUB_STEP_SUMMARY": str(directory / "step_summary.md"),
        "STUB_CALLS": str(directory / "calls.jsonl"),
    }


def checkout(directory: Path) -> Path:
    """A checkout holding the repeat script, a test file, and a module outside tests/."""
    tree = directory / "tree"
    (tree / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPEAT_SCRIPT, tree / "scripts" / "repeat_runs.py")
    (tree / "tests" / "property").mkdir(parents=True, exist_ok=True)
    (tree / "tests" / "property" / "test_sample.py").write_text("", encoding="utf-8")
    (tree / "src").mkdir(exist_ok=True)
    (tree / "src" / "module.py").write_text("", encoding="utf-8")
    return tree


def edited(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} in {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def triggers_problems(repeat: Workflow, name: str = REPEAT) -> list[str]:
    """Where the workflow `name`, the repeat workflow or another run by hand, runs on anything but a dispatch
    by hand."""
    triggers = cast(dict[object, object], repeat).get(True)
    if isinstance(triggers, dict) and list(cast(dict[str, object], triggers)) == ["workflow_dispatch"]:
        return []
    return [f"{name} runs on {triggers!r}"]


def test_the_repeat_workflow_runs_on_a_dispatch_by_hand_alone() -> None:
    assert triggers_problems(workflow(REPEAT)) == []


@pytest.mark.parametrize(
    ("triggers", "problem"),
    [
        ({"workflow_dispatch": {}, "push": {"branches": ["main"]}}, "runs on {'workflow_dispatch'"),
        ({"workflow_dispatch": {}, "pull_request_target": {}}, "'pull_request_target'"),
        ({"pull_request": {}}, "runs on {'pull_request': {}}"),
        (["workflow_dispatch", "workflow_call"], "runs on ['workflow_dispatch', 'workflow_call']"),
    ],
    ids=["a-push", "a-pull-request-target", "a-pull-request", "a-call"],
)
def test_the_trigger_check_can_fail(triggers: object, problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    cast(dict[object, object], repeat)[True] = triggers
    assert any(problem in line for line in triggers_problems(repeat)), triggers_problems(repeat)


def safety_problems(repeat: Workflow, others: dict[str, Workflow], name: str = REPEAT) -> list[str]:
    """Where the workflow `name`, the repeat workflow or another run by hand, could write to the repository,
    read a secret or the token, keep the token in its checkout, write a cache another run reads, or use an
    action not pinned to a commit as ci.yml, pages.yml and release.yml pin it, or another uv than ci.yml's."""
    problems: list[str] = []
    if repeat.get("permissions") != {"contents": "read"}:
        problems.append(f"{name} has the permissions {repeat.get('permissions')!r}")
    pinned = {
        found["uses"]
        for other, loaded in others.items()
        if other not in BY_HAND
        for job in loaded["jobs"].values()
        for found in job.get("steps", [])
        if "uses" in found
    }
    for job_id, job in repeat["jobs"].items():
        if "permissions" in job:
            problems.append(f"{job_id} sets permissions of its own")
        for found in job.get("steps", []):
            action, given = found.get("uses"), found.get("with", {})
            if action is None:
                continue
            if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action) or action not in pinned:
                problems.append(
                    f"{job_id} uses {action}, not pinned to a commit as the other workflows pin it"
                )
            if action.startswith("actions/cache"):
                problems.append(f"{job_id} uses {action}")
            if action.startswith("astral-sh/setup-uv@") and given.get("save-cache") is not False:
                problems.append(f"{job_id} saves the uv cache, which ci.yml restores")
            if action.startswith("actions/checkout@") and given.get("persist-credentials") is not False:
                problems.append(f"{job_id} keeps the token in its checkout")
    text = json.dumps(repeat, default=str)
    problems += [f"{name} reads {found}" for found in re.findall(r"\b(?:secrets|github\.token)\b", text)]
    if repeat.get("env", {}).get("UV_VERSION") != others["ci.yml"]["env"]["UV_VERSION"]:
        problems.append(f"{name}'s uv is {repeat.get('env', {}).get('UV_VERSION')!r}, not ci.yml's")
    return problems


def test_the_repeat_workflow_reads_and_writes_nothing_beyond_its_own_run() -> None:
    assert safety_problems(workflow(REPEAT), workflows()) == []


def written_permissions(repeat: Workflow) -> None:
    repeat["permissions"] = {"contents": "write"}


def a_jobs_own_permissions(repeat: Workflow) -> None:
    repeat["jobs"]["summary"]["permissions"] = {"actions": "write"}


def a_secret(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], RUNS_STEP)["env"]["TOKEN"] = "${{ secrets.CONFIDENTIAL_SCAN_KEY }}"


def the_token(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], SUM_STEP)["env"]["TOKEN"] = "${{ github.token }}"


def a_cache_saved(repeat: Workflow) -> None:
    repeat["jobs"]["runs"]["steps"].append({"uses": "actions/cache/save@v6", "with": {"path": ".hypothesis"}})


def the_uv_cache_saved(repeat: Workflow) -> None:
    del repeat["jobs"]["runs"]["steps"][1]["with"]["save-cache"]


def the_token_kept(repeat: Workflow) -> None:
    repeat["jobs"]["request"]["steps"][0]["with"]["persist-credentials"] = True


def an_action_by_its_tag(repeat: Workflow) -> None:
    repeat["jobs"]["summary"]["steps"][0]["uses"] = "actions/checkout@v7"


def an_action_pinned_elsewhere(repeat: Workflow) -> None:
    repeat["jobs"]["summary"]["steps"][0]["uses"] = "actions/checkout@" + "0" * 40


def another_uv(repeat: Workflow) -> None:
    repeat["env"]["UV_VERSION"] = "0.12.0"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (written_permissions, "has the permissions {'contents': 'write'}"),
        (a_jobs_own_permissions, "summary sets permissions of its own"),
        (a_secret, "reads secrets"),
        (the_token, "reads github.token"),
        (a_cache_saved, "runs uses actions/cache/save@v6"),
        (the_uv_cache_saved, "runs saves the uv cache"),
        (the_token_kept, "request keeps the token in its checkout"),
        (an_action_by_its_tag, "summary uses actions/checkout@v7, not pinned to a commit"),
        (
            an_action_pinned_elsewhere,
            "summary uses actions/checkout@0000000000000000000000000000000000000000,",
        ),
        (another_uv, "repeat.yml's uv is '0.12.0'"),
    ],
)
def test_the_safety_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = safety_problems(repeat, workflows())
    assert any(problem in line for line in found), found


# A dispatch of the request above on one ref, and those that differ from it in one thing each.
DISPATCHED = {"github.ref": "refs/heads/a", "github.run_id": "1"} | {
    f"inputs.{name}": value for name, value in REQUESTED.items()
}
DIFFERING = {
    "github.ref": "refs/heads/b",
    "inputs.node": "tests/property",
    "inputs.profile": "deep",
    "inputs.python": "3.11",
    "inputs.jobs": "3",
    "inputs.runs": "4",
    "inputs.first_seed": "81",
    "inputs.extra": "",
}


def repeat_concurrency_problems(repeat: Workflow) -> list[str]:
    """Where two dispatches of one request on one ref, whose runs share their seeds, could run at once, or a
    dispatch could cancel, replace or wait behind another request."""
    concurrency = repeat.get("concurrency")
    if not isinstance(concurrency, dict):
        return ["repeat.yml sets no concurrency"]
    settings = cast(dict[str, object], concurrency)
    context = DISPATCHED | {"github.workflow": repeat["name"]}
    problems: list[str] = []
    if truthy(setting(settings.get("cancel-in-progress", False), context)):
        problems.append("a dispatch cancels the one running in its group")
    group = setting(settings.get("group"), context)
    if setting(settings.get("group"), context | {"github.run_id": "2"}) != group:
        problems.append("two dispatches of one request on one ref do not share a group")
    for key, value in DIFFERING.items():
        if setting(settings.get("group"), context | {key: value}) == group:
            problems.append(f"a dispatch of another {key} shares the group {group!r}")
    return problems


def test_a_dispatch_waits_only_behind_one_of_the_same_request() -> None:
    assert repeat_concurrency_problems(workflow(REPEAT)) == []


@pytest.mark.parametrize(
    ("concurrency", "problem"),
    [
        (None, "sets no concurrency"),
        ({"group": "${{ github.workflow }}-${{ github.ref }}"}, "a dispatch of another inputs.node shares"),
        ({"group": "${{ github.workflow }}-${{ github.run_id }}"}, "of one request on one ref do not share"),
        ({"group": "${{ github.workflow }}", "cancel-in-progress": True}, "cancels the one running"),
    ],
    ids=["none", "a-group-per-ref", "a-group-per-run", "cancelling"],
)
def test_the_repeat_concurrency_check_can_fail(concurrency: object, problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    repeat["concurrency"] = concurrency
    found = repeat_concurrency_problems(repeat)
    assert any(problem in line for line in found), found


# Inputs the request's check takes and inputs it refuses, each in place of the request's own. The node holding
# a command and the counts written for bash's arithmetic, which would run the command inside `a[...]`, show
# that the step hands each input to the script whole, and no shell reads it.
TAKEN = [
    ("node", "tests"),
    ("node", "tests/property/test_sample.py::test_x[';touch ran;']"),
    ("profile", "deep"),
    ("python", "3.11"),
    ("jobs", "1"),
    ("jobs", "20"),
    ("runs", "25"),
    ("first_seed", "0"),
    ("first_seed", "999999999"),
    ("extra", ""),
]
REFUSED = [
    ("node", "src/module.py"),
    ("node", "tests/../src/module.py"),
    ("node", "tests/property/test_missing.py"),
    ("node", "tests/property/test_sample.py\nmatrix=[1]"),
    ("profile", "default"),
    ("python", "3.10"),
    ("jobs", "0"),
    ("jobs", "21"),
    ("jobs", "010"),
    ("jobs", "a[$(touch ran)]"),
    ("runs", "26"),
    ("first_seed", "-1"),
    ("first_seed", "1000000000"),
    ("extra", "--hypothesis-profile=dev"),
    ("extra", "--hypothesis-seed=5"),
    ("extra", "-o addopts="),
    ("extra", "-p no:hypothesispytest"),
]


def request_problems(repeat: Workflow, directory: Path) -> list[str]:
    """Where the request job's check, run on the checkout in `directory`, refuses an input it must take, takes
    one it must refuse, writes other outputs than the request checked, or lets an input run a command."""
    tree = directory / "tree"
    environment = runner(directory, "")
    check = step(repeat["jobs"]["request"], CHECK_STEP)
    problems: list[str] = []
    cases = [(name, value, True) for name, value in TAKEN] + [(name, value, False) for name, value in REFUSED]
    for name, value, taken in cases:
        inputs = {f"inputs.{key}": text for key, text in (REQUESTED | {name: value}).items()}
        status, outputs, _ = run_step(check, inputs, tree, base=environment, scratch=directory)
        if (tree / "ran").exists():
            problems.append(f"the {name} {value!r} ran a command")
            (tree / "ran").unlink()
        if taken and status != 0:
            problems.append(f"the check refuses the {name} {value!r}")
        if not taken and (status == 0 or outputs):
            problems.append(f"the check takes the {name} {value!r}")
    inputs = {f"inputs.{key}": text for key, text in REQUESTED.items()}
    status, outputs, _ = run_step(check, inputs, tree, base=environment, scratch=directory)
    if (status, outputs) != (0, CHECKED):
        problems.append(f"the check of the request exits {status} and writes {outputs}, not {CHECKED}")
    return problems


def test_the_request_job_refuses_each_input_out_of_bounds(tmp_path: Path) -> None:
    checkout(tmp_path)
    assert request_problems(workflow(REPEAT), tmp_path) == []


def a_bound_raised(repeat: Workflow, tree: Path) -> None:
    edited(tree / "scripts" / "repeat_runs.py", "MAX_JOBS = 20\n", "MAX_JOBS = 200\n")


def a_hypothesis_option_listed(repeat: Workflow, tree: Path) -> None:
    edited(
        tree / "scripts" / "repeat_runs.py",
        'OPTIONS = {"',
        'OPTIONS = {"--hypothesis-profile": re.compile(r"\\w+"), "',
    )


def the_refusal_ignored(repeat: Workflow, tree: Path) -> None:
    step(repeat["jobs"]["request"], CHECK_STEP)["run"] += " || true"


def a_count_in_bash_arithmetic(repeat: Workflow, tree: Path) -> None:
    check = step(repeat["jobs"]["request"], CHECK_STEP)
    check["run"] = 'echo "jobs $((JOBS))"\n' + check["run"]


def an_input_in_the_script(repeat: Workflow, tree: Path) -> None:
    check = step(repeat["jobs"]["request"], CHECK_STEP)
    check["run"] = "NODE='${{ inputs.node }}' " + check["run"]


def the_check_left_out(repeat: Workflow, tree: Path) -> None:
    step(repeat["jobs"]["request"], CHECK_STEP)["run"] = "true"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_bound_raised, "the check takes the jobs '21'"),
        (a_hypothesis_option_listed, "the check takes the extra '--hypothesis-profile=dev'"),
        (the_refusal_ignored, "the check takes the node 'src/module.py'"),
        (a_count_in_bash_arithmetic, "the jobs 'a[$(touch ran)]' ran a command"),
        (
            an_input_in_the_script,
            "the node \"tests/property/test_sample.py::test_x[';touch ran;']\" ran a command",
        ),
        (the_check_left_out, "the check of the request exits 0 and writes {}"),
    ],
)
def test_the_request_check_can_fail(
    tmp_path: Path, fault: Callable[[Workflow, Path], None], problem: str
) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat, checkout(tmp_path))
    found = request_problems(repeat, tmp_path)
    assert any(problem in line for line in found), found


# Nodes and extra arguments the request's check takes, which pytest takes or refuses when the request job
# collects the node in this repository: a test that does not exist, or a shard's name pytest does not list.
COLLECTED = [
    ("tests/unit/test_repeat_runs.py::test_with_every_run_failed_the_bound_is_one", "", True),
    ("tests/unit/test_repeat_runs.py::test_no_such_test", "", False),
    ("tests/unit/test_repeat_runs.py", "--shard=no_such_shard", False),
]
# A `uv` whose `uv run` runs a module of the Python running these tests.
UV_RUN = """
import os, sys
assert sys.argv[1] == "run"
os.execv(sys.executable, [sys.executable, "-m", *sys.argv[2:]])
"""


def collect_problems(repeat: Workflow, directory: Path, cases: list[tuple[str, str, bool]]) -> list[str]:
    """Where the request job's collect step, run on this repository, takes a node pytest refuses, or refuses
    one it takes."""
    environment = runner(directory, UV_RUN)
    collect = step(repeat["jobs"]["request"], COLLECT_STEP)
    problems: list[str] = []
    for node, extra, taken in cases:
        context = job_context("request", CHECKED | {"node": node, "extra": extra})
        status, _, printed = run_step(collect, context, REPOSITORY, base=environment, scratch=directory)
        if (status == 0) != taken:
            verb = "refuses" if taken else "takes"
            problems.append(f"the collect step {verb} {node!r} with {extra!r}: {printed[-400:]}")
    return problems


def test_the_request_job_refuses_a_node_pytest_cannot_collect(tmp_path: Path) -> None:
    assert collect_problems(workflow(REPEAT), tmp_path, COLLECTED) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (
            "  exit 1\n",
            "  exit 0\n",
            "the collect step takes 'tests/unit/test_repeat_runs.py::test_no_such_test'",
        ),
        (' "${extra[@]}")', ")", "takes 'tests/unit/test_repeat_runs.py' with '--shard=no_such_shard'"),
    ],
    ids=["a-failure-passed", "the-extra-arguments-left-out"],
)
def test_the_collect_check_can_fail(tmp_path: Path, old: str, new: str, problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    collect = step(repeat["jobs"]["request"], COLLECT_STEP)
    assert collect["run"].count(old) == 1
    collect["run"] = collect["run"].replace(old, new)
    found = collect_problems(repeat, tmp_path, [case for case in COLLECTED if not case[2]])
    assert any(problem in line for line in found), found


# A `uv` that stands for `uv run ...` of one run: it records its arguments, the profile, any variable of
# pytest's or Hypothesis's, and whether the run found an example database; writes one, as a run does; writes a
# JUnit report of one test, failing with a failing example on the seeds `STUB_FAILING` lists; and exits as
# pytest would.
STUB_UV = """
import json, os, sys
from pathlib import Path

arguments = sys.argv[1:]
given = dict(word.partition("=")[::2] for word in arguments if word.startswith("--"))
with open(os.environ["STUB_CALLS"], "a", encoding="utf-8") as calls:
    record = {
        "arguments": arguments,
        "profile": os.environ.get("MATERICA_HYPOTHESIS_PROFILE"),
        "environment": sorted(name for name in os.environ if name.startswith(("PYTEST_", "HYPOTHESIS_"))),
        "database": Path(".hypothesis").exists(),
    }
    print(json.dumps(record), file=calls)
Path(".hypothesis", "examples").mkdir(parents=True, exist_ok=True)
seed = given.get("--hypothesis-seed", "")
failing = seed in os.environ.get("STUB_FAILING", "").split()
failure = f"Failing test case: test_y(\\n    x={seed},\\n)\\n\\n@reproduce_failure('6', b'AA')"
if "--junitxml" in given:
    Path(given["--junitxml"]).write_text(
        '<testsuites><testsuite><testcase classname="tests.property.test_x" name="test_y" '
        'file="tests/property/test_x.py">'
        + (f'<failure message="assert">{failure}</failure>' if failing else "")
        + "</testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
sys.exit(1 if failing else 0)
"""
# The request a job of runs is given: three runs from seed 1.
RUN_OUTPUTS = CHECKED | {"runs": "3"}


class Ran(NamedTuple):
    status: int
    calls: list[dict[str, Any]]
    records: list[dict[str, Any]]
    printed: str


def run_the_runs(repeat: Workflow, directory: Path, failing: str = "", job: int = 1, **overrides: str) -> Ran:
    """The runs step of the job `job`, with its job's environment and `overrides`, run as written on a
    checkout in `directory` with the stub `uv`: its status, each call of `uv`, the records the step kept, and
    what it printed."""
    tree = checkout(directory)
    environment = runner(directory, STUB_UV) | {"STUB_FAILING": failing}
    runs = repeat["jobs"]["runs"]
    found = step(runs, RUNS_STEP)
    found = dict(found, env=runs.get("env", {}) | found.get("env", {}) | overrides)
    context = job_context("runs", RUN_OUTPUTS) | {"matrix.job": job}
    status, _, printed = run_step(found, context, tree, base=environment, scratch=directory)

    def lines(path: Path) -> list[dict[str, Any]]:
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []

    calls = lines(directory / "calls.jsonl")
    return Ran(status, calls, lines(directory / "runner" / "runs" / "results.jsonl"), printed)


def run_words(directory: Path, seed: int) -> list[str]:
    """The words of a run of seed `seed` after `uv run timeout --foreground --signal=INT <seconds>`."""
    return [
        *("pytest", "-n", "auto", "--dist", "worksteal", RUN_OUTPUTS["node"], *RUN_OUTPUTS["extra"].split()),
        f"--hypothesis-seed={seed}",
        f"--junitxml={directory / 'runner' / 'runs' / f'{seed}.xml'}",
    ]


def conftest_profiles() -> list[str]:
    """The profiles tests/conftest.py registers: the keys of its `EXAMPLES`."""
    module = ast.parse((REPOSITORY / "tests" / "conftest.py").read_text(encoding="utf-8"))
    [examples] = [
        node.value
        for node in module.body
        if isinstance(node, ast.Assign) and [ast.unparse(target) for target in node.targets] == ["EXAMPLES"]
    ]
    return list(ast.literal_eval(examples))


def places(value: object, at: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    """Each string of a parsed workflow, with the keys and indexes that lead to it."""
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return [found for key, item in mapping.items() for found in places(item, (*at, str(key)))]
    if isinstance(value, list):
        return [
            found
            for index, item in enumerate(cast(list[object], value))
            for found in places(item, (*at, str(index)))
        ]
    return [(at, value)] if isinstance(value, str) else []


def reach_problems(repeat: Workflow, ci: Workflow, directory: Path) -> list[str]:
    """Where an input could reach pytest's options or the Hypothesis settings but as the request's check
    passed it: an input read anywhere but the check step's environment, the run's name and the concurrency
    group; an expression in a script, which GitHub writes into its text; a variable of pytest's or
    Hypothesis's; a pytest step without the checked profile, or a profile from anything else; profiles or
    Pythons other than the repository's own; or a run given other words than its node, the extra arguments
    and its seed, run as written with the stub `uv`."""
    problems: list[str] = []
    check = str(repeat["jobs"]["request"]["steps"].index(step(repeat["jobs"]["request"], CHECK_STEP)))
    for at, text in places(repeat):
        if (
            INPUT.search(text)
            and at not in INPUTS_READ_AT
            and at[:5] != ("jobs", "request", "steps", check, "env")
        ):
            problems.append(f"an input is read at {'.'.join(at)}")
        if at[-1] == "MATERICA_HYPOTHESIS_PROFILE" and text not in PROFILE_SOURCES:
            problems.append(f"the profile at {'.'.join(at)} is {text!r}")
    problems += [
        f"repeat.yml sets {name}"
        for name in map(str, keys(repeat))
        if name.startswith(("PYTEST_", "HYPOTHESIS_"))
    ]
    for job_id, job in repeat["jobs"].items():
        for found in job.get("steps", []):
            script = str(found.get("run", ""))
            if "${{" in script:
                problems.append(f"a script of {job_id} holds an expression")
            if re.search(r"\b(?:PYTEST|HYPOTHESIS)_\w+=", script):
                problems.append(f"a script of {job_id} sets a variable of pytest's or Hypothesis's")
            environment = job.get("env", {}) | found.get("env", {})
            if "pytest" in script and environment.get("MATERICA_HYPOTHESIS_PROFILE") not in PROFILE_SOURCES:
                problems.append(f"a pytest step of {job_id} runs without the checked profile")
    inputs = dispatch(repeat)["workflow_dispatch"]["inputs"]
    profiles = [inputs["profile"]["options"], list(repeat_runs.PROFILES), conftest_profiles()]
    if any(found != profiles[0] for found in profiles):
        problems.append(f"the workflow's, the script's and tests/conftest.py's profiles are {profiles}")
    pythons = [
        inputs["python"]["options"],
        list(repeat_runs.PYTHONS),
        ci["jobs"]["tests"]["strategy"]["matrix"]["python"],
    ]
    if any(found != pythons[0] for found in pythons):
        problems.append(f"the workflow's, the script's and ci.yml's test matrix's Pythons are {pythons}")
    calls = run_the_runs(repeat, directory).calls
    for seed, call in enumerate(calls, 1):
        if call["arguments"][5:] != run_words(directory, seed) or call["environment"]:
            problems.append(
                f"the run of seed {seed} is given {call['arguments'][4:]} and {call['environment']}"
            )
        if call["profile"] != RUN_OUTPUTS["profile"]:
            problems.append(f"the run of seed {seed} has the profile {call['profile']!r}")
    if len(calls) != 3:
        problems.append(f"{len(calls)} runs of 3")
    return problems


def test_no_input_reaches_the_hypothesis_settings_or_pytests_options(tmp_path: Path) -> None:
    assert reach_problems(workflow(REPEAT), workflow("ci.yml"), tmp_path) == []


def the_profile_from_the_input(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], RUNS_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"] = "${{ inputs.profile }}"


def the_node_from_the_input(repeat: Workflow) -> None:
    step(repeat["jobs"]["request"], COLLECT_STEP)["env"]["NODE"] = "${{ inputs.node }}"


def no_profile(repeat: Workflow) -> None:
    del step(repeat["jobs"]["runs"], RUNS_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"]


def options_from_the_workflow_env(repeat: Workflow) -> None:
    repeat["env"]["PYTEST_ADDOPTS"] = "-p no:hypothesispytest"


def options_exported_in_the_loop(repeat: Workflow) -> None:
    runs = step(repeat["jobs"]["runs"], RUNS_STEP)
    runs["run"] = "export PYTEST_ADDOPTS=--hypothesis-profile=dev\n" + runs["run"]


def a_profile_in_the_loop(repeat: Workflow) -> None:
    runs = step(repeat["jobs"]["runs"], RUNS_STEP)
    runs["run"] = runs["run"].replace(
        '--hypothesis-seed="$seed"', '--hypothesis-profile=dev --hypothesis-seed="$seed"'
    )


def an_expression_in_the_loop(repeat: Workflow) -> None:
    runs = step(repeat["jobs"]["runs"], RUNS_STEP)
    runs["run"] = runs["run"].replace('"$NODE"', '"${{ needs.request.outputs.node }}"')


def a_profile_of_its_own(repeat: Workflow) -> None:
    dispatch(repeat)["workflow_dispatch"]["inputs"]["profile"]["options"].append("quick")


def another_python(repeat: Workflow) -> None:
    dispatch(repeat)["workflow_dispatch"]["inputs"]["python"]["options"].insert(0, "3.10")


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (the_profile_from_the_input, "an input is read at jobs.runs.steps.3.env.MATERICA_HYPOTHESIS_PROFILE"),
        (the_node_from_the_input, "an input is read at jobs.request.steps.4.env.NODE"),
        (no_profile, "the run of seed 1 has the profile None"),
        (options_from_the_workflow_env, "repeat.yml sets PYTEST_ADDOPTS"),
        (options_exported_in_the_loop, "a script of runs sets a variable"),
        (a_profile_in_the_loop, "the run of seed 1 is given"),
        (an_expression_in_the_loop, "a script of runs holds an expression"),
        (a_profile_of_its_own, "the workflow's, the script's and tests/conftest.py's profiles are"),
        (another_python, "Pythons are [['3.10'"),
    ],
)
def test_the_reach_check_can_fail(tmp_path: Path, fault: Callable[[Workflow], None], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = reach_problems(repeat, workflow("ci.yml"), tmp_path)
    assert any(problem in line for line in found), found


# The variables, and setup-uv's setting, that carry a part of the checked request into a step, and that part.
CARRIERS = {
    "NODE": "node",
    "PROFILE": "profile",
    "MATERICA_HYPOTHESIS_PROFILE": "profile",
    "PYTHON_VERSION": "python",
    "JOBS": "jobs",
    "RUNS": "runs",
    "FIRST_SEED": "first_seed",
    "EXTRA": "extra",
    "python-version": "python",
}


def route_problems(repeat: Workflow) -> list[str]:
    """Where a job reads the checked request by the other route than its own (`checked_route`), which renders
    empty on GitHub; names an output the request job does not write; or carries a part of the request, in a
    variable or in setup-uv's Python, as anything but that part's checked value by its own route; or where the
    request job's outputs are not its checks': the inputs' check's, and the cap step's for the runs' cap
    (`CAPS`). So the runs and the summary run and name the request that the request job checked, which they
    read from one place."""
    problems: list[str] = []
    written: dict[str, object] = repeat["jobs"]["request"].get("outputs", {})
    caps = {cap.output: CAP_OUTPUT for cap in CAPS if (cap.workflow, cap.checker) == (REPEAT, "request")}
    problems += [
        f"the request job's output {name} is {value!r}"
        for name, value in written.items()
        if value != caps.get(name, f"${{{{ {CHECKED_IN_REQUEST}{name} }}}}")
    ]
    for job_id, job in repeat["jobs"].items():
        own, other = checked_route(job_id)
        for at, text in places(job):
            if other in text:
                problems.append(f"{job_id} reads the request through {other} at {'.'.join(at)}")
            problems += [
                f"{job_id} reads {CHECKED_AFTER}{name}, which the request job does not write"
                for name in re.findall(rf"\b{re.escape(CHECKED_AFTER)}(\w+)", text)
                if name not in written
            ]
        carriers = [("its env", job.get("env", {}))]
        for index, found in enumerate(job.get("steps", [])):
            if found.get("name") == CHECK_STEP:
                continue
            carried = dict(found.get("env", {}))
            if str(found.get("uses", "")).startswith("astral-sh/setup-uv@"):
                carried["python-version"] = found.get("with", {}).get("python-version")
            carriers.append((f"step {index}", carried))
        for where, carried in carriers:
            for key, value in carried.items():
                expected = f"${{{{ {own}{CARRIERS[key]} }}}}" if key in CARRIERS else value
                if value != expected:
                    problems.append(f"{where} of {job_id} sets {key} to {value!r}, not {expected}")
    return problems


def test_each_job_reads_the_checked_request_from_one_place() -> None:
    assert route_problems(workflow(REPEAT)) == []


def runs_on_a_python_of_their_own(repeat: Workflow) -> None:
    repeat["jobs"]["runs"]["steps"][1]["with"]["python-version"] = "3.15"


def runs_with_the_profile_of_the_request_jobs_step(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], RUNS_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"] = (
        "${{ steps.checked.outputs.profile }}"
    )


def a_summary_named_by_a_constant(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], SUM_STEP)["env"]["PROFILE"] = "ci"


def a_summary_of_a_constant_python(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], SUM_STEP)["env"]["PYTHON_VERSION"] = "3.15"


def the_request_job_reading_its_own_outputs(repeat: Workflow) -> None:
    step(repeat["jobs"]["request"], COLLECT_STEP)["env"]["NODE"] = "${{ needs.request.outputs.node }}"


def a_python_left_to_uv(repeat: Workflow) -> None:
    del repeat["jobs"]["request"]["steps"][2]["with"]["python-version"]


def an_output_of_another_step(repeat: Workflow) -> None:
    repeat["jobs"]["request"]["outputs"]["profile"] = "${{ steps.collect.outputs.profile }}"


def an_output_never_written(repeat: Workflow) -> None:
    repeat["jobs"]["runs"]["steps"][1]["with"]["python-version"] = "${{ needs.request.outputs.pyton }}"


def a_part_carried_by_another(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], RUNS_STEP)["env"]["RUNS"] = "${{ needs.request.outputs.jobs }}"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (runs_on_a_python_of_their_own, "step 1 of runs sets python-version to '3.15'"),
        (
            runs_with_the_profile_of_the_request_jobs_step,
            "runs reads the request through steps.checked.outputs. at steps.3.env.MATERICA_HYPOTHESIS",
        ),
        (a_summary_named_by_a_constant, "step 2 of summary sets PROFILE to 'ci'"),
        (a_summary_of_a_constant_python, "step 2 of summary sets PYTHON_VERSION to '3.15'"),
        (
            the_request_job_reading_its_own_outputs,
            "request reads the request through needs.request.outputs. at steps.4.env.NODE",
        ),
        (a_python_left_to_uv, "step 2 of request sets python-version to None"),
        (
            an_output_of_another_step,
            "the request job's output profile is '${{ steps.collect.outputs.profile }}'",
        ),
        (
            an_output_never_written,
            "runs reads needs.request.outputs.pyton, which the request job does not write",
        ),
        (a_part_carried_by_another, "of runs sets RUNS to '${{ needs.request.outputs.jobs }}'"),
    ],
)
def test_the_route_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = route_problems(repeat)
    assert any(problem in line for line in found), found


def runner_share_problems(repeat: Workflow) -> list[str]:
    """Where a job of runs that fails cancels the others, whose seeds would then have no record, or the jobs
    of runs are not capped at REPEAT_MAX_PARALLEL at once, 10 where it is unset, as the request job checks it
    (`CAPS`): the organisation's 60 concurrent jobs are shared by this repository's CI and MIME's and
    MADDENING's."""
    strategy = repeat["jobs"]["runs"].get("strategy", {})
    problems: list[str] = []
    if strategy.get("fail-fast") is not False:
        problems.append(
            f"the runs' fail-fast is {strategy.get('fail-fast')!r}: a job that fails cancels the others"
        )
    return problems + cap_problems(repeat, CAPS[2])


def test_the_runs_take_the_checked_cap_of_runners_and_none_cancels_another() -> None:
    assert runner_share_problems(workflow(REPEAT)) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"fail-fast": True}, "the runs' fail-fast is True"),
        ({"fail-fast": None}, "the runs' fail-fast is None"),
        ({"max-parallel": None}, "the runs job runs None at once"),
        (
            {"max-parallel": "${{ fromJSON(vars.REPEAT_MAX_PARALLEL || '10') }}"},
            "the runs job runs \"${{ fromJSON(vars.REPEAT_MAX_PARALLEL || '10') }}\" at once",
        ),
        (
            {"max-parallel": "${{ fromJSON(needs.request.outputs.jobs) }}"},
            "the runs job runs '${{ fromJSON(needs.request.outputs.jobs) }}' at once",
        ),
        (
            {"max-parallel": "${{ needs.request.outputs.max_parallel }}"},
            "the runs job runs '${{ needs.request.outputs.max_parallel }}' at once",
        ),
        ({"max-parallel": 10}, "the runs job runs 10 at once"),
        ({"max-parallel": "10"}, "the runs job runs '10' at once"),
    ],
    ids=[
        "fail-fast",
        "fail-fast-by-default",
        "no-cap",
        "the-variable-read-again",
        "another-output",
        "the-output-a-string",
        "ten-always",
        "a-string",
    ],
)
def test_the_runner_share_check_can_fail(change: dict[str, object], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    strategy = repeat["jobs"]["runs"]["strategy"]
    for key, value in change.items():
        if value is None:
            del strategy[key]
        else:
            strategy[key] = value
    found = runner_share_problems(repeat)
    assert any(problem in line for line in found), found


def syncs(job: dict[str, Any]) -> bool:
    return any(str(found.get("run", "")).startswith("uv sync") for found in job.get("steps", []))


def repeat_timeout_problems(repeat: Workflow, ci: Workflow, directory: Path) -> list[str]:
    """Where a job has no timeout, or one that syncs the environment has less time, at some profile, than the
    shortest of ci.yml's jobs that do; the runs' timeout, at some profile, is not the minutes their interrupt
    is set from, or leaves no room for it; or, run as written with the stub `uv`, a run does not start under
    `uv run timeout --foreground --signal=INT` until three minutes before the job's timeout, counted from the
    step's start, or one starts with no time left."""
    problems = [
        f"{job_id} has no timeout" for job_id, job in repeat["jobs"].items() if "timeout-minutes" not in job
    ]
    least = min(
        job["timeout-minutes"]
        for job in ci["jobs"].values()
        if syncs(job) and isinstance(job.get("timeout-minutes"), int)
    )
    for job_id, job in repeat["jobs"].items():
        for profile in repeat_runs.PROFILES if syncs(job) else ():
            given = as_number(setting(job.get("timeout-minutes"), {"needs.request.outputs.profile": profile}))
            if not given >= least:
                problems.append(
                    f"{job_id} syncs in {given} minutes at {profile}, ci.yml's jobs in {least} or more"
                )
    runs = repeat["jobs"]["runs"]
    for profile in repeat_runs.PROFILES:
        context = {"needs.request.outputs.profile": profile}
        limit = setting(runs.get("timeout-minutes"), context)
        minutes = setting(runs.get("env", {}).get("JOB_MINUTES"), context)
        if not equal(limit, minutes) or as_number(limit) <= 3:
            problems.append(
                f"at {profile} the runs time out at {limit!r} minutes, their JOB_MINUTES are {minutes!r}"
            )
    calls = run_the_runs(repeat, directory / "ten", JOB_MINUTES="10").calls
    for call in calls:
        head = call["arguments"][:6]
        left = re.fullmatch(r"(\d+)s", head[4]) if len(head) == 6 else None
        if (
            head[:4] != ["run", "timeout", "--foreground", "--signal=INT"]
            or head[5:] != ["pytest"]
            or not left
        ):
            problems.append(
                f"a run starts as {head}, not under `uv run timeout --foreground --signal=INT <seconds>`"
            )
        elif not 7 * 60 - 30 <= int(left[1]) <= 7 * 60:
            when = "later" if int(left[1]) > 7 * 60 else "sooner"
            problems.append(
                f"a run of a job of 10 minutes is interrupted after {left[1]} s, {when} than about 420"
            )
    if len(calls) != 3:
        problems.append(f"{len(calls)} runs of 3 started in a job of 10 minutes")
    status, calls, _, _ = run_the_runs(repeat, directory / "three", JOB_MINUTES="3")
    if calls or status == 0:
        problems.append(f"in a job of 3 minutes {len(calls)} runs started and the step exited {status}")
    return problems


def test_each_run_is_interrupted_three_minutes_before_its_job_times_out(tmp_path: Path) -> None:
    assert repeat_timeout_problems(workflow(REPEAT), workflow("ci.yml"), tmp_path) == []


def interrupted_by_term(repeat: Workflow) -> None:
    edited_step(repeat, "--signal=INT", "--signal=TERM")


def interrupting_the_group(repeat: Workflow) -> None:
    edited_step(repeat, " --foreground", "")


def no_room_for_the_interrupt(repeat: Workflow) -> None:
    edited_step(repeat, "(JOB_MINUTES - 3)", "JOB_MINUTES")


def uv_under_timeout(repeat: Workflow) -> None:
    edited_step(
        repeat,
        'uv run timeout --foreground --signal=INT "${left}s" pytest',
        'timeout --foreground --signal=INT "${left}s" uv run pytest',
    )


def no_deadline(repeat: Workflow) -> None:
    edited_step(repeat, 'if [ "$left" -le 0 ]; then', "if false; then")


def minutes_of_another_profile(repeat: Workflow) -> None:
    runs = repeat["jobs"]["runs"]
    runs["env"]["JOB_MINUTES"] = runs["env"]["JOB_MINUTES"].replace("'deep' && 360", "'deep' && 350")


def a_summary_without_a_timeout(repeat: Workflow) -> None:
    del repeat["jobs"]["summary"]["timeout-minutes"]


def a_request_of_a_minute(repeat: Workflow) -> None:
    repeat["jobs"]["request"]["timeout-minutes"] = 1


def runs_of_a_minute_at_dev(repeat: Workflow) -> None:
    runs = repeat["jobs"]["runs"]
    runs["timeout-minutes"] = runs["timeout-minutes"].replace("|| 60 }}", "|| 1 }}")


def edited_step(repeat: Workflow, old: str, new: str) -> None:
    runs = step(repeat["jobs"]["runs"], RUNS_STEP)
    assert runs["run"].count(old) == 1, old
    runs["run"] = runs["run"].replace(old, new)


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (interrupted_by_term, "a run starts as ['run', 'timeout', '--foreground', '--signal=TERM'"),
        (interrupting_the_group, "a run starts as ['run', 'timeout', '--signal=INT'"),
        (no_room_for_the_interrupt, "s, later than about 420"),
        (uv_under_timeout, "a run starts as ['run', 'pytest', '-n'"),
        (no_deadline, "in a job of 3 minutes 3 runs started"),
        (
            minutes_of_another_profile,
            "at deep the runs time out at 360.0 minutes, their JOB_MINUTES are 350.0",
        ),
        (a_summary_without_a_timeout, "summary has no timeout"),
        (a_request_of_a_minute, "request syncs in 1.0 minutes at dev, ci.yml's jobs in 5 or more"),
        (runs_of_a_minute_at_dev, "runs syncs in 1.0 minutes at dev, ci.yml's jobs in 5 or more"),
    ],
)
def test_the_repeat_interrupt_check_can_fail(
    tmp_path: Path, fault: Callable[[Workflow], None], problem: str
) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = repeat_timeout_problems(repeat, workflow("ci.yml"), tmp_path)
    assert any(problem in line for line in found), found


def records_problems(repeat: Workflow, directory: Path) -> list[str]:
    """Where the runs step, run as written with the stub `uv` and seed 2 failing, passes; keeps other records
    than each run's, in order, or the failed run's without its failing example; lets a run find the example
    database of a run before it; given a count of runs that the script's `seeds` refuses, starts a run, passes
    or does not print why; or where the records are not kept whenever the step ran."""
    status, calls, records, _ = run_the_runs(repeat, directory / "seed-2-failing", failing="2")
    problems: list[str] = []
    refused = run_the_runs(repeat, directory / "refused", RUNS="0")
    why = "::error title=Repeat request::the number of runs a job 0 is not from 1 to 25"
    if refused.calls or refused.status == 0 or why not in refused.printed:
        problems.append(
            f"the seeds refused, the step started {len(refused.calls)} runs, exited {refused.status} and "
            f"printed {refused.printed[-300:]!r}"
        )
    if status == 0:
        problems.append("the runs step passes with a run failed")
    kept = [(found["seed"], found["outcome"]) for found in records]
    if kept != [(1, "passed"), (2, "failed"), (3, "passed")]:
        problems.append(f"the records are {kept}")
    elif not any("x=2," in example for failure in records[1]["failures"] for example in failure["examples"]):
        problems.append(f"the failed run's record is {records[1]}")
    problems += [
        f"run {index} found an example database" for index, call in enumerate(calls, 1) if call["database"]
    ]
    keep = step(repeat["jobs"]["runs"], KEEP_STEP)
    for standing, outcome in ((PASSED, "success"), (FAILED, "failure"), (CANCELLED, "cancelled")):
        if not truthy(evaluated(condition(keep), standing | {"steps.runs.outcome": outcome})):
            problems.append(f"the records are not kept when the runs step ends in {outcome}")
    return problems


def test_each_runs_record_is_kept_and_a_failed_run_fails_its_job(tmp_path: Path) -> None:
    assert records_problems(workflow(REPEAT), tmp_path) == []


def the_database_kept(repeat: Workflow) -> None:
    edited_step(repeat, "rm -rf .hypothesis\n", "")


def a_failure_forgotten(repeat: Workflow) -> None:
    edited_step(repeat, '[ "$status" -eq 0 ] || failed=1', "true")


def a_refusal_unprinted(repeat: Workflow) -> None:
    edited_step(repeat, """ || { printf '%s\\n' "$listed"; exit 1; }""", "")


def the_records_kept_on_success_alone(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], KEEP_STEP)["if"] = "success()"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (the_database_kept, "run 2 found an example database"),
        (a_failure_forgotten, "the runs step passes with a run failed"),
        (the_records_kept_on_success_alone, "the records are not kept when the runs step ends in failure"),
        (a_refusal_unprinted, "the seeds refused, the step started 0 runs, exited 1 and printed ''"),
    ],
)
def test_the_records_check_can_fail(tmp_path: Path, fault: Callable[[Workflow], None], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = records_problems(repeat, tmp_path)
    assert any(problem in line for line in found), found


def artifact_files(path: str) -> dict[str, bytes]:
    """The files upload-artifact keeps of `path`: a directory's files, by their path in it; otherwise those
    the pattern matches, by their path in the directory that holds them all."""
    if Path(path).is_dir():
        root = Path(path)
        files = [Path(directory) / name for directory, _, names in os.walk(path) for name in names]
    else:
        files = [Path(found) for found in glob.glob(path, recursive=True) if Path(found).is_file()]
        root = Path(os.path.commonpath([found.parent for found in files])) if files else Path(path)
    return {str(found.relative_to(root)): found.read_bytes() for found in files}


def fetched(
    fetch: dict[str, Any], context: Mapping[str, object], artifacts: dict[str, dict[str, bytes]]
) -> None:
    """The fetch step as download-artifact does it: each artifact its pattern matches, or the one it names,
    into its path, or every artifact for neither, each in a directory of the artifact's name where more than
    one is fetched."""
    given = fetch["with"]
    path = Path(str(setting(given["path"], context)))
    chosen = list(artifacts)
    if "name" in given:
        chosen = [given["name"]]
    elif "pattern" in given:
        chosen = [name for name in artifacts if fnmatch.fnmatchcase(name, str(given["pattern"]))]
    for name in (name for name in chosen if name in artifacts):
        target = path / name if len(chosen) > 1 and not given.get("merge-multiple") else path
        for relative, content in artifacts[name].items():
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            (target / relative).write_bytes(content)


class Kept(NamedTuple):
    name: str
    files: dict[str, bytes]
    seeds: list[int]


def plumbing_problems(repeat: Workflow, ci: Workflow, directory: Path) -> list[str]:
    """Where the jobs of runs and the summary, run as written with the stub `uv`, the records kept as the
    keep step names and finds them and fetched as the fetch step does, fall short: jobs 1 and 2 do not run
    their own seeds; every run passing fails the summary; a failed run of job 2 does not fail it by its seed;
    job 2 run again ("Re-run failed jobs"), each run passing, hides that failure or passes the summary; or a
    run again in full ("Re-run all jobs") passes it, should GitHub list that attempt's records alone. Or where
    two jobs or attempts keep their records under one name, the fetch step's pattern misses one, or the
    records are kept for another time than ci.yml's uploads that state one. A later upload of a name stands
    in for an earlier, as download-artifact keeps the newest of a name (`latest`)."""
    problems: list[str] = []
    keep, fetch = step(repeat["jobs"]["runs"], KEEP_STEP), step(repeat["jobs"]["summary"], FETCH_STEP)
    names = Counter(
        str(setting(keep["with"]["name"], {"matrix.job": job, "github.run_attempt": attempt}))
        for job in range(1, repeat_runs.MAX_JOBS + 1)
        for attempt in (1, 2, 3)
    )
    if shared := sorted(name for name, count in names.items() if count > 1):
        problems.append(f"two jobs or two attempts keep their records as {shared[:3]}")
    if missed := sorted(
        name for name in names if not fnmatch.fnmatchcase(name, str(fetch["with"].get("pattern")))
    ):
        problems.append(f"the fetch step's pattern {fetch['with'].get('pattern')!r} misses {missed[:3]}")
    reports = {
        found.get("with", {}).get("retention-days")
        for job in ci["jobs"].values()
        for found in job.get("steps", [])
        if str(found.get("uses", "")).startswith("actions/upload-artifact@")
        and "retention-days" in found.get("with", {})
    }
    if {keep["with"].get("retention-days")} != reports:
        problems.append(
            f"the records are kept {keep['with'].get('retention-days')} days, ci.yml's reports {reports}"
        )

    def kept(job: int, attempt: int, failing: str = "") -> Kept:
        where = directory / f"job-{job}-attempt-{attempt}-failing-{failing}"
        ran = run_the_runs(repeat, where, failing, job=job)
        context = {"matrix.job": job, "github.run_attempt": attempt, "runner.temp": str(where / "runner")}
        seeds = [
            int(word.partition("=")[2])
            for call in ran.calls
            for word in call["arguments"]
            if word.startswith("--hypothesis-seed=")
        ]
        name, path = (str(setting(keep["with"][key], context)) for key in ("name", "path"))
        return Kept(name, artifact_files(path), seeds)

    def summed(case: str, attempt: int, *uploads: Kept) -> tuple[int, str]:
        where = directory / f"summary-{case}"
        tree, environment = checkout(where), runner(where, "")
        artifacts = {upload.name: upload.files for upload in uploads}
        context = job_context("summary", RUN_OUTPUTS | {"jobs": "2", "matrix": "[1, 2]"}) | {
            "needs.runs.result": "success" if case != "failed" else "failure",
            "github.run_attempt": attempt,
            "runner.temp": environment["RUNNER_TEMP"],
        }
        fetched(fetch, context, artifacts)
        status, _, printed = run_step(
            step(repeat["jobs"]["summary"], SUM_STEP), context, tree, base=environment
        )
        return status, printed

    first, second = kept(1, 1), kept(2, 1)
    if (first.seeds, second.seeds) != ([1, 2, 3], [4, 5, 6]):
        problems.append(f"jobs 1 and 2 ran the seeds {first.seeds} and {second.seeds}, not 1 to 3 and 4 to 6")
    status, printed = summed("passed", 1, first, second)
    if status != 0:
        problems.append(f"the summary of two jobs whose runs all passed fails: {printed[-300:]!r}")
    failed = kept(2, 1, failing="5")
    status, printed = summed("failed", 1, first, failed)
    if status == 0 or "1 of 6 runs failed" not in printed or "### Failing seeds: 5" not in printed:
        problems.append(f"the summary of a failed run of job 2 exits {status}: {printed[-300:]!r}")
    again = kept(2, 2)
    status, printed = summed("again", 2, first, failed, again)
    if status == 0 or "1 of 6 runs failed" not in printed:
        problems.append(
            f"job 2 run again, its runs passing, leaves a summary of exit {status}: {printed[-300:]!r}"
        )
    status, printed = summed("all-again", 2, kept(1, 2), again)
    if status == 0:
        problems.append("the summary of a run again in full, every run passing, passes at attempt 2")
    return problems


def test_every_jobs_records_of_every_attempt_reach_the_summary(tmp_path: Path) -> None:
    assert plumbing_problems(workflow(REPEAT), workflow("ci.yml"), tmp_path) == []


def records_by_job_alone(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], KEEP_STEP)["with"]["name"] = "runs-${{ matrix.job }}"


def a_summary_of_any_attempt(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], SUM_STEP)["env"]["ATTEMPT"] = "1"


def a_pattern_of_another_name(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], FETCH_STEP)["with"]["pattern"] = "run-*"


def the_reports_alone_kept(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], KEEP_STEP)["with"]["path"] = "${{ runner.temp }}/runs/*.xml"


def seeds_of_job_one(repeat: Workflow) -> None:
    edited_step(
        repeat,
        "listed=$(python3 scripts/repeat_runs.py seeds)",
        'listed=$(seq "$FIRST_SEED" "$((FIRST_SEED + RUNS - 1))")',
    )


def records_kept_a_day(repeat: Workflow) -> None:
    step(repeat["jobs"]["runs"], KEEP_STEP)["with"]["retention-days"] = 1


@pytest.mark.parametrize(
    ("fault", "problems"),
    [
        (
            records_by_job_alone,
            (
                "two jobs or two attempts keep their records as ['runs-1', 'runs-10'",
                "job 2 run again, its runs passing, leaves a summary of exit 1",
            ),
        ),
        (a_summary_of_any_attempt, ("the summary of a run again in full, every run passing, passes",)),
        (
            a_pattern_of_another_name,
            (
                "the fetch step's pattern 'run-*' misses ['runs-1-1'",
                "the summary of two jobs whose runs all passed fails",
            ),
        ),
        (the_reports_alone_kept, ("the summary of two jobs whose runs all passed fails",)),
        (seeds_of_job_one, ("jobs 1 and 2 ran the seeds [1, 2, 3] and [1, 2, 3]",)),
        (records_kept_a_day, ("the records are kept 1 days, ci.yml's reports {90}",)),
    ],
)
def test_the_plumbing_check_can_fail(
    tmp_path: Path, fault: Callable[[Workflow], None], problems: tuple[str, ...]
) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = plumbing_problems(repeat, workflow("ci.yml"), tmp_path)
    assert all(any(problem in line for line in found) for problem in problems), found


# The records of two jobs of three runs from seed 1, the runs' jobs' result, and whether the summary passes.
EVERY_RUN_PASSED = dict.fromkeys(range(1, 7), "passed")
SUMMED = {
    "every run passed": (EVERY_RUN_PASSED, "success", True),
    "a run failed": (EVERY_RUN_PASSED | {4: "failed"}, "failure", False),
    "a run was interrupted": (EVERY_RUN_PASSED | {6: "interrupted"}, "failure", False),
    "a seed has no record": ({seed: "passed" for seed in range(1, 6)}, "failure", False),
    "a job of runs failed after its runs": (EVERY_RUN_PASSED, "failure", False),
    "the runs were cancelled": (EVERY_RUN_PASSED, "cancelled", False),
}
STATUSES = {"passed": 0, "failed": 1, "interrupted": 124}


def summary_problems(repeat: Workflow, directory: Path) -> list[str]:
    """Where the summary job does not wait for the runs, does not run whatever their result once the request
    was checked, or, run as written on each set of records, passes where a run failed, did not finish or left
    no record, or the runs' jobs did not succeed, fails where every run passed, or names another request than
    the request job wrote, of a profile and a Python other than the defaults."""
    job = repeat["jobs"]["summary"]
    problems: list[str] = []
    if "runs" not in job.get("needs", []):
        problems.append("the summary does not wait for the runs")
    for result in ("success", "failure", "cancelled"):
        standing: dict[str, object] = {
            "success()": result == "success",
            "failure()": result == "failure",
            "cancelled()": False,
        }
        context: dict[str, object] = standing | {
            "always()": True,
            "needs.request.result": "success",
            "needs.runs.result": result,
        }
        if not truthy(evaluated(condition(job), context)):
            problems.append(f"the summary does not run when the runs end in {result}")
    outputs = CHECKED | {"profile": "deep", "python": "3.12", "jobs": "2", "runs": "3", "matrix": "[1, 2]"}
    extra = ", ".join(map(repeat_runs.code, outputs["extra"].split()))
    named = (
        f"## Repeat runs of {repeat_runs.code(outputs['node'])}\n\nProfile {repeat_runs.code('deep')}, "
        f"Python 3.12, extra arguments: {extra}. 2 jobs of 3 runs, 6 in all, seeds 1 to 6."
    )
    for index, (case, (outcomes, result, passes)) in enumerate(SUMMED.items()):
        tree = checkout(directory / str(index))
        environment = runner(directory / str(index), "")
        for seed, outcome in outcomes.items():
            kept = Path(environment["RUNNER_TEMP"]) / "runs" / f"runs-{(seed - 1) // 3 + 1}"
            kept.mkdir(parents=True, exist_ok=True)
            record: dict[str, object] = {
                "seed": seed,
                "status": STATUSES[outcome],
                "outcome": outcome,
                "tests": 1,
                "failures": [],
            }
            with (kept / "results.jsonl").open("a", encoding="utf-8") as lines:
                lines.write(json.dumps(record) + "\n")
        context = job_context("summary", outputs) | {
            "needs.runs.result": result if "runs" in job.get("needs", []) else None,
            "github.run_attempt": 1,
        }
        status, _, printed = run_step(
            step(job, SUM_STEP), context, tree, base=environment, scratch=directory / str(index)
        )
        if (status == 0) != passes:
            problems.append(f"the summary {'fails' if passes else 'passes'} when {case}")
        if named not in printed:
            problems.append(f"the summary, when {case}, names the request as {printed[:300]!r}")
    return problems


def test_the_summary_fails_where_any_run_failed(tmp_path: Path) -> None:
    assert summary_problems(workflow(REPEAT), tmp_path) == []


def a_summary_after_success_alone(repeat: Workflow) -> None:
    repeat["jobs"]["summary"]["if"] = "needs.request.result == 'success'"


def a_summary_that_carries_on(repeat: Workflow) -> None:
    step(repeat["jobs"]["summary"], SUM_STEP)["run"] += " || true"


def a_summary_before_the_runs(repeat: Workflow) -> None:
    repeat["jobs"]["summary"]["needs"] = ["request"]


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_summary_after_success_alone, "the summary does not run when the runs end in failure"),
        (a_summary_that_carries_on, "the summary passes when a run failed"),
        (a_summary_before_the_runs, "the summary does not wait for the runs"),
        (a_summary_named_by_a_constant, "Profile <code>ci</code>, Python 3.12"),
        (a_summary_of_a_constant_python, "Profile <code>deep</code>, Python 3.15"),
    ],
)
def test_the_summary_check_can_fail(tmp_path: Path, fault: Callable[[Workflow], None], problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    fault(repeat)
    found = summary_problems(repeat, tmp_path)
    assert any(problem in line for line in found), found


# The heading of the workflows README's section on repeat.yml, whose table holds a row for each of its jobs.
REPEAT_HEADING = "## Repeat runs (`repeat.yml`)"


def repeat_table_problems(readme: str, repeat: Workflow, heading: str = REPEAT_HEADING) -> list[str]:
    """Where the workflows README's section under `heading`, on repeat.yml or another workflow run by hand,
    names other jobs than it has."""
    section = readme.partition(f"\n{heading}\n")[2].partition("\n## ")[0]
    rows = re.findall(r"^\| `([\w-]+)` \|", section, re.M)
    return (
        []
        if rows == list(repeat["jobs"])
        else [f"the table under {heading!r} names the jobs {rows}, its workflow {list(repeat['jobs'])}"]
    )


def test_the_workflows_readme_names_the_jobs_of_repeat() -> None:
    assert (
        repeat_table_problems((WORKFLOWS / "README.md").read_text(encoding="utf-8"), workflow(REPEAT)) == []
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [("| `summary` |", "| `sum` |"), (REPEAT_HEADING, "## Repeat runs")],
    ids=["a-job-renamed", "no-section"],
)
def test_the_repeat_table_check_can_fail(old: str, new: str) -> None:
    readme = (WORKFLOWS / "README.md").read_text(encoding="utf-8")
    assert readme.count(old) == 1
    assert repeat_table_problems(readme.replace(old, new), workflow(REPEAT)) != []


# The mutant workflow, `mutants.yml`: hand mutants, each a patch committed on the dispatched branch as
# mutants/<name>.patch, each run in a job of its own beside a job of the commit as it is (the baseline), and
# one table of what became of each. Its steps run here as written, on a throwaway repository holding a copy of
# its script, a package of two modules, a test of each, the files a patch may not touch and the patches: the
# request's check; each mutant's run step with a stub `uv` that records what it was given, and with one that
# runs this Python's pytest; and the table on the records those leave, fetched as download-artifact fetches.
MUTANT_WORKFLOW = "mutants.yml"
MUTANT_CHECK_STEP, MUTANT_COLLECT_STEP = (
    "The inputs and the patches, checked",
    "The selection collects a test",
)
MUTANT_RUN_STEP, RECORD_STEP = "The mutant, applied and run", "Keep the record"
RECORDS_FETCH_STEP, TABLE_STEP, TABLE_KEEP_STEP = "Fetch the records", "The table", "Keep the table"
MUTANT_SCRIPT = REPOSITORY / "scripts" / "mutant_runs.py"
# A request as a dispatch gives it, each input as text.
MUTANT_REQUESTED = {
    "mutants": "edited",
    "selection": "tests",
    "profile": "dev",
    "python": "3.15",
    "seed": "7",
    "extra": "",
}
# The tree each mutant runs on, beside the script: a package of two modules, a test of each, a workflow, the
# build's files, the repository's own ignore rules, and a link to a directory outside it.
MUTANT_TREE = {
    ".gitignore": (REPOSITORY / ".gitignore").read_text(encoding="utf-8"),
    "src/materica/__init__.py": "def double(x):\n    return 2 * x\n",
    "src/materica/half.py": "def half(x):\n    return x / 2\n",
    "tests/test_double.py": (
        "from materica import double\n\n\ndef test_double():\n    assert double(3) == 6\n"
    ),
    "tests/test_half.py": "from materica.half import half\n\n\ndef test_half():\n    assert half(4) == 2\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["src"]\njunit_family = "xunit1"\n',
    ".github/workflows/ci.yml": "on: push\n",
    "uv.lock": "version = 1\n",
}


def git_environment() -> dict[str, str]:
    """The environment a throwaway repository's git runs in, cut off from any repository around the run
    (`throwaway_git`), with an identity of its own."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return environment | {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "a",
        "GIT_AUTHOR_EMAIL": "a@example.org",
        "GIT_COMMITTER_NAME": "a",
        "GIT_COMMITTER_EMAIL": "a@example.org",
    }


def in_git(tree: Path, *arguments: str) -> str:
    ran = subprocess.run(
        ["git", *arguments], cwd=tree, env=git_environment(), capture_output=True, text=True, check=True
    )
    return ran.stdout


Change = Callable[[Path], None]


def edit(path: str, old: str, new: str) -> Change:
    def change(tree: Path) -> None:
        text = (tree / path).read_text(encoding="utf-8")
        assert text.count(old) == 1, f"{old!r} in {path}"
        (tree / path).write_text(text.replace(old, new), encoding="utf-8")

    return change


def add(path: str, text: str = "x = 1\n") -> Change:
    def change(tree: Path) -> None:
        (tree / path).parent.mkdir(parents=True, exist_ok=True)
        (tree / path).write_text(text, encoding="utf-8")

    return change


def delete(path: str) -> Change:
    return lambda tree: (tree / path).unlink()


def executable(path: str) -> Change:
    return lambda tree: (tree / path).chmod(0o755)


def link(path: str, target: str) -> Change:
    return lambda tree: (tree / path).symlink_to(target)


def rename(old: str, new: str) -> Change:
    def change(tree: Path) -> None:
        (tree / old).rename(tree / new)

    return change


def binary(path: str) -> Change:
    def change(tree: Path) -> None:
        (tree / path).write_bytes(b"\x00\x01\x02 not text\n")

    return change


def diffed(tree: Path, change: Change, *options: str) -> str:
    """The patch `git diff` gives of `change` to the committed tree, which is then restored."""
    change(tree)
    in_git(tree, "add", "-A")
    patch = in_git(tree, "diff", "--cached", "-M", *options)
    in_git(tree, "reset", "-q", "--hard")
    return patch


def written(patch: str) -> Callable[[Path], str]:
    return lambda tree: patch


def changed(change: Change, *options: str) -> Callable[[Path], str]:
    return lambda tree: diffed(tree, change, *options)


# A patch that adds one line to a file, by a path that git would write as given, for paths no change in a tree
# can make: outside it, from the root, and inside .git.
def new_file_patch(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
        "@@ -0,0 +1 @@\n+x = 1\n"
    )


# A rename without rename lines (#46's review, H1), whose one hunk replaces the old file's line with another:
# by default a `diff --git` line naming `old` then `new`; or another header given. git's reports list `new`
# alone, and `git apply` deletes `old`.
def disguised_rename(old: str, new: str = "src/materica/moved.py", header: str = "") -> str:
    return (
        f"{header or f'diff --git a/{old} b/{new}'}\nindex 1111111..2222222 100644\n"
        f"--- a/{old}\n+++ b/{new}\n@@ -1 +1 @@\n-on: push\n+moved = True\n"
    )


# A patch in git's format for one file, then a part in the traditional format for another, then a `diff --git`
# line with nothing under it, so that git's report lists as many files as there are `diff --git` lines.
PADDED = (
    "diff --git a/src/materica/half.py b/src/materica/half.py\nindex 1111111..2222222 100644\n"
    "--- a/src/materica/half.py\n+++ b/src/materica/half.py\n@@ -1,2 +1,2 @@\n def half(x):\n"
    "-    return x / 2\n+    return x / 3\n--- a/src/materica/__init__.py\n+++ b/src/materica/__init__.py\n"
    "@@ -1,2 +1,2 @@\n def double(x):\n-    return 2 * x\n+    return 3 * x\n"
    "diff --git a/src/materica/half.py b/src/materica/half.py\n"
)


# An edit of a file `uv sync` installs, which no commit holds (#46's review, H2).
INSTALLED = ".venv/lib/python3.15/site-packages/somepkg.py"
INSTALLED_EDIT = (
    f"diff --git a/{INSTALLED} b/{INSTALLED}\nindex 1111111..2222222 100644\n--- a/{INSTALLED}\n"
    f"+++ b/{INSTALLED}\n@@ -1 +1 @@\n-def given(): return 'real'\n+def given(): return 'patched'\n"
)


EDITED = edit("src/materica/__init__.py", "2 * x", "3 * x")
# The patches the request takes, each by its mutant's name: an edit, a new file, a file deleted, a file made
# executable; an edit whose context the tree does not hold, which its job records as broken; an edit that
# changes no behaviour; an edit that does not compile; and a module beside the scripts named as one of the
# standard library's, which reaches the verdict's code only if that code runs from the checkout.
PATCHES_TAKEN: dict[str, Callable[[Path], str]] = {
    "edited": changed(EDITED),
    "added": changed(add("src/materica/third.py", "def third(x):\n    return x / 3\n")),
    "deleted": changed(delete("tests/test_half.py")),
    "executable": changed(executable("src/materica/half.py")),
    "stale": lambda tree: diffed(tree, EDITED).replace("-    return 2 * x", "-    return 5 * x"),
    "equivalent": changed(edit("src/materica/__init__.py", "2 * x", "x + x")),
    "syntax": changed(edit("src/materica/half.py", "x / 2", "(x / 2")),
    "shadow": changed(add("scripts/importlib.py", 'raise ImportError("a module of the patch")\n')),
}
# The patches the request refuses, each by its mutant's name, with what it says of each: paths outside the
# tree, from its root, inside .git, of a character a plain path does not hold, or through a link out of it;
# under .github/, ignoring case, or mutants/; the runner, and the files that decide what uv installs or how it
# runs; a link made; binary data, with its bytes and without; a rename, with rename lines and without, from
# a path a patch may touch and from each it may not; a file of the environment uv installs, added or edited,
# and of the example database, which git ignores; a part not in git's format; a control character; no patch;
# and a patch that is too long.
PATCHES_REFUSED: dict[str, tuple[Callable[[Path], str], str]] = {
    "outside": (written(new_file_patch("../outside.py")), "touches '../outside.py' is not a plain path"),
    "rooted": (written(new_file_patch("/tmp/rooted.py")), "touches '/tmp/rooted.py' is not a plain path"),
    "dotgit": (
        written(new_file_patch(".git/hooks/pre-commit")),
        "touches .git/hooks/pre-commit is inside .git",
    ),
    "spaced": (
        changed(add("src/materica/sp ace.py")),
        "touches 'src/materica/sp ace.py' is not a plain path",
    ),
    "through": (written(new_file_patch("outside/x.py")), "touches outside/x.py leads out of the checkout"),
    "workflow": (
        changed(edit(".github/workflows/ci.yml", "push", "pull_request")),
        "touches .github/workflows/ci.yml is under .github/",
    ),
    "folded": (changed(add(".GitHub/workflows/x.yml", "on: push\n")), "is under .GitHub/"),
    "patches": (changed(add("mutants/more.patch", "")), "touches mutants/more.patch is under mutants/"),
    "runner": (
        changed(edit("scripts/mutant_runs.py", "import argparse\n", "import argparse  # changed\n")),
        "touches scripts/mutant_runs.py is the runner",
    ),
    "project": (changed(edit("pyproject.toml", "xunit1", "xunit2")), "touches pyproject.toml is the runner"),
    "lock": (changed(edit("uv.lock", "1", "2")), "touches uv.lock is the runner"),
    "uv-toml": (changed(add("uv.toml", 'resolution = "lowest"\n')), "touches uv.toml is the runner"),
    "python-version": (
        changed(add(".python-version", "3.11\n")),
        "touches .python-version is the runner",
    ),
    "python-versions": (
        changed(add(".python-versions", "3.11\n3.12\n")),
        "touches .python-versions is the runner",
    ),
    "symlink": (changed(link("src/materica/linked.py", "/etc/hostname")), "gives the mode 120000"),
    "binary": (changed(binary("src/materica/blob.bin"), "--binary"), "is a binary patch"),
    "binarynote": (changed(binary("src/materica/blob.bin")), "is a binary patch"),
    "renamed": (changed(rename("src/materica/half.py", "src/materica/other.py")), "renames or copies a file"),
    "disguised": (
        written(disguised_rename("src/materica/half.py")),
        "names two paths in one `diff --git` line, src/materica/half.py and src/materica/moved.py",
    ),
    "disguised-workflow": (
        written(disguised_rename(".github/workflows/ci.yml")),
        "touches .github/workflows/ci.yml is under .github/",
    ),
    "disguised-project": (
        written(disguised_rename("pyproject.toml")),
        "touches pyproject.toml is the runner",
    ),
    "disguised-lock": (written(disguised_rename("uv.lock")), "touches uv.lock is the runner"),
    "disguised-patches": (
        written(disguised_rename("mutants/edited.patch")),
        "touches mutants/edited.patch is under mutants/",
    ),
    "disguised-runner": (
        written(disguised_rename("scripts/mutant_runs.py")),
        "touches scripts/mutant_runs.py is the runner",
    ),
    "disguised-odd": (
        written(
            disguised_rename(
                ".github/workflows/ci.yml",
                header="diff --git x/.github/workflows/ci.yml y/src/materica/moved.py",
            )
        ),
        "has a `diff --git` line that names no plain path twice",
    ),
    "disguised-dashes": (
        written(
            disguised_rename(
                ".github/workflows/ci.yml",
                header="diff --git a/src/materica/moved.py b/src/materica/moved.py",
            )
        ),
        "has the line '--- a/.github/workflows/ci.yml' under `diff --git a/src/materica/moved.py",
    ),
    "padded": (written(PADDED), "where its `diff --git` lines name"),
    "venv-pth": (
        written(new_file_patch(".venv/lib/python3.15/site-packages/zz_probe.pth")),
        "touches .venv/lib/python3.15/site-packages/zz_probe.pth, which git ignores",
    ),
    "venv-edit": (
        written(INSTALLED_EDIT),
        "touches .venv/lib/python3.15/site-packages/somepkg.py, which git ignores",
    ),
    "examples": (
        written(new_file_patch(".hypothesis/examples/abcdef0123456789/0123456789abcdef")),
        "touches .hypothesis/examples/abcdef0123456789/0123456789abcdef, which git ignores",
    ),
    "traditional": (
        written(
            "--- a/src/materica/half.py\n+++ b/src/materica/half.py\n@@ -1,2 +1,2 @@\n def half(x):\n"
            "-    return x / 2\n+    return x / 3\n"
        ),
        "lists 1 files and 0 `diff --git` headers",
    ),
    "control": (
        lambda tree: diffed(tree, EDITED).replace("3 * x", "3 * x  # \x01"),
        "holds a control character",
    ),
    "empty": (written(""), "git cannot read mutants/empty.patch as a patch"),
    "huge": (changed(add("src/materica/huge.py", "#" * (1 << 20) + "\n")), "more than 1048576"),
    "dotted.name": (changed(EDITED), "the mutant 'dotted.name' is not named by"),
}
# Names the request refuses whose patch is no file committed in mutants/: none there, one in the tree but not
# committed, and one committed as a link to another patch.
NAMES_REFUSED = {
    "missing": "mutants/missing.patch is not a regular file committed",
    "uncommitted": "mutants/uncommitted.patch is not a regular file committed",
    "linkedpatch": "mutants/linkedpatch.patch is not a regular file committed",
}


def mutant_checkout(directory: Path) -> Path:
    """A throwaway repository holding `MUTANT_TREE`, the script, a link out of it, and a commit of every patch
    above, with one patch left uncommitted."""
    tree = directory / "tree"
    (directory / "elsewhere").mkdir(parents=True, exist_ok=True)
    for path, text in MUTANT_TREE.items():
        add(path, text)(tree)
    (tree / "scripts").mkdir(exist_ok=True)
    shutil.copy(MUTANT_SCRIPT, tree / "scripts" / "mutant_runs.py")
    (tree / "outside").symlink_to(directory / "elsewhere")
    in_git(tree, "init", "-q", "-b", "main")
    in_git(tree, "add", "-A")
    in_git(tree, "commit", "-q", "-m", "the tree")
    patches = {name: make(tree) for name, make in PATCHES_TAKEN.items()}
    patches |= {name: make(tree) for name, (make, _) in PATCHES_REFUSED.items()}
    (tree / "mutants").mkdir()
    for name, patch in patches.items():
        (tree / "mutants" / f"{name}.patch").write_bytes(patch.encode("utf-8"))
    (tree / "mutants" / "linkedpatch.patch").symlink_to("edited.patch")
    in_git(tree, "add", "-A")
    in_git(tree, "commit", "-q", "-m", "the patches")
    (tree / "mutants" / "uncommitted.patch").write_bytes(patches["edited"].encode("utf-8"))
    return tree


def mutant_runner(directory: Path, uv: str) -> dict[str, str]:
    """A runner's environment (`runner`) whose git is cut off from any repository around the run."""
    return runner(directory, uv) | {
        name: value for name, value in git_environment().items() if name.startswith("GIT_")
    }


def mutant_request_problems(
    mutants: Workflow, tree: Path, directory: Path, names: Sequence[str]
) -> list[str]:
    """Where the request job's check, run as written on the checkout `tree` for each mutant of `names` alone,
    takes a patch it must refuse, refuses one it must take, refuses one without saying why, or writes outputs
    where it refuses; or, for the patches it takes all at once, does not write each output as checked, the
    matrix the baseline and the mutants in order."""
    environment = mutant_runner(directory, "")
    check = step(mutants["jobs"]["request"], MUTANT_CHECK_STEP)
    refused = {name: why for name, (_, why) in PATCHES_REFUSED.items()} | NAMES_REFUSED
    problems: list[str] = []
    for name in names:
        inputs = {f"inputs.{key}": text for key, text in (MUTANT_REQUESTED | {"mutants": name}).items()}
        status, outputs, printed = run_step(check, inputs, tree, base=environment, scratch=directory)
        if name in refused:
            if status == 0 or outputs:
                problems.append(f"the check takes the patch {name}")
            elif refused[name] not in printed:
                problems.append(
                    f"the check refuses the patch {name} without saying {refused[name]!r}: {printed}"
                )
        elif status != 0:
            problems.append(f"the check refuses the patch {name}: {printed[-500:]}")
    taken = [name for name in PATCHES_TAKEN if name in names]
    if taken:
        inputs = {
            f"inputs.{key}": text for key, text in (MUTANT_REQUESTED | {"mutants": " ".join(taken)}).items()
        }
        status, outputs, printed = run_step(check, inputs, tree, base=environment, scratch=directory)
        expected = {
            "mutants": " ".join(taken),
            "matrix": json.dumps(["", *taken]),
            "selection": "tests",
            "profile": "dev",
            "python": "3.15",
            "seed": "7",
            "extra": "",
        }
        if (status, outputs) != (0, expected):
            problems.append(f"the check of {taken} exits {status} and writes {outputs}: {printed[-300:]}")
    return problems


EVERY_PATCH = [*PATCHES_TAKEN, *PATCHES_REFUSED, *NAMES_REFUSED]


def test_the_request_refuses_each_patch_it_cannot_run_safely_and_takes_the_others(tmp_path: Path) -> None:
    tree = mutant_checkout(tmp_path)
    assert mutant_request_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path, EVERY_PATCH) == []


# Each rule of the check taken out of the script, and the patch the check then takes: a path not plain, inside
# .git, through a link out of the tree, or one git ignores; under .github/, ignoring case, or mutants/; the
# runner, pyproject.toml, uv.lock, uv.toml or .python-version; a link made; binary data; a rename with rename
# lines, and one without, by a `diff --git` line naming two paths, one git reads in another form, or `---`
# and `+++` lines naming another path than it; the old path of a rename without them; a part not in git's
# format, counted or hidden behind a `diff --git` line with nothing under it; a patch not committed as a
# regular file; a control character; a patch too long; a name not plain. Each is the one rule that refuses
# its patch, since a patch two rules refuse would show neither: where a second rule refuses it too,
# `ALSO_TAKEN_OUT` takes that out as well.
RULES_TAKEN_OUT = {
    "plain-path": (
        'if not PLAIN_PATH.fullmatch(path) or any(part in {".", ".."} for part in parts):',
        "if False:",
        "spaced",
    ),
    "dot-git": ('if ".git" in folded:', "if False:", "dotgit"),
    "symbolic-link": (
        "if not (root / path).resolve().is_relative_to(root.resolve()):",
        "if False:",
        "through",
    ),
    "github": (
        'REFUSED_DIRECTORIES = (".github", MUTANTS_DIRECTORY)',
        "REFUSED_DIRECTORIES = (MUTANTS_DIRECTORY,)",
        "workflow",
    ),
    "case": (
        "if folded[0] in {directory.casefold() for directory in REFUSED_DIRECTORIES}:",
        "if parts[0] in REFUSED_DIRECTORIES:",
        "folded",
    ),
    "patches": (
        'REFUSED_DIRECTORIES = (".github", MUTANTS_DIRECTORY)',
        'REFUSED_DIRECTORIES = (".github",)',
        "patches",
    ),
    "runner": ("REFUSED_FILES = (RUNNER, ", "REFUSED_FILES = (", "runner"),
    "project": ('REFUSED_FILES = (RUNNER, "pyproject.toml", ', "REFUSED_FILES = (RUNNER, ", "project"),
    "lock": ('"pyproject.toml", "uv.lock", ', '"pyproject.toml", ', "lock"),
    "uv-toml": ('"uv.lock", "uv.toml", ', '"uv.lock", ', "uv-toml"),
    "python-version": ('"uv.toml", ".python-version", ', '"uv.toml", ', "python-version"),
    "ignored": ("        if each in ignored\n", "        if False\n", "venv-pth"),
    "modes": ('MODES = ("100644", "100755")', 'MODES = ("100644", "100755", "120000")', "symlink"),
    "binary": (
        "BINARY_LINE = re.compile(",
        'BINARY_LINE = re.compile(r"(?!)")\nNOT_BINARY_LINE = re.compile(',
        "binary",
    ),
    "rename": ('problems.append(f"{relative} renames or copies a file: {line.strip()}")', "pass", "renamed"),
    "one-path-twice": ("            if current is None:\n", "            if False:\n", "disguised"),
    "header-form": (
        'named.problems.append(f"has a `diff --git` line that names no plain path twice: {line!r}")',
        "pass",
        "disguised-odd",
    ),
    "dashes": (
        "            if line[4:] not in (side + current, NO_FILE):\n",
        "            if False:\n",
        "disguised-dashes",
    ),
    "old-path": (
        "    touched = list(dict.fromkeys([*paths, *named.paths]))\n",
        "    touched = list(paths)\n",
        "disguised-workflow",
    ),
    "format": ("    if len(named.headers) != len(paths):\n", "    if False:\n", "traditional"),
    "header-order": (
        "    elif None not in named.headers and named.headers != paths:\n",
        "    elif False:\n",
        "padded",
    ),
    "committed": (
        "        listed.returncode != 0\n        or len(entries) != 1\n"
        '        or not entries[0].startswith(tuple(f"{mode} blob " for mode in MODES))\n'
        "        or path.is_symlink()\n        or not path.is_file()\n",
        "        not path.exists()\n",
        "uncommitted",
    ),
    "control": (
        r'CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")',
        'CONTROL = re.compile(r"(?!)")',
        "control",
    ),
    "size": ("MAX_PATCH_BYTES = 1 << 20", "MAX_PATCH_BYTES = 1 << 30", "huge"),
    "name": (
        'NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")',
        'NAME = re.compile(r".+")',
        "dotted.name",
    ),
}


# The second rule that refuses a rule's patch, taken out with it: for a path that is not plain, the rule that
# a `diff --git` line names one plain path twice, as a space is in both; for a path through a link out of the
# tree, git's refusal to say whether it ignores it; for a rename with rename lines, the rule that a
# `diff --git` line names one path, not two; both signs of binary data, the
# marker line and git's counts of `-`; for a part not in git's format, the rule that git's report lists the
# files of the `diff --git` lines in their order; and, for the old path of a rename without rename lines, the
# rule that a `diff --git` line names one path, not two.
ALSO_TAKEN_OUT = {
    "plain-path": RULES_TAKEN_OUT["header-form"][:2],
    "symbolic-link": (
        'problems.append(f"git cannot say which paths of {relative} it ignores: {error}")',
        "pass",
    ),
    "rename": RULES_TAKEN_OUT["one-path-twice"][:2],
    "binary": ("    if binary and not problems:\n", "    if False:\n"),
    "format": RULES_TAKEN_OUT["header-order"][:2],
    "old-path": RULES_TAKEN_OUT["one-path-twice"][:2],
}


@pytest.mark.parametrize("rule", list(RULES_TAKEN_OUT))
def test_the_patch_check_can_fail(tmp_path: Path, rule: str) -> None:
    old, new, name = RULES_TAKEN_OUT[rule]
    tree = mutant_checkout(tmp_path)
    edited(tree / "scripts" / "mutant_runs.py", old, new)
    if also := ALSO_TAKEN_OUT.get(rule):
        edited(tree / "scripts" / "mutant_runs.py", *also)
    found = mutant_request_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path, [name])
    assert f"the check takes the patch {name}" in found, found


def test_the_request_names_every_committed_patch_when_none_is_named(tmp_path: Path) -> None:
    """No mutant named runs every patch committed in mutants/: here every refused patch is refused, and the
    uncommitted one is not among them."""
    tree = mutant_checkout(tmp_path)
    environment = mutant_runner(tmp_path, "")
    check = step(workflow(MUTANT_WORKFLOW)["jobs"]["request"], MUTANT_CHECK_STEP)
    inputs = {f"inputs.{key}": text for key, text in (MUTANT_REQUESTED | {"mutants": ""}).items()}
    status, outputs, printed = run_step(check, inputs, tree, base=environment, scratch=tmp_path)
    assert (status, outputs) == (1, {}), printed
    for name, (_, why) in PATCHES_REFUSED.items():
        assert why in printed, name
    assert "uncommitted" not in printed
    assert "the mutant missing" not in printed


# The request job's outputs for `MUTANT_REQUESTED`, as the jobs after it read them.
MUTANT_OUTPUTS = {
    "mutants": "edited",
    "matrix": json.dumps(["", "edited"]),
    "selection": "tests",
    "profile": "dev",
    "python": "3.15",
    "seed": "7",
    "extra": "",
    "max_parallel": "10",
}
# A `uv` that stands for `uv run ...` in a mutant's job: it records its arguments, the profile and any
# variable of pytest's or Hypothesis's; passes the import check and the collection, which prints one test;
# and for the run writes a JUnit report of that test, failed where `STUB_FAILING` is set, and exits as pytest
# stopped at a failure under pytest-xdist and `-x` does.
MUTANT_STUB_UV = """
import json, os, sys
from pathlib import Path

arguments = sys.argv[1:]
with open(os.environ["STUB_CALLS"], "a", encoding="utf-8") as calls:
    record = {
        "arguments": arguments,
        "profile": os.environ.get("MATERICA_HYPOTHESIS_PROFILE"),
        "environment": sorted(name for name in os.environ if name.startswith(("PYTEST_", "HYPOTHESIS_"))),
    }
    print(json.dumps(record), file=calls)
arguments = [word for word in arguments if word not in ("--no-sync", "--frozen")]
if arguments[:2] == ["run", "python"]:
    sys.exit(0)
if "--collect-only" in arguments:
    print("tests/test_double.py::test_double")
    sys.exit(0)
failing = bool(os.environ.get("STUB_FAILING"))
report = next(word.partition("=")[2] for word in arguments if word.startswith("--junitxml="))
Path(report).write_text(
    '<testsuites><testsuite><testcase classname="tests.test_double" name="test_double" '
    'file="tests/test_double.py">'
    + ('<failure message="assert 9 == 6">assert 9 == 6</failure>' if failing else "")
    + "</testcase></testsuite></testsuites>",
    encoding="utf-8",
)
sys.exit(2 if failing else 0)
"""
# A `uv` whose `uv run` runs the command in the checkout's environment, as the job's `uv sync` makes it: this
# Python, with the checkout's `src/` first on its path, for `python` and `pytest`, and `timeout` around it;
# `--no-sync` and `--frozen` change nothing here, as nothing is synced.
MUTANT_UV_RUN = """
import os, sys

assert sys.argv[1] == "run", sys.argv
words = [word for word in sys.argv[2:] if word not in ("--no-sync", "--frozen")]
command, rest = words[0], words[1:]
os.environ["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
if command == "python":
    os.execv(sys.executable, [sys.executable, *rest])
if command == "pytest":
    os.execv(sys.executable, [sys.executable, "-m", "pytest", *rest])
assert command == "timeout", command
at = rest.index("pytest")
os.execvp("timeout", ["timeout", *rest[:at], sys.executable, "-m", "pytest", *rest[at + 1 :]])
"""


class MutantRan(NamedTuple):
    status: int
    calls: list[dict[str, Any]]
    record: dict[str, Any] | None
    printed: str
    tree: Path
    temporary: Path


def mutant_context(outputs: Mapping[str, str], mutant: str | None = None) -> dict[str, object]:
    """The context of a step of a job after the request job, as GitHub gives it: the dispatch's inputs, the
    request job's outputs, and the request job's steps' outputs null, as GitHub gives a step the job does not
    have; and the job's mutant, for a mutant's job."""
    context: dict[str, object] = {f"inputs.{name}": value for name, value in MUTANT_REQUESTED.items()}
    for name, value in outputs.items():
        context[CHECKED_AFTER + name], context[CHECKED_IN_REQUEST + name] = value, None
    return context if mutant is None else context | {"matrix.mutant": mutant}


def run_a_mutant(
    mutants: Workflow,
    tree: Path,
    directory: Path,
    mutant: str,
    uv: str = MUTANT_STUB_UV,
    outputs: Mapping[str, str] = MUTANT_OUTPUTS,
    base: Mapping[str, str] | None = None,
    **overrides: str,
) -> MutantRan:
    """The run step of the job of `mutant` (`""` for the baseline), with its job's environment and
    `overrides`, run as written with `uv` in `directory` on a fresh clone of the checkout `tree`: its status,
    each call of the stub `uv`, the record it kept, what it printed, the clone and the job's temporary
    directory."""
    tree_copy = directory / "tree"
    in_git(tree.parent, "clone", "-q", str(tree), str(tree_copy))
    environment = mutant_runner(directory, uv) | dict(base or {})
    job = mutants["jobs"]["mutants"]
    found = step(job, MUTANT_RUN_STEP)
    found = dict(found, env=job.get("env", {}) | found.get("env", {}) | overrides)
    context = mutant_context(outputs, mutant)
    status, _, printed = run_step(found, context, tree_copy, base=environment, scratch=directory)
    calls_file = directory / "calls.jsonl"
    calls = (
        [json.loads(line) for line in calls_file.read_text("utf-8").splitlines()]
        if calls_file.exists()
        else []
    )
    kept = Path(environment["RUNNER_TEMP"]) / "record" / mutant_runs.RECORD
    record = json.loads(kept.read_text("utf-8")) if kept.exists() else None
    return MutantRan(status, calls, record, printed, tree_copy, Path(environment["RUNNER_TEMP"]))


def outcome(ran: MutantRan) -> str:
    return mutant_runs.verdict(ran.record)[0] if ran.record is not None else "no record"


def mutant_wiring_problems(mutants: Workflow, tree: Path, directory: Path) -> list[str]:
    """Where a mutant's run step, run as written with the stub `uv`, falls short: in a job of 10 minutes it
    does not apply the patch, check that the code imports with a copy of the script outside the checkout,
    collect the selection and run it under `uv run timeout --foreground --signal=INT` about 420 s, a worker
    per vCPU under `worksteal`, stopping at the first failure, under the request's seed, its report in the
    job's temporary directory, with the request's profile and no variable of pytest's or Hypothesis's; it
    does not record a passing run as survived and a failing one as killed, both exiting 0; the baseline is not
    run unpatched, exiting 0 where it passed and 1 where it failed; a patch that does not apply is not
    recorded broken without running anything; or a patch refused, or a job of too few minutes, starts
    anything or exits 0."""
    problems: list[str] = []
    ran = run_a_mutant(mutants, tree, directory / "edited", "edited", JOB_MINUTES="10")
    copy_of_script = ran.temporary / "runner" / "mutant_runs.py"
    report = ran.temporary / "record" / mutant_runs.REPORT
    unsynced = ("run", "--no-sync", "--frozen")
    expected = [
        [*unsynced, "python", str(copy_of_script), "imports", "src/materica/__init__.py"],
        [*unsynced, "pytest", "--collect-only", "-q", "tests"],
        [
            *unsynced,
            *("timeout", "--foreground", "--signal=INT", "<seconds>"),
            *("pytest", "-n", "auto", "--dist", "worksteal", "-x", "tests"),
            *("--hypothesis-seed=7", f"--junitxml={report}"),
        ],
    ]
    words = [call["arguments"] for call in ran.calls]
    at = expected[2].index("<seconds>")
    seconds = re.fullmatch(r"(\d+)s", words[2][at]) if len(words) == 3 and len(words[2]) > at else None
    if seconds:
        words[2][at] = "<seconds>"
    if words != expected:
        problems.append(f"the job of a mutant runs {words}, not {expected}")
    elif seconds is None or not 7 * 60 - 30 <= int(seconds[1]) <= 7 * 60:
        problems.append(f"a run of a job of 10 minutes is interrupted after {ran.calls[2]['arguments'][at]}")
    if not copy_of_script.is_file() or copy_of_script.is_relative_to(ran.tree):
        problems.append(f"the script that records the verdict runs from {copy_of_script}")
    problems += [
        f"a call of uv has the profile {call['profile']!r} and {call['environment']}"
        for call in ran.calls
        if call["profile"] != "dev" or call["environment"]
    ]
    if "3 * x" not in (ran.tree / "src" / "materica" / "__init__.py").read_text("utf-8"):
        problems.append("the mutant's patch was not applied")
    if (ran.status, outcome(ran)) != (0, mutant_runs.SURVIVED):
        problems.append(
            f"a mutant whose run passed exits {ran.status} as {outcome(ran)}: {ran.printed[-300:]}"
        )
    failed = run_a_mutant(mutants, tree, directory / "failing", "edited", STUB_FAILING="1")
    if (failed.status, outcome(failed)) != (0, mutant_runs.KILLED):
        problems.append(f"a mutant whose run failed exits {failed.status} as {outcome(failed)}")
    baseline = run_a_mutant(mutants, tree, directory / "baseline", "")
    imports = [call["arguments"] for call in baseline.calls if "python" in call["arguments"]]
    copy_of_baselines_script = str(baseline.temporary / "runner" / "mutant_runs.py")
    if imports != [["run", "--no-sync", "--frozen", "python", copy_of_baselines_script, "imports"]]:
        problems.append(f"the baseline's import check is {imports}")
    if in_git(baseline.tree, "status", "--porcelain") or (baseline.status, outcome(baseline)) != (
        0,
        "survived",
    ):
        problems.append(
            f"the baseline, passing, changes the tree or exits {baseline.status} as {outcome(baseline)}"
        )
    failing_baseline = run_a_mutant(mutants, tree, directory / "baseline-failing", "", STUB_FAILING="1")
    if failing_baseline.status == 0:
        problems.append("a baseline whose run failed exits 0")
    stale = run_a_mutant(mutants, tree, directory / "stale", "stale")
    if stale.calls or (stale.status, outcome(stale)) != (0, mutant_runs.BROKEN) or stale.record is None:
        problems.append(f"a patch that does not apply runs {len(stale.calls)} commands, exits {stale.status}")
    elif stale.record["applied"] is not False:
        problems.append(f"a patch that does not apply is recorded as {stale.record}")
    for name, minutes in (("workflow", "60"), ("edited", "3")):
        stopped = run_a_mutant(
            mutants, tree, directory / f"stopped-{name}-{minutes}", name, JOB_MINUTES=minutes
        )
        if stopped.calls or stopped.status == 0 or outcome(stopped) != mutant_runs.UNDECIDED:
            problems.append(
                f"the mutant {name} in a job of {minutes} minutes runs {len(stopped.calls)} commands and "
                f"exits {stopped.status} as {outcome(stopped)}"
            )
    return problems


def test_each_mutant_is_applied_and_run_as_ci_runs_pytest_and_recorded(tmp_path: Path) -> None:
    tree = mutant_checkout(tmp_path)
    assert mutant_wiring_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path) == []


def edited_run_step(mutants: Workflow, old: str, new: str) -> None:
    found = step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)
    assert found["run"].count(old) == 1, old
    found["run"] = found["run"].replace(old, new)


def the_script_run_from_the_checkout(mutants: Workflow) -> None:
    edited_run_step(mutants, 'cp scripts/mutant_runs.py "$runner/mutant_runs.py"\n', "")
    edited_run_step(mutants, '"$runner/mutant_runs.py" run', "scripts/mutant_runs.py run")


def another_profile(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"] = "ci"


# Faults of the script as the job runs it, each a change to its text: the environment synced after the patch,
# the run interrupted by TERM, the interrupt sent to pytest's group, no room left for it, the first failure
# not stopped at, the patch never applied, and a job exiting 0 whatever it found.
SCRIPT_FAULTS = {
    "synced": (
        'UV_RUN = ("uv", "run", "--no-sync", "--frozen")',
        'UV_RUN = ("uv", "run")',
        "the job of a mutant runs",
    ),
    "terminated": ('"--signal=INT"', '"--signal=TERM"', "the job of a mutant runs"),
    "group": ('"--foreground", ', "", "the job of a mutant runs"),
    "no-room": ("(minutes - 3) * 60", "minutes * 60", "interrupted after"),
    "every-failure": ('"worksteal", "-x", ', '"worksteal", ', "the job of a mutant runs"),
    "unapplied": (
        'applied = git(root, "apply", "--whitespace=nowarn", relative)',
        'applied = git(root, "status")',
        "the mutant's patch was not applied",
    ),
    "always-0": ("return 0 if decided else 1", "return 0", "a baseline whose run failed exits 0"),
}


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (the_script_run_from_the_checkout, "the script that records the verdict runs from"),
        (another_profile, "a call of uv has the profile 'ci'"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_mutant_job_check_can_fail(
    tmp_path: Path, fault: Callable[[Workflow], None], problem: str
) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    fault(mutants)
    found = mutant_wiring_problems(mutants, mutant_checkout(tmp_path), tmp_path)
    assert any(problem in line for line in found), found


def script_changed(tree: Path, old: str, new: str) -> None:
    """The checkout's script with `old` changed to `new`, committed, so that every job's clone runs it."""
    edited(tree / "scripts" / "mutant_runs.py", old, new)
    in_git(tree, "commit", "-q", "-a", "-m", "a fault of the script")


@pytest.mark.parametrize(("old", "new", "problem"), SCRIPT_FAULTS.values(), ids=list(SCRIPT_FAULTS))
def test_the_mutant_job_check_finds_a_fault_of_the_script(
    tmp_path: Path, old: str, new: str, problem: str
) -> None:
    tree = mutant_checkout(tmp_path)
    script_changed(tree, old, new)
    found = mutant_wiring_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path)
    assert any(problem in line for line in found), found


# The mutants run end to end, with this Python's pytest, and what each must come to: the baseline passes; the
# edit of `double` is killed by its test; the edit that changes nothing survives; the patch whose context is
# gone and the module that does not compile are broken; and the module beside the scripts survives, as the
# script that records the verdict runs from its copy.
END_TO_END = {
    "": (mutant_runs.SURVIVED, "2 tests passed"),
    "edited": (mutant_runs.KILLED, "tests/test_double.py::test_double"),
    "equivalent": (mutant_runs.SURVIVED, "2 tests passed"),
    "stale": (mutant_runs.BROKEN, "the patch does not apply"),
    "syntax": (mutant_runs.BROKEN, "the code does not import: src/materica/half.py does not compile"),
    "shadow": (mutant_runs.SURVIVED, "2 tests passed"),
}


def kept_record(mutants: Workflow, ran: MutantRan, mutant: str, attempt: int = 1) -> Kept:
    """The record a mutant's job keeps, as its keep step names it and upload-artifact finds it."""
    keep = step(mutants["jobs"]["mutants"], RECORD_STEP)
    context = {"matrix.mutant": mutant, "github.run_attempt": attempt, "runner.temp": str(ran.temporary)}
    name, path = (str(setting(keep["with"][key], context)) for key in ("name", "path"))
    return Kept(name, artifact_files(path), [])


def tabled(
    mutants: Workflow,
    tree: Path,
    directory: Path,
    uploads: Sequence[Kept],
    outputs: Mapping[str, str],
    result: str = "success",
    attempt: int = 1,
) -> tuple[int, str, dict[str, Any] | None]:
    """The table job's steps after its checkout, run as written on a clone of `tree`: the records fetched as
    the fetch step fetches them from `uploads`, then the table step; its status, what it printed, and the
    table it kept."""
    tree_copy = directory / "tree"
    in_git(tree.parent, "clone", "-q", str(tree), str(tree_copy))
    environment = mutant_runner(directory, "")
    job = mutants["jobs"]["table"]
    context = mutant_context(outputs) | {
        "needs.mutants.result": result,
        "github.run_attempt": attempt,
        "runner.temp": environment["RUNNER_TEMP"],
    }
    fetched(step(job, RECORDS_FETCH_STEP), context, {upload.name: upload.files for upload in uploads})
    status, _, printed = run_step(
        step(job, TABLE_STEP), context, tree_copy, base=environment, scratch=directory
    )
    kept = Path(str(setting(step(job, TABLE_KEEP_STEP)["with"]["path"], context))) / "table.json"
    return status, printed, json.loads(kept.read_text("utf-8")) if kept.exists() else None


def mutant_end_to_end_problems(
    mutants: Workflow, tree: Path, directory: Path, names: Sequence[str] = tuple(END_TO_END)
) -> list[str]:
    """Where the request job, each mutant's job and the table job, their steps run as written with this
    Python's pytest, do not take the mutants `names`, or come to another outcome for one than `END_TO_END`
    gives, exit other than 0 with it, or where the table of them all does not give each outcome and fail, as
    not every mutant was killed, or the table of the baseline and the killed mutant alone does not pass."""
    problems: list[str] = []
    environment = mutant_runner(directory / "request", MUTANT_UV_RUN)
    request = mutants["jobs"]["request"]
    named = [name for name in names if name]
    inputs = {
        f"inputs.{key}": text for key, text in (MUTANT_REQUESTED | {"mutants": " ".join(named)}).items()
    }
    status, outputs, printed = run_step(step(request, MUTANT_CHECK_STEP), inputs, tree, base=environment)
    if status != 0:
        return [f"the request of {named} exits {status}: {printed[-500:]}"]
    outputs["max_parallel"] = "10"
    collect = step(request, MUTANT_COLLECT_STEP)
    context = mutant_context(outputs) | {CHECKED_IN_REQUEST + name: value for name, value in outputs.items()}
    status, _, printed = run_step(collect, context, tree, base=environment, scratch=directory / "request")
    if status != 0:
        problems.append(f"the selection does not collect: {printed[-500:]}")
    uploads: dict[str, Kept] = {}
    workers = {"PYTEST_XDIST_AUTO_NUM_WORKERS": "2"}
    for mutant in json.loads(outputs["matrix"]):
        where = directory / f"job-{mutant or '_baseline'}"
        ran = run_a_mutant(mutants, tree, where, mutant, MUTANT_UV_RUN, outputs, base=workers)
        found = mutant_runs.verdict(ran.record) if ran.record is not None else ("no record", "")
        wanted, why = END_TO_END[mutant]
        if ran.status != 0 or found[0] != wanted or why not in found[1]:
            problems.append(
                f"the mutant {mutant!r} exits {ran.status} as {found}, not {wanted} ({why}): "
                f"{ran.printed[-500:]}"
            )
        uploads[mutant] = kept_record(mutants, ran, mutant)
    if set(names) != set(END_TO_END):
        return problems
    status, printed, table = tabled(mutants, tree, directory / "table", list(uploads.values()), outputs)
    rows = {row["mutant"]: row["outcome"] for row in (table or {}).get("rows", [])}
    if status == 0 or rows != {mutant: wanted for mutant, (wanted, _) in END_TO_END.items()}:
        problems.append(f"the table of every mutant exits {status} with the rows {rows}: {printed[-500:]}")
    alone = dict(outputs, mutants="edited", matrix=json.dumps(["", "edited"]))
    status, printed, table = tabled(
        mutants, tree, directory / "table-killed", [uploads[""], uploads["edited"]], alone
    )
    if status != 0 or table is None or not table["passed"]:
        problems.append(f"the table of the baseline and a killed mutant exits {status}: {printed[-500:]}")
    return problems


def test_three_mutants_are_killed_survive_and_are_broken_end_to_end(tmp_path: Path) -> None:
    tree = mutant_checkout(tmp_path)
    assert mutant_end_to_end_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path) == []


def test_the_end_to_end_check_finds_the_verdicts_code_run_from_the_checkout(tmp_path: Path) -> None:
    """The control: run from the checkout, the script that checks the imports imports the patch's module
    beside it, and the mutant that changes no test's code is taken for broken."""
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    the_script_run_from_the_checkout(mutants)
    found = mutant_end_to_end_problems(mutants, mutant_checkout(tmp_path), tmp_path, ["shadow"])
    assert any("the mutant 'shadow' exits 0 as ('broken'" in line for line in found), found


# Records as a mutant's job writes them, each of the baseline or a mutant, and the outcome the table must give
# each: a mutant whose patch did not apply, whose code did not import or whose selection did not collect is
# broken, though its record also holds a failed run; one refused, interrupted, or failed with no test named
# is undecided; and only a run that failed at a named test, after the baseline passed, is killed.
FAILED_TEST = [{"test": "tests/test_double.py::test_double", "message": "assert 9 == 6"}]


def crafted_record(mutant: str, **facts: object) -> dict[str, object]:
    base: dict[str, object] = {
        "mutant": mutant,
        "refused": [],
        "applied": True,
        "imports": True,
        "collected": True,
        "tests": 2,
        "status": 0,
        "failures": [],
        "message": "",
    }
    return base | facts


CRAFTED = {
    "": (crafted_record(""), "survived"),
    "killed": (crafted_record("killed", status=2, failures=FAILED_TEST), "killed"),
    "unapplied": (crafted_record("unapplied", applied=False, status=1, failures=FAILED_TEST), "broken"),
    "unimported": (crafted_record("unimported", imports=False, status=1, failures=FAILED_TEST), "broken"),
    "uncollected": (crafted_record("uncollected", collected=False, status=2, failures=FAILED_TEST), "broken"),
    "refused": (crafted_record("refused", refused=["a reason"], status=1, failures=FAILED_TEST), "undecided"),
    "interrupted": (crafted_record("interrupted", status=124, failures=FAILED_TEST), "undecided"),
    "unnamed": (crafted_record("unnamed", status=1), "undecided"),
}


def crafted_uploads(records: Mapping[str, dict[str, object]]) -> list[Kept]:
    return [
        Kept(f"record-{mutant or '_baseline'}-1", {mutant_runs.RECORD: json.dumps(record).encode()}, [])
        for mutant, record in records.items()
    ]


def table_verdict_problems(mutants: Workflow, tree: Path, directory: Path) -> list[str]:
    """Where the table step, run as written on the records `CRAFTED`, gives another outcome than each must
    have, a broken mutant's above all, or passes; or, the baseline's run failed, gives any mutant killed."""
    problems: list[str] = []
    named = [mutant for mutant in CRAFTED if mutant]
    outputs = dict(MUTANT_OUTPUTS, mutants=" ".join(named), matrix=json.dumps(["", *named]))
    records = {mutant: record for mutant, (record, _) in CRAFTED.items()}
    status, printed, table = tabled(mutants, tree, directory / "crafted", crafted_uploads(records), outputs)
    rows = {row["mutant"]: row["outcome"] for row in (table or {}).get("rows", [])}
    wanted = {mutant: expected for mutant, (_, expected) in CRAFTED.items()}
    problems += [
        f"the table gives the mutant {mutant!r} as {rows.get(mutant)}, not {expected}"
        for mutant, expected in wanted.items()
        if rows.get(mutant) != expected
    ]
    if status == 0:
        problems.append("the table passes with mutants that are not killed")
    records[""] = crafted_record("", status=2, failures=FAILED_TEST)
    status, printed, table = tabled(mutants, tree, directory / "baseline", crafted_uploads(records), outputs)
    rows = (table or {"rows": []})["rows"]
    killed = [row["mutant"] for row in rows if row["mutant"] and row["outcome"] == "killed"]
    if killed or status == 0 or table is None:
        problems.append(
            f"with the baseline failed, the table exits {status} with {killed} killed: {printed[-300:]}"
        )
    return problems


def test_the_table_never_gives_a_broken_mutant_as_killed(tmp_path: Path) -> None:
    tree = mutant_checkout(tmp_path)
    assert table_verdict_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path) == []


# Faults of the script's verdict, each a change to its text: a failed run taken for a kill before the patch's
# application, import and collection are looked at; and a kill counted after the baseline failed.
VERDICT_FAULTS = {
    "failures-first": (
        '    message = str(record.get("message", ""))\n',
        '    message = str(record.get("message", ""))\n'
        '    if record.get("failures"):\n        return KILLED, ""\n',
        "the table gives the mutant 'unapplied' as killed, not broken",
    ),
    "baseline-ignored": (
        "if baseline.outcome != SURVIVED and each.outcome == KILLED:",
        "if False:",
        "with the baseline failed, the table exits 1 with ['killed'] killed",
    ),
}


@pytest.mark.parametrize(("old", "new", "problem"), VERDICT_FAULTS.values(), ids=list(VERDICT_FAULTS))
def test_the_mutant_table_check_can_fail(tmp_path: Path, old: str, new: str, problem: str) -> None:
    tree = mutant_checkout(tmp_path)
    script_changed(tree, old, new)
    found = table_verdict_problems(workflow(MUTANT_WORKFLOW), tree, tmp_path)
    assert any(problem in line for line in found), found


def mutant_status_problems(mutants: Workflow) -> list[str]:
    """Where the mutants' jobs can start without the request job succeeding; the table does not wait for
    them, or does not run whatever they ended in once the request was checked; a record or the table is not
    kept whenever its step ran; the table does not read the mutants' result and the run's attempt; or any job
    or step carries on after a failure (`continue-on-error`), which would pass a check that failed."""
    problems = [line for line in cap_problems(mutants, CAPS[3]) if "can start without" in line]
    table = mutants["jobs"]["table"]
    if "mutants" not in table.get("needs", []):
        problems.append("the table does not wait for the mutants' jobs")
    for result in ("success", "failure", "cancelled"):
        context: dict[str, object] = {
            "success()": result == "success",
            "failure()": result == "failure",
            "cancelled()": result == "cancelled",
            "always()": True,
            "needs.request.result": "success",
            "needs.mutants.result": result,
        }
        if not truthy(evaluated(condition(table), context)):
            problems.append(f"the table does not run when the mutants' jobs end in {result}")
    for job_id, step_id, name in (("mutants", "run", RECORD_STEP), ("table", "table", TABLE_KEEP_STEP)):
        keep = step(mutants["jobs"][job_id], name)
        for standing, ended in ((PASSED, "success"), (FAILED, "failure"), (CANCELLED, "cancelled")):
            if not truthy(evaluated(condition(keep), standing | {f"steps.{step_id}.outcome": ended})):
                problems.append(f"{name!r} does not run when its step ends in {ended}")
        if truthy(evaluated(condition(keep), FAILED | {f"steps.{step_id}.outcome": "skipped"})):
            problems.append(f"{name!r} runs when its step was skipped, with nothing to keep")
    reads = step(table, TABLE_STEP).get("env", {})
    for variable, value in (
        ("MUTANTS_RESULT", "${{ needs.mutants.result }}"),
        ("ATTEMPT", "${{ github.run_attempt }}"),
    ):
        if reads.get(variable) != value:
            problems.append(f"the table step's {variable} is {reads.get(variable)!r}, not {value}")
    if "continue-on-error" in keys(mutants):
        problems.append("mutants.yml sets continue-on-error")
    return problems


def test_every_job_of_the_mutant_workflow_runs_when_it_must_and_none_carries_on() -> None:
    assert mutant_status_problems(workflow(MUTANT_WORKFLOW)) == []


def a_table_after_success_alone(mutants: Workflow) -> None:
    mutants["jobs"]["table"]["if"] = "needs.request.result == 'success'"


def a_table_before_the_mutants(mutants: Workflow) -> None:
    mutants["jobs"]["table"]["needs"] = ["request"]


def a_record_kept_on_success_alone(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], RECORD_STEP)["if"] = "success()"


def a_table_kept_when_skipped(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_KEEP_STEP)["if"] = "always()"


def a_mutant_job_started_whatever_the_request(mutants: Workflow) -> None:
    mutants["jobs"]["mutants"]["if"] = "always()"


def a_result_always_successful(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_STEP)["env"]["MUTANTS_RESULT"] = "success"


def an_attempt_always_the_first(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_STEP)["env"]["ATTEMPT"] = "1"


def a_mutant_job_that_carries_on(mutants: Workflow) -> None:
    mutants["jobs"]["mutants"]["continue-on-error"] = True


def a_run_step_that_carries_on(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["continue-on-error"] = True


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_table_after_success_alone, "the table does not run when the mutants' jobs end in failure"),
        (a_table_before_the_mutants, "the table does not wait for the mutants' jobs"),
        (a_record_kept_on_success_alone, "'Keep the record' does not run when its step ends in failure"),
        (a_table_kept_when_skipped, "'Keep the table' runs when its step was skipped"),
        (a_mutant_job_started_whatever_the_request, "can start without request"),
        (a_result_always_successful, "the table step's MUTANTS_RESULT is 'success'"),
        (an_attempt_always_the_first, "the table step's ATTEMPT is '1'"),
        (a_mutant_job_that_carries_on, "mutants.yml sets continue-on-error"),
        (a_run_step_that_carries_on, "mutants.yml sets continue-on-error"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_mutant_status_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    fault(mutants)
    found = mutant_status_problems(mutants)
    assert any(problem in line for line in found), found


def mutant_plumbing_problems(mutants: Workflow, ci: Workflow, tree: Path, directory: Path) -> list[str]:
    """Where two mutants' jobs, the baseline's among them, or two attempts of one, keep their records under
    one name; the fetch step's pattern misses one, or takes the table's; the records or the table are kept for
    another time than ci.yml's uploads that state one; or the table passes on an attempt of the run but the
    first, or with a mutant's record missing or kept twice."""
    problems: list[str] = []
    keep = step(mutants["jobs"]["mutants"], RECORD_STEP)
    table_keep = step(mutants["jobs"]["table"], TABLE_KEEP_STEP)
    fetch = step(mutants["jobs"]["table"], RECORDS_FETCH_STEP)
    named = ["", "baseline", "a", "a-1", "a-1-1", "b_2"]
    names = Counter(
        str(setting(keep["with"]["name"], {"matrix.mutant": mutant, "github.run_attempt": attempt}))
        for mutant in named
        for attempt in (1, 2, 11)
    )
    if shared := sorted(name for name, count in names.items() if count > 1):
        problems.append(f"two mutants or two attempts keep their records as {shared[:3]}")
    pattern = str(fetch["with"].get("pattern"))
    if missed := sorted(name for name in names if not fnmatch.fnmatchcase(name, pattern)):
        problems.append(f"the fetch step's pattern {pattern!r} misses {missed[:3]}")
    table_name = str(setting(table_keep["with"]["name"], {"github.run_attempt": 1}))
    if fnmatch.fnmatchcase(table_name, pattern):
        problems.append(f"the fetch step's pattern {pattern!r} takes the table, {table_name}")
    reports = {
        found.get("with", {}).get("retention-days")
        for job in ci["jobs"].values()
        for found in job.get("steps", [])
        if str(found.get("uses", "")).startswith("actions/upload-artifact@")
        and "retention-days" in found.get("with", {})
    }
    for kept in (keep, table_keep):
        if {kept["with"].get("retention-days")} != reports:
            problems.append(
                f"{kept['name']!r} keeps for {kept['with'].get('retention-days')} days, ci.yml {reports}"
            )
    records = {"": crafted_record(""), "edited": crafted_record("edited", status=2, failures=FAILED_TEST)}
    status, printed, _ = tabled(mutants, tree, directory / "first", crafted_uploads(records), MUTANT_OUTPUTS)
    if status != 0:
        problems.append(f"the table of a baseline passed and a mutant killed fails: {printed[-300:]}")
    for case, uploads, attempt in (
        ("a second attempt", crafted_uploads(records), 2),
        ("a record missing", crafted_uploads({"": records[""]}), 1),
        (
            "a record twice",
            [*crafted_uploads(records), Kept("record-edited-2", crafted_uploads(records)[1].files, [])],
            1,
        ),
    ):
        status, printed, _ = tabled(
            mutants, tree, directory / case.replace(" ", "-"), uploads, MUTANT_OUTPUTS, attempt=attempt
        )
        if status == 0:
            problems.append(f"the table passes with {case}")
    return problems


def test_every_mutants_record_of_every_attempt_reaches_the_table_under_a_name_of_its_own(
    tmp_path: Path,
) -> None:
    tree = mutant_checkout(tmp_path)
    assert mutant_plumbing_problems(workflow(MUTANT_WORKFLOW), workflow("ci.yml"), tree, tmp_path) == []


def records_by_mutant_alone(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], RECORD_STEP)["with"]["name"] = (
        "record-${{ matrix.mutant || '_baseline' }}"
    )


def a_baseline_named_as_a_mutant(mutants: Workflow) -> None:
    keep = step(mutants["jobs"]["mutants"], RECORD_STEP)
    keep["with"]["name"] = keep["with"]["name"].replace("'_baseline'", "'baseline'")


def a_record_pattern_of_another_name(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], RECORDS_FETCH_STEP)["with"]["pattern"] = "records-*"


def a_pattern_taking_the_table(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], RECORDS_FETCH_STEP)["with"]["pattern"] = "*"


def mutant_records_kept_a_day(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], RECORD_STEP)["with"]["retention-days"] = 1


def a_table_of_any_attempt(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_STEP)["env"]["ATTEMPT"] = "1"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (records_by_mutant_alone, "two mutants or two attempts keep their records as ['record-_baseline'"),
        (
            a_baseline_named_as_a_mutant,
            "two mutants or two attempts keep their records as ['record-baseline-1'",
        ),
        (a_record_pattern_of_another_name, "the fetch step's pattern 'records-*' misses"),
        (a_pattern_taking_the_table, "the fetch step's pattern '*' takes the table"),
        (mutant_records_kept_a_day, "'Keep the record' keeps for 1 days"),
        (a_table_of_any_attempt, "the table passes with a second attempt"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_mutant_plumbing_check_can_fail(
    tmp_path: Path, fault: Callable[[Workflow], None], problem: str
) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    fault(mutants)
    found = mutant_plumbing_problems(mutants, workflow("ci.yml"), mutant_checkout(tmp_path), tmp_path)
    assert any(problem in line for line in found), found


# The variables, and setup-uv's setting, that carry a part of the checked request into a step, and that part.
MUTANT_CARRIERS = {
    "MUTANTS": "mutants",
    "SELECTION": "selection",
    "PROFILE": "profile",
    "MATERICA_HYPOTHESIS_PROFILE": "profile",
    "PYTHON_VERSION": "python",
    "SEED": "seed",
    "EXTRA": "extra",
    "python-version": "python",
}


def mutant_reach_problems(mutants: Workflow, repeat: Workflow) -> list[str]:
    """Where an input could reach pytest's options, the Hypothesis settings or a patch but as the request's
    check passed it: an input read anywhere but the check step's environment, the run's name and the
    concurrency group; an expression in a script; a variable of pytest's or Hypothesis's; a step that runs
    pytest without the checked profile; profiles or Pythons other than repeat.yml's and the script's; a job
    that reads the checked request by another route than its own, or an output the request job does not
    write; a part of the request carried as anything but its checked value; or a request job's output that is
    not its checks'."""
    problems: list[str] = []
    request = mutants["jobs"]["request"]
    check = str(request["steps"].index(step(request, MUTANT_CHECK_STEP)))
    for at, text in places(mutants):
        if (
            INPUT.search(text)
            and at not in INPUTS_READ_AT
            and at[:5] != ("jobs", "request", "steps", check, "env")
        ):
            problems.append(f"an input is read at {'.'.join(at)}")
    problems += [
        f"mutants.yml sets {name}"
        for name in map(str, keys(mutants))
        if name.startswith(("PYTEST_", "HYPOTHESIS_"))
    ]
    written: dict[str, object] = request.get("outputs", {})
    problems += [
        f"the request job's output {name} is {value!r}"
        for name, value in written.items()
        if value != (CAP_OUTPUT if name == CAP_STEP_OUTPUT else f"${{{{ {CHECKED_IN_REQUEST}{name} }}}}")
    ]
    for job_id, job in mutants["jobs"].items():
        own, other = checked_route(job_id)
        for at, text in places(job):
            if other in text:
                problems.append(f"{job_id} reads the request through {other} at {'.'.join(at)}")
            problems += [
                f"{job_id} reads {CHECKED_AFTER}{name}, which the request job does not write"
                for name in re.findall(rf"\b{re.escape(CHECKED_AFTER)}(\w+)", text)
                if name not in written
            ]
        for index, found in enumerate(job.get("steps", [])):
            script = str(found.get("run", ""))
            if "${{" in script:
                problems.append(f"a script of {job_id} holds an expression")
            if re.search(r"\b(?:PYTEST|HYPOTHESIS)_\w+=", script):
                problems.append(f"a script of {job_id} sets a variable of pytest's or Hypothesis's")
            carried = dict(found.get("env", {}))
            if str(found.get("uses", "")).startswith("astral-sh/setup-uv@"):
                carried["python-version"] = found.get("with", {}).get("python-version")
            runs_pytest = "pytest" in script or (job_id, found.get("name")) == ("mutants", MUTANT_RUN_STEP)
            if runs_pytest and "MATERICA_HYPOTHESIS_PROFILE" not in carried:
                problems.append(f"step {index} of {job_id} runs pytest without the checked profile")
            if found.get("name") == MUTANT_CHECK_STEP:
                continue
            for key, value in carried.items():
                expected = f"${{{{ {own}{MUTANT_CARRIERS[key]} }}}}" if key in MUTANT_CARRIERS else value
                if value != expected:
                    problems.append(f"step {index} of {job_id} sets {key} to {value!r}, not {expected}")
    inputs = dispatch(mutants)["workflow_dispatch"]["inputs"]
    repeat_inputs = dispatch(repeat)["workflow_dispatch"]["inputs"]
    for name, fixed in (("profile", mutant_runs.PROFILES), ("python", mutant_runs.PYTHONS)):
        listed = [inputs[name]["options"], list(fixed), repeat_inputs[name]["options"]]
        if any(each != listed[0] for each in listed):
            problems.append(f"the {name}s of mutants.yml, its script and repeat.yml are {listed}")
    if mutant_runs.OPTIONS.keys() != repeat_runs.OPTIONS.keys():
        problems.append(
            f"the extra options are {list(mutant_runs.OPTIONS)}, repeat.yml's {list(repeat_runs.OPTIONS)}"
        )
    return problems


def test_no_input_reaches_the_hypothesis_settings_pytests_options_or_a_patch_unchecked() -> None:
    assert mutant_reach_problems(workflow(MUTANT_WORKFLOW), workflow(REPEAT)) == []


def the_mutant_from_the_input(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["env"]["MUTANT"] = "${{ inputs.mutants }}"


def the_selection_from_the_input(mutants: Workflow) -> None:
    step(mutants["jobs"]["request"], MUTANT_COLLECT_STEP)["env"]["SELECTION"] = "${{ inputs.selection }}"


def a_profile_of_the_mutants_own(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"] = "dev"


def no_profile_for_the_run(mutants: Workflow) -> None:
    del step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["env"]["MATERICA_HYPOTHESIS_PROFILE"]


def an_expression_in_the_run(mutants: Workflow) -> None:
    edited_run_step(
        mutants, 'run "$RUNNER_TEMP/record"\n', 'run "$RUNNER_TEMP/record" "${{ matrix.mutant }}"\n'
    )


def options_for_every_step(mutants: Workflow) -> None:
    mutants["env"]["PYTEST_ADDOPTS"] = "-p no:randomly"


def a_seed_of_the_requests_step(mutants: Workflow) -> None:
    step(mutants["jobs"]["mutants"], MUTANT_RUN_STEP)["env"]["SEED"] = "${{ steps.checked.outputs.seed }}"


def an_output_never_written_read(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_STEP)["env"]["SEED"] = "${{ needs.request.outputs.sead }}"


def a_profile_option_of_its_own(mutants: Workflow) -> None:
    dispatch(mutants)["workflow_dispatch"]["inputs"]["profile"]["options"].append("quick")


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (the_mutant_from_the_input, "an input is read at jobs.mutants.steps.3.env.MUTANT"),
        (the_selection_from_the_input, "an input is read at jobs.request.steps.4.env.SELECTION"),
        (a_profile_of_the_mutants_own, "step 3 of mutants sets MATERICA_HYPOTHESIS_PROFILE to 'dev'"),
        (no_profile_for_the_run, "step 3 of mutants runs pytest without the checked profile"),
        (an_expression_in_the_run, "a script of mutants holds an expression"),
        (options_for_every_step, "mutants.yml sets PYTEST_ADDOPTS"),
        (a_seed_of_the_requests_step, "mutants reads the request through steps.checked.outputs. at steps.3"),
        (
            an_output_never_written_read,
            "table reads needs.request.outputs.sead, which the request job does not",
        ),
        (a_profile_option_of_its_own, "the profiles of mutants.yml, its script and repeat.yml are"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_mutant_reach_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    fault(mutants)
    found = mutant_reach_problems(mutants, workflow(REPEAT))
    assert any(problem in line for line in found), found


def test_the_mutant_workflow_runs_on_a_dispatch_by_hand_alone_and_reads_and_writes_nothing_else() -> None:
    assert triggers_problems(workflow(MUTANT_WORKFLOW), MUTANT_WORKFLOW) == []
    assert safety_problems(workflow(MUTANT_WORKFLOW), workflows(), MUTANT_WORKFLOW) == []


def a_push_too(mutants: Workflow) -> None:
    cast(dict[object, object], mutants)[True] = {"workflow_dispatch": {}, "push": {}}


def written_mutant_permissions(mutants: Workflow) -> None:
    mutants["permissions"] = {"contents": "write"}


def a_secret_in_the_table(mutants: Workflow) -> None:
    step(mutants["jobs"]["table"], TABLE_STEP)["env"]["TOKEN"] = "${{ secrets.CONFIDENTIAL_SCAN_KEY }}"


def the_mutants_uv_cache_saved(mutants: Workflow) -> None:
    del mutants["jobs"]["mutants"]["steps"][1]["with"]["save-cache"]


def the_mutants_token_kept(mutants: Workflow) -> None:
    del mutants["jobs"]["mutants"]["steps"][0]["with"]["persist-credentials"]


def the_tables_checkout_by_its_tag(mutants: Workflow) -> None:
    mutants["jobs"]["table"]["steps"][0]["uses"] = "actions/checkout@v7"


@pytest.mark.parametrize(
    ("fault", "problem"),
    [
        (a_push_too, "mutants.yml runs on {'workflow_dispatch': {}, 'push': {}}"),
        (written_mutant_permissions, "mutants.yml has the permissions {'contents': 'write'}"),
        (a_secret_in_the_table, "mutants.yml reads secrets"),
        (the_mutants_uv_cache_saved, "mutants saves the uv cache"),
        (the_mutants_token_kept, "mutants keeps the token in its checkout"),
        (the_tables_checkout_by_its_tag, "table uses actions/checkout@v7, not pinned to a commit"),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_mutant_safety_check_can_fail(fault: Callable[[Workflow], None], problem: str) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    fault(mutants)
    found = triggers_problems(mutants, MUTANT_WORKFLOW) + safety_problems(
        mutants, workflows(), MUTANT_WORKFLOW
    )
    assert any(problem in line for line in found), found


# A dispatch of the request above on one ref, and those that differ from it in one input each.
MUTANT_DISPATCHED = {"github.ref": "refs/heads/a", "github.run_id": "1"} | {
    f"inputs.{name}": value for name, value in MUTANT_REQUESTED.items()
}
MUTANT_DIFFERING = {
    "github.ref": "refs/heads/b",
    "inputs.mutants": "added",
    "inputs.selection": "tests/unit",
    "inputs.profile": "ci",
    "inputs.python": "3.11",
    "inputs.seed": "8",
    "inputs.extra": "--shard records",
}


def mutant_concurrency_problems(mutants: Workflow) -> list[str]:
    """Where two dispatches of one request on one ref could run at once, or a dispatch could cancel another or
    wait behind another request."""
    settings = cast(dict[str, object], mutants.get("concurrency") or {})
    context = MUTANT_DISPATCHED | {"github.workflow": mutants["name"]}
    problems: list[str] = []
    if truthy(setting(settings.get("cancel-in-progress", False), context)):
        problems.append("a dispatch cancels the one running in its group")
    group = setting(settings.get("group"), context)
    if group in (None, "") or setting(settings.get("group"), context | {"github.run_id": "2"}) != group:
        problems.append("two dispatches of one request on one ref do not share a group")
    problems += [
        f"a dispatch of another {key} shares the group {group!r}"
        for key, value in MUTANT_DIFFERING.items()
        if setting(settings.get("group"), context | {key: value}) == group
    ]
    return problems


def test_a_mutant_dispatch_waits_only_behind_one_of_the_same_request() -> None:
    assert mutant_concurrency_problems(workflow(MUTANT_WORKFLOW)) == []


@pytest.mark.parametrize(
    ("concurrency", "problem"),
    [
        (None, "two dispatches of one request on one ref do not share a group"),
        (
            {"group": "${{ github.workflow }}-${{ github.ref }}"},
            "a dispatch of another inputs.mutants shares",
        ),
        ({"group": "${{ github.workflow }}-${{ github.run_id }}"}, "of one request on one ref do not share"),
        ({"group": "${{ github.workflow }}", "cancel-in-progress": True}, "cancels the one running"),
    ],
    ids=["none", "a-group-per-ref", "a-group-per-run", "cancelling"],
)
def test_the_mutant_concurrency_check_can_fail(concurrency: object, problem: str) -> None:
    mutants = copy.deepcopy(workflow(MUTANT_WORKFLOW))
    mutants["concurrency"] = concurrency
    found = mutant_concurrency_problems(mutants)
    assert any(problem in line for line in found), found


# The heading of the workflows README's section on mutants.yml, whose table holds a row for each of its jobs.
MUTANTS_HEADING = "## Mutant tables (`mutants.yml`)"


def test_the_workflows_readme_names_the_jobs_of_the_mutant_workflow() -> None:
    readme = (WORKFLOWS / "README.md").read_text(encoding="utf-8")
    assert repeat_table_problems(readme, workflow(MUTANT_WORKFLOW), MUTANTS_HEADING) == []
    assert readme.count("| `table` |") == 1
    assert repeat_table_problems(
        readme.replace("| `table` |", "| `tables` |"), workflow(MUTANT_WORKFLOW), MUTANTS_HEADING
    )
    assert repeat_table_problems(
        readme.replace(MUTANTS_HEADING, "## Mutants"), workflow(MUTANT_WORKFLOW), MUTANTS_HEADING
    )


# The repeat request's warning on a node whose tests are derandomized (#43's review, L7): nodes, with extra
# arguments, and the modules the warning must name, none for a node it must not warn on. `--property-controls
# none` leaves the audit controls out, and the modules whose own code derandomizes a search in:
# test_audits.py, and test_harvested_constants.py, which runs searches with `derandomize=True` to show what
# they draw.
DERANDOMIZED_NODES: list[tuple[str, str, list[str]]] = [
    ("tests/unit/test_audit_controls.py", "", ["tests/unit/test_audit_controls.py"]),
    ("tests/unit/test_audits.py", "", ["tests/unit/test_audits.py"]),
    ("tests/unit/test_repeat_runs.py::test_with_every_run_failed_the_bound_is_one", "", []),
    (
        "tests/unit",
        "--property-controls=none",
        ["tests/unit/test_audits.py", "tests/unit/test_harvested_constants.py"],
    ),
]
DERANDOMIZED_WARNING = "::warning title=Derandomized tests::"


def derandomized_warning_problems(repeat: Workflow, directory: Path) -> list[str]:
    """Where the request job's collect step, run as written on this repository, refuses a node it must take
    because its tests are derandomized, or does not warn naming exactly the derandomized modules of what
    pytest collected, in one workflow command, or warns on a node whose tests are not."""
    environment = runner(directory, UV_RUN)
    collect = step(repeat["jobs"]["request"], COLLECT_STEP)
    problems: list[str] = []
    for node, extra, modules in DERANDOMIZED_NODES:
        context = job_context("request", CHECKED | {"node": node, "extra": extra})
        status, outputs, printed = run_step(collect, context, REPOSITORY, base=environment, scratch=directory)
        warnings = [line for line in workflow_commands(printed) if line.startswith(DERANDOMIZED_WARNING)]
        named = re.findall(r"tests/[\w/]+\.py", " ".join(warnings))
        if status != 0 or outputs:
            problems.append(f"the collect step refuses {node!r} with {extra!r}: {printed[-300:]}")
        if (len(warnings), named) != ((1, modules) if modules else (0, [])):
            problems.append(f"the collect step warns on {node!r} with {extra!r} as {warnings}")
    return problems


def test_the_repeat_request_warns_on_a_derandomized_node_and_takes_it(tmp_path: Path) -> None:
    assert derandomized_warning_problems(workflow(REPEAT), tmp_path) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (
            'python3 scripts/repeat_runs.py derandomized <<< "$collected"\n',
            "",
            "the collect step warns on 'tests/unit/test_audit_controls.py' with '' as []",
        ),
        (
            'python3 scripts/repeat_runs.py derandomized <<< "$collected"\n',
            'python3 scripts/repeat_runs.py derandomized <<< "$collected" | grep -q . && exit 1\n',
            "the collect step refuses 'tests/unit/test_audit_controls.py'",
        ),
        (
            'python3 scripts/repeat_runs.py derandomized <<< "$collected"\n',
            'python3 scripts/repeat_runs.py derandomized <<< "$NODE"\n',
            "the collect step warns on 'tests/unit/test_audits.py' with '' as []",
        ),
        (
            'python3 scripts/repeat_runs.py derandomized <<< "$collected"\n',
            'python3 scripts/repeat_runs.py derandomized <<< "$(uv run pytest --collect-only -q "$NODE")"\n',
            "the collect step warns on 'tests/unit' with '--property-controls=none' as",
        ),
    ],
    ids=["no-warning", "a-refusal", "the-node-not-the-collection", "the-extra-arguments-left-out"],
)
def test_the_derandomized_warning_check_can_fail(tmp_path: Path, old: str, new: str, problem: str) -> None:
    repeat = copy.deepcopy(workflow(REPEAT))
    collect = step(repeat["jobs"]["request"], COLLECT_STEP)
    assert collect["run"].count(old) == 1
    collect["run"] = collect["run"].replace(old, new)
    found = derandomized_warning_problems(repeat, tmp_path)
    assert any(problem in line for line in found), found
