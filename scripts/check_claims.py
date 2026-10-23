# SPDX-License-Identifier: Apache-2.0
"""Check what a branch claims against git, the measurements recorded and the maintainer's rulings
(CONTRIBUTING, "Before asking for review").

    python scripts/check_claims.py check [BASE] [--head REV] [--description FILE] [--facts F] [--rulings F]
    python scripts/check_claims.py record VALUE WHAT --how HOW [--at REV] [--facts FILE]
    python scripts/check_claims.py baseline [--at REV]

The branch runs from the merge base of `BASE` (`origin/main`) and `--head` (`HEAD`) to that head, read from
its commits, never the working tree. Three checks:

1. Git facts, in the description and the branch's commit messages. A commit name (7 to 40 hexadecimal digits,
   a letter and a digit among them) names one commit, on the branch or on `BASE`, unless its sentence names a
   pull request (`#N`). One called the head (`head X`, `Head: X`, `head is now X`, `head (X)`, after any word
   but one naming another head: `earlier`, `old`, `previous`, `rebase`, `review`, a possessive such as
   `#77's`) is the head; one called the base (`base X`, `the base is X`, `merge base X`, `main's X`, `N
   commits on main at X`, `rebased onto main at X`, `based on main at X`, `draft, on main at X`) is the merge
   base. A count of the branch's commits (`N commits on main`, `N commits on top of main`, a sentence that
   opens `N commits,` or `N commits:`, `the N commits`, `the same N commits`, `(N commits)`, `N commits on the
   branch`), git's `N files changed`, `N insertions(+)` and `N deletions(-)` (a rename one file, as git counts
   it), and a table with `Added` and `Removed` columns (and `Files`, where it has one; its row that opens
   `total`, with `N files` there, or else its column sums) equal git's over the branch. A quotation is not
   read.
2. Measured figures, in the description and the CHANGELOG lines the branch adds (a line moved whole is not
   added). A number that is no git fact and of no kind `kind` names (a numbered thing, a version, a flag, an
   identifier, a date, a value in a physical unit, a confidence level; anything in code, a link or quotation
   marks) matches a recorded fact: its value, and its `what` starting in the figure's own phrase (before the
   next number) among the eight words after it. The fact is measured at the head, or at an earlier commit of
   the head's after which only Markdown files changed (printed with the commits since); any other change since
   fails it. A number marked an estimate (a word of `ESTIMATE` just before it, or `estimate` after it within
   its phrase) needs none. A CHANGELOG figure the baseline holds (`claims_baseline.json`: what the check
   finds, with no fact, in the CHANGELOG at its commit `at`, on `main`; each figure by its three words either
   side, with its reason) passes while the CHANGELOG holds that key no more often than it did at `at`; the
   baseline holds only such figures, and `baseline` writes it. Anything else fails, and no option turns this
   part off. A fact matches every figure with its value and words: record words that tell two figures apart.
3. Ruled wording, given the rulings file (private: its path is given at run time, and nothing of it is
   printed but the words compared, without its bold markup or the maintainer's attribution). Where a run of a
   ruling's words and of a specification sentence the branch adds nearly match, they match word for word,
   case and punctuation aside; a difference prints both. A run is made of pieces of two words or more, apart
   by at most `MAX_GAP` words on both sides or by an insertion or deletion of at most `MAX_INSERT` words on
   one; it takes in one word more at either end where that word matches across such a gap, and runs on to its
   clause's end (or back to its start) where one side's clause ends within a word of the run and the other's
   within `MAX_INSERT`. It is compared where it holds `MIN_WORDS` words in common or more, and `NEAR` of the
   longer side. A line of the rulings file that reads `accepted wording: "..."` is no ruling: the words it
   quotes, landed otherwise on purpose, are not reported (and are counted).

Left to the reviewer: prose claims ("the bar is met"), counts written in words ("three controls"), whether a
figure counts what its words say, a ruling paraphrased beyond `NEAR`, a git fact in another form, and these
forms the rules read wrongly, rare in the merged descriptions and the CHANGELOG: an edit at the first or last
word of a run where the words beyond it are the text's own and no clause ends there (that word may belong to
the text's own wording around the ruling); a ratio such as `3.14 times`, read as a Python version; a clock
duration (`7:16`), not read; a year-like count after `in` (`in 1995 of 2000 runs`); a count of commits not the
branch's (`a test makes 260 commits`), read as a git fact; a count of eight digits or more without commas
(`12000000 examples`), read as a run's number; and `about N` where `about` means "concerning". A short commit
name is checked in the object store the check runs in: one that names two objects there may name one in a
fresh clone.
"""

import argparse
import difflib
import functools
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NamedTuple

BASELINE = Path(__file__).resolve().parent / "claims_baseline.json"
DEFAULT_BASE = "origin/main"
FACTS_NAME = "claims-facts.json"
SPECIFICATION = "docs/specification/"

