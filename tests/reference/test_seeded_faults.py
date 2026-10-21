# SPDX-License-Identifier: Apache-2.0
"""The power of the case-agreement check: each seeded fault of the reference model (`mutants.py`) gives some
case file of a read an outcome the list of exceptions does not (a disagreement, a no verdict no kind lists, or
an agreement with a listed file), or is listed as a survivor with the reason no case can kill it. A survivor
the cases come to kill, and a killed fault that comes to survive, both fail, so that the table in `README.md`
stays true. A fault that makes the model raise on a case file fails its check with the model's traceback: a
crash shows that the fault broke the model, not that a case's expected answer tells the fault apart, so it is
never counted as a kill."""

from typing import NoReturn

import pytest

from tests.reference.cases import case_files, first_disagreement, outcome
from tests.reference.mutants import MUTANTS, Mutant


def check(name: str, mutant: Mutant) -> None:
    """The cases kill the fault, or it is listed as a survivor."""
    with mutant.applied():
        found = first_disagreement()
    if mutant.survives is None:
        assert found is not None, f"{name} ({mutant.fault}) gives every case file its listed outcome"
    else:
        assert found is None, f"{name} is listed as a survivor ({mutant.survives}), but {found}"


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_the_cases_kill_the_fault_or_it_is_listed_as_a_survivor(name: str) -> None:
    check(name, MUTANTS[name])


def test_the_table_holds_at_least_thirty_faults_and_says_why_each_survivor_survives() -> None:
    assert len(MUTANTS) >= 30
    assert all(mutant.survives is None or mutant.survives.strip() for mutant in MUTANTS.values())
    assert all(mutant.fault.strip() and mutant.rule.strip() for mutant in MUTANTS.values())


def test_a_fault_leaves_the_model_as_it_was_once_its_search_is_done() -> None:
    (case_file,) = [found for found in case_files() if found.path.name == "PR-035.linear_label_returned.json"]
    with MUTANTS["step_12_labels_dropped"].applied():
        assert outcome(case_file).kind == "differs"
    assert outcome(case_file).kind == "agrees"


def broken_model(kind: type[Exception]) -> Mutant:
    """A fault that breaks the model rather than a rule of the text: `status_object`, which nearly every read
    reaches, replaced by a function raising `kind`."""

    def raising(*args: object, **kwargs: object) -> NoReturn:
        raise kind("the model broken, not a rule of the text")

    return Mutant("the model raises wherever it reads a status object", "none", {"status_object": raising})


# The control: `TypeError`, and the `KeyError` and `AssertionError` that seeded faults once made the model
# raise. A check that counted the raise as a kill, of every kind or of one, would pass on it.
@pytest.mark.parametrize("kind", [TypeError, KeyError, AssertionError])
def test_a_fault_that_makes_the_model_raise_fails_its_check_and_leaves_the_model_as_it_was(
    kind: type[Exception],
) -> None:
    with pytest.raises(kind, match="the model broken") as raised:
        check("broken_model", broken_model(kind))
    notes = getattr(raised.value, "__notes__", [])
    assert any(note.startswith("the model raised reading PR-") for note in notes), notes
    (case_file,) = [found for found in case_files() if found.path.name == "PR-035.linear_label_returned.json"]
    assert outcome(case_file).kind == "agrees"
