# SPDX-License-Identifier: Apache-2.0
"""Reads of a table field through steps 10 to 13 (`record_format.md` section 6, table items 3 and 4;
`read_side_contract.md` section 1, section 3 steps 10 to 13, section 5's first row and "The form's range"),
for HP20 to HP23 (`test_table_read_properties.py`).

A read holds a table `tables.py` draws, one step 8 accepts, on a field whose row allows a table, over an axis
drawn among the numeric conditions, its axis condition `not_applicable` and its other conditions stated as
`table_form_strategies.base_reads` states them, beside the same neighbour. The request gives the axis an
operating value, a range of it or none, and no tolerance but where a way draws one on the axis; the other
conditions it leaves unchecked (`unknown`), so that step 10 never ends the read and each read reaches step 11.

Each property draws a way first, the place its rule tells apart, and builds the table and the operating value
for it, so that the feature audit holds each way to its draw floor:
- HP20, at and beside the edges: at an edge inside the readable range, at one outside a narrowed range, one
  double below and one above an edge inside it, and outside the range beyond an edge;
- HP21, at and across the readable range's ends: strictly inside, at an end, one double outside, far outside,
  and inside `x` but outside a narrower `source_range`; each read once more with a `source_range` that is no
  narrower than `x`'s range added, and once more with a tolerance on the axis;
- HP22, the statistics block: at a knot, between two, and in a table holding `points`, a block for each knot;
- HP23, the two request checks step 11 makes: no operating value for the axis, or a range of it inside the
  readable range, across an end, holding an edge, or outside."""

import copy
import json
import math
from typing import NamedTuple

from hypothesis import assume
from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import ReadRequest, ReadResult, read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from tests.property import full_fields, tables
from tests.property.full_fields import CONDITIONS, full_forms, record_of
from tests.property.strategies import SIZE, Size
from tests.property.table_form_strategies import NEIGHBOUR, NEIGHBOUR_FIELD, TABLE_FIELDS
from tests.property.value_fields import NUMERIC_CONDITIONS, Json, mapping, registered_unit, row_of

EDGE_WAYS = (
    "at_an_edge_inside",
    "at_an_edge_outside",
    "just_below_an_edge",
    "just_above_an_edge",
    "across_an_edge",
)
RANGE_WAYS = ("inside", "at_an_end", "one_double_outside", "far_outside", "outside_a_narrower_source_range")
STATISTICS_WAYS = ("at_a_knot", "between_knots", "holding_points")
REQUEST_WAYS = (
    "no_operating_value",
    "range_inside",
    "range_across_an_end",
    "range_holding_an_edge",
    "range_outside",
)
# The `source_range`s an edge inside the readable range is drawn beside: those that may leave one there.
KEEPING_EDGES: tuple[tables.RangeKind, ...] = ("no_source_range", "narrower", "wider", "across_an_end")


class TableRead(NamedTuple):
    """A read of a table field: the way drawn, the record, the field's registered name, the axis, the table's
    numbers, the axis's operating value or range (both None for none), a tolerance on the axis, `want`, and
    for HP22 the blocks of `points`, one for each knot, where the table holds them."""

    way: str
    record: Json
    field: str
    axis: str
    table: tables.Table
    at: float | None
    over: tuple[float, float] | None = None
    tolerance: float | None = None
    want: str = "value"
    points: tuple[Json, ...] | None = None


def table_json(table: tables.Table, axis: str) -> Json:
    found: Json = {
        "axis": axis,
        "axis_unit": registered_unit(axis),
        "x": list(table.x),
        "y": list(table.y),
        "scheme": table.scheme,
        "edges": list(table.edges),
    }
    if table.source_range is not None:
        found["source_range"] = list(table.source_range)
    return found


def holding(field_name: str, axis: str, table: tables.Table, points: tuple[Json, ...] | None = None) -> Json:
    """A record holding `table` over `axis` as `field_name`, with the neighbour `base_reads` puts beside it,
    and `points` where given."""
    field = copy.deepcopy(full_forms()["table"][1])
    field.pop("label")
    field["unit"] = row_of(field_name)["unit"]
    field["conditions"] = {**copy.deepcopy(CONDITIONS), axis: {"status": "not_applicable"}}
    field["table"] = table_json(table, axis)
    if points is not None:
        mapping(field["table"])["points"] = [
            {"provenance": copy.deepcopy(field["provenance"]), "statistics": copy.deepcopy(block)}
            for block in points
        ]
    record = record_of(field, field_name)
    section, _, name = NEIGHBOUR.partition(".")
    sections = mapping(mapping(record["body"])["sections"])
    held = mapping(sections.setdefault(section, {"fields": {}}))
    mapping(held["fields"])[name] = copy.deepcopy(NEIGHBOUR_FIELD)
    return record


