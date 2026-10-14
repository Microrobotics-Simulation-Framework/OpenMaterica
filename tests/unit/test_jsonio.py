# SPDX-License-Identifier: Apache-2.0
"""Examples at the edges of `record_format.md` section 1 item 6, which the properties draw too rarely to rely
on, and the faults that only plain-read cases (not yet runnable) hold."""

import json
import json.scanner
import struct
from typing import NoReturn

import pytest

from materica.core.jsonio import parse
from materica.core.reasons import Reason

MALFORMED = Reason("malformed")
LARGEST_DOUBLE = 1.7976931348623157e308
ROUNDS_TO_INFINITY = 2**1024 - 2**970


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("9007199254740993", 9007199254740992.0),
        ("-0", -0.0),
        ("1e-400", 0.0),
        ("-1e-400", -0.0),
        ("3e-324", 5e-324),
        ("2.4703282292062327e-324", 0.0),
        ("2.4703282292062328e-324", 5e-324),
        ("1.7976931348623158e308", LARGEST_DOUBLE),
        (str(ROUNDS_TO_INFINITY - 1), LARGEST_DOUBLE),
        ("0." + "0" * 4999 + "1", 0.0),
        ("1" + "0" * 5000 + "e-4800", 1e200),
    ],
)
def test_numbers_read_as_the_nearest_double(text: str, number: float) -> None:
    value = parse(text.encode())
    assert isinstance(value, float)
    assert struct.pack(">d", value) == struct.pack(">d", number)


@pytest.mark.parametrize(
    "text", ["1.7976931348623159e308", str(ROUNDS_TO_INFINITY), "-1e400", "1" + "0" * 5000]
)
def test_numbers_that_round_to_an_infinity_are_malformed(text: str) -> None:
    assert parse(text.encode()) == MALFORMED


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"\xef\xbb\xbf{}", id="byte_order_mark"),
        pytest.param('{"a":1}'.encode("utf-16-le"), id="utf16"),
        pytest.param('{"a":1}'.encode("utf-32"), id="utf32"),
        pytest.param(b'"\xc0\x80"', id="overlong"),
        pytest.param(b'"\xed\xa0\x80"', id="encoded_surrogate"),
        pytest.param(b'"\xe2\x82"', id="truncated"),
        pytest.param(b'{"a":1,"\\u0061":2}', id="repeated_name_after_unescaping"),
        pytest.param(b"NaN", id="nan"),
        pytest.param(b"[Infinity]", id="infinity"),
        pytest.param(b"-Infinity", id="minus_infinity"),
        pytest.param(b'"\\ud800"', id="lone_high_surrogate"),
        pytest.param(b'"\\udc00"', id="lone_low_surrogate"),
        pytest.param(b'"\\ud800\\u0041"', id="high_surrogate_then_letter"),
        pytest.param(b"[1,]", id="trailing_comma"),
        pytest.param(b"[1 /* comment */]", id="comment"),
        pytest.param(b'"\x01"', id="control_character"),
        pytest.param(b"", id="empty"),
    ],
)
def test_refused_as_malformed(data: bytes) -> None:
    assert parse(data) == MALFORMED


def test_nesting_counts_arrays_and_objects_only() -> None:
    assert parse(b"[" * 64 + b"]" * 64) != MALFORMED
    assert parse(b"[" * 64 + b"0" + b"]" * 64) != MALFORMED
    assert parse(b"[" * 64 + b'"[[[[{{{{"' + b"]" * 64) != MALFORMED
    assert parse(b"[" * 65 + b"]" * 65) == MALFORMED
    assert parse(b'{"a":' * 65 + b"0" + b"}" * 65) == MALFORMED


def test_nesting_100000_deep_is_malformed_without_a_crash() -> None:
    assert parse(b"[" * 100_000 + b"]" * 100_000) == MALFORMED


@pytest.mark.parametrize(
    ("data", "value"),
    [
        pytest.param(b'"\\u0000"', "\x00", id="escaped_u0000"),
        pytest.param('"\ufffe\uffff\U0010ffff"'.encode(), "\ufffe\uffff\U0010ffff", id="raw_noncharacters"),
        pytest.param(b'"\\ufdd0\\uDBFF\\uDFFF"', "\ufdd0\U0010ffff", id="escaped_noncharacters"),
        pytest.param(
            b'{"\\u00e9":0,"e\\u0301":1}', {"\u00e9": 0.0, "e\u0301": 1.0}, id="names_not_normalised"
        ),
    ],
)
def test_odd_but_valid_text_is_read(data: bytes, value: object) -> None:
    assert parse(data) == value


@pytest.mark.parametrize("error", [RecursionError, MemoryError])
def test_exhausted_resources_are_malformed(monkeypatch: pytest.MonkeyPatch, error: type[Exception]) -> None:
    def exhausted(*args: object, **kwargs: object) -> NoReturn:
        raise error

    monkeypatch.setattr(json, "loads", exhausted)
    assert parse(b"[]") == MALFORMED


def test_a_unicode_digit_is_refused_by_either_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    pure_python = vars(json.scanner)["py_make_scanner"]  # typeshed omits it
    monkeypatch.setattr(json.scanner, "make_scanner", pure_python)
    assert parse("1\u0663".encode()) == MALFORMED
    assert parse(b"[1, 2.5]") == [1.0, 2.5]
