# SPDX-License-Identifier: Apache-2.0
"""Run the mechanical checks that apply to what a branch changed, before asking for review (CONTRIBUTING,
"Before asking for review").

    python scripts/pre_review.py [BASE] [--list] [--stage fast|tests|properties] [--workers N] [--keep-going]

`BASE` is a ref, `origin/main` where none is given. The changed files are those from the merge base of `BASE`
and `HEAD` to the working tree, committed or not, with the files git does not track yet. From them it plans
the checks, prints each with the paths that selected it, and runs them in three stages: the fast checks
(sign-offs, confidential names, every generator's `--check`, and for a change to code the linters and type
checkers), the tests of what changed and of what imports it, and the property shards at the `ci` profile that
hold a changed or affected property module. A stage that fails stops the run before the next, unless
`--keep-going` is given: what the fast checks find is fixed before any test runs. After the plan it prints
reminders for what no test can check: a figure stated in a CHANGELOG line or a commit message to recount, a
mutant table changed beside a README that was not.

It adds to CI's checks and replaces none. It runs the checks that apply to the change, not every check; CI
runs them all, on every Python, and its result is the one that counts. A change it selects no check for is
printed as such: that is a gap in this script, or a change only an independent eye can judge.

What imports what is read from the import statements of the Python files, `from a import b` counting for
`a` and for `a.b`; a package is not taken to import its parents, and a data file is followed to the modules
that read it by the declared table `DATA_READERS`.
"""

import argparse
import ast
import os
import re
import subprocess
import sys
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "origin/main"
STAGES = ("fast", "tests", "properties")

# CI's own lists of the paths that are not code (`.github/workflows/ci.yml`, step "Changed paths"):
# `tests/unit/test_pre_review.py` holds these to the workflow's text.
DOCUMENTATION_PATHS = (
    r"CHANGELOG\.md|CLAUDE\.md|CONTRIBUTING\.md|SECURITY\.md|docs/regulatory/.+|docs/validation/.+"
    r"|\.github/ISSUE_TEMPLATE/.+|\.github/pull_request_template\.md"
)
SITE_PATHS = r"site/.+|assets/.+"
PYTHON_PATHS = r".*\.pyi?"

# The generators CI runs with `--check` in its generated-files job, in its own environment on Python 3.11,
# since the generator of the typed shapes does not run on 3.15.
GENERATORS = ("gen_vocabulary", "gen_reader_schema", "gen_shapes")
GENERATOR_PYTHON = "3.11"

PROFILE_VARIABLE = "MATERICA_HYPOTHESIS_PROFILE"
SPECIFICATION = r"docs/specification/.+|design/ARCHITECTURE_DRAFT\.md|DOCUMENTATION_ARCHITECTURE\.md"

# The citation test of the read model, when the model is in the tree: a reference with no quote, a drifted
# line and a quote cut short are what it catches. Absent, the rule selects nothing for it.
CITATION_TEST = "tests/reference/test_citations.py"


@dataclass(frozen=True)
class DataRule:
    """A kind of file that is no Python and what reads it: the tests that run on it alone, the paths whose
    tests run whole, and the Python modules that load it, whose importers' tests run too."""

    name: str
    pattern: str
    why: str
    tests: tuple[str, ...] = ()
    readers: tuple[str, ...] = ()


