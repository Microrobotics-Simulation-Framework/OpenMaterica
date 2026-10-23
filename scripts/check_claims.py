# SPDX-License-Identifier: Apache-2.0
"""Check what a branch claims against git, the measurements recorded and the maintainer's rulings
(CONTRIBUTING, "Before asking for review").

    python scripts/check_claims.py check [BASE] [--head REV] [--description FILE] [--facts F] [--rulings F]
    python scripts/check_claims.py record VALUE WHAT --how HOW [--at REV] [--facts FILE]

The branch runs from the merge base of `BASE` (`origin/main`) and `--head` (`HEAD`) to that head, read from
its commits, never the working tree. Three checks:

1. Git facts, in the description and the branch's commit messages. A commit name (7 to 40 hexadecimal digits,
   a letter and a digit among them) resolves to a commit; one called the head (`head X`, `the head X`) is the
   head, one called the base (`N commits on main at X`, `main's X`, `rebased onto main at X`, `based on main
   at X`, `draft, on main at X`) is the merge base. A count of the branch's commits (`N commits on main`, a
   sentence that opens `N commits,` or `N commits:`, `the N commits`, `N commits on the branch`), git's `N
   files changed`, `N insertions(+)` and `N deletions(-)`, and a table with `Added` and `Removed` columns (and
   `Files`, where it has one; its row that opens `total`, with `N files` there, or else its column sums) equal
   git's over the branch. A quotation is not read.
2. Measured figures, in the description and the CHANGELOG lines the branch adds. A number that is no git
   fact and of no kind `kind` names (a numbered thing, a version, a flag, an identifier, a date, a value in a
   physical unit, a confidence level; anything in code, a link or quotation marks) matches a recorded fact:
   its value, and its `what` among the eight words after it, measured at a commit the head holds. A number
   marked an estimate (a word of `ESTIMATE` before it, or `estimate` among the five words after it) needs
   none. A CHANGELOG figure the baseline (`claims_baseline.json`: what the check found in the CHANGELOG as it
   stood, each with its reason) holds, by its three words either side, was there before; anything else
   fails, and no option turns this off.
3. Ruled wording, given the rulings file (private: its path is given at run time, and nothing of it is
   printed but the words compared). Where a run of a ruling's words and of a specification sentence the
   branch adds nearly match (`MIN_WORDS` words in common or more, in pieces of two words or more apart by at
   most `MAX_GAP`, and `NEAR` of the longer run), they match word for word, case and punctuation aside; a
   difference prints both.

Left to the reviewer: prose claims ("the bar is met"), counts written in words ("three controls"), whether a
figure counts what its words say, a ruling paraphrased beyond `NEAR`, and a git fact in another form.
"""

import argparse
import difflib
import functools
import json
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

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
HEAD_CLAIM = re.compile(r"(?:^|[(,;:]\s*|\b(?:the|this|its)\s+)head\s+(?:is\s+|at\s+)?" + NAMED, re.I | re.M)
BASE_CLAIM = re.compile(
    r"\b(?:commits?|rebased|based|moved|draft|stacked),?(?:\s+from\s+`?[0-9a-f]{7,40}`?)?\s+(?:on|onto)\s+"
    r"`?(?:origin/)?main`?(?:'s|\s+at)?\s+" + NAMED,
    re.I,
)
OPENING = r"(?:^|[.!?]\s)\s*(?:[-*]\s+)?(?:\[[ x]\]\s+)?(?:\*\*)?"
COUNTS = [
    ("commits", rf"\b{COUNT}\s+commits?,?\s+on\s+(?:`?(?:origin/)?main\b|(?:the|this)\s+branch\b)"),
    ("commits", rf"{OPENING}{COUNT}\s+commits?(?:\*\*)?(?=[,.:;]|\s+each)"),
    (
        "commits",
        rf"\b(?:the|all|all\s+the|each\s+of\s+the)\s+{COUNT}\s+commits?\b(?!\s+(?:of|after|before|since)\b)",
    ),
    ("files", rf"\b{COUNT}\s+files?\s+changed\b"),
    ("added", rf"\b{COUNT}\s+insertions?\(\+\)"),
    ("removed", rf"\b{COUNT}\s+deletions?\(-\)"),
]
GIT_COUNTED = {"commit", "commits", "insertion", "insertions", "deletion", "deletions"}

