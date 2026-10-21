# SPDX-License-Identifier: Apache-2.0
"""S3c's mutant table (`test_extrapolation_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.extrapolation_strategies import (
    APPLIED_WAYS,
    ELSEWHERE_WAYS,
    MONOTONE_WAYS,
    NOT_APPLIED_WAYS,
    READ_SHAPE_WAYS,
    REFUSED_SHAPE_WAYS,
    TWO_WAYS,
)
from tests.property.test_extrapolation_mutants import KILLERS, MUTANTS

# What each property's examples draw first, which a mutant's `dies_at` names.
DRAWN = {
    "HP24": APPLIED_WAYS,
    "HP24 not applied": NOT_APPLIED_WAYS,
    "HP24 not applied, across an edge": ("across_an_edge",),
    "HP25": ELSEWHERE_WAYS,
    "HP25 two": TWO_WAYS,
    "HP26 refused": REFUSED_SHAPE_WAYS,
    "HP26 read": READ_SHAPE_WAYS,
    "monotonicity": MONOTONE_WAYS,
}


def test_each_mutant_names_a_killer_the_ways_that_show_it_and_its_assertion() -> None:
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    assert set(DRAWN) == set(KILLERS)
    assert all(mutant.killer in KILLERS for mutant in MUTANTS)
    assert all(mutant.dies_at and set(mutant.dies_at) <= set(DRAWN[mutant.killer]) for mutant in MUTANTS)
    assert all(mutant.says.strip() for mutant in MUTANTS)


def test_every_property_kills_a_mutant() -> None:
    """HP24 to HP26 and the monotonicity property, broad and planned, each kill one at least: none is a check
    no fault fails."""
    assert {mutant.killer for mutant in MUTANTS} == set(KILLERS)


# The S3 design's mutants (sections 6.7 and 6.8, v1's table and its additions), each by the row that stands
# for it here.
DESIGN: dict[str, dict[str, tuple[str, ...]]] = {
    "HP24": {
        "status `unknown` or `met`": (
            "status_met_under_an_extrapolation",
            "status_unknown_under_an_extrapolation",
        ),
        "the value extrapolated linearly": ("extrapolated_linearly",),
        "the far end's value": ("the_far_ends_value",),
        "steps 12 and 13 skipped": ("steps_12_and_13_skipped",),
        "applied under `want: bounds`": ("applied_under_want_bounds",),
        "applied at an edge": ("an_edge_read_under_an_extrapolation",),
        "`basis` in `assumption`": ("basis_in_the_assumption",),
        "the end value taken at `x[0]` where `source_range` narrows the range": (
            "end_value_at_x_where_source_range_narrows",
        ),
        "applied at an edge outside the readable range": ("applied_at_an_edge_outside_the_readable_range",),
    },
    "HP25": {
        "the location ignored": ("the_location_ignored",),
        "the second silently applied": ("two_read_the_second_applied",),
    },
    "HP26": {
        "`law` optional under `constant`": ("law_optional_under_constant",),
        "`basis` checked": ("basis_checked",),
        "an empty `law` accepted": ("an_empty_law_accepted",),
        "a `law` of white space refused": ("a_law_of_white_space_refused",),
    },
    "monotonicity": {"status set to `met`": ("monotone_status_met",)},
}


def test_every_mutant_the_design_names_has_its_row() -> None:
    names = {mutant.name for mutant in MUTANTS}
    rows = [row for property_rows in DESIGN.values() for given in property_rows.values() for row in given]
    assert set(rows) <= names, sorted(set(rows) - names)
