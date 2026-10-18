# SPDX-License-Identifier: Apache-2.0
"""The anomaly check's YAML reader (`scripts/check_anomalies.py`) against PyYAML's `safe_load`, the reference
it claims to read as. The reader may refuse a document; it must never read one differently, read one PyYAML
refuses, or fail other than by refusing:
- a document the reader reads is read exactly as PyYAML reads it, type for type, and a document PyYAML refuses
  is refused (`agrees`);
- a document inside the subset the reader names (its module docstring) is read, so that a rule that grew too
  strict is seen, which a differential alone cannot see (`reads_as_pyyaml`).
The documents are drawn in seven ways: whole documents inside the subset; the same with one or two choices
outside it (block mappings, sequences, the three scalar styles, block scalars, comments, line breaks); the
same inside the subset with one or two edits (a line moved, deleted or repeated, a character put in, changed
or removed), which land just outside it; single plain words and keys; one character of any kind in each place
a character stands; escapes, valid and not, with their hex digits; and the boolean and null words in every
case. Controls show that the differential can fail: a reader with one rule weakened is found by the property
meant to find it, from documents drawn to hold the fault's witness, so that no draw can miss it. The fixed
documents below are witnesses of faults seeded in the reader.

One difference is known and not tested for: PyYAML refuses a key of more than 1024 characters and the reader
reads one (`test_a_key_longer_than_pyyaml_reads_is_the_one_known_difference`).
"""

import itertools
import re
from collections.abc import Callable
from typing import Literal

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from scripts import check_anomalies

# PyYAML's own booleans and null, each in the cases its resolver reads (`yaml.resolver`) and in the others,
# which it reads as strings.
WORDS = ("yes", "no", "true", "false", "on", "off", "null")
ALSO_WORDS = (*WORDS, "y", "n")  # the last two are strings in YAML 1.1 as PyYAML reads it
BACKSLASH = "\\"


def cases(word: str) -> list[str]:
    return sorted(
        {"".join(letters) for letters in itertools.product(*((c.lower(), c.upper()) for c in word))}
    )


def read(text: str) -> object | Literal["refused"]:
    """What the reader reads `text` as, or "refused"; any other failure is the test's."""
    try:
        return check_anomalies.read_registry(text)
    except check_anomalies.RegistryFormatError:
        return "refused"


def pyyaml_reads(text: str) -> object | Literal["refused"]:
    try:
        loaded: object = yaml.safe_load(text)
    except yaml.YAMLError:
        return "refused"
    return loaded


def same(mine: object, theirs: object) -> bool:
    """Equal, by type: `True` is not `1`, and a string is not the number it spells."""
    return repr(mine) == repr(theirs) and mine == theirs


def agrees(text: str) -> bool:
    """Whether the reader refuses `text`, or reads it as PyYAML does (and PyYAML reads it)."""
    mine = read(text)
    return mine == "refused" or (pyyaml_reads(text) != "refused" and same(mine, pyyaml_reads(text)))


def reads_as_pyyaml(text: str) -> bool:
    mine = read(text)
    return mine != "refused" and same(mine, pyyaml_reads(text))


class Wild:
    """Which of a document's choices that may leave the subset do: those at the indices drawn, counted as the
    document is built. A document of none is inside the subset."""

    def __init__(self, at: frozenset[int]) -> None:
        self.at = at
        self.count = 0

    def next(self) -> bool:
        self.count += 1
        return self.count - 1 in self.at


@st.composite
def wilds(draw: st.DrawFn, outside: bool) -> Wild:
    return Wild(frozenset(draw(st.sets(st.integers(0, 24), max_size=2))) if outside else frozenset())


# What the documents are made of: forms the reader reads, and, for a wild choice, forms just outside.

