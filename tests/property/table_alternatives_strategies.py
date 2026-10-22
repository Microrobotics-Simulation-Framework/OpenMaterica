# SPDX-License-Identifier: Apache-2.0
"""Strategies for S4d's properties, HP39 and HP40 (`test_table_alternatives_properties.py`), and HP12's part
over them: a field holding alternatives, read with no pick and no overlay (`read_side_contract.md` section 3,
step 7), one of which is a table read at a place where step 11 gives a reason, or, for HP40, none.

The others are S4a's draw (`alternatives_strategies.py`, untouched), its outcome drawn first among its five
and built as S4a builds it, over `fluid.dynamic_viscosity`, a field whose row allows a table, a constant and
an interval: a base read's field, a constant unless the table's way names a `want` that needs an interval
(below), and one to five alternatives, each the base field with its own member drawn afresh and changed by
S4a's way for its standing. The table is the base field held as a table over `magnetic_flux_density`, a
numeric condition the row does not require, no other alternative states and the requirement does not name, so
that its operating value, its range or its absence changes the table's read alone. It carries the row's label,
and is stored at an index drawn among the others.

Its way, drawn second, is one of two parts of four ways each, so that each test function draws among at most
five alike:
- `KEPT_OR_SET_ASIDE`: one double outside its readable range, at no edge and across none, with no
  extrapolation (`outside`, set aside); over an operating range of its axis (`over_an_operating_range`,
  staying, a form `want` cannot give); outside as before under an extrapolation at the read and `want: value`
  (`kept`, staying, its value stated without origin, whose step-12 reason stands beside `no_pick` once it is
  read on); and the same under `want: bounds` (`kept_under_bounds`, set aside: no extrapolation applies under
  another `want`);
- `REFUSES`: at an edge inside its readable range (`at_an_edge_inside`); at an edge outside a narrowed one,
  `outside_range` beside `at_edge` (`at_an_edge_outside`); with no operating value for its axis, reaching step
  11 (`no_operating_value`); and with none, set aside at step 10 for a token the request does not accept, so
  never reaching step 11 (`no_operating_value_set_aside`).

Where the way names a `want` (`kept`, `value`; `kept_under_bounds`, `bounds`), the others are built for their
outcome under it: `no_pick` over the form that `want` gives, `want_mismatch` over the other, none of them held
in another form; otherwise under the `want` S4a draws for the outcome. No nominal is drawn: S4a's properties
hold one among alternatives, as they hold a set-aside alternative held in another form and a read without the
hash suite, which change nothing of step 11's rows: the others' set-aside alternatives keep the base form, and
the claims are plain read's and the hash suite's. Each place is the one `table_read_strategies.py` draws for
the way named beside it (`range_reads`, `edge_reads`), its numbers moved onto the axis here. HP40 draws a
table read inside its readable range (`inside`), which stays, and moves that range off the operating value
(`narrowed`)."""

import copy
import math
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.property import result_strategies as results
from tests.property import table_read_strategies as table_reads
from tests.property import tables
from tests.property.alternatives_strategies import (
    OUTCOMES,
    REFUSING,
    Alternatives,
    changed,
    counts,
    disagreeing,
    holding,
    pinned_to,
    set_aside_ways,
    staying_ways,
    want_for,
    without_implying_facts,
)
from tests.property.condition_strategies import at, base_reads, reference
from tests.property.strategies import Size
from tests.property.value_fields import registered_unit

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

