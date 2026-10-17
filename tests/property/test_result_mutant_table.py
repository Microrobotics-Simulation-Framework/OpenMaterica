# SPDX-License-Identifier: Apache-2.0
"""The result's mutant table (`test_result_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.result_strategies import KINDS, REVIEWS
from tests.property.test_result_mutants import KILLERS, MUTANTS


def test_each_mutant_names_a_killer_and_what_it_must_show_where_killed() -> None:
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    shown = {*KINDS, *REVIEWS, "negative_zero", "unknown_member", "statistics_withheld"}
    assert all(mutant.dies_at and set(mutant.dies_at) <= shown for mutant in MUTANTS)