KEYS = ["a", "b", "title", "k_1", "anomaly_id", "_z", "x1", "yes_", "nullx", "y", "n"]
WILD_KEYS = [
    *(case for word in WORDS for case in cases(word)),
    "A", "1", "a b", "a-b", "a.b", "é", "~", "a:b", "a#b", "'a'", '"a"', "?", "a\tb",
]  # fmt: skip
PLAIN_WORDS = ["open", "x", "MIME-ANO-001", "v1.2_x", "a.b", "A", "Abc", "a-b", "a_b", "Zed", "ab-1", "x.y.z"]
WILD_PLAINS = [
    *(case for word in WORDS for case in cases(word)),
    "x:", "x: y", "a: b", "a:b", "a#b", "x#c", "x #c", "a b", "a  b", "é1", "ÿ", "a\u00a0b", "a\u0085b",
    "a\u2003b", "a\tb", "1", "0.10", "1e3", "0x1", "2026-10-17", ".5", "-a", "- a", "? a", "[a]", "{}",
    "{a: b}", "&x 'a'", "*x", "!!str a", "a,b", "a/b", "a'b", 'a"b', "'a' 'b'", "'a'x", '"a"x', "'a", '"a',
    "'", '"', "<<", "=", "-", "?", ":", "@a", "`a", "%a", "!a", ">a", "|a", "[ ]x", "[a, b]",
]  # fmt: skip
EMPTIES = ["null", "~", "[]", "[ ]", '""', "''"]
COMMENTS = ["", "", "", "  # c", " #c", " # c: d", "  #", " # \"q'"]
WILD_COMMENTS = ["\t# c", "# c", "#c", "\t#c"]
ESCAPES = [
    *(BACKSLASH + c for c in "0abtnvfre \"/\\N_LP"),
    BACKSLASH + "\t", BACKSLASH + "x41", BACKSLASH + "xfF", BACKSLASH + "u00e9", BACKSLASH + "uFFFF",
    BACKSLASH + "U0001F600", BACKSLASH + "U0010FFFF", BACKSLASH + "x00", BACKSLASH + "x7f",
    BACKSLASH + "ud800", BACKSLASH + "ufeff", BACKSLASH + "u2028", BACKSLASH + "u0085",
]  # fmt: skip
WILD_ESCAPES = [
    *(BACKSLASH + c for c in "q18UuxXz"),
    BACKSLASH + "x4", BACKSLASH + "x4G", BACKSLASH + "xZZ", BACKSLASH + "uZZZZ", BACKSLASH + "u12",
    BACKSLASH + "u12345", BACKSLASH + "U00110000", BACKSLASH + "UFFFFFFFF", BACKSLASH + "U0000D800",
    BACKSLASH + "x+1", BACKSLASH + "u 123", BACKSLASH + "x\u0661\u0662", BACKSLASH, BACKSLASH + "\n",
]  # fmt: skip
DOUBLE_PARTS = ["a", "b", " ", "#", ":", "'", "-", "é", "  ", "x y", "\u00a0", "\U0001f600", "\ufeff"]
WILD_CHARACTERS = [
    "\t", "\u2028", "\u2029", "\x85", "\x7f", "\x00", "\x1b", "\ufffe", "\uffff", "\ud7ff", "\ue000", "\r",
    "\U0010ffff", "\x08",
]  # fmt: skip
SINGLE_PARTS = ["a", "b", " ", "#", ":", '"', "\\", "-", "é", "''", "  "]
BLOCK_LINES = [
    "one", "two words", "  indented", "    more", "# hash", "- item", "k: v", "é", "a  ", '"q"', "'q'",
    "a #b", "!tag", "&anc", "*al", "%d", "---", "...", "|", "> x", "x\ttab",
]  # fmt: skip
HEADERS = ["|", ">", "|-", ">-", "|+", ">+", "| # c", "> #c", "|- # c", ">+ # c"]
WILD_HEADERS = ["|2", "|-1", ">+2", "|+ x", "|x", ">  ", "|1", "|0", ">1-", "|+-", "| #", "|\t"]
STRAYS = ["b: 'y'", "- 'y'", "'y'", "# c", "b:", "y", "- k: 'y'", "b: >", "  - 'y'"]


def pieces(tame: list[str], wild_ones: list[str], wild: Wild) -> st.SearchStrategy[str]:
    return st.sampled_from(wild_ones if wild.next() else tame)


@st.composite
def double_quoted(draw: st.DrawFn, wild: Wild) -> str:
    parts = draw(
        st.lists(
            st.one_of(pieces(DOUBLE_PARTS, WILD_CHARACTERS, wild), pieces(ESCAPES, WILD_ESCAPES, wild)),
            max_size=7,
        )
    )
    return '"' + "".join(parts) + '"'


@st.composite
def single_quoted(draw: st.DrawFn, wild: Wild) -> str:
    parts = draw(st.lists(pieces(SINGLE_PARTS, ["'", "\u2028", "\x85", "\t", "\x7f"], wild), max_size=7))
    return "'" + "".join(parts) + "'"


@st.composite
def scalars(draw: st.DrawFn, wild: Wild) -> str:
    kind = draw(st.integers(0, 6))
    if kind <= 1:
        value = draw(pieces(PLAIN_WORDS, WILD_PLAINS, wild))
    elif kind == 2:
        value = draw(double_quoted(wild))
    elif kind == 3:
        value = draw(single_quoted(wild))
    else:
        value = draw(st.sampled_from(EMPTIES))
    return value + draw(pieces(COMMENTS, WILD_COMMENTS, wild))


