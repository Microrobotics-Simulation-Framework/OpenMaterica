# SPDX-License-Identifier: Apache-2.0
"""Properties of RFC 8785 serialisation (`record_format.md` section 9 item 2). The mutants they kill are in
`test_mutants.py`."""

import json
import struct
import unicodedata
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext

import pytest
import rfc8785
from hypothesis import example, given
from hypothesis import strategies as st

from materica.core.canonical import canonicalize
from materica.core.jsonio import JsonValue
from tests.property import strategies
from tests.property.support import feature

SMALLEST_NORMAL = 2.2250738585072014e-308


def utf16_units(name: str) -> list[int]:
    units: list[int] = []
    for char in name:
        code = ord(char)
        if code < 0x10000:
            units.append(code)
        else:
            units += [0xD800 + ((code - 0x10000) >> 10), 0xDC00 + ((code - 0x10000) & 0x3FF)]
    return units


def _orders_differ(names: list[str]) -> bool:
    return sorted(names, key=utf16_units) != sorted(names)


# Names across the surrogate range, more than small trees draw: their UTF-16 order differs from their
# code-point order.
ACROSS: list[str] = [chr(code) + str(index) for index, code in enumerate(range(0xD7F0, 0xD800))] + [
    chr(code) for code in (0xE000, 0xFB33, 0xFFFD, 0x10000, 0x1F600, 0x10FFFF)
]
MANY_MEMBERS: JsonValue = {name: float(index) for index, name in enumerate(ACROSS)}


def _parts(value: JsonValue) -> tuple[list[str], list[str], list[float], int]:
    """The names, strings and numbers in `value`, and the most members of any object in it."""
    if isinstance(value, float):
        return [], [], [value], 0
    if isinstance(value, str):
        return [], [value], [], 0
    if isinstance(value, list | dict):
        children = list(value.values()) if isinstance(value, dict) else value
        names = list(value) if isinstance(value, dict) else []
        parts = [_parts(child) for child in children]
        return (
            names + [name for part in parts for name in part[0]],
            [string for part in parts for string in part[1]],
            [number for part in parts for number in part[2]],
            max([len(names), *(part[3] for part in parts)]),
        )
    return [], [], [], 0


# (2a) Byte for byte what the `rfc8785` package writes.


def check_matches_rfc8785(value: JsonValue) -> None:
    assert canonicalize(value) == rfc8785.dumps(value)


@pytest.mark.features(
    three_members_to_sort=0.07,
    names_whose_utf16_order_differs=0.01,
    control_character=0.13,
    non_ascii_character=0.20,
    changed_by_normalisation=0.06,
    exponent_form=0.10,
    negative_zero=0.01,
)
@example(MANY_MEMBERS)
@given(strategies.json_values())
def test_output_matches_rfc8785(value: JsonValue) -> None:
    names, strings, numbers, widest = _parts(value)
    texts = names + strings
    feature("three_members_to_sort", widest >= 3)
    feature("names_whose_utf16_order_differs", _orders_differ(names))
    feature("control_character", any(min(text, default=" ") < " " for text in texts))
    feature("non_ascii_character", any(not text.isascii() for text in texts))
    feature("changed_by_normalisation", any(unicodedata.normalize("NFC", text) != text for text in texts))
    feature("exponent_form", any(b"e" in canonicalize(number) for number in numbers))
    feature("negative_zero", any(struct.pack(">d", number) == struct.pack(">d", -0.0) for number in numbers))
    check_matches_rfc8785(value)


# (2b) Every finite double, subnormals included, reads back bit for bit from the fewest digits that do so,
# and those digits are the nearest of their length where the nearest reads back.


def check_shortest_round_trip(number: float) -> None:
    text = canonicalize(number).decode()
    if number == 0:
        assert text == "0"
        return
    assert _bits(float(text)) == _bits(number)
    digits = _significant_digits(text)
    nearest = f"{number:.{len(digits) - 1}e}"
    if float(nearest) == number:
        assert digits == _significant_digits(nearest)
    if len(digits) > 1:
        assert number not in _neighbours(number, len(digits) - 1)


def _bits(number: float) -> bytes:
    return struct.pack(">d", number)


def _significant_digits(text: str) -> str:
    mantissa = text.lstrip("-").lower().partition("e")[0]
    return mantissa.replace(".", "").strip("0")


def _neighbours(number: float, digits: int) -> tuple[float, float]:
    """The decimals of `digits` significant digits just below and just above `number`, read as doubles."""
    exact = Decimal(number)
    quantum = Decimal(1).scaleb(exact.adjusted() - digits + 1)
    with localcontext(prec=1_100):
        return float(exact.quantize(quantum, ROUND_FLOOR)), float(exact.quantize(quantum, ROUND_CEILING))


@pytest.mark.features(subnormal=0.10, seventeen_digits=0.07, plain_form=0.05, exponent_form=0.25)
@example(5e-324)
@example(1.7976931348623157e308)
@example(-0.0)
@given(strategies.DOUBLES)
def test_every_double_reads_back_from_its_shortest_form(number: float) -> None:
    text = canonicalize(number)
    feature("subnormal", 0 < abs(number) < SMALLEST_NORMAL)
    feature("seventeen_digits", len(_significant_digits(text.decode())) == 17)
    feature("plain_form", b"e" not in text)
    feature("exponent_form", b"e" in text)
    check_shortest_round_trip(number)


# (2c) Member names on both sides of the surrogate range sort by their UTF-16 code units.

# Names are built character by character, each from one of these: st.text would merge them into one set and
# draw its lowest code points far more often than the rest, and the orders differ only where a character above
# U+FFFF meets one from U+E000 to U+FFFF.
ACROSS_SURROGATES = st.lists(
    st.one_of(
        st.sampled_from([chr(code) for code in (0xD7FF, 0xE000, 0xFB33, 0xFFFD, 0x10000, 0x1F600, 0x10FFFF)]),
        st.characters(min_codepoint=0xD700, max_codepoint=0xD7FF),
        st.characters(min_codepoint=0xE000, max_codepoint=0xFFFF),
        st.characters(min_codepoint=0x10000, max_codepoint=0x10FFFF),
    ),
    min_size=1,
    max_size=3,
).map("".join)
# Built from a list, where a repeated name simply collapses: st.dictionaries would retry it, and Hypothesis
# draws the same few characters often.
OBJECTS_ACROSS_SURROGATES = st.lists(ACROSS_SURROGATES, min_size=2, max_size=8).map(
    lambda names: dict[str, JsonValue].fromkeys(names)
)


def check_utf16_order(value: dict[str, JsonValue]) -> None:
    written: list[str] = json.loads(
        canonicalize(value), object_pairs_hook=lambda pairs: [name for name, _ in pairs]
    )
    assert written == sorted(value, key=utf16_units)


@pytest.mark.features(orders_differ=0.15, three_names=0.20)
@example(dict[str, JsonValue].fromkeys(ACROSS))
@given(OBJECTS_ACROSS_SURROGATES)
def test_names_sort_by_utf16_code_units(value: dict[str, JsonValue]) -> None:
    feature("orders_differ", _orders_differ(list(value)))
    feature("three_names", len(value) >= 3)
    check_utf16_order(value)
