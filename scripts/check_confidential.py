# SPDX-License-Identifier: Apache-2.0
"""Fail where a tracked file or a commit message names one of the maintainer's private projects, or carries a
private path.

    python scripts/check_confidential.py [--key-file KEY] [--messages RANGE]
    python scripts/check_confidential.py [--key-file KEY] --pre-push REMOTE < UPDATES
    python scripts/check_confidential.py --key-file KEY --digest < TERMS > scripts/confidential_digests.txt

The names cannot be listed in this public repository, and plain hashes of them would not hide them: they are
short words, which hashing a word list recovers. So `confidential_digests.txt` holds their HMAC-SHA256 under a
secret key, 64 hexadecimal digits from `CONFIDENTIAL_SCAN_KEY` or a key file. Its `check` line is the digest
of a fixed phrase: a key other than the one the digests were made with is refused, rather than finding
nothing. Text is lowercased and split into words of letters and digits; each word, each pair of adjacent words
and each hyphenated run of words is hashed, its words joined by hyphens. A finding gives its place and the
term's first letter and length, never the term. Without a key the names are not checked, and a warning says
so.

The private paths need no key: an absolute home directory, a session scratchpad, Claude Code's temporary
directory, and the private planning directory, which only `CLAUDE.md` names, one level up. The tracked files
are those of the repository in the working directory, read from its working tree.

With `--pre-push`, as git's pre-push hook (`scripts/pre-push`), it scans what a push publishes instead: the
name of each ref it writes, every file content and annotated tag the remote lacks, as git itself lists what to
send (`git rev-list --objects`), and the messages of the commits it brings, so that a name in a commit that a
later one removes is found too. What the remote lacks is bounded by what it advertises now (`git ls-remote`),
not by the remote-tracking refs, which a branch deleted on the server leaves behind. `--ref-name` scans a
ref's name beside the tracked files: CI gives it a pull request's branch.
"""

import argparse
import hmac
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

DIGESTS = Path(__file__).resolve().parent / "confidential_digests.txt"
KEY_VARIABLE = "CONFIDENTIAL_SCAN_KEY"
CHECK_PHRASE = "openmaterica confidential scan key check"

