# SPDX-License-Identifier: Apache-2.0
"""Mutants of step 8 (`core/value_shapes.py`, `core/fields.py`), each with one fault, and the property of
`test_value_field_properties.py` that must kill each one. As in `test_mutants.py`, each must die within the
examples the `ci` profile gives a property, at both sizes, and records the examples its kill took as
`examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function or table of
`value_shapes` or `fields`, or the `members` helper wrapped so that it checks one member otherwise.
"""

import itertools
import math
import re
from collections.abc import Callable, Collection, Iterable
from typing import Any, NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica import shapes
from materica.core import fields, read, value_shapes
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.slips import one_slip
from materica.core.value_shapes import Check, Found, JsonObject, Members
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import test_value_field_properties as properties
from tests.property import value_field_strategies as strategies
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MUTANT_SEARCH
from tests.property.test_mutants import setting

# Each property that kills a mutant, by name: its examples at a size, and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None]]] = {
    "HP3": (strategies.faulty_records, properties.check_one_fault),
    "HP5": (properties.with_unknowns, properties.check_ignored),
    # A planned search of HP5: members added in an evidence field's reports alone.
    "HP5 in a report": (lambda size: properties.with_unknowns(size, reports=True), properties.check_ignored),
    "base": (strategies.valid_records, properties.check_passes),
    "label": (properties.labelled_fields, properties.check_label),
}
ONE_FAULT, IGNORANCE, _, BASE, LABEL = KILLERS


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[
        str, ...
    ] = ()  # HP3's faults, `region.name`, one of which its kill must hold; any where none


# Faults in what a token, a status object or a slip is.


TOKEN_PROBLEMS = value_shapes.token_problems


def _unknown_tokens_ignored(
    value: JsonValue, member: str, allowed: Collection[str], where: str, found: Found
) -> None:
    if not isinstance(value, str) or value in value_shapes.KNOWN[member]:
        TOKEN_PROBLEMS(value, member, allowed, where, found)


def _unknown_token_read_as_a_shape_fault(detail: str) -> Reason:
    return Reason("form_invalid", detail=detail)


STATUS_OBJECT = value_shapes.status_object


