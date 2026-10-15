# SPDX-License-Identifier: Apache-2.0
"""(8) Step 8's laws (`read_side_contract.md` section 3, step 8), over records holding a constant drawn from
`value_field_strategies.py`. The mutants they kill are in `test_value_field_mutants.py`.

- **HP3, one fault, one refusal.** A field that passes step 8, given one fault of the catalogue, is refused
  with exactly the codes the fault's rule gives and no other, `not_met`; given a fault that breaks no rule
  step 8 checks (a condition name the reader does not know, a member it does not check, broken), it still
  passes. In a quarter of the draws, two faults of two regions give the codes of both: each step makes all its
  checks.
- **HP5, ignorance.** Members the reader does not know, added where they may go, never change the outcome,
  whether the field passes step 8 or a fault refuses it: a name more than one slip from every member named at
  its place is ignored, two slips off included. The pin is recomputed. As the S2 design says, no member is
  added to a `conditions` map, where a new name is a condition, nor to a status object.

A read that passes step 8 raises `NotImplementedError` until steps 9 to 13 are built: that is the outcome
"past step 8".
"""

import copy
import json
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from tests.property import records
from tests.property.strategies import SIZE, Size
from tests.property.support import feature
from tests.property.value_field_strategies import (
    Example,
    JsonObject,
    faulty_records,
    pinned,
    valid_records,
)

PAST_STEP_8 = "past step 8"


class Outcome(NamedTuple):
    status: str  # the result's, or PAST_STEP_8
    codes: frozenset[str]


def outcome(record: JsonObject, field: str) -> Outcome:
    """The read of `field` in `record`, pinned by its recomputed hash."""
    record = pinned(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    request: JsonObject = {"target": {"record": pin, "field": field}, "requirement": {"want": "value"}}
    try:
        result = read(request, store)
    except NotImplementedError:
        return Outcome(PAST_STEP_8, frozenset())
    return Outcome(result.status, frozenset(reason.code for reason in result.reasons))


# HP3: one fault, one refusal.


def check_one_fault(example: Example) -> None:
    found = outcome(example.record, example.field)
    expected = Outcome("not_met", example.expected) if example.expected else Outcome(PAST_STEP_8, frozenset())
    assert found == expected, example.faults


def fault_features(example: Example) -> None:
    for fault in example.faults:
        feature(f"region_{fault.partition('.')[0]}")
    feature("two_faults", len(example.faults) == 2)
    feature("passes", not example.expected)
    feature("unknown_token", "unknown_token" in example.expected)
    feature("two_codes", len(example.expected) == 2)


# Least shares, about a third of those measured.
@pytest.mark.features(
    region_statistics_tokens=0.11,
    region_statistics_numbers=0.033,
    region_statistics_statuses=0.024,
    region_statistics_members=0.015,
    region_statistics_slips=0.02,
    region_uncertainty=0.024,
    region_conditions=0.033,
    region_specimen=0.024,
    region_record=0.018,
    region_provenance=0.021,
    region_field=0.022,
    two_faults=0.048,
    unknown_token=0.046,
    two_codes=0.025,
    passes=0.001,
)
@given(faulty_records())
def test_one_fault_gives_its_refusal_and_no_other(example: Example) -> None:
    fault_features(example)
    check_one_fault(example)


def check_passes(example: Example) -> None:
    assert outcome(example.record, example.field) == Outcome(PAST_STEP_8, frozenset())


@given(valid_records())
def test_a_field_without_a_fault_passes_step_8(example: Example) -> None:
    """The base of every draw passes step 8: without it, HP3's refusals could come from the base."""
    check_passes(example)


# HP5: ignorance.

# Where a member is added, by the kind of place: an object of the record's structure, the field, an object
# inside it, or one inside a member step 8 does not check.
UNCHECKED = frozenset({"extraction", "assistance", "review", "fit", "evidence", "document", "locator"})


class Unknowns(NamedTuple):
    example: Example
    additions: tuple[tuple[tuple[str, ...], str, JsonValue], ...]  # place, name, value


def places(value: JsonValue, here: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """The objects in `value` a member may be added to: every one but a `conditions` map and a status
    object."""
    if not isinstance(value, dict):
        return []
    found: list[tuple[str, ...]] = [] if "status" in value or here[-1:] == ("conditions",) else [here]
    for name, member in value.items():
        found += places(member, (*here, name))
    return found


def place_kind(place: tuple[str, ...]) -> str:
    if UNCHECKED & set(place):
        return "unchecked"
    if len(place) <= 4:
        return "structure"
    return "field" if len(place) == 5 else "inside_the_field"


@st.composite
def with_unknowns(draw: st.DrawFn, size: Size = SIZE) -> Unknowns:
    """A valid record, or in one draw in three one with a fault, and one to four members added, each named
    `x_` and letters or, in one draw in three, a member at its place with two characters added."""
    faulty = draw(st.integers(0, 2)) == 0
    example = draw(faulty_records(size, faults=1) if faulty else valid_records(size))
    where = places(example.record)
    additions: list[tuple[tuple[str, ...], str, JsonValue]] = []
    for _ in range(draw(st.integers(1, 4))):
        place = draw(st.sampled_from(where))
        found = records.at(example.record, place)
        present = sorted(found) if isinstance(found, dict) else []
        if present and draw(st.integers(0, 2)) == 0:
            name = draw(st.sampled_from(present)) + "xx"
        else:
            name = "x_" + draw(st.text("abcdefghij", min_size=1, max_size=6))
        additions.append((place, name, draw(records.trees(size).values)))
    return Unknowns(example, tuple(additions))


def check_ignored(unknowns: Unknowns) -> None:
    example = unknowns.example
    record = copy.deepcopy(example.record)
    for place, name, value in unknowns.additions:
        records.changed(record, (*place, name), copy.deepcopy(value))
    assert outcome(record, example.field) == outcome(example.record, example.field)


@pytest.mark.features(
    structure=0.25, field=0.045, inside_the_field=0.11, unchecked=0.065, two_slips=0.23, faulty_base=0.11
)
@given(with_unknowns())
def test_members_the_reader_does_not_know_change_nothing(unknowns: Unknowns) -> None:
    for place, name, _ in unknowns.additions:
        feature(place_kind(place))
        feature("two_slips", name.endswith("xx"))
    feature("faulty_base", bool(unknowns.example.faults))
    check_ignored(unknowns)
