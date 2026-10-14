# SPDX-License-Identifier: Apache-2.0
"""Strict JSON: bytes to a value, or the reason `malformed` (`record_format.md` section 1 item 6).

The item applies to records, scene documents, engine crosswalks, read requests and conformance case files.
"""

import codecs
import json
import math
import re
from collections.abc import Iterator
from typing import NoReturn, TypeAlias

from materica.core.reasons import Reason

JsonValue: TypeAlias = bool | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
"""A value as `parse` gives it: every number is a float."""

MAX_DEPTH = 64

# A whole string, so that brackets inside one are skipped, or a bracket.
_STRING_OR_BRACKET = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"|[][{}]', re.DOTALL)
_SURROGATE = re.compile("[\ud800-\udfff]")


def parse(data: bytes) -> JsonValue | Reason:
    """Read `data` by `record_format.md` section 1 item 6.

    Gives the value, or `Reason("malformed")` with a detail for anything that item refuses. Never raises for
    any bytes.
    """
    try:
        return _parse(data)
    except (ValueError, RecursionError, MemoryError) as error:
        return Reason("malformed", detail=str(error) or type(error).__name__)


def _parse(data: bytes) -> JsonValue:
    if data.startswith(codecs.BOM_UTF8):
        raise ValueError("a byte-order mark")
    text = data.decode("utf-8")
    # Counted before json runs, so that json never recurses deeper than this: 100000 levels would exhaust
    # its stack.
    if _nesting_exceeds(text, MAX_DEPTH):
        raise ValueError(f"nested more than {MAX_DEPTH} deep")
    value: JsonValue = json.loads(
        text, object_pairs_hook=_object, parse_float=_double, parse_int=_double, parse_constant=_constant
    )
    # json joins a paired surrogate escape into one character and keeps an unpaired one; the strict decoding
    # above has refused any surrogate written as bytes.
    if any(_SURROGATE.search(string) for string in _strings(value)):
        raise ValueError("an unpaired surrogate escape")
    return value


def _nesting_exceeds(text: str, limit: int) -> bool:
    depth = 0
    for token in _STRING_OR_BRACKET.finditer(text):
        if token.group() in ("[", "{"):
            depth += 1
            if depth > limit:
                return True
        elif token.group() in ("]", "}"):
            depth -= 1
    return False


def _object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    members: dict[str, JsonValue] = {}
    for name, value in pairs:
        if name in members:
            raise ValueError(f"the member name {name!r} repeated")
        members[name] = value
    return members


def _double(text: str) -> float:
    # Integers come here too, as text: int() refuses more than 4300 digits, and float(int) overflows where
    # float(text) rounds. json's pure-Python scanner, used where its C one is missing, matches any Unicode
    # digit as a digit.
    if not text.isascii():
        raise ValueError(f"not a JSON number: {text!r}")
    number = float(text)
    if math.isinf(number):
        raise ValueError("a number that rounds to an infinity")
    return number


def _constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not JSON")


def _strings(value: JsonValue) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for name, member in value.items():
            yield name
            yield from _strings(member)
