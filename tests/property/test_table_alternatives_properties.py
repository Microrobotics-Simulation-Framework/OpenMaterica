# SPDX-License-Identifier: Apache-2.0
"""S4d's properties: step 7 over a field holding alternatives, one of them a table whose read gives a reason
at step 11, read with no pick and no overlay (`read_side_contract.md` section 3, step 7; `record_format.md`
section 5 items 2 to 5), over the draws of `table_alternatives_strategies.py`.

- HP39, in two parts by the table's way: the read agrees with HP27's oracle
  (`test_alternatives_properties.py`), which composes the reads of each alternative alone, with step 11's
  standings: an alternative whose read alone gives `at_edge` refuses the field, wherever the edge lies; one
  whose read alone gives `outside_range` without `at_edge` is set aside, unless that read applies an
  extrapolation, carrying its `assumption`, when it stays; one whose read alone is over an operating range of
  its axis (`want_mismatch` with the axis) stays, a form `want` cannot give; and `request_incomplete`, the
  request's fault, refuses it, carrying no index. Under `no_pick` the entry of a table kept or read over a
  range holds its table as stored and the members and step 12's labels of a read of it that reaches step 12:
  under the extrapolation that keeps it, or inside its readable range. And the extrapolation is among what the
  read applied exactly where the table it covers is the one left.
- HP40: ranges among alternatives. Moving a table alternative's readable range off the operating value, a
  narrower `source_range` and no edge met, gives the read of the field without that alternative, its indexes
  moved, where another stays, and `not_met` with every alternative's reasons where none does; it never makes a
  refusal `met`.

Each part's checks hold the draw to what it says first (`check_drawn`): the others' outcome, as S4a's oracle
gives it over them alone, and the table's standing, as HP39's gives it over its read alone, with the reasons
that define its way."""

import json
import math

import pytest
from hypothesis import given

from materica.core.read import ReadResult, read
from materica.core.record import RecordStore
from tests.property import table_alternatives_strategies as strategies
from tests.property import tables
from tests.property import test_alternatives_properties as hp27
from tests.property.alternatives_strategies import OUTCOMES, Alternatives, holding
from tests.property.strategies import SIZE
from tests.property.support import feature, same
from tests.property.table_alternatives_strategies import (
    AXIS,
    INSIDE,
    KEPT_OR_SET_ASIDE,
    REFUSES,
    STANDING,
    TableAlternatives,
)
from tests.property.test_model_properties import compared
from tests.property.value_fields import registered_unit
from tests.reference.strict_json import JsonObject, JsonValue

# HP39's oracle: HP27's, with step 11's rows.


def over_a_range(alone_read: JsonObject) -> bool:
    """Whether a read alone gave `want_mismatch` with a condition: section 2 item 2 gives one exactly "for a
    read over a range of an axis", which section 1 refuses at step 11."""
    return any(
        reason["code"] == "want_mismatch" and "condition" in reason for reason in hp27.reasons_of(alone_read)
    )


def standing(alone_read: JsonObject) -> str:
    """How an alternative stands, from its read alone (section 3, step 7): HP27's rules, and step 11's."""
    not_met = hp27.codes_of(alone_read, "not_met")
    if "request_incomplete" in not_met:
        # "So does a fault of the request (section 1): an alternative whose read reaches step 11 with no
        # operating value for its form's axis refuses the field"
        return "refuses"
    if "at_edge" in not_met:
        # "A table alternative read exactly at a declared edge refuses the field, wherever the edge lies,
        # outside the readable range included."
        return "refuses"
    if "outside_range" in not_met:
        # "set aside where its read lies outside its form's range at step 11, not exactly at a declared edge,
        # and no extrapolation the request carries would cover it"; one that would cover it is applied to the
        # read alone, which then carries "the declaration it rests on" (section 2, `assumption`)
        return "stays" if "assumption" in alone_read else "set_aside"
    if over_a_range(alone_read):
        # "one whose form `want` cannot give (... or a table read over an operating range of its axis, say)"
        return "stays"
    return hp27.standing(alone_read)


def inside_read(drawn: TableAlternatives) -> JsonObject:
    """The table read alone at `drawn.inside`, inside its readable range at no edge, under `want: value`,
    which gives its form (section 6)."""
    record, request = holding(drawn.drawn, drawn.stored[drawn.table_index])
    hp27.request_requirement(request)["want"] = "value"
    operating = request["operating_conditions"]
    assert isinstance(operating, dict)
    assert drawn.inside is not None
    operating[AXIS] = {"value": drawn.inside, "unit": registered_unit(AXIS)}
    return hp27.read_written(record, request, drawn.drawn.claims)


