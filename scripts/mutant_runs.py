# SPDX-License-Identifier: Apache-2.0
"""A mutant table's request, each mutant's run, and the table, for `.github/workflows/mutants.yml`.

A reviewer commits hand mutants as patches, `mutants/<name>.patch`, on a branch and dispatches the workflow on
it with a pytest selection. Each mutant runs in a job of its own, its patch applied to a clean checkout of the
dispatched commit, beside one job of the commit as it is (the baseline), and a last job writes one table of
what became of each. Standard library only, so that it runs on the runner's Python before anything is
installed, and self-contained: a mutant's job runs this file from a copy outside the checkout, made before the
patch is applied, so that nothing a patch writes reaches the code that records its verdict.

- `request` checks the dispatch's inputs, read from the environment, and every patch they name, and writes
  them, checked, as the step's outputs, the matrix of jobs among them: the baseline (`""`) and each mutant.
  A patch is a file committed in `mutants/`, never text from the dispatch form, and is refused
  (`patch_problems`) unless git reads it as a text patch in its own format that changes files in place, adds
  or deletes them, each by a plain path inside the checkout, none under `.github/` or `mutants/`, none the
  runner itself and none of the files that decide what is installed and what pytest selects
  (`REFUSED_FILES`).
- `run DIRECTORY` runs one job, the mutant `MUTANT` (`""` for the baseline): it checks the patch again,
  applies it (`git apply`), checks that the code imports (`imports`, in the project's environment), collects
  the selection, runs it until the first failure, and writes the facts it found to `DIRECTORY/record.json`.
- `imports [PATH ...]` compiles each Python file of the paths given, imports every module of the package,
  and prints what fails; `run` calls it with the paths the patch touches.
- `table DIRECTORY OUTPUT` reads every record under `DIRECTORY`, writes the table to the step summary and to
  `OUTPUT` (`table.md`, `table.json`), and exits 1 unless the baseline passed and every mutant was killed,
  each with one record, the mutants' jobs all succeeded and the run is on its first attempt (`ATTEMPT`).

A record holds facts, never a verdict: whether the patch applied, the code imported and the selection was
collected, pytest's exit status and the tests that failed. `verdict` alone turns them into one, the job's
and the table's alike, and a mutant whose patch does not apply or whose code does not import or collect is
broken whatever else its record holds, so that the table cannot report it killed.
"""

import argparse
import html
import importlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple, cast
from xml.etree import ElementTree

# Where the patches are, as `<name>.patch`, and the names a mutant may have: a word of letters, digits, `_`
# and `-`, so that a name is a path of one part and an artifact's name as it stands.
MUTANTS_DIRECTORY = "mutants"
PATCH_SUFFIX = ".patch"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
# A matrix holds at most 256 jobs: the mutants and the baseline.
MAX_MUTANTS = 200
MAX_PATCH_BYTES = 1 << 20
# The repository's Hypothesis profiles and the Pythons CI tests, as `scripts/repeat_runs.py` lists them;
# tests/unit/test_ci_workflows.py holds these, and the workflow's choices, to both.
PROFILES = ("dev", "ci", "deep")
PYTHONS = ("3.11", "3.12", "3.13", "3.14", "3.15")
MAX_SEED = 999_999_999
MAX_NODES = 20
# The extra pytest arguments a request may give, each at most once, as `scripts/repeat_runs.py` takes them.
OPTIONS = {"--shard": re.compile(r"[a-z0-9_]+"), "--property-controls": re.compile(r"[a-z]+")}
NODE_PATH = re.compile(r"tests(?:/[A-Za-z0-9_.-]+)*/?")
PRINTABLE = re.compile(r"[\x20-\x7e]+")
WHOLE_NUMBER = re.compile(r"0|[1-9][0-9]*")

