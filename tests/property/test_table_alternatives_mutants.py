# SPDX-License-Identifier: Apache-2.0
"""Mutants of S4d's step 7 over a table alternative whose read gives a reason at step 11 (`core/read.py`'s
`_standing` and the rules it calls, `_gives`, `_entry`, and the read up to step 11), each with one fault, and
the property of `test_table_alternatives_properties.py` that must kill it: the S4 design's mutants of HP39 and
HP40 (its section 6.6), and those the code invites. As in `test_alternatives_mutants.py`, each must die within
the examples the `ci` profile gives a property, at both sizes, at an example of a way it names, and at the
assertion it names, and records the examples its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function of `read`.
"""

import dataclasses
import re
from collections.abc import Callable, Collection, Sequence
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import read
from materica.core.fields import RecordField
from materica.core.read import FieldRead, Nominal, ReadRequest, ReadResult
from materica.core.reasons import Reason, merged, tagged
from materica.core.value_shapes import JsonObject, a_list, an_object
from materica.shapes import Suite
from tests.property import table_alternatives_strategies as strategies
from tests.property import test_table_alternatives_properties as properties
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.table_alternatives_strategies import INSIDE, KEPT_OR_SET_ASIDE, REFUSES
from tests.property.test_condition_mutants import kill

# Each property that kills a mutant, by name: its examples at a size and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None]]] = {
    "HP39 kept or set aside": (
        lambda size: strategies.table_alternatives(size, KEPT_OR_SET_ASIDE),
        properties.check_table_alternative,
    ),
    "HP39 refuses": (
        lambda size: strategies.table_alternatives(size, REFUSES),
        properties.check_table_alternative,
    ),
    "HP40": (lambda size: strategies.table_alternatives(size, (INSIDE,)), properties.check_narrowed),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # the table's ways, one of which the example that kills it must show
    says: str  # a pattern the message of the assertion that kills it must match: what the fault changes


def replacing(name: str, value: object) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setattr(read, name, value)


# The functions the faults wrap, taken before any replaces them.
READ_ALTERNATIVES = read._read_alternatives  # pyright: ignore[reportPrivateUsage]
READ_VALUE_FIELD = read.read_value_field
STANDING = read._standing  # pyright: ignore[reportPrivateUsage]
STANDING_AT_STEP_11 = read._standing_at_step_11  # pyright: ignore[reportPrivateUsage]
SET_ASIDE_BY_ITS_RANGE = read._set_aside_by_its_range  # pyright: ignore[reportPrivateUsage]
FOUND_READING = read._found_reading  # pyright: ignore[reportPrivateUsage]
REPORTED_BESIDE = read._reported_beside_two_or_more  # pyright: ignore[reportPrivateUsage]
GIVES = read._gives  # pyright: ignore[reportPrivateUsage]
ENTRY = read._entry  # pyright: ignore[reportPrivateUsage]
STATUS = read._status  # pyright: ignore[reportPrivateUsage]
LABELS = read._labels  # pyright: ignore[reportPrivateUsage]


def codes(found: FieldRead) -> set[str]:
    return {reason.code for reason in found.reasons}


def outside_alone(found: FieldRead) -> bool:
    return found.form_range is not None and found.form_range.outside_alone


def kept(found: FieldRead) -> bool:
    return found.form_range is not None and found.form_range.extrapolation is not None


def over_a_range(found: FieldRead) -> bool:
    return found.form_range is not None and found.form_range.over_a_range


# Where a table alternative stands.


def _an_edge_sets_aside(found: FieldRead) -> str:
    return "set_aside" if "at_edge" in codes(found) else STANDING_AT_STEP_11(found)


def _an_edge_outside_the_range_sets_aside(found: FieldRead) -> bool:
    """`outside_range` set aside whether or not `at_edge` stands beside it."""
    return "outside_range" in codes(found) and not kept(found)


def _set_aside_under_a_covering_extrapolation(found: FieldRead) -> bool:
    return outside_alone(found)


def _kept_without_an_extrapolation(found: FieldRead) -> str:
    return "stays" if outside_alone(found) else STANDING_AT_STEP_11(found)


def _outside_range_refuses(found: FieldRead) -> str:
    """Every other `not_met` refusing the field, `outside_range` among them, as before S4d."""
    return "refuses" if outside_alone(found) and not kept(found) else STANDING_AT_STEP_11(found)


def _kept_refuses(found: FieldRead) -> str:
    return "refuses" if kept(found) else STANDING_AT_STEP_11(found)


def _over_a_range_sets_aside(found: FieldRead) -> str:
    return "set_aside" if over_a_range(found) else STANDING_AT_STEP_11(found)


def _over_a_range_refuses(found: FieldRead) -> str:
    return "refuses" if over_a_range(found) else STANDING_AT_STEP_11(found)


def _request_fault_at_step_11_sets_aside(found: FieldRead) -> str:
    return "set_aside" if found.request_fault and found.form_range is not None else STANDING(found)


