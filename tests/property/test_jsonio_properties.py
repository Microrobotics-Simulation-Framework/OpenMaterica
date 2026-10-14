# SPDX-License-Identifier: Apache-2.0
"""Properties of the strict JSON reader (`record_format.md` section 1 item 6). The mutants they kill are in
`test_mutants.py`."""

import json
import math
import random
from collections.abc import Callable

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.property import strategies
from tests.property.strategies import SIZE, Size
from tests.property.support import feature, same

Parser = Callable[[bytes], JsonValue | Reason]
MALFORMED = Reason("malformed")


def nested(depth: int, innermost: JsonValue) -> JsonValue:
    """`innermost` inside `depth` arrays."""
    value: JsonValue = innermost
    for _ in range(depth):
        value = [value]
    return value


# (1a) Any bytes give a value or `malformed`, and never raise.


@st.composite
def mutated_documents(draw: st.DrawFn, size: Size = SIZE) -> bytes:
    _, text = draw(strategies.documents(size))
    data = bytearray(text.encode("utf-8"))
    for _ in range(draw(st.integers(1, 3))):
        position = draw(st.integers(0, len(data)))
        byte = draw(st.integers(0, 255))
        edit = draw(st.sampled_from(["insert", "replace", "delete"]))
        if edit == "insert" or position == len(data):
            data.insert(position, byte)
        elif edit == "replace":
            data[position] = byte
        else:
            del data[position]
    return bytes(data)


def any_bytes(size: Size = SIZE) -> st.SearchStrategy[bytes]:
    return st.one_of(
        st.binary(),
        st.text(alphabet='{}[]",:0123456789.eE+-\\/u nulltruefalseNaInfiy\t\r\n').map(str.encode),
        mutated_documents(size),
    )


def check_any_bytes(parse: Parser, data: bytes) -> None:
    result = parse(data)
    if isinstance(result, Reason):
        assert result == MALFORMED
    else:
        assert same(result, json.loads(data.decode("utf-8"), parse_int=float))


@pytest.mark.features(read_as_a_value=0.02, refused=0.30)
@example(b"[" * 64 + b"]" * 64)
@example(b"[" * 65 + b"]" * 65)
@example(b"[" * 100_000 + b"]" * 100_000)
@given(any_bytes())
def test_any_bytes_give_a_value_or_malformed(data: bytes) -> None:
    refused = isinstance(jsonio.parse(data), Reason)
    feature("read_as_a_value", not refused)
    feature("refused", refused)
    check_any_bytes(jsonio.parse, data)


# (1b) Values written with random whitespace, escapes, surrogate pairs and number spellings read back equal,
# as Python's json and float() read them.


def check_reads_back(parse: Parser, document: tuple[JsonValue, str]) -> None:
    value, text = document
    assert same(value, json.loads(text, parse_int=float))
    parsed = parse(text.encode("utf-8"))
    assert not isinstance(parsed, Reason), parsed
    assert same(value, parsed)


def _strings(value: JsonValue) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [string for item in value for string in _strings(item)]
    if isinstance(value, dict):
        return [*value, *(string for member in value.values() for string in _strings(member))]
    return []


def _numbers(value: JsonValue) -> list[float]:
    if isinstance(value, float):
        return [value]
    if isinstance(value, list):
        return [number for item in value for number in _numbers(item)]
    if isinstance(value, dict):
        return [number for member in value.values() for number in _numbers(member)]
    return []


MANY_MEMBERS: JsonValue = {f"\U0001f600 {index}": [float(index), str(index)] for index in range(100)}


@pytest.mark.features(
    astral_character=0.15, control_character=0.10, integral_number=0.06, three_deep=0.10, three_members=0.10
)
@example((MANY_MEMBERS, strategies.render(random.Random(0), MANY_MEMBERS)))
@given(strategies.documents())
def test_written_values_read_back(document: tuple[JsonValue, str]) -> None:
    value, _ = document
    strings = _strings(value)
    feature("astral_character", any(max(string, default="\x00") > "\uffff" for string in strings))
    feature("control_character", any(min(string, default=" ") < " " for string in strings))
    feature("integral_number", any(number.is_integer() for number in _numbers(value)))
    feature("three_deep", strategies.nesting(value) >= 3)
    feature("three_members", any(len(container) >= 3 for container in _containers(value)))
    check_reads_back(jsonio.parse, document)


