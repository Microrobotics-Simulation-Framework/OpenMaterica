# SPDX-License-Identifier: Apache-2.0
"""A reference reader for `record_format.md` section 1 item 6: the standard library's json, with hooks that
refuse exactly the faults the item lists.

It shares no code with `jsonio.parse`. The conformance tests read every case file and input through both, so
that the runner does not rest on the reader it tests, and the first Atheris target compares the two on fuzzed
bytes.
"""

import codecs
import json
import math
import re

from materica.core.jsonio import JsonValue

LISTED = (
    "byte_order_mark",
    "not_utf8",
    "grammar",
    "repeated_name",
    "nan_or_infinity",
    "rounds_to_infinity",
    "unpaired_surrogate",
    "too_deep",
)
_SURROGATE = re.compile("[\ud800-\udfff]")


class Refused(Exception):
    """The reference reader's refusal, naming the fault of item 6 it found."""

    def __init__(self, fault: str) -> None:
        super().__init__(fault)
        self.fault = fault


def reference(data: bytes) -> JsonValue | Refused:
    """`data` read by item 6 with the standard library's json, or the refusal of the fault it holds."""
    try:
        return _reference(data)
    except Refused as refusal:
        return refusal


def _reference(data: bytes) -> JsonValue:
    if data.startswith(codecs.BOM_UTF8):
        raise Refused("byte_order_mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("not_utf8") from None
    try:
        value: JsonValue = json.loads(
            text,
            object_pairs_hook=_no_repeats,
            parse_constant=_no_constant,
            parse_float=_finite,
            parse_int=_finite,
        )
    except RecursionError:
        raise Refused("too_deep") from None
    except json.JSONDecodeError:
        raise Refused("grammar") from None
    if _deeper_than(value, 64):
        raise Refused("too_deep")
    if any(_SURROGATE.search(string) for string in _strings(value)):
        raise Refused("unpaired_surrogate")
    return value


def _no_repeats(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    if len({name for name, _ in pairs}) < len(pairs):
        raise Refused("repeated_name")
    return dict(pairs)


def _no_constant(name: str) -> float:
    raise Refused("nan_or_infinity")


def _finite(text: str) -> float:
    number = float(text)
    if math.isinf(number):
        raise Refused("rounds_to_infinity")
    return number


def _deeper_than(value: JsonValue, limit: int) -> bool:
    """Whether `value` nests more than `limit` arrays and objects.

    It walks without recursion: where the C stack allows it (CI's 3.14 and 3.15), json returns nesting far
    deeper than Python's recursion limit lets a recursive walk follow.
    """
    pending: list[tuple[JsonValue, int]] = [(value, 1)]
    while pending:
        current, depth = pending.pop()
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
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [string for item in value for string in _strings(item)]
    if isinstance(value, dict):
        return [*value, *(string for member in value.values() for string in _strings(member))]
    return []