@st.composite
def block_lines(draw: st.DrawFn, indent: int, wild: Wild) -> list[str]:
    """The lines under a block scalar's header, in a mapping at `indent`."""
    base = indent + draw(st.sampled_from([2, 2, 1, 3] if wild.next() else [2, 2, 3, 4]))
    lines: list[str] = []
    for position in range(draw(st.integers(1, 5))):
        # A block's first line sets its indentation, so that in the subset it holds no leading space.
        text = draw(st.sampled_from([line for line in BLOCK_LINES if position or not line.startswith(" ")]))
        pad = base
        if position:
            pad = draw(st.sampled_from([base - 1, 0, indent + 1] if wild.next() else [base] * 4 + [base + 1]))
        if position == 0 or draw(st.integers(0, 5)):
            lines.append(" " * pad + text)
        else:
            lines.append(draw(pieces(["", "", " " * base], [" " * (base + 2), " " * (base - 1), " "], wild)))
    return lines


@st.composite
def mappings(draw: st.DrawFn, indent: int, depth: int, wild: Wild, first: bool = False) -> list[str]:
    """The lines of a block mapping at `indent`; with `first`, the first line without its indentation."""
    names = draw(st.lists(st.sampled_from(KEYS), min_size=1, max_size=4, unique=True))
    pad = " " * indent
    lines: list[str] = []
    for at, name in enumerate(names):
        if wild.next():
            name = draw(st.sampled_from(WILD_KEYS))
        if at and draw(st.integers(0, 5)) == 0:
            lines.append(draw(st.sampled_from(["", "# c", pad + "# c", "  # c", " ", pad])))
        space = draw(pieces([" ", " ", "  "], ["", "\t", " \t"], wild))
        kind = draw(st.integers(0, 9))
        body: list[str] = []
        if kind <= 4:
            line = f"{name}:{space}{draw(scalars(wild))}"
        elif kind == 5:
            line = f"{name}:{draw(pieces(COMMENTS, WILD_COMMENTS, wild))}"
        elif kind == 6 and depth < 2:
            line = f"{name}:{draw(pieces(COMMENTS, WILD_COMMENTS, wild))}"
            shift = draw(pieces(["0", "2", "2", "4"], ["1", "3", "5"], wild))
            body = draw(sequences(indent + int(shift), depth + 1, wild))
        elif kind == 7 and depth < 2 and wild.next():
            line = f"{name}:"
            body = draw(mappings(indent + draw(st.sampled_from([2, 4, 1])), depth + 1, wild))
        elif kind == 8:
            line = f"{name}: {draw(pieces(HEADERS, WILD_HEADERS, wild))}"
            body = draw(block_lines(indent, wild))
        else:
            line = f"{name}:"
        lines.append(line if at == 0 and first else pad + line)
        lines += body
        if wild.next():
            lines.append(" " * (indent + draw(st.sampled_from([1, 2, 4]))) + draw(st.sampled_from(STRAYS)))
    return lines


@st.composite
def sequences(draw: st.DrawFn, indent: int, depth: int, wild: Wild) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    for _ in range(draw(st.integers(1, 4))):
        if draw(st.integers(0, 5)) == 0:
            lines.append(draw(st.sampled_from(["", "# c", pad + "# c", "  # c", " "])))
        space = draw(pieces([" ", " ", "  ", "   "], ["", "\t"], wild))
        kind = draw(st.integers(0, 5))
        if kind <= 2:
            lines.append(f"{pad}-{space}{draw(scalars(wild))}")
        elif kind == 3 and depth < 2 and space:
            inner = draw(mappings(indent + 1 + len(space), depth + 1, wild, first=True))
            lines.append(f"{pad}-{space}{inner[0]}")
            lines += inner[1:]
        elif kind == 4 and wild.next():
            lines.append(f"{pad}-{draw(st.sampled_from(COMMENTS + WILD_COMMENTS))}")
        else:
            lines.append(f"{pad}- {draw(single_quoted(wild))}")
        if wild.next():
            lines.append(" " * (indent + draw(st.sampled_from([1, 2, 4]))) + draw(st.sampled_from(STRAYS)))
    return lines