UNITS: list[str] = [
    *"one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen".split(),
    *"sixteen seventeen eighteen nineteen".split(),
]
TENS: tuple[str, ...] = tuple("twenty thirty forty fifty sixty seventy eighty ninety".split())
COUNT = rf"(\d[\d,]*|(?:{'|'.join(TENS)})(?:-(?:{'|'.join(UNITS[:9])}))?|{'|'.join(UNITS)})"
NAMED = r"`?([0-9a-f]{7,40})`?(?![\w-])"
COMMIT_NAME = re.compile(r"(?<![\w/.-])`?([0-9a-f]{7,40})`?(?![\w/-])")
HEAD_OR_BASE = re.compile(
    r"\b(head|base)\b(?:\*\*)?:?(?:\*\*)?,?\s+(?:is\s+(?:now\s+)?|at\s+|commit\s+|=\s*)?\(?" + NAMED, re.I
)
MAINS = re.compile(r"`?(?:origin/)?main`?['\u2019]s\s+" + NAMED, re.I)
BASE_CLAIM = re.compile(
    r"\b(?:commits?|rebased|based|moved|draft|stacked),?(?:\s+from\s+`?[0-9a-f]{7,40}`?)?\s+(?:on|onto)\s+"
    r"`?(?:origin/)?main`?(?:'s|\s+at)?\s+" + NAMED,
    re.I,
)
# The word before `head` or `base` that names another one ("the earlier head", "#77's head").
ANOTHER = set("earlier old older previous prior former original first stale rebase review reviewed".split())
OWN = {"branch's", "request's", "pr's"}
OPENING = r"(?:^|[.!?]\s)\s*(?:[-*]\s+)?(?:\[[ x]\]\s+)?(?:\*\*)?"
COUNTS = [
    (
        "commits",
        rf"\b{COUNT}\s+commits,?\s+on\s+(?:top\s+of\s+)?(?:`?(?:origin/)?main\b|(?:the|this)\s+branch\b)",
    ),
    ("commits", rf"{OPENING}{COUNT}\s+commits?(?:\*\*)?(?=[,.:;]|\s+each)"),
    (
        "commits",
        rf"\b(?:the|all|all\s+the|each\s+of\s+the|the\s+same)\s+{COUNT}\s+commits?\b"
        r"(?!\s+(?:of|after|before|since)\b)",
    ),
    ("commits", rf"\(\s*{COUNT}\s+commits?\s*\)"),
    ("files", rf"\b{COUNT}\s+files?\s+changed\b"),
    ("added", rf"\b{COUNT}\s+insertions?\(\+\)"),
    ("removed", rf"\b{COUNT}\s+deletions?\(-\)"),
]
SENTENCE_END = re.compile(r"[.!?](?=\s)|\n\s*\n|\n(?=\s*(?:[-*+|]|\d+\.)\s)")
GIT_COUNTED = {"commit", "commits", "insertion", "insertions", "deletion", "deletions"}

MINUS = "\u2212"
APPROXIMATE = "~\u2248"
NUMBER = re.compile(
    rf"^[{APPROXIMATE}]?[-{MINUS}]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?(?:[eE][-{MINUS}]?\d+)?%?$"
)
# A word just before a number, or before a list of numbers joined by `and`, `or` and `to`, that numbers it;
# those of `DOTTED` also number a section or a version such as 4.1 or 3.11, the others a whole number only.
DOTTED = set(
    "section sections item items step steps point points question questions rule rules constraint "
    "constraints table tables figure figures equation equations page pages chapter principle principles "
    "version versions python pythons git uv pip hypothesis pytest usd-core mypy pyright ruff release dev rfc "
    "pep iso".split()
)
NUMBERED = DOTTED | set(
    "target targets seed seeds round rounds phase phases column columns row rows line lines level levels "
    "commit part parts case example issue issues pr run runs job shard arm arms stage stages piece pieces "
    "group groups".split()
)
LINKS = {"and", "or", "to", "through", ""}
FLAG = re.compile(r"^--?[A-Za-z][\w-]*$")
MONTHS = set("january february march april may june july august september october november december".split())
PHYSICAL = set("k \u00b0c \u00b0 pa kpa mpa gpa kg mg mm cm \u00b5m nm mol ml hz khz mhz m/s".split())
LEVEL = {"bound", "confidence", "one-sided", "two-sided", "interval"}
ESTIMATE = {"about", "around", "roughly", "approximately", "nearly", "almost", "estimated", *APPROXIMATE}
QUOTES = "\u201c\u201d\u2018\u2019"
STRIP = "`*_\"'()[]{},;:.!?<>|" + QUOTES
TRAILING = ",;:.!?)]}*\"'|" + QUOTES

QUOTED = rf"\"(?:[^\"\n]|\n(?!\s*\n)){{0,400}}\"|{QUOTES[0]}[^{QUOTES[1]}]{{0,400}}{QUOTES[1]}"
INTERVAL = rf"[\[(][-{MINUS}]?\d[\d.e{MINUS}-]*,\s*[-{MINUS}]?\d[\d.e{MINUS}-]*[\])]"
BLANKED = re.compile(rf"```.*?```|`[^`\n]*`|https?://\S+|\]\([^)]*\)|<!--.*?-->|{QUOTED}|{INTERVAL}", re.S)
BLANK = "\x00"

BREAK = "\u00b6"
MARKER = re.compile(r"^(?:[-*+>]|#+|\[[ x]\])$")

