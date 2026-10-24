# SPDX-License-Identifier: Apache-2.0
"""The claims check flags a stale git fact, a figure no fact records and a ruled sentence reworded, and passes
each correct form, in a throwaway repository with a rulings file written for the tests."""

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import check_claims, pre_review
from tests.unit.throwaway_git import throwaway_repository

SPECIFICATION = "docs/specification/read_side_contract.md"
RULING = (
    "an over-range or kept entry holds its unit, specimen, statistics and provenance as `record_format.md` "
    "section 5 gives them"
)
ROW = (
    "| `alternative_values` | An entry whose alternative is kept outside its form's range holds its `unit`, "
    "`specimen`, `statistics` and `provenance`{} as `record_format.md` section 5 gives them. [PR-013] |\n"
)
IDENTITY = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
REASONS = {"measured": "a measured figure", "setting": "a setting"}


def commit(message: str, files: dict[str, str] | None = None) -> str:
    for name, text in (files or {}).items():
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        Path(name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "--all"], check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "--allow-empty", "-m", message], check=True)
    return check_claims.git("rev-parse", "HEAD").strip()


def baseline(at: str, entries: Sequence[Sequence[object]] = ()) -> None:
    stored = {"about": "", "at": at, "reasons": REASONS, "changelog": [list(entry) for entry in entries]}
    check_claims.BASELINE.write_text(json.dumps(stored), encoding="utf-8")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository on its first commit, with an empty baseline at it and an empty facts file."""
    root = tmp_path / "repository"
    root.mkdir()
    throwaway_repository(root, monkeypatch)
    (tmp_path / "facts.json").write_text('{"facts": []}', encoding="utf-8")
    monkeypatch.setattr(check_claims, "BASELINE", tmp_path / "baseline.json")
    changelog = "# Changelog\n\n- Older: 12 tests.\n"
    baseline(commit("docs: on main", {"CHANGELOG.md": changelog, SPECIFICATION: "| member | text |\n"}))
    return root


def run(capsys: pytest.CaptureFixture[str], base: str, *arguments: str) -> tuple[int, list[str]]:
    """The check's status and its findings, without the summary lines."""
    facts = str(Path.cwd().parent / "facts.json")
    status = check_claims.main(["check", base, "--facts", facts, *arguments])
    lines = capsys.readouterr().out.splitlines()
    summary = ("figures:", "the ruled", "measured before the head:", "accepted by the rulings file:")
    return status, [line for line in lines if ": " in line and not line.startswith(summary)]


