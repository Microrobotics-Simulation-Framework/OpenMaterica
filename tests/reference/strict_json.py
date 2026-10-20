# SPDX-License-Identifier: Apache-2.0
"""Strict JSON (`record_format.md` section 1 item 6), RFC 8785 and the content hash (section 9), for the
reference model of the read (`read_model.py`).

Written from the text with the standard library alone; it imports nothing from `materica`, at any depth
(`test_layering.py`), so that the model never rests on the code it checks.
"""

import codecs
import hashlib
import json
import math
import re
from typing import TypeAlias

JsonValue: TypeAlias = bool | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
JsonObject: TypeAlias = dict[str, JsonValue]

# record_format.md:67 "arrays and objects nested more than 64 deep"
MAXIMUM_DEPTH = 64
_SURROGATE = re.compile("[\ud800-\udfff]")


class NotStrictJson(Exception):
    """Bytes that `record_format.md` section 1 item 6 refuses, naming the fault."""

    def __init__(self, fault: str) -> None:
        super().__init__(fault)
        self.fault = fault


def parse(data: bytes) -> JsonValue:
    """The JSON value `data` holds, every number the double nearest it; raises `NotStrictJson`."""
    # record_format.md:59 "a byte-order mark at the start"
    if data.startswith(codecs.BOM_UTF8):
        raise NotStrictJson("byte-order mark")
    # record_format.md:57 "bytes that are not well-formed UTF-8"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise NotStrictJson("not UTF-8") from None
    try:
        value: JsonValue = json.loads(
            text,
            object_pairs_hook=_unrepeated,
            parse_constant=_no_constant,
            parse_float=_double,
            parse_int=_double,
        )
    except RecursionError:
        raise NotStrictJson("nested too deep") from None
    except json.JSONDecodeError:
        # record_format.md:54-55 "text that is not a JSON text by RFC 8259's grammar"
        raise NotStrictJson("not a JSON text") from None
    if _deeper_than(value, MAXIMUM_DEPTH):
        raise NotStrictJson("nested too deep")
    # record_format.md:63 "a string escape that leaves a surrogate unpaired"
    if any(_SURROGATE.search(string) for string in _strings(value)):
        raise NotStrictJson("an unpaired surrogate")
    return value


def _unrepeated(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    # record_format.md:60 "a member name repeated within one object, names compared after their escapes are
    # decoded"
    if len({name for name, _ in pairs}) < len(pairs):
        raise NotStrictJson("a repeated member name")
    return dict(pairs)


def _no_constant(name: str) -> float:
    # record_format.md:62 "the tokens `NaN`, `Infinity` and `-Infinity`"
    raise NotStrictJson(f"the token {name}")


def _double(written: str) -> float:
    # record_format.md:70 "Every number is the IEEE 754 double nearest it, ties to even, integers included"
    number = float(written)
    # record_format.md:64 "a number that rounds to an infinity"
    if math.isinf(number):
        raise NotStrictJson("a number that rounds to an infinity")
    return number


def _deeper_than(value: JsonValue, limit: int) -> bool:
    """Walked without recursion: where the C stack allows it, `json` returns nesting deeper than Python's
    recursion limit lets a recursive walk follow."""
    pending: list[tuple[JsonValue, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        children: list[JsonValue]
        if isinstance(current, dict):
            children = list(current.values())
        elif isinstance(current, list):
            children = current
        else:
            continue
        if depth > limit:
            return True
        pending.extend((child, depth + 1) for child in children)
    return False


def _strings(value: JsonValue) -> list[str]:
    found: list[str] = []
    pending: list[JsonValue] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            found.append(current)
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict):
            found.extend(current)
            pending.extend(current.values())
    return found


def canonical(value: JsonValue) -> str:
    """`value` serialised by RFC 8785 (`record_format.md` section 9 item 2)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 section 3.2.3: members sorted by their names' UTF-16 code units.
        names = sorted(value, key=lambda name: name.encode("utf-16-be"))
        return "{" + ",".join(_string(name) + ":" + canonical(value[name]) for name in names) + "}"
    return _number(value)


def _number(number: float) -> str:
    """ECMAScript's Number.prototype.toString, which RFC 8785 section 3.2.2.3 names."""
    if number == 0:
        return "0"
    if number < 0:
        return "-" + _number(-number)
    # `repr` gives the shortest digits that read back as the same double, as ECMAScript does.
    mantissa, _, exponent_text = repr(number).lower().partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = (whole + fraction).lstrip("0")
    point = len(whole) - (len(whole + fraction) - len(digits)) + int(exponent_text or "0")
    digits = digits.rstrip("0")
    k, n = len(digits), point
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * -n + digits
    exponent = f"e{'+' if n - 1 >= 0 else '-'}{abs(n - 1)}"
    return (digits if k == 1 else digits[0] + "." + digits[1:]) + exponent


_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _string(text: str) -> str:
    """RFC 8785 section 3.2.2.2: the escapes JSON requires, and nothing else, with no normalisation."""
    escaped = (
        _ESCAPES.get(character, f"\\u{ord(character):04x}" if ord(character) < 0x20 else character)
        for character in text
    )
    return '"' + "".join(escaped) + '"'


def content_hash(value: JsonValue) -> str:
    """`record_format.md` section 9 item 1: the hash of `value` as stored, less the members it names."""
    if isinstance(value, dict):
        # record_format.md:548 "the top-level `content_hash` and `card`"
        value = {name: member for name, member in value.items() if name not in ("content_hash", "card")}
    digest = hashlib.sha256(canonical(_without_reviews(value, inside_provenance=False)).encode("utf-8"))
    # record_format.md:554 "`sha256:` followed by the 64 lowercase hexadecimal digits of the digest"
    return "sha256:" + digest.hexdigest()


def _without_reviews(value: JsonValue, *, inside_provenance: bool) -> JsonValue:
    # record_format.md:548-549 "every member named `review` or `copy` at any depth inside any object that is
    # the value of a member named `provenance`"
    if isinstance(value, list):
        return [_without_reviews(item, inside_provenance=inside_provenance) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        name: _without_reviews(
            member, inside_provenance=inside_provenance or (name == "provenance" and isinstance(member, dict))
        )
        for name, member in value.items()
        if not (inside_provenance and name in ("review", "copy"))
    }
