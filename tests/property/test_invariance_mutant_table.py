# SPDX-License-Identifier: Apache-2.0
"""The mutant table of HP4 and HP10 (`test_invariance_mutants.py`) read whole, in a module apart from its
searches, so that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property.invariance_strategies import ELSEWHERE, REWRITTEN_KINDS
from tests.property.test_invariance_mutants import KILLERS, MUTANTS


def test_each_mutant_names_a_killer_and_what_its_kill_must_show() -> None:
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    shown = {*ELSEWHERE, "own_section_specimen", *REWRITTEN_KINDS}
    for mutant in MUTANTS:
        assert mutant.dies_at, mutant.name
        assert set(mutant.dies_at) <= shown, mutant.name
