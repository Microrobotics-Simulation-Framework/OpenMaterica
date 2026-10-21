# SPDX-License-Identifier: Apache-2.0
"""A request's extrapolation (`declarations.md` section 4.1; `read_side_contract.md` sections 1, 2, 3 and 5):
the S3 design's HP24 to HP26 and its monotonicity property over an extrapolation, over reads that
`extrapolation_strategies.py` draws, each with the way it draws first. The mutants they kill are in
`test_extrapolation_mutants.py`.

- HP24, the extrapolation law: adding one that applies changes a read only outside the readable range under
  `want: value`, at no edge and across none, and then only by the value at the range's nearest end, taken from
  inside it, the members returned beside a value, the table it is read from, step 12's reasons and labels, and
  `assumption`, its `method` and `law` as the request gives them; the status stays `not_met` and the reasons
  of steps up to 11 stand; and `applied` names it. Inside the range, at an edge, beyond one, or under another
  `want`, adding it changes nothing.
- HP25, applicability: one naming another field, record or region, an interval, or no location is checked and
  never applied; two naming one field give `request_incomplete`, wherever each is located, and two naming two
  fields are both read.
- HP26, step 0's shape: `method` one of its tokens and `law` text of at least one character, white space alone
  included, or the request is refused; `basis`, `reason` and a member no document names are ignored; a member
  one slip from a named one is refused.
- Monotonicity: adding an extrapolation never turns `unknown` or `not_met` into `met`.

Each oracle is written from the text: the end value the reference evaluator gives in its `exact` mode
(`tests/reference/table_evaluator.py`) at the readable range's nearest end, rounded once, and the members
HP6's oracle gives a read beside its value (`test_result_properties.expected_members`)."""

import json
from fractions import Fraction

import pytest
from hypothesis import given

from materica.core.read import ReadResult
from tests.property import extrapolation_strategies as strategies
from tests.property.extrapolation_strategies import (
    APPLIED_WAYS,
    ELSEWHERE_WAYS,
    MONOTONE_WAYS,
    NAMED,
    NOT_APPLIED_WAYS,
    READ_SHAPE_WAYS,
    REFUSED_SHAPE_WAYS,
    TWO_WAYS,
    Extrapolated,
    MonotoneWorld,
    read_with,
)
from tests.property.support import feature, same
from tests.property.table_read_strategies import table_field
from tests.property.test_result_properties import expected_members
from tests.property.value_fields import Json as JsonObject
from tests.reference import table_evaluator


def written(result: ReadResult) -> JsonObject:
    """The result as JSON, as a consumer receives it."""
    found: JsonObject = json.loads(json.dumps(result.to_json()))
    return found


def codes(result: ReadResult) -> set[tuple[str, str | None]]:
    return {(reason.code, reason.condition) for reason in result.reasons}


def nearest_end(example: Extrapolated) -> float:
    """The end of the readable range nearest the read (`record_format.md` section 6, table item 3: "from
    `x[0]`, or `source_range[0]` where that is greater, to `x[-1]`, or `source_range[1]` where that is
    smaller")."""
    table, at = example.drawn.table, example.drawn.at
    assert at is not None
    low, high = table.x[0], table.x[-1]
    if table.source_range is not None:
        low, high = max(low, table.source_range[0]), min(high, table.source_range[1])
    return low if at < low else high


def end_value(example: Extrapolated) -> float:
    """The end value, `read_side_contract.md` section 5's "value at the range's nearest end, taken from inside
    the range": the reference evaluator's exact value there, which an end at no edge has from one side
    only."""
    table = example.drawn.table
    evaluated = table_evaluator.evaluate(
        table_evaluator.Table(table.x, table.y, table.scheme, table.edges, table.source_range),
        nearest_end(example),
        "exact",
    )
    assert evaluated.in_range, evaluated
    assert evaluated.value is not None, evaluated
    return evaluated.value if isinstance(evaluated.value, float) else float(Fraction(evaluated.value))


def assumption_of(extrapolation: JsonObject) -> JsonObject:
    """`read_side_contract.md` section 2: "`{"acceptance"}` with its kind's own members as the request gives
    them, `basis` aside"."""
    return {"acceptance": "extrapolation", "method": extrapolation["method"], "law": extrapolation["law"]}


