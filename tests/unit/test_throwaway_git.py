# SPDX-License-Identifier: Apache-2.0
"""A throwaway repository leaves the repository that git names in the environment untouched."""

import os
import subprocess
from pathlib import Path

import pytest

from tests.unit.throwaway_git import throwaway_repository


def test_a_linked_worktree_named_by_the_environment_is_left_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    clean |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def outside(*arguments: str, cwd: Path = tmp_path) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, env=clean, capture_output=True, text=True, check=True
        ).stdout

    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    outer, linked = tmp_path / "outer", tmp_path / "linked"
    outside("init", "-q", "-b", "main", str(outer))
    outside(*identity, "commit", "-q", "--allow-empty", "-m", "outer", cwd=outer)
    outside("worktree", "add", "-q", str(linked), "-b", "side", cwd=outer)

    def head() -> str:
        return outside("rev-parse", "HEAD", cwd=linked)

    config, linked_head = (outer / ".git" / "config").read_bytes(), head()
    # As `git rebase --exec` sets it for the command it runs, in a linked worktree.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git" / "worktrees" / "linked"))

    inner = tmp_path / "inner"
    inner.mkdir()
    throwaway_repository(inner, monkeypatch)
    (inner / "file").write_text("text")
    subprocess.run(["git", "add", "file"], check=True)
    subprocess.run(["git", *identity, "commit", "-q", "-m", "inner"], check=True)

    assert (outer / ".git" / "config").read_bytes() == config
    assert head() == linked_head
    log = subprocess.run(["git", "log", "--format=%s"], capture_output=True, text=True, check=True)
    assert log.stdout == "inner\n"
