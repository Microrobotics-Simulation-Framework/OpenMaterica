# SPDX-License-Identifier: Apache-2.0
"""HP12's mutants (`test_model_properties.py`): faults the agreement with the reference model must find, each
within the examples the `ci` profile gives a property, at both sizes, at an example that shows one of the
kinds, ways, steps or planted rules it names, recording the examples its kill took as `examples_to_kill`.

Two sets:
- **faults of the implementation**: a step that stops at its first fault, at each of steps 0, 8, 9 and 10 (the
  S2 design's HP12 mutant, killed on two faults of one step, B5); the design's mutants of HP1 to HP11 that a
  read's result can show, taken from the mutant modules of their properties; and a broken status object
  that reports its token, the fault HP12 found (`provenance.md:51-53`).
- **faults of the model**: the seeded faults of `tests/reference/mutants.py` that no case file kills, or that
  one case file alone kills, each applied to the model while the implementation stays as it is. Those no read
  S2 builds can show are listed in `test_model_mutant_table.py` with their reasons.
"""

import dataclasses
from collections.abc import Callable, Collection
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import canonical, conditions, fields, read, value_shapes
from materica.core.conditions import ConditionsRead
from materica.core.value_shapes import Found, JsonObject
from materica.core.vocabulary import STATUS_TOKENS
from tests.property import model_strategies as strategies
from tests.property import test_condition_mutants as condition_mutants
from tests.property import test_invariance_mutants as invariance_mutants
from tests.property import test_model_properties as properties
from tests.property import test_result_mutants as result_mutants
from tests.property import test_value_field_mutants as value_field_mutants
from tests.property.model_strategies import Example
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting
from tests.reference.mutants import MUTANTS as MODEL_FAULTS

# A search stops at the first example that kills its mutant, which Hypothesis then writes out; those of these
# properties can pass 30 kB, which Hypothesis warns of, and which nobody reads.
pytestmark = pytest.mark.filterwarnings(
    "ignore:Generating overly large repr:hypothesis.errors.HypothesisWarning"
)


def shown(example: Example) -> set[str]:
    return {example.kind, *example.planted}


