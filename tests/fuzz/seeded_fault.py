# SPDX-License-Identifier: Apache-2.0
"""A fault seeded in `jsonio.parse`, which shows that the fuzz targets find a fault and that the replay
shrinks it: an exception escapes when the bytes read as an array whose first item is an empty object.

The fuzz targets seed it when `MATERICA_FUZZ_SEEDED_FAULT` is set; pytest seeds it when loaded as a plugin,
`python -m pytest -p tests.fuzz.seeded_fault`. No seed input holds the shape, so a fuzzer has to build it.
"""

import os

import pytest

from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason

_parse = jsonio.parse


def faulty_parse(data: bytes) -> JsonValue | Reason:
    value = _parse(data)
    if isinstance(value, list) and value and value[0] == {}:
        raise IndexError("the seeded fault")
    return value


def seed() -> None:
    jsonio.parse = faulty_parse


def seed_if_asked() -> None:
    if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT"):
        seed()


def pytest_configure(config: pytest.Config) -> None:
    seed()