# What a patch may touch: plain relative paths, by parts of letters, digits, `_`, `.` and `-`, so that a path
# git prints needs no quoting and cannot start at the root; never a part `.` or `..`, nor `.git`, and never
# through a symbolic link out of the checkout. A path under one of `REFUSED_DIRECTORIES`, or one of
# `REFUSED_FILES`, is refused, ignoring case: the workflows, the patches, this runner, and the files that
# decide what `uv` installs and what pytest selects, which a mutant of the code under test never changes.
PLAIN_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
RUNNER = "scripts/mutant_runs.py"
REFUSED_DIRECTORIES = (".github", MUTANTS_DIRECTORY)
REFUSED_FILES = (RUNNER, "pyproject.toml", "uv.lock")
# The file modes a patch may give: a plain file, executable or not; never a symbolic link or a submodule.
MODES = ("100644", "100755")
# Every character a text patch may hold but those below space other than tab and line feed, and DEL.
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
BINARY_LINE = re.compile(r"GIT binary patch$|Binary files .* differ$")
# The lines of `git apply --summary`: a file created or deleted, a mode changed, a file rewritten, renamed
# or copied.
CREATED_OR_DELETED = re.compile(r" (?:create|delete) mode ([0-7]{6}) .+")
MODE_CHANGE = re.compile(r" mode change ([0-7]{6}) => ([0-7]{6}) .+")
REWRITE = re.compile(r" rewrite .+ \(\d+%\)")
RENAME_OR_COPY = re.compile(r" (?:rename|copy) .+")
# The package whose every module must import, under the checkout.
PACKAGE = ("src", "materica")

KILLED, SURVIVED, BROKEN, UNDECIDED = "killed", "survived", "broken", "undecided"
# pytest's exit status for a run whose tests all passed; those of a run in which a test failed, 1, or 2 where
# `-x` stopped it there, which pytest-xdist does by interrupting the run (checked 2026-10-18 with the locked
# pytest-xdist: a failure under `-n 2 -x` exits 2, without xdist 1); and `timeout`'s once it has interrupted
# pytest at the job's limit.
PASSED_STATUS, INTERRUPTED_STATUS = 0, 124
STOPPED_AT_A_FAILURE = (1, 2)
MAX_MESSAGE = 500
RECORD = "record.json"
REPORT = "report.xml"
# The facts a record holds, and the types each may take.
RECORD_FIELDS: dict[str, tuple[type, ...]] = {
    "mutant": (str,),
    "refused": (list,),
    "applied": (bool, type(None)),
    "imports": (bool, type(None)),
    "collected": (bool, type(None)),
    "tests": (int, type(None)),
    "status": (int, type(None)),
    "failures": (list,),
    "message": (str,),
}


class Request(NamedTuple):
    mutants: tuple[str, ...]
    selection: tuple[str, ...]
    profile: str
    python: str
    seed: int
    extra: tuple[str, ...]


class RequestError(Exception):
    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


def whole_number(name: str, text: str, low: int, high: int, problems: list[str]) -> int:
    """`text` as a whole number from `low` to `high`, in ASCII digits without a sign or a leading zero;
    otherwise a problem, and `low`."""
    if not WHOLE_NUMBER.fullmatch(text):
        problems.append(f"{name} {text!r} is not a whole number in plain digits")
        return low
    value = int(text)
    if not low <= value <= high:
        problems.append(f"{name} {value} is not from {low} to {high}")
        return low
    return value


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def first_lines(text: str, count: int = 3) -> str:
    return " | ".join(line.strip() for line in text.strip().splitlines()[:count])[:MAX_MESSAGE]


def last_lines(text: str, count: int = 5) -> str:
    return " | ".join(line.strip() for line in text.strip().splitlines()[-count:])[-MAX_MESSAGE:]


def patch_path(name: str) -> str:
    return f"{MUTANTS_DIRECTORY}/{name}{PATCH_SUFFIX}"


def path_problems(root: Path, path: str) -> list[str]:
    """Why a patch may not touch `path`, if it may not."""
    parts = path.split("/")
    folded = [part.casefold() for part in parts]
    if not PLAIN_PATH.fullmatch(path) or any(part in {".", ".."} for part in parts):
        return [f"{path!r} is not a plain path inside the checkout"]
    if ".git" in folded:
        return [f"{path} is inside .git"]
    if folded[0] in {directory.casefold() for directory in REFUSED_DIRECTORIES}:
        return [f"{path} is under {parts[0]}/, which a patch may not touch"]
    if path.casefold() in {file.casefold() for file in REFUSED_FILES}:
        return [
            f"{path} is the runner or decides the environment or the selection, which a patch may not touch"
        ]
    if not (root / path).resolve().is_relative_to(root.resolve()):
        return [f"{path} leads out of the checkout through a symbolic link"]
    return []


