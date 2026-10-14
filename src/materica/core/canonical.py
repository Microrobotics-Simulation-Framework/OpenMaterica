# SPDX-License-Identifier: Apache-2.0
"""RFC 8785 canonical JSON, which the content hash is taken over (`record_format.md` section 9 item 2)."""

import math

from materica.core.jsonio import JsonValue

_ESCAPES = {code: f"\\u{code:04x}" for code in range(0x20)} | {
    ord('"'): '\\"',
    ord("\\"): "\\\\",
    ord("\b"): "\\b",
    ord("\f"): "\\f",
    ord("\n"): "\\n",
    ord("\r"): "\\r",
    ord("\t"): "\\t",
}


def canonicalize(value: JsonValue) -> bytes:
    """`value`, as `parse` gives it, serialised by RFC 8785 in UTF-8.

    Strings are written as they are, never Unicode-normalised. A value `parse` would never give raises rather
    than being written: `TypeError` for an `int` or a tuple, say, and `ValueError` for a number that is not
    finite or a lone surrogate.
    """
    parts: list[str] = []
    _write(value, parts)
    return "".join(parts).encode("utf-8")


def _write(value: JsonValue, parts: list[str]) -> None:
    if value is None:
        parts.append("null")
    elif isinstance(value, bool):
        parts.append("true" if value else "false")
    elif isinstance(value, float):
        parts.append(_number(value))
    elif isinstance(value, str):
        parts.append(_string(value))
    elif isinstance(value, list):
        parts.append("[")
        for index, item in enumerate(value):
            if index:
                parts.append(",")
            _write(item, parts)
        parts.append("]")
    elif isinstance(value, dict):
        parts.append("{")
        for index, name in enumerate(sorted(value, key=_utf16_units)):
            if index:
                parts.append(",")
            parts.append(_string(name))
            parts.append(":")
            _write(value[name], parts)
        parts.append("}")
    else:
        raise TypeError(f"not a JSON value as parse gives it: {type(value).__name__}")


def _number(number: float) -> str:
    """ECMAScript's `Number.prototype.toString`, as RFC 8785 section 3.2.2.3 requires."""
    if not math.isfinite(number):
        raise ValueError(f"{number} has no JSON form")
    if number == 0:
        return "0"
    # repr gives the fewest digits that read back as the same double, the nearest where several do, as
    # ECMAScript does. Here the double is 0.<digits> times 10**point.
    mantissa, _, exponent = repr(abs(number)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    written = whole + fraction
    digits = written.strip("0")
    leading_zeros = len(written) - len(written.lstrip("0"))
    point = len(whole) - leading_zeros + int(exponent or "0")
    count = len(digits)
    sign = "-" if number < 0 else ""
    if count <= point <= 21:
        return sign + digits + "0" * (point - count)
    if 0 < point <= 21:
        return sign + digits[:point] + "." + digits[point:]
    if -6 < point <= 0:
        return sign + "0." + "0" * -point + digits
    fraction_part = "." + digits[1:] if count > 1 else ""
    return f"{sign}{digits[0]}{fraction_part}e{point - 1:+d}"


def _string(text: str) -> str:
    return '"' + text.translate(_ESCAPES) + '"'


def _utf16_units(name: str) -> bytes:
    # Big-endian bytes order as the UTF-16 code units they encode.
    return name.encode("utf-16-be")
