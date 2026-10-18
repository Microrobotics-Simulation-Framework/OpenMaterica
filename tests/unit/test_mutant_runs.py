# SPDX-License-Identifier: Apache-2.0
"""The mutant table's script never gives a broken mutant as killed, refuses a request it cannot run as asked,
and reads a record only as its job writes one. tests/unit/test_ci_workflows.py runs the workflow's steps with
it, the patches' refusals among them."""

import itertools
import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts import mutant_runs
from scripts.mutant_runs import BROKEN, KILLED, SURVIVED, UNDECIDED, Request, RequestError
from tests.unit.throwaway_git import throwaway_repository

FAILED = [{"test": "tests/test_x.py::test_y", "message": "assert 1 == 2"}]
# Two collected tests that failed, the first first; and a collection error pytest-xdist reported, no test.
TWO_FAILED = [*FAILED, {"test": "tests/test_x.py::test_z", "message": "assert 3 == 4"}]
NOT_A_TEST = [{"test": "gw0::gw0", "message": "collection failure"}]
STAGES = ("applied", "imports", "collected")


def every_record() -> list[dict[str, Any]]:
    """A record of each combination of facts a job can write, and some it cannot: each stage passed, failed or
    not reached, refused or not, each exit status pytest or `timeout` gives and one never given, no failure,
    a named one, two, or one that is not a failure's shape, and an entry of the report that is no collected
    test or none."""
    records: list[dict[str, Any]] = []
    for applied, imports, collected, refused, status, failures, uncollected in itertools.product(
        (True, False, None),
        (True, False, None),
        (True, False, None),
        ([], ["a reason"]),
        (None, 0, 1, 2, 3, 4, 5, 124, 7),
        ([], FAILED, TWO_FAILED, [{"name": "x"}]),
        ([], NOT_A_TEST),
    ):
        records.append(
            {
                "mutant": "m",
                "touched": ["src/materica/a.py"],
                "refused": refused,
                "applied": applied,
                "imports": imports,
                "collected": collected,
                "tests": 3,
                "status": status,
                "failures": failures,
                "uncollected": uncollected,
                "message": "why",
            }
        )
    return records


def verdict_problems(verdict: Callable[[Mapping[str, Any]], tuple[str, str]]) -> list[str]:
    """Each record of `every_record` to which `verdict` gives another outcome than its facts allow: killed
    only where nothing was refused, every stage passed, the report named nothing that is no collected test,
    and pytest failed (1, or 2 where `-x` stopped it under pytest-xdist) at a collected test, the first of
    which it gives; broken wherever, nothing refused, a stage failed, or every stage passed and the report
    named what is no collected test; survived only where every stage passed and pytest passed naming no
    failure; undecided otherwise."""
    problems: list[str] = []
    for record in every_record():
        found = verdict(record)
        stages = [record[stage] for stage in STAGES]
        failures = record["failures"]
        if record["refused"]:
            expected = UNDECIDED
        elif False in stages:
            expected = BROKEN
        elif stages != [True, True, True]:
            expected = UNDECIDED
        elif record["uncollected"]:
            expected = BROKEN
        elif record["status"] == 0 and not failures:
            expected = SURVIVED
        elif record["status"] in (1, 2) and failures in (FAILED, TWO_FAILED):
            expected = KILLED
        else:
            expected = UNDECIDED
        if found[0] != expected or (expected == KILLED and found[1] != failures[0]["test"]):
            problems.append(f"{record} is {found}, not {expected}")
    return problems


def test_no_record_is_given_an_outcome_its_facts_do_not_allow() -> None:
    assert verdict_problems(mutant_runs.verdict) == []


def test_the_verdict_check_can_fail() -> None:
    """The control: a verdict that reads the failures before the stages gives a broken mutant as killed."""

    def failures_first(record: Mapping[str, Any]) -> tuple[str, str]:
        if record["failures"] == FAILED and record["status"] in (1, 2):
            return KILLED, FAILED[0]["test"]
        return mutant_runs.verdict(record)

    problems = verdict_problems(failures_first)
    assert any(
        "'applied': False" in line and "('killed'" in line and "not broken" in line for line in problems
    )