def numstat_paths(text: str) -> tuple[list[str], bool]:
    """The paths `git apply --numstat -z` lists, and whether it lists a binary file (`-` for its counts). A
    rename, which `git diff` would give as an empty path then its two paths, gives both."""
    fields = text.split("\0")
    paths: list[str] = []
    binary = False
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        added, _, rest = entry.partition("\t")
        deleted, _, path = rest.partition("\t")
        binary = binary or added == "-" or deleted == "-"
        if path:
            paths.append(path)
        else:
            paths += [found for found in fields[index : index + 2] if found]
            index += 2
    return paths, binary


def patch_problems(root: Path, name: str) -> tuple[list[str], list[str]]:
    """Why the checkout at `root` may not run the mutant `name`, if it may not, and the paths its patch
    touches. The patch must be `mutants/<name>.patch`, a regular file committed at HEAD, at most
    `MAX_PATCH_BYTES` of UTF-8 text with no control character but tab and line feed; git must read it as a
    patch in its own format (`diff --git`, one for each file it lists), with no binary data, no rename or
    copy, and only the `MODES`; and each path it touches must pass `path_problems`. Whether it applies is not
    checked here: a patch that does not apply changes nothing, and its job records it broken."""
    if not NAME.fullmatch(name):
        return [
            f"the mutant {name!r} is not named by 1 to 64 letters, digits, `_` and `-`, a letter or a digit "
            "first"
        ], []
    relative = patch_path(name)
    listed = git(root, "ls-tree", "-z", "HEAD", "--", relative)
    entries = [entry for entry in listed.stdout.split("\0") if entry]
    path = root / relative
    if (
        listed.returncode != 0
        or len(entries) != 1
        or not entries[0].startswith(tuple(f"{mode} blob " for mode in MODES))
        or path.is_symlink()
        or not path.is_file()
    ):
        return [f"{relative} is not a regular file committed at the dispatched commit"], []
    data = path.read_bytes()
    if len(data) > MAX_PATCH_BYTES:
        return [f"{relative} holds {len(data)} bytes, more than {MAX_PATCH_BYTES}"], []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{relative} is not UTF-8 text"], []
    if CONTROL.search(text):
        return [f"{relative} holds a control character other than tab and line feed"], []
    problems: list[str] = []
    if any(BINARY_LINE.match(line) for line in text.split("\n")):
        problems.append(f"{relative} is a binary patch")
    numstat = git(root, "apply", "--numstat", "-z", relative)
    if numstat.returncode != 0:
        return [*problems, f"git cannot read {relative} as a patch: {first_lines(numstat.stderr)}"], []
    paths, binary = numstat_paths(numstat.stdout)
    if binary and not problems:
        problems.append(f"{relative} is a binary patch")
    headers = sum(line.startswith("diff --git ") for line in text.split("\n"))
    if headers != len(paths):
        problems.append(
            f"{relative} lists {len(paths)} files and {headers} `diff --git` headers: each file of a patch "
            "must be in git's own format"
        )
    summary = git(root, "apply", "--summary", relative)
    for line in summary.stdout.splitlines():
        modes = CREATED_OR_DELETED.fullmatch(line) or MODE_CHANGE.fullmatch(line)
        if modes:
            problems += [
                f"{relative} gives the mode {mode}, not a plain file's"
                for mode in modes.groups()
                if mode not in MODES
            ]
        elif RENAME_OR_COPY.fullmatch(line):
            problems.append(f"{relative} renames or copies a file: {line.strip()}")
        elif not REWRITE.fullmatch(line):
            problems.append(f"{relative} has a summary line git's format does not give: {line.strip()!r}")
    if summary.returncode != 0:
        problems.append(f"git cannot summarise {relative}: {first_lines(summary.stderr)}")
    for touched in paths:
        problems += [f"{relative} touches {problem}" for problem in path_problems(root, touched)]
    return problems, paths


