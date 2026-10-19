# SPDX-License-Identifier: Apache-2.0
"""S4a's mutant table (`test_alternatives_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

import pytest
from hypothesis import given, settings

from tests.conftest import EXAMPLES
from tests.property.alternatives_strategies import OUTCOMES
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MARGIN
from tests.property.test_alternatives_mutants import KILLERS, MUTANTS


def test_each_mutant_names_a_killer_its_outcomes_and_its_assertion() -> None:
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    assert {mutant.killer for mutant in MUTANTS} == set(KILLERS)
    assert all(mutant.dies_at and set(mutant.dies_at) <= set(OUTCOMES) for mutant in MUTANTS)
    assert all(mutant.says.strip() for mutant in MUTANTS)


# A planned search draws the region where its fault shows, so it must draw only reads the core passes: a
# mutant it kills then dies of its fault and not of an example the core fails too. Each is held to HP27's
# check (the oracle written from the text) on the core as it is, for the examples a search can draw before its
# kill, which the margin guard holds to the first `MARGIN` (a run of 2,000 of each passed on 2026-10-20).
PLANNED = [name for name in KILLERS if name.startswith("HP27 ") and name != "HP27"]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("name", PLANNED)
def test_a_planned_search_draws_only_reads_the_core_passes(name: str, size: Size) -> None:
    examples, check = KILLERS[name]

    @settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], MARGIN), deadline=None)
    @given(examples(size))
    def run(example: object) -> None:
        check(example)

    run()


def test_every_planned_search_is_named() -> None:
    assert len(PLANNED) == 5, PLANNED
    assert {mutant.killer for mutant in MUTANTS if mutant.killer.startswith("HP27 ")} <= {*PLANNED, "HP27"}