@st.composite
def documents(draw: st.DrawFn, outside: bool) -> str:
    """A document inside the subset, or, with `outside`, with one or two choices outside it."""
    wild = draw(wilds(outside))
    lines = draw(mappings(0, 0, wild))
    if wild.next():
        marker = draw(st.sampled_from(["---", "...", "--- ", "%YAML 1.1", "--- a", "...  # c", "<<: *a"]))
        lines.insert(draw(st.integers(0, len(lines))), marker)
    if wild.next():
        lines.insert(0, draw(st.sampled_from(["\ufeff", "\ufeffa: b"])))
    if draw(st.integers(0, 4)) == 0:
        lines.insert(0, draw(st.sampled_from(["# top", "", "  # indented comment", " "])))
    breaks = draw(pieces(["\n"], ["\r\n", "\r", "\n\r", "\u2028", "\x85", "\u2029"], wild))
    end = draw(pieces(["\n"], ["", "\n\n", "\r\n", " \n", "\n  \n", "\n#c"], wild))
    return breaks.join(lines) + end


EDITS = [
    ":", "#", "'", '"', "\\", "-", " ", "\t", "&", "*", "!", "|", ">", "[", "]", "{", "}", "%", "@", "`", "?",
    ",", "\x7f", "\x85", "\u2028", "\ufeff", "\ufffe", "\x00", "~", "\r", "a", "0",
]  # fmt: skip


@st.composite
def edited_documents(draw: st.DrawFn) -> str:
    """A document inside the subset with one or two edits, which usually leave it just outside."""
    text = draw(documents(outside=False))
    for _ in range(draw(st.integers(1, 2))):
        lines = text.split("\n")
        at = draw(st.integers(0, len(lines) - 1))
        line = lines[at]
        operation = draw(st.integers(0, 6))
        if operation == 0:
            lines[at] = " " * draw(st.integers(1, 3)) + line
        elif operation == 1:
            lines[at] = line[draw(st.integers(1, 3)) :] if line.startswith(" ") else line
        elif operation == 2:
            del lines[at]
        elif operation == 3:
            lines.insert(at, line)
        else:
            place = draw(st.integers(0, len(line)))
            put = draw(st.sampled_from(EDITS))
            if operation == 4:
                lines[at] = line[:place] + put + line[place:]
            elif operation == 5:
                lines[at] = line[:place] + put + line[place + 1 :]
            else:
                lines[at] = line[:place] + line[place + 1 :]
        text = "\n".join(lines)
    return text


PLAIN_FRAGMENTS = ["a", "x", "1", ":", " ", "#", "-", ".", "_", "\t", "'", '"', "[", "]", "{", "&", "!", "é"]
PLAIN_STEMS = ["a", "x", "ab", "1", "a b", "Zed", "x.y", "a-b", "_a"]
PLAIN_TAILS = [
    ":",
    "#",
    " #",
    ": ",
    ":#",
    "#c",
    ":x",
    " :",
    ",",
    "[",
    "{",
    "'",
    '"',
    "\t",
    " ",
    "\u00a0",
    "-",
]


PLAIN_FORMS = [
    "a: {w}\n",
    "a: {w}  # c\n",
    "a: {w}\nb: 'x'\n",
    "a:\n  - {w}\n",
    "a:\n- {w}\nb: x\n",
    "{w}: 'x'\n",
    "{w}:\n",
    "a: 'x'\n{w}: 'y'\n",
    "a:\n  - {w}: 'x'\n",
    "a: {w} # {w}\n",
]


@st.composite
def plain_documents(draw: st.DrawFn) -> str:
    """A short run of characters that matter to a plain scalar, as a value, an item and a key."""
    word = draw(
        st.one_of(
            st.lists(st.sampled_from(PLAIN_FRAGMENTS), min_size=1, max_size=5).map("".join),
            st.builds(str.__add__, st.sampled_from(PLAIN_STEMS), st.sampled_from(PLAIN_TAILS)),
            st.sampled_from(ALSO_WORDS),
        )
    )
    form = draw(st.sampled_from(PLAIN_FORMS))
    return form.format(w=word)


BOUNDARIES = [
    "\x00", "\x08", "\t", "\x0b", "\x0c", "\r", "\x1f", " ", "~", "\x7f", "\x80", "\x84", "\x85", "\x86",
    "\x9f", "\xa0", "\u2027", "\u2028", "\u2029", "\u202a", "\ud7ff", "\ud800", "\udbff", "\udc00", "\udfff",
    "\ue000", "\ufdd0", "\ufeff", "\ufffd", "\ufffe", "\uffff", "\U00010000", "\U0010ffff", "é", "\u200b",
    "\u0300",
]  # fmt: skip