# Declared, not derived: which Python reads which data. `test_pre_review.py` holds every path named here to
# exist, and every module that locates data by `resources.files` or `__file__` to be named in `readers` or to
# be listed there as reading none.
DATA_RULES = (
    DataRule(
        "the specification",
        SPECIFICATION,
        "its tables generate the vocabulary; its references, quotes and member tables are held to the code",
        tests=("tests/spec_sync", "tests/unit/test_generators.py", CITATION_TEST),
    ),
    DataRule(
        "a schema",
        r"src/materica/schema/.+",
        "the schemas and the vocabulary are read by the reader and held to the specification",
        tests=("tests/spec_sync", "tests/unit/test_shapes.py", "tests/unit/test_vocabulary.py"),
        readers=(
            "src/materica/core/vocabulary.py",
            "tests/spec_sync/schemas.py",
            "tests/property/condition_oracle.py",
            "tests/verdicts.py",
        ),
    ),
    DataRule(
        "a conformance case",
        r"src/materica/data/conformance/.+",
        "the cases are run by the conformance runner and held to CASES.md and the step map",
        tests=("tests/conformance", "tests/spec_sync"),
        readers=("tests/conformance/runner.py",),
    ),
    DataRule(
        "a spec-sync table",
        r"tests/spec_sync/.+\.json",
        "the tables are checked against the text and the schemas",
        tests=("tests/spec_sync",),
    ),
    DataRule(
        "a workflow",
        r"\.github/workflows/.+",
        "the workflows' jobs, guards and caps are held by tests",
        tests=("tests/unit/test_ci_workflows.py", "tests/unit/test_repeat_runs.py"),
    ),
    DataRule(
        "the project's build",
        r"pyproject\.toml|uv\.lock",
        "the supported Pythons, the profiles and the lock file are held by tests",
        tests=(
            "tests/unit/test_python_versions.py",
            "tests/unit/test_hypothesis_profiles.py",
            "tests/unit/test_source_files.py",
            "tests/unit/test_ci_workflows.py",
        ),
    ),
    DataRule(
        "the confidential digests",
        r"scripts/confidential_digests\.txt",
        "the digests are read by the scan, whose tests run it on them",
        tests=("tests/unit/test_check_confidential.py",),
    ),
)

# Modules outside `tests/unit` and `tests/spec_sync` (whose files the rules above run, whole or by name) that
# locate files by `resources.files` or `__file__` without being one of `DATA_RULES`' readers, each with the
# reason a change to a data file need not follow it.
LOCATES_NO_RULED_DATA = {
    "tests/conftest.py": "locates the example database; a change to a conftest selects every test",
    "tests/fuzz/jsonio_bytes.py": "an Atheris target: CI's fuzz job runs it, this script cannot",
    "tests/fuzz/read_field_bytes.py": "an Atheris target: CI's fuzz job runs it, this script cannot",
    "tests/property/test_validators_agree.py": "lists the tests' own modules, no data file",
}


@dataclass
class Planned:
    stage: str
    command: tuple[str, ...]
    why: str
    because: list[str] = field(default_factory=list[str])
    env: dict[str, str] = field(default_factory=dict[str, str])
    # The files of the repository the command names: `test_pre_review.py` holds each to exist.
    paths: tuple[str, ...] = ()
    # A path that may be absent: its rule selects it only where it exists.
    optional: bool = False


def git(*arguments: str, root: Path = REPOSITORY, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], capture_output=True, text=True, check=check, cwd=root)


def changed_files(base: str, root: Path = REPOSITORY) -> list[str]:
    """The files changed from the merge base of `base` and HEAD to the working tree, deleted ones included,
    with those not tracked yet, each path once, sorted. A rename counts as the old path gone and the new one
    added."""
    merge_base = git("merge-base", base, "HEAD", root=root).stdout.strip()
    tracked = git("diff", "--no-renames", "--name-only", "-z", merge_base, root=root).stdout
    untracked = git("ls-files", "--others", "--exclude-standard", "-z", root=root).stdout
    return sorted({path for path in (tracked + untracked).split("\0") if path})


def is_code(changed: Sequence[str]) -> bool:
    """CI's rule: a change is code unless it has paths, none a Python file, and each is documentation or the
    site's (the gate's `code`)."""
    if not changed:
        return True
    if any(re.fullmatch(PYTHON_PATHS, path) for path in changed):
        return True
    return any(not re.fullmatch(f"{DOCUMENTATION_PATHS}|{SITE_PATHS}", path) for path in changed)


