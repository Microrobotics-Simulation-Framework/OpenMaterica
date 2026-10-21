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

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.property import table_form_strategies as strategies
from tests.property.condition_strategies import OTHER_UNITS
from tests.property.support import feature
from tests.property.table_form_strategies import (
    CATALOGUE,
    KINDS,
    ON_ITS_ROWS_AXIS,
    PAST_STEP_9,
    REGIONS,
    Added,
    Faulty,
    Labelled,
    OtherAxisUnit,
    Outcome,
    neighbour,
    outcome,
)

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
