# SPDX-License-Identifier: Apache-2.0
"""Steps 9 and 10's mutant table (`test_condition_mutants.py`) read whole, in a module apart from its
searches, so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.test_condition_mutants import KILLERS, MUTANTS


def test_each_mutant_names_a_killer() -> None:
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