CHARACTER_FORMS = [
    'a: "x{c}y"\n',
    "a: 'x{c}y'\n",
    "a: x{c}y\n",
    "a: x # {c}\n",
    "a: |\n  x{c}y\n",
    "a: >\n  {c}\n",
    "# {c}\na: 'x'\n",
    "a:\n  - 'x{c}'\n",
    "{c}: 'x'\n",
    "a: {c}\n",
    "a: 'x'\n  {c}\n",
    "a:{c}'x'\n",
    "a: >\n  x\n  {c}y\n",
    "a: |\n  {c}\n",
    "a:\n  - {c}\n",
    "a: 'x'{c}\n",
    "a: 'x' #{c}\n",
]


@st.composite
def character_documents(draw: st.DrawFn) -> str:
    """One character, of any kind, in each place a character stands."""
    character = draw(st.one_of(st.sampled_from(BOUNDARIES), st.integers(0, 0x10FFFF).map(chr)))
    form = draw(st.sampled_from(CHARACTER_FORMS))
    return form.format(c=character)


ESCAPE_FORMS = ["a: {v}\n", "a:\n  - {v}\n", "a:\n- {v}\nb: {v}\n"]


@st.composite
def escape_documents(draw: st.DrawFn) -> str:
    """Escapes among text in a double-quoted value, valid or not, in each place a value stands; and a hex
    escape followed by any run of hex digits and not."""
    hexed = st.tuples(
        st.sampled_from(["x", "u", "U"]), st.text('0123456789abcdefABCDEFgG+- "\u0661\uff11', max_size=9)
    )
    parts = draw(
        st.lists(
            st.one_of(
                st.sampled_from(ESCAPES + WILD_ESCAPES),
                hexed.map(lambda pair: BACKSLASH + pair[0] + pair[1]),
                st.sampled_from(["a", " "]),
            ),
            max_size=3,
        )
    )
    value = '"' + "".join(parts) + '"' + draw(st.sampled_from(["", "  # c"]))
    return draw(st.sampled_from(ESCAPE_FORMS)).format(v=value)


WORD_KEY_FORMS = ["{w}: 'x'\n", "a: 'x'\n{w}:\n"]
WORD_FORMS = ["a: {w}\n", "a:\n  - {w}\n", *WORD_KEY_FORMS, "a:\n- {w}\nb: x\n", "a: {w} # c\n"]


@st.composite
def word_documents(draw: st.DrawFn) -> str:
    """A boolean or null word, in each of its cases, as a value, an item and a key."""
    word = draw(st.sampled_from(ALSO_WORDS))
    spelled = draw(st.sampled_from(cases(word)))
    return draw(st.sampled_from(WORD_FORMS)).format(w=spelled)


def reads_what_it_reads(text: str) -> None:
    assert reads_as_pyyaml(text), text


def refuses_or_agrees(text: str) -> None:
    assert agrees(text), text


test_a_document_inside_the_subset_is_read_as_pyyaml_reads_it = given(documents(outside=False))(
    reads_what_it_reads
)
test_a_document_with_choices_outside_the_subset_is_refused_or_read_as_pyyaml_reads_it = given(
    documents(outside=True)
)(refuses_or_agrees)
test_a_document_with_an_edit_is_refused_or_read_as_pyyaml_reads_it = given(edited_documents())(
    refuses_or_agrees
)
test_a_plain_word_is_refused_or_read_as_pyyaml_reads_it = given(plain_documents())(refuses_or_agrees)
test_a_character_is_refused_or_read_as_pyyaml_reads_it = given(character_documents())(refuses_or_agrees)
test_an_escape_is_refused_or_read_as_pyyaml_reads_it = given(escape_documents())(refuses_or_agrees)
test_a_boolean_or_null_word_is_refused_or_read_as_pyyaml_reads_it = given(word_documents())(refuses_or_agrees)


# The specifier syntax against `packaging`'s, which it ports: sets of specifiers, each a spelling of an
# operator, a release, a pre-release, a post-release, a development release, a local label and a wildcard, in
# the cases and with the separators PEP 440 allows and a few it does not. Every part of a set is non-empty, as
# the check refuses an empty specifier where `packaging` skips it (`test_check_anomalies.py`).
OPERATORS = [
    "==",
    "!=",
    "~=",
    "<=",
    ">=",
    "<",
    ">",
    "==",
    "!=",
    "~=",
    "<=",
    ">=",
    "<",
    ">",
    "===",
    "=",
    "=>",
    "~",
    "",
]
RELEASES = [
    "1",
    "1.0",
    "0.1.0",
    "2.10.3",
    "1!2.0",
    "v1.0",
    "V2",
    "00.1",
    "1.0.0.0",
    "10",
    "2.0",
    "1.2",
    "1!",
    "1.",
]
PRE_RELEASES = ["", "", "a1", "b2", "rc3", "c1", ".alpha", "-beta.2", "_preview", "RC1", "pre4", ".rc", "a"]
POST_RELEASES = ["", "", ".post1", "-1", "r2", "-rev3", ".REV", "post", "_post_4", "-"]
DEVELOPMENT_RELEASES = ["", "", ".dev1", "dev", "-dev.2", "_DEV3"]
LOCAL_LABELS = ["", "", "+abc", "+a.b", "+a-b", "+a_b", "+A1.b2", "+", "+.", "+a..b", "+-a"]
WILDCARDS = ["", "", "", ".*", ".*.1"]
SPACES = ["", "", " ", "  ", "\t"]