def test_the_verdict_check_finds_a_kill_by_what_is_no_collected_test_and_the_last_failure_named() -> None:
    """The controls: a verdict that does not read what the report named beside the collected tests gives a
    collection error under pytest-xdist as killed (#46's review, H3); one that names the last failure gives
    the second test of two (its L4, m08)."""

    def uncollected_unread(record: Mapping[str, Any]) -> tuple[str, str]:
        return mutant_runs.verdict(dict(record, uncollected=[]))

    def last_named(record: Mapping[str, Any]) -> tuple[str, str]:
        found = mutant_runs.verdict(record)
        return (KILLED, record["failures"][-1]["test"]) if found[0] == KILLED else found

    assert any("gw0::gw0" in line and "not broken" in line for line in verdict_problems(uncollected_unread))
    assert any("test_z" in line and "not killed" in line for line in verdict_problems(last_named))


def test_gits_report_gives_one_path_a_file_and_says_where_one_is_binary() -> None:
    """`git apply --numstat -z` gives one path for each file, the new path alone of a rename (checked with git
    2.43), which is why the request also reads the `diff --git` lines; an entry without a path gives an empty
    one, which no plain path matches."""
    assert mutant_runs.numstat_paths("1\t1\tsrc/a.py\x00-\t-\tb.bin\x00") == (["src/a.py", "b.bin"], True)
    assert mutant_runs.numstat_paths("0\t0\t\x00") == ([""], False)
    assert mutant_runs.numstat_paths("") == ([], False)