FIELD = "fluid.dynamic_viscosity"
AXIS = "magnetic_flux_density"
KEPT_OR_SET_ASIDE = ("outside", "over_an_operating_range", "kept", "kept_under_bounds")
REFUSES = ("at_an_edge_inside", "at_an_edge_outside", "no_operating_value", "no_operating_value_set_aside")
INSIDE = "inside"
WAYS = (*KEPT_OR_SET_ASIDE, *REFUSES)
# How the table stands by its way (section 3, step 7), which HP39 holds its oracle to, so that the audit's
# count of each way is a count of what the text decides.
STANDING = {
    "outside": "set_aside",
    "over_an_operating_range": "stays",
    "kept": "stays",
    "kept_under_bounds": "set_aside",
    "at_an_edge_inside": "refuses",
    "at_an_edge_outside": "refuses",
    "no_operating_value": "refuses",
    "no_operating_value_set_aside": "set_aside",
    INSIDE: "stays",
}
# The place each way reads the table at, as `table_read_strategies.py` draws it: one way of its own each.
PLACE = {
    "outside": "one_double_outside",
    "kept": "one_double_outside",
    "kept_under_bounds": "one_double_outside",
    "over_an_operating_range": "inside",
    "at_an_edge_inside": "at_an_edge_inside",
    "at_an_edge_outside": "at_an_edge_outside",
    "no_operating_value": "inside",
    "no_operating_value_set_aside": "inside",
    INSIDE: "inside",
}
# The `want` a way reads the table under, where it names one, and the base form each outcome of the others
# then needs: `no_pick` the form that `want` gives, `want_mismatch` the other.
NAMED_WANT = {"kept": "value", "kept_under_bounds": "bounds"}
FORM_GIVEN = {"value": "constant", "bounds": "interval"}
FORM_NOT_GIVEN = {"value": "interval", "bounds": "constant"}
EXTRAPOLATED = ("kept", "kept_under_bounds")
WITHOUT_AN_OPERATING_VALUE = ("no_operating_value", "no_operating_value_set_aside")


class TableAlternatives(NamedTuple):
    """The draw: the outcome S4a's draw gives the others, drawn first; the table's way, drawn second; the
    field read (`drawn`, S4a's shape, its `ways` naming the table "table"); the table's stored index, its
    numbers, and the place it is read at, where the request gives one; and `inside`, a place inside its
    readable range at no edge, where it reads a value."""

    others: str
    way: str
    drawn: Alternatives
    table_index: int
    table: tables.Table
    at: float | None
    inside: float | None

    @property
    def stored(self) -> list[JsonValue]:
        return self.drawn.stored


def table_alternative(field: JsonObject, table: tables.Table) -> JsonObject:
    """The base field held as `table` over `AXIS`, its axis condition `not_applicable`, every other as the
    base states it, with the row's label."""
    alternative = copy.deepcopy(field)
    for member in ("value", "interval", "label"):
        alternative.pop(member, None)
    alternative["form"] = "table"
    alternative["table"] = table_reads.table_json(table, AXIS)
    at(alternative, "conditions")[AXIS] = {"status": "not_applicable"}
    label = VOCABULARY.fields[FIELD].label
    assert label is not None
    alternative["label"] = label
    return alternative


def placed(draw: Draw, size: Size, way: str) -> table_reads.TableRead:
    """The table and the place it is read at for `way`, as `table_read_strategies.py` draws them."""
    place = PLACE[way]
    if place in table_reads.EDGE_WAYS:
        return draw(table_reads.edge_reads(size, (place,)))
    return draw(table_reads.range_reads(size, (place,)))


def operating(way: str, read: table_reads.TableRead, draw: Draw) -> JsonObject | None:
    """The request's operating condition for the axis: the place's value, a range from it upward over an
    operating range, or none."""
    if way in WITHOUT_AN_OPERATING_VALUE:
        return None
    unit = registered_unit(AXIS)
    assert read.at is not None
    if way == "over_an_operating_range":
        return {"range": [read.at, draw(tables.above(read.at))], "unit": unit}
    return {"value": read.at, "unit": unit}


def form_and_want(draw: Draw, outcome: str, way: str) -> tuple[str, str | None]:
    """The base form, and the `want` the way names, for the others' `outcome`."""
    named = NAMED_WANT.get(way)
    if named is None:
        return "constant", None
    if outcome == "no_pick":
        return FORM_GIVEN[named], named
    if outcome == "want_mismatch":
        return FORM_NOT_GIVEN[named], named
    return "constant", named


def keeping_the_form(outcome: str, number: int) -> bool:
    """Whether the staying alternative of the others numbered `number` keeps the base form, as S4a's
    `no_pick` keeps its first."""
    return outcome == "no_pick" and number == 0


