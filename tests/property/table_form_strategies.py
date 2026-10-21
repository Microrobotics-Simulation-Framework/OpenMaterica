# SPDX-License-Identifier: Apache-2.0
"""Reads of a table field through steps 8 and 9 (`record_format.md` section 6, table items 1, 2, 4 and 5;
`read_side_contract.md` section 3, steps 8 and 9), for HP13 to HP16 (`test_table_form_properties.py`).

A base read holds a table that steps 8 and 9 pass: its knots, values, scheme, edges and `source_range` as
`tables.py` draws a table step 8 accepts, on a field whose row allows a table, over an axis drawn among the
numeric conditions, its `axis_unit` that condition's registered unit and its axis condition `not_applicable`.
Beside it, in the record, stands a full composition (`full_fields.py`), in the same section as a density. A
read of a table that steps 8 and 9 pass goes on to steps 10 to 13, read with no operating condition: its
outcome is then `PAST_STEP_9`, whatever those steps give, as it was while they raised `NotImplementedError`.

HP13's catalogue changes a base read by one fault the text names, written here from the text with the codes
its rule gives, or by a near miss the text allows, which gives none; HP14 adds a member the reader does not
know, more than one slip from every member named at a table's place or one slip from one; HP15 changes the
`axis_unit`; HP16 puts the row's label on a table over an axis drawn first as the one its Label cell names or
another. Each is drawn first, so that the feature audit holds each to its draw floor.
"""

import copy
import json
import math
from collections.abc import Callable
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from tests.property import tables
from tests.property.condition_oracle import REASONS
from tests.property.condition_strategies import OTHER_UNITS, other_unit
from tests.property.full_fields import CONDITIONS, full_forms, record_of
from tests.property.strategies import SIZE, Size
from tests.property.value_fields import (
    FIELDS,
    NUMERIC_CONDITIONS,
    TOKEN_CONDITIONS,
    Json,
    listing,
    mapping,
    registered_unit,
    row_of,
)

TABLE_FIELDS = tuple(name for name in FIELDS if "table" in listing(row_of(name)["forms"]))
# The neighbour every record holds, read to show that a fault in the table changes nothing of its read.
NEIGHBOUR, NEIGHBOUR_FIELD = full_forms()["composition"]
# The members named at a table's place: `record_format.md` section 6's example (lines 376 to 378) and table
# item 5's `points`, which "counts as a member named at a table's place".
NAMED = ("axis", "axis_unit", "x", "y", "scheme", "edges", "source_range", "points")
REQUIRED = ("axis", "axis_unit", "x", "y", "scheme", "edges")
PAST_STEP_9 = "past step 9"
STEPS_8_AND_9 = {8, 9}


class Outcome(NamedTuple):
    status: str  # PAST_STEP_9 where steps 8 and 9 pass the table, or what the read raised
    reasons: frozenset[tuple[str, str | None]] = frozenset()


class Read(NamedTuple):
    record: Json
    field: str  # the table's registered name


def outcome(record: Json, field: str, want: str = "value") -> Outcome:
    """The read of `field` in `record`, pinned by its hash recomputed: `PAST_STEP_9` where steps 8 and 9 pass
    it, so that it gives no reason of a code either step gives (`read_side_contract.md` section 4, its `Step`
    column), as a step that gives `not_met` ends the read. An exception is an outcome no rule gives: "A read
    never stops with an error for anything a record or request contains" (`read_side_contract.md` section 2
    item 1)."""
    record = {**record, "content_hash": content_hash(record)}
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    try:
        result = read({"target": {"record": pin, "field": field}, "requirement": {"want": want}}, store)
    except Exception as error:
        return Outcome(f"raised {error!r}")
    if not any(STEPS_8_AND_9 & set(REASONS["reasons"][reason.code]["steps"]) for reason in result.reasons):
        return Outcome(PAST_STEP_9)
    return Outcome(result.status, frozenset((reason.code, reason.condition) for reason in result.reasons))


def neighbour(record: Json) -> Outcome:
    return outcome(record, NEIGHBOUR, "components")


def table_of(drawn: Read) -> Json:
    return mapping(field_of(drawn)["table"])


