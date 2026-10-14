# SPDX-License-Identifier: Apache-2.0
"""The core's hand-written envelope checks and the generated reader schema accept and refuse the same values:
every conformance input that parses, records or not.

The reader reads with `envelope.py`; `record.reader.json` is for readers in other languages, and must say the
same (`record_format.md` section 1 item 2). Records drawn near each boundary are the property's
(`tests/property/test_envelope_properties.py`).
"""

from pathlib import Path

import pytest

from materica.core import jsonio
from materica.core.envelope import envelope_problems
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.spec_sync.schemas import PACKAGE, validator

READER = validator("record.reader.json")


def parsed(path: Path) -> JsonValue | Reason:
    return jsonio.parse(path.read_bytes())


VECTORS = [
    path
    for path in sorted(PACKAGE.glob("data/conformance/*/inputs/*"))
    if not isinstance(parsed(path), Reason)
]


@pytest.mark.parametrize("path", VECTORS, ids=lambda path: f"{path.parent.parent.name}/{path.name}")
def test_the_envelope_checks_agree_with_the_reader_schema(path: Path) -> None:
    value = parsed(path)
    assert not isinstance(value, Reason)
    assert (envelope_problems(value) == []) == (READER(value) == []), envelope_problems(value)


def test_the_vectors_hold_both_answers() -> None:
    """A comparison that met only one answer could not tell two checks apart (56 of 199 accept)."""
    values = [value for path in VECTORS if not isinstance(value := parsed(path), Reason)]
    accepted = sum(envelope_problems(value) == [] for value in values)
    assert 0 < accepted < len(VECTORS)
