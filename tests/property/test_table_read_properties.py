# SPDX-License-Identifier: Apache-2.0
"""A table's steps 10 to 13 (`record_format.md` section 6, table items 3 and 4; `read_side_contract.md`
section 1, section 3 steps 10 to 13, section 5's first row and "The form's range", section 6): the S3 design's
HP20 to HP23, over reads that `table_read_strategies.py` draws, each with the way it draws first. The mutants
they kill are in `test_table_read_mutants.py`.

- HP20, edges: at an edge, wherever it lies, `at_edge` with the axis and no value; outside the readable range
  `outside_range` beside it; one double below an edge reads the interval below, one above the interval above;
  outside the range beyond an edge, the edge outside it or on its end, `outside_range` alone and no value; and
  step 11 reports that no extrapolation could cover a read at an edge or beyond one.
- HP21, the range: outside the readable range, `outside_range` with the axis, the axis entry `not_met` and no
  value, an extrapolation able to cover it; inside it, at its ends included, the axis entry `met` and the
  table's value; a `source_range` no narrower than `x`'s range, and a tolerance on the axis, change nothing;
  one narrower than `x`'s narrows it.
- HP22, statistics: the table's block, as stored, at every read; a table holding `points` refused
  (`points_unsupported`), with no value and no block.
- HP23, the request checks step 11 makes: no operating value for the axis gives `request_incomplete` with the
  axis, the result holding `conditions`; an operating range of it gives `want_mismatch` with the axis and no
  other reason of step 11.

Each oracle is written from the text: the value the reference evaluator gives in its `exact` mode
(`tests/reference/table_evaluator.py`), on the whole table or on the one interval the text names, rounded
once. The read's report for step 7 (`read.form_range`) is called with the request the read checks."""

import json
import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core import read as read_module
from materica.core.read import FormRange, ReadResult, read
from materica.core.record import RecordStore
from tests.property import table_read_strategies as strategies
from tests.property.strategies import SIZE, Size
from tests.property.support import feature, same
from tests.property.table_read_strategies import (
    EDGE_WAYS,
    RANGE_WAYS,
    REQUEST_WAYS,
    STATISTICS_WAYS,
    MetWorld,
    TableRead,
    table_field,
)
from tests.property.test_result_properties import expected_members
from tests.property.value_fields import Json as JsonObject
from tests.property.value_fields import mapping
from tests.reference import table_evaluator


def read_of(drawn: TableRead) -> ReadResult:
    found = strategies.read_drawn(drawn)
    assert isinstance(found, ReadResult), f"the {drawn.way} read: {found}"
    return found


def on_the_axis(drawn: TableRead, result: ReadResult) -> set[tuple[str, str | None]]:
    """The reasons that carry the axis: step 11's, and none of step 10's, which gives the axis none."""
    return {(reason.code, reason.condition) for reason in result.reasons if reason.condition == drawn.axis}


def axis_entry(drawn: TableRead, result: ReadResult) -> str:
    assert result.conditions is not None, f"the {drawn.way} read holds no conditions"
    (entry,) = [entry for entry in result.conditions if entry.name == drawn.axis]
    return entry.status


def reported(drawn: TableRead) -> FormRange:
    table = mapping(table_field(drawn)["table"])
    return read_module.form_range(table, strategies.checked_request(drawn))


def exact(table: table_evaluator.Table, at: float) -> float:
    """The value at `at` the reference evaluator gives in its `exact` mode, rounded once to a double."""
    found = table_evaluator.evaluate(table, at, "exact")
    assert found.in_range, found
    assert found.value is not None, found
    return found.value if isinstance(found.value, float) else float(Fraction(found.value))


def whole_table(drawn: TableRead) -> table_evaluator.Table:
    table = drawn.table
    return table_evaluator.Table(table.x, table.y, table.scheme, table.edges, table.source_range)


def interval_value(drawn: TableRead, side: str, edge: float, at: float) -> float:
    """The value at `at` of the one interval beside `edge` on `side`: "a read just below an edge uses the knot
    below it" (table item 3), and above it the interval above (`read_side_contract.md` section 7 item 4)."""
    x, y = drawn.table.x, drawn.table.y
    first = x.index(edge)
    below, above = (first - 1, first) if side == "below" else (first + 1, first + 2)
    return exact(table_evaluator.Table((x[below], x[above]), (y[below], y[above]), drawn.table.scheme), at)


