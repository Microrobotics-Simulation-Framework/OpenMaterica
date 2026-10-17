# SPDX-License-Identifier: Apache-2.0
"""Seeded faults of the reference model, each one rule of the text broken, run against every case file
(`test_seeded_faults.py`). A fault the cases kill is a rule they pin; one that survives is a rule no case
pins, which the properties of S2a-4's phase B must kill. The table, with what each one's search found, is
`README.md`'s.

Each fault replaces one or two of the model's module-level names, which the model looks up when it runs."""

import dataclasses
import math
from collections.abc import Generator, Iterable, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from fractions import Fraction
from unittest import mock

from tests.reference import read_model as model
from tests.reference.read_model import (
    ConditionRow,
    FieldRead,
    FieldRow,
    ImpliedCondition,
    Reason,
    Reasons,
    Reference,
    Request,
    Source,
    Status,
    StatusObject,
)
from tests.reference.strict_json import JsonObject, JsonValue, NotStrictJson


@dataclass(frozen=True)
class Mutant:
    fault: str
    rule: str  # where the text states the rule the fault breaks
    patches: Mapping[str, object]
    survives: str | None = None  # why no case file kills it, for one none does

    @contextmanager
    def applied(self) -> Generator[None, None, None]:
        with ExitStack() as stack:
            for name, replacement in self.patches.items():
                stack.enter_context(mock.patch.object(model, name, replacement))
            yield


# The model's own functions, taken before any fault replaces them.
_check_value_field = model.check_value_field
_checked_acceptances = model.checked_acceptances
_checked_requirement = model.checked_requirement
_check_composition = model.check_composition
_check_fact = model.check_fact
_check_input_specimens = model.check_input_specimens
_check_population_level = model.check_population_level
_check_plus_minus = model.check_plus_minus
_check_uncertainty = model.check_uncertainty
_check_label = model.check_label
_check_provenance = model.check_provenance
_check_units = model.check_units
_condition_entry = model.condition_entry
_conditions_checked = model.conditions_checked
_read_alternatives = model.read_alternatives
_read_decided = model.read_decided
_read_value_field = model.read_value_field
_resolve = model.resolve
_review_read = model.review_read
_same_unit = model.same_unit
_plural_of_either = model._plural_of_either  # pyright: ignore[reportPrivateUsage]
_shape_by_want = model.shape_by_want
_sources_read = model.sources_read
_status_object = model.status_object
_unit_returned = model.unit_returned
_within_tolerance = model.within_tolerance


class EveryString:
    def __contains__(self, item: object) -> bool:
        return isinstance(item, str)


class EveryPair:
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = None  # type: ignore[assignment]


def no_request_unit_compared(unit: JsonValue, row: ConditionRow) -> bool:
    return False


def operating_for_every_tolerance(
    request: JsonObject, claims: frozenset[str], reasons: Reasons
) -> tuple[str | None, dict[str, float], dict[str, tuple[str, ...]]]:
    requirement = request.get("requirement")
    conditions = requirement.get("conditions") if isinstance(requirement, dict) else None
    operating = request.get("operating_conditions", {})
    if isinstance(conditions, dict) and isinstance(operating, dict):
        given: JsonObject = {name: {} for name in conditions}
        request = {**request, "operating_conditions": {**given, **operating}}
    return _checked_requirement(request, claims, reasons)


def negative_zero_tolerance_refused(
    request: JsonObject, claims: frozenset[str], reasons: Reasons
) -> tuple[str | None, dict[str, float], dict[str, tuple[str, ...]]]:
    checked = _checked_requirement(request, claims, reasons)
    requirement = request.get("requirement")
    conditions = requirement.get("conditions") if isinstance(requirement, dict) else None
    if not isinstance(conditions, dict):
        return checked
    for name, entry in conditions.items():
        tolerance = entry.get("tolerance") if isinstance(entry, dict) else None
        value = tolerance.get("value") if isinstance(tolerance, dict) else None
        if isinstance(value, float) and value == 0.0 and math.copysign(1.0, value) < 0:
            reasons.add("request_incomplete", name)
    return checked


def no_slip(value: JsonObject, named: Iterable[str]) -> bool:
    return False


def no_plural(word: str, other: str) -> bool:
    return False


def no_record_slip(record: JsonObject) -> bool:
    return False


def no_section_slip(section: JsonObject, section_name: str) -> bool:
    return False


def anywhere(acceptance: JsonObject, reference: Reference | None) -> bool:
    return True


def first_nominal_of_each_field(
    request: JsonObject, field_name: str | None, reference: Reference | None, reasons: Reasons
) -> tuple[tuple[ImpliedCondition, ...], float | None]:
    given = request.get("acceptances")
    if isinstance(given, list):
        kept: list[JsonValue] = []
        named: set[str] = set()
        for acceptance in given:
            field_name_given = acceptance.get("field") if isinstance(acceptance, dict) else None
            if isinstance(acceptance, dict) and acceptance.get("acceptance") == "nominal":
                if isinstance(field_name_given, str) and field_name_given in named:
                    continue
                if isinstance(field_name_given, str):
                    named.add(field_name_given)
            kept.append(acceptance)
        request = {**request, "acceptances": kept}
    return _checked_acceptances(request, field_name, reference, reasons)


def any_field_on_the_pattern(value: JsonValue) -> str | None:
    return value if isinstance(value, str) and model.FIELD_PATTERN.fullmatch(value) else None