def test_every_name_a_patch_gives_its_file_is_read() -> None:
    """A `diff --git` line naming one plain path twice gives it; one naming two gives both and a problem, as
    does one git reads in another form and a `---` or `+++` line before the first hunk naming another path;
    a hunk's lines are content, though they start as those lines do."""
    edit = "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n--- a/x\n+++ b/y\n"
    new = (
        "diff --git a/src/n.py b/src/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/n.py\n"
        "@@ -0,0 +1 @@\n+1\n"
    )
    assert mutant_runs.named_paths(edit + new) == (
        ["src/a.py", "src/n.py"],
        ["src/a.py"] * 2 + ["src/n.py"] * 2,
        [],
    )
    two = mutant_runs.named_paths("diff --git a/src/a.py b/src/b.py\n--- a/src/a.py\n+++ b/src/b.py\n")
    assert (two.headers, two.paths) == ([None], ["src/a.py", "src/b.py"])
    assert len(two.problems) == 1
    assert "names two paths in one `diff --git` line, src/a.py and src/b.py" in two.problems[0]
    odd = mutant_runs.named_paths("diff --git x/src/a.py y/src/b.py\n")
    assert (odd.headers, odd.paths, len(odd.problems)) == ([None], [], 1)
    dashes = mutant_runs.named_paths("diff --git a/src/b.py b/src/b.py\n--- a/src/a.py\n+++ b/src/b.py\n")
    assert (dashes.headers, len(dashes.problems)) == (["src/b.py"], 1), dashes


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A committed tree holding a test file and two patches in mutants/, one of them a plain edit."""
    root = throwaway_repository(tmp_path, monkeypatch)
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_y():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "t"], check=True)
    (root / "tests" / "test_x.py").write_text("def test_y():\n    assert False\n", encoding="utf-8")
    patch = subprocess.run(["git", "diff"], check=True, capture_output=True, text=True).stdout
    subprocess.run(["git", "checkout", "-q", "--", "tests"], check=True)
    (root / "mutants").mkdir()
    for name in ("b", "a"):
        (root / "mutants" / f"{name}.patch").write_text(patch, encoding="utf-8")
    (root / "mutants" / "README.md").write_text("notes\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "m"], check=True)
    return root


GOOD = {
    "MUTANTS": "a b",
    "SELECTION": "tests/test_x.py::test_y tests",
    "PROFILE": "ci",
    "PYTHON_VERSION": "3.12",
    "SEED": "0",
    "EXTRA": "--shard records  --property-controls=none",
}


def test_a_request_within_its_bounds_is_written_as_its_outputs(repository: Path) -> None:
    request = mutant_runs.checked_request(GOOD, repository)
    assert mutant_runs.outputs(request) == {
        "mutants": "a b",
        "matrix": json.dumps(["", "a", "b"]),
        "selection": "tests/test_x.py::test_y tests",
        "profile": "ci",
        "python": "3.12",
        "seed": "0",
        "extra": "--shard=records --property-controls=none",
    }


def test_no_mutant_named_runs_every_committed_patch_and_no_seed_one_drawn(repository: Path) -> None:
    drawn: list[int] = []

    def draw(below: int) -> int:
        drawn.append(below)
        return 123

    request = mutant_runs.checked_request(GOOD | {"MUTANTS": "", "SEED": ""}, repository, draw)
    assert (request.mutants, request.seed, drawn) == (("a", "b"), 123, [mutant_runs.MAX_SEED + 1])


@pytest.mark.parametrize(
    ("name", "value", "problem"),
    [
        ("MUTANTS", "a a", "the mutant a is named twice"),
        ("MUTANTS", "a A", "the mutants a and A differ only in case"),
        ("MUTANTS", "a\tb", "MUTANTS 'a\\tb' holds a character other than printable ASCII"),
        ("MUTANTS", " ".join(f"m{index}" for index in range(201)), "201 mutants, more than 200"),
        ("SELECTION", "", "the selection is empty"),
        ("SELECTION", "src", "the selection's path 'src' is not `tests` or a path under it"),
        ("SELECTION", "tests/../src", "is not `tests` or a path under it"),
        ("SELECTION", "tests/test_missing.py", "is no file or directory under tests/"),
        ("SELECTION", "tests::", "names nothing after `::`"),
        ("SELECTION", " ".join(["tests"] * 21), "names 21 paths or nodes, more than 20"),
        ("PROFILE", "default", "the profile 'default' is not one of dev, ci, deep"),
        ("PYTHON_VERSION", "3.10", "the Python '3.10' is not one of"),
        ("SEED", "-1", "the seed '-1' is not a whole number"),
        ("SEED", "1000000000", "the seed 1000000000 is not from 0 to 999999999"),
        ("SEED", "010", "the seed '010' is not a whole number"),
        ("EXTRA", "--hypothesis-seed=5", "is not one of --shard, --property-controls"),
        ("EXTRA", "--shard a --shard b", "the extra argument --shard is given twice"),
    ],
)
def test_a_request_out_of_its_bounds_is_refused_with_every_reason(
    repository: Path, name: str, value: str, problem: str
) -> None:
    with pytest.raises(RequestError) as refused:
        mutant_runs.checked_request(GOOD | {name: value}, repository)
    assert any(problem in line for line in refused.value.problems), refused.value.problems


def test_no_patch_committed_and_none_named_is_refused(repository: Path) -> None:
    subprocess.run(["git", "rm", "-q", "mutants/a.patch", "mutants/b.patch"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "none"], check=True)
    with pytest.raises(RequestError, match="no mutant is named, and no patch is committed in mutants/"):
        mutant_runs.checked_request(GOOD | {"MUTANTS": ""}, repository)


def record(mutant: str, **facts: object) -> dict[str, object]:
    found: dict[str, object] = {
        "mutant": mutant,
        "touched": [],
        "refused": [],
        "applied": True,
        "imports": True,
        "collected": True,
        "tests": 3,
        "status": 0,
        "failures": [],
        "uncollected": [],
        "message": "",
    }
    return found | facts


def kept(directory: Path, *records: object) -> Path:
    for index, each in enumerate(records):
        where = directory / "records" / f"record-{index}"
        where.mkdir(parents=True)
        (where / mutant_runs.RECORD).write_text(json.dumps(each), encoding="utf-8")
    return directory / "records"


REQUEST = Request(("a", "b"), ("tests",), "dev", "3.15", 7, ())


def test_a_table_passes_where_the_baseline_passed_and_every_mutant_was_killed(tmp_path: Path) -> None:
    records = kept(
        tmp_path, record(""), record("a", status=2, failures=FAILED), record("b", status=1, failures=FAILED)
    )
    text, rows, verdict, ok = mutant_runs.table(REQUEST, records, "success", 1, "f" * 40)
    assert ok, verdict
    assert [row.outcome for row in rows] == [SURVIVED, KILLED, KILLED]
    assert "2 of 2 mutants killed, 0 survived, 0 broken, 0 undecided" == verdict
    assert "| <code>a</code> | killed | <code>tests/test_x.py::test_y</code> |" in text
    assert "seed 7" in text
    assert "<code>ffffffffffff</code>" in text


@pytest.mark.parametrize(
    ("records", "result", "attempt", "problem"),
    [
        ([record(""), record("a", status=2, failures=FAILED)], "success", 1, "1 undecided"),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in ("a", "b", "b")]],
            "success",
            1,
            "1 undecided",
        ),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in ("a", "b", "c")]],
            "success",
            1,
            "problems with the records: 1",
        ),
        ([record(""), *[record(name, status=2, failures=FAILED) for name in "ab"]], "failure", 1, "ended in"),
        (
            [record(""), *[record(name, status=2, failures=FAILED) for name in "ab"]],
            "success",
            2,
            "attempt 2",
        ),
        (
            [
                record("", status=2, failures=FAILED),
                *[record(name, status=2, failures=FAILED) for name in "ab"],
            ],
            "success",
            1,
            "0 of 2 mutants killed, 0 survived, 0 broken, 2 undecided; the baseline did not pass",
        ),
        (
            [record(""), record("a", status=True), record("b", status=2, failures=FAILED)],
            "success",
            1,
            "problems",
        ),
        ([record(""), record("a", failures=[{"test": 1}]), record("b")], "success", 1, "problems"),
        (
            [record(""), record("a", status=2, failures=[FAILED[0] | {"line": "7"}]), record("b")],
            "success",
            1,
            "problems",
        ),
        ([record(""), record("a", uncollected=[{"test": "gw0"}]), record("b")], "success", 1, "problems"),
        ([record(""), record("a", touched=[1]), record("b")], "success", 1, "problems"),
        ([record(""), {"mutant": "a"}, record("b")], "success", 1, "problems"),
        ([record(""), record("a", outcome="killed"), record("b")], "success", 1, "problems"),
    ],
    ids=[
        "a-record-missing",
        "two-records",
        "a-record-of-another",
        "a-job-failed",
        "a-second-attempt",
        "the-baseline-failed",
        "a-bool-for-a-status",
        "a-failure-of-another-shape",
        "a-failure-with-another-key",
        "an-uncollected-entry-of-another-shape",
        "a-touched-path-of-another-type",
        "fields-missing",
        "an-outcome-written-in",
    ],
)
def test_a_table_fails_unless_every_record_is_there_once_and_every_mutant_killed(
    tmp_path: Path, records: list[object], result: str, attempt: int, problem: str
) -> None:
    text, _, verdict, ok = mutant_runs.table(REQUEST, kept(tmp_path, *records), result, attempt)
    assert not ok
    assert problem in verdict, verdict
    assert verdict in text


@pytest.mark.parametrize(
    ("touched", "marked"),
    [
        (["src/materica/a.py"], []),
        (["src/materica/a.py", "tests/unit/test_a.py"], ["tests/unit/test_a.py"]),
        (["conftest.py"], ["conftest.py"]),
        (["tests/conftest.py"], ["tests/conftest.py"]),
        (["pytest.ini", ".pytest.ini"], ["pytest.ini", ".pytest.ini"]),
        (["tests/pyproject.toml", "tests/tox.ini"], ["tests/pyproject.toml", "tests/tox.ini"]),
        (["setup.cfg"], ["setup.cfg"]),
        (["src/sitecustomize.py", "src/usercustomize.py"], ["src/sitecustomize.py", "src/usercustomize.py"]),
        (["scripts/other.py", "src/materica/tests.py"], []),
    ],
)
def test_each_row_gives_what_its_patch_touched_and_a_kill_by_an_edit_of_the_tests_is_marked(
    tmp_path: Path, touched: list[str], marked: list[str]
) -> None:
    """#46's review, M2: a kill by a patch that edits the tests, a conftest, pytest's configuration or
    Python's startup hooks may be the edit's doing, so the row and the verdict say so; the paths every patch
    touched are in its row. A mutant that is not killed is not marked, whatever it touched."""
    records = kept(
        tmp_path,
        record(""),
        record("a", status=2, failures=FAILED, touched=touched),
        record("b", touched=touched),
    )
    text, rows, verdict, _ = mutant_runs.table(REQUEST, records, "success")
    assert [rows[1].touched, rows[1].marked, rows[2].marked] == [tuple(touched), tuple(marked), ()]
    assert (
        "1 of the kills by a patch that edits the tests or pytest's settings (marked)" in verdict
    ) == bool(marked), verdict
    assert ("**marked**" in text) == bool(marked)
    assert all(text.count(mutant_runs.code(path)) >= 2 for path in marked), text
    assert all(mutant_runs.code(path) in text for path in touched)


def test_the_mark_check_can_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: with no file counted among the tests' settings, a kill by a patch that edits a conftest
    is not marked."""
    monkeypatch.setattr(mutant_runs, "TEST_SETTINGS", ())
    records = kept(tmp_path, record(""), record("a", status=2, failures=FAILED, touched=["conftest.py"]))
    _, rows, verdict, _ = mutant_runs.table(
        Request(("a",), ("tests",), "dev", "3.15", 7, ()), records, "success"
    )
    assert (rows[1].marked, "(marked)" in verdict) == ((), False)