MIN_WORDS = 6
MAX_GAP = 3
MAX_INSERT = 8
NEAR = 0.7
# The rulings file's bold markup, the maintainer's attribution, a parenthesis naming a question by its label
# and an item's mark (`(7)`, `(a)`) end a ruling's sentence; a line naming an accepted wording is no ruling.
ATTRIBUTION = re.compile(
    r"\*\*|(?i:\((?:the\s+)?maintainer\b[^)]*\))|\([^()]*\b[A-Z][\w-]*Q\d+\b[^()]*\)"
    r"|(?<!\S)\((?:\d{1,2}|[A-Za-z])\)(?!\S)"
)
ACCEPTED = re.compile(r"accepted wording:\s*\"(.+)\"", re.I)

Word = tuple[str, str, int]


class ClaimsError(ValueError):
    pass


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], capture_output=True, text=True, check=True).stdout


def resolve(name: str) -> str | None:
    found = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"{name}^{{commit}}"], capture_output=True, text=True
    )
    return found.stdout.strip() or None


def ambiguous(name: str) -> bool:
    found = subprocess.run(["git", "rev-parse", f"--disambiguate={name}"], capture_output=True, text=True)
    return len(found.stdout.split()) > 1


def is_ancestor(commit: str, head: str) -> bool:
    return (
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, head], capture_output=True).returncode
        == 0
    )


@dataclass(frozen=True)
class Range:
    base: str
    head: str
    main: str = ""

    def count(self, kind: str) -> int:
        return counts(self.base, self.head)[kind]

    def holds(self, commit: str) -> bool:
        return is_ancestor(commit, self.head) or is_ancestor(commit, self.main or self.base)


@functools.cache
def counts(base: str, head: str) -> dict[str, int]:
    totals = {
        "commits": int(git("rev-list", "--count", f"{base}..{head}")),
        "files": 0,
        "added": 0,
        "removed": 0,
    }
    for line in git("diff", "--numstat", "--find-renames", base, head).splitlines():
        added, removed, _ = line.split("\t", 2)
        totals["files"] += 1
        totals["added"] += int(added) if added.isdigit() else 0
        totals["removed"] += int(removed) if removed.isdigit() else 0
    return totals


def number(text: str) -> int | None:
    text = text.lower().replace(",", "")
    tens, _, unit = text.partition("-")
    if text.isdigit():
        return int(text)
    if tens in TENS and (not unit or unit in UNITS[:9]):
        return 20 + 10 * TENS.index(tens) + (UNITS.index(unit) + 1 if unit else 0)
    return UNITS.index(text) + 1 if text in UNITS else None


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def sentence_of(text: str, offset: int) -> str:
    start = max((end.end() for end in SENTENCE_END.finditer(text, 0, offset)), default=0)
    stop = next((end.start() for end in SENTENCE_END.finditer(text, offset)), len(text))
    return text[start:stop]


def names_another(text: str, start: int) -> bool:
    """Whether the word before `head` or `base` at `start` names another one than the branch's."""
    previous = re.search(r"(\S+)\s*$", text[:start])
    if previous is None or previous.group(1).endswith((".", ",", ";", ":", "!", "?", "(", "|")):
        return False
    word = previous.group(1).lower().replace("`", "").strip("*_\"'()[]")
    return word in ANOTHER or (re.search(r"['\u2019]s$", word) is not None and word not in OWN)