def refused(drawn: TableRead, result: ReadResult, reasons: set[tuple[str, str | None]]) -> None:
    """Step 11 refuses the read with exactly `reasons` on the axis: `not_met`, no value, no table, the axis
    entry `not_met`."""
    assert on_the_axis(drawn, result) == reasons, (
        f"the {drawn.way} read's step 11: {on_the_axis(drawn, result)}"
    )
    assert result.status == "not_met", f"the {drawn.way} read: {result.status}"
    assert (result.value, result.table) == (None, None), f"the {drawn.way} read's value {result.value}"
    assert axis_entry(drawn, result) == "not_met", f"the {drawn.way} read's axis entry"


def read_on(drawn: TableRead, result: ReadResult, value: float) -> None:
    """Step 11 lets the read on: no reason on the axis, the axis entry `met`, the value `value` bit for bit,
    and the table it is read from, as stored."""
    assert on_the_axis(drawn, result) == set(), (
        f"the {drawn.way} read's step 11: {on_the_axis(drawn, result)}"
    )
    assert axis_entry(drawn, result) == "met", f"the {drawn.way} read's axis entry"
    assert same(value, result.value), f"the {drawn.way} value {result.value}, not {value}"
    assert result.table == table_field(drawn)["table"], f"the {drawn.way} read's table {result.table}"


# HP20.

AT_EDGE = ("at_edge", None)


def check_edge(drawn: TableRead) -> None:
    result = read_of(drawn)
    axis = drawn.axis
    if drawn.way in ("at_an_edge_inside", "at_an_edge_outside", "across_an_edge"):
        refusals: dict[str, set[tuple[str, str | None]]] = {
            "at_an_edge_inside": {("at_edge", axis)},
            "at_an_edge_outside": {("at_edge", axis), ("outside_range", axis)},
            "across_an_edge": {("outside_range", axis)},
        }
        refused(drawn, result, refusals[drawn.way])
        report = reported(drawn)
        assert not report.coverable, f"the {drawn.way} read reported coverable by an extrapolation"
        assert report.outside_alone == (drawn.way == "across_an_edge"), (
            f"the {drawn.way} read's report {report}"
        )
        return
    assert drawn.at is not None
    edge = math.nextafter(drawn.at, math.inf if drawn.way == "just_below_an_edge" else -math.inf)
    side = "below" if drawn.way == "just_below_an_edge" else "above"
    read_on(drawn, result, interval_value(drawn, side, edge, drawn.at))


@pytest.mark.drawn(*EDGE_WAYS)
@given(strategies.edge_reads())
def test_a_read_at_an_edge_is_refused_and_beside_one_reads_its_own_side(drawn: TableRead) -> None:
    feature(drawn.way)
    check_edge(drawn)


# HP21.

OUTSIDE = ("one_double_outside", "far_outside", "outside_a_narrower_source_range")


def check_range(drawn: TableRead) -> None:
    result = read_of(drawn)
    if drawn.way in OUTSIDE:
        refused(drawn, result, {("outside_range", drawn.axis)})
        report = reported(drawn)
        assert report.outside_alone, f"the {drawn.way} read's report {report}"
        assert report.coverable, f"the {drawn.way} read's report {report}"
        return
    assert drawn.at is not None
    read_on(drawn, result, exact(whole_table(drawn), drawn.at))


@pytest.mark.drawn(*RANGE_WAYS)
@given(strategies.range_reads())
def test_the_readable_range_holds_its_ends_and_nothing_beyond(drawn: TableRead) -> None:
    feature(drawn.way)
    check_range(drawn)


def without_table(result: ReadResult) -> object:
    written = dict(result.to_json())
    written.pop("table", None)
    return written


def check_no_wider_and_tolerance(example: tuple[TableRead, TableRead, TableRead]) -> None:
    """The read of a table without `source_range`, with one no narrower than `x`'s range, and with a tolerance
    on the axis: the three alike but for the `table` returned."""
    plain, wider, tolerant = example
    expected = without_table(read_of(plain))
    assert without_table(read_of(wider)) == expected, (
        f"a source_range {wider.table.source_range} changed the read"
    )
    assert without_table(read_of(tolerant)) == expected, (
        f"a tolerance {tolerant.tolerance} on the axis changed the read"
    )


