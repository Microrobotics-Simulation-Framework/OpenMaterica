# SPDX-License-Identifier: Apache-2.0
"""Fail where a tracked file or a commit message names one of the maintainer's private projects, or carries a
private path.

    python scripts/check_confidential.py [--key-file KEY] [--messages RANGE]
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


def git(*arguments: str) -> bytes:
    try:
        return subprocess.run(["git", *arguments], capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as error:
        raise ScanError(
            f"git {' '.join(arguments)}: {error.stderr.decode(errors='replace').strip()}"
        ) from error


def tracked_texts() -> Iterator[tuple[str, str]]:
    """Each tracked file of the working tree that is text, by its path: one holding a NUL byte is binary."""
    root = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    for name in git("-C", str(root), "ls-files", "-z").decode("utf-8").split("\0"):
        path = root / name
        if name and path.is_file():
            data = path.read_bytes()
            if b"\0" not in data:
                yield name, data.decode("utf-8", errors="replace")


def commit_messages(revisions: str) -> Iterator[tuple[str, str]]:
    """Each commit's message in `revisions`, as `git log` reads them, by its shortened hash."""
    for entry in (
        git("log", "-z", "--format=%H%n%B", "--end-of-options", revisions).decode("utf-8").split("\0")
    ):
        commit, _, message = entry.partition("\n")
        if commit:
            yield commit[:12], message


def scan(scanner: Scanner, revisions: str | None) -> list[str]:
    found: list[str] = []
    for name, text in tracked_texts():
        found += scanner.findings(name, text, ALLOWED_PATHS.get(name))
    for commit, message in commit_messages(revisions) if revisions else ():
        found += scanner.findings(f"commit {commit} message", message)
    return found


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find private names and paths in tracked files and commits.")
    parser.add_argument("--key-file", type=Path, help=f"the key, instead of {KEY_VARIABLE}")
    parser.add_argument("--messages", metavar="RANGE", help="scan the messages of the commits in RANGE too")
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
        found = scan(Scanner(key, digests), options.messages)
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
