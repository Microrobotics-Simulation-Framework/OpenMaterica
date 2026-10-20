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
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason, merged
from materica.core.value_shapes import Found, JsonObject, a_list, an_object
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
    # A planned search of the first part: constants under `want: bounds`, as drawn or with an implied
    # temperature, every one of which the read meets and so asks of its form (not at a boundary, where a
    # constant may lie outside its tolerance and end the read at step 10). Until 2026-10-19 it drew `valued`
    # whole, which S2b-1 and S2b-2 had made draw every form, so a constant under `bounds` came up in one draw
    # in 35 (a constant in two in five, `bounds` in one `want` in 14).
    "constants": lambda size: strategies.valued(size, ("as_drawn", "implied"), constant_under_bounds=True),
    # A planned search of the first part: an interval under `want: bounds`, with no nominal, every one of
    # which the read gives its bounds for, `upper: none` among them. Drawn whole, `upper_none_as_infinity`
    # died at the 503rd example at the small size once S4a's alternatives joined the part's draws.
    "an interval under bounds": lambda size: strategies.valued(size, interval_under_bounds=True),
    # A planned search of the second part: a condition the request gives no tolerance for, which step 10
    # gives as `condition_unchecked` (HP1's mutant drops its condition there).
    "an unchecked condition": lambda size: strategies.step_9_or_10_faults(size, ("unchecked",)),
    # A planned search of the first part: constants at section 5's boundaries alone.
    "values at a boundary": lambda size: strategies.valued(size, ("at_a_boundary",)),
    # Planned searches of the first part: an interval's read under a nominal, alone and over alternatives.
    "values under a nominal": lambda size: strategies.valued(size, nominal=True),
    "alternatives under a nominal": lambda size: strategies.alternatives(size, nominal=True),
    # A planned search of the first part: evidence whose unit is a status object with a reason.
    "evidence's unit with a reason": lambda size: strategies.valued(size, unit_with_a_reason=True),
    "faults": lambda size: strategies.drawn(size, properties.PARTS["faults"]),
    "two of one step": strategies.two_faults_of_one_step,
    "early": lambda size: strategies.drawn(size, properties.PARTS["early"]),
    # A planned search of the third part: step 0's catalogue, the first fault a nominal's.
    "nominals at step 0": lambda size: strategies.request_faults(size, strategies.NOMINAL_REQUEST_FAULTS),
    "unpinned": strategies.unpinned,
    # A planned search of the first part: S4a's alternatives alone, each of step 7's outcomes drawn first; and
    # three narrower, as `test_alternatives_mutants.py` plans HP27's: a refusal by a fault of the request, an
    # interval under a nominal, and evidence whose first alternative an implied condition sets aside.
    "outcomes of step 7": strategies.outcomes_of_step_7,
    "a refusal by a fault of the request": lambda size: strategies.outcomes_of_step_7(
        size, ("refused",), refusing_ways=("request_fault",)
    ),
    "an interval under a nominal": lambda size: strategies.outcomes_of_step_7(
        size, ("refused", "one_left", "no_pick"), forms=("interval",), under_a_nominal=True
    ),
    "evidence set aside first": lambda size: strategies.outcomes_of_step_7(
        size, ("no_pick",), forms=("evidence",), set_aside_first=True
    ),
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


# Open point 1's request half read as the implementation read it before the fix round.


def _declaration_names_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    setting(read, "_REQUIREMENT_MEMBERS", ("want", "conditions", "label", "represents", "population_level"))(
        monkeypatch
    )
    setting(read, "_REQUIREMENT_CONDITION_MEMBERS", ("tolerance", "accept"))(monkeypatch)


# The recomputed hash taken over the members in the order the source writes them, not in RFC 8785's (the S2
# design's HP10 mutant, B7: the hash taken over the source's form, not the canonical one).


def _as_written(name: str) -> bytes:
    return b""


# Step 7 over alternatives, step 13 for a constant, and step 0 on a text that is no JSON, each of which a
# variety of HP12's draws must show (S2a-4's review B, L1 and L2).