def git_findings(text: str, place: str, span: Range) -> list[str]:
    """Check 1 over `text`, each finding as `place:line: what`. A quotation, someone else's claim, is not
    read."""
    found: list[str] = []
    text = re.sub(QUOTED, lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
    claims: dict[int, tuple[str, str]] = {}
    for match in HEAD_OR_BASE.finditer(text):
        if not names_another(text, match.start()):
            claims[match.start(2)] = (match.group(1).lower(), match.group(2))
    for claim in (MAINS, BASE_CLAIM):
        for match in claim.finditer(text):
            claims[match.start(1)] = ("base", match.group(1))
    for match in COMMIT_NAME.finditer(text):
        name, where = match.group(1), f"{place}:{line_of(text, match.start())}"
        if not (re.search("[a-f]", name) and re.search("[0-9]", name)) or match.start(1) in claims:
            continue
        commit = resolve(name)
        if commit is None:
            found.append(f"{where}: `{name}` names no commit here")
        elif len(name) < 40 and ambiguous(name):
            found.append(f"{where}: `{name}` names more than one object here")
        elif not span.holds(commit) and not re.search(r"#\d", sentence_of(text, match.start())):
            found.append(f"{where}: `{name}` is not on this branch or main")
    for offset, (which, name) in sorted(claims.items()):
        expected = span.head if which == "head" else span.base
        if (resolve(name) or name) != expected:
            found.append(f"{place}:{line_of(text, offset)}: the {which} is `{expected[:8]}`, not `{name}`")
    stated: dict[int, tuple[str, str]] = {}
    for kind_, pattern in COUNTS:
        for match in re.finditer(pattern, text, re.I | re.M):
            stated.setdefault(match.start(1), (kind_, match.group(1)))
    for table in tables(text.split("\n")):
        stated.update(table_counts(text, table))
    for offset, (kind_, value) in sorted(stated.items()):
        if number(value) != span.count(kind_):
            line = line_of(text, offset)
            found.append(f"{place}:{line}: {value} {kind_}, where git counts {span.count(kind_)}")
    return found


def cells(row: str) -> list[str]:
    return [cell.strip(" *`") for cell in row.strip().strip("|").split("|")]


def tables(lines: list[str]) -> Iterator[range]:
    """The lines of each Markdown table with `Added` and `Removed` columns."""
    start = 0
    while start < len(lines):
        end = start
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        if end - start > 2 and {"added", "removed"} <= {cell.lower() for cell in cells(lines[start])}:
            yield range(start, end)
        start = max(end, start + 1)


def table_counts(text: str, table: range) -> dict[int, tuple[str, str]]:
    """What a table of lines added and removed (and of files, where it has the column) states: its total
    row, or else its column sums."""
    lines = text.split("\n")
    offset = len("\n".join(lines[: table.start])) + 1
    header = [cell.lower() for cell in cells(lines[table.start])]
    body = [cells(lines[index]) for index in table[2:]]
    totals = [row for row in body if row[0].lower().startswith("total")]
    stated: dict[int, tuple[str, str]] = {}
    for step, kind_ in enumerate(kind_ for kind_ in ("added", "removed", "files") if kind_ in header):
        column = header.index(kind_)
        values = [number(row[column]) if column < len(row) else None for row in totals or body]
        if None not in values:
            stated[offset + step] = (kind_, str(sum(value or 0 for value in values)))
    files = re.search(r"(\d[\d,]*)\s+files?\b", totals[0][0]) if totals else None
    if files:
        stated[offset + 3] = ("files", files.group(1))
    return stated


class Token(NamedTuple):
    line: int
    text: str
    leading: bool  # the first on its line, after list or quotation markers
    cut: bool  # code, a link, a quotation or an interval lies just before it


@dataclass(frozen=True)
class Figure:
    line: int
    text: str
    before: tuple[str, ...]
    after: tuple[str, ...]

    def key(self) -> str:
        """The figure by its three words either side, as the baseline holds it."""
        return " ".join(word for word in (*self.before[-3:], normalised(self.text), *self.after[:3]) if word)


def normalised(token: str) -> str:
    word = token.lower().strip(STRIP)
    return word.replace(",", "") if NUMBER.match(word) else word


def prose(text: str) -> str:
    """`text` with code, links, quotations and intervals blanked to `BLANK` and the tables of check 1 emptied,
    lines kept."""
    lines = BLANKED.sub(lambda match: re.sub(r"[^\n]", BLANK, match.group(0)), text).split("\n")
    for table in tables(text.split("\n")):
        for index in table:
            lines[index] = ""
    return "\n".join(lines)


def figures(text: str, lines: set[int] | None = None) -> tuple[list[Figure], dict[str, int]]:
    """The figures of `text`, on `lines` alone where given, that a fact must match; and how many numbers each
    reason of `kind` left out. A figure's words stop at its paragraph or list item."""
    tokens: list[Token] = []
    cut = False  # a blanked span at the end of a line cuts the next line's first word from the words before
    for line, row in enumerate(prose(text).split("\n"), 1):
        if not row.replace(BLANK, " ").strip() or re.match(r"\s*(?:[-*+]|\d+\.)\s", row):
            tokens.append(Token(line, BREAK, False, False))
        leading = True
        for piece in re.finditer(rf"[^\s{BLANK}]+|{BLANK}+", row):
            if piece.group().startswith(BLANK):
                cut = True
                continue
            tokens.append(Token(line, piece.group(), leading, cut))
            leading, cut = leading and MARKER.match(piece.group()) is not None, False
    words = ["" if token.leading and MARKER.match(token.text) else normalised(token.text) for token in tokens]
    found: list[Figure] = []
    left: dict[str, int] = {}
    for index, token in enumerate(tokens):
        bare = token.text.strip(TRAILING).lstrip("(*[")
        if (lines is not None and token.line not in lines) or not NUMBER.match(bare):
            continue
        following = tuple(word for word in words[index + 1 : index + 9] if word)
        following = following[: following.index(BREAK)] if BREAK in following else following
        before = tuple(words[max(0, index - 3) : index])
        why = kind(tokens, words, index, following)
        if why:
            left[why] = left.get(why, 0) + 1
        else:
            found.append(
                Figure(
                    token.line,
                    bare,
                    before[before.index(BREAK) + 1 :] if BREAK in before else before,
                    following,
                )
            )
    return found, left


def opens(token: Token) -> bool:
    """Whether a parenthesis or a blanked span opens `token`, so that no word before it numbers it."""
    return token.cut or token.text.lstrip("*").startswith("(")


def opens_sentence(tokens: list[Token], index: int) -> bool:
    return (
        index == 0
        or tokens[index].leading
        or tokens[index - 1].text == BREAK
        or tokens[index - 1].text.endswith((".", "!", "?", ":"))
    )


def opens_clause(tokens: list[Token], index: int) -> bool:
    """Whether the token at `index` opens a clause, as an item's mark does: "(1) the first; (2) ..."."""
    previous = tokens[index - 1] if index else None
    return (
        previous is None
        or previous.text == BREAK
        or previous.text.endswith((":", ";", ".", "!", "?"))
        or (previous.leading and MARKER.match(previous.text) is not None)
    )


def kind(tokens: list[Token], words: list[str], index: int, following: tuple[str, ...]) -> str:
    """Why the number at `index` needs no fact, or "" where it needs one."""
    raw = tokens[index].text.strip("*")
    bare = raw.strip(TRAILING).lstrip("(*[")
    # The word that names the number, through a list of numbers ("items 1, 2 and 4") but not across the end
    # of a phrase ("in section 2: 1,180 files", "the fast stage, 15 of 15"), a parenthesis or code.
    before, cut = index - 1, opens(tokens[index])
    while not cut and before >= 0 and not tokens[before].text.rstrip(",").endswith((";", ":", ".", ")")):
        if words[before] not in LINKS and not NUMBER.match(words[before]):
            break
        cut = opens(tokens[before])
        before -= 1
    ended = cut or before < 0 or tokens[before].text.endswith((",", ";", ":", ".", ")"))
    first = next((place for place in range(before + 1, index) if words[place]), index)
    listed = first == index or NUMBER.match(words[first]) is not None  # "figures and 6 settings" is no list
    named = "" if ended or not listed else words[before]
    if named in NUMBERED and "." in bare and (named not in DOTTED or bare.startswith("0.")):
        named = ""  # "the shard 0.72 to 0.79 of its CPU", "the slowest part 67.4"
    previous = tokens[index - 1].text.lstrip("([*") if index else ""
    prior = words[index - 1] if index else ""  # "about 45 s", not "a note about the 12 files"
    if (re.match(r"^\(\d+\)", raw) and opens_clause(tokens, index)) or (
        tokens[index].leading and re.match(r"^\d+[.)]$", raw)
    ):
        return "a list or heading number"
    if re.match(r"^(?:19\d\d|20[0-3]\d)$", bare) and (
        named in MONTHS
        or previous == "in"
        or re.match(r"^\(\d{4}\)", raw)
        or (previous[:1].isupper() and not opens_sentence(tokens, index - 1))
    ):
        return "a year"
    if named in NUMBERED or FLAG.match(previous) or re.match(r"^3\.1\d$", bare):
        return "a numbered thing, a version or a flag"
    if re.match(r"^\d{8,}$", bare):
        return "a run's or a job's number"
    counted = re.sub(r"\(.*", "", following[0]) if following else ""
    if counted in GIT_COUNTED or following[:2] in {("file", "changed"), ("files", "changed")}:
        return "a git fact"
    if following[:1] and following[0] in PHYSICAL:
        return "a value in a physical unit"
    if LEVEL & set(following[:3]) and (bare.endswith("%") or following[:1] == ("%",)):
        return "a confidence level"
    if bare[0] in APPROXIMATE or named in ESTIMATE or prior in ESTIMATE:
        return "an estimate"
    place = index  # `estimate` after the number, within its phrase: "55 minutes by estimate"
    while place < min(len(tokens) - 1, index + 5) and not tokens[place].text.endswith(
        (",", ";", ":", ".", "!", "?")
    ):
        place += 1
        if words[place] in {"estimate", "estimated"}:
            return "an estimate"
        if NUMBER.match(words[place]) or tokens[place].text == BREAK:
            break
    return ""


@dataclass(frozen=True)
class Fact:
    value: Decimal
    what: tuple[str, ...]
    at: str


def decimal(text: str) -> Decimal:
    try:
        return Decimal(text.lstrip(APPROXIMATE).replace(",", "").replace(MINUS, "-").rstrip("%"))
    except InvalidOperation as error:
        raise ClaimsError(f"{text!r} is not a number") from error


def load_facts(path: Path) -> list[Fact]:
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["facts"]
        return [
            Fact(
                decimal(entry["value"]),
                tuple(normalised(word) for word in entry["what"].split()),
                entry["at"],
            )
            for entry in entries
        ]
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ClaimsError(f"{path} is not a facts file: {error}") from error


@functools.cache
def since(commit: str, head: str) -> tuple[int, tuple[str, ...]]:
    """The commits from `commit` to `head`, and the files they change that are not Markdown."""
    changed = git("diff", "--name-only", "--find-renames", commit, head).split()
    return int(git("rev-list", "--count", f"{commit}..{head}")), tuple(
        path for path in changed if not path.endswith(".md")
    )


def figure_findings(
    text: str,
    place: str,
    span: Range,
    facts: list[Fact],
    lines: set[int] | None = None,
    baseline: dict[str, int] | None = None,
) -> tuple[list[str], dict[str, int], list[str]]:
    """Check 2 over `text`: the findings; how many figures a fact matched, the baseline held and an estimate
    marked; and, for each figure a fact measured before the head holds, the commits since."""
    found: list[str] = []
    notes: list[str] = []
    stated, left = figures(text, lines)
    held: Counter[str] = Counter(figure.key() for figure in figures(text)[0] if baseline is not None)
    tally = {"matched": 0, "baseline": 0, "estimates": left.get("an estimate", 0)}
    for figure in stated:
        phrase = next((at for at, word in enumerate(figure.after) if NUMBER.match(word)), len(figure.after))
        matching = [
            fact
            for fact in facts
            if decimal(figure.text) == fact.value
            and any(
                figure.after[start : start + len(fact.what)] == fact.what for start in range(max(phrase, 1))
            )
        ]
        about = f"{figure.text} ({' '.join(figure.after[:4])} ...)"
        earlier = sorted(
            (since(fact.at, span.head), fact.at) for fact in matching if is_ancestor(fact.at, span.head)
        )
        markdown = [(commits, at) for (commits, changed), at in earlier if not changed]
        if baseline is not None and held[figure.key()] <= baseline.get(figure.key(), 0):
            tally["baseline"] += 1
        elif not matching:
            found.append(f"{place}:{figure.line}: {about} matches no recorded fact")
        elif not earlier:
            found.append(f"{place}:{figure.line}: {about} was measured at a commit the head does not hold")
        elif markdown:
            tally["matched"] += 1
            commits, at = markdown[0]
            if commits:
                notes.append(
                    f"{place}:{figure.line}: {about} was measured at `{at[:8]}`, {commits} commits "
                    "before the head, which change Markdown files alone"
                )
        else:
            (commits, changed), at = earlier[0]
            found.append(
                f"{place}:{figure.line}: {about} was measured at `{at[:8]}`, {commits} commits before the "
                f"head, which change {len(changed)} files that are not Markdown: {', '.join(changed[:5])}"
            )
    return found, tally, notes


def added_lines(span: Range, path: str) -> dict[str, set[int]]:
    """The lines each file under `path` gains on the branch, numbered as at the head."""
    added: dict[str, set[int]] = {}
    current = ""
    for line in git("diff", "--no-renames", "-U0", span.base, span.head, "--", path).splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        hunk = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if hunk and current:
            first, length = int(hunk.group(1)), int(hunk.group(2) or 1)
            added.setdefault(current, set()).update(range(first, first + length))
    return added


def new_lines(span: Range, path: str, text: str) -> set[int]:
    """The lines the branch adds to `path` (whose text at the head is `text`), but for lines moved whole: a
    line's text the base holds as often."""
    before = subprocess.run(["git", "show", f"{span.base}:{path}"], capture_output=True, text=True).stdout
    rows = text.split("\n")
    there, here = Counter(row.strip() for row in before.split("\n")), Counter(row.strip() for row in rows)
    added = added_lines(span, path).get(path, set())
    return {line for line in added if here[rows[line - 1].strip()] > there[rows[line - 1].strip()]}


def load_baseline(span: Range) -> dict[str, int]:
    """Each key the baseline holds, with how often the CHANGELOG held it at the baseline's commit, after
    checking that each entry is a figure there, with a listed reason, and that the commit is on `main`."""
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))
    at = resolve(stored["at"])
    if at is None or not (is_ancestor(at, span.main or span.base) or is_ancestor(at, DEFAULT_BASE)):
        raise ClaimsError(f"the baseline's commit {stored['at']} is not on main here")
    there: dict[str, list[int]] = {}
    for figure in figures(git("show", f"{at}:CHANGELOG.md"))[0]:
        there.setdefault(figure.key(), []).append(figure.line)
    for key, line, reason in stored["changelog"]:
        if line not in there.get(key, []):
            raise ClaimsError(
                f"the baseline holds {key!r} at line {line}, where CHANGELOG.md at {at[:8]} has no such "
                "figure"
            )
        if reason not in stored["reasons"]:
            raise ClaimsError(
                f"the baseline holds {key!r} with the reason {reason!r}, which it does not list"
            )
    return {key: len(there[key]) for key, _, _ in stored["changelog"]}


