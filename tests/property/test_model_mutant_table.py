# SPDX-License-Identifier: Apache-2.0
"""HP12's mutant table (`test_model_mutants.py`) read whole, in a module apart from its searches, so that it
runs on every Python (`--property-controls` in `tests/conftest.py`)."""

import pytest
from hypothesis import given, settings

from tests.conftest import EXAMPLES
from tests.property import model_strategies as strategies
from tests.property.alternatives_strategies import OUTCOMES
from tests.property.condition_strategies import FAULTS
from tests.property.result_strategies import REVIEWS
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MARGIN
from tests.property.test_model_mutants import IMPLEMENTATION, KILLERS, MODEL, NOT_SHOWN, agreement
from tests.property.value_field_strategies import CATALOGUE
from tests.reference.mutants import MUTANTS as MODEL_FAULTS

SHOWN = {
    *strategies.KINDS,
    *strategies.VALUED_WAYS,
    *strategies.ALTERNATIVE_WAYS,
    *strategies.APART_WAYS,
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
    "not_json",
    "form_constant",
    "form_interval",
    "form_composition",
    "form_evidence",
    "unit_with_a_reason",
    *strategies.NOMINAL_PLANTS,
    *OUTCOMES,
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


# S4a's planned searches of the first part, `upper_none_as_infinity`'s, and those planned when the region
# floors moved their kills (2026-10-20): each draws a region, and must draw only reads the core agrees with
# the model on, so that a mutant it kills dies of its fault.
PLANNED_BY_S4A = (
    "outcomes of step 7",
    "a refusal by a fault of the request",
    "an interval under a nominal",
    "evidence set aside first",
    "an interval under bounds",
    "a plus or minus unit",
    "a composition under components",
    "an unknown member",
    "request faults apart",
    "a token condition's unit",
)


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("name", PLANNED_BY_S4A)
def test_a_planned_search_draws_only_reads_the_core_agrees_with_the_model_on(name: str, size: Size) -> None:
    @settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], MARGIN), deadline=None)
    @given(KILLERS[name](size))
    def run(example: strategies.Example) -> None:
        agreement(example)

    run()


# The planned searches of 2026-10-20 each draw their region in every example, not in some by chance: what the
# draw plants names it.
REGION_OF = {
    "a plus or minus unit": "unit_plus_minus",
    "a token condition's unit": "unit_token_condition",
    "a composition under components": "form_composition",
    "an unknown member": "unknown_member",
    "request faults apart": "request_faults_apart",
}


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("name", sorted(REGION_OF))
def test_a_planned_search_draws_its_region_in_every_example(name: str, size: Size) -> None:
    @settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], MARGIN), deadline=None)
    @given(KILLERS[name](size))
    def run(example: strategies.Example) -> None:
        assert REGION_OF[name] in example.planted, example.planted

    run()
