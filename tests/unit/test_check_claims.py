# SPDX-License-Identifier: Apache-2.0
"""The claims check flags a stale git fact, a figure no fact records and a ruled sentence reworded, and passes
each correct form, in a throwaway repository with a rulings file written for the tests."""

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import check_claims
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
    summary = ("figures:", "the ruled", "measured before the head:")
    return status, [line for line in lines if ": " in line and not line.startswith(summary)]


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
        "Its checks: (1) the reader; (2) the writer, with seeds 0 and 3",
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


def test_a_fact_measured_before_the_head_holds_only_across_commits_that_change_markdown_alone(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.py": "x = 1\n"})
    description = repository.parent / "description.md"
    description.write_text("The suite: 41 tests pass.\n", encoding="utf-8")
    facts = ["--facts", str(repository.parent / "facts.json")]
    assert check_claims.main(["record", "41", "tests pass", "--how", "pytest -q", *facts]) == 0
    measured = check_claims.git("rev-parse", "HEAD").strip()
    commit("docs: a note", {"NOTES.md": "a note\n"})
    status, found = run(capsys, base, "--description", str(description))
    assert (status, found) == (0, [])
    assert check_claims.main(["check", base, "--description", str(description), *facts]) == 0
    assert (
        f"measured before the head: {description}:1: 41 (tests pass ...) was measured at `{measured[:8]}`, "
        "1 commits before the head, which change Markdown files alone"
    ) in capsys.readouterr().out.splitlines()
    commit("fix: two", {"a.py": "x = 2\n", "b.py": "y = 1\n"})
    status, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        f"41 (tests pass ...) was measured at `{measured[:8]}`, 2 commits before the head, which change 2 "
        "files that are not Markdown: a.py, b.py"
    ]


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


def test_the_committed_baseline_holds_only_figures_of_the_changelog_at_its_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(check_claims.BASELINE.parent.parent)
    at = json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))["at"]
    if check_claims.resolve(at) is None:
        pytest.skip(f"a shallow clone holds no {at[:8]}; the check itself holds the baseline to it each run")
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
