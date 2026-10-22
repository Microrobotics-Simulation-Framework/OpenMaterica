# SPDX-License-Identifier: Apache-2.0
"""S4d's mutant table (`test_table_alternatives_mutants.py`) read whole, in a module apart from its searches,
so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.table_alternatives_strategies import INSIDE, KEPT_OR_SET_ASIDE, REFUSES
from tests.property.test_table_alternatives_mutants import KILLERS, MUTANTS

# What each property's examples draw as the table's way, which a mutant's `dies_at` names.
DRAWN = {"HP39 kept or set aside": KEPT_OR_SET_ASIDE, "HP39 refuses": REFUSES, "HP40": (INSIDE,)}


def test_each_mutant_names_a_killer_the_ways_that_show_it_and_its_assertion() -> None:
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    assert set(DRAWN) == set(KILLERS)
    assert all(mutant.killer in KILLERS for mutant in MUTANTS)
    assert all(mutant.dies_at and set(mutant.dies_at) <= set(DRAWN[mutant.killer]) for mutant in MUTANTS)
    assert all(mutant.says.strip() for mutant in MUTANTS)


def test_every_property_kills_a_mutant() -> None:
    """HP39's two parts and HP40 each kill one at least: none is a check no fault fails."""
    assert {mutant.killer for mutant in MUTANTS} == set(KILLERS)


# The S4 design's mutants of HP39 and HP40 (its section 6.6), each by the row that stands for it here.
DESIGN: dict[str, dict[str, tuple[str, ...]]] = {
    "HP39": {
        "an edge setting aside": ("an_edge_sets_aside",),
        "an edge outside a narrowed range setting aside": ("an_edge_outside_the_range_sets_aside",),
        "`outside_range` set aside under a covering extrapolation": (
            "set_aside_under_a_covering_extrapolation",
        ),
        "kept without one": ("kept_without_an_extrapolation",),
        "kept under `want: bounds`": ("kept_under_any_want",),
        "step 11's `request_incomplete` setting aside, or tagged": (
            "request_fault_at_step_11_sets_aside",
            "request_fault_at_step_11_tagged",
        ),
        "an over-range table set aside, or counted as giving": (
            "over_a_range_sets_aside",
            "over_a_range_gives",
        ),
        "a kept table's entry holding the end value or an `assumption`": ("kept_entry_its_read",),
        "the extrapolation applied under `no_pick`": ("extrapolation_applied_under_no_pick",),
        "an over-range entry without step 12's labels": ("over_a_range_entry_without_step_12_labels",),
        "a kept table's step-12 `unknown` dropped beside `no_pick`": (
            "kept_unknown_dropped_beside_two_or_more",
        ),
    },
    "HP40": {
        "`outside_range` refusing": ("outside_range_refuses",),
        "the narrowed alternative kept": ("narrowed_alternative_kept",),
        "its reasons beside the one left": ("set_aside_by_its_range_beside_the_one_left",),
    },
}


def test_every_mutant_the_design_names_has_its_row() -> None:
    names = {mutant.name for mutant in MUTANTS}
    rows = [row for property_rows in DESIGN.values() for given in property_rows.values() for row in given]
    assert set(rows) <= names, sorted(set(rows) - names)
