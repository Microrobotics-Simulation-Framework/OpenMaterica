# SPDX-License-Identifier: Apache-2.0
"""RFC 8785's own examples, and what `canonicalize` refuses."""

import json
import struct

import pytest

from materica.core.canonical import canonicalize
from materica.core.jsonio import JsonValue, parse
from materica.core.reasons import Reason

# RFC 8785 Appendix B, less its NaN and Infinity rows.
APPENDIX_B = [
    ("0000000000000000", "0"),
    ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"),
    ("8000000000000001", "-5e-324"),
    ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("ffefffffffffffff", "-1.7976931348623157e+308"),
    ("4340000000000000", "9007199254740992"),
    ("c340000000000000", "-9007199254740992"),
    ("4430000000000000", "295147905179352830000"),
    ("44b52d02c7e14af5", "9.999999999999997e+22"),
    ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef4f", "999999999999999900000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("41b3de4355555553", "333333333.3333332"),
    ("41b3de4355555554", "333333333.33333325"),
    ("41b3de4355555555", "333333333.3333333"),
    ("41b3de4355555556", "333333333.3333334"),
    ("41b3de4355555557", "333333333.33333343"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]


def double(bits: str) -> float:
    number: float = struct.unpack(">d", bytes.fromhex(bits))[0]
    return number


@pytest.mark.parametrize(("bits", "text"), APPENDIX_B)
def test_appendix_b_numbers(bits: str, text: str) -> None:
    assert canonicalize(double(bits)) == text.encode()


def test_section_3_2_2_sample_gives_the_bytes_of_section_3_2_4() -> None:
    sample = (
        '{\n  "numbers": [333333333.33333329, 1E30, 4.50,\n'
        "              2e-3, 0.000000000000000000000000001],\n"
        '  "string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/",\n'
        '  "literals": [null, true, false]\n}'
    )
    expected = bytes.fromhex(
        "7b 22 6c 69 74 65 72 61 6c 73 22 3a 5b 6e 75 6c 6c 2c 74 72"
        "75 65 2c 66 61 6c 73 65 5d 2c 22 6e 75 6d 62 65 72 73 22 3a"
        "5b 33 33 33 33 33 33 33 33 33 2e 33 33 33 33 33 33 33 2c 31"
        "65 2b 33 30 2c 34 2e 35 2c 30 2e 30 30 32 2c 31 65 2d 32 37"
        "5d 2c 22 73 74 72 69 6e 67 22 3a 22 e2 82 ac 24 5c 75 30 30"
        "30 66 5c 6e 41 27 42 5c 22 5c 5c 5c 5c 5c 22 2f 22 7d"
    )
    value = parse(sample.encode())
    assert not isinstance(value, Reason)
    assert canonicalize(value) == expected


def test_section_3_2_3_member_order() -> None:
    names = ["\u20ac", "\r", "\ufb33", "1", "\U0001f600", "\u0080", "\u00f6"]
    written = json.loads(canonicalize(dict[str, JsonValue].fromkeys(names)))
    assert list(written) == ["\r", "1", "\u0080", "\u00f6", "\u20ac", "\U0001f600", "\ufb33"]


def test_strings_are_written_as_they_are() -> None:
    assert canonicalize("e\u0301\u00e9") == '"e\u0301\u00e9"'.encode()
    assert (
        canonicalize('\x00\x1f\b\f\n\r\t"\\/\x7f\u2028')
        == b'"\\u0000\\u001f\\b\\f\\n\\r\\t\\"\\\\/\x7f\xe2\x80\xa8"'
    )


@pytest.mark.parametrize(
    ("value", "error"),
    [
        pytest.param(1, TypeError, id="int"),
        pytest.param([True, 2], TypeError, id="int_in_array"),
        pytest.param((1.0,), TypeError, id="tuple"),
        pytest.param(float("nan"), ValueError, id="nan"),
        pytest.param({"a": float("inf")}, ValueError, id="infinity"),
        pytest.param("\ud800", ValueError, id="lone_surrogate"),
        pytest.param({"\udc00": None, "a": None}, ValueError, id="lone_surrogate_in_a_name"),
    ],
)
def test_only_values_as_parse_gives_them_are_written(value: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        canonicalize(value)  # type: ignore[arg-type]  # Refusing what the type excludes is the test.
