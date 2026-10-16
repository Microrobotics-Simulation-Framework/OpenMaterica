# SPDX-License-Identifier: Apache-2.0
"""The workflows do what their comments say.

A workflow that runs less than it claims still goes green, so each test here holds one thing nothing else
would notice breaking, and each has a control in which the check must fail.
"""

import ast
import copy
import itertools
import math
import os
import re
import shlex
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Callable, Mapping, Set
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

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
    loaded: Workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return loaded


def unpinned_jobs(workflows: dict[str, Workflow]) -> list[str]:
    """Each job, by workflow, that does not run on `RUNNER_IMAGE`."""
    return [
        f"{name}: {job_id} runs on {job.get('runs-on')!r}"
        for name, loaded in workflows.items()
        for job_id, job in loaded["jobs"].items()
        if job.get("runs-on") != RUNNER_IMAGE
    ]


def workflows() -> dict[str, Workflow]:
    """Every workflow, by its file's name."""
    names = sorted(path.name for path in WORKFLOWS.glob("*.yml"))
    assert {"ci.yml", "pages.yml", "release.yml"} <= set(names)
    return {name: workflow(name) for name in names}


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
# (`github.event_name`), the status functions (`success()`), `!`, `==`, `!=`, `&&`, `||` and parentheses.
# Anything else fails the test, rather than be guessed.
EXPRESSION_TOKEN = re.compile(
    r"\s*('(?:[^']|'')*'|\d+(?:\.\d+)?|[A-Za-z_][\w.-]*(?:\(\))?|==|!=|&&|\|\||[!()])"
)
STATUS_FUNCTION = re.compile(r"\b(?:success|failure|cancelled|always)\(\)")


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
    context = {"github.event_name": "push", "github.run_id": "7", "matrix.python": "3.15"}
    cases = {
        "github.event_name == 'PUSH'": True,
        "github.event_name != 'push'": False,
        "github.event_name == 'pull_request' && 'cancel' || github.run_id": "7",
        "github.event_name == 'push' && 'push' || github.run_id": "push",
        "!(matrix.python == '3.15') || null": None,
        "github.run_id == 7": True,
        "'it''s'": "it's",
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


def run_step(
    found: dict[str, Any], context: Mapping[str, object], cwd: Path
) -> tuple[int, dict[str, str], str]:
    """The step's script run in `cwd` as GitHub runs it, from a file, with `GITHUB_BASH`: its exit status,
    what it wrote to `GITHUB_OUTPUT` (a file beside `cwd`), and what it printed."""
    script = cwd.parent / f"{cwd.name}.step.sh"
    script.write_text(rendered(found["run"], context), encoding="utf-8")
    outputs = cwd.parent / f"{cwd.name}.github_output"
    outputs.write_text("", encoding="utf-8")
    environment = dict(os.environ, GITHUB_OUTPUT=str(outputs))
    environment |= {name: rendered(str(value), context) for name, value in found.get("env", {}).items()}
    ran = subprocess.run(
        [*GITHUB_BASH, str(script)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    written = dict(line.split("=", 1) for line in outputs.read_text(encoding="utf-8").splitlines())
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


def gate_outputs(repository: Path, context: dict[str, str]) -> dict[str, str]:
    status, outputs, printed = run_step(
        step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP), context, repository
    )
    assert status == 0, printed
    return outputs


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "repository").mkdir()
    root = throwaway_repository(tmp_path / "repository", monkeypatch)
    commit("src/materica/core/read.py", "README.md", "CHANGELOG.md")
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
    }


def test_a_manual_run_of_the_fuzz_job_alone_runs_no_other_job(repository: Path) -> None:
    assert gate_outputs(repository, gate_context("workflow_dispatch", fuzz_only="true")) == {
        "code": "false",
        "hypothesis": "false",
    }


@pytest.mark.parametrize(
    ("paths", "code", "hypothesis"),
    [
        pytest.param(list(DOCUMENTATION_EXAMPLES), "false", "false", id="documentation"),
        # Code, though written as documentation: what the wheel, the type checkers, the spec-sync tests and
        # the Pages workflow read.
        (["README.md"], "true", "false"),
        (["LICENSE"], "true", "false"),
        (["typings/atheris/__init__.pyi"], "true", "false"),
        (["docs/specification/README.md"], "true", "false"),
        (["site/index.html"], "true", "false"),
        # A path nobody listed is code, and one path of code makes a change code.
        (["notes/plan.txt"], "true", "false"),
        (["CHANGELOG.md", "scripts/check_wheel.py"], "true", "false"),
        # A diff with no path at all, as if the diff had gone wrong: the safe side.
        ([], "true", "false"),
        (["tests/unit/test_read.py"], "true", "false"),
        (["src/materica/core/read.py"], "true", "true"),
    ],
    ids=lambda value: "+".join(cast(list[str], value)) or "nothing" if isinstance(value, list) else None,
)
def test_a_pull_request_runs_the_jobs_its_paths_need(
    repository: Path, paths: list[str], code: str, hypothesis: str
) -> None:
    base = commit()
    head = commit(*paths)
    assert gate_outputs(repository, gate_context("pull_request", base, head)) == {
        "code": code,
        "hypothesis": hypothesis,
    }