@st.composite
def no_wider_and_tolerance(draw: st.DrawFn, size: Size = SIZE) -> tuple[TableRead, TableRead, TableRead]:
    """A read of HP21 inside, at or outside the readable range, on a table whose readable range is `x`'s, read
    off any `source_range`, and the two reads that must give it again: with a `source_range` no narrower than
    `x`'s range, and with a tolerance on the axis of zero, of the distance to `x`'s farther end, or twice
    that."""
    drawn = draw(strategies.range_reads(size, ways=RANGE_WAYS[:4], x_range=True))
    plain = strategies.with_table(drawn, drawn.table._replace(source_range=None))
    x = drawn.table.x
    wider = strategies.with_table(drawn, drawn.table._replace(source_range=strategies.no_narrower(draw, x)))
    assert drawn.at is not None
    distance = max(abs(x[0] - drawn.at), abs(drawn.at - x[-1]))
    tolerance = draw(st.sampled_from((0.0, distance, 2 * distance))) if math.isfinite(2 * distance) else 0.0
    return plain, wider, plain._replace(tolerance=tolerance)


@pytest.mark.drawn(*RANGE_WAYS[:4])
@given(no_wider_and_tolerance())
def test_a_source_range_no_narrower_than_x_and_a_tolerance_on_the_axis_change_nothing(
    example: tuple[TableRead, TableRead, TableRead],
) -> None:
    feature(example[0].way)
    check_no_wider_and_tolerance(example)


# HP22.


def check_statistics(drawn: TableRead) -> None:
    result = read_of(drawn)
    if drawn.way == "holding_points":
        assert ("points_unsupported", None) in {
            (reason.code, reason.condition) for reason in result.reasons
        }, f"a table holding points read: {result.reasons}"
        assert (result.status, result.value, result.statistics) == ("not_met", None, None), (
            f"a table holding points read: {result.status}, {result.value}, {result.statistics}"
        )
        return
    # "A block on a table or a power law applies to every value the form gives" (`uncertainty.md` section 1
    # item 2): HP6's oracle of a block as stored, which reads no section.
    block = expected_members(table_field(drawn), {"specimen": {}})["statistics"]
    written: JsonObject = json.loads(json.dumps(result.to_json()))
    assert same(block, written.get("statistics")), f"the block at the {drawn.way} read: {result.statistics}"


@pytest.mark.drawn(*STATISTICS_WAYS)
@given(strategies.statistics_reads())
def test_a_tables_block_stands_at_every_read_and_points_are_refused(drawn: TableRead) -> None:
    feature(drawn.way)
    check_statistics(drawn)


# HP23.


def check_request(drawn: TableRead) -> None:
    result = read_of(drawn)
    if drawn.way == "no_operating_value":
        refused(drawn, result, {("request_incomplete", drawn.axis)})
        assert reported(drawn).request_fault, "no operating value reported as no fault of the request"
        return
    refused(drawn, result, {("want_mismatch", drawn.axis)})
    assert reported(drawn).over_a_range, "an operating range reported as none"


@pytest.mark.drawn(*REQUEST_WAYS)
@given(strategies.request_reads())
def test_step_11s_request_checks_give_their_reason_with_the_axis(drawn: TableRead) -> None:
    feature(drawn.way)
    check_request(drawn)


# The S3 design's monotonicity property over a table (the maintainer's information monotonicity, 2026-10-14).


def status_of(record: JsonObject, request: JsonObject) -> str:
    """The status of the read of `request`, pinned at `record`, which a store holds alone."""
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    pinned: JsonObject = {**request, "target": {**mapping(request["target"]), "record": pin}}
    try:
        return read(pinned, store).status
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error


def check_monotone(world: MetWorld) -> None:
    """Adding a `source_range`, or a tolerance on the axis, never turns `unknown` or `not_met` into `met`; and
    a read inside the range of a table without `source_range`, where the request meets every other condition,
    is `met`, or `unknown` where the field is stated without origin, so that the relation is not vacuous on
    either half. Over a field without alternatives: among alternatives a narrower `source_range` can set a
    table alternative aside and turn `no_pick` into another one's `met`."""
    plain = status_of(world.plain, world.request)
    if world.way in ("inside", "at_an_end"):
        expected = "unknown" if world.unoriginated else "met"
        assert plain == expected, f"a read {world.way} its range, every condition met: {plain}"
    narrowed = status_of(world.narrowed, world.request)
    tolerant = status_of(world.plain, world.tolerant)
    if plain != "met":
        assert narrowed != "met", f"a source_range turned a read {plain} at {world.way} into met"
        assert tolerant != "met", f"a tolerance on the axis turned a read {plain} at {world.way} into met"


@pytest.mark.drawn(*RANGE_WAYS[:4])
@given(strategies.met_worlds())
def test_a_source_range_or_a_tolerance_on_the_axis_never_turns_a_read_met(world: MetWorld) -> None:
    feature(world.way)
    check_monotone(world)