def committed_patches(root: Path) -> list[str]:
    """The name of each patch committed directly in `mutants/`, in order."""
    listed = git(root, "ls-tree", "-z", "--name-only", "HEAD", f"{MUTANTS_DIRECTORY}/")
    return sorted(
        path.removeprefix(f"{MUTANTS_DIRECTORY}/").removesuffix(PATCH_SUFFIX)
        for path in listed.stdout.split("\0")
        if path.endswith(PATCH_SUFFIX)
    )


def node_problems(node: str, root: Path) -> list[str]:
    """Why pytest may not be given `node`, if it may not: it must be `tests` or a path under it that exists,
    by plain parts, with any part after `::` in printable ASCII but a space (`scripts/repeat_runs.py`)."""
    path, separator, rest = node.partition("::")
    if not NODE_PATH.fullmatch(path) or any(part in {".", ".."} for part in path.split("/")):
        return [f"the selection's path {path!r} is not `tests` or a path under it, by plain parts"]
    if separator and not rest:
        return [f"the selection's node {node!r} names nothing after `::`"]
    tests = (root / "tests").resolve()
    found = (root / path).resolve()
    if not found.exists() or not found.is_relative_to(tests):
        return [f"the selection's path {path!r} is no file or directory under tests/"]
    return []


def extra_arguments(text: str, problems: list[str]) -> tuple[str, ...]:
    """The extra arguments, each as `--option=value`: an option of `OPTIONS` at most once, its value given
    after `=` or as the next word."""
    words = [word for word in text.split(" ") if word]
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


def checked_request(
    environment: Mapping[str, str], root: Path, draw: Callable[[int], int] = secrets.randbelow
) -> Request:
    """The request the environment gives, and every patch it names, checked against the checkout at `root`.
    No mutant named runs every patch committed in `mutants/`; no seed given runs one drawn by `draw`."""
    problems: list[str] = []
    texts = {name: environment.get(name, "") for name in ("MUTANTS", "SELECTION", "SEED", "EXTRA")}
    for name, text in texts.items():
        if text and not PRINTABLE.fullmatch(text):
            problems.append(f"{name} {text!r} holds a character other than printable ASCII")
            texts[name] = ""
    mutants = [word for word in texts["MUTANTS"].split(" ") if word] or committed_patches(root)
    if not mutants:
        problems.append(f"no mutant is named, and no patch is committed in {MUTANTS_DIRECTORY}/")
    if len(mutants) > MAX_MUTANTS:
        problems.append(f"{len(mutants)} mutants, more than {MAX_MUTANTS}")
    problems += [
        f"the mutant {name} is named twice" for name in sorted({m for m in mutants if mutants.count(m) > 1})
    ]
    for name in dict.fromkeys(mutants):
        problems += patch_problems(root, name)[0]
    selection = [word for word in texts["SELECTION"].split(" ") if word]
    if not selection:
        problems.append("the selection is empty: give `tests` for the whole suite")
    if len(selection) > MAX_NODES:
        problems.append(f"the selection names {len(selection)} paths or nodes, more than {MAX_NODES}")
    for node in selection:
        problems += node_problems(node, root)
    profile = environment.get("PROFILE", "")
    if profile not in PROFILES:
        problems.append(f"the profile {profile!r} is not one of {', '.join(PROFILES)}")
    python = environment.get("PYTHON_VERSION", "")
    if python not in PYTHONS:
        problems.append(f"the Python {python!r} is not one of {', '.join(PYTHONS)}")
    if texts["SEED"]:
        seed = whole_number("the seed", texts["SEED"], 0, MAX_SEED, problems)
    else:
        seed = draw(MAX_SEED + 1)
    extra = extra_arguments(texts["EXTRA"], problems)
    if problems:
        raise RequestError(problems)
    return Request(tuple(mutants), tuple(selection), profile, python, seed, extra)


def outputs(request: Request) -> dict[str, str]:
    return {
        "mutants": " ".join(request.mutants),
        "matrix": json.dumps(["", *request.mutants]),
        "selection": " ".join(request.selection),
        "profile": request.profile,
        "python": request.python,
        "seed": str(request.seed),
        "extra": " ".join(request.extra),
    }