def table_field(drawn: TableRead) -> Json:
    section, _, name = drawn.field.partition(".")
    body = mapping(drawn.record["body"])
    return mapping(mapping(mapping(mapping(body["sections"])[section])["fields"])[name])


def request_of(drawn: TableRead) -> Json:
    """The request: the axis's operating value or range, in its registered unit, and `want`; a tolerance on
    the axis where drawn. The record's other conditions are stated with no tolerance, so each is unchecked."""
    unit = registered_unit(drawn.axis)
    operating: Json = {}
    if drawn.at is not None:
        operating[drawn.axis] = {"value": drawn.at, "unit": unit}
    elif drawn.over is not None:
        operating[drawn.axis] = {"range": list(drawn.over), "unit": unit}
    record = {**drawn.record, "content_hash": content_hash(drawn.record)}
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    requirement: Json = {"want": drawn.want}
    if drawn.tolerance is not None:
        requirement["conditions"] = {drawn.axis: {"tolerance": {"value": drawn.tolerance, "unit": unit}}}
    return {
        "target": {"record": pin, "field": drawn.field},
        "operating_conditions": operating,
        "requirement": requirement,
    }


def read_drawn(drawn: TableRead) -> ReadResult | str:
    """The read of `drawn`, or what it raised: "A read never stops with an error for anything a record or
    request contains" (`read_side_contract.md` section 2 item 1)."""
    record = {**drawn.record, "content_hash": content_hash(drawn.record)}
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    try:
        return read(request_of(drawn), store)
    except Exception as error:
        return f"raised {error!r}"


def checked_request(drawn: TableRead) -> ReadRequest:
    checked = ReadRequest.from_json(request_of(drawn))
    assert isinstance(checked, ReadRequest), checked
    return checked


def with_table(drawn: TableRead, table: tables.Table) -> TableRead:
    """`drawn` with its table's numbers replaced by `table`'s."""
    return drawn._replace(record=holding(drawn.field, drawn.axis, table, drawn.points), table=table)


# The places, each from the text's words, and the tables that hold them.


def readable(table: tables.Table) -> tuple[float, float]:
    return tables.readable_ends(table)


def axis_and_field(draw: st.DrawFn) -> tuple[str, str]:
    return draw(st.sampled_from(NUMERIC_CONDITIONS)), draw(st.sampled_from(TABLE_FIELDS))


def strictly_inside_edges(table: tables.Table) -> list[float]:
    low, high = readable(table)
    return sorted(edge for edge in table.edges if low < edge < high)


def an_edge_strictly_inside(draw: st.DrawFn, size: Size) -> tuple[tables.Table, float]:
    """A table with an edge strictly inside its readable range, and that edge: where the drawn `source_range`
    leaves none there, the table without it (every edge lies strictly between `x[0]` and `x[-1]`)."""
    table, _ = draw(tables.tables(size, with_edges=True, range_kinds=KEEPING_EDGES))
    if not strictly_inside_edges(table):
        table = table._replace(source_range=None)
    return table, draw(st.sampled_from(strictly_inside_edges(table)))


def narrowed_beyond(draw: st.DrawFn, table: tables.Table, edge: float) -> tables.Table:
    """`table` with a `source_range` that leaves `edge` outside the readable range: from the first knot above
    the edge to `x[-1]`, or from `x[0]` to the last knot below it. Each shares with `x`'s range a value that
    is no edge (table item 4), since every edge lies strictly between `x[0]` and `x[-1]`."""
    above = min(knot for knot in table.x if knot > edge)
    below = max(knot for knot in table.x if knot < edge)
    return table._replace(source_range=(above, table.x[-1]) if draw(st.booleans()) else (table.x[0], below))