def write_baseline(at: str | None) -> int:
    """Write the baseline from the CHANGELOG at `at` (by default the baseline's own commit), keeping each kept
    figure's reason; a new figure's reason is "unlabelled" until a person labels it."""
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))
    commit = resolve(at or stored["at"])
    if commit is None:
        raise ClaimsError(f"cannot resolve {at or stored['at']}")
    reasons = {key: reason for key, _, reason in stored["changelog"]}
    entries: dict[str, list[object]] = {}
    for figure in figures(git("show", f"{commit}:CHANGELOG.md"))[0]:
        entries.setdefault(figure.key(), [figure.key(), figure.line, reasons.get(figure.key(), "unlabelled")])
    head = {"about": stored["about"], "at": commit, "reasons": stored["reasons"]}
    rows = ",\n".join("    " + json.dumps(entry, ensure_ascii=False) for entry in entries.values())
    text = json.dumps(head, indent=2, ensure_ascii=False)[:-2] + f',\n  "changelog": [\n{rows}\n  ]\n}}\n'
    BASELINE.write_text(text, encoding="utf-8")
    labelled = sum(entry[2] != "unlabelled" for entry in entries.values())
    print(
        f"wrote {len(entries)} entries at {commit[:8]}, {len(entries) - labelled} unlabelled, to {BASELINE}"
    )
    return 0