def node_id(case: ElementTree.Element) -> str:
    """A test case's pytest node id, from its file (`junit_family = "xunit1"`), any classes, and its name."""
    file = case.get("file", "")
    module = file.removesuffix(".py").replace("/", ".")
    classname = case.get("classname", "")
    classes = classname.removeprefix(module + ".").split(".") if classname.startswith(module + ".") else []
    return "::".join([file or classname, *classes, case.get("name", "")])


def reported_failures(report: Path) -> list[dict[str, str]]:
    """Each test the JUnit report says failed or erred, in the order pytest reported it (with pytest-xdist,
    the order the tests ended in), with the first line of its message; none for a report missing or
    unreadable."""
    try:
        cases = list(ElementTree.parse(report).getroot().iter("testcase"))
    except (OSError, ElementTree.ParseError):
        return []
    failures: list[dict[str, str]] = []
    for case in cases:
        if not any(case.get(attribute) for attribute in ("name", "classname", "file")):
            continue
        for found in case:
            if found.tag in {"failure", "error"}:
                failure = {"test": node_id(case), "message": first_lines(found.get("message", ""), 1)}
                if failure not in failures:
                    failures.append(failure)
    return failures


def verdict(record: Mapping[str, Any]) -> tuple[str, str]:
    """The outcome a record shows, and why: broken where the patch did not apply or the code did not import
    or collect, whatever else the record holds; otherwise survived where pytest passed and named no failure,
    killed where it failed and named the test that failed first; undecided for anything else (a refusal, a
    stage not reached, a run interrupted at the job's limit, or a status and failures that disagree)."""
    message = str(record.get("message", ""))
    if record.get("refused"):
        return UNDECIDED, "the patch was refused: " + "; ".join(map(str, record["refused"]))
    for stage, why in (
        ("applied", "the patch does not apply"),
        ("imports", "the code does not import"),
        ("collected", "pytest cannot collect the selection"),
    ):
        if record.get(stage) is False:
            return BROKEN, f"{why}: {message}"
    if not all(record.get(stage) is True for stage in ("applied", "imports", "collected")):
        return UNDECIDED, f"the job stopped before it ran the selection: {message}"
    status = record.get("status")
    failures: list[Any] = list(record.get("failures") or [])
    if status == PASSED_STATUS and not failures:
        return SURVIVED, f"{record.get('tests')} tests passed"
    if status in STOPPED_AT_A_FAILURE and failures and is_failure(failures[0]):
        return KILLED, str(cast(dict[str, str], failures[0])["test"])
    if status == INTERRUPTED_STATUS:
        return UNDECIDED, "the run was interrupted at the job's time limit"
    return UNDECIDED, f"pytest exited {status} and named {len(failures)} failed tests"


class Stage(NamedTuple):
    passed: bool | None
    message: str
    printed: str


def staged(command: Sequence[str], root: Path, seconds: float, head: bool = False) -> Stage:
    """`command` run in `root` for at most `seconds`: whether it exited 0, None where time ran out first; the
    tail of what it printed where it did not pass, or its head with `head`, and all it printed to its standard
    output."""
    if seconds <= 0:
        return Stage(None, "the job's time ran out before it", "")
    try:
        ran = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Stage(None, f"`{' '.join(command[:4])}` ran out of the job's time", "")
    passed = ran.returncode == 0
    printed = ran.stdout + ran.stderr
    return Stage(passed, "" if passed else (first_lines if head else last_lines)(printed), ran.stdout)