_WORD = re.compile(r"[a-z0-9]+")
_HYPHENATED = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
_KEY = re.compile(r"[0-9a-fA-F]{64}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_OBJECT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_NO_OBJECT = re.compile(r"0+")
# Each written so that its own source does not match it: this file is scanned too.
PATHS = {
    "an absolute home directory path": re.compile(r"/(?:home|Users)/[^/\s]+/"),
    "a session scratchpad path": re.compile(r"/scratch(?:pad)\b"),
    "a path into Claude Code's temporary directory": re.compile(r"/tmp/claud(?:e)"),
    "a path into the private planning directory": re.compile(r"\bplan(?:s)/"),
}
# CLAUDE.md says where the private working files are: in the planning directory beside the repository.
ALLOWED_PATHS = {"CLAUDE.md": re.compile(r"\.\./plan(?:s)/")}


class ScanError(ValueError):
    """A key, a digest file or a range this script cannot use."""


def parse_key(text: str) -> bytes:
    if not _KEY.fullmatch(text.strip()):
        raise ScanError(f"a key is 64 hexadecimal digits ({KEY_VARIABLE} or --key-file)")
    return bytes.fromhex(text.strip())


def load_key(key_file: Path | None) -> bytes | None:
    """The key from `key_file`, else from the environment; None when neither gives one."""
    if key_file is not None:
        try:
            return parse_key(key_file.read_text(encoding="utf-8"))
        except OSError as error:
            raise ScanError(f"--key-file: {error}") from error
    from_environment = os.environ.get(KEY_VARIABLE, "")
    return parse_key(from_environment) if from_environment else None


def normalised(term: str) -> str:
    return "-".join(_WORD.findall(term.lower()))


def digest(key: bytes, term: str) -> str:
    return hmac.digest(key, term.encode("utf-8"), "sha256").hex()


def digest_file(key: bytes, terms: Iterable[str]) -> str:
    """The text of `confidential_digests.txt` for `terms`, sorted, so that it keeps no order of the terms."""
    digests = sorted({digest(key, normalised(term)) for term in terms if normalised(term)})
    header = "# Written by scripts/check_confidential.py --digest (scripts/README.md). Do not edit by hand.\n"
    return header + f"check {digest(key, CHECK_PHRASE)}\n" + "".join(f"{line}\n" for line in digests)


def read_digests(text: str, key: bytes) -> frozenset[str]:
    """The digests of `text`, a digest file, once its check line shows that they were made with `key`."""
    digests: set[str] = set()
    check = None
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("check "):
            check = line.removeprefix("check ")
        elif _DIGEST.fullmatch(line):
            digests.add(line)
        else:
            raise ScanError(f"not a digest: {line!r}")
    if check is None or not hmac.compare_digest(check, digest(key, CHECK_PHRASE)):
        raise ScanError("the key is not the one the digests were made with")
    return frozenset(digests)


def candidates(text: str) -> Iterator[tuple[int, str]]:
    """Each word, pair of adjacent words and hyphenated run of words in `text`, normalised, with its line; a
    pair split by a line break is on the second word's line."""
    previous = ""
    for number, line in enumerate(text.lower().splitlines(), 1):
        for hyphenated in _HYPHENATED.findall(line):
            yield number, hyphenated
        for word in _WORD.findall(line):
            yield number, word
            if previous:
                yield number, f"{previous}-{word}"
            previous = word


def masked(term: str) -> str:
    return f"{term[0]}..., {len(term)} characters"


class Scanner:
    def __init__(self, key: bytes | None, digests: frozenset[str]) -> None:
        self.key = key
        self.digests = digests
        self.confidential: dict[str, bool] = {}

    def is_confidential(self, candidate: str) -> bool:
        if self.key is None:
            return False
        if candidate not in self.confidential:
            self.confidential[candidate] = digest(self.key, candidate) in self.digests
        return self.confidential[candidate]

    def findings(self, place: str, text: str, allowed: re.Pattern[str] | None = None) -> list[str]:
        """Each private path and confidential term in `text`, as `place:line: what`, in line order."""
        found: list[tuple[int, str]] = []
        for number, line in enumerate(text.splitlines(), 1):
            checked = allowed.sub("", line) if allowed else line
            found += [(number, kind) for kind, pattern in PATHS.items() if pattern.search(checked)]
        for number, candidate in candidates(text):
            if self.is_confidential(candidate):
                found.append((number, f"a confidential term ({masked(candidate)})"))
        return [f"{place}:{number}: {what}" for number, what in sorted(found, key=lambda finding: finding[0])]


def git(*arguments: str, stdin: bytes | None = None) -> bytes:
    try:
        return subprocess.run(["git", *arguments], input=stdin, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as error:
        raise ScanError(
            f"git {' '.join(arguments)}: {error.stderr.decode(errors='replace').strip()}"
        ) from error


def names_of(output: bytes) -> str:
    """git's output of paths or ref names, which are bytes: those that are not UTF-8 kept apart, so that a
    path read from it opens the same file."""
    return output.decode("utf-8", "surrogateescape")


def shown(name: str) -> str:
    """A path or ref name as a finding prints it, on one line: bytes that are not UTF-8 and control
    characters escaped."""
    text = name.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    return "".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in text)


def tracked_texts() -> Iterator[tuple[str, str]]:
    """Each tracked file of the working tree that is text, by its path: one holding a NUL byte is binary."""
    root = Path(names_of(git("rev-parse", "--show-toplevel")).strip())
    for name in names_of(git("-C", str(root), "ls-files", "-z")).split("\0"):
        path = root / name
        if name and path.is_file():
            data = path.read_bytes()
            if b"\0" not in data:
                yield name, data.decode("utf-8", errors="replace")


def commit_messages(*revisions: str, stdin: bytes | None = None) -> Iterator[tuple[str, str]]:
    """Each commit's message in `revisions`, `git log`'s arguments, by its shortened hash."""
    for entry in (
        git("log", "-z", "--format=%H%n%B", *revisions, stdin=stdin).decode("utf-8", "replace").split("\0")
    ):
        commit, _, message = entry.partition("\n")
        if commit:
            yield commit[:12], message


def ref_findings(scanner: Scanner, ref: str) -> list[str]:
    """The findings in a ref's name, which is public from the moment it is pushed, as `ref <name>`."""
    short = next(
        (ref.removeprefix(prefix) for prefix in ("refs/heads/", "refs/tags/") if ref.startswith(prefix)), ref
    )
    return scanner.findings(f"ref {shown(short)}", short)


def scan(scanner: Scanner, revisions: str | None, ref_names: Sequence[str] = ()) -> list[str]:
    found: list[str] = []
    for name, text in tracked_texts():
        found += scanner.findings(shown(name), text, ALLOWED_PATHS.get(name))
    for commit, message in commit_messages("--end-of-options", revisions) if revisions else ():
        found += scanner.findings(f"commit {commit} message", message)
    for ref in ref_names:
        found += ref_findings(scanner, ref)
    return found


def lines(names: Iterable[str]) -> bytes:
    return "".join(f"{name}\n" for name in names).encode()


def object_kinds(names: Iterable[str]) -> dict[str, str]:
    """The kind (`blob`, `tree`, `commit` or `tag`) of each of the objects `names` that this repository holds;
    one it lacks is left out, since a remote may advertise one never fetched."""
    asked = list(dict.fromkeys(names))
    listed = git("cat-file", "--batch-check", stdin=lines(asked)).decode("ascii", "replace") if asked else ""
    return {fields[0]: fields[1] for fields in map(str.split, listed.splitlines()) if len(fields) == 3}


def advertised(remote: str) -> list[str]:
    """The object each ref of `remote`, a remote's name or URL, names now, as the remote itself advertises
    them: anything reachable from one is public already, `refs/pull/*` included."""
    listed = git("ls-remote", "--end-of-options", remote).decode("utf-8", "replace")
    return [line.split("\t", 1)[0] for line in listed.splitlines() if line.strip()]


def push_updates(updates: str) -> list[tuple[str, str, str]]:
    """git's pre-push input, a line `<local ref> <local object> <remote ref> <remote object>` for each ref
    pushed, as (local object, remote ref, remote object); a ref deleted has the local object 0."""
    found: list[tuple[str, str, str]] = []
    for line in updates.splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4 or not all(_OBJECT.fullmatch(name) for name in fields[1::2]):
            raise ScanError(f"not a line of git's pre-push input: {shown(line)!r}")
        found.append((fields[1], fields[2], fields[3]))
    return found


def pushed_objects(revisions: bytes) -> Iterator[tuple[str, str, bytes]]:
    """Each file content and annotated tag that `revisions` (`git rev-list --stdin`'s input) select, as `git
    rev-list --objects` lists what a push sends, by its kind (`blob` or `tag`), a name and its data. git names
    a content once though two files hold it, gives a tag its ref's name, and names a content directly under a
    tag, or at a path holding a line break, with nothing (`object <hash>` here); so a content's paths are read
    from the trees of the commits pushed, and it is given once for each kind of place it has there, by its
    first path of that kind, since `CLAUDE.md` may name what another file may not."""
    names: dict[str, str] = {}
    for line in names_of(git("rev-list", "--objects", "--stdin", stdin=revisions)).split("\n"):
        name, _, path = line.partition(" ")
        if _OBJECT.fullmatch(name):
            names.setdefault(name, path or f"object {name[:12]}")
    kinds = object_kinds(names)
    wanted = {name for name in names if kinds.get(name) in ("blob", "tag")}
    if not wanted:
        return
    paths: dict[str, set[str]] = {}
    for commit in git("rev-list", "--stdin", stdin=revisions).decode("ascii").split():
        for entry in names_of(git("ls-tree", "-r", "-z", "--full-tree", commit)).split("\0"):
            described, _, path = entry.partition("\t")
            if path and (name := described.split()[2]) in wanted:
                paths.setdefault(name, set()).add(path)
    batch = git("cat-file", "--batch", stdin=lines(name for name in names if name in wanted))
    at = 0
    while at < len(batch):
        header_end = batch.index(b"\n", at)
        name, kind, size = batch[at:header_end].decode("ascii").split()
        data = batch[header_end + 1 : header_end + 1 + int(size)]
        at = header_end + 1 + int(size) + 1
        if kind == "tag":
            yield kind, names[name], data
        else:
            first: dict[re.Pattern[str] | None, str] = {}
            for path in sorted(paths.get(name, {names[name]})):
                first.setdefault(ALLOWED_PATHS.get(path), path)
            for path in first.values():
                yield kind, path, data


def scan_push(scanner: Scanner, remote: str, updates: str) -> list[str]:
    """Each finding in what a push publishes: the names of the refs it writes, its files, its annotated tags
    and its commits' messages. A ref deleted publishes nothing, so that a name pushed by mistake can be taken
    down."""
    found: list[str] = []
    pushed: list[str] = []
    reported: list[str] = []
    for local, ref, remote_object in push_updates(updates):
        if not _NO_OBJECT.fullmatch(local):
            pushed.append(local)
            found += ref_findings(scanner, ref)
        if not _NO_OBJECT.fullmatch(remote_object):
            reported.append(remote_object)
    if not pushed:
        return found
    held = object_kinds([*reported, *advertised(remote)])
    revisions = lines([*pushed, *(f"^{name}" for name in held)])
    for kind, name, data in pushed_objects(revisions):
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        if kind == "blob":
            found += scanner.findings(f"{shown(name)} (pushed)", text, ALLOWED_PATHS.get(name))
        else:
            found += scanner.findings(f"tag {shown(name)}", text)
    for commit, message in commit_messages("--stdin", stdin=revisions):
        found += scanner.findings(f"commit {commit} message", message)
    return found


def standard_input() -> str:
    """Standard input, git's pre-push input, whose ref names are bytes, as `names_of` reads them."""
    raw = getattr(sys.stdin, "buffer", None)
    return names_of(raw.read()) if raw is not None else sys.stdin.read()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find private names and paths in tracked files and commits.")
    parser.add_argument("--key-file", type=Path, help=f"the key, instead of {KEY_VARIABLE}")
    scanned = parser.add_mutually_exclusive_group()
    scanned.add_argument("--messages", metavar="RANGE", help="scan the messages of the commits in RANGE too")
    scanned.add_argument(
        "--pre-push",
        metavar="REMOTE",
        help="scan what a push to REMOTE publishes, from git's pre-push input on standard input, instead",
    )
    parser.add_argument(
        "--ref-name", action="append", default=[], metavar="NAME", help="scan a ref's name too (repeatable)"
    )
    parser.add_argument(
        "--digest",
        action="store_true",
        help="write the digest file for the terms on standard input, one a line",
    )
    options = parser.parse_args(arguments)
    try:
        key = load_key(options.key_file)
        if options.digest:
            if key is None:
                raise ScanError("--digest needs the key")
            sys.stdout.write(digest_file(key, sys.stdin.read().splitlines()))
            return 0
        digests = read_digests(DIGESTS.read_text(encoding="utf-8"), key) if key else frozenset[str]()
        scanner = Scanner(key, digests)
        if options.pre_push is not None:
            if options.ref_name:
                raise ScanError(
                    "--ref-name is for the scan of the tracked files; --pre-push reads the refs pushed"
                )
            found = scan_push(scanner, options.pre_push, standard_input())
        else:
            found = scan(scanner, options.messages, options.ref_name)
    except ScanError as error:
        print(error, file=sys.stderr)
        return 2
    for finding in found:
        print(finding, file=sys.stderr)
    if key is None:
        print(
            f"warning: no key ({KEY_VARIABLE} or --key-file), so the confidential names were not checked; "
            "the private paths were",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