def no_edge_between(table: tables.Table, at: float) -> bool:
    """`at` lies at no edge, and outside the readable range no edge lies between it and the range's nearest
    end, or on that end."""
    low, high = readable(table)
    if at < low:
        return not any(at <= edge <= low for edge in table.edges)
    if at > high:
        return not any(high <= edge <= at for edge in table.edges)
    return at not in table.edges


def beside_on(edge: float, side: float) -> float:
    return math.nextafter(edge, side)


@st.composite
def edge_reads(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = EDGE_WAYS) -> TableRead:
    """HP20: a read at or beside an edge, its way drawn first. Each place is one the table holds: one double
    below the least edge strictly inside the range, and above the greatest, is no edge, though one double
    beside another may be, two edges being adjacent doubles."""
    way = draw(st.sampled_from(ways))
    axis, field = axis_and_field(draw)
    table, edge = an_edge_strictly_inside(draw, size)
    inside = strictly_inside_edges(table)
    if way in ("at_an_edge_outside", "across_an_edge"):
        table = narrowed_beyond(draw, table, edge)
        low, _ = readable(table)
        if way == "at_an_edge_outside":
            at = edge
        else:
            # Beyond the edge, on the far side from the range: one double past it, unless that is another
            # edge, or `x`'s end on that side, which is none.
            toward = -math.inf if edge < low else math.inf
            beyond = [beside_on(edge, toward), table.x[0] if edge < low else table.x[-1]]
            at = draw(st.sampled_from(sorted({place for place in beyond if place not in table.edges})))
    elif way == "at_an_edge_inside":
        at = edge
    else:
        toward = -math.inf if way == "just_below_an_edge" else math.inf
        edges = [one for one in inside if beside_on(one, toward) not in table.edges]
        if not edges:
            # A chain of edges, each one double from the next, from an end of a narrowed range: without the
            # `source_range`, no edge lies below the least or above the greatest.
            table = table._replace(source_range=None)
            edges = [one for one in strictly_inside_edges(table) if beside_on(one, toward) not in table.edges]
        at = beside_on(draw(st.sampled_from(edges)), toward)
    return TableRead(way, holding(field, axis, table), field, axis, table, at)


def outside_places(table: tables.Table) -> dict[str, list[float]]:
    """The places outside the readable range at no edge and across none, by the way that reads each: one
    double beyond each end, `x`'s values beyond it, and a double far beyond each, where finite."""
    low, high = readable(table)
    found: dict[str, list[float]] = {
        "one_double_outside": [beside_on(low, -math.inf), beside_on(high, math.inf)],
        "far_outside": [
            low - abs(low) - 1,
            high + abs(high) + 1,
            *(knot for knot in table.x if knot < low or knot > high),
        ],
        "outside_a_narrower_source_range": [knot for knot in table.x if knot < low or knot > high],
    }
    return {
        way: sorted({place for place in places if math.isfinite(place) and no_edge_between(table, place)})
        for way, places in found.items()
    }


def without_edges(table: tables.Table) -> tables.Table:
    """`table` with no edge: each edge's second entry, the value above it, taken out of `x` and `y`."""
    x: list[float] = []
    y: list[float] = []
    for knot, value in zip(table.x, table.y, strict=True):
        if not (x and knot == x[-1]):
            x.append(knot)
            y.append(value)
    return table._replace(x=tuple(x), y=tuple(y), edges=())


def narrowed_below_the_last(table: tables.Table) -> tables.Table:
    """`table`, which holds no edge, with a `source_range` from `x[0]` to the double below `x[-1]`: one that
    shares `x[0]` with `x`'s range (table item 4), and leaves `x[-1]` outside the readable range."""
    return table._replace(source_range=(table.x[0], beside_on(table.x[-1], -math.inf)))


