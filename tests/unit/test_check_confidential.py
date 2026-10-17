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


# The pre-push scan: what a push sends, read from git's pre-push input, a line for each ref pushed.
NO_OBJECT = "0" * 40


@pytest.fixture
def remote(repository: Path, tmp_path: Path) -> Path:
    """A bare repository, the remote `origin` of `repository`, holding its first commit."""
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], check=True)
    commit("docs: the start", {"README.md": b"Nothing here.\n"})
    subprocess.run(["git", "push", "-q", "origin", "main"], check=True)
    return bare


def object_name(revision: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "rev-parse", revision], capture_output=True, text=True, check=True
    ).stdout.strip()


def pre_push(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key_file: Path | None,
    remote: str,
    *updates: str,
) -> tuple[int, list[str]]:
    """The scan's exit status and findings, run as the pre-push hook runs it."""
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in updates)))
    keyed = ["--key-file", str(key_file)] if key_file else []
    status = check_confidential.main([*keyed, "--pre-push", remote])
    return status, [line for line in capsys.readouterr().err.splitlines() if not line.startswith("warning:")]


def update(local: str, remote_object: str, ref: str = "refs/heads/main") -> str:
    return f"{ref} {local} {ref} {remote_object}"


@pytest.fixture
def key_file(tmp_path: Path) -> Path:
    written = tmp_path / "key"
    written.write_text(KEY.hex(), encoding="utf-8")
    return written


