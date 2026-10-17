# SPDX-License-Identifier: Apache-2.0
"""Strategies for the property tests: JSON values, texts that write them in many valid ways, and texts holding
one of the faults `record_format.md` section 1 item 6 lists."""

import codecs
import math
import random
import struct
from decimal import Decimal
from typing import NamedTuple, cast

from hypothesis import settings
from hypothesis import strategies as st

from materica.core.jsonio import JsonValue

# Values


# A double's three fields. Strategies are built once, here or by their arguments: Hypothesis spends more
# building and checking a strategy than drawing from it.
_SIGN = st.integers(0, 1)
_EXPONENT = st.one_of(st.just(0), st.integers(0, 2046))
_FRACTION = st.integers(0, 2**52 - 1)


@st.composite
def every_double(draw: st.DrawFn) -> float:
    """Any finite double from its bits, with zeros and subnormals (exponent field 0) drawn half the time."""
    sign = draw(_SIGN)
    exponent = draw(_EXPONENT)
    fraction = draw(_FRACTION)
    bits = sign << 63 | exponent << 52 | fraction
    number: float = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
    return number


# Both zeros, the subnormal and normal edges, and the largest double, which neither strategy draws often.
EDGE_DOUBLES = [
    0.0,
    -0.0,
    5e-324,
    -5e-324,
    2.2250738585072014e-308,
    1.7976931348623157e308,
    -1.7976931348623157e308,
]
DOUBLES = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False), every_double(), st.sampled_from(EDGE_DOUBLES)
)

# Characters the specification treats apart, which full-Unicode text seldom draws: a combining mark and the
# letters it composes with, a precomposed letter and a Hangul syllable (both change under normalisation), the
# last code points before the surrogates and the first after them, astral characters, control characters, the
# characters RFC 8785 escapes, and the separators JavaScript once escaped.
SPECIAL_CHARACTERS = (
    'e\u0301\u00e9\uac00\ud7ff\ue000\ufb33\ufffd\U00010000\U0001f600\U0010ffff\x00\x1f\x7f"\\/\u2028\u2029'
)
# Text is full Unicode half the time, and the other half built from SPECIAL_CHARACTERS one by one: st.text
# would draw an alphabet's lowest code points far more often than the rest.
TEXT = st.one_of(st.text(), st.lists(st.sampled_from(SPECIAL_CHARACTERS)).map("".join))

NONCHARACTERS = [chr(code) for code in range(0xFDD0, 0xFDF0)] + [
    chr(plane << 16 | low) for plane in range(17) for low in (0xFFFE, 0xFFFF)
]


class Size(NamedTuple):
    """How large a generated tree may be."""

    leaves: int  # scalars in the whole tree
    members: int  # members of one object, or items of one array
    depth: int  # nesting, counted as `nesting` counts it


# `dev` and `ci` draw small trees; `deep` draws the sizes these properties were first written with, or larger.
# Shapes that small trees cannot reach are explicit examples in the properties, run under every profile.
SMALL = Size(leaves=10, members=3, depth=5)
ORIGINAL = Size(leaves=30, members=5, depth=6)
SIZE = {"dev": SMALL, "ci": SMALL, "deep": ORIGINAL}[settings.get_current_profile_name()]

# Out of 100, the share of scalars at each depth below the root: a root is nearly always a container, and
# containers grow rarer with depth, as the trees st.recursive drew before (mean depth 2.1, at most 5).
_SCALAR_SHARE = (4, 55, 60, 65, 70, 75)

# json_values's strategy for each distinct set of arguments, kept with the arguments, so that no `id` in a key
# is reused while the key is held.
_JSON_VALUES: dict[object, tuple[st.SearchStrategy[JsonValue], tuple[object, ...]]] = {}