# Each part of HP12 that kills a mutant, by name: its examples at a size.
KILLERS: dict[str, Callable[[Size], st.SearchStrategy[Example]]] = {
    "values": lambda size: strategies.drawn(size, properties.PARTS["valued"]),
    # A planned search of the first part: constants at section 5's boundaries alone.
    "values at a boundary": lambda size: strategies.valued(size, ("at_a_boundary",)),
    "faults": lambda size: strategies.drawn(size, properties.PARTS["faults"]),
    "two of one step": strategies.two_faults_of_one_step,
    "early": lambda size: strategies.drawn(size, properties.PARTS["early"]),
    "unpinned": strategies.unpinned,
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # kinds, ways, steps or planted rules, one of which the kill must show
    among: tuple[str, ...] = ()  # step 8's faults a planned search draws first, as HP3's do


def searched(killer: str, among: tuple[str, ...], size: Size) -> st.SearchStrategy[Example]:
    """The examples of `killer`, or, for a planned search, records whose first fault of step 8's catalogue is
    one of `among` (`value_field_strategies.faulty_records`)."""
    return strategies.step_8_faults(size, among) if among else KILLERS[killer](size)


# A step that stops at its first fault (the S2 design's HP12 mutant).

FROM_JSON = read.ReadRequest.from_json
FORM_PROBLEMS = fields.form_problems
UNIT_PROBLEMS = fields.unit_problems
CHECK_CONDITIONS = conditions.check_conditions


def _step_0_first_fault(cls: type[read.ReadRequest], request: Any, claims: Any = read.CLAIMS) -> Any:
    checked = FROM_JSON(request, claims)
    return checked[:1] if isinstance(checked, tuple) else checked


def _step_8_first_fault(*arguments: Any) -> Found:
    return FORM_PROBLEMS(*arguments)[:1]


def _step_9_first_fault(*arguments: Any) -> Found:
    return UNIT_PROBLEMS(*arguments)[:1]


def _step_10_first_fault(*arguments: Any, **members: Any) -> ConditionsRead:
    found: ConditionsRead = CHECK_CONDITIONS(*arguments, **members)
    return dataclasses.replace(found, reasons=found.reasons[:1])


# A broken status object that reports its token, the fault HP12 found.

STATUS_OBJECT = value_shapes.status_object


def _broken_status_reports_its_token(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    before = len(found)
    STATUS_OBJECT(value, where, tokens, defines, found)
    broken = any(reason.code == "form_invalid" for reason in found[before:])
    status = value["status"]
    if broken and tokens is not None and isinstance(status, str) and status not in STATUS_TOKENS:
        found.append(value_shapes.unknown_token(f"{where} holds the status {status!r}"))


# The recomputed hash taken over the members in the order the source writes them, not in RFC 8785's (the S2
# design's HP10 mutant, B7: the hash taken over the source's form, not the canonical one).


def _as_written(name: str) -> bytes:
    return b""


# The design's mutants of HP1 to HP11, from the mutant modules of their properties.


def taken(module_mutants: list[Any], name: str) -> Callable[[pytest.MonkeyPatch], None]:
    (found,) = [mutant for mutant in module_mutants if mutant.name == name]
    inject: Callable[[pytest.MonkeyPatch], None] = found.inject
    return inject


IMPLEMENTATION = [
    Mutant(
        "step_0_stops_at_its_first_fault",
        "two of one step",
        setting(read.ReadRequest, "from_json", classmethod(_step_0_first_fault)),
        ("step_0",),
    ),
    Mutant(
        "step_8_stops_at_its_first_fault",
        "two of one step",
        setting(read, "form_problems", _step_8_first_fault),
        ("step_8",),
    ),
    Mutant(
        "step_9_stops_at_its_first_fault",
        "two of one step",
        setting(read, "unit_problems", _step_9_first_fault),
        ("step_9",),
    ),
    Mutant(
        "step_10_stops_at_its_first_fault",
        "two of one step",
        setting(read, "check_conditions", _step_10_first_fault),
        ("step_10",),
    ),
    Mutant(
        "broken_status_object_reports_its_token",
        "unpinned",
        setting(value_shapes, "status_object", _broken_status_reports_its_token),
        ("broken_status_object",),
    ),
    # HP1
    Mutant(
        "condition_unchecked_without_its_condition",
        "faults",
        taken(result_mutants.MUTANTS, "condition_unchecked_without_its_condition"),
        ("unchecked",),
    ),
    # HP2
    Mutant(
        "value_beside_condition_outside",
        "faults",
        taken(result_mutants.MUTANTS, "value_beside_condition_outside"),
        ("outside", "range_outside", "not_accepted", "implied_outside"),
    ),
    # HP3
    Mutant(
        "unknown_tokens_ignored",
        "faults",
        taken(value_field_mutants.MUTANTS, "unknown_tokens_ignored"),
        ("step_8",),
    ),
    Mutant(
        "missing_represents_accepted",
        "faults",
        taken(value_field_mutants.MUTANTS, "missing_represents_accepted"),
        ("statistics_members.represents_missing",),
        ("statistics_members.represents_missing",),
    ),
    Mutant(
        "null_read_as_absent",
        "faults",
        taken(value_field_mutants.MUTANTS, "null_read_as_absent"),
        ("condition_tokens.set_or_measured_null", "provenance.source_null"),
        ("condition_tokens.set_or_measured_null", "provenance.source_null"),
    ),
    Mutant(
        "unknown_condition_names_checked",
        "faults",
        taken(value_field_mutants.MUTANTS, "unknown_condition_names_checked"),
        ("step_8", "steps_9_and_10"),
    ),
    # HP5 (an unknown member returned) and HP6
    Mutant(
        "unknown_members_returned",
        "values",
        taken(result_mutants.MUTANTS, "unknown_members_returned"),
        ("unknown_member",),
    ),
    Mutant(
        "expanded_uncertainty_divided_by_its_k",
        "values",
        taken(result_mutants.MUTANTS, "expanded_uncertainty_divided_by_its_k"),
        ("valued", "alternatives"),
    ),
    # HP7
    Mutant(
        "floating_point_as_written",
        "values at a boundary",
        taken(condition_mutants.MUTANTS, "floating_point_as_written"),
        ("at_a_boundary",),
    ),
    Mutant(
        "strict_inequalities",
        "values",
        taken(condition_mutants.MUTANTS, "strict_inequalities"),
        ("valued", "alternatives"),
    ),
    Mutant(
        "plus_minus_ignored",
        "values at a boundary",
        taken(condition_mutants.MUTANTS, "plus_minus_ignored"),
        ("at_a_boundary",),
    ),
    Mutant(
        "plus_minus_makes_not_met",
        "values at a boundary",
        taken(condition_mutants.MUTANTS, "plus_minus_makes_not_met"),
        ("at_a_boundary",),
    ),
    # HP8
    Mutant(
        "nfkc_before_comparing",
        "faults",
        taken(condition_mutants.MUTANTS, "nfkc_before_comparing"),
        ("steps_9_and_10",),
    ),
    Mutant("case_folded", "faults", taken(condition_mutants.MUTANTS, "case_folded"), ("steps_9_and_10",)),
    # HP9
    Mutant(
        "section_facts_win",
        "values",
        taken(condition_mutants.MUTANTS, "section_facts_win"),
        ("valued", "alternatives"),
    ),
    # HP4
    Mutant(
        "specimen_facts_merged_across_sections",
        "values",
        taken(invariance_mutants.MUTANTS, "specimen_facts_merged_across_sections"),
        ("another_section",),
    ),
    # HP10
    Mutant(
        "hash_over_members_as_written",
        "values",
        setting(canonical, "_utf16_units", _as_written),
        ("valued", "alternatives"),
    ),
    # HP11
    Mutant(
        "labelled_before_step_4",
        "early",
        taken(result_mutants.MUTANTS, "labelled_before_step_4"),
        ("before_step_4", "stores"),
    ),
]


# Faults of the model, applied while the implementation stays as it is.


class ModelFault(NamedTuple):
    name: str  # a key of `tests/reference/mutants.MUTANTS`
    killer: str
    dies_at: tuple[str, ...]
    among: tuple[str, ...] = ()


MODEL = [
    # No case file kills these (phase 0's survivors, and those seeded in phase B).
    ModelFault("plurals_not_slips", "unpinned", ("plural_of_two_characters",)),
    ModelFault("member_checked_off_its_row", "unpinned", ("form_off_its_row",)),
    ModelFault("composition_checked_beyond_its_basis", "unpinned", ("composition_basis_off_its_row",)),
    ModelFault("broken_status_object_reports_its_token", "unpinned", ("broken_status_object",)),
    ModelFault("members_of_the_other_kind_read", "unpinned", ("members_of_the_other_kind",)),
    ModelFault("members_of_the_other_kind_ignored", "unpinned", ("members_of_the_other_kind",)),
    ModelFault("slips_of_alternatives_ignored", "unpinned", ("alternatives_slip_beside",)),
    ModelFault(
        "declaration_names_not_named_in_a_request", "unpinned", ("names_a_declaration_gives_a_requirement",)
    ),
    ModelFault(
        "population_level_checks_stop_at_a_missing_member", "unpinned", ("checks_beside_a_broken_object",)
    ),
    ModelFault("dof_token_unchecked_under_student_t", "unpinned", ("checks_beside_a_broken_object",)),
    ModelFault("every_status_object_an_unstated_kind", "unpinned", ("checks_beside_a_broken_object",)),
    ModelFault(
        "input_specimens_optional",
        "faults",
        ("derivation.input_specimens_missing",),
        ("derivation.input_specimens_missing",),
    ),
    # One case file alone kills these.
    ModelFault("hash_not_checked_before_step_4", "early", ("request", "before_step_4", "stores")),
    ModelFault("token_condition_unit_accepted", "faults", ("unit_token_condition",)),
    ModelFault("plus_minus_units_unchecked", "faults", ("unit_plus_minus",)),
    ModelFault("implied_values_compared_by_value", "unpinned", ("implied_zero_beside_minus_zero",)),
    ModelFault("stated_without_origin_unreported", "values", ("valued", "alternatives")),
]


def agreement(example: Example) -> None:
    properties.check_agreement(example)


# The model's faults that no read S2 builds can show, each with its reason: phase 0's survivors, and those one
# case file alone kills, beside the others above.
EVIDENCE = "an evidence entry is read by S2b-2: the implementation raises at it"
NOMINALS = "the implementation raises for any acceptance but an implied condition until S2b-2 reads nominals"
NOT_SHOWN: dict[str, str] = {
    "evidence_entry_provenance_unchecked": EVIDENCE,
    "entry_withheld_in_part_read": EVIDENCE,
    "unit_returned_without_its_reason": (
        "only `biocompatibility.evidence` registers a unit held as a status object, and evidence waits for "
        "S2b-2"
    ),
    "two_nominals_for_one_field": NOMINALS,
    "nominal_ignored_over_alternatives": NOMINALS,
    "nominal_applied_under_no_pick": NOMINALS,
    "results_share_the_record": (
        "a result that shares the record's objects reads as JSON as one that does not; HP6 holds the "
        "implementation to sharing nothing"
    ),
}


SIZES = [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("mutant", IMPLEMENTATION, ids=[mutant.name for mutant in IMPLEMENTATION])
def test_the_implementations_mutant_is_killed_by_the_agreement(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    mutant.inject(monkeypatch)
    tried, example = kill(searched(mutant.killer, mutant.among, size), agreement)
    record_property("examples_to_kill", tried)
    assert shown(example) & set(mutant.dies_at), shown(example)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("fault", MODEL, ids=[fault.name for fault in MODEL])
def test_the_models_seeded_mutant_is_killed_by_the_agreement(
    fault: ModelFault, size: Size, record_property: Callable[[str, object], None]
) -> None:
    with MODEL_FAULTS[fault.name].applied():
        tried, example = kill(searched(fault.killer, fault.among, size), agreement)
    record_property("examples_to_kill", tried)
    assert shown(example) & set(fault.dies_at), shown(example)