def module_name(path: str) -> str | None:
    """The dotted name a Python file is imported by, from the repository's root or `src/`."""
    if not re.fullmatch(r".*\.pyi?", path):
        return None
    parts = Path(path).with_suffix("").parts
    if parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def imported_names(path: str, source: str) -> set[str]:
    """Each name the file imports: `import a.b` gives `a.b`, and `from a import b, c` gives `a`, `a.b` and
    `a.c`, so that a name that is a module and one that is not are both met. Relative imports are resolved
    against the file's package."""
    name = module_name(path)
    package = name.split(".") if name else []
    if name and Path(path).stem != "__init__":
        package = package[:-1]
    found: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                origin = ".".join([*base, *([node.module] if node.module else [])])
            else:
                origin = node.module or ""
            if not origin:
                continue
            found.add(origin)
            found.update(f"{origin}.{alias.name}" for alias in node.names if alias.name != "*")
    return found


class Tree:
    """The repository's Python files and what they import, read once."""

    def __init__(self, root: Path = REPOSITORY) -> None:
        self.root = root
        self.files: dict[str, str] = {}
        for top in ("src", "tests", "scripts"):
            for file in sorted((root / top).rglob("*.py")):
                if "__pycache__" not in file.parts:
                    self.files[file.relative_to(root).as_posix()] = file.read_text(encoding="utf-8")
        self.importers: dict[str, set[str]] = defaultdict(set)
        for path, source in self.files.items():
            for name in imported_names(path, source):
                self.importers[name].add(path)
        self._shards: dict[str, tuple[str, ...]] | None = None

    def exists(self, path: str) -> bool:
        return (self.root / path).exists()

    def shards(self) -> dict[str, tuple[str, ...]]:
        """`SHARDS` of `tests/conftest.py`, read without importing it."""
        if self._shards is None:
            tree = ast.parse(self.files["tests/conftest.py"])
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "SHARDS" for target in node.targets
                ):
                    self._shards = {key: tuple(value) for key, value in ast.literal_eval(node.value).items()}
                    break
            else:
                raise ValueError("tests/conftest.py has no SHARDS")
        return self._shards

    def shard_of(self, path: str) -> str | None:
        stem = Path(path).stem
        if Path(path).parent.as_posix() != "tests/property":
            return None
        return next((name for name, modules in self.shards().items() if stem in modules), None)

    def affected(self, paths: Iterable[str]) -> set[str]:
        """The Python files among `paths`, and every file that imports one of them, directly or through
        others. A deleted file is followed by the name it had."""
        reached: set[str] = set()
        queue = deque(path for path in paths if module_name(path))
        while queue:
            path = queue.popleft()
            if path in reached:
                continue
            reached.add(path)
            name = module_name(path)
            if name:
                queue.extend(self.importers.get(name, ()))
        return reached


def is_test_module(path: str) -> bool:
    parts = Path(path).parts
    return (
        parts[0] == "tests"
        and len(parts) > 1
        and parts[1] in {"unit", "spec_sync", "conformance", "property"}
        and Path(path).name.startswith("test_")
        and path.endswith(".py")
    )


def pytest_command(paths: Sequence[str], workers: int, *extra: str) -> tuple[str, ...]:
    return (
        "uv",
        "run",
        "pytest",
        *paths,
        *extra,
        "-n",
        str(workers),
        "--dist",
        "worksteal",
        "-q",
        "--tb=short",
    )


class Plan:
    """The checks selected for a change, each once, with the paths that selected it."""

    def __init__(self) -> None:
        self._planned: dict[tuple[str, tuple[str, ...]], Planned] = {}

    def add(self, planned: Planned, because: str | None = None) -> None:
        key = (planned.stage, planned.command)
        held = self._planned.setdefault(key, planned)
        if because is not None and because not in held.because:
            held.because.append(because)

    def checks(self) -> list[Planned]:
        order = {stage: number for number, stage in enumerate(STAGES)}
        return sorted(self._planned.values(), key=lambda planned: order[planned.stage])


def generator_environment() -> dict[str, str]:
    """The environment of CI's Python 3.11 check of the generators, kept beside the project's own so that
    neither is rebuilt for the other."""
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return {"UV_PROJECT_ENVIRONMENT": str(cache / "openmaterica" / f"python-{GENERATOR_PYTHON}")}