def test_the_script_runs_as_a_file_in_isolated_mode() -> None:
    script = Path(check_claims.__file__)
    done = subprocess.run([sys.executable, "-I", str(script), "--help"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_a_stale_head_base_or_count_is_flagged_and_the_true_ones_pass(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\nb\n"})
    old = commit("feat: two", {"b.txt": "c\n"})
    description = repository.parent / "description.md"
    text = (
        f"Draft, head `{old[:8]}`, 2 commits on `main` at `{base[:8]}`.\n\nTwo commits, each signed off.\n\n"
        "2 files changed, 3 insertions(+)\n\n"
        "| Part | Added | Removed |\n|---|---|---|\n| a.txt | 2 | 0 |\n| b.txt | 1 | 0 |\n"
        "| total, 2 files | 3 | 0 |\n"
    )
    description.write_text(text, encoding="utf-8")
    assert run(capsys, base, "--description", str(description)) == (0, [])
    head = commit("fix: three", {"a.txt": "a\n"})
    status, found = run(capsys, base, "--description", str(description))
    assert status == 1
    assert [line.partition(": ")[2] for line in found] == [
        f"the head is `{head[:8]}`, not `{old[:8]}`",
        "2 commits, where git counts 3",
        "Two commits, where git counts 3",
        "3 added, where git counts 2",
        "3 added, where git counts 2",
    ]
    description.write_text(
        f"On `main` at `{base[:8]}`, rebased onto `main` at `{old[:8]}`; see `0123abcd`.\n\n"
        f'Quoted, not read: "the head is `{base[:8]}`. Nine commits, each signed off."\n\n'
        "| Part | Files | Added | Removed |\n|---|---|---|---|\n"
        "| a.txt | 1 | 1 | 1 |\n| b.txt | 2 | 1 | 0 |\n"
    )
    status, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        "`0123abcd` names no commit here",
        f"the base is `{base[:8]}`, not `{old[:8]}`",
        "1 removed, where git counts 0",
        "3 files, where git counts 2",
    ]


HEAD = "52d25837" + "0" * 32
BASE = "1c42af03" + "0" * 32
STALE = "35f50802" + "0" * 32


@pytest.fixture
def known_commits(monkeypatch: pytest.MonkeyPatch) -> check_claims.Range:
    """Git stood in for: three commits, each on the branch, and the branch's counts."""

    def resolve(name: str) -> str | None:
        return next((full for full in (HEAD, BASE, STALE) if full.startswith(name)), None)

    def counts(base: str, head: str) -> dict[str, int]:
        return dict.fromkeys(("commits", "files"), 7)

    def holds(commit: str, head: str) -> bool:
        return True

    def ambiguous(name: str) -> bool:
        return False

    monkeypatch.setattr(check_claims, "resolve", resolve)
    monkeypatch.setattr(check_claims, "ambiguous", ambiguous)
    monkeypatch.setattr(check_claims, "is_ancestor", holds)
    monkeypatch.setattr(check_claims, "counts", counts)
    return check_claims.Range(BASE, HEAD, BASE)


@pytest.mark.parametrize(
    ("text", "which"),
    [
        ("Head `{}`, 7 commits.", "head"),
        ("- Head `{}`, 7 commits.", "head"),
        ("All checks ran at head `{}`.", "head"),
        ("**Head:** `{}`.", "head"),
        ("Head: `{}`.", "head"),
        ("The head is now `{}`.", "head"),
        ("The head is `{}`.", "head"),
        ("Its head at `{}` passes.", "head"),
        ("The new head `{}`.", "head"),
        ("The head (`{}`) passes.", "head"),
        (f"Merge base `{BASE[:8]}`, head `{{}}`.", "head"),
        ("The branch sits on `main`'s `{}`.", "base"),
        ("The base is `{}`.", "base"),
        ("Seven commits on `main`'s `{}`.", "base"),
        ("Stacked on `main` at `{}`.", "base"),
    ],
)
def test_a_head_or_base_is_read_in_the_forms_the_docstring_names(
    text: str, which: str, known_commits: check_claims.Range
) -> None:
    right = HEAD if which == "head" else BASE
    assert check_claims.git_findings(text.format(right[:8]), "d", known_commits) == []
    assert check_claims.git_findings(text.format(STALE[:8]), "d", known_commits) == [
        f"d:1: the {which} is `{right[:8]}`, not `{STALE[:8]}`"
    ]


@pytest.mark.parametrize(
    "text",
    [
        "The earlier head `{}` passed too.",
        "#77's head `{}` is another pull request's.",
        "the review's head `{}` held the old reader.",
        "It passed on the old\nhead `{}` as well.",
        "The previous base `{}` is gone.",
    ],
)
def test_a_head_or_base_named_as_another_is_not_read(text: str, known_commits: check_claims.Range) -> None:
    assert check_claims.git_findings(text.format(STALE[:8]), "d", known_commits) == []


@pytest.mark.parametrize(
    ("text", "stated", "count"),
    [
        ("Seven commits: the schema; the reader.", "Seven", 7),
        ("- [x] One commit, signed off", "One", 1),
        ("Twenty-two commits, each passing alone.", "Twenty-two", 22),
        ("Thirty-one commits, each passing alone.", "Thirty-one", 31),
        ("Each of the 1,012 commits, exported.", "1,012", 1012),
        ("Four commits on the branch now.", "Four", 4),
        ("21 commits on `origin/main` `e1647082`.", "21", 21),
        ("This branch has 8 commits on top of `main`.", "8", 8),
        ("The same 14 commits in the same order, now on #36.", "14", 14),
        ("Rebased (8 commits) onto the new main.", "8", 8),
        ("The last two commits fix it; the first nine commits pass.", None, 0),
        ("The two commits after it change only a README.", None, 0),
        ("76 commits of `main` lie underneath.", None, 0),
        ("More than 256 commits fail the gate.", None, 0),
        ("A name must now be one commit on the branch or on main.", None, 0),
    ],
)
def test_a_commit_count_is_checked_in_its_forms_and_a_partial_count_is_not(
    text: str, stated: str | None, count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "e1647082" + "0" * 32
    for counted in (count, count + 1):

        def counts(base: str, head: str, counted: int = counted) -> dict[str, int]:
            return dict.fromkeys(("commits", "files"), counted)

        def resolve(name: str) -> str:
            return base

        monkeypatch.setattr(check_claims, "counts", counts)
        monkeypatch.setattr(check_claims, "resolve", resolve)
        found = check_claims.git_findings(text, "d", check_claims.Range(base, "f" * 40))
        stale = stated and counted != count
        assert found == ([f"d:1: {stated} commits, where git counts {counted}"] if stale else [])


def short(name: str) -> str:
    """The shortest name of 7 hexadecimal digits or more with a letter and a digit, as the check reads."""
    return next(
        name[:size]
        for size in range(7, 40)
        if len(set(name[:size]) & set("abcdef")) and len(set(name[:size]) - set("abcdef"))
    )


def test_a_commit_name_is_one_commit_on_the_branch_or_main_unless_its_sentence_names_a_pull_request(
    repository: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    base = short(check_claims.git("rev-parse", "HEAD").strip())
    blob = short(check_claims.git("rev-parse", "HEAD:CHANGELOG.md").strip())
    commit("feat: one", {"a.txt": "a\n"})
    elsewhere = short(check_claims.git(*IDENTITY, "commit-tree", "HEAD^{tree}", "-m", "elsewhere").strip())
    description = repository.parent / "description.md"
    description.write_text(
        f"The file's content is `{blob}`.\n\nIts reader was fixed at `{elsewhere}`.\n\n"
        f"Rebased from #12, whose reader was at `{elsewhere}`.\n\nOn `main` at `{base}`.\n",
        encoding="utf-8",
    )
    _, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        f"`{blob}` names no commit here",
        f"`{elsewhere}` is not on this branch or main",
    ]

    upstream = check_claims.git(
        *IDENTITY, "commit-tree", f"{base}^{{tree}}", "-p", base, "-m", "on main"
    ).strip()
    description.write_text(f"Main's newer reader is at `{short(upstream)}`.\n", encoding="utf-8")
    assert run(capsys, upstream, "--description", str(description)) == (0, [])

    def ambiguous(name: str) -> bool:
        return name == base

    monkeypatch.setattr(check_claims, "ambiguous", ambiguous)
    description.write_text(f"On `main` at `{base}`.\n", encoding="utf-8")
    _, found = run(capsys, base, "--description", str(description))
    assert f"description.md:1: `{base}` names more than one object here" in [
        line.rpartition("/")[2] for line in found
    ]


def test_a_short_name_two_objects_share_is_ambiguous(repository: Path) -> None:
    for content in ("195\n", "389\n"):  # two blobs whose names both open 6bb2
        subprocess.run(["git", "hash-object", "-w", "--stdin"], input=content, text=True, check=True)
    assert check_claims.ambiguous("6bb2")
    assert not check_claims.ambiguous("6bb2f4e")


def test_the_branch_s_commit_messages_are_held_to_git(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\n"})
    second = commit(f"feat: two\n\nTwo commits on `main` at `{base[:8]}`.", {"b.txt": "b\n"})
    assert run(capsys, base) == (0, [])
    third = commit(f"fix: three\n\nThe head is now `{second[:8]}`.", {"a.txt": "b\n"})
    status, found = run(capsys, base)
    assert status == 1
    assert found == [
        f"commit {third[:8]}, message:3: the head is `{third[:8]}`, not `{second[:8]}`",
        f"commit {second[:8]}, message:3: Two commits, where git counts 3",
    ]


def test_a_table_of_one_total_row_and_git_s_deletions_are_read(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = commit("docs: the file", {"a.txt": "a\nb\nc\n"})
    commit("fix: one line less", {"a.txt": "a\nb\n"})
    description = repository.parent / "description.md"
    for removed, status in ((1, 0), (2, 1)):
        description.write_text(
            f"1 file changed, {removed} deletion(-)\n\n"
            f"| Part | Files | Added | Removed |\n|---|---|---|---|\n| total, 1 file | 1 | 0 | {removed} |\n",
            encoding="utf-8",
        )
        found = run(capsys, base, "--description", str(description))
        assert found[0] == status
        assert [line.partition(": ")[2] for line in found[1]] == [
            f"{removed} removed, where git counts 1"
        ] * (2 * status)


def test_a_line_table_s_total_row_names_its_files_where_it_has_no_files_column(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = commit("docs: the file", {"a.txt": "a\n"})
    commit("fix: one line more", {"a.txt": "a\nb\n"})
    description = repository.parent / "description.md"
    for files, stale in ((1, []), (2, ["2 files, where git counts 1"])):
        description.write_text(
            f"| Part | Added | Removed |\n|---|---|---|\n| total, {files} files | 1 | 0 |\n", encoding="utf-8"
        )
        _, found = run(capsys, base, "--description", str(description))
        assert [line.partition(": ")[2] for line in found] == stale


def test_git_s_own_shortstat_of_a_rename_passes(repository: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = commit("docs: a file", {"a.txt": "".join(f"line {n}\n" for n in range(5))})
    subprocess.run(["git", "mv", "a.txt", "b.txt"], check=True)
    commit("refactor: renamed")
    description = repository.parent / "description.md"
    description.write_text(check_claims.git("diff", "--shortstat", "-M", base, "HEAD"), encoding="utf-8")
    assert "1 file changed" in description.read_text(encoding="utf-8")
    assert run(capsys, base, "--description", str(description)) == (0, [])


@pytest.mark.parametrize(
    "text",
    [
        "section 4.1 and steps 8 to 13, items 1, 2 and 4",
        "on Python 3.11 and 3.15; `pytest -n 8`, -n 12 and `1723 passed` in code",
        "BC-048, HP13, S7a-2, PR-339 and #77, U+2212 and the 500th example",
        "on 2026-10-23 at 10:24, in run 39404674681 (Marcinkowska-Gapinska 2013), and in 2026 (2013)",
        '(1) the first; "1180 of 1522 case files" as quoted; the interval [275, 283]',
        "at 37 °C, at the one-sided 95 % bound, about 45 s, ~3 runs and 55 minutes by estimate",
        "Its checks: (1) the reader; (2) the writer, with items 0 and 3",
        "fuzz target 4 reads it, and seed 2 draws it",
    ],
)
def test_a_number_of_a_kind_that_is_no_measurement_needs_no_fact(text: str) -> None:
    assert check_claims.figures(text)[0] == []


@pytest.mark.parametrize(
    ("text", "stated"),
    [
        ("the fast stage, 15 of 15 ok", ["15", "15"]),
        ("In section 2: 1,180 of 1,522", ["1,180", "1,522"]),
        ("143 measured figures and 6 settings", ["143", "6"]),
        ("The site checker's tests pass (71).", ["71"]),
        ("Unused acceptances: BC-001 (3), BC-002 (5).", ["3", "5"]),
        ("- 24 case files now pass at the head.", ["24"]),
        ("The new shard - 41 tests - passes alone.", ["41"]),
        ("The set-up time of a job (6 to 8 s) is the same.", ["6", "8"]),
        ("Timeouts: `writer` 180 (slowest part 67.4), `json` 55 (23.9).", ["180", "67.4", "55", "23.9"]),
        ("The shard 0.72 to 0.79 of its CPU at the head.", ["0.72", "0.79"]),
        ("Its CPU time was 25% lower than the old rule's.", ["25%"]),
        ("The kill share sits 3 % upper of the floor.", ["3"]),
        ("The job took 38 minutes, against the 45 estimated.", ["38"]),
        ("The reader is about the 1,180 case files that pass.", ["1,180"]),
        ("Of 2000 runs, 1995 found the fault.", ["2000", "1995"]),
        ("the rate's 0.031 upper bound", ["0.031"]),
        ("The suite ran 2010 tests.", ["2010"]),
        ("The model drifts by 0.4 per K.", ["0.4"]),
        ("It drew 1234567 examples.", ["1234567"]),
        ("Its slowest part `writer` 67 s at the head.", ["67"]),
        ("Its slowest part `writer`\n67 s at the head.", ["67"]),
        ("The set-up took 6 s, where it estimated less.", ["6"]),
        ("So a push's head runs 30 jobs at once where it ran 18.", ["30", "18"]),
        ("The suite can run 3266 tests in 4 minutes.", ["3266", "4"]),
    ],
)
def test_a_number_a_numbering_word_does_not_reach_needs_a_fact(text: str, stated: list[str]) -> None:
    assert [figure.text for figure in check_claims.figures(text)[0]] == stated


def test_a_figure_needs_a_recorded_fact_measured_at_a_commit_the_head_holds(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\n"})
    description = repository.parent / "description.md"
    description.write_text(
        "In section 2: 1,180 of 1,522 case files pass; 35 are verified.\n", encoding="utf-8"
    )
    facts = ["--facts", str(repository.parent / "facts.json")]
    status, found = run(capsys, base, "--description", str(description))
    assert status == 1
    stated = ("1,180 (of 1522 case files ...)", "1,522 (case files pass 35 ...)", "35 (are verified ...)")
    assert [line.partition(": ")[2] for line in found] == [
        f"{figure} matches no recorded fact" for figure in stated
    ]
    how = ["--how", "pytest tests/conformance -q", *facts]
    recorded = [
        ("1180", "of 1,522 case files pass"),
        ("1,522", "case files"),
        ("34", "are verified"),
        ("35", "seeds"),
    ]
    for value, what in recorded:
        assert check_claims.main(["record", value, what, *how]) == 0
    assert run(capsys, base, "--description", str(description)) == (1, found[2:])
    assert check_claims.main(["record", "35", "are verified", *how]) == 0
    assert check_claims.main(["check", base, "--description", str(description), *facts]) == 0
    assert f"3 matched a fact of the 5 in {repository.parent / 'facts.json'}" in capsys.readouterr().out
    elsewhere = check_claims.git(*IDENTITY, "commit-tree", "HEAD^{tree}", "-m", "elsewhere").strip()
    stored = json.loads((repository.parent / "facts.json").read_text(encoding="utf-8"))
    stored["facts"][4]["at"] = elsewhere
    (repository.parent / "facts.json").write_text(json.dumps(stored), encoding="utf-8")
    status, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        "35 (are verified ...) was measured at a commit the head does not hold"
    ]
    assert check_claims.main(["record", "many", "tests", "--how", "counted", *facts]) == 2
    assert check_claims.main(["record", "3", "tests", "--how", " ", *facts]) == 2


def test_a_fact_s_words_start_in_its_figure_s_own_phrase(repository: Path) -> None:
    head = check_claims.git("rev-parse", "HEAD").strip()
    span = check_claims.Range(head, head, head)

    def fact(value: str, what: str) -> check_claims.Fact:
        return check_claims.Fact(check_claims.decimal(value), tuple(what.split()), head)

    text = "35 tests pass, in 12 files; 35 of the tests pass.\n"
    found, tally, _ = check_claims.figure_findings(
        text, "d", span, [fact("35", "files"), fact("12", "files")]
    )
    assert found == [
        "d:1: 35 (tests pass in 12 ...) matches no recorded fact",
        "d:1: 35 (of the tests pass ...) matches no recorded fact",
    ]
    found, tally, _ = check_claims.figure_findings(
        text, "d", span, [fact("35", "tests pass"), fact("12", "files")]
    )
    assert (found, tally["matched"]) == ([], 3)


def test_a_fact_s_words_start_within_the_eight_words_after_its_figure(repository: Path) -> None:
    head = check_claims.git("rev-parse", "HEAD").strip()
    span = check_claims.Range(head, head, head)
    fact = check_claims.Fact(check_claims.decimal("41"), ("tests",), head)
    found, tally, _ = check_claims.figure_findings("41 a b c d e f g tests pass.\n", "d", span, [fact])
    assert (found, tally["matched"]) == ([], 1)
    found, _, _ = check_claims.figure_findings("41 a b c d e f g h tests pass.\n", "d", span, [fact])
    assert found == ["d:1: 41 (a b c d ...) matches no recorded fact"]


def test_a_fact_is_recorded_in_the_git_directory_by_default_and_the_tree_stays_clean(
    repository: Path,
) -> None:
    assert check_claims.main(["record", "3", "tests pass", "--how", "pytest -q"]) == 0
    stored = Path(check_claims.git("rev-parse", "--git-path", check_claims.FACTS_NAME).strip())
    assert json.loads(stored.read_text(encoding="utf-8"))["facts"][0]["value"] == "3"
    assert check_claims.git("status", "--porcelain") == ""


def measured_before(repository: Path) -> tuple[str, str, Path, list[str]]:
    """A branch with a fact recorded at its first commit: its base, that commit, its description and facts."""
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.py": "x = 1\n"})
    description = repository.parent / "description.md"
    description.write_text("The suite: 41 tests pass.\n", encoding="utf-8")
    facts = ["--facts", str(repository.parent / "facts.json")]
    assert check_claims.main(["record", "41", "tests pass", "--how", "pytest -q", *facts]) == 0
    return base, check_claims.git("rev-parse", "HEAD").strip(), description, facts


@pytest.mark.parametrize(
    ("path", "prose"),
    [
        ("CHANGELOG.md", True),
        ("notes/README.md", True),  # a README no test reads
        ("docs/specification/record_format.md", False),
        ("tests/property/README.md", False),  # a README a test reads: the kill counts' table
        ("NOTES.md", False),  # Markdown that is neither a README nor documentation
        ("docs/make.cmd", False),  # documentation's place, but no Markdown
    ],
)
def test_a_fact_measured_before_the_head_holds_only_across_commits_that_change_prose_markdown_alone(
    path: str, prose: bool, repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base, measured, description, facts = measured_before(repository)
    commit("docs: a note", {path: "a note\n"})
    status = check_claims.main(["check", base, "--description", str(description), *facts])
    lines = capsys.readouterr().out.splitlines()
    about = f"{description}:1: 41 (tests pass ...) was measured at `{measured[:8]}`, 1 commits"
    if prose:
        assert status == 0
        assert (
            f"measured before the head: {about} before the head, which change prose Markdown alone" in lines
        )
    else:
        assert status == 1
        assert (
            f"{about} before the head, which change 1 files that are code or that a test reads: {path}"
            in lines
        )


def test_a_file_moved_to_a_prose_name_counts_by_both_its_names(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base, measured, description, _ = measured_before(repository)
    subprocess.run(["git", "mv", "a.py", "docs/a.md"], check=True)
    commit("docs: the module becomes a page")
    _, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        f"41 (tests pass ...) was measured at `{measured[:8]}`, 1 commits before the head, which change 1 "
        "files that are code or that a test reads: a.py"
    ]


def test_markdown_a_reader_table_names_is_code_and_the_specification_is_code_whatever_the_tables_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readme, read = "notes/README.md", "tests/property/README.md"
    assert check_claims.prose_markdown(readme)
    rule = pre_review.DataRule("a README a test reads", r"notes/README\.md", "a test reads it", ("tests",))
    monkeypatch.setattr(pre_review, "DATA_RULES", (*pre_review.DATA_RULES, rule))
    assert not check_claims.prose_markdown(readme)
    monkeypatch.setattr(pre_review, "DATA_RULES", ())
    assert check_claims.prose_markdown(read)
    assert not check_claims.prose_markdown(SPECIFICATION)


def test_a_changelog_figure_the_branch_adds_fails_unless_a_fact_or_the_baseline_holds_it(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = "- The runner: 1180 of 1573 case files pass, and the suite took 23.7 minutes.\n"
    base = commit("docs: the counts on main", {"CHANGELOG.md": f"# Changelog\n\n{line}- Older: 12 tests.\n"})
    text = "# Changelog\n\n- The runner: 1180 of 1573 case files pass,\n  and the suite took 23.7 minutes.\n"
    text += "- Older: 12 tests.\n"
    commit("docs: the counts rewrapped", {"CHANGELOG.md": text})
    status, found = run(capsys, base)
    assert status == 1
    assert [line.split(": ")[0] for line in found] == ["CHANGELOG.md:3", "CHANGELOG.md:3", "CHANGELOG.md:4"]
    keys = [figure.key() for figure in check_claims.figures(text)[0]]
    assert keys == [
        "the runner 1180 of 1573 case",
        "runner 1180 of 1573 case files pass",
        "the suite took 23.7 minutes",
        "older 12 tests",
    ]
    baseline(base, [[key, 3, "measured"] for key in keys[:2]])
    status, found = run(capsys, base)
    assert [line.split(": ")[0] for line in found] == ["CHANGELOG.md:4"]


def test_the_baseline_holds_no_description_figure_and_no_figure_added_more_often_than_it_was(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    older, newer = "- Older: 12 tests.\n", "- Newer: 3 runs, recorded where they were measured.\n"
    baseline(check_claims.git("rev-parse", "HEAD").strip(), [["older 12 tests", 3, "measured"]])
    base = commit("docs: a newer entry", {"CHANGELOG.md": "# Changelog\n\n" + newer + older})
    commit(
        "docs: the changelog moves",
        {"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n" + older + "\n## [Released]\n\n" + newer},
    )
    assert "+" + newer in check_claims.git("diff", base, "HEAD")
    assert run(capsys, base) == (0, [])  # nothing added: the lines moved whole
    description = repository.parent / "description.md"
    description.write_text("Older: 12 tests.\n", encoding="utf-8")
    commit(
        "docs: an entry copied",
        {"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n" + older + older + newer},
    )
    _, found = run(capsys, base, "--description", str(description))
    assert found[0].rpartition("/")[2] == "description.md:1: 12 (tests ...) matches no recorded fact"
    assert found[1:] in (  # either copy, as git's diff sees it
        [f"CHANGELOG.md:{line}: 12 (tests ...) matches no recorded fact"] for line in (5, 6)
    )


def test_the_baseline_holds_only_figures_of_the_changelog_at_its_commit_with_a_listed_reason(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    at = check_claims.git("rev-parse", "HEAD").strip()
    for entries, error in (
        ([["older 12 tests", 3, "measured"]], ""),
        ([["older 12 tests", 3, "measured"], ["a check of a branch claims that a", 15, "measured"]], "holds"),
        ([["older 12 tests", 4, "measured"]], "at line 4"),
        ([["older 12 tests", 3, "declared"]], "the reason 'declared'"),
    ):
        baseline(at, entries)
        assert check_claims.main(["check", at, "--facts", str(repository.parent / "facts.json")]) == (
            2 if error else 0
        )
        assert error in capsys.readouterr().err
    commit("docs: two figures", {"CHANGELOG.md": "# Changelog\n\n- Older: 12 tests.\n- Newer: 3 runs.\n"})
    baseline(check_claims.git("rev-parse", "HEAD").strip(), [["older 12 tests", 3, "declared"]])
    assert check_claims.main(["check", at, "--facts", str(repository.parent / "facts.json")]) == 2
    assert "is not on main here" in capsys.readouterr().err
    assert check_claims.main(["baseline", "--at", "HEAD"]) == 0
    stored = json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))
    assert stored["changelog"] == [["older 12 tests", 3, "declared"], ["newer 3 runs", 4, "unlabelled"]]


def test_the_committed_baseline_holds_each_figure_once_with_a_listed_reason() -> None:
    stored = json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))
    keys = [key for key, _, _ in stored["changelog"]]
    assert len(keys) == len(set(keys))
    assert {reason for _, _, reason in stored["changelog"]} == set(stored["reasons"])
    assert all(isinstance(line, int) and line > 0 for _, line, _ in stored["changelog"])


ADVISORY = "advisory figure finding: "


def advised(
    capsys: pytest.CaptureFixture[str], base: str, *arguments: str
) -> tuple[int, list[str], list[str]]:
    """The status of the check under `--figures-advisory`, its advisory figure findings and its other
    findings, without the summary lines."""
    facts = str(Path.cwd().parent / "facts.json")
    status = check_claims.main(["check", base, "--facts", facts, "--figures-advisory", *arguments])
    lines = capsys.readouterr().out.splitlines()
    summary = ("figures:", "the ruled", "measured before the head:", "accepted by the rulings file:", "no ")
    advisory = [line.removeprefix(ADVISORY) for line in lines if line.startswith(ADVISORY)]
    others = [line for line in lines if ": " in line and not line.startswith((*summary, ADVISORY))]
    return status, advisory, others


def test_a_figure_finding_is_printed_and_passes_under_the_option_and_fails_without_it(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\n"})
    description = repository.parent / "description.md"
    description.write_text("In section 2: 1,180 of 1,522 case files pass.\n", encoding="utf-8")
    status, found = run(capsys, base, "--description", str(description))
    assert status == 1
    assert len(found) == 2
    status, advisory, others = advised(capsys, base, "--description", str(description))
    assert (status, others) == (0, [])
    assert advisory == found
    facts = str(repository.parent / "facts.json")
    status = check_claims.main(
        ["check", base, "--facts", facts, "--figures-advisory", "--description", str(description)]
    )
    out = capsys.readouterr().out
    assert status == 0
    assert "no git fact or ruled wording found that git or the rulings contradict" in out
    assert "2 findings" not in out
    assert "0 findings, 2 advisory figure findings" in out


def test_the_output_without_the_option_names_no_advisory_finding(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\n"})
    description = repository.parent / "description.md"
    description.write_text("In section 2: 35 are verified.\n", encoding="utf-8")
    assert run(capsys, base, "--description", str(description))[0] == 1
    status = check_claims.main(
        ["check", base, "--facts", str(repository.parent / "facts.json"), "--description", str(description)]
    )
    out = capsys.readouterr().out
    assert status == 1
    assert "advisory" not in out
    assert "baseline; 1 findings\n" in out


def test_a_changelog_figure_is_advisory_under_the_option_too(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit(
        "docs: a count",
        {"CHANGELOG.md": "# Changelog\n\n- Older: 12 tests.\n- Newer: 1180 of 1573 files pass.\n"},
    )
    assert run(capsys, base)[0] == 1
    status, advisory, others = advised(capsys, base)
    assert (status, others) == (0, [])
    assert advisory
    assert all(line.startswith("CHANGELOG.md:4: ") for line in advisory)


def test_a_git_fact_still_fails_under_the_option_whatever_it_is_found_in(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one\n\nThe branch has 7 commits on top of main.", {"a.txt": "a\n"})
    head = commit("feat: two", {"b.txt": "b\n"})
    description = repository.parent / "description.md"
    description.write_text(f"Head `{base[:8]}`; 9 commits on `main`. Also 1,180 of 1,522 case files pass.\n")
    status, advisory, others = advised(capsys, base, "--description", str(description))
    assert status == 1
    assert [line.partition(": ")[2] for line in others] == [
        f"the head is `{head[:8]}`, not `{base[:8]}`",
        "9 commits, where git counts 2",
        "7 commits, where git counts 2",
    ]
    assert len(advisory) == 2
    # Each alone in the description, with no figure beside it, and the commit message's count beside it.
    for text, finding in (
        (f"The head is `{base[:8]}`.\n", f"the head is `{head[:8]}`, not `{base[:8]}`"),
        ("It has 9 commits on `main`.\n", "9 commits, where git counts 2"),
    ):
        description.write_text(text, encoding="utf-8")
        status, advisory, others = advised(capsys, base, "--description", str(description))
        assert (status, advisory) == (1, [])
        assert [line.partition(": ")[2] for line in others] == [finding, "7 commits, where git counts 2"]
    description.write_text("Nothing to find.\n", encoding="utf-8")
    commit("feat: three\n\nIts 8 commits on main.", {"c.txt": "c\n"})
    status, advisory, others = advised(capsys, base, "--description", str(description))
    assert (status, advisory) == (1, [])
    assert [line.partition(": ")[2] for line in others] == [
        "8 commits, where git counts 3",
        "7 commits, where git counts 3",
    ]


def test_a_ruled_wording_still_fails_under_the_option(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rulings = repository.parent / "rulings.md"
    rulings.write_text(f"- **A ruling** (maintainer: yes): {RULING}.\n", encoding="utf-8")
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("docs(specification): as first written", {SPECIFICATION: ROW.format(" as stored,")})
    status, advisory, others = advised(capsys, base, "--rulings", str(rulings))
    assert (status, advisory) == (1, [])
    assert len(others) == 1
    assert "a ruled sentence differs" in others[0]
    commit("docs(specification): in the ruling's words", {SPECIFICATION: ROW.format("")})
    assert advised(capsys, base, "--rulings", str(rulings)) == (0, [], [])


def test_the_committed_baseline_holds_only_figures_of_the_changelog_at_its_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(check_claims.BASELINE.parent.parent)
    at = json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))["at"]
    if check_claims.resolve(at) is None:
        pytest.skip(
            f"a shallow clone holds no {at[:8]}: CI's test jobs check out at depth 1, so this guard runs "
            "only where the history is (an open point for CI); the check refuses a grown baseline on each run"
        )
    held = check_claims.load_baseline(check_claims.Range(at, at, at))
    assert len(held) == len(json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))["changelog"])


@pytest.mark.parametrize("added", [" as stored,", " stored"])
def test_a_ruled_sentence_with_words_added_is_flagged_with_both_forms_and_the_ruled_words_pass(
    added: str, repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rulings = repository.parent / "rulings.md"
    rulings.write_text(
        f"## A private heading\n\n- **Two sentences** (maintainer: yes to all): {RULING}; "
        "and an index counts from 0.\n",
        encoding="utf-8",
    )
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("docs(specification): as first written", {SPECIFICATION: ROW.format(added)})
    status, found = run(capsys, base, "--rulings", str(rulings))
    assert status == 1
    assert found == [
        f"{SPECIFICATION}:1: a ruled sentence differs: the ruling has "
        '"holds its unit, specimen, statistics and provenance as `record_format.md` section 5 gives them;", '
        'this line "holds its `unit`, `specimen`, '
        f'`statistics` and `provenance`{added} as `record_format.md` section 5 gives them."'
    ]
    assert "private heading" not in found[0]
    assert "Two sentences" not in found[0]
    written = check_claims.git("rev-parse", "HEAD").strip()
    commit("docs(specification): the row's case", {SPECIFICATION: ROW.format(added).replace("013", "014")})
    assert run(capsys, written, "--rulings", str(rulings)) == (0, [])
    commit("docs(specification): in the ruling's words", {SPECIFICATION: ROW.format("")})
    assert run(capsys, base, "--rulings", str(rulings)) == (0, [])


SWEPT = (
    "an over-range or kept entry holds its unit, specimen, statistics and provenance as `record_format.md` "
    "section 5 gives them, and an alternative's index counts from 0 in stored order."
)
PHRASE = (
    "holds its unit, specimen, statistics and provenance as `record_format.md` section 5 gives them".split()
)
OWN_LEAD = "An entry whose alternative is kept outside its form's range"
RULED_LEAD = "An over-range or kept entry"


def judged(rulings: str, text: str) -> tuple[list[str], list[str]]:
    """Check 3's findings over `text` against `rulings`, and apart those an accepted wording holds."""
    return check_claims.ruling_findings(
        rulings, [("s.md", sentence) for sentence in check_claims.sentences(text)]
    )


def ruled(rulings: str, text: str) -> list[str]:
    return judged(rulings, text)[0]


@pytest.mark.parametrize("lead", [OWN_LEAD, RULED_LEAD])
@pytest.mark.parametrize("tail", [".", ", and an alternative's index counts from 0 in stored order."])
@pytest.mark.parametrize(
    ("change", "position"),
    [
        *((change, position) for change in ("substitute", "delete", "insert") for position in range(13)),
        *(("insert four", position) for position in range(1, 13)),
        ("insert", 13),
    ],
)
def test_a_ruled_phrase_with_a_word_changed_anywhere_is_flagged(
    lead: str, tail: str, change: str, position: int
) -> None:
    words: list[str] = list(PHRASE)
    if change == "substitute":
        words[position] = "XYZ"
    elif change == "delete":
        del words[position]
    else:
        words[position:position] = ["XYZ"] * (4 if change == "insert four" else 1)
    assert ruled(SWEPT, f"{lead} {' '.join(PHRASE)}{tail}") == []
    # Left to the reviewer: the run's first word changed where the words before it are the text's own and its
    # ruling's clause starts more than `MAX_LEAD` words before it ("an over-range or kept entry").
    unseen = lead == OWN_LEAD and position == 0 and change in {"substitute", "delete", "insert"}
    assert bool(ruled(SWEPT, f"{lead} {' '.join(words)}{tail}")) is not unseen


OPENING = (
    "every reader of a record refuses it where its unit names no quantity the field allows here today".split()
)


@pytest.mark.parametrize(
    ("change", "position"),
    [
        *((change, position) for change in ("substitute", "delete") for position in range(len(OPENING))),
        *((change, position) for change in ("insert", "insert four") for position in range(len(OPENING) + 1)),
    ],
)
def test_a_ruled_clause_with_a_word_changed_at_either_end_under_the_text_s_own_lead_is_flagged(
    change: str, position: int
) -> None:
    ruling = " ".join(OPENING).capitalize() + "."
    words: list[str] = list(OPENING)
    if change == "substitute":
        words[position] = "XYZ"
    elif change == "delete":
        del words[position]
    else:
        words[position:position] = ["XYZ"] * (4 if change == "insert four" else 1)
    assert ruled(ruling, f"Under this profile {' '.join(OPENING)}; and nothing more follows.") == []
    # Left to the reviewer: a word added before the ruling clause's first word, as the text's own lead is.
    unseen = position == 0 and change.startswith("insert")
    assert (
        bool(ruled(ruling, f"Under this profile {' '.join(words)}; and nothing more follows.")) is not unseen
    )


OBJECT = "its unit, specimen, statistics and provenance as `record_format.md` section 5 gives them."


@pytest.mark.parametrize(
    ("ruling", "text"),
    [
        # A negation or a modal before the ruled verb, where the text keeps a word of the ruling's subject.
        (SWEPT, f"An over-range entry does not hold {OBJECT}"),
        (SWEPT, f"An over-range entry may hold {OBJECT}"),
        (SWEPT, f"Such an entry must hold {OBJECT}"),
        # A negation under the text's own subject, where the ruling's clause opens within `MAX_LEAD` words.
        (
            "Readers refuse a record whose unit names no quantity.",
            "Under this profile they do not refuse a record whose unit names no quantity.",
        ),
        # The ruled clause's last word changed, where the text goes on in its own words.
        (
            "Every reader refuses a record whose unit names no quantity, whatever its source.",
            "Under this profile every reader refuses a record whose unit names no XYZ that the field allows "
            "in this release.",
        ),
    ],
    ids=["negated", "may", "must", "negated-under-its-own-subject", "last-word-and-on"],
)
def test_a_word_changed_at_a_ruled_run_s_edge_is_flagged(ruling: str, text: str) -> None:
    assert ruled(ruling, text)


@pytest.mark.parametrize(
    ("ruling", "text", "ours", "theirs"),
    [
        # A word added where the text's clause opens, before the ruling clause's first word.
        (
            "Readers refuse a record whose unit names no quantity.",
            "In this profile, all readers refuse a record whose unit names no quantity.",
            "Readers refuse a record whose unit names no quantity.",
            "all readers refuse a record whose unit names no quantity.",
        ),
        # The text's words before the run, as many as the ruling's, within its own clause.
        (
            "Alpha beta refuses a record whose unit names no quantity the field allows.",
            "It holds, refuses a record whose unit names no quantity the field allows.",
            "Alpha beta refuses a record whose unit names no quantity the field allows.",
            "refuses a record whose unit names no quantity the field allows.",
        ),
        # And after it.
        (
            "Every reader refuses it where its unit names no quantity the field allows, whatever its source.",
            "Every reader refuses it where its unit names no quantity it reads, and so on.",
            "Every reader refuses it where its unit names no quantity the field allows,",
            "Every reader refuses it where its unit names no quantity it reads,",
        ),
    ],
    ids=["added-where-its-clause-opens", "before-within-its-clause", "after-within-its-clause"],
)
def test_a_run_takes_the_text_s_words_at_its_edges_within_the_text_s_own_clause(
    ruling: str, text: str, ours: str, theirs: str
) -> None:
    assert ruled(ruling, text) == [
        f's.md:1: a ruled sentence differs: the ruling has "{ours}", this line "{theirs}"'
    ]


@pytest.mark.parametrize(
    ("old", "new", "flagged"),
    [
        ("holds", "holds only", True),
        ("gives them", "describes them", True),
        ("its unit", "unit", True),
        ("provenance as", "provenance as they were stored, as", True),
        ("provenance as", "provenance not as", True),
        ("specimen, statistics and", "specimen and", True),
        # 13 words in common of 17, 0.76 of the longer run: flagged at `NEAR` 0.7, missed at 0.8.
        ("as `record_format.md` section 5", "as stored, as `record_format.md` section 5 item 5", True),
        # 9 words in common of 13, 0.69: a paraphrase past `NEAR`.
        ("its unit, specimen, statistics and provenance", "its provenance", False),
    ],
)
def test_the_ruled_sentence_reworded_naturally_is_flagged_while_near(
    old: str, new: str, flagged: bool
) -> None:
    text = f"{OWN_LEAD} {' '.join(PHRASE).replace(old, new, 1)}."
    assert bool(ruled(RULING + ".", text)) is flagged


def test_a_ruled_clause_cut_short_or_run_on_is_flagged_and_the_text_s_own_lead_is_not() -> None:
    phrase = " ".join(PHRASE)
    assert ruled(RULING + " in stored order.", f"{OWN_LEAD} {phrase}.")
    assert ruled(RULING + ".", f"{OWN_LEAD} {phrase} as stored.")
    merged = (
        "An entry whose alternative is kept outside its form's range, or is a table read over an operating "
        "range of its axis, holds its `unit`, `specimen`, `statistics` and `provenance` as "
        "`record_format.md` section 5 gives them, even where its read ended at step 11."
    )
    assert ruled(f"{RULING}; and an index counts from 0.", merged) == []


def test_a_word_that_would_make_a_run_far_is_not_its() -> None:
    # "of" matches seven words on in the text: joined, it would make the run far, and the run would go unseen.
    found = ruled(
        "x is the test method only of a value of origin y, held by a writer.",
        "x is the test method of a value evaluated from a reference formulation, an equation of state.",
    )
    assert found == [
        's.md:1: a ruled sentence differs: the ruling has "x is the test method only of a value", '
        'this line "x is the test method of a value"'
    ]


WORDS = (
    "every reader of a record refuses it where its unit names no quantity the field allows here today".split()
)
LONGER = [*WORDS, "and", "where", "its", "value", "lies", "outside"]


@pytest.mark.parametrize(
    ("ruling", "text", "flagged"),
    [
        # Pieces apart by `MAX_GAP` words on both sides form one run; by one more, two identical runs.
        (WORDS, [*WORDS[:5], "x", "y", "z", *WORDS[8:]], True),
        (WORDS, [*WORDS[:5], "w", "x", "y", "z", *WORDS[9:]], False),
        # An insertion of `MAX_INSERT` words joins a run; one more word splits it.
        (LONGER, [*LONGER[:10], *(f"x{n}" for n in range(8)), *LONGER[10:]], True),
        (LONGER, [*LONGER[:10], *(f"x{n}" for n in range(9)), *LONGER[10:]], False),
        # `MIN_WORDS` words in common are compared, one fewer are not.
        (WORDS[:7], [*WORDS[:6], "other"], True),
        (WORDS[:6], [*WORDS[:5], "other"], False),
        # A run reaches back to its ruling clause's start `MAX_LEAD` words before it, and no further.
        (["alpha", "beta", *WORDS[5:]], ["gamma", "delta", *WORDS[5:]], True),
        (["alpha", "beta", "omega", *WORDS[5:]], ["gamma", "delta", "sigma", *WORDS[5:]], False),
        # Two shared runs of three words make a pair to compare.
        (WORDS[:7], [*WORDS[:3], "other", *WORDS[4:7]], True),
    ],
)
def test_the_ruled_wording_constants_hold_at_their_bounds(
    ruling: list[str], text: list[str], flagged: bool
) -> None:
    assert bool(ruled(" ".join(ruling) + ".", " ".join(text) + ".")) is flagged


def test_a_ruling_is_printed_without_its_markup_attribution_or_labels(repository: Path) -> None:
    rulings = (
        '- **S3b-2** (maintainer, 2026-10-19, "confirmed"): each entry holds its unit as the row gives it '
        "(A1Q1); (7) every reader refuses a record whose unit names no quantity.\n"
    )
    text = "Each entry holds its unit as the table gives it.\n\nA reader refuses a record whose unit names no"
    found = ruled(rulings, text + " quantity.")
    assert found == [
        's.md:1: a ruled sentence differs: the ruling has "each entry holds its unit as the row gives it", '
        'this line "Each entry holds its unit as the table gives it."',
        's.md:3: a ruled sentence differs: the ruling has "every reader refuses a record whose unit names no '
        'quantity.", this line "A reader refuses a record whose unit names no quantity."',
    ]


def test_a_ruling_s_bold_markup_ends_its_sentence_and_is_not_printed() -> None:
    found = ruled(
        "Each entry holds its unit as the row gives it **Settled**\n",
        "Each entry holds its unit as the table gives it.",
    )
    assert found == [
        's.md:1: a ruled sentence differs: the ruling has "Each entry holds its unit as the row gives it", '
        'this line "Each entry holds its unit as the table gives it."'
    ]


def test_a_wording_accepted_for_a_ruling_is_printed_with_the_run_it_waives_not_reported(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rulings = repository.parent / "rulings.md"
    rulings.write_text(f"- {RULING}.\n{ACCEPTED_LINE}\n", encoding="utf-8")
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("docs(specification): as stored, accepted", {SPECIFICATION: LANDED})
    assert run(capsys, base, "--rulings", str(rulings)) == (0, [])
    facts = str(repository.parent / "facts.json")
    assert check_claims.main(["check", base, "--facts", facts, "--rulings", str(rulings)]) == 0
    assert (
        f"accepted by the rulings file: {SPECIFICATION}:1: a ruled sentence differs: the ruling has "
        '"holds its unit, specimen, statistics and provenance as `record_format.md` section 5 gives them.", '
        'this line "holds its `unit`, `specimen`, `statistics` and `provenance` as stored, as '
        '`record_format.md` section 5 gives them."'
    ) in capsys.readouterr().out.splitlines()
    commit("docs(specification): in the ruling's words", {SPECIFICATION: ROW.format("")})
    assert run(capsys, base, "--rulings", str(rulings)) == (0, [])  # the accepted line is no ruling


KEPT = (
    "a kept entry holds its unit, specimen, statistics and provenance exactly as `record_format.md` "
    "section 5 gives them, never as stored."
)
LANDED = ROW.format(" as stored,")
ACCEPTED_LINE = (
    '  Accepted wording: "holds its `unit`, `specimen`, `statistics` and `provenance` as stored, as '
    '`record_format.md` section 5 gives them"'
)


@pytest.mark.parametrize(
    ("rulings", "reported", "waived"),
    [
        # Just under a ruling, it waives that ruling's difference and no other ruling's.
        (f"- {RULING}.\n{ACCEPTED_LINE}\n- {KEPT}\n", ["kept"], ["ruled"]),
        (f"- {RULING}.\n- {KEPT}\n{ACCEPTED_LINE}\n", ["ruled"], ["kept"]),
        # Under no ruling it waives nothing; inside a ruling's line it is that ruling's, compared as usual.
        (f"- {RULING}.\n\n{ACCEPTED_LINE}\n- {KEPT}\n", ["kept", "ruled"], []),
        (f"- {RULING}. ({ACCEPTED_LINE.strip()})\n- {KEPT}\n", ["kept", "ruled"], []),
        # A wording that differs from the landed one by a word waives nothing, though it shares the rest.
        (f"- {RULING}.\n{ACCEPTED_LINE.replace('stored', 'kept')}\n- {KEPT}\n", ["kept", "ruled"], []),
        # It closes its ruling: a paragraph's line after it opens another ruling.
        (f"{RULING}.\n{ACCEPTED_LINE}\n{KEPT}\n", ["kept"], ["ruled"]),
    ],
    ids=[
        "under-the-first",
        "under-the-second",
        "under-none",
        "in-a-ruling-s-line",
        "another-wording",
        "closing-its-paragraph",
    ],
)
def test_an_accepted_wording_waives_only_the_ruling_just_above_it_and_only_the_words_it_quotes(
    rulings: str, reported: list[str], waived: list[str]
) -> None:
    def which(findings: list[str]) -> list[str]:
        return sorted("kept" if "exactly" in finding else "ruled" for finding in findings)

    found, accepted = judged(rulings, LANDED)
    assert (which(found), which(accepted)) == (reported, waived)
