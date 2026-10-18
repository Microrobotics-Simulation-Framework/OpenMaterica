# SPDX-License-Identifier: Apache-2.0
"""Steps 9 and 10's mutant table (`test_condition_mutants.py`) read whole, and its planned search held
against the core, in a module apart from the searches, so that it runs on every Python
(`--property-controls` in `tests/conftest.py`)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import EXAMPLES
from tests.property import test_condition_properties as properties
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


def test_a_kill_at_an_example_with_a_long_repr_is_counted() -> None:
    """Hypothesis warns where the repr of the example it reports is long (30 kB), which the tests' warning
    filter makes an error: a search must count its kill, not fail on the report."""

    def refused(example: str) -> None:
        raise AssertionError(len(example))

    assert kill(st.just("x" * 40_000), refused)[0] == 1
