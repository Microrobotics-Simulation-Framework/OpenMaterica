# SPDX-License-Identifier: Apache-2.0
"""The monotonicity relations' mutant table (`test_monotonicity_mutants.py`) read whole, in a module apart
from its searches, so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.test_monotonicity_mutants import MUTANTS, TWIN_SEARCHES, TWINS
from tests.property.test_monotonicity_properties import RELATIONS

# The spike's relations that S2's forms reach (the S2a-4 brief, phase B item 3).
REACHED = ("N1r", "N2", "N3r", "N4", "N5r", "N6", "N8", "P1", "P2", "P3", "P4", "S1", "S2", "S5")


def test_each_relation_s2_reaches_is_a_property_with_a_mutant_it_must_kill() -> None:
    assert tuple(RELATIONS) == REACHED
    assert {mutant.relation for mutant in MUTANTS} == set(REACHED)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)


def test_each_unrestricted_twin_is_searched_against_its_restricted_relation() -> None:
    assert set(TWINS) == set(TWIN_SEARCHES) == {"N1", "N3"}
    assert set(TWINS.values()) <= set(RELATIONS)