def test_the_replay_runs_the_dispatchs_selection_under_its_seed(tmp_path: Path) -> None:
    """#46's review, L1: a run of the failed test alone loads fewer modules and may draw other examples
    (`tests/property/audits.py`, `replay`), so the table replays the selection the dispatch ran."""
    request = Request(
        ("a",), ("tests/unit", "tests/property/test_x.py"), "ci", "3.15", 9, ("--shard=records",)
    )
    text, *_ = mutant_runs.table(request, kept(tmp_path, record(""), record("a")), "success")
    assert (
        "<code>git apply mutants/&lt;name&gt;.patch &amp;&amp; MATERICA_HYPOTHESIS_PROFILE=ci uv run pytest "
        "-x tests/unit tests/property/test_x.py --shard=records --hypothesis-seed=9</code>"
    ) in text, text
    assert "may draw other examples under the same seed" in text


def test_a_table_escapes_what_a_record_says() -> None:
    assert mutant_runs.cell("a | <b>") == "a &#124; &lt;b&gt;"
    assert mutant_runs.code("x|y") == "<code>x&#124;y</code>"


def test_each_failed_test_is_read_from_the_report_in_its_order(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_x" name="test_ok" file="tests/test_x.py"/>'
        '<testcase classname="tests.test_x.TestC" name="test_b" file="tests/test_x.py">'
        '<failure message="first line&#10;second">t</failure></testcase>'
        '<testcase classname="tests.test_x" name="test_a" file="tests/test_x.py"><error message="e">t</error>'
        "</testcase><testcase time='1.0'/></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert mutant_runs.reported_failures(report) == [
        {"test": "tests/test_x.py::TestC::test_b", "message": "first line"},
        {"test": "tests/test_x.py::test_a", "message": "e"},
    ]
    assert mutant_runs.reported_failures(tmp_path / "missing.xml") == []


