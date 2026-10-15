# SPDX-License-Identifier: Apache-2.0
"""The confidentiality scan finds invented terms however they are written, and the private paths, in tracked
files and commit messages, never echoes a term, and refuses a key its digests were not made with.

The paths are built by concatenation, so that this file does not hold them for the scan to find.
"""

import io
import subprocess
from pathlib import Path

import pytest

from scripts import check_confidential
from scripts.check_confidential import ALLOWED_PATHS, ScanError, Scanner
from tests.unit.throwaway_git import throwaway_repository

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
TERMS = ("Zorblax", "quux-widget")
HOME = "/" + "home/someone/"
SCRATCHPAD = "/tmp/x/" + "scratch" + "pad/notes.txt"
TEMPORARY = "/tmp/" + "claude-1000/"
PLANNING = "plan" + "s/"


def scanner(key: bytes | None = KEY) -> Scanner:
    digests = check_confidential.read_digests(check_confidential.digest_file(KEY, TERMS), KEY)
    return Scanner(key, digests)


@pytest.mark.parametrize(
    "text",
    [
        "Zorblax",
        "the ZORBLAX team",
        "mail@zorblax.org",
        "quux widget",
        "Quux-Widget",
        "quux_widget",
        "a quux\nwidget",
        "the quux-widget-core repository",
    ],
)
def test_a_term_is_found_however_it_is_written(text: str) -> None:
    assert scanner().findings("notes.md", text)


@pytest.mark.parametrize("text", ["zorblaxes", "quuxwidget", "widget quux", "quux, then a widget", ""])
def test_other_words_are_not_found(text: str) -> None:
    assert scanner().findings("notes.md", text) == []


def test_a_finding_gives_its_place_and_never_the_term() -> None:
    assert scanner().findings("notes.md", "First line.\nBy zorblax.\nAnd quux\nwidget.") == [
        "notes.md:2: a confidential term (z..., 7 characters)",
        "notes.md:4: a confidential term (q..., 11 characters)",
    ]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (f"see {HOME}notes", "an absolute home directory path"),
        (f"see {SCRATCHPAD}", "a session scratchpad path"),
        (f"see {TEMPORARY}x", "a path into Claude Code's temporary directory"),
        (f"see {PLANNING}draft.md", "a path into the private planning directory"),
        (f"see ../{PLANNING}draft.md", "a path into the private planning directory"),
    ],
)
def test_the_private_paths_are_found_without_a_key(text: str, kind: str) -> None:
    assert scanner(key=None).findings("notes.md", f"Line one.\n{text}") == [f"notes.md:2: {kind}"]


def test_only_claude_md_names_the_planning_directory_and_only_one_level_up() -> None:
    allowed = ALLOWED_PATHS["CLAUDE.md"]
    assert scanner().findings("CLAUDE.md", f"Working files are in `../{PLANNING}`.", allowed) == []
    assert scanner().findings("CLAUDE.md", f"Working files are in `{PLANNING}`.", allowed) == [
        "CLAUDE.md:1: a path into the private planning directory"
    ]


def test_the_digests_are_refused_under_another_key() -> None:
    text = check_confidential.digest_file(KEY, TERMS)
    assert check_confidential.read_digests(text, KEY) == {
        check_confidential.digest(KEY, check_confidential.normalised(term)) for term in TERMS
    }
    with pytest.raises(ScanError, match="not the one the digests were made with"):
        check_confidential.read_digests(text, OTHER_KEY)
    with pytest.raises(ScanError, match="not the one the digests were made with"):
        check_confidential.read_digests(text.replace("check ", "# check "), KEY)
    with pytest.raises(ScanError, match="not a digest"):
        check_confidential.read_digests(text + "zorblax\n", KEY)


def test_the_committed_digest_file_holds_a_check_and_digests_only() -> None:
    lines = [
        line
        for line in check_confidential.DIGESTS.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert [line for line in lines if line.startswith("check ")] == lines[:1]
    assert len(lines) > 1
    assert all(len(line.removeprefix("check ")) == 64 for line in lines)


@pytest.mark.parametrize("text", ["", "00" * 31, "zz" * 32, "00" * 33])
def test_a_key_is_64_hexadecimal_digits(text: str) -> None:
    with pytest.raises(ScanError, match="64 hexadecimal digits"):
        check_confidential.parse_key(text)


def test_a_key_file_comes_before_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(check_confidential.KEY_VARIABLE, OTHER_KEY.hex())
    assert check_confidential.load_key(None) == OTHER_KEY
    (tmp_path / "key").write_text(KEY.hex() + "\n", encoding="utf-8")
    assert check_confidential.load_key(tmp_path / "key") == KEY
    monkeypatch.setenv(check_confidential.KEY_VARIABLE, "")
    assert check_confidential.load_key(None) is None
    with pytest.raises(ScanError, match="--key-file"):
        check_confidential.load_key(tmp_path / "absent")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository as the working directory, with the digest file of `TERMS` under `KEY`."""
    digests = tmp_path / "digests.txt"
    digests.write_text(check_confidential.digest_file(KEY, TERMS), encoding="utf-8")
    monkeypatch.setattr(check_confidential, "DIGESTS", digests)
    monkeypatch.delenv(check_confidential.KEY_VARIABLE, raising=False)
    root = tmp_path / "repository"
    root.mkdir()
    return throwaway_repository(root, monkeypatch)


def commit(message: str, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        Path(name).write_bytes(data)
    subprocess.run(["git", "add", *files], check=True)
    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    subprocess.run(["git", *identity, "commit", "-q", "-m", message], check=True)


def test_the_command_scans_tracked_files_and_the_messages_in_a_range(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "key").write_text(KEY.hex(), encoding="utf-8")
    key_file = ["--key-file", str(tmp_path / "key")]
    commit("docs: the start", {"README.md": b"Nothing here.\n"})
    commit("docs: by Zorblax", {"README.md": b"Nothing here.\n", "data.bin": b"zorblax\0"})
    (repository / "untracked.md").write_text("zorblax\n", encoding="utf-8")
    assert check_confidential.main(key_file) == 0
    assert check_confidential.main([*key_file, "--messages", "HEAD~1..HEAD"]) == 1
    assert "message:1: a confidential term (z..., 7 characters)" in capsys.readouterr().err
    commit("docs: notes", {"notes.md": f"By quux widget.\nIn {HOME}x.\n".encode()})
    assert check_confidential.main(key_file) == 1
    assert capsys.readouterr().err.splitlines() == [
        "notes.md:1: a confidential term (q..., 11 characters)",
        "notes.md:2: an absolute home directory path",
    ]
    assert check_confidential.main([]) == 1
    errors = capsys.readouterr().err.splitlines()
    assert errors[0] == "notes.md:2: an absolute home directory path"
    assert errors[1].startswith("warning: no key")
    monkeypatch.setenv(check_confidential.KEY_VARIABLE, OTHER_KEY.hex())
    assert check_confidential.main([]) == 2
    assert check_confidential.main([*key_file, "--messages", "no-such-revision"]) == 2


def test_the_digest_command_writes_the_digest_file(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "key").write_text(KEY.hex(), encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(TERMS) + "\n\n"))
    assert check_confidential.main(["--key-file", str(tmp_path / "key"), "--digest"]) == 0
    assert capsys.readouterr().out == check_confidential.digest_file(KEY, TERMS)
    assert check_confidential.main(["--digest"]) == 2