@st.composite
def range_reads(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = RANGE_WAYS) -> TableRead:
    """HP21: a read inside, at or outside the readable range's ends, its way drawn first, at no edge and
    across none. Where the table drawn holds no such place for the way, the table is changed so that it
    does: inside, a knot added beyond `x`'s end, which leaves the range room; at an end, its `source_range`
    taken away, which leaves `x`'s ends, no edges; outside, its `source_range` taken away, or, where edges or
    the largest doubles still leave no place, its edges taken away and a `source_range` ending a double below
    `x[-1]`."""
    way = draw(st.sampled_from(ways))
    axis, field = axis_and_field(draw)
    narrower = way == "outside_a_narrower_source_range"
    kinds: tuple[tables.RangeKind, ...] = (
        ("narrower", "within_an_interval") if narrower else tables.RANGE_KINDS
    )
    table, _ = draw(tables.tables(size, range_kinds=kinds))
    if way == "inside":
        table = with_room(table)
        low, high = readable(table)
        places = sorted({place for knot in (*table.x, low, high) for place in (knot, *tables.beside(knot))})
        at = draw(
            st.sampled_from([place for place in places if low < place < high and place not in table.edges])
        )
    elif way == "at_an_end":
        low, high = readable(table)
        if low in table.edges and high in table.edges:
            table = table._replace(source_range=None)
            low, high = readable(table)
        at = draw(st.sampled_from(sorted({end for end in (low, high) if end not in table.edges})))
    else:
        places = outside_places(table)[way]
        if not places and not narrower:
            table = table._replace(source_range=None)
            places = outside_places(table)[way]
        if not places:
            table = narrowed_below_the_last(without_edges(table))
            places = outside_places(table)[way]
        at = draw(st.sampled_from(places))
    return TableRead(way, holding(field, axis, table), field, axis, table, at)


def knot_added_beyond(table: tables.Table) -> tables.Table:
    """`table` with a knot added beyond `x[-1]`, holding `y[-1]`, so that the interval between them has room,
    or before `x[0]`, holding `y[0]`, where nothing finite lies far enough beyond `x[-1]`, and no
    `source_range`, which might leave the new interval outside; a log-log table's knots stay positive."""
    last, first = table.x[-1], table.x[0]
    beyond = last + abs(last) + 1
    if math.isfinite(beyond):
        return table._replace(x=(*table.x, beyond), y=(*table.y, table.y[-1]), source_range=None)
    before = first / 2 if first > 0 else first - abs(first) - 1
    return table._replace(x=(before, *table.x), y=(table.y[0], *table.y), source_range=None)


def with_an_interval_with_room(table: tables.Table) -> tables.Table:
    """`table`, or where no two neighbouring knots have a double between them, with a knot added."""
    if any(math.nextafter(low, math.inf) < high for low, high in zip(table.x, table.x[1:], strict=False)):
        return table
    return knot_added_beyond(table)


def with_room(table: tables.Table) -> tables.Table:
    """`table` as it is where its readable range holds a double strictly inside it at no edge; otherwise
    without its `source_range` and, where `x`'s range has no room either, with a knot added beyond `x[-1]`,
    holding `y[-1]`, so that the interval between them has room (or before `x[0]` where `x[-1]` is the
    largest double)."""

    def roomy(found: tables.Table) -> bool:
        low, high = readable(found)
        return any(
            low < place < high and place not in found.edges
            for knot in (*found.x, low, high)
            for place in (knot, *tables.beside(knot))
        )

    if roomy(table):
        return table
    table = table._replace(source_range=None)
    if roomy(table):
        return table
    return knot_added_beyond(table)


def no_narrower(draw: st.DrawFn, x: tuple[float, ...]) -> tuple[float, float]:
    """A `source_range` no narrower than `[x[0], x[-1]]`: each end `x`'s or beyond it, which "never extends
    the readable range" (table item 4)."""
    first = draw(st.one_of(st.just(x[0]), tables.below(x[0]))) if x[0] > -tables.LARGEST else x[0]
    last = draw(st.one_of(st.just(x[-1]), tables.above(x[-1]))) if x[-1] < tables.LARGEST else x[-1]
    return first, last


@st.composite
def statistics_reads(
    draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = STATISTICS_WAYS
) -> TableRead:
    """HP22: a read at a knot or between two, or of a table holding `points`, its way drawn first; the table's
    block as `full_forms` states it, and in `points` a block for each knot whose `sd` is the knot's index, so
    that no two hold one block."""
    way = draw(st.sampled_from(ways))
    axis, field = axis_and_field(draw)
    table, _ = draw(tables.tables(size, range_kinds=("no_source_range", "wider")))
    if way == "between_knots":
        table = with_an_interval_with_room(table)
        roomy = [
            (low, high)
            for low, high in zip(table.x, table.x[1:], strict=False)
            if math.nextafter(low, math.inf) < high
        ]
        low, high = draw(st.sampled_from(roomy))
        at = draw(st.floats(low, high, exclude_min=True, exclude_max=True))
    else:
        at = draw(st.sampled_from(sorted(knot for knot in set(table.x) if knot not in table.edges)))
    points = None
    if way == "holding_points":
        block = mapping(full_forms()["table"][1]["statistics"])
        points = tuple({**copy.deepcopy(block), "sd": float(index)} for index in range(len(table.x)))
    return TableRead(way, holding(field, axis, table, points), field, axis, table, at, points=points)