# Entries of the JUnit reports pytest-xdist wrote for #46's review (H3), trimmed: a module that did not
# collect on one worker (`gw1`); workers that collected different tests, from a set's order, which string
# hashing makes each process's own; and a worker that crashed in a collected test.
XDIST_REPORT = (
    "<testsuites><testsuite>"
    '<testcase classname="" name="tests.test_half" file="tests/test_half.py" time="0.000">'
    '<error message="collection failure">RuntimeError: collection fails on gw1 alone</error></testcase>'
    '<testcase classname="" name="gw0" file="gw0" time="0.000"><error message="collection failure">'
    "Different tests were collected between gw1 and gw0.</error></testcase>"
    '<testcase classname="tests.test_half" name="test_n[3]" file="tests/test_half.py" time="0.000">'
    "<error message=\"failed on setup with &quot;worker 'gw2' crashed while running "
    "'tests/test_half.py::test_n[3]'&quot;\">crashed</error></testcase>"
    "</testsuite></testsuites>"
)
COLLECTED = {"tests/test_half.py::test_n[3]", "tests/test_half.py::test_case[a]"}


def test_only_a_collected_test_fails_and_kills(tmp_path: Path) -> None:
    """A module or a worker named in the report, a collected test's id given xdist's collection message, and
    an id the collect step did not list, whatever its message, are no collected test's failure, which leaves
    the mutant broken: the reviewer's two cases, the module that does not
    collect on one worker (status 2) and the workers that collected different tests (status 1). A crash in a
    collected test kills."""
    report = tmp_path / "report.xml"
    report.write_text(XDIST_REPORT, encoding="utf-8")
    module, worker, crash = mutant_runs.reported_failures(report)
    assert (module["test"], worker["test"]) == ("tests/test_half.py::tests.test_half", "gw0::gw0")
    assert mutant_runs.split_failures([module, worker, crash], COLLECTED) == ([crash], [module, worker])
    given = {"test": "tests/test_half.py::test_n[3]", "message": mutant_runs.COLLECTION_FAILURE}
    assert mutant_runs.split_failures([given], COLLECTED) == ([], [given])
    elsewhere = {"test": "tests/test_other.py::test_gone", "message": "assert 1 == 2"}
    assert mutant_runs.split_failures([elsewhere], COLLECTED) == ([], [elsewhere])
    for status, entry in ((2, module), (1, worker)):
        tests, others = mutant_runs.split_failures([entry], COLLECTED)
        found = mutant_runs.verdict(record("m", status=status, failures=tests, uncollected=others))
        assert found[0] == BROKEN, found
        assert found[1].startswith("the selection does not collect under pytest-xdist: "), found
    tests, others = mutant_runs.split_failures([crash], COLLECTED)
    found = mutant_runs.verdict(record("m", status=1, failures=tests, uncollected=others))
    assert found == (KILLED, "tests/test_half.py::test_n[3]")


