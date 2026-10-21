# SPDX-License-Identifier: Apache-2.0
"""S3b-2's mutant table (`test_table_read_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.table_read_strategies import EDGE_WAYS, RANGE_WAYS, REQUEST_WAYS, STATISTICS_WAYS
from tests.property.test_model_mutants import IMPLEMENTATION, TABLE_PARTS
from tests.property.test_table_read_mutants import KILLERS, MUTANTS

# What each property's examples draw first, which a mutant's `dies_at` names.
DRAWN = {
    "HP20": EDGE_WAYS,
    "HP21": RANGE_WAYS,
    "HP21 no wider and tolerance": RANGE_WAYS[:4],
    "HP22": STATISTICS_WAYS,
    "HP23": REQUEST_WAYS,
    "monotonicity": RANGE_WAYS[:4],
    "monotonicity, one double outside": ("one_double_outside",),
}


def test_each_mutant_names_a_killer_the_ways_that_show_it_and_its_assertion() -> None:
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    assert set(DRAWN) == set(KILLERS)
    assert all(mutant.killer in KILLERS for mutant in MUTANTS)
    assert all(mutant.dies_at and set(mutant.dies_at) <= set(DRAWN[mutant.killer]) for mutant in MUTANTS)
    assert all(mutant.says.strip() for mutant in MUTANTS)


def test_every_property_kills_a_mutant() -> None:
    """HP20 to HP23, HP21's relation and the monotonicity property, broad and planned, each kill one at least:
    none is a check no fault fails."""
    assert {mutant.killer for mutant in MUTANTS} == set(KILLERS)


def test_hp12_searches_every_mutant_of_a_tables_steps_10_to_13() -> None:
    """The S3 design's HP12, widened: the agreement with the reference model kills each mutant above too, each
    in the table part's kind of the family whose property kills it."""
    searched = {
        mutant.name: mutant.killer for mutant in IMPLEMENTATION if mutant.killer in TABLE_PARTS.values()
    }
    assert searched == {mutant.name: TABLE_PARTS[mutant.killer] for mutant in MUTANTS}
    assert set(TABLE_PARTS) == set(KILLERS)