@st.composite
def specifier(draw: st.DrawFn) -> str:
    """One specifier with the operator, the release and at most two of the optional parts."""
    optional = [PRE_RELEASES, POST_RELEASES, DEVELOPMENT_RELEASES, LOCAL_LABELS, WILDCARDS]
    shown = draw(st.sets(st.integers(0, len(optional) - 1), max_size=2))
    return (
        draw(st.sampled_from(OPERATORS))
        + draw(st.sampled_from(SPACES))
        + draw(st.sampled_from(RELEASES))
        + "".join(draw(st.sampled_from(parts)) for at, parts in enumerate(optional) if at in shown)
        + draw(st.sampled_from(SPACES))
    )


@st.composite
def specifier_sets(draw: st.DrawFn) -> str:
    specifiers = draw(st.lists(specifier(), min_size=1, max_size=3))
    return draw(st.sampled_from([",", ", ", " ,", ",\t"])).join(specifiers)


def reads_as_packaging(text: str) -> None:
    try:
        SpecifierSet(text)
    except InvalidSpecifier:
        valid = False
    else:
        valid = True
    assert check_anomalies.is_specifier_set(text) == valid, text


test_a_specifier_set_is_read_as_packaging_reads_it = given(specifier_sets())(reads_as_packaging)


# Controls: the differential run on a reader with one rule weakened must find it, and must find it on every
# run, whatever the draws: a control that sometimes cannot fail is a defect. So each draws the fault's witness
# directly, in valid surrounding YAML (or a valid specifier set), and every document it draws is one on which
# the weakened reader differs. The first example then finds the fault, and no seed or draw order can miss it.
# The ordinary properties above still draw broadly.
SAFE_ESCAPES = [*(BACKSLASH + c for c in '0abtvfre "/\\N_LP'), BACKSLASH + "x41", BACKSLASH + "u00e9"]
COLON_STEMS = ["a", "x", "ab", "Zed", "x.y", "a-b"]
COLON_FORMS = ["a: {w}\n", "a: {w}  # c\n", "a: {w}\nb: 'x'\n", "a: {w} # {w}\n"]
DEL_FORMS = [
    'a: "x{c}y"\n', "a: 'x{c}y'\n", "a: x # {c}\n", "a: |\n  x{c}y\n", "a: >\n  {c}\n", "# {c}\na: 'x'\n",
    "a:\n  - 'x{c}'\n", "a: |\n  {c}\n", "a: 'x' #{c}\n",
]  # fmt: skip
PLAIN_SPECIFIERS = ["==1.0", "!=2.1.*", "~=1.2", ">=2", "<3.0", "<=1.0rc1", ">0.1.0", "===x"]
# Cased parts of a version that `packaging` reads, which the pattern reads only with `re.IGNORECASE`.
CASED_VERSIONS = [
    "V2", "V1.0", "1.0RC1", "1.0.REV", "1.0_DEV3", "1.0+A1.b2", "1.0A1", "2B2", "1.0-Beta.2", "1.0.POST1",
]  # fmt: skip


@st.composite
def escaped_newline_documents(draw: st.DrawFn) -> str:
    """A double-quoted value with the escape `\\n` among escapes and text the reader reads."""
    around = st.lists(st.sampled_from([*SAFE_ESCAPES, "a", " "]), max_size=2)
    parts = [*draw(around), BACKSLASH + "n", *draw(around)]
    value = '"' + "".join(parts) + '"' + draw(st.sampled_from(["", "  # c"]))
    return draw(st.sampled_from(ESCAPE_FORMS)).format(v=value)


@st.composite
def off_documents(draw: st.DrawFn) -> str:
    """The word `off` as a value, an item and a key. PyYAML reads only `off`, `Off` and `OFF` as a
    boolean, and the reader reads a key of lowercase only."""
    form = draw(st.sampled_from(WORD_FORMS))
    return form.format(w="off" if form in WORD_KEY_FORMS else draw(st.sampled_from(["off", "Off", "OFF"])))