@st.composite
def table_alternatives(draw: Draw, size: Size, ways: tuple[str, ...]) -> TableAlternatives:
    """The others' outcome drawn first among S4a's five, the table's way second among `ways`, then the
    others as S4a draws them, and the table among them."""
    outcome = draw(st.sampled_from(OUTCOMES))
    way = draw(st.sampled_from(ways))
    form, named = form_and_want(draw, outcome, way)
    read = draw(base_reads(size, (FIELD,), form))
    without_implying_facts(read.record, read.field)
    field = results.field_at(read.record, read.field)
    results.without_origin_s_reason(field)
    refusing, set_aside, staying = counts(draw, outcome)
    # S4a's `no_pick` keeps its first staying alternative in the base form; under a `want` the way names,
    # `want_mismatch` keeps every one in it, so that none is held in the form that `want` gives.
    none_giving = outcome == "want_mismatch" and named is not None
    others = [
        *(draw(st.sampled_from(REFUSING)) for _ in range(refusing)),
        *(draw(st.sampled_from(set_aside_ways(form))) for _ in range(set_aside)),
        *(
            draw(
                st.sampled_from(
                    staying_ways(form, FIELD, giving=none_giving or keeping_the_form(outcome, number))
                )
            )
            for number in range(staying)
        ),
    ]
    others = draw(st.permutations(others))
    want = named or want_for(draw, outcome, form, FIELD)
    request = results.with_want(read.request, want)
    acceptances: list[JsonValue] = draw(disagreeing(read)) if "request_fault" in others else []
    stored: list[JsonValue] = []
    for other in others:
        alternative = results.another_value(draw, field, FIELD)
        changed(draw, alternative, other, request, FIELD)
        stored.append(alternative)
    place = placed(draw, size, way)
    table = table_alternative(field, place.table)
    if way in EXTRAPOLATED:
        at(table, "provenance")["origin"] = "stated_without_origin"
        acceptances.append(
            {
                "acceptance": "extrapolation",
                "record": reference(read.record),
                "field": FIELD,
                "method": "constant",
                "law": "the end value held",
            }
        )
    if way == "no_operating_value_set_aside":
        changed(draw, table, "not_accepted", request, FIELD)
    given = operating(way, place, draw)
    if given is not None:
        at(request, "operating_conditions")[AXIS] = given
    if acceptances:
        request["acceptances"] = acceptances
    position = draw(st.integers(0, len(stored)))
    stored.insert(position, table)
    record = results.holding(read, {"alternatives": stored})
    drawn = Alternatives(
        outcome,
        form,
        (*others[:position], "table", *others[position:]),
        record,
        pinned_to(request, record, reference(read.record)),
        results.WITH_HASH,
        FIELD,
        False,
    )
    inside = place.at if PLACE[way] == INSIDE else None
    return TableAlternatives(outcome, way, drawn, position, place.table, place.at, inside)


def without_the_table(drawn: TableAlternatives) -> Alternatives:
    """The others alone, as S4a's draw gives them: the field without the table, its index gone."""
    others = [alternative for index, alternative in enumerate(drawn.stored) if index != drawn.table_index]
    ways = tuple(way for index, way in enumerate(drawn.drawn.ways) if index != drawn.table_index)
    record, request = holding_alternatives(drawn.drawn, others)
    return drawn.drawn._replace(ways=ways, record=record, request=request)


def holding_alternatives(drawn: Alternatives, stored: list[JsonValue]) -> tuple[JsonObject, JsonObject]:
    """The record of `drawn` holding `stored` as the field's alternatives, pinned by its hash, and the
    request pinned to it."""
    return holding(drawn, {"alternatives": stored})


def narrowed(drawn: TableAlternatives) -> Alternatives:
    """HP40: the field with the table's readable range moved off the operating value, which lies strictly
    inside it at no edge: a `source_range` from the double above that value to the readable range's upper end,
    or, where that holds no value that is no edge (table item 4: the source range shares with `[x[0], x[-1]]`
    "at least one value that is no edge"), from its lower end to the double below; and where neither does,
    the readable range's ends lying one double from the value and both edges, from that double to `x`'s end,
    which is no edge (`record_format.md` section 6, table items 3 and 4)."""
    at_ = drawn.at
    assert at_ is not None
    low, high = tables.readable_ends(drawn.table)
    above, below = math.nextafter(at_, math.inf), math.nextafter(at_, -math.inf)
    candidates = [(above, high), (low, below), (above, drawn.table.x[-1])]
    moved = next(
        drawn.table._replace(source_range=candidate)
        for candidate in candidates
        if candidate[0] < candidate[1] or candidate[0] not in drawn.table.edges
    )
    stored = copy.deepcopy(drawn.stored)
    table = stored[drawn.table_index]
    assert isinstance(table, dict)
    table["table"] = table_reads.table_json(moved, AXIS)
    record, request = holding_alternatives(drawn.drawn, stored)
    return drawn.drawn._replace(record=record, request=request)