def test_the_split_check_can_fail(tmp_path: Path) -> None:
    """The control: every entry the report names taken for a test's failure, as before #46's review, gives
    the reviewer's two cases as killed, by a module and by a worker."""
    report = tmp_path / "report.xml"
    report.write_text(XDIST_REPORT, encoding="utf-8")
    module, worker, _ = mutant_runs.reported_failures(report)
    found = [mutant_runs.verdict(record("m", status=2, failures=[entry])) for entry in (module, worker)]
    assert found == [(KILLED, "tests/test_half.py::tests.test_half"), (KILLED, "gw0::gw0")]


README = Path(__file__).resolve().parents[1] / "README.md"
# The line of tests/README.md's recipe that writes a mutant's patch and restores the tree for the next.
RECIPE_START = "git diff > mutants/m01.patch"


def recipe_problems(line: str, root: Path) -> list[str]:
    """Where `line`, run as written in the throwaway repository at `root` after each of two mutants, the first
    of which adds a source file and a test (`git add -N`, as the recipe says), leaves the tree unclean, or
    lets the first mutant's files into the second patch (#46's review, M1)."""
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (root / "tests" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "t"], check=True)
    (root / "mutants").mkdir()
    (root / "src" / "a.py").write_text("A = 2\n", encoding="utf-8")
    (root / "src" / "new.py").write_text("B = 1\n", encoding="utf-8")
    (root / "tests" / "test_new.py").write_text("def test_new():\n    assert False\n", encoding="utf-8")
    subprocess.run(["git", "add", "-N", "src/new.py", "tests/test_new.py"], check=True)
    subprocess.run(["bash", "-c", line], check=True)
    (root / "src" / "a.py").write_text("A = 3\n", encoding="utf-8")
    subprocess.run(["bash", "-c", line.replace("m01", "m02")], check=True)
    problems: list[str] = []
    for name, wanted in (("m01", ["src/a.py", "src/new.py", "tests/test_new.py"]), ("m02", ["src/a.py"])):
        patch = (root / "mutants" / f"{name}.patch").read_text(encoding="utf-8")
        found = sorted(line.split(" b/")[-1] for line in patch.splitlines() if line.startswith("diff --git "))
        if found != wanted:
            problems.append(f"the patch {name} holds {found}, not {wanted}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout
    if status != "?? mutants/\n":
        problems.append(f"the tree is left as {status!r}")
    return problems


def test_the_readmes_recipe_leaves_the_tree_clean_for_the_next_mutant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = [line.strip() for line in README.read_text(encoding="utf-8").splitlines()]
    (line,) = [line for line in lines if line.startswith(RECIPE_START)]
    assert recipe_problems(line, throwaway_repository(tmp_path, monkeypatch)) == []


def test_the_recipe_check_can_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: the recipe before #46's review, which leaves a file added with `git add -N` in the index
    and the tree, lets it into the next patch."""
    old = f"{RECIPE_START} && git checkout -- src tests"
    found = recipe_problems(old, throwaway_repository(tmp_path, monkeypatch))
    assert any(
        "the patch m02 holds ['src/a.py', 'src/new.py', 'tests/test_new.py']" in line for line in found
    )


def imported_in_a_fresh_process(root: Path, *paths: str) -> list[str]:
    """`import_problems` run as the job runs it: in a fresh Python, the checkout's `src/` on its path."""
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1] + '/src'); "
        f"sys.path.insert(0, {str(Path(mutant_runs.__file__).parent)!r}); import mutant_runs; "
        "print('\\n'.join(mutant_runs.import_problems(Path(sys.argv[1]), sys.argv[2:])))"
    )
    ran = subprocess.run(
        [sys.executable, "-I", "-c", script, str(root), *paths], capture_output=True, text=True, check=True
    )
    return [line for line in ran.stdout.splitlines() if line]