def _strict_key(value: object) -> object:
    """`value` as a key that tells apart what `==` does not: 0.0 and -0.0, and True, 1 and 1.0, are equal and
    hash alike. A float by its bits, a strategy by its identity, a tuple (a `Size`) by its type and items."""
    kind = type(value)
    if isinstance(value, float):
        return kind, struct.pack(">d", value)
    if isinstance(value, tuple):
        return kind, tuple(_strict_key(item) for item in cast(tuple[object, ...], value))
    if isinstance(value, st.SearchStrategy):
        return kind, id(cast(object, value))
    return kind, value


def json_values(
    strings: st.SearchStrategy[str] | None = None,
    names: st.SearchStrategy[str] | None = None,
    numbers: st.SearchStrategy[float] = DOUBLES,
    size: Size = SIZE,
) -> st.SearchStrategy[JsonValue]:
    """Trees of JSON values within `size`.

    They are drawn top-down with the remaining leaf budget passed down, so that no draw is thrown away. Each
    node's kind and child count are one integer each, which shrink towards a `null` and fewer children.

    Built once for each set of arguments (`_strict_key`), since callers ask for it in every draw.
    """
    strings = TEXT if strings is None else strings
    names = TEXT if names is None else names
    arguments = (strings, names, numbers, size)
    key = _strict_key(arguments)
    if key in _JSON_VALUES:
        return _JSON_VALUES[key][0]
    rolls, counts, booleans = st.integers(0, 99), st.integers(0, size.members), st.booleans()

    @st.composite
    def trees(draw: st.DrawFn) -> JsonValue:
        budget = [size.leaves]

        def node(depth: int) -> JsonValue:
            roll = draw(rolls)
            if roll < (_SCALAR_SHARE[depth] if depth < size.depth else 100):
                budget[0] -= 1
                kind = roll % 4
                if kind == 0:
                    return None
                if kind == 1:
                    return draw(booleans)
                return draw(numbers) if kind == 2 else draw(strings)
            children: list[JsonValue] = []
            for _ in range(draw(counts)):
                if budget[0] == 0:
                    break
                children.append(node(depth + 1))
            if roll % 2:
                return children
            # A repeated name collapses, where st.dictionaries would retry it.
            return {draw(names): child for child in children}

        return node(0)

    _JSON_VALUES[key] = (trees(), arguments)
    return _JSON_VALUES[key][0]


SCALARS: st.SearchStrategy[JsonValue] = st.one_of(st.none(), st.booleans(), DOUBLES, TEXT)


def nesting(value: JsonValue) -> int:
    """The depth item 6 counts: 1 for the outermost array or object, 0 for a scalar."""
    if isinstance(value, list):
        return 1 + max((nesting(item) for item in value), default=0)
    if isinstance(value, dict):
        return 1 + max((nesting(member) for member in value.values()), default=0)
    return 0


# Texts

SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "/": "\\/",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}

# A value that `render` writes as a raw U+0000, which it never writes otherwise; a fault replaces it. No
# generated string holds it, since a lone surrogate is never drawn.
MARKER = "\udfff"

# How a value is written is chosen by a Random that Hypothesis seeds: a draw per character would cost more
# than the rest of the search, and the seed is drawn, so a failure replays.
WRITINGS = st.randoms(use_true_random=True)