MINUS = "\u2212"
APPROXIMATE = "~\u2248"
NUMBER = re.compile(
    rf"^[{APPROXIMATE}]?[-{MINUS}]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?(?:[eE][-{MINUS}]?\d+)?%?$"
)
# A word just before a number, or before a list of numbers joined by `and`, `or` and `to`, that numbers it.
NUMBERED = set(
    "section sections item items step steps point points question questions rule rules constraint "
    "constraints target targets seed seeds round rounds phase phases table tables figure figures equation "
    "equations page pages chapter column columns row rows line lines level levels principle principles "
    "commit part parts case example issue issues pr run runs job shard arm arms stage stages piece pieces "
    "group groups version versions python pythons git uv pip hypothesis pytest usd-core mypy pyright ruff "
    "release dev rfc pep iso".split()
)
MONTHS = set("january february march april may june july august september october november december".split())
PHYSICAL = set("k \u00b0c \u00b0 pa kpa mpa gpa kg mg mm cm \u00b5m nm mol ml hz khz mhz m/s".split())
LEVEL = {"bound", "confidence", "one-sided", "two-sided", "upper", "lower", "interval"}
ESTIMATE = {"about", "around", "roughly", "approximately", "nearly", "almost", "estimated", *APPROXIMATE}
QUOTES = "\u201c\u201d\u2018\u2019"
STRIP = "`*_\"'()[]{},;:.!?<>|" + QUOTES
TRAILING = ",;:.!?)]}*\"'|" + QUOTES

QUOTED = rf"\"(?:[^\"\n]|\n(?!\s*\n)){{0,400}}\"|{QUOTES[0]}[^{QUOTES[1]}]{{0,400}}{QUOTES[1]}"
INTERVAL = rf"[\[(][-{MINUS}]?\d[\d.e{MINUS}-]*,\s*[-{MINUS}]?\d[\d.e{MINUS}-]*[\])]"
BLANKED = re.compile(rf"```.*?```|`[^`\n]*`|https?://\S+|\]\([^)]*\)|<!--.*?-->|{QUOTED}|{INTERVAL}", re.S)

BREAK = "\u00b6"
MARKER = re.compile(r"^(?:[-*+>]|#+|\[[ x]\])$")

MIN_WORDS = 6
MAX_GAP = 3
NEAR = 0.7

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


@dataclass(frozen=True)
class Range:
    base: str
    head: str

    def count(self, kind: str) -> int:
        return counts(self.base, self.head)[kind]


@functools.cache
def counts(base: str, head: str) -> dict[str, int]:
    totals = {
        "commits": int(git("rev-list", "--count", f"{base}..{head}")),
        "files": 0,
        "added": 0,
        "removed": 0,
    }
    for line in git("diff", "--numstat", "--no-renames", base, head).splitlines():
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


def git_findings(text: str, place: str, span: Range) -> list[str]:
    """Check 1 over `text`, each finding as `place:line: what`. A quotation, someone else's claim, is not
    read."""
    found: list[str] = []
    text = re.sub(QUOTED, lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)
    for match in COMMIT_NAME.finditer(text):
        name = match.group(1)
        if re.search("[a-f]", name) and re.search("[0-9]", name) and resolve(name) is None:
            found.append(f"{place}:{line_of(text, match.start())}: `{name}` names no commit here")
    for claim, which, expected in ((HEAD_CLAIM, "head", span.head), (BASE_CLAIM, "base", span.base)):
        for match in claim.finditer(text):
            if (resolve(match.group(1)) or match.group(1)) != expected:
                where = line_of(text, match.start(1))
                found.append(f"{place}:{where}: the {which} is `{expected[:8]}`, not `{match.group(1)}`")
    stated: dict[int, tuple[str, str]] = {}
    for kind_, pattern in COUNTS:
        for match in re.finditer(pattern, text, re.I | re.M):
            stated.setdefault(match.start(1), (kind_, match.group(1)))
    for table in tables(text.split("\n")):
        stated.update(table_counts(text, table))
    for offset, (kind_, value) in sorted(stated.items()):
        if number(value) != span.count(kind_):
            where = line_of(text, offset)
            found.append(f"{place}:{where}: {value} {kind_}, where git counts {span.count(kind_)}")
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
    """`text` with code, links, quotations, intervals and the tables of check 1 blanked, lines kept."""
    lines = BLANKED.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text).split("\n")
    for table in tables(text.split("\n")):
        for index in table:
            lines[index] = ""
    return "\n".join(lines)