def _kept_under_any_want(monkeypatch: pytest.MonkeyPatch) -> None:
    """A table kept where the request carries an extrapolation at the read that its place could take, under
    any `want`: step 7 asks the request, not whether the extrapolation applies to the read."""
    carried: list[bool] = [False]

    def reading(
        field: RecordField,
        record: JsonObject,
        request: ReadRequest,
        claims: Collection[Suite],
        labels: tuple[str, ...],
        nominal: Nominal | None,
    ) -> ReadResult:
        carried[0] = request.extrapolation() is not None
        return READ_ALTERNATIVES(field, record, request, claims, labels, nominal)

    def standing(found: FieldRead) -> str:
        ranged = found.form_range
        if ranged is not None and ranged.coverable and carried[0]:
            return "stays"
        return STANDING_AT_STEP_11(found)

    monkeypatch.setattr(read, "_read_alternatives", reading)
    monkeypatch.setattr(read, "_standing_at_step_11", standing)


def _set_aside_at_step_10_reaches_step_11(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """A table alternative that step 10 sets aside refusing the field for its axis's missing operating value,
    as if it reached step 11."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    for alternative in a_list(an_object(field.value)["alternatives"]):
        value = an_object(alternative)
        table = value.get("table")
        axis = table.get("axis") if value.get("form") == "table" and isinstance(table, dict) else None
        if not isinstance(axis, str) or axis in request.operating_conditions:
            continue
        found = READ_VALUE_FIELD(RecordField(field.spec, alternative, field.section), record, request, claims)
        if found.conditions_not_met:
            missing = Reason("request_incomplete", axis, f"no operating value for the table's axis {axis}")
            return ReadResult("not_met", merged((missing, *result.reasons)), labels)
    return result


# What step 7 reports.


def _request_fault_at_step_11_tagged(found: FieldRead) -> tuple[Reason, ...]:
    assert found.alternative is not None
    if found.request_fault and found.form_range is not None:
        return tagged(found.found, found.alternative)
    return FOUND_READING(found)


def _kept_unknown_dropped_beside_two_or_more(staying: Sequence[FieldRead]) -> tuple[Reason, ...]:
    return REPORTED_BESIDE([found for found in staying if not kept(found)])


def _over_a_range_gives(found: FieldRead, stored: Any, want: Any, nominal: Any) -> bool:
    """`_gives` without its clause for a read over a range, where step 13 found nothing."""
    return GIVES(dataclasses.replace(found, form_range=None), stored, want, nominal)


def _set_aside_by_its_range_beside_the_one_left(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """The reasons of a table alternative set aside by its range reported beside the one left."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if result.conditions is None or result.alternative_values is not None:
        return result
    aside = [
        reason
        for index, alternative in enumerate(a_list(an_object(field.value)["alternatives"]))
        for found in [
            dataclasses.replace(
                READ_VALUE_FIELD(
                    RecordField(field.spec, alternative, field.section), record, request, claims
                ),
                alternative=index,
            )
        ]
        if SET_ASIDE_BY_ITS_RANGE(found)
        for reason in FOUND_READING(found)
    ]
    reasons = merged((*result.reasons, *aside))
    return dataclasses.replace(result, status=STATUS(reasons), reasons=reasons)


# A `no_pick` entry.


def _kept_entry_its_read(found: FieldRead, stored: list[Any]) -> FieldRead:
    """A kept table's entry its read under the extrapolation: the end value, `assumption` and what it
    applied."""
    return found if kept(found) else ENTRY(found, stored)


def _over_a_range_entry_its_read(found: FieldRead, stored: list[Any]) -> FieldRead:
    """An over-range table's entry with the labels of its read, which ended at step 11 before step 12 gave
    any."""
    entry = ENTRY(found, stored)
    return dataclasses.replace(entry, labels=found.labels) if over_a_range(found) else entry


def _entry_labels_of_the_first_alternative(found: FieldRead, stored: list[Any]) -> FieldRead:
    """A kept or over-range table's entry with the labels step 12 gives the first stored alternative, not its
    own: where the table is not stored first, a draw's stored index tells them apart."""
    entry = ENTRY(found, stored)
    if found.form_range is None:
        return entry
    first = an_object(stored[0])
    return dataclasses.replace(entry, labels=LABELS(first, an_object(first["provenance"])))


def _extrapolation_applied_under_no_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    """A kept table's extrapolation among what a `no_pick` read applied."""

    def entry(found: FieldRead, stored: list[Any]) -> FieldRead:
        made = ENTRY(found, stored)
        return dataclasses.replace(made, applied=found.applied) if kept(found) else made

    def reading(*arguments: Any) -> ReadResult:
        result: ReadResult = READ_ALTERNATIVES(*arguments)
        entries = [entry for entry in result.alternative_values or () if kept(entry)]
        applied = sorted({index for entry in entries for index in entry.applied})
        return dataclasses.replace(result, applied=(*result.applied, *applied)) if applied else result

    monkeypatch.setattr(read, "_entry", entry)
    monkeypatch.setattr(read, "_read_alternatives", reading)


KEPT = ("kept",)
OVER = ("over_an_operating_range",)
EDGES = ("at_an_edge_inside", "at_an_edge_outside")
# What a fault of a standing changes: the status, the reasons, which members the result holds, or, under
# `no_pick`, its entries.
STANDS = "^(status|reasons|members|alternative_values)"

MUTANTS: list[Mutant] = [
    Mutant(
        "an_edge_sets_aside",
        "HP39 refuses",
        replacing("_standing_at_step_11", _an_edge_sets_aside),
        EDGES,
        STANDS,
    ),
    Mutant(
        "an_edge_outside_the_range_sets_aside",
        "HP39 refuses",
        replacing("_set_aside_by_its_range", _an_edge_outside_the_range_sets_aside),
        ("at_an_edge_outside",),
        STANDS,
    ),
    Mutant(
        "set_aside_under_a_covering_extrapolation",
        "HP39 kept or set aside",
        replacing("_set_aside_by_its_range", _set_aside_under_a_covering_extrapolation),
        KEPT,
        "^(status|reasons|members|alternative_values|applied)",
    ),
    Mutant(
        "kept_without_an_extrapolation",
        "HP39 kept or set aside",
        replacing("_standing_at_step_11", _kept_without_an_extrapolation),
        ("outside", "kept_under_bounds"),
        STANDS,
    ),
    Mutant(
        "kept_under_any_want",
        "HP39 kept or set aside",
        _kept_under_any_want,
        ("kept_under_bounds",),
        STANDS,
    ),
    Mutant(
        "kept_refuses",
        "HP39 kept or set aside",
        replacing("_standing_at_step_11", _kept_refuses),
        KEPT,
        STANDS,
    ),
    Mutant(
        "over_a_range_sets_aside",
        "HP39 kept or set aside",
        replacing("_standing_at_step_11", _over_a_range_sets_aside),
        OVER,
        STANDS,
    ),
    Mutant(
        "over_a_range_refuses",
        "HP39 kept or set aside",
        replacing("_standing_at_step_11", _over_a_range_refuses),
        OVER,
        STANDS,
    ),
    Mutant(
        "over_a_range_gives",
        "HP39 kept or set aside",
        replacing("_gives", _over_a_range_gives),
        OVER,
        STANDS,
    ),
    Mutant(
        "request_fault_at_step_11_sets_aside",
        "HP39 refuses",
        replacing("_standing", _request_fault_at_step_11_sets_aside),
        ("no_operating_value",),
        STANDS,
    ),
    Mutant(
        "request_fault_at_step_11_tagged",
        "HP39 refuses",
        replacing("_found_reading", _request_fault_at_step_11_tagged),
        ("no_operating_value",),
        "^reasons",
    ),
    Mutant(
        "set_aside_at_step_10_reaches_step_11",
        "HP39 refuses",
        replacing("_read_alternatives", _set_aside_at_step_10_reaches_step_11),
        ("no_operating_value_set_aside",),
        STANDS,
    ),
    Mutant(
        "kept_entry_its_read",
        "HP39 kept or set aside",
        replacing("_entry", _kept_entry_its_read),
        KEPT,
        "^alternative_values",
    ),
    Mutant(
        "extrapolation_applied_under_no_pick",
        "HP39 kept or set aside",
        _extrapolation_applied_under_no_pick,
        KEPT,
        "^applied",
    ),
    Mutant(
        "over_a_range_entry_without_step_12_labels",
        "HP39 kept or set aside",
        replacing("_entry", _over_a_range_entry_its_read),
        OVER,
        "^alternative_values",
    ),
    Mutant(
        "entry_labels_of_the_first_alternative",
        "HP39 kept or set aside",
        replacing("_entry", _entry_labels_of_the_first_alternative),
        ("over_an_operating_range", "kept"),
        "^alternative_values",
    ),
    Mutant(
        "kept_unknown_dropped_beside_two_or_more",
        "HP39 kept or set aside",
        replacing("_reported_beside_two_or_more", _kept_unknown_dropped_beside_two_or_more),
        KEPT,
        "^reasons",
    ),
    Mutant(
        "outside_range_refuses",
        "HP40",
        replacing("_standing_at_step_11", _outside_range_refuses),
        (INSIDE,),
        STANDS,
    ),
    Mutant(
        "narrowed_alternative_kept",
        "HP40",
        replacing("_standing_at_step_11", _kept_without_an_extrapolation),
        (INSIDE,),
        STANDS,
    ),
    Mutant(
        "set_aside_by_its_range_beside_the_one_left",
        "HP40",
        replacing("_read_alternatives", _set_aside_by_its_range_beside_the_one_left),
        (INSIDE,),
        "^(status|reasons)",
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_table_alternatives_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the ways it names, and at the assertion it names."""
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    said: list[str] = []

    def checked(example: Any) -> None:
        try:
            check(example)
        except AssertionError as error:
            said.append(str(error))
            raise

    tried, example = kill(examples(size), checked)
    record_property("examples_to_kill", tried)
    assert example.way in mutant.dies_at, example.way
    assert re.search(mutant.says, said[0]), said[0]