def run_mutant(
    environment: Mapping[str, str],
    root: Path,
    records: Path,
    script: Path,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """The record of the mutant `MUTANT` (`""` for the baseline), run in the checkout at `root` until three
    minutes before the job's timeout (`JOB_MINUTES`), counted from now: its patch checked and applied, the
    code imported (`script`'s `imports`, in the project's environment), the selection collected, and then run
    under `timeout --foreground --signal=INT`, as CI's jobs run pytest, stopping at the first failure. Each
    stage runs only where the one before it passed."""
    problems: list[str] = []
    minutes = whole_number("the job's minutes", environment.get("JOB_MINUTES", ""), 4, 360, problems)
    seed = whole_number("the seed", environment.get("SEED", ""), 0, MAX_SEED, problems)
    deadline = clock() + (minutes - 3) * 60
    mutant = environment.get("MUTANT", "")
    selection = [word for word in environment.get("SELECTION", "").split(" ") if word]
    extra = [word for word in environment.get("EXTRA", "").split(" ") if word]
    if not selection:
        problems.append("the selection is empty")
    record: dict[str, Any] = {
        "mutant": mutant,
        "refused": problems,
        "applied": None,
        "imports": None,
        "collected": None,
        "tests": None,
        "status": None,
        "failures": [],
        "message": "",
    }
    touched: list[str] = []
    if mutant and not problems:
        refused, touched = patch_problems(root, mutant)
        problems += refused
    if problems:
        return record
    if mutant:
        relative = patch_path(mutant)
        applied = git(root, "apply", "--whitespace=nowarn", relative)
        record["applied"] = applied.returncode == 0
        if applied.returncode != 0:
            record["message"] = first_lines(applied.stderr)
            return record
    else:
        record["applied"] = True
    python_files = [path for path in touched if path.endswith(".py")]
    # The import check prints the files that do not compile first; pytest prints its errors before a summary.
    check = ["uv", "run", "python", str(script), "imports", *python_files]
    imports = staged(check, root, deadline - clock(), head=True)
    record["imports"], record["message"] = imports.passed, imports.message
    if imports.passed is not True:
        return record
    collect = ["uv", "run", "pytest", "--collect-only", "-q", *selection, *extra]
    collected = staged(collect, root, deadline - clock())
    record["collected"], record["message"] = collected.passed, collected.message
    if collected.passed is not True:
        return record
    record["tests"] = sum("::" in line for line in collected.printed.splitlines())
    left = int(deadline - clock())
    if left <= 0:
        record["message"] = "the job's time ran out before the run"
        return record
    report = records / REPORT
    command = [
        *("uv", "run", "timeout", "--foreground", "--signal=INT", f"{left}s"),
        *("pytest", "-n", "auto", "--dist", "worksteal", "-x", *selection, *extra),
        *(f"--hypothesis-seed={seed}", f"--junitxml={report}"),
    ]
    record["status"] = subprocess.run(command, cwd=root, check=False).returncode
    record["failures"] = reported_failures(report)
    return record


def import_problems(root: Path, paths: Sequence[str]) -> list[str]:
    """Each Python file of `paths` under `root` that does not compile, and each module of the package that
    does not import, or the package imported from elsewhere than `root`."""
    problems: list[str] = []
    for path in paths:
        source = root / path
        if path.endswith(".py") and source.is_file():
            try:
                compile(source.read_bytes(), path, "exec")
            except (SyntaxError, ValueError) as error:
                problems.append(f"{path} does not compile: {error}")
    package = root.joinpath(*PACKAGE)
    modules = sorted(
        ".".join(module.relative_to(package.parent).with_suffix("").parts).removesuffix(".__init__")
        for module in package.rglob("*.py")
        if module.stem != "__main__"
    )
    for name in modules:
        try:
            loaded = importlib.import_module(name)
        except (Exception, SystemExit) as error:
            problems.append(f"{name} does not import: {type(error).__name__}: {first_lines(str(error), 1)}")
            continue
        where = Path(str(getattr(loaded, "__file__", ""))).resolve()
        if not where.is_relative_to(package.resolve()):
            problems.append(f"{name} is imported from {where}, not from the checkout")
    return problems


def read_records(directory: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Every record under `directory`, by mutant, and the files that are not records."""
    found: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    for path in sorted(directory.rglob(RECORD)):
        where = path.relative_to(directory).as_posix()
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            problems.append(f"{where} is not JSON")
            continue
        if not isinstance(record, dict) or set(cast(dict[str, Any], record)) != set(RECORD_FIELDS):
            problems.append(f"{where} does not hold a record's fields")
            continue
        fields = cast(dict[str, Any], record)
        wrong = [
            name
            for name, types in RECORD_FIELDS.items()
            if not isinstance(fields[name], types) or (bool not in types and isinstance(fields[name], bool))
        ]
        if not all(isinstance(problem, str) for problem in fields["refused"]):
            wrong.append("refused")
        if not all(is_failure(failure) for failure in fields["failures"]):
            wrong.append("failures")
        if wrong:
            problems.append(f"{where} holds {', '.join(wrong)} of another type")
            continue
        found.setdefault(fields["mutant"], []).append(fields)
    return found, problems


def is_failure(value: object) -> bool:
    """Whether `value` is a failure as a record holds it: a test and a message, each a string."""
    if not isinstance(value, dict):
        return False
    failure = cast(dict[object, object], value)
    return set(failure) == {"test", "message"} and all(isinstance(each, str) for each in failure.values())


def code(text: str) -> str:
    return f"<code>{html.escape(text).replace('|', '&#124;')}</code>"


def cell(text: str) -> str:
    return html.escape(text).replace("|", "&#124;")


class Row(NamedTuple):
    mutant: str
    outcome: str
    why: str


def table(
    request: Request,
    directory: Path,
    mutants_result: str,
    attempt: int = 1,
    commit: str = "",
) -> tuple[str, list[Row], str, bool]:
    """The table's Markdown, its rows, its one-line verdict, and whether it passes: the baseline passed, every
    mutant was killed, each with exactly one record and no record of another, the mutants' jobs all succeeded,
    and the run is on its first attempt. Where the baseline did not pass, no mutant counts as killed."""
    records, problems = read_records(directory)
    for name in sorted(set(records) - {"", *request.mutants}):
        problems.append(f"a record of {name!r}, which the request does not name")

    def row(name: str) -> Row:
        found = records.get(name, [])
        if len(found) != 1:
            return Row(name, UNDECIDED, "no record" if not found else f"{len(found)} records")
        return Row(name, *verdict(found[0]))

    baseline = row("")
    rows = [baseline]
    for name in request.mutants:
        each = row(name)
        if baseline.outcome != SURVIVED and each.outcome == KILLED:
            each = Row(name, UNDECIDED, f"the baseline did not pass; killed by {each.why}")
        rows.append(each)
    counts = {
        outcome: sum(each.outcome == outcome for each in rows[1:])
        for outcome in (KILLED, SURVIVED, BROKEN, UNDECIDED)
    }
    verdict_text = (
        f"{counts[KILLED]} of {len(request.mutants)} mutants killed, {counts[SURVIVED]} survived, "
        f"{counts[BROKEN]} broken, {counts[UNDECIDED]} undecided"
    )
    if baseline.outcome != SURVIVED:
        verdict_text += f"; the baseline did not pass ({baseline.outcome}: {baseline.why})"
    if problems:
        verdict_text += f"; problems with the records: {len(problems)} (below)"
    if mutants_result != "success":
        verdict_text += f"; the mutants' jobs ended in {mutants_result!r}"
    if attempt != 1:
        verdict_text += f"; this is attempt {attempt} of the run, which counts only a first: dispatch it anew"
    ok = (
        baseline.outcome == SURVIVED
        and counts[KILLED] == len(request.mutants)
        and not problems
        and mutants_result == "success"
        and attempt == 1
    )
    extra = ", ".join(code(argument) for argument in request.extra) or "none"
    at = f", at {code(commit[:12])}" if commit else ""
    shown = {SURVIVED: "passed", KILLED: "failed"}
    lines = [
        f"## Mutants against {code(' '.join(request.selection))}",
        "",
        f"Profile {code(request.profile)}, Python {request.python}, seed {request.seed}, extra arguments: "
        f"{extra}{at}. {len(request.mutants)} mutants, each the patch {code(patch_path('<name>'))}.",
        "",
        "| Mutants | Killed | Survived | Broken | Undecided |",
        "|---:|---:|---:|---:|---:|",
        "| " + " | ".join(str(count) for count in (len(request.mutants), *counts.values())) + " |",
        "",
        f"**{verdict_text[0].upper()}{verdict_text[1:]}.**",
        "",
        "| Mutant | Outcome | The test that failed first, or why |",
        "|---|---|---|",
        f"| the baseline, no patch | {shown.get(baseline.outcome, baseline.outcome)} | "
        f"{cell(baseline.why)} |",
    ]
    for each in rows[1:]:
        why = code(each.why) if each.outcome == KILLED else cell(each.why)
        lines.append(f"| {code(each.mutant)} | {each.outcome} | {why} |")
    lines += [
        "",
        "A mutant's run replays with its patch applied and the same seed: "
        + code(
            f"git apply {patch_path('<name>')} && MATERICA_HYPOTHESIS_PROFILE={request.profile} "
            f"uv run pytest <test> --hypothesis-seed={request.seed}"
        )
        + ".",
        "",
    ]
    if problems:
        lines += ["### Records that cannot be read", "", *[f"- {cell(problem)}" for problem in problems], ""]
    return "\n".join(lines), rows, verdict_text, ok


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


def tabled_request(environment: Mapping[str, str]) -> Request:
    """The request as the request job wrote it: its seed read again, its text as given."""
    problems: list[str] = []
    seed = whole_number("the seed", environment.get("SEED", ""), 0, MAX_SEED, problems)
    if problems:
        raise RequestError(problems)

    def words(name: str) -> tuple[str, ...]:
        return tuple(word for word in environment.get(name, "").split(" ") if word)

    return Request(
        words("MUTANTS"),
        words("SELECTION"),
        environment.get("PROFILE", ""),
        environment.get("PYTHON_VERSION", ""),
        seed,
        words("EXTRA"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("request", help="check the request and its patches, and write them as outputs")
    running = commands.add_parser("run", help="run the mutant MUTANT and write its record into DIRECTORY")
    running.add_argument("directory", type=Path)
    importing = commands.add_parser("imports", help="compile the files given and import the package")
    importing.add_argument("paths", nargs="*")
    tabling = commands.add_parser("table", help="write the table of the records under DIRECTORY")
    tabling.add_argument("directory", type=Path)
    tabling.add_argument("output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "request":
            request = checked_request(os.environ, Path.cwd())
            write_outputs(outputs(request))
            print(f"The request, checked: {request}")
        elif arguments.command == "run":
            record = run_mutant(os.environ, Path.cwd(), arguments.directory, Path(__file__).resolve())
            arguments.directory.mkdir(parents=True, exist_ok=True)
            (arguments.directory / RECORD).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
            outcome, why = verdict(record)
            name = record["mutant"] or "the baseline"
            decided = outcome == SURVIVED if not record["mutant"] else outcome in {KILLED, SURVIVED, BROKEN}
            print(
                f"::{'notice' if decided else 'error'} title=Mutant {name}::{annotation(f'{outcome}: {why}')}"
            )
            return 0 if decided else 1
        elif arguments.command == "imports":
            problems = import_problems(Path.cwd(), arguments.paths)
            print("\n".join(problems) or "every module imports")
            return 1 if problems else 0
        else:
            request = tabled_request(os.environ)
            refused: list[str] = []
            attempt = whole_number(
                "the run's attempt", os.environ.get("ATTEMPT", ""), 1, sys.maxsize, refused
            )
            if refused:
                raise RequestError(refused)
            text, rows, verdict_text, ok = table(
                request,
                arguments.directory,
                os.environ.get("MUTANTS_RESULT", ""),
                attempt,
                os.environ.get("GITHUB_SHA", ""),
            )
            print(text)
            arguments.output.mkdir(parents=True, exist_ok=True)
            (arguments.output / "table.md").write_text(text + "\n", encoding="utf-8")
            (arguments.output / "table.json").write_text(
                json.dumps(
                    {
                        "request": request._asdict(),
                        "verdict": verdict_text,
                        "passed": ok,
                        "rows": [each._asdict() for each in rows],
                    },
                    indent=1,
                )
                + "\n",
                encoding="utf-8",
            )
            if target := os.environ.get("GITHUB_STEP_SUMMARY"):
                with Path(target).open("a", encoding="utf-8") as markdown:
                    markdown.write(text + "\n")
            print(f"::{'notice' if ok else 'error'} title=Mutant table::{annotation(verdict_text)}")
            return 0 if ok else 1
    except RequestError as error:
        for problem in error.problems:
            print(f"::error title=Mutant request::{annotation(problem)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