def entry(drawn: TableAlternatives, index: int) -> JsonObject:
    """An alternative's entry under `no_pick` (section 2, the `alternative_values` row): HP27's, but for a
    table "kept outside its form's range" or "read over an operating range of its axis", which holds "its
    form's member as stored instead, with no nominal or extrapolation applied", and "the labels step 12 gives
    that alternative even where its read ended at step 11": its conditions as its read alone gives them, its
    table as stored and the other members and labels as a read of it that reaches step 12 gives them, under
    the extrapolation that keeps it, or, over a range, inside its readable range."""
    if index != drawn.table_index:
        return hp27.entry(drawn.drawn, index)
    own = hp27.alone(drawn.drawn, index)
    if "assumption" in own:
        reaching_step_12 = own
    elif over_a_range(own):
        reaching_step_12 = inside_read(drawn)
    else:
        return hp27.entry(drawn.drawn, index)
    found: JsonObject = {
        "alternative": float(index),
        "value": reaching_step_12["table"],
        "conditions": own["conditions"],
    }
    for name in ("unit", "specimen", "statistics", "provenance"):
        found[name] = reaching_step_12[name]
    labels = reaching_step_12["labels"]
    assert isinstance(labels, list)
    found["labels"] = [label for label in labels if label != "hash_not_checked"]
    return found


def expected(drawn: TableAlternatives) -> tuple[str, JsonObject]:
    return hp27.expected(drawn.drawn, standing, lambda _, index: entry(drawn, index))


def read_result(drawn: Alternatives) -> ReadResult:
    store = RecordStore()
    store.add("record", json.dumps(drawn.record).encode())
    return read(drawn.request, store, claims=drawn.claims)


def way_shown(alone_read: JsonObject) -> str:
    """The way a table's read alone shows by the reasons that define it: no operating value for its axis at
    step 11 (`request_incomplete`), an edge outside the readable range or inside it, outside it kept by an
    extrapolation (`assumption`) or not, over an operating range of its axis, set aside at step 10, or inside
    its readable range, giving none of these."""
    not_met = hp27.codes_of(alone_read, "not_met")
    if "request_incomplete" in not_met:
        return "no_operating_value"
    if "at_edge" in not_met:
        return "at_an_edge_outside" if "outside_range" in not_met else "at_an_edge_inside"
    if "outside_range" in not_met:
        return "kept" if "assumption" in alone_read else "outside"
    if over_a_range(alone_read):
        return "over_an_operating_range"
    return "no_operating_value_set_aside" if not_met else INSIDE


# A way whose read alone shows as another's: outside under `want: bounds`, where no extrapolation applies.
SHOWN_AS = {"kept_under_bounds": "outside"}


def check_drawn(drawn: TableAlternatives) -> None:
    """The strategy's own check: the others alone give the outcome drawn for them, and the table stands as its
    way says and its read alone gives the reasons that define the way, so that the audit's counts are of what
    the text decides."""
    others = hp27.expected(strategies.without_the_table(drawn))[0]
    assert others == drawn.others, f"the others drawn for {drawn.others}, the text's {others}"
    alone_read = hp27.alone(drawn.drawn, drawn.table_index)
    table = standing(alone_read)
    assert table == STANDING[drawn.way], f"the table drawn {drawn.way}, standing {table}"
    shown = way_shown(alone_read)
    assert shown == SHOWN_AS.get(drawn.way, drawn.way), f"the table drawn {drawn.way}, its read alone {shown}"


def check_outcome(drawn: TableAlternatives) -> None:
    """HP39: the read is the oracle's, every member compared as section 2 compares it."""
    actual, oracle = compared(hp27.read_drawn(drawn.drawn)), compared(expected(drawn)[1])
    assert same(actual["status"], oracle["status"]), (
        f"status {actual['status']}, the text's {oracle['status']}"
    )
    assert same(actual["reasons"], oracle["reasons"]), (
        f"reasons {actual['reasons']}, the text's {oracle['reasons']}"
    )
    assert actual.keys() == oracle.keys(), f"members {sorted(actual)}, the text's {sorted(oracle)}"
    for name in oracle:
        assert same(actual[name], oracle[name]), f"{name}: {actual[name]}, the text's {oracle[name]}"


def check_applied(drawn: TableAlternatives) -> None:
    """HP39: "The extrapolation is applied only where that alternative is the one left" (section 3, step 7):
    the read applies what the read of the one left alone applies, and nothing where the result rests on no
    single alternative (section 2, `applied` outside the result's JSON: what a build maps to what accepted
    it)."""
    outcome = expected(drawn)[0]
    found = read_result(drawn.drawn).applied
    if outcome != "one_left":
        assert found == (), f"applied {found}, the outcome {outcome}"
        return
    reads = [hp27.alone(drawn.drawn, index) for index in range(len(drawn.stored))]
    (left,) = [index for index, alone_read in enumerate(reads) if standing(alone_read) == "stays"]
    record, request = holding(drawn.drawn, drawn.stored[left])
    alone = read_result(drawn.drawn._replace(record=record, request=request)).applied
    assert found == alone, f"applied {found}, the one left alone {alone}"


def check_table_alternative(drawn: TableAlternatives) -> None:
    check_drawn(drawn)
    check_outcome(drawn)
    check_applied(drawn)


# HP40: ranges among alternatives.


