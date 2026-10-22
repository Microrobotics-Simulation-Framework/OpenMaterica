# SPDX-License-Identifier: Apache-2.0
"""Mutants of S3b-2's table read through steps 10 to 13 (`core/read.py`'s `form_range` and `axis_status`,
`core/evaluate.py`, `core/conditions.py`'s step 10), each with one fault, and the property of
`test_table_read_properties.py` that must kill it: the S3 design's mutants of HP20 to HP23. As in
`test_table_form_mutants.py`, each must die within the examples the `ci` profile gives a property, at both
sizes, at an example of a way it names, and at the assertion it names, and records the examples its kill
took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function of `read`,
`evaluate`, `conditions` or `fields`.
"""

import dataclasses
import re
from bisect import bisect_left
from collections.abc import Callable, Collection, Sequence
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica import shapes
from materica.core import conditions, evaluate, fields
from materica.core import read as read_module
from materica.core.conditions import AxisEntry, ConditionsRead, ImpliedCondition
from materica.core.fields import RecordField
from materica.core.read import FormRange, ReadRequest
from materica.core.reasons import Reason
from materica.core.status import ReadStatus
from materica.core.value_shapes import JsonObject
from tests.property import table_read_strategies as strategies
from tests.property import test_table_read_properties as properties
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill

# Each property that kills a mutant, by name: its examples at a size, its check, and the way an example drew.
Killer = tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None], Callable[[Any], str]]


def way_of(drawn: strategies.TableRead) -> str:
    return drawn.way