def unchanged(example: Extrapolated, found: ReadResult) -> None:
    """The read under the acceptances is the read without them, member for member, and applies none."""
    plain = read_with(example.drawn, ())
    assert written(found) == written(plain), (
        f"the {example.way} read changed under {example.acceptances}: {written(found)}, not {written(plain)}"
    )
    assert found.applied == (), f"the {example.way} read applied {found.applied}"


# HP24.


def check_applied(example: Extrapolated) -> None:
    drawn, extrapolation = example.drawn, example.extrapolation
    assert extrapolation is not None
    plain = read_with(drawn, ())
    found = read_with(drawn, example.acceptances)
    # "the result stays `not_met`, its reasons kept; the read goes on to steps 12 and 13, which add theirs"
    assert found.status == "not_met", f"the {example.way} read under an extrapolation: {found.status}"
    step_12: set[tuple[str, str | None]] = (
        {("stated_without_origin", None)} if example.way == "stated_without_origin" else set()
    )
    assert codes(found) == codes(plain) | step_12, (
        f"the {example.way} read's reasons under an extrapolation: {codes(found)}"
    )
    assert found.conditions == plain.conditions, f"the {example.way} read's conditions changed"
    # "and the result carries the value at the range's nearest end, taken from inside the range, and
    # `assumption`"
    assert same(end_value(example), found.value), (
        f"the {example.way} read's value {found.value}, not the end value {end_value(example)}"
    )
    assert found.assumption == assumption_of(extrapolation), (
        f"the {example.way} read's assumption {found.assumption}"
    )
    # Section 2 item 6: `unit`, `specimen`, `statistics` and `provenance` "exactly when `value` is", and
    # `table` "exactly when `value` is and is read from a table ... under an extrapolation too".
    result = written(found)
    expected = expected_members(table_field(drawn), {"specimen": {}})
    for name in ("unit", "specimen", "statistics", "provenance"):
        assert same(expected[name], result.get(name)), f"the {example.way} read's {name}: {result.get(name)}"
    assert found.table == table_field(drawn)["table"], f"the {example.way} read's table {found.table}"
    assert found.applied == (0,), f"the {example.way} read applied {found.applied}"


@pytest.mark.drawn(*APPLIED_WAYS)
@given(strategies.applied())
def test_an_extrapolation_that_applies_adds_the_end_value_and_what_rests_on_it(example: Extrapolated) -> None:
    feature(example.way)
    check_applied(example)


def check_not_applied(example: Extrapolated) -> None:
    """Inside the readable range, at an edge, beyond one, or under another `want`: `read_side_contract.md`
    section 5, "Under any other `want` an extrapolation is not applied, nor at a declared edge" and "Nor is an
    extrapolation applied across a declared edge"."""
    unchanged(example, read_with(example.drawn, example.acceptances))


@pytest.mark.drawn(*NOT_APPLIED_WAYS)
@given(strategies.not_applied())
def test_an_extrapolation_changes_no_read_in_the_range_at_or_across_an_edge_or_under_another_want(
    example: Extrapolated,
) -> None:
    feature(example.way)
    check_not_applied(example)


# HP25.


def check_elsewhere(example: Extrapolated) -> None:
    """Section 1: "One naming another field, another record or region, an `interval` ... or no location is
    checked and not applied"."""
    unchanged(example, read_with(example.drawn, example.acceptances))


@pytest.mark.drawn(*ELSEWHERE_WAYS)
@given(strategies.elsewhere())
def test_an_extrapolation_located_elsewhere_is_checked_and_never_applied(example: Extrapolated) -> None:
    feature(example.way)
    check_elsewhere(example)


def check_two(example: Extrapolated) -> None:
    """Section 1: "So do two acceptances of one kind, `nominal`, `extrapolation` or `pick`, that name one
    field, whatever location or other members each holds"; two naming two fields are each read, the one at the
    read applied."""
    found = read_with(example.drawn, example.acceptances)
    if example.way == "each_its_own_field":
        assert example.extrapolation is not None
        alone = read_with(example.drawn, (example.extrapolation,))
        assert written(found) == written(alone), f"two for two fields read as {written(found)}"
        index = example.acceptances.index(example.extrapolation)
        assert found.applied == (index,), f"two for two fields applied {found.applied}, not ({index},)"
        return
    assert (found.status, codes(found)) == ("not_met", {("request_incomplete", None)}), (
        f"two extrapolations naming one field, {example.way}: {found.status}, {codes(found)}"
    )
    assert (found.value, found.conditions, found.applied) == (None, None, ()), (
        f"two extrapolations naming one field, {example.way}, read on"
    )