def figures(text: str, lines: set[int] | None = None) -> tuple[list[Figure], dict[str, int]]:
    """The figures of `text`, on `lines` alone where given, that a fact must match; and how many numbers each
    reason of `kind` left out. A figure's words stop at its paragraph or list item."""
    tokens: list[tuple[int, str, bool]] = []
    for line, row in enumerate(prose(text).split("\n"), 1):
        if not row.strip() or re.match(r"\s*(?:[-*+]|\d+\.)\s", row):
            tokens.append((line, BREAK, False))
        leading = True
        for token in row.split():
            tokens.append((line, token, leading))
            leading = leading and MARKER.match(token) is not None
    words = ["" if leading and MARKER.match(token) else normalised(token) for _, token, leading in tokens]
    found: list[Figure] = []
    left: dict[str, int] = {}
    for index, (line, token, _) in enumerate(tokens):
        bare = token.strip(TRAILING).lstrip("(*[")
        if (lines is not None and line not in lines) or not NUMBER.match(bare):
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
                    line, bare, before[before.index(BREAK) + 1 :] if BREAK in before else before, following
                )
            )
    return found, left


def kind(
    tokens: list[tuple[int, str, bool]], words: list[str], index: int, following: tuple[str, ...]
) -> str:
    """Why the number at `index` needs no fact, or "" where it needs one."""
    raw = tokens[index][1].strip("*")
    bare = raw.strip(TRAILING).lstrip("(*[")
    before = index - 1
    while before >= 0 and (
        words[before] in {"and", "or", "to", "through", ""} or NUMBER.match(words[before])
    ):
        before -= 1
    named = words[before] if before >= 0 else ""
    previous = tokens[index - 1][1].lstrip("([*") if index else ""
    if re.match(r"^\(\d+\)", raw) or (tokens[index][2] and re.match(r"^\d+[.)]$", raw)):
        return "a list or heading number"
    if named in NUMBERED or previous.startswith("-") or re.match(r"^3\.1\d$", bare):
        return "a numbered thing, a version or a flag"
    if re.match(r"^\d{8,}$", bare):
        return "a run's or a job's number"
    if re.match(r"^(?:19\d\d|20[0-3]\d)$", bare) and (
        named in MONTHS or previous[:1].isupper() or previous == "in"
    ):
        return "a year"
    counted = re.sub(r"\(.*", "", following[0]) if following else ""
    if counted in GIT_COUNTED or following[:2] in {("file", "changed"), ("files", "changed")}:
        return "a git fact"
    if following[:1] and following[0] in PHYSICAL:
        return "a value in a physical unit"
    if LEVEL & set(following[:3]) and (bare.endswith("%") or following[:1] == ("%",)):
        return "a confidence level"
    if bare[0] in APPROXIMATE or named in ESTIMATE or ESTIMATE & set(words[max(0, index - 2) : index]):
        return "an estimate"
    if {"estimate", "estimated"} & set(following[:5]):
        return "an estimate"
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


def figure_findings(
    text: str,
    place: str,
    span: Range,
    facts: list[Fact],
    lines: set[int] | None = None,
    known: frozenset[str] = frozenset(),
) -> tuple[list[str], dict[str, int]]:
    """Check 2 over `text`: the findings, and how many figures a fact matched, the baseline held and an
    estimate marked."""
    found: list[str] = []
    stated, left = figures(text, lines)
    tally = {"matched": 0, "baseline": 0, "estimates": left.get("an estimate", 0)}
    for figure in stated:
        width = len(figure.after)
        matching = [
            fact
            for fact in facts
            if decimal(figure.text) == fact.value
            and any(figure.after[start : start + len(fact.what)] == fact.what for start in range(width))
        ]
        about = f"{figure.text} ({' '.join(figure.after[:4])} ...)"
        if figure.key() in known:
            tally["baseline"] += 1
        elif not matching:
            found.append(f"{place}:{figure.line}: {about} matches no recorded fact")
        elif not any(is_ancestor(fact.at, span.head) for fact in matching):
            found.append(f"{place}:{figure.line}: {about} was measured at a commit the head does not hold")
        else:
            tally["matched"] += 1
    return found, tally


def is_ancestor(commit: str, head: str) -> bool:
    return (
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, head], capture_output=True).returncode
        == 0
    )


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