def _containers(value: JsonValue) -> list[list[JsonValue] | dict[str, JsonValue]]:
    if isinstance(value, list):
        return [value, *(found for item in value for found in _containers(item))]
    if isinstance(value, dict):
        return [value, *(found for member in value.values() for found in _containers(member))]
    return []


def check_number(parse: Parser, literal: str) -> None:
    nearest = float(literal)
    result = parse(f"[ {literal} ]".encode())
    if math.isinf(nearest):
        assert result == MALFORMED
    else:
        assert same([nearest], json.loads(f"[{literal}]", parse_int=float))
        assert not isinstance(result, Reason), result
        assert same([nearest], result)


@pytest.mark.features(
    rounds_to_an_infinity=0.01, rounds_to_zero_or_a_subnormal=0.02, more_than_17_digits=0.01, integer=0.03
)
@example(str(2**1024 - 2**970))
@example("2.4703282292062328e-324")
@given(strategies.number_literals())
def test_every_number_reads_as_the_nearest_double(literal: str) -> None:
    nearest = float(literal)
    digits = literal.lstrip("-").lower().partition("e")[0].replace(".", "").strip("0")
    feature("rounds_to_an_infinity", math.isinf(nearest))
    feature("rounds_to_zero_or_a_subnormal", bool(digits) and abs(nearest) < 2.2250738585072014e-308)
    feature("more_than_17_digits", len(digits) > 17)
    feature("integer", literal.lstrip("-").isdigit())
    check_number(jsonio.parse, literal)


# (1c) Each fault the item lists, put into valid text, is refused.


def check_fault_refused(parse: Parser, faulty: tuple[str, bytes]) -> None:
    fault, data = faulty
    assert parse(data) == MALFORMED, fault


@pytest.mark.features(**{fault: 0.02 for fault in [*strategies.FRAGMENTS, *strategies.DOCUMENT_FAULTS]})
@example(("too_deep", b"[" * 65 + b"]" * 65))
@example(("too_deep", b'{"a":' * 65 + b"0" + b"}" * 65))
@example(("too_deep", b"[" * 100_000 + b"]" * 100_000))
@given(strategies.faulty_documents())
def test_each_listed_fault_is_refused(faulty: tuple[str, bytes]) -> None:
    feature(faulty[0])
    check_fault_refused(jsonio.parse, faulty)


# (1d) Odd but valid text is never refused: noncharacters, an escaped U+0000, nesting exactly 64.


def check_odd_but_valid(parse: Parser, document: tuple[JsonValue, str]) -> None:
    value, text = document
    assert strategies.nesting(value) == 64
    parsed = parse(text.encode("utf-8"))
    assert not isinstance(parsed, Reason), parsed
    assert same(value, parsed)


def _innermost(value: JsonValue) -> JsonValue:
    while isinstance(value, list | dict) and len(value) == 1:
        value = value[0] if isinstance(value, list) else next(iter(value.values()))
    return value


@pytest.mark.features(noncharacter=0.30, u0000=0.20, scalar_at_depth_64=0.03)
@example((nested(64, 0.0), "[" * 64 + "0" + "]" * 64))
@example((nested(63, {}), "[" * 63 + "{}" + "]" * 63))
@given(strategies.odd_documents())
def test_odd_but_valid_text_is_read(document: tuple[JsonValue, str]) -> None:
    value, _ = document
    strings = "".join(_strings(value))
    feature("noncharacter", any(char in strategies.NONCHARACTERS for char in strings))
    feature("u0000", "\x00" in strings)
    feature("scalar_at_depth_64", not isinstance(_innermost(value), list | dict))
    check_odd_but_valid(jsonio.parse, document)