@pytest.mark.drawn(*TWO_WAYS)
@given(strategies.two())
def test_two_extrapolations_naming_one_field_are_refused_wherever_located(example: Extrapolated) -> None:
    feature(example.way)
    check_two(example)


# HP26.

REFUSED = ("not_met", {("request_incomplete", None)})


def check_refused_shape(example: Extrapolated) -> None:
    """Section 1: "Each is checked here, whatever field or location it names: ... its kind's own members, have
    their shapes"; `declarations.md` section 4.1: "`method` (`constant` or `consumer_law`), `law` (text of at
    least one character, which a reader does not judge)"."""
    found = read_with(example.drawn, example.acceptances)
    assert (found.status, codes(found)) == REFUSED, (
        f"an extrapolation with its {example.way}: {found.status}, {codes(found)}"
    )
    assert (found.value, found.conditions) == (None, None), f"an extrapolation with its {example.way} read on"


@pytest.mark.drawn(*REFUSED_SHAPE_WAYS)
@given(strategies.refused_shapes())
def test_an_extrapolation_whose_method_or_law_breaks_its_shape_is_refused(example: Extrapolated) -> None:
    feature(example.way)
    check_refused_shape(example)


def check_read_shape(example: Extrapolated) -> None:
    """A `law` of white space alone is text of at least one character; `basis` and `reason` are ignored, and
    so is a member no document names (section 1), each read as the extrapolation without them is; a member one
    slip from a named one is refused (section 1: "a member one slip ... from a member this section or
    `declarations.md` names at that place")."""
    extrapolation = example.extrapolation
    assert extrapolation is not None
    found = read_with(example.drawn, example.acceptances)
    if example.way == "a_slip_of_a_member":
        assert (found.status, codes(found)) == REFUSED, (
            f"an extrapolation holding a slip: {found.status}, {codes(found)}"
        )
        return
    named = {name: member for name, member in extrapolation.items() if name in NAMED}
    named.pop("basis", None)
    named.pop("reason", None)
    clean = read_with(example.drawn, (named,))
    assert written(found) == written(clean), (
        f"an extrapolation with its {example.way} read as {written(found)}, not {written(clean)}"
    )
    assert found.assumption == assumption_of(extrapolation), (
        f"an extrapolation with its {example.way}: assumption {found.assumption}"
    )


@pytest.mark.drawn(*READ_SHAPE_WAYS)
@given(strategies.read_shapes())
def test_an_extrapolations_ignored_members_and_white_space_law_are_read_and_a_slip_refused(
    example: Extrapolated,
) -> None:
    feature(example.way)
    check_read_shape(example)


# The S3 design's monotonicity property over an extrapolation (the maintainer's information monotonicity,
# 2026-10-14).


def check_monotone(example: MonotoneWorld) -> None:
    """Adding an extrapolation never turns `unknown` or `not_met` into `met`; and so that the relation is not
    vacuous, a read in the range of a table the request can meet is `met`, or `unknown` stated without origin,
    and one outside it `not_met` both ways, the extrapolation applied there: its value present."""
    world = example.world
    plain = strategies.read_world(world, ())
    found = strategies.read_world(world, (example.extrapolation,))
    if world.way in ("inside", "at_an_end"):
        expected = "unknown" if world.unoriginated else "met"
        assert plain.status == expected, f"a read {world.way} its range, every condition met: {plain.status}"
    else:
        assert plain.status == "not_met", f"a read {world.way} its range: {plain.status}"
        assert found.value is not None, f"an extrapolation applied to no read {world.way} its range"
    if plain.status != "met":
        assert found.status != "met", f"an extrapolation turned a read {plain.status} at {world.way} into met"


@pytest.mark.chances(stated_without_origin=0.2)
@pytest.mark.drawn(*MONOTONE_WAYS)
@given(strategies.monotone_worlds())
def test_an_extrapolation_never_turns_a_read_met(example: MonotoneWorld) -> None:
    feature(example.world.way)
    feature("stated_without_origin", example.world.unoriginated)
    check_monotone(example)