def ruling_findings(rulings: str, added: list[tuple[str, list[Word]]]) -> list[str]:
    """Check 3: each run of a ruling's words that an added specification sentence nearly matches, not word for
    word. Two sentences are compared where they share two runs of three words."""
    index: dict[tuple[str, ...], set[int]] = {}
    for position, (_, sentence) in enumerate(added):
        for trigram in trigrams(sentence):
            index.setdefault(trigram, set()).add(position)
    found: set[str] = set()
    for ruled in sentences(rulings):
        shared: dict[int, int] = {}
        for trigram in trigrams(ruled):
            for position in index.get(trigram, ()):
                shared[position] = shared.get(position, 0) + 1
        for position in (position for position, count in shared.items() if count >= 2):
            path, sentence = added[position]
            for ours, theirs in near_runs(ruled, sentence):
                found.add(
                    f"{path}:{theirs[0][2]}: a ruled sentence differs: the ruling has "
                    f'"{" ".join(token for _, token, _ in ours)}", this line '
                    f'"{" ".join(token for _, token, _ in theirs)}"'
                )
    return sorted(found)


def near_runs(ruled: list[Word], sentence: list[Word]) -> Iterator[tuple[list[Word], list[Word]]]:
    """The runs of `ruled` and `sentence` that nearly match and differ."""
    matcher = difflib.SequenceMatcher(
        None, [w for w, _, _ in ruled], [w for w, _, _ in sentence], autojunk=False
    )
    chains: list[list[difflib.Match]] = []
    for block in (block for block in matcher.get_matching_blocks() if block.size > 1):
        last = chains[-1][-1] if chains else None
        if last and block.a - last.a - last.size <= MAX_GAP and block.b - last.b - last.size <= MAX_GAP:
            chains[-1].append(block)
        else:
            chains.append([block])
    for chain in chains:
        common = sum(block.size for block in chain)
        ours = ruled[chain[0].a : chain[-1].a + chain[-1].size]
        theirs = sentence[chain[0].b : chain[-1].b + chain[-1].size]
        longer = max(len(ours), len(theirs))
        if MIN_WORDS <= common < longer and common >= NEAR * longer:
            yield ours, theirs


def check(options: argparse.Namespace) -> int:
    head, base = resolve(options.head), resolve(options.base)
    if head is None or base is None:
        raise ClaimsError(f"cannot resolve {options.head if head is None else options.base}")
    span = Range(git("merge-base", base, head).strip(), head)
    facts = load_facts(options.facts or default_facts())
    found: list[str] = []
    tally = {"matched": 0, "baseline": 0, "estimates": 0}
    texts: list[tuple[str, str, set[int] | None]] = []
    if options.description:
        text = options.description.read_text(encoding="utf-8")
        found += git_findings(text, str(options.description), span)
        texts.append((text, str(options.description), None))
    for entry in git("log", "--format=%H%x00%B%x1e", f"{span.base}..{span.head}").split("\x1e"):
        name, _, message = entry.strip("\n").partition("\x00")
        if name:
            found += git_findings(message, f"commit {name[:8]}, message", span)
    changelog = added_lines(span, "CHANGELOG.md").get("CHANGELOG.md")
    if changelog:
        texts.append((git("show", f"{span.head}:CHANGELOG.md"), "CHANGELOG.md", changelog))
    known = frozenset(key for key, *_ in json.loads(BASELINE.read_text(encoding="utf-8"))["changelog"])
    for text, place, lines in texts:
        more, counted = figure_findings(text, place, span, facts, lines, known)
        found += more
        tally = {name: tally[name] + counted[name] for name in tally}
    if options.rulings:
        found += ruling_findings(options.rulings.read_text(encoding="utf-8"), added_sentences(span))
    print("\n".join(found) if found else "no claim found that git, the facts or the rulings contradict")
    matched, estimates, baseline = tally["matched"], tally["estimates"], tally["baseline"]
    print(
        f"figures: {matched} matched a fact, {estimates} marked estimates, {baseline} in the CHANGELOG's "
        f"baseline; {len(found)} findings"
    )
    if not options.rulings:
        print("the ruled wording was not checked: no rulings file was given (--rulings)")
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
    options = parser.parse_args(arguments)
    try:
        return check(options) if options.command == "check" else record(options)
    except (ClaimsError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else error
        print(f"check_claims: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