@pytest.mark.parametrize(
    ("source", "destination", "also", "hypothesis"),
    [
        ("src/materica/core/read.py", "docs/regulatory/read.py", (), "true"),
        ("src/materica/core/read.py", "docs/validation/read.py", ("CHANGELOG.md",), "true"),
        ("tests/unit/test_read.py", "docs/validation/test_read.py", (), "false"),
        ("tests/unit/test_read.py", ".github/ISSUE_TEMPLATE/test_read.py", (), "false"),
    ],
    ids=[
        "core-into-regulatory",
        "core-into-validation-beside-the-changelog",
        "test-into-validation",
        "test-into-the-issue-templates",
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
    }


def documentation_pattern() -> str:
    """The gate's pattern of the paths that are documentation only (`docs_paths`), matched whole."""
    found = re.search(
        r"^ *docs_paths='([^']+)'$", step(workflow("ci.yml")["jobs"]["gate"], GATE_STEP)["run"], re.M
    )
    assert found, "the gate's step sets no docs_paths"
    return found[1]


def checkout_files() -> list[str]:
    """Every file of the checkout but those of git and of the virtual environment: an export of a commit has
    no `.git/` to list the tracked files."""
    files: list[str] = []
    for directory, subdirectories, names in os.walk(REPOSITORY):
        subdirectories[:] = [name for name in subdirectories if name not in {".git", ".venv"}]
        files += [(Path(directory) / name).relative_to(REPOSITORY).as_posix() for name in names]
    return files


def named_paths(source: str) -> set[str]:
    """What a Python module could name a path by: each string, and each run of strings joined by `/`, as in
    `REPOSITORY / "docs" / "specification"`."""
    names: set[str] = set()
    in_a_join: set[int] = set()

    def operands(node: ast.expr) -> list[ast.expr]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            in_a_join.add(id(node))
            return operands(node.left) + operands(node.right)
        return [node]

    # ast.walk reaches a join before its parts, so that a part joined is not also taken alone.
    for node in ast.walk(ast.parse(source)):
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
            names.add(node.value)
    return names


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
    """Whether `name` can mean `path`: the path, its end (`intended_use.md`), or a directory it is in."""
    name = name.removeprefix("./").strip("/")
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
} | {
    ("tests/unit/test_ci_workflows.py", example): "a path the gate's tests commit in a throwaway repository"
    for example in DOCUMENTATION_EXAMPLES
}


def documentation_named(pattern: str, files: list[str], named: dict[str, set[str]]) -> list[str]:
    """Each place a test, a script or the build names a path that `pattern` calls documentation, but those
    `NAMED_NOT_READ` gives; and each of those it no longer finds."""
    documentation = [path for path in files if re.fullmatch(pattern, path)]
    found = {
        (reader, name, path)
        for reader, names_there in named.items()
        for name in names_there
        for path in documentation
        if names(name, path)
    }
    problems = [
        f"{reader} names {path} as {name!r}, and the gate calls it documentation"
        for reader, name, path in sorted(found)
        if (reader, name) not in NAMED_NOT_READ
    ]
    still_named = {(reader, name) for reader, name, _ in found}
    return problems + [
        f"{reader} no longer names {name!r}" for reader, name in sorted(NAMED_NOT_READ.keys() - still_named)
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
    ],
    ids=["readme", "specification", "a-script", "a-joined-directory", "an-f-string"],
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