def field_of(drawn: Read) -> Json:
    section, _, name = drawn.field.partition(".")
    return mapping(
        mapping(mapping(mapping(mapping(drawn.record["body"])["sections"])[section])["fields"])[name]
    )


def conditions_of(drawn: Read) -> Json:
    return mapping(field_of(drawn)["conditions"])


@st.composite
def base_reads(draw: st.DrawFn, size: Size = SIZE, fields: tuple[str, ...] = TABLE_FIELDS) -> Read:
    """A record holding a table steps 8 and 9 pass, and its neighbour."""
    registered = draw(st.sampled_from(fields))
    drawn, _ = draw(tables.tables(size))
    axis = draw(st.sampled_from(NUMERIC_CONDITIONS))
    table: Json = {
        "axis": axis,
        "axis_unit": registered_unit(axis),
        "x": list(drawn.x),
        "y": list(drawn.y),
        "scheme": drawn.scheme,
        "edges": list(drawn.edges),
    }
    if drawn.source_range is not None:
        table["source_range"] = list(drawn.source_range)
    field = copy.deepcopy(full_forms()["table"][1])
    field.pop("label")
    field["unit"] = row_of(registered)["unit"]
    field["conditions"] = {**copy.deepcopy(CONDITIONS), axis: {"status": "not_applicable"}}
    field["table"] = table
    record = record_of(field, registered)
    section, _, name = NEIGHBOUR.partition(".")
    sections = mapping(mapping(record["body"])["sections"])
    held = mapping(sections.setdefault(section, {"fields": {}}))
    mapping(held["fields"])[name] = copy.deepcopy(NEIGHBOUR_FIELD)
    return Read(record, registered)


# HP13: one fault of a catalogue written from the text, each with the reasons its rule gives, or a near miss
# the text allows, with none. A change returns the reasons; `None` for a near miss, whose read passes steps 8
# and 9 as its base's does.
Reasons = frozenset[tuple[str, str | None]]
FORM_INVALID: Reasons = frozenset({("form_invalid", None)})
UNKNOWN_TOKEN: Reasons = frozenset({("unknown_token", None)})
POINTS_UNSUPPORTED: Reasons = frozenset({("points_unsupported", None)})
Change = Callable[[st.DrawFn, Read], Reasons | None]
# Values of other JSON types than a member's, for the faults that write them.
NOT_LISTS: list[JsonValue] = [1.0, {"status": "unstated"}, "[]", None]
NOT_STRINGS: list[JsonValue] = [1.0, None, ["linear"], {"status": "unstated"}]
NOT_UNITS: list[JsonValue] = [1.0, None, ["K"], True, {"status": "unstated", "unit": "K"}]
POINTS: list[JsonValue] = [[], [{}], {}, "x", 1.0, {"status": "withheld"}]


def interior_knot(draw: st.DrawFn, drawn: Read) -> float:
    """A value of `x` strictly between its ends, held once and no edge: one there is, or a knot added where
    two neighbouring knots have room, else past an end, a value for it added to `y`, so that the table stays
    one step 8 accepts."""
    table = table_of(drawn)
    x, y, edges = listing(table["x"]), listing(table["y"]), listing(table["edges"])
    once = [value for value in x[1:-1] if x.count(value) == 1 and value not in edges]
    if once:
        return float(str(draw(st.sampled_from(once))))
    knots = [float(str(value)) for value in x]
    roomy = [at for at in range(len(knots) - 1) if math.nextafter(knots[at], math.inf) < knots[at + 1]]
    if roomy:
        at = draw(st.sampled_from(roomy))
        added = math.nextafter(knots[at], math.inf)
        x.insert(at + 1, added)
        y.insert(at + 1, y[at])
        return added
    # Every two neighbouring knots adjacent doubles: a knot past the last, or before the first, which leaves
    # that end inside (a log-log table's first knot stays above zero, the last below the largest double).
    if math.isfinite(math.nextafter(knots[-1], math.inf)):
        x.append(math.nextafter(knots[-1], math.inf))
        y.append(y[-1])
        return knots[-1]
    x.insert(0, math.nextafter(knots[0], -math.inf))
    y.insert(0, y[0])
    return knots[0]


