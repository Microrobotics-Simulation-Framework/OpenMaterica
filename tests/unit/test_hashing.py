# SPDX-License-Identifier: Apache-2.0
"""What the conformance cases do not check of the hash: that the view leaves stored JSON alone, and the
package's export."""

import copy
import re
from collections.abc import Iterator

import materica
from materica.core import hashing
from materica.core.jsonio import JsonValue, parse

RECORD = b'{"card": "c", "a": [{"provenance": {"review": {"by": "x"}, "copy": [1], "kept": [2, {"b": 3}]}}]}'


def containers(value: JsonValue) -> Iterator[JsonValue]:
    if isinstance(value, list | dict):
        yield value
        for child in value.values() if isinstance(value, dict) else value:
            yield from containers(child)


def test_the_view_changes_nothing_and_shares_no_container() -> None:
    value = parse(RECORD)
    assert isinstance(value, dict)
    stored = copy.deepcopy(value)
    view = hashing.hashable_view(value)
    assert value == stored
    assert view == {"a": [{"provenance": {"kept": [2.0, {"b": 3.0}]}}]}
    assert not {id(container) for container in containers(view)} & {id(c) for c in containers(value)}


def test_the_hash_is_sha256_in_lowercase_hexadecimal() -> None:
    value = parse(RECORD)
    assert isinstance(value, dict)
    assert re.fullmatch("sha256:[0-9a-f]{64}", hashing.content_hash(value))
    assert materica.content_hash is hashing.content_hash
