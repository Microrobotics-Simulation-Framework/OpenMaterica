# SPDX-License-Identifier: Apache-2.0
"""The pre-review script selects the checks a change calls for, and no others, and every check it can select
exists. Each rule has a change that must select its check and one that must not."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import pre_review
from scripts.pre_review import (
    DATA_RULES,
    GENERATORS,
    LOCATES_NO_RULED_DATA,
    Planned,
    Tree,
    plan_checks,
)
from tests.unit.throwaway_git import throwaway_repository

REPOSITORY = Path(__file__).resolve().parents[2]
CI = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
TREE = Tree(REPOSITORY)
KEY = "KEY"


def plan(*changed: str, tree: Tree = TREE) -> tuple[list[Planned], list[str]]:
    return plan_checks(changed, tree, base="BASE", workers=3, key_file=KEY)


def commands(checks: list[Planned], stage: str | None = None) -> list[str]:
    return [" ".join(check.command) for check in checks if stage is None or check.stage == stage]


def run_paths(checks: list[Planned]) -> set[str]:
    """The paths the planned pytest commands of the tests stage name."""
    return {path for check in checks if check.stage == "tests" for path in check.paths}


def shards(checks: list[Planned]) -> set[str]:
    return {
        check.command[check.command.index("--shard") + 1] for check in checks if check.stage == "properties"
    }


# --- what CI runs: the script holds its lists to the workflow's -------------------------------------------


def ci_assignment(name: str) -> str:
    match = re.search(rf"^\s*{name}='([^']*)'$", CI, re.MULTILINE)
    assert match, name
    return match.group(1)


def test_the_documentation_site_and_python_paths_are_the_workflows() -> None:
    assert ci_assignment("docs_paths") == pre_review.DOCUMENTATION_PATHS
    assert ci_assignment("site_paths") == pre_review.SITE_PATHS
    assert ci_assignment("python_paths") == pre_review.PYTHON_PATHS


def test_the_generators_are_the_ones_the_workflow_checks_on_python_3_11() -> None:
    assert set(re.findall(r"scripts/(gen_\w+)\.py --check", CI)) == set(GENERATORS)
    assert f'python-version: "{pre_review.GENERATOR_PYTHON}"' in CI
    assert f"--python {pre_review.GENERATOR_PYTHON}" in CI


@pytest.mark.parametrize(
    "command",
    [
        ("uv", "run", "ruff", "check"),
        ("uv", "run", "ruff", "format", "--check"),
        ("uv", "run", "mypy"),
        ("uv", "run", "pyright"),
    ],
)
def test_each_static_check_is_a_step_of_the_workflows_static_job(command: tuple[str, ...]) -> None:
    assert f"- run: {' '.join(command)}" in CI
    checks, _ = plan("src/materica/core/read.py")
    assert " ".join(command) in commands(checks, "fast")


def test_the_confidential_and_sign_off_checks_are_the_gates_commands() -> None:
    assert 'python3 scripts/check_signoff.py "$BASE" "$HEAD"' in CI
    assert "python3 scripts/check_confidential.py" in CI
    assert "--messages" in CI


# --- the rules, each with a change that selects its check and one that does not ----------------------------


@pytest.mark.parametrize(
    "path", ["CHANGELOG.md", "site/other.html", "src/materica/core/read.py", "scripts/x.sh"]
)
def test_every_change_runs_the_sign_off_scan_generators_and_freeze_checks(path: str) -> None:
    fast = commands(plan(path)[0], "fast")
    assert "python3 scripts/check_signoff.py BASE HEAD" in fast
    assert f"python3 scripts/check_confidential.py --messages BASE..HEAD --key-file {KEY}" in fast
    assert "python3 scripts/freeze_schema.py --check" in fast
    for generator in GENERATORS:
        assert any(command.endswith(f"scripts/{generator}.py --check") for command in fast)


def test_the_generators_run_in_their_own_python_3_11_environment_not_the_projects() -> None:
    checks, _ = plan("CHANGELOG.md")
    generated = [check for check in checks if "--check" in check.command and "--python" in check.command]
    synced = [check for check in checks if check.command[:2] == ("uv", "sync")]
    assert len(generated) == len(GENERATORS)
    assert len(synced) == 1
    assert {check.env["UV_PROJECT_ENVIRONMENT"] for check in [*generated, *synced]} == {
        pre_review.generator_environment()["UV_PROJECT_ENVIRONMENT"]
    }
    assert pre_review.generator_environment()["UV_PROJECT_ENVIRONMENT"].endswith("python-3.11")
    assert not any(
        "UV_PROJECT_ENVIRONMENT" in check.env for check in checks if check not in generated + synced
    )


@pytest.mark.parametrize(
    "path", ["src/materica/core/read.py", "README.md", "tests/unit/test_read.py", "typings/x.pyi"]
)
def test_a_change_to_code_runs_the_linters_and_type_checkers(path: str) -> None:
    fast = commands(plan(path)[0], "fast")
    assert {"uv run ruff check", "uv run ruff format --check", "uv run mypy", "uv run pyright"} <= set(fast)


@pytest.mark.parametrize(
    "path",
    [
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "docs/validation/other.yaml",
        "site/other.html",
        "assets/logo.svg",
    ],
)
def test_a_change_to_documentation_or_the_site_alone_runs_none_of_them(path: str) -> None:
    fast = commands(plan(path)[0], "fast")
    assert not {"uv run ruff check", "uv run mypy", "uv run pyright"} & set(fast)


def test_a_change_with_no_path_is_code_as_the_gate_reads_it() -> None:
    assert pre_review.is_code([])
    assert not pre_review.is_code(["CHANGELOG.md", "site/other.html"])
    assert pre_review.is_code(["CHANGELOG.md", "site/other.html", "scripts/x.py"])
    assert pre_review.is_code(["docs/regulatory/helper.py"])  # a Python file is code wherever it sits
    assert not pre_review.is_code(["docs/regulatory/other.md"])


def test_the_lock_file_is_checked_when_it_or_pyproject_changes_and_not_otherwise() -> None:
    assert "uv lock --check" in commands(plan("pyproject.toml")[0], "fast")
    assert "uv lock --check" in commands(plan("uv.lock")[0], "fast")
    assert "uv lock --check" not in commands(plan("src/materica/core/read.py")[0], "fast")


def test_a_property_module_runs_its_shard_at_ci_and_the_audit_controls_that_import_it() -> None:
    checks, _ = plan("tests/property/test_value_field_properties.py")
    assert "records" in shards(checks)
    assert "tests/unit/test_audit_controls.py" in run_paths(checks)
    assert all(
        check.env == {"MATERICA_HYPOTHESIS_PROFILE": "ci"} for check in checks if check.stage == "properties"
    )
    assert "writer" not in shards(checks)  # control: a shard that holds none of the module's importers


def test_a_mutant_module_and_its_table_run_with_their_shard() -> None:
    assert "writer" in shards(plan("tests/property/test_writer_mutants.py")[0])
    assert "writer" in shards(plan("tests/property/test_writer_mutant_table.py")[0])
    assert "step8_mutants" in shards(plan("tests/property/test_value_field_mutant_table.py")[0])
    assert "step8_mutants" not in shards(plan("tests/property/test_writer_mutant_table.py")[0])


def test_a_property_helper_runs_the_shards_of_the_modules_that_import_it() -> None:
    checks, _ = plan("tests/property/audits.py")
    assert "tests/unit/test_audits.py" in run_paths(checks)
    assert "tests/unit/test_audit_controls.py" in run_paths(checks)
    assert {"json", "records"} <= shards(checks)


def test_a_core_module_runs_the_property_shards_and_the_unit_test_of_what_imports_it() -> None:
    checks, _ = plan("src/materica/core/hashing.py")
    assert "json" in shards(checks)
    assert "tests/unit/test_hashing.py" in run_paths(checks)
    assert "tests/unit/test_check_signoff.py" not in run_paths(
        checks
    )  # control: nothing there imports hashing


def test_a_conftest_applies_to_every_shard_and_the_top_one_to_every_test() -> None:
    assert shards(plan("tests/property/conftest.py")[0]) == set(TREE.shards())
    assert "tests/unit/test_read.py" not in run_paths(plan("tests/property/conftest.py")[0])
    assert "tests/unit/test_read.py" in run_paths(plan("tests/conftest.py")[0])


def test_a_script_runs_its_own_unit_test_and_no_shard() -> None:
    checks, _ = plan("scripts/check_signoff.py")
    assert run_paths(checks) == {"tests/unit/test_check_signoff.py"}
    assert shards(checks) == set()
    assert "tests/unit/test_check_signoff.py" not in run_paths(plan("scripts/check_site.py")[0])  # control


def test_a_specification_file_runs_the_spec_sync_tests_and_the_generators_tests() -> None:
    for path in (
        "docs/specification/provenance.md",
        "DOCUMENTATION_ARCHITECTURE.md",
        "design/ARCHITECTURE_DRAFT.md",
    ):
        checks, uncovered = plan(path)
        assert {"tests/spec_sync", "tests/unit/test_generators.py"} <= run_paths(checks)
        assert uncovered == []
        assert shards(checks) == set()
    assert run_paths(plan("docs/regulatory/other.md")[0]) == set()  # control: not a specification file


def test_a_schema_file_runs_the_spec_sync_tests_and_the_shards_of_what_reads_it() -> None:
    checks, _ = plan("src/materica/schema/0.1/record.writer.json")
    assert {"tests/spec_sync", "tests/unit/test_shapes.py"} <= run_paths(checks)
    assert {"writer", "agreement"} <= shards(checks)
    assert run_paths(plan("src/materica/data/conformance/plain_read/CASES.md")[0]).isdisjoint(
        {"tests/unit/test_shapes.py"}
    )


def test_a_conformance_case_runs_the_conformance_and_spec_sync_tests() -> None:
    checks, _ = plan("src/materica/data/conformance/plain_read/CASES.md")
    assert {"tests/conformance", "tests/spec_sync"} <= run_paths(checks)


def test_a_spec_sync_table_runs_the_spec_sync_tests_alone() -> None:
    checks, _ = plan("tests/spec_sync/name_overlaps.json")
    assert run_paths(checks) == {"tests/spec_sync"}
    assert shards(checks) == set()


def test_a_workflow_runs_the_workflow_tests_and_a_site_file_does_not() -> None:
    assert "tests/unit/test_ci_workflows.py" in run_paths(plan(".github/workflows/repeat.yml")[0])
    assert run_paths(plan("site/other.html")[0]) == set()


def test_the_build_files_run_the_tests_that_hold_the_pythons_and_the_profiles() -> None:
    assert {"tests/unit/test_python_versions.py", "tests/unit/test_hypothesis_profiles.py"} <= run_paths(
        plan("pyproject.toml")[0]
    )


def test_a_directory_named_runs_the_tests_under_it_once() -> None:
    checks, _ = plan("docs/specification/provenance.md", "tests/spec_sync/test_t1.py")
    (command,) = [check.command for check in checks if check.stage == "tests"]
    assert "tests/spec_sync" in command
    assert "tests/spec_sync/test_t1.py" not in command


def test_a_change_selects_each_check_once_with_every_path_that_selected_it() -> None:
    checks, _ = plan("docs/specification/provenance.md", "docs/specification/uncertainty.md")
    (run,) = [check for check in checks if check.stage == "tests"]
    assert run.because == ["docs/specification/provenance.md", "docs/specification/uncertainty.md"]
    keys = [(check.stage, check.command) for check in checks]
    assert len(keys) == len(set(keys))


def test_a_change_no_rule_selects_a_check_for_is_listed() -> None:
    assert plan("CHANGELOG.md")[1] == ["CHANGELOG.md"]
    assert plan("tests/property/README.md")[1] == ["tests/property/README.md"]
    assert plan("site/other.html", "scripts/check_signoff.py")[1] == ["site/other.html"]  # control: covered


def test_the_stages_run_in_order() -> None:
    checks, _ = plan("src/materica/core/hashing.py", "docs/specification/provenance.md")
    stages = [check.stage for check in checks]
    assert stages == sorted(stages, key=pre_review.STAGES.index)
    assert set(stages) == set(pre_review.STAGES)


# --- the import graph --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "source", "names"),
    [
        ("tests/a.py", "import x.y\nimport z as w", {"x.y", "z"}),
        ("tests/a.py", "from x import y, z", {"x", "x.y", "x.z"}),
        ("tests/a.py", "from x import *", {"x"}),
        ("tests/property/a.py", "from . import b", {"tests.property", "tests.property.b"}),
        ("tests/property/a.py", "from .b import c", {"tests.property.b", "tests.property.b.c"}),
        ("tests/property/a.py", "from ..unit import d", {"tests.unit", "tests.unit.d"}),
        ("src/materica/core/__init__.py", "from . import jsonio", {"materica.core", "materica.core.jsonio"}),
        ("tests/a.py", "def f(:", set[str]()),
    ],
)
def test_imported_names(path: str, source: str, names: set[str]) -> None:
    assert pre_review.imported_names(path, source) == names


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("src/materica/core/read.py", "materica.core.read"),
        ("src/materica/core/__init__.py", "materica.core"),
        ("src/materica/shapes.pyi", "materica.shapes"),
        ("tests/property/strategies.py", "tests.property.strategies"),
        ("scripts/pre_review.py", "scripts.pre_review"),
        ("README.md", None),
    ],
)
def test_module_names(path: str, name: str | None) -> None:
    assert pre_review.module_name(path) == name


def small_tree(tmp_path: Path) -> Tree:
    files = {
        "src/pkg/__init__.py": "",
        "src/pkg/a.py": "",
        "src/pkg/b.py": "from pkg import a",
        "src/pkg/c.py": "",
        "tests/conftest.py": 'SHARDS = {"one": ("test_p",), "two": ("test_q",)}\n',
        "tests/unit/test_b.py": "from pkg import b",
        "tests/unit/test_c.py": "from pkg import c",
        "tests/property/test_p.py": "from pkg import b",
        "tests/property/test_q.py": "from pkg import c",
        "tests/spec_sync/test_s.py": "",
        "docs/specification/x.md": "",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    return Tree(tmp_path)


def test_a_change_reaches_what_imports_it_through_others_and_not_what_does_not(tmp_path: Path) -> None:
    tree = small_tree(tmp_path)
    checks, _ = plan("src/pkg/a.py", tree=tree)
    assert run_paths(checks) == {"tests/unit/test_b.py"}  # through b
    assert shards(checks) == {"one"}  # control: two imports only c


def test_a_deleted_module_still_reaches_what_imported_it(tmp_path: Path) -> None:
    tree = small_tree(tmp_path)
    (tmp_path / "src/pkg/a.py").unlink()
    assert run_paths(plan("src/pkg/a.py", tree=tree)[0]) == {"tests/unit/test_b.py"}


def test_a_deleted_test_is_not_run(tmp_path: Path) -> None:
    tree = small_tree(tmp_path)
    (tmp_path / "tests/unit/test_b.py").unlink()
    assert run_paths(plan("tests/unit/test_b.py", tree=tree)[0]) == set()


def test_the_citation_test_runs_for_a_specification_file_where_it_exists_and_only_there(
    tmp_path: Path,
) -> None:
    tree = small_tree(tmp_path)
    assert pre_review.CITATION_TEST not in run_paths(plan("docs/specification/x.md", tree=tree)[0])
    (tmp_path / "tests/reference").mkdir()
    (tmp_path / pre_review.CITATION_TEST).write_text("", encoding="utf-8")
    assert pre_review.CITATION_TEST in run_paths(plan("docs/specification/x.md", tree=Tree(tmp_path))[0])
    # control: a change that is no specification file does not select it
    assert pre_review.CITATION_TEST not in run_paths(plan("src/pkg/c.py", tree=Tree(tmp_path))[0])


# --- every check it can run exists -----------------------------------------------------------------------


def everything_changed() -> list[str]:
    """A change that matches every rule: one file of each kind of path the rules name."""
    return [
        "src/materica/core/read.py",
        "tests/conftest.py",
        "tests/property/conftest.py",
        *(f"tests/property/{module}.py" for modules in TREE.shards().values() for module in modules),
        "scripts/check_signoff.py",
        "pyproject.toml",
        "docs/specification/provenance.md",
        "src/materica/schema/0.1/record.writer.json",
        "src/materica/data/conformance/plain_read/CASES.md",
        "tests/spec_sync/name_overlaps.json",
        ".github/workflows/ci.yml",
        "scripts/confidential_digests.txt",
    ]


def test_every_path_a_check_names_exists() -> None:
    checks, uncovered = plan(*everything_changed())
    assert uncovered == []
    for check in checks:
        for path in check.paths:
            assert (REPOSITORY / path).exists(), f"{path} in: {' '.join(check.command)}"
    assert {check.stage for check in checks} == set(pre_review.STAGES)


def test_every_path_a_data_rule_names_exists_but_the_optional_citation_test() -> None:
    for rule in DATA_RULES:
        for path in (*rule.tests, *rule.readers):
            if path != pre_review.CITATION_TEST:
                assert (REPOSITORY / path).exists(), f"{path} in the rule for {rule.name}"
        assert re.compile(rule.pattern)


def test_every_shard_a_check_names_is_one_of_the_conftests() -> None:
    checks, _ = plan(*everything_changed())
    assert shards(checks) == set(TREE.shards())


@pytest.mark.parametrize("shard", sorted(Tree(REPOSITORY).shards()))
def test_pytest_collects_each_shard_the_checks_name(shard: str) -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/property",
            "--shard",
            shard,
            "--collect-only",
            "-q",
            "-p",
            "no:xdist",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-500:] + done.stderr[-500:]
    assert re.search(r"\b\d+ tests? collected\b", done.stdout)


def test_every_module_that_finds_a_data_file_by_its_own_location_is_a_reader_or_listed_why_not() -> None:
    readers = {reader for rule in DATA_RULES for reader in rule.readers}
    found = {
        path
        for path, source in TREE.files.items()
        if (
            path.startswith("src/materica/")
            or path.startswith(("tests/property/", "tests/conformance/", "tests/fuzz/"))
        )
        or path in {"tests/conftest.py", "tests/verdicts.py"}
        if "resources.files" in source or "__file__" in source
    }
    assert found - readers - set(LOCATES_NO_RULED_DATA) == set()
    assert set(LOCATES_NO_RULED_DATA) <= found, "an entry for a module that no longer locates files"
    assert readers <= set(TREE.files), "a reader that does not exist"


# --- the changes, read from git ---------------------------------------------------------------------------


def commit(message: str, *options: str) -> None:
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@example.org",
            "commit",
            "-q",
            *options,
            "-m",
            message,
        ],
        check=True,
    )


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return throwaway_repository(tmp_path, monkeypatch)


def test_the_changes_are_committed_staged_unstaged_untracked_deleted_and_renamed_files(
    repository: Path,
) -> None:
    for name in ("kept", "edited", "staged", "deleted", "moved", "untouched"):
        (repository / name).write_text(name)
    commit("base")
    subprocess.run(["git", "checkout", "-q", "-b", "branch"], check=True)
    (repository / "edited").write_text("changed")
    commit("on the branch")
    (repository / "staged").write_text("changed")
    subprocess.run(["git", "add", "staged"], check=True)
    (repository / "kept").write_text("changed, not staged")
    (repository / "deleted").unlink()
    (repository / "moved").rename(repository / "moved_to")
    (repository / "new").write_text("untracked")
    assert pre_review.changed_files("main", repository) == [
        "deleted",
        "edited",
        "kept",
        "moved",
        "moved_to",
        "new",
        "staged",
    ]


def test_the_changes_are_from_the_merge_base_not_from_the_base_tip(repository: Path) -> None:
    (repository / "a").write_text("a")
    commit("base")
    subprocess.run(["git", "checkout", "-q", "-b", "branch"], check=True)
    (repository / "mine").write_text("mine")
    commit("mine")
    subprocess.run(["git", "checkout", "-q", "main"], check=True)
    (repository / "theirs").write_text("theirs")
    commit("theirs, since the branch was cut")
    subprocess.run(["git", "checkout", "-q", "branch"], check=True)
    assert pre_review.changed_files("main", repository) == ["mine"]


def test_a_file_moved_with_git_mv_and_committed_gives_both_paths(repository: Path) -> None:
    # A rename git pairs is only one it reports from a commit or the index; without `--no-renames` the old
    # path is lost, and with it the importers of a moved module.
    (repository / "core").mkdir()
    (repository / "core" / "hashing.py").write_text("x = 1\n" * 20)
    commit("base")
    subprocess.run(["git", "checkout", "-q", "-b", "branch"], check=True)
    subprocess.run(["git", "mv", "core/hashing.py", "core/digest.py"], check=True)
    commit("moved")
    assert pre_review.changed_files("main", repository) == ["core/digest.py", "core/hashing.py"]
    (repository / "core" / "again.py").write_text("x = 1\n" * 20)
    subprocess.run(
        ["git", "mv", "core/digest.py", "core/other.py"], check=True
    )  # and one staged, not committed
    assert pre_review.changed_files("main", repository) == [
        "core/again.py",
        "core/hashing.py",
        "core/other.py",
    ]


def test_a_path_with_a_newline_in_it_is_one_path(repository: Path) -> None:
    (repository / "kept").write_text("kept")
    commit("base")
    subprocess.run(["git", "checkout", "-q", "-b", "branch"], check=True)
    (repository / "two\nlines.py").write_text("x")
    (repository / "kept").write_text("changed")
    commit("a name with a newline")
    (repository / "tab\there.py").write_text("x")  # untracked
    assert pre_review.changed_files("main", repository) == ["kept", "tab\there.py", "two\nlines.py"]


def test_an_unknown_base_is_refused() -> None:
    assert pre_review.main(["no-such-ref-anywhere", "--list"]) == 2


def test_the_scan_key_is_the_one_given_else_the_clones_setting_else_none(repository: Path) -> None:
    assert pre_review.key_arguments(None, repository) == ()
    assert pre_review.key_arguments("given", repository) == ("--key-file", "given")
    subprocess.run(["git", "config", "openmaterica.scanKeyFile", "~/a.key"], check=True)
    assert pre_review.key_arguments(None, repository) == ("--key-file", str(Path("~/a.key").expanduser()))
    assert pre_review.key_arguments("given", repository) == ("--key-file", "given")


# --- running -----------------------------------------------------------------------------------------------


def checks_of_every_stage() -> list[Planned]:
    return [
        Planned("fast", ("fast-1",), "why"),
        Planned("fast", ("fast-2",), "why"),
        Planned("tests", ("tests-1",), "why"),
        Planned("properties", ("properties-1",), "why"),
    ]


def test_the_stages_run_in_order_and_a_failure_stops_the_next() -> None:
    ran: list[str] = []

    def runner(planned: Planned, root: Path) -> int:
        ran.append(planned.command[0])
        return 1 if planned.command[0] == "fast-2" else 0

    status, summary = pre_review.execute(checks_of_every_stage(), pre_review.STAGES, False, runner=runner)
    assert status == 1
    assert ran == ["fast-1", "fast-2"]
    assert [line for line in summary if "not run" in line] == [
        "  not run (an earlier stage failed): tests-1",
        "  not run (an earlier stage failed): properties-1",
    ]
    assert "FAILED" in "\n".join(summary)


def test_keep_going_runs_the_stages_after_a_failure() -> None:
    ran: list[str] = []

    def runner(planned: Planned, root: Path) -> int:
        ran.append(planned.command[0])
        return 1 if planned.command[0] == "fast-1" else 0

    status, _ = pre_review.execute(checks_of_every_stage(), pre_review.STAGES, True, runner=runner)
    assert status == 1
    assert ran == ["fast-1", "fast-2", "tests-1", "properties-1"]


def test_a_run_where_every_check_passes_exits_zero_and_a_stage_not_asked_for_is_said() -> None:
    ran: list[str] = []

    def runner(planned: Planned, root: Path) -> int:
        ran.append(planned.command[0])
        return 0

    status, summary = pre_review.execute(checks_of_every_stage(), ["fast", "tests"], False, runner=runner)
    assert status == 0
    assert ran == ["fast-1", "fast-2", "tests-1"]
    assert "[properties] not asked for" in summary


def test_the_environment_of_a_check_reaches_its_process(tmp_path: Path) -> None:
    out = tmp_path / "seen"
    code = f"import os; open({str(out)!r}, 'w').write(os.environ['PRE_REVIEW_X'])"
    planned = Planned("fast", (sys.executable, "-c", code), "why", env={"PRE_REVIEW_X": "seen"})
    assert pre_review.run_check(planned, tmp_path) == 0
    assert out.read_text() == "seen"
    assert (
        pre_review.run_check(Planned("fast", (sys.executable, "-c", "raise SystemExit(3)"), "why"), tmp_path)
        == 3
    )


def test_the_command_lists_its_plan_without_running_it(capsys: pytest.CaptureFixture[str]) -> None:
    assert pre_review.main(["HEAD", "--list"]) == 0
    printed = capsys.readouterr().out
    assert "check(s) selected" in printed
    assert "[fast]" in printed
    assert "selected by" in printed


def test_the_script_runs_as_a_command() -> None:
    done = subprocess.run(
        [sys.executable, "scripts/pre_review.py", "HEAD", "--list"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "[fast]" in done.stdout


def test_the_chosen_pytest_command_has_the_workers_and_the_work_stealing_distribution() -> None:
    command = pre_review.pytest_command(["tests/unit"], 7, "--shard", "json")
    assert command[command.index("-n") + 1] == "7"
    assert command[command.index("--dist") + 1] == "worksteal"
    assert command[command.index("--shard") + 1] == "json"


def test_the_checks_come_in_the_order_of_the_stages_whatever_the_order_they_were_planned_in() -> None:
    plan_of_checks = pre_review.Plan()
    for stage in ("properties", "tests", "fast"):
        plan_of_checks.add(Planned(stage, (stage,), "why"))
    assert [check.stage for check in plan_of_checks.checks()] == ["fast", "tests", "properties"]


def test_is_test_module_names_the_four_groups_of_tests_and_no_other_file() -> None:
    for group in ("unit", "spec_sync", "conformance", "property"):
        assert pre_review.is_test_module(f"tests/{group}/test_x.py")
    for path in ("tests/fuzz/test_x.py", "tests/unit/helper.py", "scripts/test_x.py", "tests/unit/test_x.md"):
        assert not pre_review.is_test_module(path)


def test_a_module_of_the_same_name_outside_the_property_directory_is_in_no_shard(tmp_path: Path) -> None:
    tree = small_tree(tmp_path)
    assert tree.shard_of("tests/property/test_p.py") == "one"
    assert tree.shard_of("tests/unit/test_p.py") is None
    assert tree.shard_of("tests/property/sub/test_p.py") is None


@pytest.mark.parametrize(
    ("status", "said"), [(1, "pre-review checks failed"), (0, "pre-review checks that ran passed")]
)
def test_the_command_ends_with_the_status_of_the_checks_it_ran(
    status: int, said: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:

    def executed(*arguments: object, **keywords: object) -> tuple[int, list[str]]:
        return status, ["  summary line"]

    monkeypatch.setattr(pre_review, "execute", executed)
    assert pre_review.main(["HEAD", "--stage", "fast"]) == status
    assert said in capsys.readouterr().out


def test_listing_the_plan_runs_none_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    def never(*arguments: object, **keywords: object) -> tuple[int, list[str]]:
        raise AssertionError("--list ran the checks")

    monkeypatch.setattr(pre_review, "execute", never)
    assert pre_review.main(["HEAD", "--list"]) == 0


# --- what no check can decide ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "figures"),
    [
        ("69,617 test cases over 101,231 cases", ["69,617 test cases", "101,231 cases"]),
        ("each of the 1266 case files, 1266 case files again", ["1266 case files"]),
        ("38 mutants and 2,000 examples in 12 tests", ["38 mutants", "2,000 examples", "12 tests"]),
        ("a section 3 item 12 of 4 steps, version 1.2", []),
    ],
)
def test_stated_figures(text: str, figures: list[str]) -> None:
    assert pre_review.stated_figures(text) == figures


def test_reminders_name_a_mutant_table_changed_beside_a_readme_that_was_not() -> None:
    mutants = "tests/property/test_writer_mutants.py"
    assert any("mutant" in text for text in pre_review.reminders([mutants], []))
    assert not any(
        "mutant" in text for text in pre_review.reminders([mutants, "tests/property/README.md"], [])
    )
    assert not any(
        "mutant" in text for text in pre_review.reminders(["tests/property/test_writer_properties.py"], [])
    )


def test_reminders_name_code_changed_beside_a_changelog_that_was_not() -> None:
    assert any("CHANGELOG" in text for text in pre_review.reminders(["src/materica/core/read.py"], []))
    assert not any(
        "CHANGELOG" in text
        for text in pre_review.reminders(["src/materica/core/read.py", "CHANGELOG.md"], [])
    )
    assert not any("CHANGELOG" in text for text in pre_review.reminders(["CONTRIBUTING.md"], []))


def test_reminders_list_the_figures_stated_and_none_where_none_is() -> None:
    (reminder,) = [
        text for text in pre_review.reminders(["CHANGELOG.md"], ["1266 case files"]) if "recount" in text
    ]
    assert '"1266 case files"' in reminder
    assert not any("recount" in text for text in pre_review.reminders(["CHANGELOG.md"], []))


def test_the_figures_added_are_those_of_the_changelog_lines_and_commit_messages_of_the_branch(
    repository: Path,
) -> None:
    (repository / "CHANGELOG.md").write_text("- an old line of 5 tests\n")
    commit("base with 7 mutants")
    subprocess.run(["git", "checkout", "-q", "-b", "branch"], check=True)
    (repository / "CHANGELOG.md").write_text("- an old line of 5 tests\n- a new line of 1,266 case files\n")
    commit("the branch, 9 examples")
    assert pre_review.added_figures("main", repository) == ["1,266 case files", "9 examples"]