def an_edge(draw: st.DrawFn, drawn: Read) -> float:
    """An edge of the table: one it has, or an interior knot made one (held twice, a value above it added)."""
    table = table_of(drawn)
    edges = listing(table["edges"])
    if edges:
        return float(str(draw(st.sampled_from(edges))))
    knot = interior_knot(draw, drawn)
    x, y = listing(table["x"]), listing(table["y"])
    at = x.index(knot)
    x.insert(at + 1, knot)
    y.insert(at + 1, y[at])
    edges.append(knot)
    return knot


def _y_longer(draw: st.DrawFn, drawn: Read) -> Reasons:
    y = listing(table_of(drawn)["y"])
    y.insert(draw(st.integers(0, len(y))), y[0])
    return FORM_INVALID


def _y_shorter(draw: st.DrawFn, drawn: Read) -> Reasons:
    y = listing(table_of(drawn)["y"])
    del y[draw(st.integers(0, len(y) - 1))]
    return FORM_INVALID


def _x_one_value(draw: st.DrawFn, drawn: Read) -> Reasons:
    table = table_of(drawn)
    table.update(x=listing(table["x"])[:1], y=listing(table["y"])[:1], edges=[])
    table.pop("source_range", None)
    return FORM_INVALID


def _x_without_two_distinct_values(draw: st.DrawFn, drawn: Read) -> Reasons:
    """`x` holds at least two distinct values: here one, held twice or more, and no edge."""
    table = table_of(drawn)
    count = draw(st.integers(2, 4))
    table.update(x=[listing(table["x"])[0]] * count, y=listing(table["y"])[:1] * count, edges=[])
    table.pop("source_range", None)
    return FORM_INVALID