def check_narrowed(drawn: TableAlternatives) -> None:
    """HP40: the table, read inside its readable range, that range moved off the operating value."""
    full = hp27.read_drawn(strategies.narrowed(drawn))
    others = strategies.without_the_table(drawn)
    without = hp27.read_drawn(others)
    shifted = hp27.moved(without, lambda index: index + 1 if index >= drawn.table_index else index)
    if hp27.expected(others)[0] in ("refused", "all_set_aside"):
        # "where an alternative refuses the field, or every alternative is set aside, `not_met`, with every
        # alternative's reasons": the table's own, `outside_range` with its axis, among them.
        its_own: JsonObject = {
            "code": "outside_range",
            "condition": AXIS,
            "alternative": float(drawn.table_index),
        }
        reasons: list[JsonValue] = [*hp27.reasons_of(shifted), its_own]
        shifted = {**shifted}
        shifted["reasons"] = reasons
    actual, oracle = compared(full), compared(shifted)
    assert actual.keys() == oracle.keys(), f"members {sorted(actual)}, without the table {sorted(oracle)}"
    for name in oracle:
        assert same(actual[name], oracle[name]), (
            f"{name}, narrowed: {actual[name]}, without it {oracle[name]}"
        )
    if hp27.read_drawn(drawn.drawn)["status"] == "not_met":
        assert full["status"] != "met", "a refusal made met by moving a table's range off the operating value"


# HP40's move of a readable range, at each of its three places, on tables written by hand: the third, where
# both doubles beside the value are the readable range's ends and edges, `ci`'s draws reach too seldom to hold
# it.
ABOVE_ONE, BELOW_ONE = math.nextafter(1.0, math.inf), math.nextafter(1.0, -math.inf)
MOVED_OFF: list[tuple[tables.Table, float, tuple[float, float]]] = [
    (tables.Table((0.0, 4.0), (1.0, 2.0), "linear", (), None), 1.0, (ABOVE_ONE, 4.0)),
    (
        tables.Table(
            (0.0, ABOVE_ONE, ABOVE_ONE, 4.0), (1.0, 2.0, 3.0, 4.0), "linear", (ABOVE_ONE,), (0.0, ABOVE_ONE)
        ),
        1.0,
        (0.0, BELOW_ONE),
    ),
    (
        tables.Table(
            (0.0, BELOW_ONE, BELOW_ONE, ABOVE_ONE, ABOVE_ONE, 4.0),
            (1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            "linear",
            (BELOW_ONE, ABOVE_ONE),
            (BELOW_ONE, ABOVE_ONE),
        ),
        1.0,
        (ABOVE_ONE, 4.0),
    ),
]


@pytest.mark.parametrize(("table", "at", "moved"), MOVED_OFF, ids=["above", "below", "to_the_end_of_x"])
def test_a_readable_range_moved_off_the_value_holds_a_value_that_is_no_edge(
    table: tables.Table, at: float, moved: tuple[float, float]
) -> None:
    found = strategies.off_the_value(table, at)
    assert found == moved
    low, high = found
    assert not low <= at <= high
    assert low < high or low not in table.edges


# Each property's examples, and its check of one, which the mutant searches take too.


# Each part draws the others' outcome first among S4a's five and the table's way second among its four, each
# declared by its chance, below its least share measured, at which a correct run falls below the floor with a
# probability of at most 1e-6 at the variance measured. Over 20 derandomised runs of 2,000 examples a size,
# each its own stream (2026-10-22), an outcome showed in 0.19 to 0.21 of the examples (least 0.13), a way in
# 0.24 to 0.26 (least 0.16), each count varying 2.7 to 13.7 times a binomial's: at the draw floor of one in
# five, 110 examples, `refused` would fail a run of the first part with 1.2e-3 at `ci`'s size (least 0.1335,
# 13.3 times), and `over_an_operating_range` with 9e-5 at `deep`'s. At these chances, floors of 35 and 60, a
# run of a part fails with at most 2.3e-7 (by the cluster model at each feature's least share and variance;
# 3.1e-7 and 5.9e-7 a floor by the audits' own model).
OUTCOME_CHANCE = 0.11
WAY_CHANCE = 0.14


@pytest.mark.chances(
    **dict.fromkeys(OUTCOMES, OUTCOME_CHANCE), **dict.fromkeys(KEPT_OR_SET_ASIDE, WAY_CHANCE)
)
@given(strategies.table_alternatives(SIZE, KEPT_OR_SET_ASIDE))
def test_a_table_alternative_kept_or_set_aside_by_its_range_is_read_as_the_text_says(
    drawn: TableAlternatives,
) -> None:
    feature(drawn.others)
    feature(drawn.way)
    check_table_alternative(drawn)


@pytest.mark.chances(**dict.fromkeys(OUTCOMES, OUTCOME_CHANCE), **dict.fromkeys(REFUSES, WAY_CHANCE))
@given(strategies.table_alternatives(SIZE, REFUSES))
def test_a_table_alternative_at_an_edge_or_with_no_operating_value_is_read_as_the_text_says(
    drawn: TableAlternatives,
) -> None:
    feature(drawn.others)
    feature(drawn.way)
    check_table_alternative(drawn)


@given(strategies.table_alternatives(SIZE, (INSIDE,)))
def test_moving_a_table_alternatives_range_off_the_operating_value_sets_it_aside(
    drawn: TableAlternatives,
) -> None:
    check_narrowed(drawn)