READ_ALTERNATIVES = read._read_alternatives  # pyright: ignore[reportPrivateUsage]
READ_VALUE_FIELD = read.read_value_field
BY_WANT = read._by_want  # pyright: ignore[reportPrivateUsage]
COUNTED_MEMBER = read._counted_member  # pyright: ignore[reportPrivateUsage]
PARSED = read._parsed  # pyright: ignore[reportPrivateUsage]


def _request_faults_of_the_first_alternative(
    field: RecordField,
    record: JsonObject,
    request: read.ReadRequest,
    claims: Any,
    labels: tuple[str, ...],
    nominal: read.Nominal | None,
) -> read.ReadResult:
    """Where a fault of the request inside the alternatives refuses the field, only the first faulted
    alternative's reasons given."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if result.status != "not_met" or any(reason.code != "request_incomplete" for reason in result.reasons):
        return result
    for alternative in a_list(an_object(field.value)["alternatives"]):
        one = READ_VALUE_FIELD(RecordField(field.spec, alternative, field.section), record, request, claims)
        if one.request_fault:
            return read.ReadResult("not_met", merged(one.reasons), labels)
    return result


def _first_alternative_in_every_entry(*arguments: Any) -> read.ReadResult:
    result: read.ReadResult = READ_ALTERNATIVES(*arguments)
    entries = result.alternative_values
    if entries is None:
        return result
    return dataclasses.replace(result, alternative_values=entries[:1] * len(entries))


def _bounds_given_by_a_constant(field: JsonObject, name: str, form: str, want: Any) -> Reason | None:
    return BY_WANT(field, name, form, "value" if want == "bounds" and form == "constant" else want)


def _minus_zero_given_as_zero(member: JsonValue) -> JsonValue:
    returned = COUNTED_MEMBER(member)
    return abs(returned) if isinstance(returned, float) and returned == 0.0 else returned


def _every_constant_not_built(field: JsonObject, name: str, form: str, want: Any) -> Reason | None:
    if form == "constant":
        raise NotImplementedError("the member of a field of form constant is not read yet")
    return BY_WANT(field, name, form, want)


def _text_that_is_no_json_raises(request: Any) -> JsonValue | Reason:
    value: JsonValue | Reason = PARSED(request)
    if isinstance(value, Reason):
        raise ValueError(f"the request is not JSON: {value.detail}")
    return value


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
    # Open point 1's request half, as the implementation read it before the fix round: a slip of a name a
    # declaration gives a requirement ignored, and an implied value's member of the other kind ignored.
    Mutant(
        "declaration_names_ignored",
        "unpinned",
        _declaration_names_ignored,
        ("names_a_declaration_gives_a_requirement",),
    ),
    Mutant(
        "implied_members_of_the_other_kind_ignored",
        "unpinned",
        setting(read, "_OF_THE_OTHER_KIND", {"numeric": (), "token": ()}),
        ("implied_member_of_the_other_kind",),
    ),
    # HP1. Drawn with the faults' part whole it died at a passing fault of step 8, which goes on to step 10,
    # where the step-8 kind's request leaves every condition unchecked, or at `unchecked`; over 24 seeds it
    # took up to 811 examples (2026-10-19), so its search is planned.
    Mutant(
        "condition_unchecked_without_its_condition",
        "an unchecked condition",
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
        ("condition_tokens.name_unknown",),
        ("condition_tokens.name_unknown",),
    ),
    # S2b-1's HP3: an interval's and a composition's own member.
    Mutant(
        "interval_order_unchecked",
        "faults",
        taken(value_field_mutants.MUTANTS, "interval_order_unchecked"),
        ("interval.lower_above_upper",),
        ("interval.lower_above_upper",),
    ),
    Mutant(
        "component_twice_allowed",
        "faults",
        taken(value_field_mutants.MUTANTS, "component_twice_allowed"),
        ("composition.component_repeated",),
        ("composition.component_repeated",),
    ),
    Mutant(
        "element_by_pattern",
        "faults",
        taken(value_field_mutants.MUTANTS, "element_by_pattern"),
        ("component.element_unknown",),
        ("component.element_unknown",),
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
    Mutant(
        "upper_none_as_infinity",
        "an interval under bounds",
        taken(result_mutants.MUTANTS, "upper_none_as_infinity"),
        ("form_interval",),
    ),
    Mutant(
        "components_normalised",
        "values",
        taken(result_mutants.MUTANTS, "components_normalised"),
        ("form_composition",),
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
    # Step 7 over alternatives: each alternative's faults of the request, and each entry's own read.
    Mutant(
        "request_faults_of_the_first_alternative_alone",
        "values",
        setting(read, "_read_alternatives", _request_faults_of_the_first_alternative),
        ("request_faults_apart",),
    ),
    Mutant(
        "first_alternative_in_every_entry",
        "values",
        setting(read, "_read_alternatives", _first_alternative_in_every_entry),
        ("alternatives",),
    ),
    # Step 13 for a constant: each `want`, a value's `-0`, and a constant read as S2 builds it.
    Mutant(
        "bounds_given_by_a_constant",
        "constants",
        setting(read, "_by_want", _bounds_given_by_a_constant),
        ("valued",),
    ),
    Mutant(
        "minus_zero_given_as_zero",
        "values",
        setting(read, "_counted_member", _minus_zero_given_as_zero),
        ("negative_zero",),
    ),
    Mutant(
        "every_constant_not_built",
        "values",
        setting(read, "_by_want", _every_constant_not_built),
        ("valued", "alternatives"),
    ),
    # Step 0 on a text that is no JSON, which refuses rather than raise.
    Mutant(
        "text_that_is_no_json_raises",
        "early",
        setting(read, "_parsed", _text_that_is_no_json_raises),
        ("not_json",),
    ),
]


# Faults of the model, applied while the implementation stays as it is.


# Step 8's faults of evidence that the model's evidence faults must die at, each searched among them.
EVIDENCE_PROVENANCE = (
    "evidence_provenance.origin_unknown",
    "evidence_provenance.origin_missing",
    "evidence_provenance.source_key_not_a_string",
    "evidence_provenance.source_missing_for_its_origin",
    "evidence_provenance.derivation_missing",
    "evidence_provenance.not_an_object",
)
WITHHELD_IN_PART = ("evidence_list.report_withheld_in_part", "evidence_list.withheld_report_opened")


class ModelFault(NamedTuple):
    name: str  # a key of `tests/reference/mutants.MUTANTS`
    killer: str
    dies_at: tuple[str, ...]
    among: tuple[str, ...] = ()


MODEL = [
    # No case file kills these (phase 0's survivors, and those seeded in phase B), but
    # `member_checked_off_its_row`, which two of PR #37's review's cases came to kill: HP12 still searches it.
    ModelFault("plurals_not_slips", "unpinned", ("plural_of_two_characters",)),
    ModelFault("member_checked_off_its_row", "unpinned", ("form_off_its_row",)),
    ModelFault("composition_checked_beyond_its_basis", "unpinned", ("composition_basis_off_its_row",)),
    ModelFault("broken_status_object_reports_its_token", "unpinned", ("broken_status_object",)),
    ModelFault("slips_of_alternatives_ignored", "unpinned", ("alternatives_slip_beside",)),
    ModelFault(
        "declaration_names_not_named_in_a_request", "unpinned", ("names_a_declaration_gives_a_requirement",)
    ),
    ModelFault(
        "population_level_checks_stop_at_a_missing_member", "unpinned", ("checks_beside_a_broken_object",)
    ),
    ModelFault("dof_token_unchecked_under_student_t", "unpinned", ("checks_beside_a_broken_object",)),
    ModelFault("every_status_object_an_unstated_kind", "unpinned", ("checks_beside_a_broken_object",)),
    ModelFault("every_forms_member_named_at_a_field", "unpinned", ("another_forms_member_slipped",)),
    ModelFault("ies_not_a_plural", "unpinned", ("plural_of_two_characters",)),
    ModelFault("review_of_both_shapes_read_as_its_status", "unpinned", ("review_of_both_shapes",)),
    ModelFault("reviewed_review_keeps_a_status_objects_members", "unpinned", ("review_of_both_shapes",)),
    ModelFault(
        "donor_age_of_neither_accepted",
        "faults",
        ("specimen.fact_neither_value_nor_range",),
        ("specimen.fact_neither_value_nor_range",),
    ),
    ModelFault(
        "input_specimens_optional",
        "faults",
        ("derivation.input_specimens_missing",),
        ("derivation.input_specimens_missing",),
    ),
    # Open point 1, read as the implementation read its record half until the maintainer's ruling of
    # 2026-10-19: the two cases of the token ruling (2026-10-18) kill these by the implied half, which each
    # breaks too, and the two of the record half's ruling by that half.
    ModelFault(
        "members_of_the_other_kind_read",
        "unpinned",
        ("members_of_the_other_kind", "implied_member_of_the_other_kind"),
    ),
    ModelFault(
        "members_of_the_other_kind_ignored",
        "unpinned",
        ("members_of_the_other_kind", "implied_member_of_the_other_kind"),
    ),
    # One case file alone kills these.
    ModelFault("hash_not_checked_before_step_4", "early", ("request", "before_step_4", "stores")),
    ModelFault("token_condition_unit_accepted", "faults", ("unit_token_condition",)),
    ModelFault("plus_minus_units_unchecked", "faults", ("unit_plus_minus",)),
    ModelFault("implied_values_compared_by_value", "unpinned", ("implied_zero_beside_minus_zero",)),
    ModelFault("stated_without_origin_unreported", "values", ("valued", "alternatives")),
    # Case files kill these; HP12 holds the model to them on the forms S2b-1 reads.
    ModelFault("value_given_by_an_interval", "values", ("form_interval",)),
    ModelFault("bounds_given_by_a_constant", "values", ("form_constant",)),
    # S2b-2's evidence and nominals, which HP12 draws since S2b-2 reads them.
    ModelFault("evidence_entry_provenance_unchecked", "faults", EVIDENCE_PROVENANCE, EVIDENCE_PROVENANCE),
    ModelFault("entry_withheld_in_part_read", "faults", WITHHELD_IN_PART, WITHHELD_IN_PART),
    ModelFault("unit_returned_without_its_reason", "evidence's unit with a reason", ("unit_with_a_reason",)),
    ModelFault("two_nominals_for_one_field", "nominals at step 0", ("two_nominals_for_one_field",)),
    ModelFault(
        "nominal_ignored_over_alternatives", "alternatives under a nominal", ("nominal_over_alternatives",)
    ),
    ModelFault(
        "nominal_applied_under_no_pick", "alternatives under a nominal", ("nominal_over_alternatives",)
    ),
    ModelFault("nominal_outside_supplies_the_value", "values under a nominal", ("nominal_outside",)),
    # S4a's step 7, the five of its faults one case file alone kills.
    ModelFault("request_fault_sets_aside", "a refusal by a fault of the request", ("refused",)),
    ModelFault("nominal_not_applied_to_the_one_left", "an interval under a nominal", ("one_left",)),
    ModelFault("unknown_reasons_dropped_beside_no_pick", "outcomes of step 7", ("want_mismatch", "no_pick")),
    ModelFault("set_aside_reasons_beside_no_pick", "outcomes of step 7", ("want_mismatch", "no_pick")),
    ModelFault("unit_of_the_first_stored_alternative", "evidence set aside first", ("no_pick",)),
]


def agreement(example: Example) -> None:
    properties.check_agreement(example)


# The model's faults that no read S2 builds can show, each with its reason: phase 0's survivors, and those one
# case file alone kills, beside the others above.
NOT_SHOWN: dict[str, str] = {
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
