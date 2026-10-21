# SPDX-License-Identifier: Apache-2.0
"""The table form through steps 8 and 9 (`record_format.md` section 6, table items 1, 2, 4 and 5;
`read_side_contract.md` section 3, steps 8 and 9): the S3 design's HP13 to HP16, over reads that
`table_form_strategies.py` draws. A read of a table that steps 8 and 9 pass goes on to steps 10 to 13: its
outcome is then "past step 9", whatever they give. The mutants they kill are in `test_table_form_mutants.py`.

- HP13: one fault of a catalogue written from the text gives exactly the reasons its rule gives, and a near
  miss the text allows gives none; the base passes steps 8 and 9; and the fault changes nothing of the read of
  another field of the record, in the same section as a density. Four parts, a property each.
- HP14: a member added to a table, more than one slip from every member named there, changes nothing; one
  slip from one refuses the field (`form_invalid`).
- HP15: an `axis_unit` other than its axis condition's registered unit, code point for code point, gives
  `unit_mismatch` with the axis as `condition`, as HP8 holds a field's and a condition's.
- HP16: the row's label on a table is refused (`form_invalid`) exactly where the table's axis is the
  condition its Label cell names.
"""

import copy
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.property import table_form_strategies as strategies
from tests.property.condition_strategies import OTHER_UNITS
from tests.property.support import feature
from tests.property.table_form_strategies import (
    CATALOGUE,
    FORM_INVALID,
    KINDS,
    ON_ITS_ROWS_AXIS,
    PAST_STEP_9,
    REGIONS,
    TABLE_FIELDS,
    Added,
    Faulty,
    Labelled,
    OtherAxisUnit,
    Outcome,
    Read,
    neighbour,
    outcome,
    table_of,
)
from tests.property.tables import LARGEST, Table
from tests.property.value_fields import NUMERIC_CONDITIONS, listing

# HP13.


def check_one_fault(faulty: Faulty) -> None:
    """The fault first, then its base, so that a reader that refuses some bases and gives a fault the wrong
    reasons is reported at the fault wherever an example draws it; then the neighbour."""
    found = outcome(faulty.read.record, faulty.read.field)
    assert found == faulty.expected, f"the fault {faulty.fault}: {found}, not {faulty.expected}"
    assert outcome(faulty.base.record, faulty.base.field) == Outcome(PAST_STEP_9), (
        f"the base: {outcome(faulty.base.record, faulty.base.field)}"
    )
    assert neighbour(faulty.read.record) == neighbour(faulty.base.record), (
        f"the neighbour, beside the fault {faulty.fault}: {neighbour(faulty.read.record)}"
    )


# The regions of HP13's planned searches, each declared by its chance, below the share measured: the axis
# condition held as a value, two ways of four of one fault in seven, showed in 0.0876 of the examples on
# average over 18 runs of 2,000 at `ci`, 0.055 at least (110, against the floor of 10 that 0.07 gives).
REGION_CHANCES = {"tokens": {"axis_condition_held_as_a_value": 0.07}}


@pytest.mark.parametrize(
    "part",
    [
        pytest.param(
            part,
            marks=[pytest.mark.drawn(*faults), pytest.mark.chances(**REGION_CHANCES.get(part, {}))],
        )
        for part, faults in CATALOGUE.items()
    ],
)
@given(data=st.data())
def test_one_table_fault_gives_the_reasons_its_rule_gives(part: str, data: st.DataObject) -> None:
    faulty = data.draw(strategies.faulty_reads(part))
    feature(faulty.fault)
    for region, shows in REGIONS.get(part, {}).items():
        feature(region, shows(faulty))
    check_one_fault(faulty)


# HP13's fault `source_range_disjoint` where no finite double lies beyond either end of `x`, which holds the
# least double and the largest, so that the fault lowers the run of knots at `x`'s top by one double first
# (`top_lowered`). Before it did, the fault refused to build each but the second: `main`'s `deep` run of
# 2026-10-21 drew the last. The second, its run at the bottom, holds that the run lowered is the top's.
SECOND_LARGEST = math.nextafter(LARGEST, -math.inf)