def key_arguments(key_file: str | None, root: Path = REPOSITORY) -> tuple[str, ...]:
    """The scan's `--key-file`: the one given, or the clone's `openmaterica.scanKeyFile` (CONTRIBUTING,
    "Confidentiality"); without either the scan reads `CONFIDENTIAL_SCAN_KEY`, or checks the paths alone."""
    if key_file is None:
        configured = git("config", "--get", "openmaterica.scanKeyFile", root=root, check=False).stdout.strip()
        key_file = os.path.expanduser(configured) if configured else None
    return ("--key-file", key_file) if key_file else ()


def plan_checks(
    changed: Sequence[str],
    tree: Tree,
    base: str = DEFAULT_BASE,
    workers: int = 12,
    key_file: str | None = None,
) -> tuple[list[Planned], list[str]]:
    """The checks that apply to `changed`, and the changed paths no rule selects a check for."""
    plan = Plan()
    covered: set[str] = set()

    # Every change.
    plan.add(
        Planned(
            "fast",
            ("python3", "scripts/check_signoff.py", base, "HEAD"),
            "every commit is signed off by its author (constraint 1); CI's gate runs it",
            paths=("scripts/check_signoff.py",),
        ),
        "every change",
    )
    plan.add(
        Planned(
            "fast",
            (
                "python3",
                "scripts/check_confidential.py",
                "--messages",
                f"{base}..HEAD",
                *key_arguments(key_file, tree.root),
            ),
            "no tracked file or commit message names a private project or path; CI's gate runs it",
            paths=("scripts/check_confidential.py",),
        ),
        "every change",
    )
    environment = generator_environment()
    plan.add(
        Planned(
            "fast",
            ("uv", "sync", "--locked", "--python", GENERATOR_PYTHON),
            f"the environment of the generators' check on Python {GENERATOR_PYTHON}, as CI makes it",
            env=environment,
        ),
        "every change",
    )
    for generator in GENERATORS:
        plan.add(
            Planned(
                "fast",
                (
                    "uv",
                    "run",
                    "--locked",
                    "--python",
                    GENERATOR_PYTHON,
                    "python",
                    f"scripts/{generator}.py",
                    "--check",
                ),
                "a generated file or a specification table that differs from its source fails CI",
                env=environment,
                paths=(f"scripts/{generator}.py",),
            ),
            "every change",
        )
    plan.add(
        Planned(
            "fast",
            ("python3", "scripts/freeze_schema.py", "--check"),
            "a released schema version's file added, removed or changed (the tests job runs the same check)",
            paths=("scripts/freeze_schema.py",),
        ),
        "every change",
    )

    # A change to code.
    if is_code(changed):
        for command in (
            ("uv", "run", "ruff", "check"),
            ("uv", "run", "ruff", "format", "--check"),
            ("uv", "run", "mypy"),
            ("uv", "run", "pyright"),
        ):
            plan.add(
                Planned("fast", command, "CI's static job runs it on every change to code"),
                "a change to code",
            )
    if any(path in {"pyproject.toml", "uv.lock"} for path in changed):
        plan.add(
            Planned(
                "fast",
                ("uv", "lock", "--check"),
                "the lock file is out of date with pyproject.toml; CI installs with `uv sync --locked`",
            ),
            next(path for path in changed if path in {"pyproject.toml", "uv.lock"}),
        )

    # The tests of what changed and of what imports it; a property module is run in its shard, whole.
    file_tests: dict[str, list[str]] = defaultdict(list)
    shard_causes: dict[str, list[str]] = defaultdict(list)

    def route(test: str, cause: str) -> None:
        shard = tree.shard_of(test)
        if shard is None:
            file_tests[test].append(cause)
        else:
            shard_causes[shard].append(cause)

    def route_importers(root: str, cause: str) -> None:
        for affected in sorted(tree.affected([root])):
            if is_test_module(affected) and tree.exists(affected):
                route(affected, cause)

    for path in changed:
        if module_name(path) is not None:
            covered.add(path)
            route_importers(path, path)
        if Path(path).name == "conftest.py":
            # A conftest applies to every test under its directory.
            covered.add(path)
            directory = Path(path).parent.as_posix()
            for shard in tree.shards():
                shard_causes[shard].append(path)
            if directory == "tests":
                for other in tree.files:
                    if is_test_module(other) and tree.shard_of(other) is None:
                        file_tests[other].append(path)

    # Data files, and the modules that read them.
    for path in changed:
        for rule in DATA_RULES:
            if not re.fullmatch(rule.pattern, path):
                continue
            covered.add(path)
            for test in rule.tests:
                if tree.exists(test):
                    route(test, path)
            for reader in rule.readers:
                route_importers(reader, path)

    if file_tests:
        names = sorted(file_tests)
        # A path under a directory another names runs with it.
        directories = [name for name in names if (tree.root / name).is_dir()]
        kept = [
            name
            for name in names
            if not any(name != directory and name.startswith(f"{directory}/") for directory in directories)
        ]
        planned = Planned(
            "tests",
            pytest_command(kept, workers),
            "the tests of what changed, of what imports it and of what reads it, at the default profile",
            paths=tuple(kept),
        )
        for name in names:
            for cause in dict.fromkeys(file_tests[name]):
                plan.add(planned, cause)
    for shard in sorted(shard_causes):
        planned = Planned(
            "properties",
            pytest_command(["tests/property"], workers, "--shard", shard),
            f"shard {shard} holds a property module that changed or imports what changed: its properties, "
            "feature audits and mutant searches, at the `ci` profile",
            env={PROFILE_VARIABLE: "ci"},
            paths=("tests/property",),
        )
        for cause in dict.fromkeys(shard_causes[shard]):
            plan.add(planned, cause)

    return plan.checks(), [path for path in changed if path not in covered]


