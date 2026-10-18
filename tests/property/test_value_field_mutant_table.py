# SPDX-License-Identifier: Apache-2.0
"""Step 8's mutant table (`test_value_field_mutants.py`) read whole, in a module apart from its searches, so
that it runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from hypothesis import strategies as st

from tests.property import value_field_strategies as strategies
from tests.property.test_value_field_mutants import KILLERS, MUTANTS, kill


def test_each_mutant_names_faults_of_the_catalogue() -> None:
    """A fault renamed in the catalogue would leave a mutant no fault to die at."""
    faults = {f"{region}.{name}" for region, faults_of in strategies.CATALOGUE.items() for name in faults_of}
    for mutant in MUTANTS:
        assert set(mutant.dies_at) <= faults, mutant.name
        assert mutant.killer in KILLERS, mutant.name


def test_a_kill_at_an_example_with_a_long_repr_is_counted() -> None:
    """As steps 9 and 10's search (`test_condition_mutant_table.py`)."""

    def refused(example: str) -> None:
        raise AssertionError(len(example))

    assert kill(st.just("x" * 40_000), refused)[0] == 1