def sentences(text: str) -> Iterator[list[Word]]:
    """Each sentence of `text` as its words (compared form, as written, line), split at a sentence's end, a
    semicolon, a list item, a blank line and a table cell."""
    sentence: list[Word] = []
    for line, row in enumerate(text.split("\n"), 1):
        if (not row.strip() or re.match(r"\s*(?:[-*]|\d+\.)\s", row)) and sentence:
            yield sentence
            sentence = []
        for token in row.split():
            word = token.lower().strip(STRIP)
            if word:
                sentence.append((word, token, line))
            if (token == "|" or token.endswith((".", ";", "?", "!"))) and sentence:
                yield sentence
                sentence = []
    if sentence:
        yield sentence


def added_sentences(span: Range) -> list[tuple[str, list[Word]]]:
    """The specification's sentences the branch adds: on a line it adds, and not in that file at the base."""
    found: list[tuple[str, list[Word]]] = []
    for path, lines in added_lines(span, SPECIFICATION).items():
        before = subprocess.run(["git", "show", f"{span.base}:{path}"], capture_output=True, text=True).stdout
        kept = {tuple(word for word, _, _ in sentence) for sentence in sentences(before)}
        for sentence in sentences(git("show", f"{span.head}:{path}")):
            if (
                any(line in lines for *_, line in sentence)
                and tuple(word for word, _, _ in sentence) not in kept
            ):
                found.append((path, sentence))
    return found