def result_status(gate: str, code: str, hypothesis: str, jobs: dict[str, str], tmp_path: Path) -> int:
    """The result step's exit status, for the gate's result and outputs and each other job's result."""
    context = {
        "needs.gate.result": gate,
        "needs.gate.outputs.code": code,
        "needs.gate.outputs.hypothesis": hypothesis,
    } | {f"needs.{job}.result": result for job, result in jobs.items()}
    status, _, _ = run_step(step(workflow("ci.yml")["jobs"]["result"], RESULT_STEP), context, tmp_path)
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
        ("success", "false", "false", all_jobs("skipped", tests="failure")),
    ],
    ids=[
        "asked-for-and-skipped",
        "controls-asked-for-and-skipped",
        "hypothesis-asked-for-and-skipped",
        "asked-for-and-cancelled",
        "outputs-empty",
        "gate-failed",
        "not-asked-for-and-failed",
    ],
)
def test_the_result_fails_when_a_job_the_gate_asked_for_did_not_succeed(
    tmp_path: Path, gate: str, code: str, hypothesis: str, jobs: dict[str, str]
) -> None:
    """A skipped job reports success to a required check: a gate whose outputs are empty or wrong would skip
    every job, and a result that looked only for failures would pass."""
    assert result_status(gate, code, hypothesis, jobs, tmp_path) == 1


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
        if job.get("if") != f"needs.gate.outputs.{output} == 'true'":
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


# The mutant searches and the audit controls by file, as the maintainer named them; CI selects them with
# `--property-controls`, by module (`PROPERTY_CONTROLS` in tests/conftest.py).
CONTROL_FILES = re.compile(r"tests/(?:[^/]+/)*test_[^/]*mutants[^/]*\.py|tests/unit/test_audit_controls\.py")


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
    controls = {test for test in every if CONTROL_FILES.fullmatch(test.partition("::")[0])}
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
    control_files = {
        test.partition("::")[0] for test in selected[None] if CONTROL_FILES.fullmatch(test.partition("::")[0])
    }
    on_disk = {
        path.relative_to(REPOSITORY).as_posix()
        for path in (REPOSITORY / "tests").rglob("test_*.py")
        if CONTROL_FILES.fullmatch(path.relative_to(REPOSITORY).as_posix())
    }
    assert "tests/unit/test_audit_controls.py" in on_disk
    assert control_files == on_disk
    assert matrix_problems(workflow("ci.yml"), selected) == []


READ, AUDIT = "tests/unit/test_read.py::test_reads", "tests/unit/test_audit_controls.py::test_control"
MUTANTS, WRITER_MUTANTS = (
    "tests/property/test_mutants.py::test_kills",
    "tests/property/test_writer_mutants.py::test_kills",
)
EVERY = frozenset({READ, AUDIT, MUTANTS, WRITER_MUTANTS})
SELECTED: dict[str | None, frozenset[str]] = {None: EVERY, "none": frozenset({READ}), "only": EVERY - {READ}}


def test_the_matrix_check_passes_the_selection_meant() -> None:
    assert matrix_problems(workflow("ci.yml"), SELECTED) == []


def controls_on_3_11_alone(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["strategy"]["matrix"]["python"] = ["3.11"]


def controls_job_running_none(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    ci["jobs"]["controls"]["steps"][3]["run"] = ci["jobs"]["controls"]["steps"][3]["run"].replace(
        "only", "none"
    )


def a_mutant_module_left_unselected(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> None:
    selected["only"] = selected["only"] - {WRITER_MUTANTS}


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
SELECTIONS = {
    # Every test but the mutant searches and the audit controls.
    "tests": [["--property-controls", "none"]],
    # The mutant searches and the audit controls alone.
    "controls": [["--property-controls", "only"]],
    # The property tests of one shard.
    "hypothesis": [["tests/property", "--shard", "${{matrix.shard}}"]],
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
        # The replay: the property tests, but the writer schema's, no fuzz target, and the mutant tables,
        # which keep no example database.
        [
            "tests/property",
            "--ignore=tests/property/test_writer_properties.py",
            "--ignore=tests/property/test_writer_mutants.py",
            "--ignore=tests/property/test_mutants.py",
            "--ignore=tests/property/test_record_mutants.py",
            "--ignore=tests/property/test_value_field_mutants.py",
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
    """Where the workflows README's table names other jobs than `ci.yml` has, or other Hypothesis shards."""
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
        ("four shards side by side", "three shards side by side", "the table's shards are three"),
        (", `step8_mutants`)", ")", "the table's shards are four"),
        ("shards side by side", "shards", "names no shards"),
    ],
    ids=["a-job-renamed", "a-count-wrong", "a-shard-missing", "no-shards"],
)
def test_the_table_check_can_fail(old: str, new: str, problem: str) -> None:
    readme = (WORKFLOWS / "README.md").read_text(encoding="utf-8")
    assert readme.count(old) == 1
    found = table_problems(readme.replace(old, new), workflow("ci.yml"))
    assert any(problem in line for line in found), found
