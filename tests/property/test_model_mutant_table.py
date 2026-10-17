# SPDX-License-Identifier: Apache-2.0
"""HP12's mutant table (`test_model_mutants.py`) read whole, in a module apart from its searches, so that it
runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from tests.property import model_strategies as strategies
from tests.property.condition_strategies import FAULTS
from tests.property.result_strategies import REVIEWS
from tests.property.test_model_mutants import IMPLEMENTATION, KILLERS, MODEL, NOT_SHOWN
from tests.property.value_field_strategies import CATALOGUE
from tests.reference.mutants import MUTANTS as MODEL_FAULTS

SHOWN = {
    *strategies.KINDS,
    *strategies.VALUED_WAYS,
    *strategies.ALTERNATIVE_WAYS,
    *strategies.EARLY_WAYS,
    *strategies.PLANTS,
    *strategies.REQUEST_FAULTS,
    *(f"step_{step}" for step in strategies.STEPS),
    *(f"{region}.{name}" for region, faults in CATALOGUE.items() for name in faults),
    *FAULTS,
    *REVIEWS,
    "negative_zero",
    "unknown_member",
    "another_section",
    "form_constant",
    "form_interval",
    "form_composition",
}


def test_each_mutant_names_a_killer_and_what_its_kill_must_show() -> None:
    searches = [(mutant.name, mutant.killer, mutant.dies_at, mutant.among) for mutant in IMPLEMENTATION]
    searches += [(fault.name, fault.killer, fault.dies_at, fault.among) for fault in MODEL]
    for name, killer, dies_at, among in searches:
        assert killer in KILLERS, name
        assert dies_at, name
        assert set(dies_at) <= SHOWN, name
        assert set(among) <= SHOWN, name
    for table in (IMPLEMENTATION, MODEL):
        assert len({mutant.name for mutant in table}) == len(table)


def test_every_fault_of_the_model_no_case_kills_is_killed_here_or_said_why_it_cannot_be() -> None:
    searched = {fault.name for fault in MODEL}
    assert searched <= MODEL_FAULTS.keys()
    assert NOT_SHOWN.keys() <= MODEL_FAULTS.keys()
    assert not searched & NOT_SHOWN.keys()
    survivors = {name for name, fault in MODEL_FAULTS.items() if fault.survives is not None}
    assert survivors <= searched | NOT_SHOWN.keys(), survivors - searched - NOT_SHOWN.keys()
    assert all(reason.strip() for reason in NOT_SHOWN.values())
