# SPDX-License-Identifier: Apache-2.0
"""The result's mutant table (`test_result_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

import pytest
from hypothesis import given, settings

from tests.conftest import EXAMPLES
from tests.property import test_result_properties as properties
from tests.property.result_strategies import KINDS, NOMINAL_WAYS, REVIEWS, Drawn, drawn_reads
from tests.property.strategies import SIZE
from tests.property.support import fails
from tests.property.test_result_mutants import KILLERS, MUTANTS
from tests.property.value_field_strategies import READ_FORMS


def test_each_mutant_names_a_killer_and_what_it_must_show_where_killed() -> None:
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)
    forms = {f"form_{form}" for form in READ_FORMS}
    nominals = {f"nominal_{way}" for way in NOMINAL_WAYS}
    shown = {*KINDS, *REVIEWS, *forms, *nominals, "negative_zero", "unknown_member", "statistics_withheld"}
    assert all(mutant.dies_at and set(mutant.dies_at) <= shown for mutant in MUTANTS)


# The region HP1 holds to a floor is where the planned search's mutant shows: over HP1's own draws, a result
# holds `condition_unchecked` exactly where `condition_unchecked_without_its_condition` fails HP1's check.
UNCHECKED = next(mutant for mutant in MUTANTS if mutant.name == "condition_unchecked_without_its_condition")


@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(drawn_reads(SIZE))
def test_a_result_holding_condition_unchecked_is_where_its_mutant_shows(drawn: Drawn) -> None:
    shown = "condition_unchecked" in properties.codes_given(drawn)
    with pytest.MonkeyPatch.context() as monkeypatch:
        UNCHECKED.inject(monkeypatch)
        killed = fails(properties.check_totality, drawn)
    assert shown == killed, drawn.kind