def trigrams(sentence: list[Word]) -> set[tuple[str, ...]]:
    return {tuple(word for word, _, _ in sentence[index : index + 3]) for index in range(len(sentence) - 2)}


def ruling_findings(rulings: str, added: list[tuple[str, list[Word]]]) -> tuple[list[str], int]:
    """Check 3: each run of a ruling's words that an added specification sentence nearly matches, not word for
    word, and how many differences an accepted wording holds. Two sentences are compared where they share two
    runs of three words."""
    accepted = [
        [word for word, _, _ in words]
        for match in ACCEPTED.finditer(rulings)
        for words in sentences(match.group(1))
    ]
    rulings = "\n".join(
        "" if ACCEPTED.search(row) else ATTRIBUTION.sub("\n\n", row) for row in rulings.split("\n")
    )
    index: dict[tuple[str, ...], set[int]] = {}
    for position, (_, sentence) in enumerate(added):
        for trigram in trigrams(sentence):
            index.setdefault(trigram, set()).add(position)
    found: set[str] = set()
    waived: set[str] = set()
    for ruled in sentences(rulings):
        shared: dict[int, int] = {}
        for trigram in trigrams(ruled):
            for position in index.get(trigram, ()):
                shared[position] = shared.get(position, 0) + 1
        for position in (position for position, count in shared.items() if count >= 2):
            path, sentence = added[position]
            for ours, theirs in near_runs(ruled, sentence):
                finding = (
                    f"{path}:{theirs[0][2]}: a ruled sentence differs: the ruling has "
                    f'"{" ".join(token for _, token, _ in ours)}", this line '
                    f'"{" ".join(token for _, token, _ in theirs)}"'
                )
                (waived if any(within(theirs, words) for words in accepted) else found).add(finding)
    return sorted(found), len(waived)


def within(run: list[Word], words: list[str]) -> bool:
    compared = [word for word, _, _ in run]
    return any(words[start : start + len(compared)] == compared for start in range(len(words)))


def ends_clause(token: str) -> bool:
    return token.rstrip("`*_\"')]}" + QUOTES).endswith((",", ";", ":", ".", "!", "?"))


def to_clause_start(words: list[Word], start: int) -> int:
    back = 0
    while start - back > 0 and not ends_clause(words[start - back - 1][1]):
        back += 1
    return back


def to_clause_end(words: list[Word], end: int) -> int:
    on = 0
    while end + on < len(words) and not ends_clause(words[end + on - 1][1]):
        on += 1
    return on


def joins(left: difflib.Match, right: difflib.Match, gap: int) -> bool:
    """Whether two matching pieces belong to one run: apart by at most `gap` words on both sides, or by an
    insertion or a deletion of at most `MAX_INSERT` words."""
    apart = (right.a - left.a - left.size, right.b - left.b - left.size)
    return max(apart) <= gap or (min(apart) == 0 and max(apart) <= MAX_INSERT)


def near_runs(ruled: list[Word], sentence: list[Word]) -> Iterator[tuple[list[Word], list[Word]]]:
    """The runs of `ruled` and `sentence` that nearly match and differ."""
    matcher = difflib.SequenceMatcher(
        None, [w for w, _, _ in ruled], [w for w, _, _ in sentence], autojunk=False
    )
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    chains: list[list[difflib.Match]] = []
    for block in (block for block in blocks if block.size > 1):
        if chains and joins(chains[-1][-1], block, MAX_GAP):
            chains[-1].append(block)
        else:
            chains.append([block])
    for chain in chains:
        first, last = blocks.index(chain[0]), blocks.index(chain[-1])
        start, end = (chain[0].a, chain[0].b), (chain[-1].a + chain[-1].size, chain[-1].b + chain[-1].size)
        common = sum(block.size for block in chain)
        # Each step outward is taken only where the run stays near: a word that would make it far is not its.
        if first and blocks[first - 1].size == 1 and joins(blocks[first - 1], chain[0], 1):
            start, end, common = taken(start, end, common, (blocks[first - 1].a, blocks[first - 1].b), end, 1)
        if last + 1 < len(blocks) and blocks[last + 1].size == 1 and joins(chain[-1], blocks[last + 1], 1):
            further = (blocks[last + 1].a + 1, blocks[last + 1].b + 1)
            start, end, common = taken(start, end, common, start, further, 1)
        back = (to_clause_start(ruled, start[0]), to_clause_start(sentence, start[1]))
        if max(back) <= 1:
            start, end, common = taken(start, end, common, (start[0] - back[0], start[1] - back[1]), end, 0)
        on = (to_clause_end(ruled, end[0]), to_clause_end(sentence, end[1]))
        if min(on) <= 1 and max(on) <= MAX_INSERT:
            start, end, common = taken(start, end, common, start, (end[0] + on[0], end[1] + on[1]), 0)
        ours, theirs = ruled[start[0] : end[0]], sentence[start[1] : end[1]]
        if (
            common >= MIN_WORDS
            and near(start, end, common)
            and [w for w, _, _ in ours] != [w for w, _, _ in theirs]
        ):
            yield ours, theirs


