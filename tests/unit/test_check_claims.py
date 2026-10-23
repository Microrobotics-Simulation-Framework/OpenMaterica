# SPDX-License-Identifier: Apache-2.0
"""The claims check flags a stale git fact, a figure no fact records and a ruled sentence reworded, and passes
each correct form, in a throwaway repository with a rulings file written for the tests."""

import json
import subprocess
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


def commit(message: str, files: dict[str, str] | None = None) -> str:
    for name, text in (files or {}).items():
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        Path(name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "--all"], check=True)
    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    subprocess.run(["git", *identity, "commit", "-q", "--allow-empty", "-m", message], check=True)
    return check_claims.git("rev-parse", "HEAD").strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository on its first commit, an empty baseline and an empty facts file beside it."""
    root = tmp_path / "repository"
    root.mkdir()
    throwaway_repository(root, monkeypatch)
    (tmp_path / "baseline.json").write_text('{"changelog": []}', encoding="utf-8")
    (tmp_path / "facts.json").write_text('{"facts": []}', encoding="utf-8")
    monkeypatch.setattr(check_claims, "BASELINE", tmp_path / "baseline.json")
    changelog = "# Changelog\n\n- Older: 12 tests.\n"
    commit("docs: on main", {"CHANGELOG.md": changelog, SPECIFICATION: "| member | text |\n"})
    return root


def run(capsys: pytest.CaptureFixture[str], base: str, *arguments: str) -> tuple[int, list[str]]:
    """The check's status and its findings, without the summary lines."""
    facts = str(Path.cwd().parent / "facts.json")
    status = check_claims.main(["check", base, "--facts", facts, *arguments])
    lines = capsys.readouterr().out.splitlines()
    return status, [line for line in lines if ": " in line and not line.startswith(("figures:", "the ruled"))]


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
        "| Part | Added | Removed |\n|---|---|---|\n| a.txt | 1 | 1 |\n| b.txt | 1 | 0 |\n"
    )
    status, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        "`0123abcd` names no commit here",
        f"the base is `{base[:8]}`, not `{old[:8]}`",
        "1 removed, where git counts 0",
    ]


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


@pytest.mark.parametrize(
    "text",
    [
        "section 4.1 and steps 8 to 13, items 1, 2 and 4",
        "on Python 3.11 and 3.15; `pytest -n 8`, -n 12 and `1723 passed` in code",
        "BC-048, HP13, S7a-2, PR-339 and #77, U+2212 and the 500th example",
        "on 2026-10-23 at 10:24, in run 39404674681 (Marcinkowska-Gapinska 2013)",
        '(1) the first; "1180 of 1522 case files" as quoted; the interval [275, 283]',
        "at 37 °C, at the one-sided 95 % bound, about 45 s, ~3 runs and 55 minutes by estimate",
    ],
)
def test_a_number_of_a_kind_that_is_no_measurement_needs_no_fact(text: str) -> None:
    assert check_claims.figures(text)[0] == []


def test_a_figure_needs_a_recorded_fact_measured_at_a_commit_the_head_holds(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    commit("feat: one", {"a.txt": "a\n"})
    description = repository.parent / "description.md"
    description.write_text(
        "Conformance: 1,180 of 1,522 case files pass; 35 are verified.\n", encoding="utf-8"
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
    assert run(capsys, base, "--description", str(description)) == (0, [])
    elsewhere = check_claims.git("commit-tree", "HEAD^{tree}", "-m", "elsewhere").strip()
    stored = json.loads((repository.parent / "facts.json").read_text(encoding="utf-8"))
    stored["facts"][4]["at"] = elsewhere
    (repository.parent / "facts.json").write_text(json.dumps(stored), encoding="utf-8")
    status, found = run(capsys, base, "--description", str(description))
    assert [line.partition(": ")[2] for line in found] == [
        "35 (are verified ...) was measured at a commit the head does not hold"
    ]
    assert check_claims.main(["record", "many", "tests", "--how", "counted", *facts]) == 2
    assert check_claims.main(["record", "3", "tests", "--how", " ", *facts]) == 2


def test_a_changelog_figure_the_branch_adds_fails_unless_a_fact_or_the_baseline_holds_it(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = check_claims.git("rev-parse", "HEAD").strip()
    text = "# Changelog\n\n- The runner: 1180 of 1573 case files pass,\n  and the suite took 23.7 minutes.\n"
    text += "- Older: 12 tests.\n"
    commit("docs: the counts", {"CHANGELOG.md": text})
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
    entries = [[key, 3, "measured"] for key in keys[:2]]
    check_claims.BASELINE.write_text(json.dumps({"changelog": entries}), encoding="utf-8")
    status, found = run(capsys, base)
    assert [line.split(": ")[0] for line in found] == ["CHANGELOG.md:4"]


def test_the_committed_baseline_holds_each_figure_once_with_a_listed_reason() -> None:
    baseline = json.loads(check_claims.BASELINE.read_text(encoding="utf-8"))
    keys = [key for key, _, _ in baseline["changelog"]]
    assert len(keys) == len(set(keys))
    assert {reason for _, _, reason in baseline["changelog"]} == set(baseline["reasons"])
    assert all(isinstance(line, int) and line > 0 for _, line, _ in baseline["changelog"])


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