KILLERS: dict[str, Killer] = {
    "HP20": (lambda size: strategies.edge_reads(size), properties.check_edge, way_of),
    # A planned search of HP20: across an edge alone, the way that draws an edge on the readable range's end
    # (in half its draws, on one end or the other), where the mutants of step 11's report on such an edge
    # show; over HP20's five ways they died after the 500th example on 1 or 2 of 40 streams a size.
    "HP20, across an edge": (
        lambda size: strategies.edge_reads(size, ("across_an_edge",)),
        properties.check_edge,
        way_of,
    ),
    "HP21": (lambda size: strategies.range_reads(size), properties.check_range, way_of),
    "HP21 no wider and tolerance": (
        properties.no_wider_and_tolerance,
        properties.check_no_wider_and_tolerance,
        lambda example: example[0].way,
    ),
    "HP22": (lambda size: strategies.statistics_reads(size), properties.check_statistics, way_of),
    "HP23": (lambda size: strategies.request_reads(size), properties.check_request, way_of),
    "monotonicity": (
        lambda size: strategies.met_worlds(size),
        properties.check_monotone,
        lambda world: world.way,
    ),
    # A planned search of the monotonicity property: one double outside alone, its region, which a
    # `source_range` reaching past `x`'s end on the read's side covers (one kind in five of `source_range`, on
    # one side of two); over its four ways it died after 300 examples on some streams.
    "monotonicity, one double outside": (
        lambda size: strategies.met_worlds(size, ("one_double_outside",)),
        properties.check_monotone,
        lambda world: world.way,
    ),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # the ways one of which the example that kills it must show
    says: str  # a pattern the message of the assertion that kills it must match


def replacing(module: object, name: str, value: object) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setattr(module, name, value)


def both(*injections: Callable[[pytest.MonkeyPatch], None]) -> Callable[[pytest.MonkeyPatch], None]:
    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        for injection in injections:
            injection(monkeypatch)

    return inject


# The functions the faults wrap, taken before any replaces them.
FORM_RANGE = read_module.form_range
AXIS_STATUS = read_module.axis_status
CHECK_CONDITIONS = conditions.check_conditions
READ_VALUE_FIELD = read_module.read_value_field
BEYOND_AN_EDGE = evaluate.beyond_an_edge


def _numbers(table: JsonObject, name: str) -> list[float]:
    found = table.get(name)
    return [float(number) for number in found if isinstance(number, float)] if isinstance(found, list) else []


def _axis_value(table: JsonObject, request: ReadRequest) -> float | None:
    operating = request.operating_conditions.get(str(table["axis"]))
    return operating["value"] if operating is not None and "value" in operating else None  # type: ignore[typeddict-item]


# HP20's.


def _edge_read_from_the_interval_above(table: JsonObject, request: ReadRequest) -> FormRange:
    """At an edge inside the readable range, the value of the interval above, and no refusal."""
    at = _axis_value(table, request)
    x, y = _numbers(table, "x"), _numbers(table, "y")
    low, high = evaluate.readable_range(x, table.get("source_range"))  # type: ignore[arg-type]
    if at is not None and at in _numbers(table, "edges") and low <= at <= high:
        return FormRange(value=y[x.index(at) + 1])
    return FORM_RANGE(table, request)


def _below_an_edge_from_the_degenerate_interval(x: Sequence[float], at: float) -> tuple[int, int]:
    """The knots that bracket `at`, but just below an edge the edge's own two entries, a degenerate
    interval."""
    above = bisect_left(x, at)
    if x[above] == at:
        return above, above
    if above + 1 < len(x) and x[above] == x[above + 1]:
        return above, above + 1
    return above - 1, above


def _at_edge_dropped_beside_outside_range(table: JsonObject, request: ReadRequest) -> FormRange:
    found = FORM_RANGE(table, request)
    codes = {reason.code for reason in found.reasons}
    if {"at_edge", "outside_range"} <= codes:
        kept = tuple(reason for reason in found.reasons if reason.code != "at_edge")
        return FormRange(kept, outside_alone=True, coverable=True)
    return found


def _range_checked_before_the_edge(table: JsonObject, request: ReadRequest) -> FormRange:
    """Outside the readable range, `outside_range` alone and an extrapolation's to cover, the edge
    unchecked."""
    at = _axis_value(table, request)
    x = _numbers(table, "x")
    source_range = table.get("source_range")
    if at is not None and not evaluate.in_readable_range(x, source_range, at):  # type: ignore[arg-type]
        axis = str(table["axis"])
        return FormRange((Reason("outside_range", axis),), outside_alone=True, coverable=True)
    return FORM_RANGE(table, request)


def _an_edge_on_the_lower_end_not_across(
    x: Sequence[float], edges: Collection[float], source_range: Sequence[float] | None, at: float
) -> bool:
    """Below the readable range, an edge on its lower end read as none between the read and the range, so
    that a read beyond it is reported coverable by an extrapolation (`read_side_contract.md` section 5: "or
    on that end")."""
    low, _ = evaluate.readable_range(x, source_range)
    if at < low:
        return any(at < edge < low for edge in edges)
    return BEYOND_AN_EDGE(x, edges, source_range, at)


def _an_edge_on_the_upper_end_not_across(
    x: Sequence[float], edges: Collection[float], source_range: Sequence[float] | None, at: float
) -> bool:
    """Above the readable range, the same of an edge on its upper end."""
    _, high = evaluate.readable_range(x, source_range)
    if at > high:
        return any(high < edge < at for edge in edges)
    return BEYOND_AN_EDGE(x, edges, source_range, at)


# HP21's.


def _ends_by_strict_inequality(x: Sequence[float], source_range: Sequence[float] | None, at: float) -> bool:
    low, high = evaluate.readable_range(x, source_range)
    return low < at < high


def _source_range_ignored(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    return x[0], x[-1]


def _source_range_widening(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    if source_range is None:
        return x[0], x[-1]
    return min(x[0], source_range[0]), max(x[-1], source_range[1])


def _widened_by_the_tolerance(table: JsonObject, request: ReadRequest) -> ReadRequest:
    """The request read as if the readable range were widened by its tolerance on the table's axis, as a
    `source_range` no narrower than `x` would not: a read outside the range by no more than the tolerance
    moved to the range's nearest end, where the table gives its end value. (Read at the operating value
    itself, a log-log table's exact evaluation beyond `x` can take minutes.)"""
    axis, at = str(table["axis"]), _axis_value(table, request)
    required = request.conditions.get(axis)
    if at is None or required is None or "tolerance" not in required:
        return request
    tolerance = required["tolerance"]["value"]  # type: ignore[typeddict-item]
    low, high = evaluate.readable_range(_numbers(table, "x"), table.get("source_range"))  # type: ignore[arg-type]
    nearest = low if low - tolerance <= at < low else high if high < at <= high + tolerance else at
    if nearest == at:
        return request
    moved = {**request.operating_conditions, axis: {**request.operating_conditions[axis], "value": nearest}}
    return dataclasses.replace(request, operating_conditions=moved)  # type: ignore[arg-type]


def _the_tolerance_widens_the_range(table: JsonObject, request: ReadRequest) -> FormRange:
    return FORM_RANGE(table, _widened_by_the_tolerance(table, request))


def _the_tolerance_widens_the_axis_entry(table: JsonObject, request: ReadRequest) -> ReadStatus:
    return AXIS_STATUS(table, _widened_by_the_tolerance(table, request))


def _outside_at_step_10(
    field: RecordField,
    operating: Any,
    required: Any,
    implied: Sequence[ImpliedCondition] = (),
    axis: AxisEntry | None = None,
) -> ConditionsRead:
    """The axis entry's `not_met` given a reason at step 10, `condition_outside`, which ends the read
    there."""
    found = CHECK_CONDITIONS(field, operating, required, implied, axis)
    if axis is None or axis.status != "not_met" or found.entries is None:
        return found
    return ConditionsRead(
        (*found.reasons, Reason("condition_outside", axis.name)), found.entries, found.applied
    )


# HP22's.


def _points_ignored(entry: JsonObject, where: str, found: Any) -> None:
    return None


def _the_nearest_knots_block(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[shapes.Suite],
    nominal: Any = None,
) -> read_module.FieldRead:
    """`points` read: the block of the knot nearest the operating value in place of the table's."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    value = field.value if isinstance(field.value, dict) else {}
    table = value.get("table")
    points = table.get("points") if isinstance(table, dict) else None
    at = _axis_value(table, request) if isinstance(table, dict) else None
    if not isinstance(points, list) or at is None or found.statistics is None:
        return found
    x = _numbers(table, "x")  # type: ignore[arg-type]
    nearest = min(range(len(x)), key=lambda index: abs(x[index] - at))
    entry = points[nearest]
    block = entry.get("statistics") if isinstance(entry, dict) else None
    return found if not isinstance(block, dict) else dataclasses.replace(found, statistics=block)


def _a_member_dropped_from_the_tables_block(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[shapes.Suite],
    nominal: Any = None,
) -> read_module.FieldRead:
    """A table's statistics block returned without its first member, as stored: the block not as stored at a
    read (HP22's clause "the table's block, as stored, at every read")."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    value = field.value if isinstance(field.value, dict) else {}
    if value.get("form") != "table" or not found.statistics:
        return found
    first = next(iter(found.statistics))
    return dataclasses.replace(
        found, statistics={name: member for name, member in found.statistics.items() if name != first}
    )


# HP23's.


def _range_mismatch_without_its_axis(table: JsonObject, request: ReadRequest) -> FormRange:
    found = FORM_RANGE(table, request)
    if found.over_a_range:
        return FormRange((Reason("want_mismatch"),), over_a_range=True)
    return found


def _outside_range_beside_a_range_across_an_end(table: JsonObject, request: ReadRequest) -> FormRange:
    found = FORM_RANGE(table, request)
    operating = request.operating_conditions.get(str(table["axis"]))
    if not found.over_a_range or operating is None or "range" not in operating:
        return found
    lo, hi = operating["range"]  # type: ignore[typeddict-item]
    low, high = evaluate.readable_range(_numbers(table, "x"), table.get("source_range"))  # type: ignore[arg-type]
    if lo < low or hi > high:
        axis = str(table["axis"])
        return FormRange((*found.reasons, Reason("outside_range", axis)), over_a_range=True)
    return found


INSIDE_ENDS = ("at_an_end",)
OUTSIDE = ("one_double_outside", "far_outside", "outside_a_narrower_source_range")

MUTANTS = [
    Mutant(
        "edge_read_from_the_interval_above",
        "HP20",
        replacing(read_module, "form_range", _edge_read_from_the_interval_above),
        ("at_an_edge_inside",),
        "^the at_an_edge_inside read's step 11",
    ),
    Mutant(
        "below_an_edge_from_the_degenerate_interval",
        "HP20",
        replacing(evaluate, "interval", _below_an_edge_from_the_degenerate_interval),
        # Any read in an interval whose upper knot is an edge: just above an edge too, where the interval
        # above ends at another edge.
        ("just_below_an_edge", "just_above_an_edge"),
        "^the just_(below|above)_an_edge read: raised",
    ),
    Mutant(
        "at_edge_dropped_beside_outside_range",
        "HP20",
        replacing(read_module, "form_range", _at_edge_dropped_beside_outside_range),
        ("at_an_edge_outside",),
        "^the at_an_edge_outside read's step 11",
    ),
    Mutant(
        "range_checked_before_the_edge",
        "HP20",
        replacing(read_module, "form_range", _range_checked_before_the_edge),
        # Beyond an edge outside the range too, a read it reports coverable across the edge.
        ("at_an_edge_outside", "across_an_edge"),
        "^the (at_an_edge_outside read's step 11|across_an_edge read reported coverable)",
    ),
    # The review's hand mutant of step 11's report on an edge on the readable range's end, on each end,
    # searched by HP20 across an edge (planned). The report has a reader in a result only where an
    # extrapolation meets such an edge (S3c, and S4d's step 7), which HP12 draws nowhere, so HP12 cannot
    # search these (`test_model_mutants.REPORT_ALONE`).
    Mutant(
        "an_edge_on_the_lower_end_not_across",
        "HP20, across an edge",
        replacing(evaluate, "beyond_an_edge", _an_edge_on_the_lower_end_not_across),
        ("across_an_edge",),
        "^the across_an_edge read reported coverable",
    ),
    Mutant(
        "an_edge_on_the_upper_end_not_across",
        "HP20, across an edge",
        replacing(evaluate, "beyond_an_edge", _an_edge_on_the_upper_end_not_across),
        ("across_an_edge",),
        "^the across_an_edge read reported coverable",
    ),
    Mutant(
        "ends_by_strict_inequality",
        "HP21",
        replacing(evaluate, "in_readable_range", _ends_by_strict_inequality),
        INSIDE_ENDS,
        "^the at_an_end read's step 11",
    ),
    Mutant(
        "source_range_ignored",
        "HP21",
        replacing(evaluate, "readable_range", _source_range_ignored),
        OUTSIDE,
        "read's step 11",
    ),
    Mutant(
        "source_range_widening",
        "HP21",
        replacing(evaluate, "readable_range", _source_range_widening),
        OUTSIDE,
        "^the (one_double_outside|far_outside|outside_a_narrower_source_range) read",
    ),
    Mutant(
        "the_tolerance_widens_the_range",
        "HP21 no wider and tolerance",
        both(
            replacing(read_module, "form_range", _the_tolerance_widens_the_range),
            replacing(read_module, "axis_status", _the_tolerance_widens_the_axis_entry),
        ),
        ("one_double_outside", "far_outside"),
        "^a tolerance",
    ),
    Mutant(
        "outside_at_step_10",
        "HP21",
        replacing(read_module, "check_conditions", _outside_at_step_10),
        OUTSIDE,
        "read's step 11",
    ),
    Mutant(
        "points_ignored",
        "HP22",
        replacing(fields, "_points", _points_ignored),
        ("holding_points",),
        "^a table holding points read",
    ),
    Mutant(
        "the_nearest_knots_block",
        "HP22",
        both(
            replacing(fields, "_points", _points_ignored),
            replacing(read_module, "read_value_field", _the_nearest_knots_block),
        ),
        ("holding_points",),
        "^a table holding points read",
    ),
    # HP22's clause of the block as stored at every read: `the_nearest_knots_block` injects `points_ignored`
    # too, and no knot block shows without `points` read, so it dies where that one does; this one shows at a
    # read of a table without `points`.
    Mutant(
        "a_member_dropped_from_the_tables_block",
        "HP22",
        replacing(read_module, "read_value_field", _a_member_dropped_from_the_tables_block),
        ("at_a_knot", "between_knots"),
        "^the block at the (at_a_knot|between_knots) read",
    ),
    Mutant(
        "range_mismatch_without_its_axis",
        "HP23",
        replacing(read_module, "form_range", _range_mismatch_without_its_axis),
        ("range_inside", "range_across_an_end", "range_holding_an_edge", "range_outside"),
        "read's step 11",
    ),
    Mutant(
        "outside_range_beside_a_range_across_an_end",
        "HP23",
        replacing(read_module, "form_range", _outside_range_beside_a_range_across_an_end),
        ("range_across_an_end", "range_outside"),
        "read's step 11",
    ),
    # The monotonicity property's two mutants (the S3 design's section 6.7).
    Mutant(
        "monotone_the_tolerance_widens_the_range",
        "monotonicity",
        both(
            replacing(read_module, "form_range", _the_tolerance_widens_the_range),
            replacing(read_module, "axis_status", _the_tolerance_widens_the_axis_entry),
        ),
        ("one_double_outside", "far_outside"),
        "^a tolerance on the axis turned",
    ),
    Mutant(
        "monotone_source_range_widening",
        "monotonicity, one double outside",
        replacing(evaluate, "readable_range", _source_range_widening),
        ("one_double_outside",),
        "^(a source_range turned|the read raised)",
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_table_read_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the ways it names, and at the assertion it names."""
    mutant.inject(monkeypatch)
    examples, check, drew = KILLERS[mutant.killer]
    said: list[str] = []

    def checked(example: Any) -> None:
        try:
            check(example)
        except AssertionError as error:
            said.append(str(error))
            raise

    tried, example = kill(examples(size), checked)
    record_property("examples_to_kill", tried)
    assert drew(example) in mutant.dies_at, drew(example)
    assert re.search(mutant.says, said[0]), said[0]
