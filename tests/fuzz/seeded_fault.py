# SPDX-License-Identifier: Apache-2.0
"""Faults seeded in the core, which show that the fuzz targets find a fault and that the replay shrinks it.

- In `jsonio.parse`, for the first two targets: an exception escapes when the bytes read as an array whose
  first item is an empty object. No seed input holds the shape, so a fuzzer has to build it.
- In the read, for the third: an exception escapes when two copies of the target state its pin and are
  identical byte for byte, which a read must take as one record (`read_side_contract.md` section 3, step 1),
  beside an unreadable source, by a reader without the hash suite: a conjunction of three draws, which a
  fuzzer has to explore to meet.
- In step 8, for the fourth: an exception escapes for a constant above 1 measured above 311 K whose
  statistics block represents a population's spread. No seed holds two of the three: nine seeds represent a
  population (a viscosity of 0.000692 at 310.15 K), 18 hold a value above 1 (none of them a population's
  spread, none above 311 K), and none a temperature above 311 K. So the fuzzer has to change two numbers of
  one seed, each change new coverage (S2a-2's review, L3: the earlier fault was one digit from a seed, which
  held two of its three parts).

Each raises its own message, so that CI can tell which fault a run found.

The first three targets seed the first two faults when `MATERICA_FUZZ_SEEDED_FAULT` is set, and pytest seeds
them when loaded as a plugin, `python -m pytest -p tests.fuzz.seeded_fault`. Only the fourth target seeds the
third, since the property targets draw statistics blocks too and would find it before their own.
"""

import os
from collections.abc import Callable, Collection
from typing import Protocol, TypeVar

import pytest

from materica.core import fields, jsonio, read
from materica.core.fields import RecordField
from materica.core.identifiers import MaterialRef
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.core.resolve import Refused, ResolvedRecord, resolve_record
from materica.shapes import Suite

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


_form_problems = fields.form_problems


def faulty_form_problems(
    field: RecordField, record: dict[str, JsonValue], claims: Collection[Suite]
) -> list[Reason]:
    value = field.value if isinstance(field.value, dict) else {}
    statistics = value.get("statistics")
    if isinstance(statistics, dict) and statistics.get("represents") == "population":
        constant = value.get("value")
        if isinstance(constant, float) and constant > 1.0:
            conditions = value.get("conditions")
            temperature = conditions.get("temperature") if isinstance(conditions, dict) else None
            kelvin = temperature.get("value") if isinstance(temperature, dict) else None
            if isinstance(kelvin, float) and kelvin > 311.0:
                raise IndexError("the seeded fault in step 8")
    return _form_problems(field, record, claims)


def seed() -> None:
    jsonio.parse = faulty_parse
    read.resolve_record = faulty_resolve_record  # type: ignore[attr-defined]  # read's own name for it, not exported


def seed_if_asked() -> None:
    if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT"):
        seed()


_Function = TypeVar("_Function", bound=Callable[..., object])


class Instrument(Protocol):
    def __call__(self, function: _Function, /) -> _Function: ...


def seed_step_8_if_asked(instrument: Instrument) -> None:
    """The fourth target's fault, which only it seeds, since the property targets draw fields too.
    `instrument` is Atheris's, so that each part of the conjunction the fuzzer meets is new coverage and each
    comparison a hint, as in a real fault of the core."""
    if os.environ.get("MATERICA_FUZZ_SEEDED_FAULT"):
        read.form_problems = instrument(faulty_form_problems)  # type: ignore[attr-defined]  # read's own name


def pytest_configure(config: pytest.Config) -> None:
    seed()