@st.composite
def request_reads(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = REQUEST_WAYS) -> TableRead:
    """HP23: no operating value for the axis, or a range of it, its way drawn first."""
    way = draw(st.sampled_from(ways))
    axis, field = axis_and_field(draw)
    with_edges = True if way == "range_holding_an_edge" else None
    table, _ = draw(tables.tables(size, with_edges=with_edges, range_kinds=KEEPING_EDGES))
    if way == "range_holding_an_edge" and not strictly_inside_edges(table):
        table = table._replace(source_range=None)
    low, high = readable(table)
    over: tuple[float, float] | None = None
    if way == "range_inside":
        over = (low, high) if low == high else tuple(sorted((low, draw(st.floats(low, high)))))  # type: ignore[assignment]
    elif way == "range_across_an_end":
        if draw(st.booleans()) and low > -tables.LARGEST:
            over = (draw(tables.below(low)), high)
        else:
            assume(high < tables.LARGEST)
            over = (low, draw(tables.above(high)))
    elif way == "range_holding_an_edge":
        edge = draw(st.sampled_from(strictly_inside_edges(table)))
        over = (draw(st.floats(low, edge)), draw(st.floats(edge, high)))
    elif way == "range_outside":
        assume(high < tables.LARGEST)
        above = draw(tables.above(high))
        over = (
            above,
            draw(
                st.one_of(st.just(above), tables.above(above)) if above < tables.LARGEST else st.just(above)
            ),
        )
    return TableRead(way, holding(field, axis, table), field, axis, table, None, over)


# The table reads HP1, HP2, HP11 and HP12 draw beside their own kinds (`test_result_properties.py`,
# `test_model_properties.py`): a kind drawn first among HP20 to HP23's families, then that family's way, with
# `want: value` in three draws of four and `want: bounds` in the fourth, and, across the range, a tolerance on
# the axis in half the draws, of the distance from the read to `x`'s farther end; HP12 draws a table beside a
# constant among alternatives too.
TABLE_KINDS = ("table_at_an_edge", "table_across_its_range", "table_statistics", "table_request")
ALTERNATIVES_KIND = "table_among_alternatives"
BUILDERS = {
    "table_at_an_edge": edge_reads,
    "table_across_its_range": range_reads,
    "table_statistics": statistics_reads,
    "table_request": request_reads,
}
WANTS = ("value", "value", "value", "bounds")


def farther_end(table: tables.Table, at: float) -> float | None:
    """The distance from `at` to `x`'s farther end, where finite."""
    distance = max(abs(table.x[0] - at), abs(at - table.x[-1]))
    return distance if math.isfinite(distance) else None


@st.composite
def table_reads(
    draw: st.DrawFn, size: Size = SIZE, kinds: tuple[str, ...] = TABLE_KINDS
) -> tuple[str, TableRead]:
    """A table read of one of `kinds`, the kind drawn first, then its way, its `want` and a tolerance."""
    kind = draw(st.sampled_from(kinds))
    family = draw(st.sampled_from(sorted(BUILDERS))) if kind == ALTERNATIVES_KIND else kind
    drawn = draw(BUILDERS[family](size))._replace(want=draw(st.sampled_from(WANTS)))
    if family == "table_across_its_range" and draw(st.booleans()) and drawn.at is not None:
        drawn = drawn._replace(tolerance=farther_end(drawn.table, drawn.at))
    if kind == ALTERNATIVES_KIND:
        drawn = among_alternatives(draw, drawn)
    return kind, drawn


