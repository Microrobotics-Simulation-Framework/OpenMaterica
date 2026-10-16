# SPDX-License-Identifier: Apache-2.0
"""Faults seeded in the core, which show that the fuzz targets find a fault and that the replay shrinks it.

- In `jsonio.parse`, for the first two targets: an exception escapes when the bytes read as an array whose
  first item is an empty object. No seed input holds the shape, so a fuzzer has to build it.
- In the read, for the third: an exception escapes when two copies of the target state its pin and are
  identical byte for byte, which a read must take as one record (`read_side_contract.md` section 3, step 1),
  beside an unreadable source, by a reader without the hash suite: a conjunction of three draws, which a
  fuzzer has to explore to meet.
- In step 10, for the fourth: an exception escapes for a temperature above 311 K stated with a plus or minus,
  beside a shear rate stated as a range other than 10 to 1000 1/s. No seed holds two of the three (S2a-3,
  2026-10-16): 18 hold a plus or minus on a temperature, at 310.15 K or below, 17 of them beside a shear rate
  of 10 to 1000 1/s and one beside an unstated one; three state a shear rate's range otherwise, with no plus
  or minus on their temperature; none a temperature above 311 K. So the fuzzer has to change two numbers of
  one seed, keeping the field through steps 8 and 9 to reach step 10, each change new coverage. It replaced
  the step-8 fault of S2a-2's fix round (a constant above 1 measured above 311 K whose statistics block
  represents a population's spread), which no seed held two parts of either, when the target came to read
  steps 9 and 10.

Each raises its own message, so that CI can tell which fault a run found.

The first three targets seed the first two faults when `MATERICA_FUZZ_SEEDED_FAULT` is set, and pytest seeds
them when loaded as a plugin, `python -m pytest -p tests.fuzz.seeded_fault`. Only the fourth target seeds the
third, since the property targets draw conditions too and would find it before their own.
"""

import os
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Protocol, TypeVar

import pytest

from materica.core import conditions, jsonio, read
from materica.core.conditions import ConditionsRead, ImpliedCondition
from materica.core.fields import RecordField
from materica.core.identifiers import MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.resolve import Refused, ResolvedRecord, resolve_record
from materica.shapes import OperatingCondition, RequirementCondition, Suite

_parse = jsonio.parse


def faulty_parse(data: bytes) -> JsonValue | Reason:
    value = _parse(data)
    if isinstance(value, list) and value and value[0] == {}:
        raise IndexError("the seeded fault in parse")
    return value


def faulty_resolve_record(
    ref: MaterialRef, store: RecordStore, claims: Collection[Suite]
) -> ResolvedRecord | Refused:
    pinned = [
        copy for copy in store.get(ref.id, ref.version) if copy.value.get("content_hash") == ref.content_hash
    ]
    identical = len(pinned) > 1 and all(copy.data == pinned[0].data for copy in pinned)
    if identical and store.unparsed() and "hash" not in claims:
        raise IndexError("the seeded fault in the read")
    return resolve_record(ref, store, claims)


_check_conditions = conditions.check_conditions


def faulty_check_conditions(
    field: RecordField,
    operating: Mapping[str, OperatingCondition],
    required: Mapping[str, RequirementCondition],
    implied: Sequence[ImpliedCondition] = (),
) -> ConditionsRead:
    value = field.value if isinstance(field.value, dict) else {}
    held = value.get("conditions")
    held = held if isinstance(held, dict) else {}
    temperature, shear_rate = held.get("temperature"), held.get("shear_rate")
    if isinstance(temperature, dict) and isinstance(shear_rate, dict):
        entries = temperature.get("plus_minus")
        if isinstance(entries, list) and entries:
            kelvin = temperature.get("value")
            if isinstance(kelvin, float) and kelvin > 311.0:
                ends = shear_rate.get("range")
                if isinstance(ends, list) and len(ends) == 2 and ends != [10.0, 1000.0]:
                    raise IndexError("the seeded fault in step 10")
    return _check_conditions(field, operating, required, implied)


def seed() -> None:
    jsonio.parse = faulty_parse
    read.resolve_record = faulty_resolve_record  # type: ignore[attr-defined]  # read's own name for it, not exported


def seed_if_asked() -> None:
    if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT"):
        seed()


_Function = TypeVar("_Function", bound=Callable[..., object])


class Instrument(Protocol):
    def __call__(self, function: _Function, /) -> _Function: ...


def seed_step_10_if_asked(instrument: Instrument) -> None:
    """The fourth target's fault, which only it seeds, since the property targets draw fields too.
    `instrument` is Atheris's, so that each part of the conjunction the fuzzer meets is new coverage and each
    comparison a hint, as in a real fault of the core."""
    if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT"):
        read.check_conditions = instrument(faulty_check_conditions)  # type: ignore[attr-defined]  # read's own name


def pytest_configure(config: pytest.Config) -> None:
    seed()