def _x_decreasing(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Two distinct neighbouring knots swapped, or `x` reversed."""
    x = listing(table_of(drawn)["x"])
    steps = [index for index in range(len(x) - 1) if x[index] != x[index + 1]]
    if draw(st.booleans()):
        x.reverse()
    else:
        at = draw(st.sampled_from(steps))
        x[at], x[at + 1] = x[at + 1], x[at]
    return FORM_INVALID


def _repeated_x_no_edge(draw: st.DrawFn, drawn: Read) -> Reasons:
    knot = interior_knot(draw, drawn)
    table = table_of(drawn)
    x, y = listing(table["x"]), listing(table["y"])
    at = x.index(knot)
    x.insert(at, knot)
    y.insert(at, y[at])
    return FORM_INVALID


def _not_numbers(draw: st.DrawFn, drawn: Read) -> Reasons:
    """`x`, `y` or `edges` holding other than a list of numbers: an item a string, `null`, a status object, or
    the member a number or a status object."""
    table = table_of(drawn)
    member = draw(st.sampled_from(["x", "y", "edges"]))
    wrong: list[JsonValue] = ["1.0", None, {"status": "unstated"}, True]
    if draw(st.booleans()) or not listing(table[member]):
        table[member] = draw(st.sampled_from(NOT_LISTS))
    else:
        values = listing(table[member])
        values[draw(st.integers(0, len(values) - 1))] = draw(st.sampled_from(wrong))
    return FORM_INVALID


def _member_missing(draw: st.DrawFn, drawn: Read) -> Reasons:
    del table_of(drawn)[draw(st.sampled_from(REQUIRED))]
    return FORM_INVALID


def _edge_at_an_end(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Each edge lies strictly between `x[0]` and `x[-1]`: here at one, held twice there."""
    table = table_of(drawn)
    x, y = listing(table["x"]), listing(table["y"])
    if draw(st.booleans()):
        x.insert(0, x[0])
        y.insert(0, y[0])
        listing(table["edges"]).append(x[0])
    else:
        x.append(x[-1])
        y.append(y[-1])
        listing(table["edges"]).append(x[-1])
    return FORM_INVALID


def _edge_not_in_x(draw: st.DrawFn, drawn: Read) -> Reasons:
    """An edge strictly between two knots, which `x` does not hold: where no two knots have room, a value
    beyond an end, which `x` does not hold either."""
    table = table_of(drawn)
    x = [float(str(value)) for value in listing(table["x"])]
    roomy = [index for index in range(len(x) - 1) if math.nextafter(x[index], math.inf) < x[index + 1]]
    if roomy:
        at = draw(st.sampled_from(roomy))
        edge = math.nextafter(x[at], math.inf)
    else:
        edge = math.nextafter(x[-1], math.inf)
        edge = edge if math.isfinite(edge) else math.nextafter(x[0], -math.inf)
    listing(table["edges"]).append(edge)
    return FORM_INVALID


def _edge_not_repeated(draw: st.DrawFn, drawn: Read) -> Reasons:
    listing(table_of(drawn)["edges"]).append(interior_knot(draw, drawn))
    return FORM_INVALID


def _edge_repeated_thrice(draw: st.DrawFn, drawn: Read) -> Reasons:
    edge = an_edge(draw, drawn)
    table = table_of(drawn)
    x, y = listing(table["x"]), listing(table["y"])
    at = x.index(edge)
    x.insert(at, edge)
    y.insert(at, y[at])
    return FORM_INVALID


def _edge_listed_twice(draw: st.DrawFn, drawn: Read) -> Reasons:
    """No number twice in `edges`, compared by value: the same edge again, or `-0` beside `0`."""
    edge = an_edge(draw, drawn)
    listing(table_of(drawn)["edges"]).append(-edge if edge == 0 else edge)
    return FORM_INVALID


def zero_edge(draw: st.DrawFn, drawn: Read) -> tuple[Json, list[float]]:
    """The table replaced by one over `[-1, 0, 0, 1]` scaled, an edge at zero, its two entries `-0` and `0` in
    an order drawn: equal by value, so it holds its edge twice (table item 1, "so `-0` equals `0`")."""
    table = table_of(drawn)
    scale = draw(st.sampled_from([1.0, 1e-300, 1e300, 5e-324]))
    zeros = draw(st.permutations([0.0, -0.0]))
    table.update(
        x=[-scale, *zeros, scale],
        y=[draw(tables.numbers("ordinary", positive=False)) for _ in range(4)],
        scheme="linear",
    )
    table.pop("source_range", None)
    return table, zeros


def _zero_edge_both_signs(draw: st.DrawFn, drawn: Read) -> None:
    table, zeros = zero_edge(draw, drawn)
    table["edges"] = [draw(st.sampled_from(zeros))]
    return None


def _edges_zero_and_minus_zero(draw: st.DrawFn, drawn: Read) -> Reasons:
    table, _ = zero_edge(draw, drawn)
    table["edges"] = list(draw(st.permutations([0.0, -0.0])))
    return FORM_INVALID


def _log_log_not_positive(draw: st.DrawFn, drawn: Read) -> Reasons:
    """A log-log table of positive numbers but one, zero, `-0` or below, in `x`'s first or any `y`."""
    table = table_of(drawn)
    count = draw(st.integers(2, 4))
    x = [float(index + 1) for index in range(count)]
    y = [draw(tables.numbers("ordinary", positive=True)) for _ in range(count)]
    value = draw(st.sampled_from([0.0, -0.0, -1.0, -5e-324]))
    if draw(st.booleans()):
        x[0] = value
    else:
        y[draw(st.integers(0, count - 1))] = value
    held_x: list[JsonValue] = [*x]
    held_y: list[JsonValue] = [*y]
    table.update(x=held_x, y=held_y, scheme="loglog", edges=[])
    table.pop("source_range", None)
    return FORM_INVALID


def _scheme_unknown(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 2: a `scheme` that is a string other than the two is a token the reader does not know."""
    table_of(drawn)["scheme"] = draw(st.sampled_from(["cubic", "log_log", "Linear", "linear ", "", "spline"]))
    return UNKNOWN_TOKEN


def _axis_unknown(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 2: an `axis` naming no numeric condition the reader knows is a token it does not know."""
    table_of(drawn)["axis"] = draw(
        st.sampled_from(["frequency", "Temperature", "temperature ", "x", "energy"])
    )
    return UNKNOWN_TOKEN


def _axis_token_condition(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 2: "a token condition's name included"."""
    table_of(drawn)["axis"] = draw(st.sampled_from(TOKEN_CONDITIONS))
    return UNKNOWN_TOKEN


def _token_not_a_string(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 2: "An `axis` that is not a string breaks item 1"; a `scheme` that is not one breaks its shape."""
    member = draw(st.sampled_from(["axis", "scheme"]))
    table_of(drawn)[member] = draw(st.sampled_from(NOT_STRINGS))
    return FORM_INVALID


def _axis_condition_held_otherwise(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 1: the field's `conditions` hold the axis as `{"status": "not_applicable"}`: here as a value, as a
    range, absent, or as another status. The two ways that hold a value, which a reader taking it as the
    axis's own passes, are half the four, so that the feature audit holds them to a floor of their own (one
    way in three, they were one draw in 21, too seldom for one)."""
    way = draw(st.sampled_from(HELD_OTHERWISE))
    if way in HELD_AS_A_VALUE:
        return axis_condition_held_as_a_value(draw, drawn, way)
    axis = str(table_of(drawn)["axis"])
    conditions = conditions_of(drawn)
    if way == "absent":
        del conditions[axis]
    else:
        conditions[axis] = {"status": draw(st.sampled_from(["unstated", "not_checked", "none", "withheld"]))}
    return FORM_INVALID


HELD_AS_A_VALUE = ("value", "range")
HELD_OTHERWISE = (*HELD_AS_A_VALUE, "absent", "status")


def axis_condition_held_as_a_value(draw: st.DrawFn, drawn: Read, way: str | None = None) -> Reasons:
    """The axis condition holding a value, stated as a number or as a range (`way`, drawn where None) in its
    registered unit, the shapes a numeric condition takes off the axis."""
    axis = str(table_of(drawn)["axis"])
    unit = registered_unit(axis)
    way = way or draw(st.sampled_from(HELD_AS_A_VALUE))
    held: Json = (
        {"value": 1.0, "unit": unit, "basis": "stated"}
        if way == "value"
        else {"range": [1.0, 2.0], "unit": unit, "basis": "stated"}
    )
    conditions_of(drawn)[axis] = held
    return FORM_INVALID


def held_as_a_value(drawn: Read) -> bool:
    """Whether the read's axis condition holds a value or a range: the region where a reader that takes it
    as the axis's own shows (`axis_condition_held_as_a_value_accepted`)."""
    table, conditions = table_of(drawn), conditions_of(drawn)
    held = conditions.get(str(table.get("axis")))
    return isinstance(held, dict) and ("value" in held or "range" in held)


def _axis_condition_with_a_reason(draw: st.DrawFn, drawn: Read) -> None:
    """A near miss: the axis condition `not_applicable` with its `reason`, and perhaps a member beside it
    that a condition's shape does not name, which a status object ignores (`provenance.md` section 1 item
    5)."""
    held: Json = {"status": "not_applicable", "reason": "the table's axis"}
    if draw(st.booleans()):
        held["note"] = 1.0
    conditions_of(drawn)[str(table_of(drawn)["axis"])] = held
    return None


def _axis_unit_not_a_unit(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 1: "`axis_unit` is a string or a status object": here neither, or a status object holding a
    member beside `status` and `reason` where a string goes."""
    table_of(drawn)["axis_unit"] = draw(st.sampled_from(NOT_UNITS))
    return FORM_INVALID


def _source_range_reversed(draw: st.DrawFn, drawn: Read) -> Reasons:
    table = table_of(drawn)
    x = listing(table["x"])
    table["source_range"] = [x[-1], x[0]]
    return FORM_INVALID


def _source_range_disjoint(draw: st.DrawFn, drawn: Read) -> Reasons:
    """A `source_range` past `x`'s range: two doubles above its end, or below its start, or one where only one
    lies there. An `x` from the least double to the largest has its last knot lowered by one double first,
    which leaves the table one step 8 accepts, the knot before it lying lower."""
    table = table_of(drawn)
    x = listing(table["x"])
    knots = [float(str(value)) for value in x]
    if not any(
        math.isfinite(math.nextafter(end, away))
        for end, away in ((knots[-1], math.inf), (knots[0], -math.inf))
    ):
        lowered = math.nextafter(knots[-1], -math.inf)
        assert knots[-2] < lowered, "x holds the two largest doubles and the least"
        x[-1] = knots[-1] = lowered
    for end, away in ((knots[-1], math.inf), (knots[0], -math.inf)):
        near = math.nextafter(end, away)
        if math.isfinite(near):
            far = math.nextafter(near, away)
            ends = sorted((near, far if math.isfinite(far) else near))
            table["source_range"] = [ends[0], ends[1]]
            break
    return FORM_INVALID


def _source_range_only_at_an_edge(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 4: sharing with `[x[0], x[-1]]` a value that is no edge; here only the edge, `[e, e]`."""
    edge = an_edge(draw, drawn)
    table_of(drawn)["source_range"] = [edge, edge]
    return FORM_INVALID


def _source_range_one_point_no_edge(draw: st.DrawFn, drawn: Read) -> None:
    """A near miss: a `source_range` of one point that is no edge, an end of `x` or an interior knot."""
    table = table_of(drawn)
    x, edges = listing(table["x"]), listing(table["edges"])
    point = draw(st.sampled_from([value for value in (x[0], x[-1]) if value not in edges]))
    table["source_range"] = [point, point]
    return None


def _source_range_not_two_numbers(draw: st.DrawFn, drawn: Read) -> Reasons:
    table = table_of(drawn)
    low, high = listing(table["x"])[0], listing(table["x"])[-1]
    shapes: list[JsonValue] = [[low], [low, high, high], [low, str(high)], "x", {"status": "unstated"}, None]
    table["source_range"] = draw(st.sampled_from(shapes))
    return FORM_INVALID


def _x_empty_beside_edges_or_a_source_range(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 1: `x` holds at least two distinct values: here none, and `y` none, beside an edge, a
    `source_range` or both, whose rules read `x`'s ends (the S3a review's H1: the read raised). An edge or a
    range the base lacks is taken from its `x` before it is emptied."""
    table = table_of(drawn)
    x = listing(table["x"])
    beside = draw(st.sampled_from(["edges", "source_range", "both"]))
    if beside != "source_range" and not listing(table["edges"]):
        table["edges"] = [x[len(x) // 2]]
    if beside == "source_range":
        table["edges"] = []
    if beside != "edges" and "source_range" not in table:
        table["source_range"] = [x[0], x[-1]]
    if beside == "edges":
        table.pop("source_range", None)
    table.update(x=[], y=[])
    return FORM_INVALID


def _points(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 5: a table holding `points`, whatever it holds, `[]` included."""
    table_of(drawn)["points"] = draw(st.sampled_from(POINTS))
    return POINTS_UNSUPPORTED


def _points_null(draw: st.DrawFn, drawn: Read) -> Reasons:
    """Item 5: "`null` there also gives `form_invalid`"."""
    table_of(drawn)["points"] = None
    return POINTS_UNSUPPORTED | FORM_INVALID


# The catalogue in four parts, each a property drawing its fault first among at most eight.
CATALOGUE: dict[str, dict[str, Change]] = {
    "knots": {
        "y_longer": _y_longer,
        "y_shorter": _y_shorter,
        "x_one_value": _x_one_value,
        "x_without_two_distinct_values": _x_without_two_distinct_values,
        "x_decreasing": _x_decreasing,
        "repeated_x_no_edge": _repeated_x_no_edge,
        "not_numbers": _not_numbers,
        "member_missing": _member_missing,
    },
    "edges": {
        "edge_at_an_end": _edge_at_an_end,
        "edge_not_in_x": _edge_not_in_x,
        "edge_not_repeated": _edge_not_repeated,
        "edge_repeated_thrice": _edge_repeated_thrice,
        "edge_listed_twice": _edge_listed_twice,
        "edges_zero_and_minus_zero": _edges_zero_and_minus_zero,
        "zero_edge_both_signs": _zero_edge_both_signs,
        "log_log_not_positive": _log_log_not_positive,
    },
    "tokens": {
        "scheme_unknown": _scheme_unknown,
        "axis_unknown": _axis_unknown,
        "axis_token_condition": _axis_token_condition,
        "token_not_a_string": _token_not_a_string,
        "axis_condition_held_otherwise": _axis_condition_held_otherwise,
        "axis_condition_with_a_reason": _axis_condition_with_a_reason,
        "axis_unit_not_a_unit": _axis_unit_not_a_unit,
    },
    "source_range_and_points": {
        "source_range_reversed": _source_range_reversed,
        "source_range_disjoint": _source_range_disjoint,
        "source_range_only_at_an_edge": _source_range_only_at_an_edge,
        "source_range_one_point_no_edge": _source_range_one_point_no_edge,
        "source_range_not_two_numbers": _source_range_not_two_numbers,
        "points": _points,
        "points_null": _points_null,
        "x_empty_beside_edges_or_a_source_range": _x_empty_beside_edges_or_a_source_range,
    },
}


class Faulty(NamedTuple):
    fault: str
    base: Read
    read: Read
    expected: Outcome  # what the faulty read gives: its reasons, or PAST_STEP_9 for a near miss


# The regions a planned search of HP13 draws alone, each a share of one fault's draws that the feature audit
# holds to the floor of its chance: by part, each region's name and whether a faulty read shows it.
REGIONS: dict[str, dict[str, Callable[[Faulty], bool]]] = {
    "tokens": {
        "axis_condition_held_as_a_value": lambda faulty: (
            faulty.fault == "axis_condition_held_otherwise" and held_as_a_value(faulty.read)
        ),
    },
}


@st.composite
def faulty_reads(
    draw: st.DrawFn,
    part: str,
    size: Size = SIZE,
    only: tuple[str, ...] = (),
    zeros_alike: bool = False,
) -> Faulty:
    """A base read and the same read with one fault of `part`'s, drawn first, alike, or among `only`; with
    `zeros_alike`, on a base whose zeros of `x` and `edges` are each held as `0` (`zeros_held_alike`)."""
    faults = CATALOGUE[part]
    name = draw(st.sampled_from([fault for fault in faults if not only or fault in only]))
    base = draw(base_reads(size))
    if zeros_alike:
        zeros_held_alike(base)
    changed = Read(copy.deepcopy(base.record), base.field)
    reasons = faults[name](draw, changed)
    expected = Outcome(PAST_STEP_9) if reasons is None else Outcome("not_met", reasons)
    return Faulty(name, base, changed, expected)


@st.composite
def axis_conditions_held_as_a_value(draw: st.DrawFn, size: Size = SIZE) -> Faulty:
    """HP13's tokens fault `axis_condition_held_otherwise`, in its way that holds the axis condition as a
    value: the region where `axis_condition_held_as_a_value_accepted` shows, for its planned search."""
    base = draw(base_reads(size))
    changed = Read(copy.deepcopy(base.record), base.field)
    reasons = axis_condition_held_as_a_value(draw, changed)
    return Faulty("axis_condition_held_otherwise", base, changed, Outcome("not_met", reasons))


def zeros_held_alike(drawn: Read) -> None:
    """Each `-0` of the table's `x` and `edges` held as `0`, which the table reads as it did (table item 1,
    "Numbers are compared by value, so `-0` equals `0`"): a base that a reader comparing zeros by their sign
    bit does not itself refuse, for the planned search of that mutant."""
    table = table_of(drawn)
    for member in ("x", "edges"):
        table[member] = [0.0 if value == 0 else value for value in listing(table[member])]


# HP14: a member the reader does not know, added to a table.
FAR = ("note", "comment", "remark", "unit", "provenance", "statistics", "label", "values", "abscissae")
SLIPS = ("added", "deleted", "substituted", "swapped", "plural")
KINDS = ("far", *SLIPS)
LETTERS = "abcdefghijklmnopqrstuvwxyz_"


def slip_of(draw: st.DrawFn, kind: str, name: str) -> str | None:
    """`name` changed by one slip of `kind` (`record_format.md` section 10): a character added, deleted or
    substituted, two adjacent characters swapped, or a word made plural or singular; None where the kind
    gives `name` nothing new."""
    if kind == "added":
        at = draw(st.integers(0, len(name)))
        return name[:at] + draw(st.sampled_from(LETTERS)) + name[at:]
    if kind == "deleted":
        if len(name) < 2:
            return None
        at = draw(st.integers(0, len(name) - 1))
        return name[:at] + name[at + 1 :]
    if kind == "substituted":
        at = draw(st.integers(0, len(name) - 1))
        return name[:at] + draw(st.sampled_from([c for c in LETTERS if c != name[at]])) + name[at + 1 :]
    if kind == "swapped":
        pairs = [at for at in range(len(name) - 1) if name[at] != name[at + 1]]
        if not pairs:
            return None
        at = draw(st.sampled_from(pairs))
        return name[:at] + name[at + 1] + name[at] + name[at + 2 :]
    words = name.split("_")
    at = draw(st.integers(0, len(words) - 1))
    word = words[at]
    words[at] = (
        word[:-1] if word.endswith("s") and len(word) > 1 else word + draw(st.sampled_from(["s", "es"]))
    )
    return "_".join(words)


class Added(NamedTuple):
    kind: str
    member: str
    read: Read
    expected: Outcome


@st.composite
def added_members(draw: st.DrawFn, size: Size = SIZE) -> Added:
    """A base read, a member added to its table: more than one slip from every member named there, a name
    drawn from a list or a longer one drawn, which no slip of a named name reaches; or one slip from one."""
    kind = draw(st.sampled_from(KINDS))
    drawn = draw(base_reads(size))
    if kind == "far":
        member = draw(st.one_of(st.sampled_from(FAR), st.text(LETTERS, min_size=15, max_size=20)))
        expected = Outcome(PAST_STEP_9)
    else:
        candidates = [
            slipped
            for name in NAMED
            if (slipped := slip_of(draw, kind, name)) is not None and slipped and slipped not in NAMED
        ]
        member = draw(st.sampled_from(candidates))
        expected = Outcome("not_met", FORM_INVALID)
    table_of(drawn)[member] = draw(st.sampled_from([1.0, "x", None, [], {}]))
    return Added(kind, member, drawn, expected)


# HP15: a table's `axis_unit` other than its axis condition's registered unit.


class OtherAxisUnit(NamedTuple):
    kind: str
    read: Read
    axis: str


@st.composite
def other_axis_units(draw: st.DrawFn, size: Size = SIZE) -> OtherAxisUnit:
    """A base read, its `axis_unit` another than the registered one, of a kind drawn first: equal under NFKC,
    under case folding, or but for a space, another registered unit, any text, or a status object. Every
    numeric condition's unit holds a cased letter, so each kind is drawn on any axis."""
    kind = draw(st.sampled_from(OTHER_UNITS))
    drawn = draw(base_reads(size))
    table = table_of(drawn)
    axis = str(table["axis"])
    table["axis_unit"] = draw(other_unit(kind, registered_unit(axis)))
    return OtherAxisUnit(kind, drawn, axis)


# HP16: the row's label on a table, over the axis its Label cell names or another.
LABELLED = tuple(name for name in TABLE_FIELDS if row_of(name).get("label_not_on_axis"))
ON_ITS_ROWS_AXIS = ("on_its_rows_axis", "on_another_axis")


class Labelled(NamedTuple):
    way: str
    read: Read
    expected: Outcome


@st.composite
def labelled_tables(draw: st.DrawFn, size: Size = SIZE) -> Labelled:
    """`record_format.md` section 4.1's Label column: the row's label goes "on a constant, or on a table whose
    axis is not" the condition the cell names; on one whose axis is that condition, it refuses the field
    (`form_invalid`)."""
    way = draw(st.sampled_from(ON_ITS_ROWS_AXIS))
    drawn = draw(base_reads(size, LABELLED))
    row = row_of(drawn.field)
    own = str(row["label_not_on_axis"])
    axis = (
        own
        if way == "on_its_rows_axis"
        else draw(st.sampled_from([name for name in NUMERIC_CONDITIONS if name != own]))
    )
    table, conditions = table_of(drawn), conditions_of(drawn)
    conditions[str(table["axis"])] = copy.deepcopy(CONDITIONS.get(str(table["axis"]), {"status": "unstated"}))
    conditions[axis] = {"status": "not_applicable"}
    table.update(axis=axis, axis_unit=registered_unit(axis))
    field_of(drawn)["label"] = row["label"]
    expected = Outcome("not_met", FORM_INVALID) if way == "on_its_rows_axis" else Outcome(PAST_STEP_9)
    return Labelled(way, drawn, expected)