# A figure a message states as a count of something a recount can show: "69,617 test cases".
FIGURE = re.compile(
    r"\b\d[\d,]*\s+(?:test cases|test case|cases|case files|files|tests|mutants|examples|runs|properties)\b"
)
MUTANT_MODULE = re.compile(r"tests/property/test_\w*mutant\w*\.py")
README_OF_PROPERTIES = "tests/property/README.md"


def stated_figures(text: str) -> list[str]:
    """Each count in `text` of a kind a recount can show, once, in order."""
    return list(dict.fromkeys(match.group(0) for match in FIGURE.finditer(text)))


def reminders(changed: Sequence[str], stated: Sequence[str]) -> list[str]:
    """What no check here can decide, from the paths changed and the figures stated in the CHANGELOG lines and
    commit messages the branch adds."""
    found: list[str] = []
    if any(MUTANT_MODULE.fullmatch(path) for path in changed) and README_OF_PROPERTIES not in changed:
        found.append(
            f"a mutant module changed and {README_OF_PROPERTIES} did not: is each mutant's row current, "
            "and does it name the assertion the mutant dies at?"
        )
    if is_code(changed) and "CHANGELOG.md" not in changed:
        found.append(
            "code changed and the CHANGELOG did not: does the change need an entry under Unreleased?"
        )
    if stated:
        found.append(
            "recount each figure the CHANGELOG lines and commit messages state, by what counts that thing "
            "(`pytest --collect-only -q` counts tests, not examples, case files or trace lines): "
            + "; ".join(f'"{figure}"' for figure in stated)
        )
    return found


def describe(planned: Planned) -> str:
    environment = " ".join(f"{name}={value}" for name, value in planned.env.items())
    command = " ".join(planned.command)
    return f"{environment + ' ' if environment else ''}{command}"