def among_alternatives(draw: st.DrawFn, drawn: TableRead) -> TableRead:
    """`drawn` with its table one of two alternatives of its field, the other a constant of the field's unit
    whose conditions it states as `full_fields`'s constant does, unchecked by the request, in an order
    drawn."""
    table = copy.deepcopy(table_field(drawn))
    constant = full_fields.constant(full_fields.PROVENANCE_BY_SOURCE, "population", label=False)
    constant["unit"] = row_of(drawn.field)["unit"]
    alternatives: list[JsonValue] = [table, constant] if draw(st.booleans()) else [constant, table]
    record = copy.deepcopy(drawn.record)
    section, _, name = drawn.field.partition(".")
    fields = mapping(mapping(mapping(mapping(record["body"])["sections"])[section])["fields"])
    fields[name] = {"alternatives": alternatives}
    return drawn._replace(record=record)


def source_of(drawn: TableRead) -> bytes:
    """The record as a source, its content hash the one its pin names."""
    return json.dumps({**drawn.record, "content_hash": content_hash(drawn.record)}).encode()


# The S3 design's monotonicity property (the maintainer's information monotonicity, 2026-10-14) over a table
# read the request can meet: the field's conditions its axis, `not_applicable`, and each other condition its
# row requires, stated and met by the request (a numeric one by its value with no tolerance, a token one by an
# accept list of its token), so that a read inside the readable range is `met`.
MET_VALUES: dict[str, float] = {"temperature": 310.15, "shear_rate": 100.0, "magnetic_flux_density": 0.5}


def met_conditions(field_name: str, axis: str) -> tuple[Json, Json, Json]:
    """The field's conditions, and the request's operating conditions and requirement that meet each."""
    held: Json = {axis: {"status": "not_applicable"}}
    operating: Json = {}
    required: Json = {}
    for name in VOCABULARY.fields[field_name].requires:
        if name == axis:
            continue
        spec = VOCABULARY.conditions[name]
        if spec.shape == "token":
            token = sorted(spec.tokens)[0]
            held[name] = {"token": token, "basis": "stated"}
            required[name] = {"accept": [token]}
        else:
            assert spec.unit is not None
            value = MET_VALUES[name]
            held[name] = {"value": value, "unit": spec.unit, "basis": "stated"}
            operating[name] = {"value": value, "unit": spec.unit}
            required[name] = {"tolerance": {"value": 0.0, "unit": spec.unit}}
    return held, operating, required


class MetWorld(NamedTuple):
    """A table read the request can meet: the way the read lies, the record without `source_range` and with
    the one drawn, the field, and the request at the operating value, without and with a tolerance on the
    axis."""

    way: str
    plain: Json
    narrowed: Json
    field: str
    request: Json
    tolerant: Json


@st.composite
def met_worlds(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = RANGE_WAYS[:4]) -> MetWorld:
    """A table read inside, at or outside its range without a `source_range`, its way drawn first, and the
    same table with a `source_range` of a kind `tables.py` draws, narrower ones among them."""
    drawn = draw(range_reads(size, ways))
    axis, field_name, table, at = drawn.axis, drawn.field, drawn.table, drawn.at
    assert at is not None
    # A narrower one needs three distinct knots, as `tables.tables` draws it beside.
    distinct = sorted(set(table.x))
    kinds: list[tables.RangeKind] = [
        kind for kind in tables.RANGE_KINDS[1:] if kind != "narrower" or len(distinct) > 2
    ]
    bounds = draw(tables.source_range(draw(st.sampled_from(kinds)), distinct, list(table.edges)))
    narrowed = table._replace(source_range=bounds)
    held, operating, required = met_conditions(field_name, axis)
    unit = registered_unit(axis)
    operating[axis] = {"value": at, "unit": unit}

    def record(of: tables.Table) -> Json:
        found = holding(field_name, axis, of)
        mapping(table_field(drawn._replace(record=found)))["conditions"] = copy.deepcopy(held)
        return {**found, "content_hash": content_hash(found)}

    plain, narrow = record(table._replace(source_range=None)), record(narrowed)
    pin = {member: plain[member] for member in ("id", "version", "content_hash")}
    request: Json = {
        "target": {"record": pin, "field": field_name},
        "operating_conditions": operating,
        "requirement": {"want": "value", "conditions": required},
    }
    distance = farther_end(table, at)
    tolerant = copy.deepcopy(request)
    if distance is not None:
        mapping(mapping(tolerant["requirement"])["conditions"])[axis] = {
            "tolerance": {"value": distance, "unit": unit}
        }
    return MetWorld(drawn.way, plain, narrow, field_name, request, tolerant)