def render(writing: random.Random, value: JsonValue) -> str:
    """A JSON text of `value`, its whitespace, escapes and number spellings chosen by `writing`."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return _spell_number(writing, value)
    if value == MARKER:
        return "\x00"
    if isinstance(value, str):
        return _spell_string(writing, value)
    if isinstance(value, list):
        items = [_space(writing) + render(writing, item) + _space(writing) for item in value]
        return "[" + (",".join(items) or _space(writing)) + "]"
    assert isinstance(value, dict)
    members = [
        _space(writing)
        + _spell_string(writing, name)
        + _space(writing)
        + ":"
        + _space(writing)
        + render(writing, member)
        + _space(writing)
        for name, member in value.items()
    ]
    return "{" + (",".join(members) or _space(writing)) + "}"


@st.composite
def documents(draw: st.DrawFn, size: Size = SIZE) -> tuple[JsonValue, str]:
    value = draw(json_values(size=size))
    writing = draw(WRITINGS)
    return value, _space(writing) + render(writing, value) + _space(writing)


def _space(writing: random.Random) -> str:
    return "".join(writing.choices(" \t\n\r", k=writing.randint(0, 2)))


def _spell_number(writing: random.Random, number: float) -> str:
    # Each spelling reads back as exactly `number`.
    spellings = [repr(number), f"{number:.16e}", f"{number:.16E}", str(Decimal(number))]
    if number.is_integer():
        spellings.append(("-" if math.copysign(1.0, number) < 0 else "") + str(int(abs(number))))
    return writing.choice(spellings)


def _spell_string(writing: random.Random, text: str) -> str:
    must_escape = '"\\' + "".join(map(chr, range(0x20)))
    return (
        '"'
        + "".join(
            _escape(writing, char) if char in must_escape or writing.random() < 0.5 else char for char in text
        )
        + '"'
    )


def _escape(writing: random.Random, char: str) -> str:
    if char in SHORT_ESCAPES and writing.random() < 0.5:
        return SHORT_ESCAPES[char]
    code = ord(char)
    units = (
        [code] if code < 0x10000 else [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
    )
    form = writing.choice(["\\u{:04X}", "\\u{:04x}"])
    return "".join(form.format(unit) for unit in units)


@st.composite
def number_literals(draw: st.DrawFn) -> str:
    """JSON numbers of up to 400 significant digits, from far below the smallest subnormal to far beyond the
    largest double."""
    whole = draw(st.one_of(st.just("0"), st.from_regex(r"[1-9][0-9]{0,400}", fullmatch=True)))
    fraction = draw(st.one_of(st.just(""), st.from_regex(r"\.[0-9]{1,400}", fullmatch=True)))
    exponent = ""
    if draw(st.booleans()):
        # Any power, or one near the edges of the doubles: overflow from about 308, underflow from about -308.
        power = draw(st.one_of(st.integers(-800, 400), st.integers(280, 330), st.integers(-345, -295)))
        exponent = draw(st.sampled_from("eE")) + ("-" if power < 0 else draw(st.sampled_from(["", "+"])))
        exponent += str(abs(power)).zfill(draw(st.integers(1, 4)))
    return draw(st.sampled_from(["", "-"])) + whole + fraction + exponent


# Faults


def _with_marker(draw: st.DrawFn, value: JsonValue) -> JsonValue:
    """`value` with one of its values, perhaps the whole, replaced by MARKER."""
    if isinstance(value, list) and value and draw(st.booleans()):
        index = draw(st.integers(0, len(value) - 1))
        return [*value[:index], _with_marker(draw, value[index]), *value[index + 1 :]]
    if isinstance(value, dict) and value and draw(st.booleans()):
        name = draw(st.sampled_from(sorted(value)))
        return {**value, name: _with_marker(draw, value[name])}
    return MARKER


ASCII_TEXT = st.text(alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='"\\'))


@st.composite
def _repeated_name(draw: st.DrawFn) -> str:
    """An object naming one member twice, each spelled with its own escapes, perhaps with others between."""
    name = draw(st.text(max_size=4))
    others = [
        other for other in draw(st.lists(st.text(max_size=4), max_size=3, unique=True)) if other != name
    ]
    writing = draw(WRITINGS)
    return "{" + ",".join(_spell_string(writing, member) + ":0" for member in [name, *others, name]) + "}"


@st.composite
def _unpaired_surrogate(draw: st.DrawFn) -> str:
    high = f"\\u{draw(st.integers(0xD800, 0xDBFF)):04x}"
    low = f"\\u{draw(st.integers(0xDC00, 0xDFFF)):04x}"
    lone = draw(
        st.sampled_from([high, low, high + "x", low + high, high + high, high + "\\n", high + "\\u0041"])
    )
    return '"' + draw(ASCII_TEXT) + lone + draw(ASCII_TEXT) + '"'


@st.composite
def _too_deep(draw: st.DrawFn) -> str:
    openers = draw(st.lists(st.sampled_from(["[", '{"k":']), min_size=65, max_size=70))
    return "".join(openers) + "0" + "".join("]" if opener == "[" else "}" for opener in reversed(openers))


OVERFLOWING = st.one_of(
    st.sampled_from(["1.7976931348623159e308", "1e309", "-1E400", str(2**1024 - 2**970), "9" * 400]),
    st.integers(309, 100_000).map(lambda power: f"-1e{power}"),
)

# Each fault the item lists, as the bytes that replace one value of a valid document.
NOT_UTF8 = st.sampled_from(
    [
        b"\xc0\x80",
        b"\xe0\x80\xaf",
        b"\xed\xa0\x80",
        b"\xed\xbf\xbf",
        b"\xe2\x82",
        b"\xf0\x9f\x98",
        b"\xff",
        b"\x80",
        b"\xf4\x90\x80\x80",
    ]
).map(lambda bad: b'"' + bad + b'"')
_TEXT_FRAGMENTS: dict[str, st.SearchStrategy[str]] = {
    "repeated_name": _repeated_name(),
    "nan_or_infinity": st.sampled_from(["NaN", "Infinity", "-Infinity", "-NaN"]),
    "unpaired_surrogate": _unpaired_surrogate(),
    "rounds_to_infinity": OVERFLOWING,
    "too_deep": _too_deep(),
    "grammar": st.sampled_from(
        [
            "[0,]",
            '{"a":0,}',
            "[0/*c*/]",
            "[0 // c\n]",
            '"\x01"',
            '"\x1f"',
            "01",
            "1.",
            ".5",
            "+1",
            "-",
            "1e",
            "0x10",
            "nan",
            "True",
            "'a'",
            "{a:0}",
            "[0 0]",
            '{"a" 0}',
            "[",
            "}",
        ]
    ),
}
FRAGMENTS: dict[str, st.SearchStrategy[bytes]] = {
    "not_utf8": NOT_UTF8,
    **{fault: fragments.map(str.encode) for fault, fragments in _TEXT_FRAGMENTS.items()},
}
DOCUMENT_FAULTS = ("byte_order_mark", "utf16", "utf32")


@st.composite
def faulty_documents(draw: st.DrawFn, size: Size = SIZE) -> tuple[str, bytes]:
    """A fault's name, and a document holding that fault and no other."""
    fault = draw(st.sampled_from([*sorted(FRAGMENTS), *DOCUMENT_FAULTS]))
    value = draw(json_values(size=size))
    writing = draw(WRITINGS)
    if fault in DOCUMENT_FAULTS:
        text = render(writing, value)
        if fault == "byte_order_mark":
            return fault, codecs.BOM_UTF8 + text.encode("utf-8")
        width = "16" if fault == "utf16" else "32"
        return fault, text.encode(
            draw(st.sampled_from([f"utf-{width}", f"utf-{width}-le", f"utf-{width}-be"]))
        )
    text = render(writing, _with_marker(draw, value))
    return fault, text.encode("utf-8").replace(b"\x00", draw(FRAGMENTS[fault]))


# Texts that are odd but valid: noncharacters, escaped U+0000 and nesting exactly 64.

ODD_CHARACTERS = [*NONCHARACTERS, "\x00", "a", "\u00e9", "\U0001f600"]
ODD_STRINGS = st.text(alphabet=st.sampled_from(ODD_CHARACTERS), max_size=6)


@st.composite
def odd_documents(draw: st.DrawFn, size: Size = SIZE) -> tuple[JsonValue, str]:
    value: JsonValue = draw(json_values(strings=ODD_STRINGS, names=ODD_STRINGS, size=size))
    # The wrappers that bring it to depth 64 are chosen like the writing: a draw each would cost more than the
    # rest of the example.
    writing = draw(WRITINGS)
    for _ in range(64 - nesting(value)):
        name = "".join(writing.choices(ODD_CHARACTERS, k=writing.randint(0, 6)))
        value = [value] if writing.random() < 0.5 else {name: value}
    return value, render(writing, value)