@st.composite
def delete_documents(draw: st.DrawFn) -> str:
    """The character DEL (U+007F), which PyYAML refuses, in each place the reader reads a character."""
    return draw(st.sampled_from(DEL_FORMS)).format(c="\x7f")


@st.composite
def word_colon_documents(draw: st.DrawFn) -> str:
    """A plain value of a word and a colon, which PyYAML refuses and a reader that takes the colon for part of
    the word reads."""
    word = draw(st.sampled_from(COLON_STEMS)) + draw(st.sampled_from([":", "::"]))
    return draw(st.sampled_from(COLON_FORMS)).format(w=word)


@st.composite
def cased_specifier_sets(draw: st.DrawFn) -> str:
    """A set of specifiers, valid, one of which has a part in capitals."""
    cased = (
        draw(st.sampled_from(["==", "!="]))
        + draw(st.sampled_from(SPACES))
        + draw(st.sampled_from(CASED_VERSIONS))
    )
    others = st.lists(st.sampled_from(PLAIN_SPECIFIERS), max_size=1)
    specifiers = [*draw(others), cased + draw(st.sampled_from(SPACES)), *draw(others)]
    return draw(st.sampled_from([",", ", ", " ,", ",\t"])).join(specifiers)


def differs(check: Callable[[str], None], text: str) -> bool:
    try:
        check(text)
    except AssertionError:
        return True
    return False


def finds_a_difference(
    witnesses: st.SearchStrategy[str], check: Callable[[str], None] = refuses_or_agrees
) -> None:
    """That `check`, the property, fails on every witness, and so on a search for one, the reader being
    weakened. Each runs under settings of its own, keeping nothing in the example database, which the
    properties' do."""

    @settings(database=None)
    @given(witnesses)
    def every_witness_is_one(text: str) -> None:
        assert differs(check, text), text

    every_witness_is_one()
    with pytest.raises(AssertionError):
        settings(database=None)(given(witnesses)(check))()


def test_the_differential_finds_an_escape_read_as_another(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(check_anomalies._ESCAPES, "n", "n")  # pyright: ignore[reportPrivateUsage]
    finds_a_difference(escaped_newline_documents())


def test_the_differential_finds_a_boolean_word_read_as_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    words = check_anomalies._NOT_STRINGS - {"off"}  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(check_anomalies, "_NOT_STRINGS", words)
    finds_a_difference(off_documents())


def test_the_differential_finds_a_character_pyyaml_refuses_read(monkeypatch: pytest.MonkeyPatch) -> None:
    unread = check_anomalies._UNREAD.pattern.replace("\x20-\x7e", "\x20-\x7f")  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(check_anomalies, "_UNREAD", re.compile(unread))
    finds_a_difference(delete_documents())


def test_the_differential_finds_a_colon_read_in_a_plain_word(monkeypatch: pytest.MonkeyPatch) -> None:
    word = check_anomalies._WORD.pattern.replace("[A-Za-z0-9_.-]*", "[A-Za-z0-9_.:-]*")  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(check_anomalies, "_WORD", re.compile(word))
    finds_a_difference(word_colon_documents())


def test_the_differential_finds_a_specifier_pattern_that_ignores_no_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check_anomalies, "SPECIFIER", re.compile(check_anomalies.SPECIFIER.pattern))
    finds_a_difference(cased_specifier_sets(), reads_as_packaging)


# The same witnesses on the reader as it is: it must agree, so that a control is found by its fault and not by
# a witness that is itself a document the reader gets wrong.
test_an_escaped_newline_is_refused_or_read_as_pyyaml_reads_it = given(escaped_newline_documents())(
    refuses_or_agrees
)
test_the_word_off_is_refused_or_read_as_pyyaml_reads_it = given(off_documents())(refuses_or_agrees)
test_a_delete_character_is_refused_or_read_as_pyyaml_reads_it = given(delete_documents())(refuses_or_agrees)
test_a_word_and_a_colon_is_refused_or_read_as_pyyaml_reads_it = given(word_colon_documents())(
    refuses_or_agrees
)
test_a_set_with_a_cased_specifier_is_read_as_packaging_reads_it = given(cased_specifier_sets())(
    reads_as_packaging
)


# Fixed documents. Each is one on which the reader, weakened in the rule named, read wrongly or crashed (the
# independent review of the pull request that added the reader). The differential above finds them too, but a
# witness does not wait for a draw, and a refusal of a document PyYAML reads, which no differential sees, is
# found only by a document the reader must read.

