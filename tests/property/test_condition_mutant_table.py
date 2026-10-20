# SPDX-License-Identifier: Apache-2.0
"""Steps 9 and 10's mutant table (`test_condition_mutants.py`) read whole, and its planned search held
against the core, in a module apart from the searches, so that it runs on every Python
(`--property-controls` in `tests/conftest.py`)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import EXAMPLES
from tests.property import test_condition_properties as properties
from tests.property.support import fails
from tests.property.test_condition_mutants import KILLERS, MUTANTS, kill, table_cases_without_a_requirement


def test_each_mutant_names_a_killer() -> None:
    assert {mutant.killer for mutant in MUTANTS} <= set(KILLERS)
    assert len({mutant.name for mutant in MUTANTS}) == len(MUTANTS)


# This checks the mutants' own code, not the core's: a planned search draws only cases the core passes, so
# that a mutant it kills dies of its fault.
@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(table_cases_without_a_requirement())
def test_a_requirement_held_nowhere_is_checked_by_the_core(drawn: tuple[str, properties.Case]) -> None:
    properties.check_against_the_oracle(drawn[1])


# The region HP7's table holds to a floor is where the planned search's mutant shows: over the property's own
# draws, a case holds a required condition nowhere exactly where `row_requirements_ignored` fails the oracle.
@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(properties.table_cases())
def test_a_requirement_held_nowhere_is_where_its_mutant_shows(drawn: tuple[str, properties.Case]) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        next(mutant for mutant in MUTANTS if mutant.name == "row_requirements_ignored").inject(monkeypatch)
        killed = fails(properties.check_against_the_oracle, drawn[1])
    assert bool(properties.held_nowhere(drawn[1])) == killed, drawn


def test_a_kill_at_an_example_with_a_long_repr_is_counted() -> None:
    """Hypothesis warns where the repr of the example it reports is long (30 kB), which the tests' warning
    filter makes an error: a search must count its kill, not fail on the report."""

    def refused(example: str) -> None:
        raise AssertionError(len(example))

    assert kill(st.just("x" * 40_000), refused)[0] == 1