def _status_tokens_unchecked(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    STATUS_OBJECT(value, where, None, defines, found)


def _members_beside_a_status_ignored(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    kept = value if not defines else {name: member for name, member in value.items() if name not in defines}
    STATUS_OBJECT(kept, where, tokens, defines, found)


def slipped_by(
    relation: Callable[[str, str], str | None],
) -> Callable[[Iterable[str], Collection[str]], list[tuple[str, str]]]:
    """`slips.slipped`, with `relation` in place of `one_slip`."""

    def slipped(members: Iterable[str], named: Collection[str]) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for member in members:
            if member not in named:
                name = next((name for name in sorted(named) if relation(member, name) is not None), None)
                if name is not None:
                    found.append((member, name))
        return found

    return slipped


def without(*kinds: str) -> Callable[[str, str], str | None]:
    """`one_slip`, blind to the slips of `kinds`."""

    def relation(a: str, b: str) -> str | None:
        slip = one_slip(a, b)
        return None if slip in kinds else slip

    return relation


def within_two_slips(a: str, b: str) -> str | None:
    """Two names one or two characters apart, a relation wider than section 10's."""
    if one_slip(a, b) is not None:
        return "one slip"
    longer, shorter = sorted((a, b), key=len, reverse=True)
    return "two added" if len(longer) - len(shorter) == 2 and longer.startswith(shorter) else None


# Faults in which members a check reads, and how: `members` wrapped.

MEMBERS = value_shapes.members


def members_with(change: Callable[[Members], Members]) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection under which `members` checks the required and optional members `change` gives."""

    def checked(
        value: JsonValue,
        where: str,
        found: Found,
        required: Members,
        optional: Members | None = None,
        *,
        named: Collection[str] = (),
    ) -> JsonObject | None:
        changed = change({**required, **{f"?{name}": check for name, check in (optional or {}).items()}})
        required = {name: check for name, check in changed.items() if not name.startswith("?")}
        optional = {name[1:]: check for name, check in changed.items() if name.startswith("?")}
        return MEMBERS(value, where, found, required, optional, named=named)

    return setting(value_shapes, "members", checked)


def replacing(name: str, check: Check) -> Callable[[Members], Members]:
    return lambda checks: {key: check if key.lstrip("?") == name else value for key, value in checks.items()}


def optional(name: str) -> Callable[[Members], Members]:
    return lambda checks: {(f"?{key}" if key == name else key): value for key, value in checks.items()}


def _any(value: JsonValue, where: str, found: Found) -> None:
    pass


def _lists(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, list):
        found.append(value_shapes.invalid(f"{where} is not a list"))


def _without_nulls(
    value: JsonValue,
    where: str,
    found: Found,
    required: Members,
    optional: Members | None = None,
    *,
    named: Collection[str] = (),
) -> JsonObject | None:
    if isinstance(value, dict):
        value = {name: member for name, member in value.items() if member is not None}
    return MEMBERS(value, where, found, required, optional, named=named)


def _unknown_condition_names_checked(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict):
        for name, entry in value.items():
            check = value_shapes.CONDITIONS.get(name, value_shapes.NUMERIC_CONDITION)
            check(entry, f"{where}.{name}", found)


def _every_unnamed_member_refused(
    value: JsonObject, named: Collection[str], where: str, found: Found
) -> None:
    for member in value:
        if member not in named:
            found.append(value_shapes.invalid(f"{where} holds {member!r}, which it does not name"))


def _nothing(*arguments: object) -> None:
    pass


def _no_record_problems(record: JsonObject) -> Found:
    return []


FORM_PROBLEMS = fields.form_problems


def _first_refusal_only(field: RecordField, record: JsonObject, claims: Collection[Suite]) -> Found:
    return FORM_PROBLEMS(field, record, claims)[:1]


def _section_specimen_unchecked(name: str, section: JsonObject) -> Found:
    return value_shapes.section_problems(
        name, {key: member for key, member in section.items() if key != "specimen"}
    )


COUNT_AS_NUMBER = value_shapes.or_status(value_shapes.number, shapes.StatisticsBlock, "n_specimens")


def facts_with(**shapes_of: value_shapes.Check) -> dict[str, value_shapes.Check]:
    """Step 8's specimen facts, the named ones checked as `shapes_of` gives."""
    changed = {
        name: value_shapes.or_status(check, shapes.Specimen, name) for name, check in shapes_of.items()
    }
    return {**value_shapes.FACTS, **changed}


STATE = value_shapes.fact_token("disease_and_treatment_state")
TEXT_ANYWHERE = facts_with(
    disease_and_treatment_state=value_shapes.based({"token": STATE}, {"text": value_shapes.string})
)
MIMICS_EITHER_BASIS = facts_with(mimics=value_shapes.based({"text": value_shapes.string}))


def _the_unit_s(value: JsonValue, where: str, found: Found) -> None:
    if value != "s":
        found.append(value_shapes.invalid(f"{where} is not s"))


# A fact's unit judged at step 8 as S2a-2 first did: `s` alone, and a status object of the five tokens only.
FACT_UNIT_S = value_shapes.or_status(_the_unit_s, shapes.PostMortemInterval, "unit")
FACT_UNIT_JUDGED = facts_with(
    post_mortem_interval=value_shapes.based({"value": value_shapes.number, "unit": FACT_UNIT_S}),
    donor_age=value_shapes.based(
        {"unit": FACT_UNIT_S}, {"value": value_shapes.number, "range": value_shapes.in_order}
    ),
)

# The eleven rules S2a-2's review found untested, and the slips it found HP3 blind to (findings M1, M2).

WITHIN_ANY_STATUS = value_shapes.status_or(value_shapes.listed("within", "level"), None, ())
UNCERTAINTY_PRECISION_ANY_STRING = (
    value_shapes.UNCERTAINTY[0],
    {
        "precision_conditions": value_shapes.or_status(
            value_shapes.string, shapes.Uncertainty, "precision_conditions"
        )
    },
)


def uncertainty_with(**checks: Check) -> tuple[Members, Members]:
    required, optional = value_shapes.UNCERTAINTY
    return {**required, **{name: check for name, check in checks.items() if name in required}}, optional


def _not_below_zero_but_one(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not 0 <= value <= 1:
        found.append(value_shapes.invalid(f"{where} is not from zero to one"))


def rebuilt(monkeypatch: pytest.MonkeyPatch, condition: Callable[[Any], Check] | None = None) -> None:
    """Step 8's conditions and facts built again under the faults `monkeypatch` holds, which `based` and
    `condition` read when they build them; `condition` in place of step 8's where given."""
    build = condition or value_shapes.condition
    monkeypatch.setattr(
        value_shapes, "CONDITIONS", {name: build(spec) for name, spec in VOCABULARY.conditions.items()}
    )
    facts = {
        name: value_shapes.or_status(
            value_shapes.based(
                required, optional, rule, fixed_basis=VOCABULARY.facts[name].fixed.get("basis")
            ),
            shapes.Specimen,
            name,
        )
        for name, (required, optional, rule) in value_shapes.FACT_SHAPES.items()
    }
    monkeypatch.setattr(value_shapes, "FACTS", facts)


def rebuilt_with(condition: Callable[[Any], Check]) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: rebuilt(monkeypatch, condition)


def basis_any_string(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = value_shapes.listed

    def any_basis(member: str, token_list: str) -> Check:
        return (
            value_shapes.string if (member, token_list) == ("basis", "basis") else listed(member, token_list)
        )

    monkeypatch.setattr(value_shapes, "listed", any_basis)
    rebuilt(monkeypatch)


def own_shape_only(spec: Any) -> Check:
    """A condition whose status object refuses the members of its own shape only."""
    own = (
        value_shapes.NUMERIC_CONDITION
        if spec.shape == "numeric"
        else value_shapes.based(
            {"token": value_shapes.token("token", spec.tokens)}, {"unit": value_shapes.unit}
        )
    )
    return value_shapes.or_status(own, shapes.Conditions, spec.name)


def token_unit_unchecked(spec: Any) -> Check:
    if spec.shape == "numeric":
        return value_shapes.condition(spec)
    own = value_shapes.based({"token": value_shapes.token("token", spec.tokens)}, {"unit": _any})
    return value_shapes.or_status(own, shapes.Conditions, spec.name, value_shapes.CONDITION_MEMBERS)


CONDITION_TOKENS = frozenset(token for spec in VOCABULARY.conditions.values() for token in spec.tokens)
FACT_TOKENS = frozenset(token for spec in VOCABULARY.facts.values() for token in spec.tokens)


def _token_known_within_its_kind(
    value: JsonValue, member: str, allowed: Collection[str], where: str, found: Found
) -> None:
    """A condition's `token` knowing the conditions' tokens alone, and a fact's the facts' alone."""
    if member == "token" and isinstance(value, str) and value not in allowed:
        kind = CONDITION_TOKENS if set(allowed) <= CONDITION_TOKENS else FACT_TOKENS
        reason = value_shapes.invalid if value in kind else value_shapes.unknown_token
        found.append(reason(f"{where} holds {value!r}"))
    else:
        TOKEN_PROBLEMS(value, member, allowed, where, found)


LABEL_ALLOWED = value_shapes.label_allowed


def _label_on_any_table(spec: Any, form: str | None, field: JsonObject) -> bool:
    return (form == "table" and spec.label is not None) or LABEL_ALLOWED(spec, form, field)


def _label_beside_an_unknown_form_as_on_a_constant(spec: Any, form: str | None, field: JsonObject) -> bool:
    return LABEL_ALLOWED(spec, "constant" if form is None else form, field)


FIELD_PROBLEMS = value_shapes.field_problems


def _no_form_member_named_beside_an_unknown_form(field: JsonObject, spec: Any, form: str | None) -> Found:
    """Step 8's shared check, naming no form's own member where the form is a token the reader does not
    know."""
    if form is not None:
        return FIELD_PROBLEMS(field, spec, form)
    stripped = {
        name: member
        for name, member in field.items()
        if not any(one_slip(name, own) for own in value_shapes.FORM_MEMBERS.values())
    }
    return FIELD_PROBLEMS(stripped, spec, form)


def _inputs_may_be_empty(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, list):
        found.append(value_shapes.invalid(f"{where} is not a list"))
        return
    for index, item in enumerate(value):
        value_shapes.derivation_input(item, f"{where}[{index}]", found)


def _both_but_not_neither(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict) and "value" in value and "range" in value:
        found.append(value_shapes.invalid(f"{where} holds both value and range"))


def neither_value_nor_range_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    required, optional = (
        {"unit": value_shapes.unit},
        {
            "value": value_shapes.number,
            "range": value_shapes.in_order,
            "plus_minus": value_shapes.plus_minus,
            "set_or_measured": value_shapes.listed("set_or_measured", "set_or_measured"),
        },
    )
    numeric = value_shapes.based(required, optional, _both_but_not_neither)
    monkeypatch.setattr(value_shapes, "NUMERIC_CONDITION", numeric)
    rebuilt(monkeypatch)


BLOCK_PRECISION_ANY_STRING = (
    value_shapes.STATISTICS[0],
    {
        **value_shapes.STATISTICS[1],
        "precision_conditions": value_shapes.or_status(
            value_shapes.string, shapes.StatisticsBlock, "precision_conditions"
        ),
    },
)


STATISTICS_BLOCK = value_shapes.statistics_block


def _block_slips_ignored(value: JsonValue, where: str, found: Found) -> None:
    mine: Found = []
    STATISTICS_BLOCK(value, where, mine)
    found += [
        reason
        for reason in mine
        if not (str(reason.detail).startswith(f"{where} holds") and "one slip" in str(reason.detail))
    ]


def _field_slips_ignored(field: JsonObject, spec: Any, form: str | None) -> Found:
    return [
        reason
        for reason in FIELD_PROBLEMS(field, spec, form)
        if not (str(reason.detail).startswith(f"{spec.name} holds") and "one slip" in str(reason.detail))
    ]


def _status_slips_ignored(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    mine: Found = []
    STATUS_OBJECT(value, where, tokens, defines, mine)
    found += [reason for reason in mine if "one slip" not in str(reason.detail)]


# The faults of a token the reader knows for no member of its name, each where `token_problems` finds it.
# Faults in a form's own member (`fields.py`): its check replaced in `fields.OWN_MEMBERS`, a status object
# read as before, or a table or check it reads when it runs.

OWN_MEMBER_SHAPES = {"interval": shapes.IntervalField, "composition": shapes.CompositionField}
INTERVAL = fields.interval
COMPOSITION = fields.composition
COMPONENTS = fields.components


def own_member(form: str, check: Check) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection under which step 8 reads `form`'s own member with `check`."""

    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        held = value_shapes.or_status(check, OWN_MEMBER_SHAPES[form], form)
        monkeypatch.setitem(fields.OWN_MEMBERS, form, held)

    return inject


def _bounds(value: JsonValue) -> tuple[JsonValue, JsonValue]:
    return (value.get("lower"), value.get("upper")) if isinstance(value, dict) else (None, None)


def _interval_in_any_order(value: JsonValue, where: str, found: Found) -> None:
    lower, upper = _bounds(value)
    if isinstance(value, dict) and isinstance(lower, float) and isinstance(upper, float):
        value = {**value, "lower": min(lower, upper), "upper": max(lower, upper)}
    INTERVAL(value, where, found)


def _two_nones_as_one(value: JsonValue, where: str, found: Found) -> None:
    lower, upper = _bounds(value)
    if isinstance(value, dict) and isinstance(lower, dict) and isinstance(upper, dict):
        value = {**value, "lower": 0.0}
    INTERVAL(value, where, found)


def _strictly_ordered(value: JsonValue, where: str, found: Found) -> None:
    INTERVAL(value, where, found)
    lower, upper = _bounds(value)
    if isinstance(lower, float) and isinstance(upper, float) and lower == upper:
        found.append(value_shapes.invalid(f"{where} has equal bounds"))


def _ordered_by_sign(value: JsonValue, where: str, found: Found) -> None:
    INTERVAL(value, where, found)
    lower, upper = _bounds(value)
    if isinstance(lower, float) and isinstance(upper, float) and lower == upper == 0.0:
        if math.copysign(1.0, lower) > math.copysign(1.0, upper):
            found.append(value_shapes.invalid(f"{where} has 0 above -0"))


BOUND_ANY_STATUS = value_shapes.status_or(
    value_shapes.number, None, value_shapes.status_row(shapes.Interval, "lower")[1]
)


def _every_basis_allowed(*arguments: object) -> bool:
    return True


def _components_may_be_empty(value: JsonValue, where: str, found: Found) -> None:
    if value != []:
        COMPONENTS(value, where, found)


def _each_component_once(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, list):
        named = {str(item.get("component")): item for item in value if isinstance(item, dict)}
        value = [*named.values(), *(item for item in value if not isinstance(item, dict))]
    COMPONENTS(value, where, found)


def _a_repeat_found_only_beside_itself(value: JsonValue, where: str, found: Found) -> None:
    """A component named twice is found only where it follows itself."""
    own: Found = []
    COMPONENTS(value, where, own)
    items = value if isinstance(value, list) else []
    named = [item.get("component") for item in items if isinstance(item, dict)]
    beside = {f"{first!r} twice" for first, then in itertools.pairwise(named) if first == then}
    found.extend(
        reason
        for reason in own
        if not str(reason.detail).endswith(" twice") or any(str(reason.detail).endswith(b) for b in beside)
    )


def _any_number(value: JsonValue, where: str, found: Found) -> None:
    value_shapes.number(value, where, found)


def _within_zero_and_one_open(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not 0 < value < 1:
        found.append(value_shapes.invalid(f"{where} is not a number between zero and one"))


def _an_element_by_pattern(value: JsonValue, where: str, found: Found) -> None:
    """The S2 design's alternative for SQ43: a symbol checked by `[A-Z][a-z]?` alone."""
    if not (isinstance(value, str) and re.fullmatch(r"element:[A-Z][a-z]?", value)):
        found.append(value_shapes.invalid(f"{where} is not an element"))


def _sums_checked(value: JsonValue, where: str, found: Found) -> None:
    COMPOSITION(value, where, found)
    if not isinstance(value, dict) or value.get("sum_rule") != "sums_to_one" or "stated_sum" in value:
        return
    held = value.get("components")
    fractions = (
        [item.get("fraction") for item in held if isinstance(item, dict)] if isinstance(held, list) else []
    )
    if abs(math.fsum(fraction for fraction in fractions if isinstance(fraction, float)) - 1) > 1e-6:
        found.append(value_shapes.invalid(f"{where} does not sum to one"))


OWN_MEMBER_NAMES = {
    "interval": ("lower", "upper", "basis"),
    "composition": ("basis", "sum_rule", "stated_sum", "components"),
}
COMPONENT_NAMES = ("component", "fraction", "statistics")


def _unknown_members_refused_in(form: str) -> Check:
    """`form`'s own member, any member it, or a component, does not name refused."""

    def checked(value: JsonValue, where: str, found: Found) -> None:
        {"interval": INTERVAL, "composition": COMPOSITION}[form](value, where, found)
        held = [value] if isinstance(value, dict) else []
        if isinstance(value, dict) and isinstance(components := value.get("components"), list):
            held += [item for item in components if isinstance(item, dict)]
        for item in held:
            names = OWN_MEMBER_NAMES[form] if item is value else COMPONENT_NAMES
            if set(item) - set(names):
                found.append(value_shapes.invalid(f"{where} holds a member it does not name"))

    return checked


def _unknown_members_refused_in_an_own_member(monkeypatch: pytest.MonkeyPatch) -> None:
    for form in OWN_MEMBER_NAMES:
        own_member(form, _unknown_members_refused_in(form))(monkeypatch)


# Evidence's own member (`record_format.md` section 4.3), S2b-2's.

EVIDENCE = fields.evidence
EVIDENCE_ENTRY = fields.evidence_entry


def evidence_with(check: Check) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection under which step 8 reads evidence's own member with `check`."""
    return lambda monkeypatch: monkeypatch.setitem(fields.OWN_MEMBERS, "evidence", check)


def _withheld_read_as(old: str, new: str) -> Check:
    def checked(value: JsonValue, where: str, found: Found) -> None:
        own: Found = []
        EVIDENCE(value, where, own)
        found += [Reason(new) if reason.code == old else reason for reason in own]  # type: ignore[arg-type]

    return checked


def _an_empty_list_taken(value: JsonValue, where: str, found: Found) -> None:
    if value != []:
        EVIDENCE(value, where, found)


def _a_status_read_as_withheld(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict) and value.get("status") == "withheld":
        found.append(Reason("withheld"))
    else:
        EVIDENCE(value, where, found)


def entries_with(keep: Callable[[Reason], bool]) -> Callable[[pytest.MonkeyPatch], None]:
    """An injection under which a report's check drops the reasons `keep` does not keep."""

    def entry(value: JsonValue, where: str, found: Found) -> bool:
        own: Found = []
        withheld = EVIDENCE_ENTRY(value, where, own)
        found += [reason for reason in own if keep(reason)]
        return withheld

    return lambda monkeypatch: monkeypatch.setattr(fields, "evidence_entry", entry)


def _registered_conditions_taken(conditions: JsonValue, where: str, found: Found) -> None:
    pass


# The members a report names, its standard's and its provenance's (`record_format.md` section 4.3).
REPORT_NAMES = {
    "report": (*fields.REPORT, "provenance"),
    "standard": ("designation", "year"),
    "provenance": value_shapes.PROVENANCE_MEMBERS,
}


def _unknown_members_refused_in_a_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """A member a report, its standard or its provenance does not name refused."""

    def entry(value: JsonValue, where: str, found: Found) -> bool:
        held = {"report": value}
        if isinstance(value, dict):
            held |= {name: value.get(name) for name in ("standard", "provenance")}
        if any(
            isinstance(part, dict) and "status" not in part and set(part) - set(REPORT_NAMES[name])
            for name, part in held.items()
        ):
            found.append(value_shapes.invalid(f"{where} holds a member it does not name"))
        return EVIDENCE_ENTRY(value, where, found)

    monkeypatch.setattr(fields, "evidence_entry", entry)


UNKNOWN_TOKENS = (
    "statistics_tokens.central_unknown",
    "statistics_tokens.distribution_unknown",
    "statistics_tokens.level_unknown",
    "statistics_tokens.precision_conditions_unknown",
    "statistics_tokens.within_unknown",
    "uncertainty_tokens.uncertainty_basis_unknown",
    "uncertainty_tokens.uncertainty_precision_unknown",
    "uncertainty_tokens.uncertainty_represents_unknown",
    "condition_tokens.basis_unknown",
    "condition_tokens.set_or_measured_unknown",
    "condition_tokens.token_unknown",
    "specimen_tokens.fact_token_unknown",
    "provenance.origin_unknown",
    "interval_tokens.basis_unknown",
    "composition_tokens.basis_unknown",
    "composition_tokens.sum_rule_unknown",
    "component.element_unknown",
    "component.kind_unknown",
    "component.symbol_case_unknown",
    "component.statistics_central_unknown",
    "evidence_provenance.origin_unknown",
)


MUTANTS = [
    Mutant(
        "unknown_tokens_ignored",
        ONE_FAULT,
        setting(value_shapes, "token_problems", _unknown_tokens_ignored),
        UNKNOWN_TOKENS,
    ),
    Mutant(
        "unknown_token_read_as_a_shape_fault",
        ONE_FAULT,
        setting(value_shapes, "unknown_token", _unknown_token_read_as_a_shape_fault),
        (
            *UNKNOWN_TOKENS,
            "statistics_statuses.status_unknown",
            "field.label_unknown",
            "evidence_report.status_unknown",
            "evidence_report.standard_status_unknown",
        ),
    ),
    Mutant(
        "status_tokens_unchecked",
        ONE_FAULT,
        setting(value_shapes, "status_object", _status_tokens_unchecked),
        (
            "statistics_statuses.block_status_not_allowed",
            "statistics_statuses.status_not_allowed",
            "statistics_statuses.status_unknown",
            "statistics_statuses.within_status_not_allowed",
            "field.value_status_not_allowed",
        ),
    ),
    Mutant(
        "members_beside_a_status_ignored",
        ONE_FAULT,
        setting(value_shapes, "status_object", _members_beside_a_status_ignored),
        (
            "statistics_statuses.uncertainty_status_beside_a_member",
            "condition_tokens.status_beside_a_token",
            "condition_tokens.status_beside_unit",
            "specimen_tokens.fact_status_beside_its_token",
        ),
    ),
    Mutant(
        "missing_represents_accepted",
        ONE_FAULT,
        members_with(optional("represents")),
        ("statistics_members.represents_missing",),
    ),
    Mutant(
        "null_read_as_absent",
        ONE_FAULT,
        setting(value_shapes, "members", _without_nulls),
        ("condition_tokens.set_or_measured_null", "provenance.source_null"),
    ),
    Mutant(
        "unknown_condition_names_checked",
        ONE_FAULT,
        setting(value_shapes, "conditions", _unknown_condition_names_checked),
        ("condition_tokens.name_unknown",),
    ),
    Mutant(
        "plus_minus_kinds_unchecked",
        ONE_FAULT,
        members_with(replacing("plus_minus", _lists)),
        (
            "conditions.plus_minus_empty",
            "conditions.plus_minus_negative",
            "conditions.plus_minus_two_bounds",
            "conditions.plus_minus_unit_not_a_string",
            "conditions.plus_minus_unstated_beside_sd",
        ),
    ),
    Mutant(
        "range_order_unchecked",
        ONE_FAULT,
        members_with(replacing("range", _any)),
        (
            "conditions.range_reversed",
            "conditions.range_reversed_on_shear_rate",
            "specimen.fact_range_reversed",
        ),
    ),
    Mutant(
        "counts_not_whole",
        ONE_FAULT,
        members_with(replacing("n_specimens", COUNT_AS_NUMBER)),
        ("statistics_numbers.count_not_whole",),
    ),
    Mutant(
        "conditional_members_unchecked",
        ONE_FAULT,
        setting(value_shapes, "present_exactly_where", _nothing),
        (
            "statistics_members.n_sources_elsewhere",
            "statistics_members.population_level_elsewhere",
            "statistics_members.population_level_missing",
            "statistics_members.precision_conditions_missing",
            "uncertainty.uncertainty_precision_missing",
        ),
    ),
    Mutant(
        "uncertainty_rules_unchecked",
        ONE_FAULT,
        setting(value_shapes, "uncertainty_rules", _nothing),
        (
            "uncertainty.dof_status_under_student_t",
            "uncertainty.dof_under_normal",
            "uncertainty.no_coverage_number",
            "uncertainty.uncertainty_precision_missing",
        ),
    ),
    Mutant(
        "named_state_text_unchecked",
        ONE_FAULT,
        setting(value_shapes, "FACTS", TEXT_ANYWHERE),
        ("specimen.fact_text_beside_normal", "specimen.fact_treated_without_text"),
    ),
    Mutant(
        "fixed_basis_unchecked",
        ONE_FAULT,
        setting(value_shapes, "FACTS", MIMICS_EITHER_BASIS),
        ("specimen_tokens.fact_basis_not_its_rows",),
    ),
    Mutant(
        "fact_unit_judged_at_step_8",
        ONE_FAULT,
        setting(value_shapes, "FACTS", FACT_UNIT_JUDGED),
        ("specimen.fact_unit_not_its_rows", "specimen.fact_unit_status_any_token"),
    ),
    Mutant(
        "record_structure_unchecked",
        ONE_FAULT,
        setting(fields, "record_problems", _no_record_problems),
        ("record.body_slip", "record.envelope_slip", "record.licence_slip", "record.section_name_slip"),
    ),
    Mutant(
        "section_specimen_unchecked",
        ONE_FAULT,
        setting(fields, "section_problems", _section_specimen_unchecked),
        ("section_specimen.section_fact_name_slip", "section_specimen.section_fact_not_its_shape"),
    ),
    Mutant(
        "first_refusal_only",
        ONE_FAULT,
        setting(read, "form_problems", _first_refusal_only),
        ("field_form.form_unknown_beside_a_slip",),
    ),
    *[
        Mutant(
            f"slip_by_{name}_missed",
            ONE_FAULT,
            setting(value_shapes, "slipped", slipped_by(without(*kinds))),
            dies_at,
        )
        for name, (kinds, dies_at) in {
            "substitution": (
                ("a character substituted",),
                ("statistics_slips_beside.slip_beside_substituted", "field_slips_optional.slip_substituted"),
            ),
            "insertion": (
                ("a character added",),
                (
                    "statistics_slips_beside.slip_beside_inserted",
                    "statistics_slips_beside.slip_beside_deleted",
                    "field_slips_optional.slip_inserted",
                    "field_slips_optional.slip_deleted",
                ),
            ),
            "swap": (
                ("two characters swapped",),
                (
                    "statistics_slips_beside.slip_beside_swapped",
                    "conditions.plus_minus_slip",
                    "field_slips_optional.slip_swapped",
                ),
            ),
            "plural": (
                ("singular or plural",),
                ("statistics_slips_beside.slip_beside_plural", "field_slips_optional.slip_plural"),
            ),
            "underscore": (
                ("an underscore added",),
                ("statistics_slips_beside.slip_beside_underscore", "field_slips_optional.slip_underscore"),
            ),
        }.items()
    ],
    Mutant(
        "unknown_members_refused", IGNORANCE, setting(value_shapes, "slips", _every_unnamed_member_refused)
    ),
    Mutant("two_slips_refused", IGNORANCE, setting(value_shapes, "slipped", slipped_by(within_two_slips))),
    # S2a-2's review, M1: the eleven rules no test checked (the fact unit's is `fact_unit_judged_at_step_8`).
    Mutant(
        "within_any_status",
        ONE_FAULT,
        members_with(replacing("within", WITHIN_ANY_STATUS)),
        ("statistics_statuses.within_status_not_allowed",),
    ),
    Mutant(
        "uncertainty_precision_any_string",
        ONE_FAULT,
        setting(value_shapes, "UNCERTAINTY", UNCERTAINTY_PRECISION_ANY_STRING),
        ("uncertainty_tokens.uncertainty_precision_unknown",),
    ),
    Mutant(
        "statistics_not_applicable_on_a_constant",
        ONE_FAULT,
        setting(value_shapes, "FIELD_STATISTICS", value_shapes.REFERENCE_DATA_STATISTICS),
        ("statistics_statuses.block_status_not_allowed",),
    ),
    Mutant(
        "basis_any_string",
        ONE_FAULT,
        basis_any_string,
        ("condition_tokens.basis_unknown", "specimen_tokens.fact_basis_of_another_member"),
    ),
    Mutant(
        "condition_status_refuses_its_own_shapes_members_only",
        ONE_FAULT,
        rebuilt_with(own_shape_only),
        ("condition_tokens.status_beside_a_token",),
    ),
    Mutant(
        "token_known_within_its_kind",
        ONE_FAULT,
        setting(value_shapes, "token_problems", _token_known_within_its_kind),
        ("condition_tokens.token_of_a_fact", "specimen_tokens.fact_token_of_a_condition"),
    ),
    Mutant(
        "token_condition_unit_unchecked",
        ONE_FAULT,
        rebuilt_with(token_unit_unchecked),
        ("condition_tokens.token_condition_unit_not_a_string",),
    ),
    Mutant("label_on_any_table", LABEL, setting(value_shapes, "label_allowed", _label_on_any_table)),
    Mutant(
        "label_beside_an_unknown_form_as_on_a_constant",
        ONE_FAULT,
        setting(value_shapes, "label_allowed", _label_beside_an_unknown_form_as_on_a_constant),
        ("field_form.form_unknown_beside_the_label",),
    ),
    Mutant(
        "no_form_member_named_beside_an_unknown_form",
        ONE_FAULT,
        setting(fields, "field_problems", _no_form_member_named_beside_an_unknown_form),
        ("field_form.form_unknown_beside_a_slip",),
    ),
    # S2a-2's review, M2: slips HP3 could not tell from a missing member, and parts of the text it had no
    # fault for.
    Mutant(
        "statistics_block_slips_ignored",
        ONE_FAULT,
        setting(
            value_shapes,
            "FIELD_STATISTICS",
            value_shapes.or_status(_block_slips_ignored, shapes.ConstantField, "statistics"),
        ),
        tuple(f"statistics_slips_beside.slip_beside_{kind}" for kind in strategies.SLIPS),
    ),
    Mutant(
        "field_level_slips_ignored",
        ONE_FAULT,
        setting(fields, "field_problems", _field_slips_ignored),
        tuple(f"field_slips_optional.slip_{kind}" for kind in strategies.SLIPS),
    ),
    Mutant(
        "status_object_slips_ignored",
        ONE_FAULT,
        setting(value_shapes, "status_object", _status_slips_ignored),
        ("statistics_statuses.status_slip",),
    ),
    Mutant(
        "derivation_unchecked",
        ONE_FAULT,
        setting(value_shapes, "derivation", _nothing),
        tuple(
            f"{region}.{name}"
            for region in ("derivation", "derivation_inputs")
            for name in strategies.CATALOGUE[region]
            if name != "derivation_missing"
        ),
    ),
    Mutant(
        "derivation_inputs_may_be_empty",
        ONE_FAULT,
        setting(value_shapes, "derivation_inputs", _inputs_may_be_empty),
        ("derivation.inputs_empty",),
    ),
    Mutant(
        "block_mean_any",
        ONE_FAULT,
        members_with(replacing("mean", _any)),
        ("statistics_numbers.mean_not_a_number",),
    ),
    Mutant(
        "block_precision_any_string",
        ONE_FAULT,
        setting(value_shapes, "STATISTICS", BLOCK_PRECISION_ANY_STRING),
        ("statistics_tokens.precision_conditions_unknown",),
    ),
    Mutant(
        "neither_value_nor_range_allowed",
        ONE_FAULT,
        neither_value_nor_range_allowed,
        ("conditions.neither_value_nor_range",),
    ),
    Mutant(
        "n_sources_any_number",
        ONE_FAULT,
        members_with(replacing("n_sources", COUNT_AS_NUMBER)),
        ("statistics_numbers.n_sources_not_whole", "statistics_numbers.n_sources_negative"),
    ),
    Mutant(
        "dof_of_zero_allowed",
        ONE_FAULT,
        setting(
            value_shapes,
            "UNCERTAINTY",
            uncertainty_with(
                dof=value_shapes.or_status(value_shapes.not_below_zero, shapes.Uncertainty, "dof")
            ),
        ),
        ("uncertainty.dof_zero",),
    ),
    Mutant(
        "coverage_probability_of_zero_allowed",
        ONE_FAULT,
        setting(
            value_shapes,
            "UNCERTAINTY",
            uncertainty_with(
                coverage_probability=value_shapes.or_status(
                    _not_below_zero_but_one, shapes.Uncertainty, "coverage_probability"
                )
            ),
        ),
        ("uncertainty.coverage_probability_zero",),
    ),
    Mutant(
        "population_level_any_string",
        ONE_FAULT,
        members_with(replacing("level", value_shapes.string)),
        ("statistics_tokens.level_unknown",),
    ),
    # S2b-1's: an interval's and a composition's own member (`record_format.md` section 6), each rule HP3's
    # catalogue holds a fault for, and its near misses.
    Mutant(
        "interval_order_unchecked",
        ONE_FAULT,
        own_member("interval", _interval_in_any_order),
        ("interval.lower_above_upper",),
    ),
    Mutant(
        "both_bounds_none_allowed",
        ONE_FAULT,
        own_member("interval", _two_nones_as_one),
        ("interval.both_none",),
    ),
    Mutant(
        "equal_bounds_refused",
        ONE_FAULT,
        own_member("interval", _strictly_ordered),
        ("interval.bounds_equal",),
    ),
    Mutant(
        "minus_zero_below_zero",
        ONE_FAULT,
        own_member("interval", _ordered_by_sign),
        ("interval.zero_and_minus_zero",),
    ),
    Mutant(
        "bound_any_status",
        ONE_FAULT,
        setting(fields, "INTERVAL_BOUND", BOUND_ANY_STATUS),
        ("interval.bound_status_not_allowed",),
    ),
    Mutant(
        "interval_basis_any_string",
        ONE_FAULT,
        setting(fields, "INTERVAL_BASIS", value_shapes.string),
        ("interval_tokens.basis_unknown",),
    ),
    Mutant(
        "composition_basis_any_string",
        ONE_FAULT,
        setting(fields, "COMPOSITION_BASIS", value_shapes.string),
        ("composition_tokens.basis_unknown",),
    ),
    Mutant(
        "sum_rule_any_string",
        ONE_FAULT,
        setting(fields, "SUM_RULE", value_shapes.string),
        ("composition_tokens.sum_rule_unknown",),
    ),
    Mutant(
        "composition_basis_off_its_row_read",
        ONE_FAULT,
        setting(fields, "_basis_allowed", _every_basis_allowed),
        ("composition_tokens.basis_not_its_rows",),
    ),
    Mutant(
        "empty_components_allowed",
        ONE_FAULT,
        setting(fields, "components", _components_may_be_empty),
        ("composition.components_empty",),
    ),
    Mutant(
        "component_twice_allowed",
        ONE_FAULT,
        setting(fields, "components", _each_component_once),
        ("composition.component_repeated",),
    ),
    Mutant(
        "fraction_any_number",
        ONE_FAULT,
        setting(fields, "COMPONENT", {**fields.COMPONENT, "fraction": _any_number}),
        ("composition.fraction_above_one", "composition.fraction_negative"),
    ),
    Mutant(
        "fraction_neither_zero_nor_one",
        ONE_FAULT,
        setting(fields, "COMPONENT", {**fields.COMPONENT, "fraction": _within_zero_and_one_open}),
        ("composition.fractions_zero_and_one",),
    ),
    Mutant(
        "element_by_pattern",
        ONE_FAULT,
        setting(fields, "COMPONENT", {**fields.COMPONENT, "component": _an_element_by_pattern}),
        ("component.element_unknown",),
    ),
    Mutant(
        "component_statistics_unchecked",
        ONE_FAULT,
        setting(fields, "COMPONENT_STATISTICS", _any),
        (
            "component.statistics_count_not_whole",
            "component.statistics_central_unknown",
            "component.statistics_status_not_allowed",
            "component.statistics_represents_missing",
        ),
    ),
    Mutant(
        "stated_sum_any",
        ONE_FAULT,
        setting(fields, "number", _any),
        ("composition.stated_sum_not_a_number",),
    ),
    Mutant(
        "sums_checked_at_read",
        ONE_FAULT,
        own_member("composition", _sums_checked),
        ("composition.sum_unflagged",),
    ),
    Mutant("unknown_members_refused_in_an_own_member", IGNORANCE, _unknown_members_refused_in_an_own_member),
    # S2b-1's review (L3): a bound's status object of any token read as `none`, and a repeated component found
    # only where it follows itself.
    Mutant(
        "any_bound_status_read_as_none",
        ONE_FAULT,
        setting(fields, "_none", value_shapes.is_status_object),
        ("interval_tokens.bound_status_unknown",),
    ),
    Mutant(
        "a_repeat_found_only_beside_itself",
        ONE_FAULT,
        setting(fields, "components", _a_repeat_found_only_beside_itself),
        ("composition.component_repeated_apart",),
    ),
    # S2b-2's: evidence's own member (`record_format.md` section 4.3), each rule HP3's catalogue holds a fault
    # for.
    Mutant(
        "every_report_withheld_read_as_some",
        ONE_FAULT,
        evidence_with(_withheld_read_as("withheld", "entries_withheld")),
        ("evidence_list.every_report_withheld",),
    ),
    Mutant(
        "some_reports_withheld_read_as_every",
        ONE_FAULT,
        evidence_with(_withheld_read_as("entries_withheld", "withheld")),
        ("evidence_list.one_more_report_withheld",),
    ),
    Mutant(
        "an_empty_list_taken",
        ONE_FAULT,
        evidence_with(_an_empty_list_taken),
        ("evidence_list.list_empty",),
    ),
    Mutant(
        "a_status_list_read_as_withheld",
        ONE_FAULT,
        evidence_with(_a_status_read_as_withheld),
        ("evidence_list.list_a_status",),
    ),
    Mutant(
        "a_report_withheld_in_part_taken",
        ONE_FAULT,
        entries_with(lambda reason: "withholding" not in str(reason.detail)),
        ("evidence_list.report_withheld_in_part", "evidence_list.withheld_report_opened"),
    ),
    Mutant(
        "a_report_member_optional",
        ONE_FAULT,
        entries_with(lambda reason: " holds no " not in str(reason.detail)),
        ("evidence_report.member_missing",),
    ),
    Mutant(
        "a_reports_provenance_unchecked",
        ONE_FAULT,
        setting(fields, "provenance", _any),
        (
            "evidence_provenance.origin_unknown",
            "evidence_provenance.origin_missing",
            "evidence_provenance.source_key_not_a_string",
            "evidence_provenance.source_missing_for_its_origin",
            "evidence_provenance.derivation_missing",
            "evidence_provenance.not_an_object",
        ),
    ),
    Mutant(
        "a_years_fraction_taken",
        ONE_FAULT,
        setting(fields, "whole", value_shapes.number),
        ("evidence_report.standard_year_not_whole",),
    ),
    Mutant(
        "a_registered_condition_taken_under_evidence",
        ONE_FAULT,
        setting(fields, "_no_registered_condition", _registered_conditions_taken),
        ("evidence_field.registered_condition", "evidence_field.registered_condition_unstated"),
    ),
    Mutant("unknown_members_refused_in_a_report", "HP5 in a report", _unknown_members_refused_in_a_report),
]


def kill(examples: st.SearchStrategy[Any], check: Callable[[Any], None]) -> tuple[int, str]:
    """The examples searched until `check` first fails, and its message; an AssertionError where it never
    does. Hypothesis runs the failing example once more to report it, which is not counted."""
    tried = 0
    first: list[tuple[int, str]] = []

    @MUTANT_SEARCH
    @given(examples)
    def search(example: Any) -> None:
        nonlocal tried
        tried += 1
        try:
            check(example)
        except AssertionError as error:
            first.append((tried, str(error)))
            raise

    try:
        search()
    except AssertionError:
        return first[0]
    raise AssertionError(f"the mutant survived {tried} examples")


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At one of the faults it names, where it names some: its search is then planned, HP3 drawing its first
    fault among them, and HP3's message is the faults of the example that kills it."""
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    drawn = strategies.faulty_records(size, among=mutant.dies_at) if mutant.dies_at else examples(size)
    tried, message = kill(drawn, check)
    record_property("examples_to_kill", tried)
    assert not mutant.dies_at or any(repr(fault) in message for fault in mutant.dies_at), message
