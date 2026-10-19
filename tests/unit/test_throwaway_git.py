# SPDX-License-Identifier: Apache-2.0
"""A throwaway repository leaves the repository that git names in the environment untouched, and runs no
automatic maintenance."""

import json
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


def maintenance_started_by_a_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, setting: bool
) -> list[str]:
    """The commands a commit in a throwaway repository starts that run git's maintenance, read from the
    commit's own trace; with `setting` False, in one whose `maintenance.auto` is unset again."""
    repository = tmp_path / "repository"
    repository.mkdir()
    throwaway_repository(repository, monkeypatch)
    if not setting:
        subprocess.run(["git", "config", "--unset", "maintenance.auto"], check=False)
        unset = subprocess.run(
            ["git", "config", "--get", "maintenance.auto"], capture_output=True, check=False
        )
        assert unset.returncode == 1, unset
    trace = tmp_path / "trace2.json"
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))
    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    subprocess.run(["git", *identity, "commit", "-q", "--allow-empty", "-m", "change"], check=True)
    events = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    assert any(event["event"] == "start" and "commit" in event["argv"] for event in events), events
    started = [" ".join(event["argv"]) for event in events if event["event"] == "child_start"]
    return [command for command in started if {"maintenance", "gc"} & set(command.split())]


def test_a_commit_in_a_throwaway_repository_starts_no_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert maintenance_started_by_a_commit(tmp_path, monkeypatch, setting=True) == []


def test_the_maintenance_check_can_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git starts its maintenance after every commit, whatever its version and however few objects are loose;
    whether that maintenance then repacks is git's decision, which is why the start is what is checked."""
    assert maintenance_started_by_a_commit(tmp_path, monkeypatch, setting=False) != []