READ = {
    "an escaped newline": 'a: "x' + BACKSLASH + 'ny"\n',
    "an escaped bell": 'a: "' + BACKSLASH + 'a"\n',
    "an escaped backspace": 'a: "' + BACKSLASH + 'b"\n',
    "an escaped vertical tab": 'a: "' + BACKSLASH + 'v"\n',
    "an escaped form feed": 'a: "' + BACKSLASH + 'f"\n',
    "an escaped carriage return": 'a: "' + BACKSLASH + 'r"\n',
    "an escaped slash": 'a: "' + BACKSLASH + '/"\n',
    "an escaped tab": 'a: "' + BACKSLASH + '\t"\n',
    "a comment right after a key": "a: # c\nb: 'x'\n",
    "a comment before a sequence's items": "a:\n  # c\n  - 'x'\n",
    "a hash after a space after a plain word": "a: x #c\n",
    "a key that YAML 1.1 does not read as a boolean": "y: 'x'\nn: 'x'\n",
}


@pytest.mark.parametrize("text", READ.values(), ids=READ.keys())
def test_a_document_the_reader_must_read_is_read_as_pyyaml_reads_it(text: str) -> None:
    assert reads_as_pyyaml(text)


# Documents PyYAML refuses, which the reader must refuse, not read and not crash on.
REFUSED_BY_PYYAML = {
    "a line past a key's value": "a: 'x'\n  b: 'y'\n",
    "a line past a sequence's items": "a:\n  - 'x'\n    - 'y'\n",
    "a colon at the end of a plain word": "a: x:\n",
    "a NEL in a quoted value": "a: 'x\u0085y'\n",
    "a DEL in a quoted value": "a: 'x\x7f'\n",
    "U+FFFE in a quoted value": "a: 'x\ufffe'\n",
    "a bad hex digit": 'a: "' + BACKSLASH + 'xZZ"\n',
    "a bad second hex digit": 'a: "' + BACKSLASH + 'x4G"\n',
    "a bad fourth hex digit": 'a: "' + BACKSLASH + 'u004G"\n',
    "an escape out of range": 'a: "' + BACKSLASH + 'UFFFFFFFF"\n',
    "an escape just out of range": 'a: "' + BACKSLASH + 'U00110000"\n',
    "a sign in an escape's digits": 'a: "' + BACKSLASH + 'x+1"\n',
    "a non-ASCII digit in an escape": 'a: "' + BACKSLASH + 'x\u0661\u0662"\n',
}


@pytest.mark.parametrize("text", REFUSED_BY_PYYAML.values(), ids=REFUSED_BY_PYYAML.keys())
def test_a_document_pyyaml_refuses_is_not_read(text: str) -> None:
    """The control is each document's neighbour that PyYAML reads, in the differential's strategies."""
    assert read(text) == "refused"


# What PyYAML reads as a string, or as no string, by the shape of the line.
SHAPES = {
    "no space after a key's colon": "a:'x'\n",
    "a hash with no space before it": "a: x#c\n",
    "a word PyYAML reads as a string, in mixed case": "a: yEs\nb: nUll\n",
}


@pytest.mark.parametrize("text", SHAPES.values(), ids=SHAPES.keys())
def test_a_line_shape_is_not_read_as_a_value_pyyaml_reads_otherwise(text: str) -> None:
    assert agrees(text)


@pytest.mark.parametrize("spelled", [case for word in WORDS for case in cases(word)])
def test_each_case_of_a_boolean_or_null_word_is_read_as_pyyaml_reads_it(spelled: str) -> None:
    for text in (f"a: {spelled}\n", f"a:\n  - {spelled}\n", f"{spelled}: 'x'\n"):
        assert agrees(text), text


@pytest.mark.parametrize("escape", [BACKSLASH + c for c in '0abtnvfre "/\\N_LP\t'])
def test_every_escape_YAML_defines_is_read_as_pyyaml_reads_it(escape: str) -> None:
    text = f'a: "x{escape}y"\n'
    assert reads_as_pyyaml(text), text


def test_a_key_longer_than_pyyaml_reads_is_the_one_known_difference() -> None:
    """Why the module docstring states it: the reader reads a key of 1025 characters, PyYAML refuses it."""
    text = "a" * 1025 + ": 'x'\n"
    assert pyyaml_reads(text) == "refused"
    assert read(text) == {"a" * 1025: "x"}
    assert reads_as_pyyaml("a" * 1024 + ": 'x'\n")