def never_unreadable(value: JsonValue | NotStrictJson) -> bool:
    return False


def first_copy_of_each_record(sources: Sequence[bytes]) -> list[Source]:
    kept: list[Source] = []
    seen: set[str] = set()
    for source in _sources_read(sources):
        value = source.value
        if isinstance(value, dict):
            identity = repr([value.get("id"), value.get("version"), value.get("content_hash")])
            if identity in seen:
                continue
            seen.add(identity)
        kept.append(source)
    return kept


def labelled_before_step_4(
    request: JsonValue | NotStrictJson, sources: Sequence[bytes], claims: frozenset[str]
) -> JsonObject:
    answer = _read_decided(request, sources, claims)
    labels = answer["labels"]
    if "hash" not in claims and isinstance(labels, list) and "hash_not_checked" not in labels:
        answer["labels"] = [*labels, "hash_not_checked"]
    return answer


def hash_never_recomputed(
    reference: Reference,
    sources: Sequence[Source],
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
) -> JsonObject | None:
    if "hash" in claims:
        return _resolve(reference, sources, claims - {"hash"}, reasons, [])
    return _resolve(reference, sources, claims, reasons, labels)


def never_broken(field_value: JsonObject) -> bool:
    return False


def want_mismatch_beside_no_pick(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    answer = _read_alternatives(
        field_value, section, request, claims, reasons, labels, record_fault=record_fault
    )
    alternatives = field_value["alternatives"]
    given = model.GIVES.get(request.want, ())
    found = answer["reasons"]
    if "alternative_values" in answer and isinstance(alternatives, list) and isinstance(found, list):
        if any(isinstance(one, dict) and one.get("form") not in given for one in alternatives):
            answer["reasons"] = [*found, {"code": "want_mismatch"}]
            answer["status"] = "not_met"
    return answer


def conditions_kept_under_no_pick(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    answer = _read_alternatives(
        field_value, section, request, claims, reasons, labels, record_fault=record_fault
    )
    entries = answer.get("alternative_values")
    if isinstance(entries, list) and isinstance(entries[0], dict):
        answer["conditions"] = entries[0]["conditions"]
    return answer


def alternatives_counted_from_one(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    answer = _read_alternatives(
        field_value, section, request, claims, reasons, labels, record_fault=record_fault
    )
    entries = answer.get("alternative_values")
    for entry in entries if isinstance(entries, list) else []:
        index = entry.get("alternative") if isinstance(entry, dict) else None
        if isinstance(entry, dict) and isinstance(index, float):
            entry["alternative"] = index + 1
    return answer


def labels_raised_from_alternatives(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    answer = _read_alternatives(
        field_value, section, request, claims, reasons, labels, record_fault=record_fault
    )
    entries, found = answer.get("alternative_values"), answer["labels"]
    if isinstance(entries, list) and isinstance(entries[0], dict) and isinstance(found, list):
        raised = entries[0]["labels"]
        answer["labels"] = [*found, *(raised if isinstance(raised, list) else [])]
    return answer


def nominal_ignored_over_alternatives(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    without = dataclasses.replace(request, nominal=None)
    return _read_alternatives(
        field_value, section, without, claims, reasons, labels, record_fault=record_fault
    )


def nominal_applied_to_every_alternative(
    field_value: JsonValue,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    *,
    record_fault: bool,
    nominal: float | None,
) -> FieldRead:
    applied = nominal if nominal is not None else request.nominal
    read = _read_value_field(
        field_value, section, request, claims, record_fault=record_fault, nominal=applied
    )
    if "assumption" in read.members:
        read.stored = read.members["value"]
    return read


def every_unknown_token_a_shape_fault(
    value: JsonValue, member: str, allowed: Iterable[str], faults: Reasons
) -> None:
    if not isinstance(value, str) or value not in tuple(allowed):
        faults.add("form_invalid")


def status_tokens_unchecked(
    value: JsonValue,
    faults: Reasons,
    *,
    allowed: frozenset[str],
    shape: tuple[str, ...] = (),
    scalar: bool = False,
    unit: bool = False,
) -> StatusObject | None:
    return _status_object(value, faults, allowed=allowed, shape=shape, scalar=scalar, unit=True)


def member_checked_off_its_row(
    field_value: JsonValue,
    section: JsonObject,
    field_name: str,
    claims: frozenset[str],
    *,
    record_fault: bool,
) -> tuple[Reasons, str | None]:
    faults, form = _check_value_field(field_value, section, field_name, claims, record_fault=record_fault)
    row = model.FIELDS[field_name]
    if isinstance(field_value, dict) and form in ("constant", "interval", "composition", "evidence"):
        if form not in row.forms:
            allowing = dataclasses.replace(row, forms=(*row.forms, form), bases=model.COMPOSITION_BASES)
            model.check_form_member(field_value, form, allowing, faults)
    return faults, form


def composition_checked_beyond_its_basis(value: JsonValue, row: FieldRow, faults: Reasons) -> None:
    _check_composition(value, row, faults)
    if isinstance(value, dict) and value.get("basis") in model.COMPOSITION_BASES:
        _check_composition(value, dataclasses.replace(row, bases=model.COMPOSITION_BASES), faults)


def family_suite_ignored(
    field_value: JsonValue,
    section: JsonObject,
    field_name: str,
    claims: frozenset[str],
    *,
    record_fault: bool,
) -> tuple[Reasons, str | None]:
    faults, form = _check_value_field(field_value, section, field_name, claims, record_fault=record_fault)
    return Reasons(reason for reason in faults if reason.code != "family_suite_absent"), form


def withheld_in_part(withheld_members: list[bool], faults: Reasons) -> bool:
    return len(withheld_members) == len(model.EVIDENCE_ENTRY_NAMES) - 1 and all(withheld_members)


def missing_label_refused(field_value: JsonObject, row: FieldRow, faults: Reasons) -> None:
    _check_label(field_value, row, faults)
    if "label" not in field_value:
        faults.add("form_invalid")


def unreadable_review_refused(provenance: JsonValue, faults: Reasons) -> None:
    _check_provenance(provenance, faults)
    if isinstance(provenance, dict):
        read = _review_read(provenance)
        if read == {"status": "not_checked"} and provenance.get("review") != read:
            faults.add("form_invalid")


def without_nulls(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {name: without_nulls(member) for name, member in value.items() if member is not None}
    if isinstance(value, list):
        return [without_nulls(item) for item in value]
    return value


def nulls_read_as_absent(
    field_value: JsonValue,
    section: JsonObject,
    field_name: str,
    claims: frozenset[str],
    *,
    record_fault: bool,
) -> tuple[Reasons, str | None]:
    section_without = without_nulls(section)
    assert isinstance(section_without, dict)
    return _check_value_field(
        without_nulls(field_value), section_without, field_name, claims, record_fault=record_fault
    )


def section_specimen_unchecked(
    field_value: JsonValue,
    section: JsonObject,
    field_name: str,
    claims: frozenset[str],
    *,
    record_fault: bool,
) -> tuple[Reasons, str | None]:
    without = {name: member for name, member in section.items() if name != "specimen"}
    return _check_value_field(field_value, without, field_name, claims, record_fault=record_fault)


def block_unchecked(block: JsonValue, faults: Reasons, *, allowed: frozenset[str]) -> None:
    return None


def unchecked(value: JsonValue, faults: Reasons) -> None:
    return None


def population_level_checks_stop_at_a_missing_member(value: JsonValue, faults: Reasons) -> None:
    if isinstance(value, dict) and not all(name in value for name in model.POPULATION_LEVEL_NAMES):
        if model.status_object(value, faults, allowed=frozenset({"unstated"})) is None:
            faults.add("form_invalid")
        return
    _check_population_level(value, faults)


def dof_token_unchecked_under_student_t(value: JsonValue, faults: Reasons) -> None:
    dof = value.get("dof") if isinstance(value, dict) else None
    if isinstance(value, dict) and value.get("distribution") == "student_t" and isinstance(dof, dict):
        _check_uncertainty({**value, "dof": -1.0}, faults)
        return
    _check_uncertainty(value, faults)


def every_status_object_an_unstated_kind(entries: JsonValue, faults: Reasons) -> None:
    unstated: JsonValue = {"status": "unstated"}
    read_as: JsonValue = entries
    if isinstance(entries, list):
        each: list[JsonValue] = [
            {**entry, "stated_as": unstated}
            if isinstance(entry, dict) and isinstance(entry.get("stated_as"), dict)
            else entry
            for entry in entries
        ]
        read_as = each
    _check_plus_minus(read_as, faults)
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("stated_as"), dict):
            model.status_object(entry["stated_as"], faults, allowed=frozenset({"unstated"}), scalar=True)


def every_forms_member_named(form: str | None) -> tuple[str, ...]:
    return model.FIELD_PLACE_NAMES


def input_specimens_optional(entries: JsonValue, inputs: int, faults: Reasons) -> None:
    if entries is not None:
        _check_input_specimens(entries, inputs, faults)


def condition_unchecked(name: str, condition: JsonValue, faults: Reasons) -> None:
    return None


def case_folded(stored: JsonValue, registered: str | model.StatusUnit) -> bool:
    if isinstance(stored, str) and isinstance(registered, str):
        return stored.casefold() == registered.casefold()
    return _same_unit(stored, registered)


def broken_status_reports_its_token(
    value: JsonValue,
    faults: Reasons,
    *,
    allowed: frozenset[str],
    shape: tuple[str, ...] = (),
    scalar: bool = False,
    unit: bool = False,
) -> StatusObject | None:
    found = _status_object(value, faults, allowed=allowed, shape=shape, scalar=scalar, unit=unit)
    token = value.get("status") if isinstance(value, dict) else None
    if found is not None and found.token is None and not unit and isinstance(token, str):
        if token not in model.STATUS_TOKENS:
            faults.add("unknown_token")
    return found


def holds_no_other_kind(value: JsonObject, members: tuple[str, ...]) -> bool:
    return False


def entry_without_the_other_kind(
    name: str, held: JsonObject, applied: Mapping[str, JsonObject], request: Request, reasons: Reasons
) -> JsonObject:
    """A condition entry whose `record` leaves out the members of the other kind's shape, as members the
    reader does not know at that place."""
    entry = _condition_entry(name, held, applied, request, reasons)
    record = entry.get("record")
    if isinstance(record, dict) and name in model.CONDITIONS and "status" not in record:
        other = ("token",) if model.CONDITIONS[name].shape == "numeric" else model.NUMERIC_CONDITION_ONLY
        entry["record"] = {member: value for member, value in record.items() if member not in other}
    return entry


def entry_provenance_unchecked(provenance: JsonValue, faults: Reasons) -> None:
    return None


def no_specimen_checked(field_value: JsonObject, section: JsonObject) -> list[JsonObject]:
    return []


def token_condition_units_accepted(field_value: JsonObject, section: JsonObject, field_name: str) -> Reasons:
    return Reasons(
        reason
        for reason in _check_units(field_value, section, field_name)
        if reason.condition is None or model.CONDITIONS[reason.condition].shape != "token"
    )


def plus_minus_units_unchecked(field_value: JsonObject, section: JsonObject, field_name: str) -> Reasons:
    conditions = field_value["conditions"]
    if isinstance(conditions, dict):
        stripped: JsonObject = {
            name: {member: given for member, given in condition.items() if member != "plus_minus"}
            if isinstance(condition, dict)
            else condition
            for name, condition in conditions.items()
        }
        field_value = {**field_value, "conditions": stripped}
    return _check_units(field_value, section, field_name)


def float_ends(value: JsonObject) -> tuple[float, float]:
    given = value["value"] if "value" in value else value["range"]
    low, high = given if isinstance(given, list) else (given, given)
    assert isinstance(low, float)
    assert isinstance(high, float)
    return low, high


def in_floating_point(stated: JsonObject, operating: JsonObject, tolerance: float) -> Status:
    low, high = float_ends(stated)
    operating_low, operating_high = float_ends(operating)
    if not (low - tolerance <= operating_low and operating_high <= high + tolerance):
        return "not_met"
    entries = stated.get("plus_minus", [])
    bounds = (
        [entry["value"] for entry in entries if isinstance(entry, dict) and entry.get("stated_as") == "bound"]
        if isinstance(entries, list)
        else []
    )
    if bounds and isinstance(bounds[0], float):
        u = bounds[0]
        return (
            "met"
            if low + u - tolerance <= operating_low and operating_high <= high - u + tolerance
            else "unknown"
        )
    return _within_tolerance(stated, operating, tolerance)


def strict_inequalities(stated: JsonObject, operating: JsonObject, tolerance: float) -> Status:
    low, high = model.ends(stated)
    operating_low, operating_high = model.ends(operating)
    t = Fraction(tolerance)
    if not (low - t < operating_low and operating_high < high + t):
        return "not_met"
    return _within_tolerance(stated, operating, tolerance)


def plus_minus_ignored(stated: JsonObject, operating: JsonObject, tolerance: float) -> Status:
    without = {name: given for name, given in stated.items() if name != "plus_minus"}
    return _within_tolerance(without, operating, tolerance)


def unchecked_read_as_met(
    name: str, held: JsonObject, applied: Mapping[str, JsonObject], request: Request, reasons: Reasons
) -> JsonObject:
    found = Reasons()
    entry = _condition_entry(name, held, applied, request, found)
    if Reason("condition_unchecked", name) in set(found):
        entry["status"] = "met"
    else:
        reasons.extend(found)
    return entry


def operating_omitted(
    name: str, held: JsonObject, applied: Mapping[str, JsonObject], request: Request, reasons: Reasons
) -> JsonObject:
    entry = _condition_entry(name, held, applied, request, reasons)
    entry.pop("operating", None)
    return entry


def fills_anything(condition: JsonValue) -> bool:
    return True


def compared_by_value(one: JsonObject, other: JsonObject) -> bool:
    return one.keys() == other.keys() and all(one[member] == other[member] for member in one)


def always_the_same(one: JsonObject, other: JsonObject) -> bool:
    return True


def registered_names_only(held: JsonObject, applied: Mapping[str, JsonObject], request: Request) -> list[str]:
    return [name for name in _conditions_checked(held, applied, request) if name in model.CONDITIONS]


def origin_unreported(
    field_value: JsonValue,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    *,
    record_fault: bool,
    nominal: float | None,
) -> FieldRead:
    read = _read_value_field(
        field_value, section, request, claims, record_fault=record_fault, nominal=nominal
    )
    read.own = Reasons(reason for reason in read.own if reason.code != "stated_without_origin")
    return read


def no_labels(field_value: JsonObject, provenance: JsonObject) -> list[str]:
    return []


def nominal_outside_supplies_the_value(
    read: FieldRead, field_value: JsonObject, request: Request, nominal: float | None
) -> None:
    _shape_by_want(read, field_value, request, nominal)
    if nominal is not None and Reason("nominal_invalid") in set(read.by_want):
        read.by_want = Reasons([Reason("want_mismatch")])
        read.members["value"] = nominal
        read.members["assumption"] = {"acceptance": "nominal", "value": nominal}


def best(statuses: Iterable[Status]) -> Status:
    found = list(statuses)
    return min(found, key=model.STATUSES_BEST_FIRST.index) if found else "met"


def value_whatever_the_status(status: Status, members: JsonObject) -> bool:
    return "value" in members


def members_read_past_a_refusal(
    field_value: JsonValue,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    *,
    record_fault: bool,
    nominal: float | None,
) -> FieldRead:
    """A field step 10 refuses read on to step 13 all the same, its reasons kept."""
    read = _read_value_field(
        field_value, section, request, claims, record_fault=record_fault, nominal=nominal
    )
    if read.conditions is not None and not read.members:
        unchecked = dataclasses.replace(request, tolerances={}, accepts={})
        read_on = _read_value_field(
            field_value, section, unchecked, claims, record_fault=record_fault, nominal=nominal
        )
        read.members, read.labels = read_on.members, read_on.labels
    return read


def every_member(value: JsonObject, names: Iterable[str]) -> JsonObject:
    return model.copied_object(value)


def review_result_alone(provenance: JsonObject) -> JsonObject:
    read = _review_read(provenance)
    return {"result": read["result"]} if "result" in read else read


def reviewed_with_a_status_objects_members(provenance: JsonObject) -> JsonObject:
    review = provenance.get("review")
    read = _review_read(provenance)
    if isinstance(review, dict) and "result" in read:
        return model.known_members(review, model.REVIEW_NAMES)
    return read


def both_shapes_read_as_the_status_object(provenance: JsonObject) -> JsonObject:
    review = provenance.get("review")
    if (
        isinstance(review, dict)
        and review.get("status") == "not_checked"
        and "result" in review
        and not model.slipped(review, model.REVIEW_NAMES)
    ):
        return model.status_returned(review)
    return _review_read(provenance)


def ies_not_a_plural(word: str, other: str) -> bool:
    ies = any(
        singular.endswith("y") and plural == singular[:-1] + "ies"
        for singular, plural in ((word, other), (other, word))
    )
    return not ies and _plural_of_either(word, other)


def donor_age_of_neither_accepted(name: str, fact: JsonValue, faults: Reasons) -> None:
    if name == "donor_age" and isinstance(fact, dict) and not {"status", "value", "range"} & fact.keys():
        fact = {**fact, "value": 0.0}
    _check_fact(name, fact, faults)


def units_stored_differently_compared(
    field_value: JsonObject,
    section: JsonObject,
    request: Request,
    claims: frozenset[str],
    reasons: Reasons,
    labels: list[str],
    *,
    record_fault: bool,
) -> JsonObject:
    """Step 7 over alternatives, each alternative's unit, once its read passes step 13, taken as the first
    one's: units stored differently go unseen, and `no_pick` stands."""
    first: list[JsonValue] = []

    def read_one(*arguments: object, **members: object) -> FieldRead:
        one: FieldRead = _read_value_field(*arguments, **members)  # type: ignore[arg-type]
        if "unit" in one.members:
            first.append(one.members["unit"])
            one.members["unit"] = first[0]
        return one

    with mock.patch.object(model, "read_value_field", read_one):
        return _read_alternatives(
            field_value, section, request, claims, reasons, labels, record_fault=record_fault
        )


def registered_unit(unit: JsonValue) -> JsonValue:
    if isinstance(unit, dict):
        return {name: given for name, given in unit.items() if name == "status"}
    return _unit_returned(unit)


def field_facts_alone(section: JsonObject, field_value: JsonObject) -> JsonObject:
    specimen = field_value.get("specimen")
    return dict(specimen) if isinstance(specimen, dict) else {}


def shared(value: JsonValue) -> JsonValue:
    return value


NO_REQUIRED_WITH = {
    name: dataclasses.replace(row, required_with=()) for name, row in model.CONDITIONS.items()
}

MUTANTS: Mapping[str, Mutant] = {
    # Step 0
    "want_outside_section_6": Mutant(
        "a `want` that is none of section 6's tokens is read",
        "read_side_contract.md:35",
        {"WANTS": EveryString()},
    ),
    "fits_wants_without_their_suite": Mutant(
        "`fit`, `coverage` and `reference_data` read by a reader without their suite",
        "read_side_contract.md:49-51",
        {"FITS_AND_REFERENCE_DATA_WANTS": ()},
    ),
    "tolerance_without_an_operating_condition": Mutant(
        "a tolerance with no operating condition accepted",
        "read_side_contract.md:43",
        {"checked_requirement": operating_for_every_tolerance},
    ),
    "request_units_not_compared": Mutant(
        "an operating condition's, a tolerance's or an implied value's unit not compared",
        "read_side_contract.md:51-55",
        {"request_unit_differs": no_request_unit_compared},
    ),
    "negative_zero_tolerance_refused": Mutant(
        "a tolerance of `-0` read as below zero",
        "read_side_contract.md:43",
        {"checked_requirement": negative_zero_tolerance_refused},
    ),
    "declaration_members_in_a_requirement_read": Mutant(
        "a requirement holding `label`, `represents` or `population_level` read",
        "read_side_contract.md:37-39",
        {"DECLARATION_ONLY_REQUIREMENT_NAMES": ()},
    ),
    "acceptances_applied_anywhere": Mutant(
        "an acceptance applied at another record, a region, an interval or no location",
        "read_side_contract.md:79-86",
        {"at_the_read": anywhere},
    ),
    "two_nominals_for_one_field": Mutant(
        "two nominals naming one field read as the first",
        "read_side_contract.md:68-69",
        {"checked_acceptances": first_nominal_of_each_field},
    ),
    "unregistered_field_requested": Mutant(
        "a field the reader's version does not register read, and found absent",
        "read_side_contract.md:33-34",
        {"registered_field": any_field_on_the_pattern},
    ),
    # The slip rule, in a request and a record
    "every_slip_ignored": Mutant(
        "a member one slip from a named one ignored, in a request and in a record",
        "record_format.md:568-573",
        {"slipped": no_slip},
    ),
    "plurals_not_slips": Mutant(
        "a word made plural or singular not one slip",
        "record_format.md:582-584",
        {"_plural_of_either": no_plural},
        survives="each plural slip in the cases adds an `s` (`fluids`), and so is one character inserted",
    ),
    "envelope_body_and_section_slips_ignored": Mutant(
        "a slip in the envelope, the body or a section refuses no field",
        "record_format.md:570-572",
        {"record_slips": no_record_slip, "section_slips": no_section_slip},
    ),
    # Steps 1 to 5
    "unreadable_sources_ignored": Mutant(
        "an unreadable source never turns `absent` or `pin_mismatch` into `malformed`",
        "read_side_contract.md:187-196",
        {"unreadable": never_unreadable},
    ),
    "first_of_differing_copies_read": Mutant(
        "of two copies with the pin whose bytes differ, the first read",
        "read_side_contract.md:191-192",
        {"sources_read": first_copy_of_each_record},
    ),
    "hash_not_checked_before_step_4": Mutant(
        "`hash_not_checked` on a result that ends before step 4",
        "read_side_contract.md:206-207",
        {"read_decided": labelled_before_step_4},
    ),
    "hash_never_recomputed": Mutant(
        "a reader claiming HS never recomputes the hash",
        "read_side_contract.md:203-205",
        {"resolve": hash_never_recomputed},
    ),
    "other_minor_versions_read": Mutant(
        "a record of another `MAJOR.MINOR` read",
        "read_side_contract.md:199-200",
        {"READER_MAJOR_MINOR": EveryPair()},
    ),
    # Step 7
    "alternatives_shape_unchecked": Mutant(
        "an `alternatives` that is empty, not a list or beside a value field's members read",
        "record_format.md:322-326",
        {"alternatives_broken": never_broken},
    ),
    "want_mismatch_beside_no_pick": Mutant(
        "`want_mismatch` reported under `no_pick` for an alternative whose form `want` cannot give",
        "read_side_contract.md:278-279",
        {"read_alternatives": want_mismatch_beside_no_pick},
    ),
    "conditions_kept_under_no_pick": Mutant(
        "a `no_pick` result holding `conditions` of its own",
        "read_side_contract.md:163-164",
        {"read_alternatives": conditions_kept_under_no_pick},
    ),
    "alternatives_counted_from_one": Mutant(
        "an `alternative_values` entry's index counted from one",
        "read_side_contract.md:116",
        {"read_alternatives": alternatives_counted_from_one},
    ),
    "labels_raised_from_an_alternative": Mutant(
        "an alternative's labels on the `no_pick` result's own",
        "read_side_contract.md:122",
        {"read_alternatives": labels_raised_from_alternatives},
    ),
    "nominal_ignored_over_alternatives": Mutant(
        "an interval beside other alternatives not counted as a form `want: value` gives under a nominal",
        "read_side_contract.md:271-272",
        {"read_alternatives": nominal_ignored_over_alternatives},
    ),
    "nominal_applied_under_no_pick": Mutant(
        "a nominal applied to an interval alternative under `no_pick`",
        "read_side_contract.md:522-523",
        {"read_value_field": nominal_applied_to_every_alternative},
    ),
    # Step 8
    "unknown_tokens_read_as_shape_faults": Mutant(
        "a token the reader knows for no member of that name gives `form_invalid`",
        "read_side_contract.md:288-290",
        {"known_token": every_unknown_token_a_shape_fault},
    ),
    "status_tokens_unchecked": Mutant(
        "a status object takes any token, in any member",
        "provenance.md:50-51",
        {"status_object": status_tokens_unchecked},
    ),
    "member_checked_off_its_row": Mutant(
        "the member of a form the row does not allow checked as on a row allowing it",
        "read_side_contract.md:292-294",
        {"check_value_field": member_checked_off_its_row},
        survives="each member of a form its row does not allow is well formed in the cases",
    ),
    "composition_checked_beyond_its_basis": Mutant(
        "a composition whose basis the row does not allow checked further",
        "maintainer, 2026-10-15 (OPEN_POINTS: form_not_allowed_by_its_row)",
        {"check_composition": composition_checked_beyond_its_basis},
        survives="each composition whose basis its row does not allow is otherwise well formed in the cases",
    ),
    "family_suite_ignored": Mutant(
        "a parameter set read without the family evaluation suite not `family_suite_absent`",
        "read_side_contract.md:323-324",
        {"check_value_field": family_suite_ignored},
    ),
    "entry_withheld_in_part_read": Mutant(
        "an evidence entry withheld in some members but not every one read",
        "record_format.md:233-235",
        {"withheld_whole": withheld_in_part},
    ),
    "missing_label_refused": Mutant(
        "a field without its row's label refused",
        "record_format.md:190-191",
        {"check_label": missing_label_refused},
    ),
    "unreadable_review_refuses": Mutant(
        "a review the reader cannot read refuses the field",
        "provenance.md:118-124",
        {"check_provenance": unreadable_review_refused},
    ),
    "null_read_as_absent": Mutant(
        "`null` in a member step 8 checks read as the member absent",
        "record_format.md:47-50",
        {"check_value_field": nulls_read_as_absent},
    ),
    "statistics_unchecked": Mutant(
        "a statistics block not checked", "read_side_contract.md:296", {"check_block": block_unchecked}
    ),
    "uncertainties_unchecked": Mutant(
        "a relative or expanded uncertainty not checked",
        "uncertainty.md:44-51",
        {"check_uncertainty": unchecked},
    ),
    "derivation_unchecked": Mutant(
        "a derived value's derivation not checked", "provenance.md:185-189", {"check_derivation": unchecked}
    ),
    "population_level_checks_stop_at_a_missing_member": Mutant(
        "a population level missing a member has its `level` and `within` left unchecked",
        "read_side_contract.md:127-128",
        {"check_population_level": population_level_checks_stop_at_a_missing_member},
        survives="no case holds a population level missing a member beside a token of its own",
    ),
    "dof_token_unchecked_under_student_t": Mutant(
        "a `dof` held as a status object under a Student's t distribution has its token left unchecked",
        "read_side_contract.md:127-128",
        {"check_uncertainty": dof_token_unchecked_under_student_t},
        survives="no case holds a `dof` status object of an unknown token under a Student's t distribution",
    ),
    "every_status_object_an_unstated_kind": Mutant(
        "a `plus_minus` entry whose `stated_as` holds any status object counted as of unstated kind",
        "provenance.md:246-247",
        {"check_plus_minus": every_status_object_an_unstated_kind},
        survives="no case holds a `stated_as` of another status token beside an entry of a stated kind",
    ),
    "every_forms_member_named_at_a_field": Mutant(
        "every form's member named at a field's place, so that a slip of another form's refuses a constant",
        "record_format.md:311",
        {"named_at_a_field": every_forms_member_named},
        survives="no case holds a slip of another form's member beside a form the reader knows",
    ),
    "input_specimens_optional": Mutant(
        "a derivation without `input_specimens` read",
        "provenance.md:185",
        {"check_input_specimens": input_specimens_optional},
        survives="every derivation in the cases holds `input_specimens`",
    ),
    "section_specimen_unchecked": Mutant(
        "a section's `specimen` not checked for a field read from it",
        "read_side_contract.md:284-285",
        {"check_value_field": section_specimen_unchecked},
    ),
    "condition_shapes_unchecked": Mutant(
        "a condition of a name the reader knows not checked",
        "read_side_contract.md:295-296",
        {"check_condition": condition_unchecked},
    ),
    "broken_status_object_reports_its_token": Mutant(
        "a status object that breaks its shape gives its token's `unknown_token` beside `form_invalid`",
        "provenance.md:51-53",
        {"status_object": broken_status_reports_its_token},
        survives="no case holds a status object breaking its shape with a token the reader does not know",
    ),
    # The points the text leaves open (`OPEN_POINTS`)
    "members_of_the_other_kind_read": Mutant(
        "a numeric condition holding `token`, or a token condition holding `value`, read",
        "OPEN_POINTS: members_of_the_other_kind",
        {"holds_another_kind": holds_no_other_kind},
        survives="no case holds a condition with a member of the other kind's shape: the text leaves it open",
    ),
    "members_of_the_other_kind_ignored": Mutant(
        "a numeric condition's `token`, or a token condition's `value`, ignored as a member the reader does "
        "not know: not refused, and not returned",
        "OPEN_POINTS: members_of_the_other_kind",
        {"holds_another_kind": holds_no_other_kind, "condition_entry": entry_without_the_other_kind},
        survives="no case holds a condition with a member of the other kind's shape: the text leaves it open",
    ),
    "slips_of_alternatives_ignored": Mutant(
        "a member one slip from `alternatives` beside a value field's members ignored",
        "OPEN_POINTS: alternatives_named_at_a_field",
        {"FIELD_PLACE_NAMES": model.VALUE_FIELD_NAMES},
        survives="no case holds a member one slip from `alternatives`: the text leaves it open",
    ),
    "evidence_entry_provenance_unchecked": Mutant(
        "an evidence entry's `provenance` not checked",
        "OPEN_POINTS: evidence_entry_provenance",
        {"check_entry_provenance": entry_provenance_unchecked},
        survives="each evidence entry's `provenance` in the cases is well formed: the text leaves it open",
    ),
    "declaration_names_not_named_in_a_request": Mutant(
        "a slip of a requirement's `field`, or of its conditions' `reason` or `consequence`, ignored",
        "OPEN_POINTS: names_a_declaration_gives_a_requirement",
        {
            "REQUIREMENT_NAMES": model.REQUIREMENT_NAMES[:-1],
            "REQUIREMENT_CONDITION_NAMES": model.REQUIREMENT_CONDITION_NAMES[:2],
        },
        survives="no case holds a slip of `field`, `reason` or `consequence` in a requirement",
    ),
    # Step 9
    "units_compared_after_case_folding": Mutant(
        "a record's units compared after case folding", "record_format.md:210-212", {"same_unit": case_folded}
    ),
    "fact_units_unchecked": Mutant(
        "a specimen fact's unit not compared with the one its row fixes",
        "read_side_contract.md:332-335",
        {"checked_specimens": no_specimen_checked},
    ),
    "token_condition_unit_accepted": Mutant(
        "a `unit` on a token condition passes step 9",
        "read_side_contract.md:328-329",
        {"check_units": token_condition_units_accepted},
    ),
    "plus_minus_units_unchecked": Mutant(
        "a `plus_minus` entry's unit not compared",
        "read_side_contract.md:328",
        {"check_units": plus_minus_units_unchecked},
    ),
    # Step 10
    "floating_point_as_written": Mutant(
        "section 5's tests computed in floating point as written",
        "read_side_contract.md:465-468",
        {"within_tolerance": in_floating_point},
    ),
    "strict_inequalities": Mutant(
        "`<` for `<=` in section 5's table",
        "read_side_contract.md:456-459",
        {"within_tolerance": strict_inequalities},
    ),
    "plus_minus_ignored": Mutant(
        "a stated plus or minus ignored",
        "read_side_contract.md:473-484",
        {"within_tolerance": plus_minus_ignored},
    ),
    "unchecked_read_as_met": Mutant(
        "a stated condition the request gives no tolerance or accept list for read as `met`",
        "read_side_contract.md:455",
        {"condition_entry": unchecked_read_as_met},
    ),
    "operating_omitted_from_entries": Mutant(
        "a condition entry without the request's operating condition",
        "read_side_contract.md:160-161",
        {"condition_entry": operating_omitted},
    ),
    "implied_fills_any_condition": Mutant(
        "an implied condition fills a stated condition, or one held as another status object",
        "declarations.md:200-202",
        {"unstated_or_absent": fills_anything},
    ),
    "disagreeing_implied_conditions_read": Mutant(
        "two implied conditions that disagree read as the first",
        "read_side_contract.md:98-103",
        {"same_supplied_value": always_the_same},
    ),
    "implied_values_compared_by_value": Mutant(
        "two implied values compared as numbers, so that `0` and `-0` agree",
        "read_side_contract.md:100-102",
        {"same_supplied_value": compared_by_value},
    ),
    "required_with_ignored": Mutant(
        "a condition another condition requires with its token not checked",
        "read_side_contract.md:445",
        {"CONDITIONS": NO_REQUIRED_WITH},
    ),
    "unknown_condition_names_ignored": Mutant(
        "a condition name the reader does not know gives no entry and no reason",
        "read_side_contract.md:454",
        {"conditions_checked": registered_names_only},
    ),
    # Step 12
    "stated_without_origin_unreported": Mutant(
        "a value stated without origin not `unknown`",
        "read_side_contract.md:342",
        {"read_value_field": origin_unreported},
    ),
    "step_12_labels_dropped": Mutant(
        "the field's label and `mixed_conditions` not added",
        "read_side_contract.md:343-344",
        {"step_12_labels": no_labels},
    ),
    # Step 13
    "bounds_given_by_a_constant": Mutant(
        "`want: bounds` gives a constant's value",
        "read_side_contract.md:508",
        {"GIVES": {**model.GIVES, "bounds": ("interval", "constant")}},
    ),
    "value_given_by_an_interval": Mutant(
        "`want: value` gives an interval's bounds without a nominal",
        "read_side_contract.md:507",
        {"GIVES": {**model.GIVES, "value": (*model.GIVES["value"], "interval")}},
    ),
    "nominal_outside_supplies_the_value": Mutant(
        "a nominal outside an interval's bounds supplies the value",
        "read_side_contract.md:507",
        {"shape_by_want": nominal_outside_supplies_the_value},
    ),
    # The status law and the result's members
    "best_status": Mutant(
        "the status the best of the reasons, not the worst", "read_side_contract.md:127", {"worst": best}
    ),
    "value_beside_not_met": Mutant(
        "a value returned beside `not_met` without an assumption, as beside `condition_outside`",
        "read_side_contract.md:115",
        {"read_value_field": members_read_past_a_refusal, "value_returned": value_whatever_the_status},
    ),
    "unknown_members_returned": Mutant(
        "a member the reader does not know returned",
        "read_side_contract.md:153-154",
        {"known_members": every_member},
    ),
    "review_returned_as_its_result": Mutant(
        "a known review returned as its `result` alone",
        "provenance.md:118-121",
        {"review_read": review_result_alone},
    ),
    "unit_returned_without_its_reason": Mutant(
        "a unit held as a status object returned without its `reason`",
        "read_side_contract.md:117",
        {"unit_returned": registered_unit},
    ),
    "section_facts_not_merged": Mutant(
        "the result's `specimen` the field's facts alone",
        "read_side_contract.md:119",
        {"merged_specimen": field_facts_alone},
    ),
    "results_share_the_record": Mutant(
        "a result shares its members with the record read",
        "read_side_contract.md:150-152",
        {"copied": shared},
        survives="a case compares a result's JSON, in which no object is shared",
    ),
    # Rules S2a-4's review pinned (half B, L4; half A, L6)
    "ies_not_a_plural": Mutant(
        "a final `y` exchanged with `ies` not one slip",
        "record_format.md:583-584",
        {"_plural_of_either": ies_not_a_plural},
        survives="no case holds a slip of a final `y` made `ies`",
    ),
    "donor_age_of_neither_accepted": Mutant(
        "a `donor_age` holding neither `value` nor `range` accepted",
        "provenance.md:275",
        {"check_fact": donor_age_of_neither_accepted},
        survives="no case holds a `donor_age` with neither `value` nor `range`",
    ),
    "review_of_both_shapes_read_as_its_status": Mutant(
        "a review holding both `status` and `result` read as its status object",
        "provenance.md:122",
        {"review_read": both_shapes_read_as_the_status_object},
        survives="no case holds a review holding both `status` and `result`",
    ),
    "reviewed_review_keeps_a_status_objects_members": Mutant(
        "a reviewed review returned with a status object's members, its `reason` among them",
        "provenance.md:96",
        {"review_read": reviewed_with_a_status_objects_members},
        survives="no case holds a reviewed review beside a `reason`",
    ),
    # A step S4 owns, which no read S2 builds reaches (S2a-4's review B, L1)
    "units_stored_differently_read_as_no_pick": Mutant(
        "alternatives whose units are stored differently read as `no_pick`, which S4 decides",
        "OPEN_POINTS: alternatives_within_decision_12",
        {"read_alternatives": units_stored_differently_compared},
        survives="no case holds alternatives whose units are stored differently",
    ),
}