def test_the_pre_push_scan_finds_what_the_push_sends_a_later_commit_undoes_included(
    remote: Path,
    key_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file a later commit removes is still sent, and public once pushed; the working tree no longer has it,
    so the scan of the tracked files, the control, finds nothing."""
    start = object_name()
    commit("docs: notes", {"notes.md": f"In {HOME}x.\n".encode()})
    found_in = object_name()[:12]
    subprocess.run(["git", "rm", "-q", "notes.md"], check=True)
    commit("docs: by Zorblax", {"README.md": b"Still nothing.\n"})
    status, found = pre_push(monkeypatch, capsys, key_file, "origin", update(object_name(), start))
    assert status == 1
    assert found[0] == "notes.md (pushed):1: an absolute home directory path"
    assert found[1].endswith("message:1: a confidential term (z..., 7 characters)")
    assert found_in not in found[1]
    assert check_confidential.main(["--key-file", str(key_file)]) == 0


def test_the_pre_push_scan_reads_only_what_the_remote_lacks(
    remote: Path,
    key_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """What the remote holds is public already; a push to it is judged by what it adds. To a URL, with no
    remote-tracking refs and no object the remote reported, the whole history is read: the control."""
    commit("docs: quux widget", {"old.md": b"By quux widget.\n"})
    subprocess.run(["git", "push", "-q", "origin", "main"], check=True)
    held = object_name()
    commit("docs: more", {"new.md": b"Nothing private.\n"})
    assert pre_push(monkeypatch, capsys, key_file, "origin", update(object_name(), held)) == (0, [])
    new_branch = update(object_name(), NO_OBJECT, "refs/heads/topic")
    assert pre_push(monkeypatch, capsys, key_file, "origin", new_branch) == (0, [])
    status, found = pre_push(monkeypatch, capsys, key_file, str(remote), new_branch)
    assert status == 1
    assert "old.md (pushed):1: a confidential term (q..., 11 characters)" in found
    assert pre_push(monkeypatch, capsys, key_file, str(remote), update(object_name(), held)) == (0, [])


def test_the_pre_push_scan_reads_an_annotated_tag_and_nothing_for_a_deleted_ref(
    remote: Path,
    key_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = ["-c", "user.name=Author", "-c", "user.email=author@example.org"]
    subprocess.run(["git", *identity, "tag", "-a", "v1", "-m", "For Zorblax"], check=True)
    status, found = pre_push(
        monkeypatch, capsys, key_file, "origin", update(object_name("v1"), NO_OBJECT, "refs/tags/v1")
    )
    assert (status, found) == (1, ["tag v1:6: a confidential term (z..., 7 characters)"])
    deleted = f"(delete) {NO_OBJECT} refs/heads/old {object_name()}"
    assert pre_push(monkeypatch, capsys, key_file, "origin", deleted) == (0, [])


def test_the_pre_push_scan_keeps_the_allowed_path_and_leaves_binary_files_out(
    remote: Path,
    key_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    start = object_name()
    commit(
        "docs: where the plans are",
        {"CLAUDE.md": f"See ../{PLANNING}x.\n".encode(), "data.bin": f"{HOME}\0".encode()},
    )
    assert pre_push(monkeypatch, capsys, key_file, "origin", update(object_name(), start)) == (0, [])
    commit("docs: copied", {"notes.md": f"See ../{PLANNING}x.\n".encode()})
    status, found = pre_push(monkeypatch, capsys, key_file, "origin", update(object_name(), start))
    assert (status, found) == (1, ["notes.md (pushed):1: a path into the private planning directory"])


@pytest.mark.parametrize(
    "line",
    ["refs/heads/main abc refs/heads/main def", "refs/heads/main", f"main {NO_OBJECT} main {NO_OBJECT} more"],
)
def test_the_pre_push_scan_refuses_input_that_is_not_gits(
    remote: Path, line: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status, found = pre_push(monkeypatch, capsys, None, "origin", line)
    assert status == 2
    assert found == [f"not a line of git's pre-push input: {line!r}"]


SCRIPTS = Path(check_confidential.__file__).resolve().parent


def push(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "push", *arguments], capture_output=True, text=True, check=False)


def test_the_hook_refuses_a_push_that_would_publish_a_private_path_or_name(
    remote: Path, tmp_path: Path, key_file: Path
) -> None:
    """The hook as a person installs it, run by `git push`: the paths without the key, the names with the
    key file the configuration names; and a push without a finding goes through."""
    (Path("scripts")).mkdir()
    commit(
        "build: the scan and its hook",
        {
            "scripts/check_confidential.py": (SCRIPTS / "check_confidential.py").read_bytes(),
            "scripts/pre-push": (SCRIPTS / "pre-push").read_bytes(),
            "scripts/confidential_digests.txt": check_confidential.digest_file(KEY, TERMS).encode(),
        },
    )
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-push").write_bytes((SCRIPTS / "pre-push").read_bytes())
    (hooks / "pre-push").chmod(0o755)
    subprocess.run(["git", "config", "core.hooksPath", str(hooks)], check=True)
    assert push("-q", "origin", "main").returncode == 0
    commit("docs: by Zorblax", {"notes.md": b"Nothing else.\n"})
    assert push("-q", "origin", "main").returncode == 0, "without the key, a name goes through"
    commit("docs: notes", {"notes.md": f"In {HOME}x.\n".encode()})
    refused = push("origin", "main")
    assert refused.returncode != 0
    assert "notes.md (pushed):1: an absolute home directory path" in refused.stderr
    subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1"], check=True)
    commit("docs: by quux widget", {"more.md": b"Nothing.\n"})
    subprocess.run(["git", "config", "openmaterica.scanKeyFile", str(key_file)], check=True)
    refused = push("origin", "main")
    assert refused.returncode != 0
    assert "message:1: a confidential term (q..., 11 characters)" in refused.stderr
    assert "warning: no key" not in refused.stderr


def test_the_hook_refuses_to_push_from_a_checkout_whose_scan_predates_it(
    remote: Path, tmp_path: Path
) -> None:
    """The control of the hook's own check: a scan without `--pre-push` would refuse every push with a usage
    error; the hook says what to do instead."""
    (Path("scripts")).mkdir()
    commit("build: an old scan", {"scripts/check_confidential.py": b"import sys\nsys.exit(0)\n"})
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-push").write_bytes((SCRIPTS / "pre-push").read_bytes())
    (hooks / "pre-push").chmod(0o755)
    subprocess.run(["git", "config", "core.hooksPath", str(hooks)], check=True)
    refused = push("origin", "main")
    assert refused.returncode != 0
    assert "has no --pre-push; rebase it onto main" in refused.stderr