def upward(start: float, count: int) -> tuple[float, ...]:
    """`count` adjacent doubles, from `start` up."""
    found = [start]
    while len(found) < count:
        found.append(math.nextafter(found[-1], math.inf))
    return tuple(found)


NO_DOUBLE_BEYOND: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    "the_least_and_the_two_largest": ((-LARGEST, SECOND_LARGEST, LARGEST), ()),
    "the_two_least_and_the_largest": ((-LARGEST, -SECOND_LARGEST, LARGEST), ()),
    "both_ends_beside_knots": ((-LARGEST, -SECOND_LARGEST, SECOND_LARGEST, LARGEST), ()),
    "an_edge_beside_the_largest": ((-LARGEST, SECOND_LARGEST, SECOND_LARGEST, LARGEST), (SECOND_LARGEST,)),
    "the_deep_runs": ((*upward(-LARGEST, 12), 0.0, SECOND_LARGEST, LARGEST), ()),
}


@pytest.mark.parametrize(
    ("x", "edges"), [pytest.param(*corner, id=name) for name, corner in NO_DOUBLE_BEYOND.items()]
)
def test_a_source_range_past_x_is_built_where_no_double_lies_beyond_either_end(
    x: tuple[float, ...], edges: tuple[float, ...]
) -> None:
    """The fault reads as HP13 holds it, its `source_range` lies past `x`'s range, and its table without
    that `source_range` passes steps 8 and 9, each value of `y` at its knot: the knots it lowered leave a
    table step 8 accepts, so that the refusal is the `source_range`'s."""
    y = tuple(float(index) for index in range(len(x)))
    base = strategies.read_of(Table(x, y, "linear", edges, None), TABLE_FIELDS[0], NUMERIC_CONDITIONS[0])
    read = Read(copy.deepcopy(base.record), base.field)
    table = table_of(read)
    strategies.source_range_past_x(table)
    check_one_fault(Faulty("source_range_disjoint", base, read, Outcome("not_met", FORM_INVALID)))
    knots = [float(str(value)) for value in listing(table["x"])]
    low, high = (float(str(value)) for value in listing(table.pop("source_range")))
    assert knots[-1] < low <= high or low <= high < knots[0], f"{[low, high]} beside x {knots}"
    assert listing(table["y"]) == list(y), f"y moved: {table['y']}"
    assert outcome(read.record, read.field) == Outcome(PAST_STEP_9), (
        f"x {knots}, edges {table['edges']}: {outcome(read.record, read.field)}"
    )


# HP14.


def check_added(added: Added) -> None:
    found = outcome(added.read.record, added.read.field)
    assert found == added.expected, f"the member {added.member!r} ({added.kind}): {found}"


@pytest.mark.drawn(*KINDS)
@given(strategies.added_members())
def test_a_member_one_slip_from_a_tables_refuses_and_any_other_is_ignored(added: Added) -> None:
    feature(added.kind)
    check_added(added)


# HP15.


def check_other_axis_unit(drawn: OtherAxisUnit) -> None:
    expected = Outcome("not_met", frozenset({("unit_mismatch", drawn.axis)}))
    found = outcome(drawn.read.record, drawn.read.field)
    assert found == expected, f"the axis unit {drawn.kind}: {found}"


@pytest.mark.drawn(*OTHER_UNITS)
@given(strategies.other_axis_units())
def test_any_other_axis_unit_gives_unit_mismatch_with_the_axis(drawn: OtherAxisUnit) -> None:
    """Code point for code point (`record_format.md` section 4.2, "The same holds for a table's
    `axis_unit`"): a unit equal under NFKC or case folding, or but for a space, is another unit, and so is a
    status object where a string is registered."""
    feature(drawn.kind)
    check_other_axis_unit(drawn)


# HP16.


def check_label(labelled: Labelled) -> None:
    found = outcome(labelled.read.record, labelled.read.field)
    assert found == labelled.expected, f"the label {labelled.way}: {found}"


@pytest.mark.drawn(*ON_ITS_ROWS_AXIS)
@given(strategies.labelled_tables())
def test_a_rows_label_is_refused_exactly_on_a_table_over_its_axis(labelled: Labelled) -> None:
    feature(labelled.way)
    check_label(labelled)