def test_a_module_that_does_not_compile_or_import_is_found(tmp_path: Path) -> None:
    package = tmp_path / "src" / "materica"
    (package / "core").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core" / "__init__.py").write_text("", encoding="utf-8")
    (package / "core" / "good.py").write_text("X = 1\n", encoding="utf-8")
    assert imported_in_a_fresh_process(tmp_path) == []
    (package / "core" / "bad.py").write_text("raise RuntimeError('at import')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_z.py").write_text("def f(:\n", encoding="utf-8")
    problems = imported_in_a_fresh_process(tmp_path, "tests/test_z.py", "tests/gone.py", "notes.md")
    assert len(problems) == 2, problems
    assert problems[0].startswith("tests/test_z.py does not compile: "), problems
    assert problems[1] == "materica.core.bad does not import: RuntimeError: at import", problems


def test_a_package_imported_from_elsewhere_is_found(tmp_path: Path) -> None:
    """The control of the walk above: a module of the checkout's that another copy of the package gives."""
    elsewhere = tmp_path / "elsewhere" / "src" / "materica"
    elsewhere.mkdir(parents=True)
    (elsewhere / "__init__.py").write_text("", encoding="utf-8")
    checkout = tmp_path / "checkout" / "src" / "materica"
    checkout.mkdir(parents=True)
    (checkout / "__init__.py").write_text("", encoding="utf-8")
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[2] + '/src'); "
        f"sys.path.insert(0, {str(Path(mutant_runs.__file__).parent)!r}); import mutant_runs; "
        "print('\\n'.join(mutant_runs.import_problems(Path(sys.argv[1]), [])))"
    )
    ran = subprocess.run(
        [sys.executable, "-I", "-c", script, str(checkout.parents[1]), str(elsewhere.parents[1])],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "materica is imported from" in ran.stdout
    assert "not from the checkout" in ran.stdout