def print_plan(
    checks: Sequence[Planned], uncovered: Sequence[str], files: Sequence[str], to_decide: Sequence[str] = ()
) -> None:
    print(f"{len(files)} changed file(s); {len(checks)} check(s) selected")
    for stage in STAGES:
        staged = [planned for planned in checks if planned.stage == stage]
        if not staged:
            continue
        print(f"\n[{stage}]")
        for planned in staged:
            print(f"  {describe(planned)}")
            print(f"      why: {planned.why}")
            if planned.because:
                shown = ", ".join(planned.because[:4])
                more = len(planned.because) - 4
                print(f"      selected by: {shown}{f' and {more} more' if more > 0 else ''}")
    if uncovered:
        print("\nno check is selected for these (CI may check them; the self-review list applies):")
        for path in uncovered:
            print(f"  {path}")
    if to_decide:
        print("\nfor you to decide (no check can):")
        for reminder in to_decide:
            print(f"  - {reminder}")


Runner = Callable[[Planned, Path], int]


def run_check(planned: Planned, root: Path) -> int:
    environment = {**os.environ, **planned.env}
    return subprocess.run(planned.command, cwd=root, env=environment, check=False).returncode


def execute(
    checks: Sequence[Planned],
    stages: Sequence[str],
    keep_going: bool,
    root: Path = REPOSITORY,
    runner: Runner = run_check,
) -> tuple[int, list[str]]:
    """Run the checks of `stages` in order; the exit status (1 where any failed) and one summary line each.
    A stage after one that failed is not run, unless `keep_going`."""
    summary: list[str] = []
    failed = False
    for stage in STAGES:
        if stage not in stages:
            summary.append(f"[{stage}] not asked for")
            continue
        staged = [planned for planned in checks if planned.stage == stage]
        if failed and not keep_going:
            summary.extend(f"  not run (an earlier stage failed): {describe(planned)}" for planned in staged)
            continue
        for planned in staged:
            print(f"\n$ {describe(planned)}", flush=True)
            started = time.monotonic()
            status = runner(planned, root)
            seconds = time.monotonic() - started
            failed = failed or status != 0
            summary.append(f"  {'ok    ' if status == 0 else 'FAILED'} {seconds:6.1f} s  {describe(planned)}")
    return (1 if failed else 0), summary


def added_figures(base: str, root: Path = REPOSITORY) -> list[str]:
    """The figures in the CHANGELOG lines the branch adds and in its commit messages."""
    merge_base = git("merge-base", base, "HEAD", root=root).stdout.strip()
    changelog = git("diff", "--no-renames", "-U0", merge_base, "--", "CHANGELOG.md", root=root).stdout
    added = "\n".join(
        line[1:] for line in changelog.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    messages = git("log", "--format=%B", f"{merge_base}..HEAD", root=root).stdout
    return stated_figures(f"{added}\n{messages}")


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the mechanical checks that apply to a branch's changes."
    )
    parser.add_argument(
        "base", nargs="?", default=DEFAULT_BASE, help=f"the ref the branch is based on ({DEFAULT_BASE})"
    )
    parser.add_argument(
        "--list", action="store_true", help="print the checks and what selected them; run none"
    )
    parser.add_argument("--stage", action="append", choices=STAGES, help="run this stage alone (repeatable)")
    parser.add_argument(
        "--workers", type=int, default=min(12, os.cpu_count() or 1), help="pytest-xdist workers"
    )
    parser.add_argument("--keep-going", action="store_true", help="run a stage after one that failed")
    parser.add_argument("--key-file", help="the confidential-names key, else openmaterica.scanKeyFile")
    options = parser.parse_args(arguments)
    try:
        files = changed_files(options.base)
    except subprocess.CalledProcessError as error:
        print(f"cannot find the changes from {options.base}: {error.stderr.strip()}", file=sys.stderr)
        return 2
    checks, uncovered = plan_checks(files, Tree(), options.base, options.workers, options.key_file)
    print_plan(checks, uncovered, files, reminders(files, added_figures(options.base)))
    if options.list:
        return 0
    status, summary = execute(checks, options.stage or STAGES, options.keep_going)
    print("\nsummary")
    print("\n".join(summary))
    skipped = [stage for stage in STAGES if options.stage and stage not in options.stage]
    if skipped:
        print(f"stages not run: {', '.join(skipped)}")
    print("pre-review checks failed" if status else "the pre-review checks that ran passed; CI runs the rest")
    return status


if __name__ == "__main__":
    sys.exit(main())
