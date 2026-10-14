# SPDX-License-Identifier: Apache-2.0
"""The content hash of a record, or of any JSON value (`record_format.md` section 9)."""

import hashlib

from materica.core.canonical import canonicalize
from materica.core.jsonio import JsonValue


def hashable_view(value: JsonValue) -> JsonValue:
    """`value` without the members `record_format.md` section 9 item 1 removes; `value` is left unchanged.

    The top-level `content_hash` and `card` go only when `value` is an object. `review` and `copy` go at any
    depth inside an object that is the value of a member named `provenance`, through objects and arrays.
    """
    if isinstance(value, dict):
        value = {name: member for name, member in value.items() if name not in ("content_hash", "card")}
    return _view(value, inside_provenance=False)


def _view(value: JsonValue, *, inside_provenance: bool) -> JsonValue:
    if isinstance(value, dict):
        return {
            name: _view(
                member,
                inside_provenance=inside_provenance or (name == "provenance" and isinstance(member, dict)),
            )
            for name, member in value.items()
            if not (inside_provenance and name in ("review", "copy"))
        }
    if isinstance(value, list):
        return [_view(item, inside_provenance=inside_provenance) for item in value]
    return value


def content_hash(value: JsonValue) -> str:
    """`sha256:` and the lowercase hexadecimal SHA-256 of `value`'s hashable view in RFC 8785 form."""
    return "sha256:" + hashlib.sha256(canonicalize(hashable_view(value))).hexdigest()
