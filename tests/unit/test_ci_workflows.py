# SPDX-License-Identifier: Apache-2.0
"""The workflows do what their comments say.

A workflow that runs less than it claims still goes green, so each test here holds one thing nothing else
would notice breaking, and each has a control in which the check must fail.
"""

import ast
import copy
import os
import re
import shlex
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Callable, Set
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


def test_every_job_of_every_workflow_runs_on_the_pinned_image() -> None:
    names = sorted(path.name for path in WORKFLOWS.glob("*.yml"))
    assert {"ci.yml", "pages.yml", "release.yml"} <= set(names)
    assert unpinned_jobs({name: workflow(name) for name in names}) == []


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


def rendered(text: str, context: dict[str, str]) -> str:
    """`text` with each `${{ expression }}` filled in from `context`; an expression it lacks fails the test,
    rather than run the step with a guess."""

    def value(match: re.Match[str]) -> str:
        expression = match[1].strip()
        assert expression in context, f"the test does not know the expression {expression!r}"
        return context[expression]

    return re.sub(r"\$\{\{(.*?)\}\}", value, text)


def run_step(found: dict[str, Any], context: dict[str, str], cwd: Path) -> tuple[int, dict[str, str], str]:
    """The step's script run in `cwd` as GitHub runs it, under bash with `-e` and `pipefail`: its exit status,
    what it wrote to `GITHUB_OUTPUT` (a file beside `cwd`), and what it printed."""
    outputs = cwd.parent / f"{cwd.name}.github_output"
    outputs.write_text("", encoding="utf-8")
    environment = dict(os.environ, GITHUB_OUTPUT=str(outputs))
    environment |= {name: rendered(str(value), context) for name, value in found.get("env", {}).items()}
    ran = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", rendered(found["run"], context)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    written = dict(line.split("=", 1) for line in outputs.read_text(encoding="utf-8").splitlines())
    return ran.returncode, written, ran.stdout + ran.stderr


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


def pytest_commands(job: dict[str, Any]) -> list[list[str]]:
    """Each pytest command of the job, its arguments as the shell splits them, up to the end of the command;
    an expression `${{ ... }}` is kept as one word."""
    commands: list[list[str]] = []
    for found in job.get("steps", []):
        script = re.sub(r"\\\n", " ", str(found.get("run", "")))
        for line in script.splitlines():
            line = re.sub(r"\$\{\{(.*?)\}\}", lambda match: "${{" + match[1].replace(" ", "") + "}}", line)
            words = list(shlex.shlex(line, posix=True, punctuation_chars=True))
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


def matrix_problems(ci: Workflow, selected: dict[str | None, frozenset[str]]) -> list[str]:
    """Where the test matrix's jobs, together, leave a test out on a Python: any test on the supported
    range's ends, any but the mutant searches and the audit controls between them, which run there.
    `selected` gives the tests that each value of `--property-controls` selects, None for a run without it."""
    every = selected[None]
    controls = {test for test in every if CONTROL_FILES.fullmatch(test.partition("::")[0])}
    pythons: list[str] = ci["jobs"]["tests"]["strategy"]["matrix"]["python"]
    ends = {min(pythons, key=version), max(pythons, key=version)}
    run: dict[str, set[str]] = {python: set() for python in pythons}
    for job_id in ("tests", "controls"):
        job = ci["jobs"][job_id]
        for python in job["strategy"]["matrix"]["python"]:
            run.setdefault(python, set()).update(selected[property_controls(job)])

    def by_file(tests: Set[str]) -> str:
        files = Counter(test.partition("::")[0] for test in tests)
        return ", ".join(f"{count} of {file}" for file, count in sorted(files.items()))

    problems: list[str] = []
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
    ],
)
def test_the_matrix_check_can_fail(
    fault: Callable[[Workflow, dict[str | None, frozenset[str]]], None], problem: str
) -> None:
    ci, selected = copy.deepcopy(workflow("ci.yml")), dict(SELECTED)
    fault(ci, selected)
    found = matrix_problems(ci, selected)
    assert any(problem in line for line in found), found