def near(start: tuple[int, int], end: tuple[int, int], common: int) -> bool:
    return common >= NEAR * max(end[0] - start[0], end[1] - start[1])


def taken(
    start: tuple[int, int],
    end: tuple[int, int],
    common: int,
    wider: tuple[int, int],
    further: tuple[int, int],
    more: int,
) -> tuple[tuple[int, int], tuple[int, int], int]:
    """The run widened to `wider` and `further`, with `more` words in common, where it stays near."""
    return (wider, further, common + more) if near(wider, further, common + more) else (start, end, common)


def check(options: argparse.Namespace) -> int:
    head, base = resolve(options.head), resolve(options.base)
    if head is None or base is None:
        raise ClaimsError(f"cannot resolve {options.head if head is None else options.base}")
    span = Range(git("merge-base", base, head).strip(), head, base)
    facts_path = options.facts or default_facts()
    facts = load_facts(facts_path)
    found: list[str] = []
    notes: list[str] = []
    tally = {"matched": 0, "baseline": 0, "estimates": 0}
    texts: list[tuple[str, str, set[int] | None, dict[str, int] | None]] = []
    if options.description:
        text = options.description.read_text(encoding="utf-8")
        found += git_findings(text, str(options.description), span)
        texts.append((text, str(options.description), None, None))
    for entry in git("log", "--format=%H%x00%B%x1e", f"{span.base}..{span.head}").split("\x1e"):
        name, _, message = entry.strip("\n").partition("\x00")
        if name:
            found += git_findings(message, f"commit {name[:8]}, message", span)
    baseline = load_baseline(span)
    changelog = subprocess.run(
        ["git", "show", f"{span.head}:CHANGELOG.md"], capture_output=True, text=True
    ).stdout
    added = new_lines(span, "CHANGELOG.md", changelog)
    if added:
        texts.append((changelog, "CHANGELOG.md", added, baseline))
    for text, place, lines, known in texts:
        more, counted, noted = figure_findings(text, place, span, facts, lines, known)
        found += more
        notes += noted
        tally = {name: tally[name] + counted[name] for name in tally}
    waived = 0
    if options.rulings:
        more, waived = ruling_findings(options.rulings.read_text(encoding="utf-8"), added_sentences(span))
        found += more
    print("\n".join(found) if found else "no claim found that git, the facts or the rulings contradict")
    for note in notes:
        print(f"measured before the head: {note}")
    matched, estimates, held = tally["matched"], tally["estimates"], tally["baseline"]
    print(
        f"figures: {matched} matched a fact of the {len(facts)} in {facts_path}, {estimates} marked "
        f"estimates, {held} in the CHANGELOG's baseline; {len(found)} findings"
    )
    if not options.rulings:
        print("the ruled wording was not checked: no rulings file was given (--rulings)")
    elif waived:
        print(f"the ruled wording: {waived} differences the rulings file accepts")
    return 1 if found else 0


def default_facts() -> Path:
    return Path(git("rev-parse", "--git-path", FACTS_NAME).strip()).resolve()


def record(options: argparse.Namespace) -> int:
    decimal(options.value)
    what, how, at = options.what.strip(), options.how.strip(), resolve(options.at)
    if not what or not how or at is None:
        raise ClaimsError(
            "a fact needs what follows the figure, how it was measured and a commit it was measured at"
        )
    path = options.facts or default_facts()
    facts: list[object] = json.loads(path.read_text(encoding="utf-8"))["facts"] if path.exists() else []
    recorded = datetime.now(UTC).isoformat(timespec="seconds")
    facts.append({"value": options.value, "what": what, "how": how, "at": at, "recorded": recorded})
    path.write_text(json.dumps({"facts": facts}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded {options.value} {what}, measured at {at[:8]}, in {path}")
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a branch's claims against git, facts and rulings.")
    commands = parser.add_subparsers(dest="command", required=True)
    checking = commands.add_parser("check", help="check the branch's claims")
    checking.add_argument(
        "base", nargs="?", default=DEFAULT_BASE, help=f"the base, {DEFAULT_BASE} by default"
    )
    checking.add_argument("--head", default="HEAD", help="the head, HEAD by default")
    checking.add_argument("--description", type=Path, help="the pull request's description, in a file")
    checking.add_argument("--rulings", type=Path, help="the rulings file")
    recording = commands.add_parser("record", help="record a measured figure as a fact")
    recording.add_argument("value", help="the figure as stated")
    recording.add_argument("what", help="the words after it where it is stated, such as 'case files pass'")
    recording.add_argument(
        "--how", required=True, help="how it was measured: the command, and what it printed"
    )
    recording.add_argument("--at", default="HEAD", help="the commit measured, HEAD by default")
    for command in (checking, recording):
        command.add_argument(
            "--facts", type=Path, help=f"the facts file, the git directory's {FACTS_NAME} by default"
        )
    writing = commands.add_parser(
        "baseline", help="write claims_baseline.json from the CHANGELOG at a commit"
    )
    writing.add_argument("--at", help="the commit on main, the baseline's own by default")
    options = parser.parse_args(arguments)
    try:
        if options.command == "baseline":
            return write_baseline(options.at)
        return check(options) if options.command == "check" else record(options)
    except (ClaimsError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else error
        print(f"check_claims: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
