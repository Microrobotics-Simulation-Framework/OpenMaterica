# SPDX-License-Identifier: Apache-2.0
"""The sign-off check passes signed and design commits, and fails on any other, in a throwaway repository."""

import subprocess
from pathlib import Path

import pytest

from scripts import check_signoff
from tests.unit.throwaway_git import throwaway_repository

AUTHOR = "Author <author@example.org>"


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return throwaway_repository(tmp_path, monkeypatch)


def commit(message: str, author: str = AUTHOR) -> str:
    Path("file").write_text(message)
    subprocess.run(["git", "add", "file"], check=True)
    name, _, email = author.partition(" <")
    identity = ["-c", f"user.name={name}", "-c", f"user.email={email.rstrip('>')}"]
    subprocess.run(["git", *identity, "commit", "-q", "-m", message], check=True)
    return check_signoff.git("rev-parse", "HEAD").stdout.strip()


def test_design_commits_are_exempt_and_others_need_their_authors_sign_off(repository: Path) -> None:
    base = commit("docs: on main")
    design = commit("docs: before the first code")
    commit(f"feat: signed\n\nSigned-off-by: {AUTHOR}")
    unsigned = commit("feat: unsigned")
    by_another = commit("fix: signed by another\n\nSigned-off-by: Other <other@example.org>")
    buried = commit(f"fix: sign-off not in the last paragraph\n\nSigned-off-by: {AUTHOR}\n\nMore text.")
    problems = check_signoff.unsigned_commits(base, "HEAD", design_history=design)
    assert [problem.split()[0] for problem in problems] == [c[:12] for c in (buried, by_another, unsigned)]


def test_a_design_history_absent_from_the_repository_exempts_nothing(repository: Path) -> None:
    base = commit("docs: on main")
    design = commit("docs: before the first code")
    problems = check_signoff.unsigned_commits(base, "HEAD", design_history="0" * 40)
    assert [problem.split()[0] for problem in problems] == [design[:12]]


def test_the_command_fails_on_an_unsigned_commit(repository: Path) -> None:
    base = commit("docs: on main")
    signed = commit(f"feat: signed\n\nSigned-off-by: {AUTHOR}")
    assert check_signoff.main([base, signed]) == 0
    commit("feat: unsigned")
    assert check_signoff.main([base, "HEAD"]) == 1
