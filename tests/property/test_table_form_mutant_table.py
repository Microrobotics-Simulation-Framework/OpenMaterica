# SPDX-License-Identifier: Apache-2.0
"""S3a's mutant table (`test_table_form_mutants.py`) read whole, in a module apart from its searches, so that
it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

import pytest
from hypothesis import given, settings

from tests.conftest import EXAMPLES
from tests.property.condition_strategies import OTHER_UNITS
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MARGIN
from tests.property.table_form_strategies import CATALOGUE, KINDS, ON_ITS_ROWS_AXIS
from tests.property.test_table_form_mutants import KILLERS, MUTANTS, ZERO_FAULTS

# What each property's examples draw first, which a mutant's `dies_at` names; a planned search draws its
# faults among those named.
DRAWN = {
    **{f"HP13 {part}": tuple(faults) for part, faults in CATALOGUE.items()},
    "HP13 edges, signed zeros on a base held alike": ZERO_FAULTS,
    "HP13 edges, the zero edge's near miss": ("zero_edge_both_signs",),
    "HP13 tokens, the axis condition held as a value": ("axis_condition_held_otherwise",),
    "HP14": KINDS,
    "HP15": OTHER_UNITS,
    "HP16": ON_ITS_ROWS_AXIS,
}
PLANNED = [name for name in KILLERS if name.startswith("HP13 ") and "," in name]


def test_each_mutant_names_a_killer_the_draws_that_show_it_and_its_assertion() -> None:
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert set(DRAWN) == set(KILLERS)
    assert all(mutant.dies_at and set(mutant.dies_at) <= set(DRAWN[mutant.killer]) for mutant in MUTANTS)
    assert all(mutant.says.strip() for mutant in MUTANTS)


def test_every_property_kills_a_mutant() -> None:
    """HP13's four parts, HP14, HP15 and HP16 each kill one at least, and so does each planned search: none
    is a check no fault fails."""
    assert {mutant.killer for mutant in MUTANTS} == set(KILLERS)


def test_every_planned_search_is_named() -> None:
    assert PLANNED == [
        "HP13 edges, signed zeros on a base held alike",
        "HP13 edges, the zero edge's near miss",
        "HP13 tokens, the axis condition held as a value",
    ]


# A planned search draws the region where its fault shows, so it must draw only reads the core passes: a
# mutant it kills then dies of its fault and not of an example the core fails too. Each is held to its
# property's check on the core as it is, for the examples a search can draw before its kill, which the margin
# guard holds to the first `MARGIN`.
@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("name", PLANNED)
def test_a_planned_search_draws_only_reads_the_core_passes(name: str, size: Size) -> None:
    examples, check, drew = KILLERS[name]

    @settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], MARGIN), deadline=None)
    @given(examples(size))
    def run(example: object) -> None:
        assert drew(example) in DRAWN[name]
        check(example)

    run()
