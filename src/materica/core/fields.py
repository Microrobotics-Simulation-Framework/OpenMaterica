# SPDX-License-Identifier: Apache-2.0
"""A record's value fields (`record_format.md` sections 5 and 6): finding the field a read names (step 7 of
`read_side_contract.md` section 3), checking its form and shape (step 8) and its units (step 9).

Step 8 checks the form token against the field's row, a composition's basis included, then the members every
form shares (`value_shapes.py`), then the form's own member, where the row allows the form. Only a constant's
is read so far: a table, an interval, a composition or evidence the row allows raises `NotImplementedError`,
whatever the other members hold, rather than give an answer its own member could add a reason to (every reason
found is reported, `read_side_contract.md` section 2 item 2). A form the row does not allow is refused
whatever its own member holds, which the read neither uses nor returns.

Step 9 compares each unit the field states with the one registered for it, code point for code point, as
step 0 does a request's, and a unit registered as a status object by its token (`record_format.md` section
4.2): none is parsed or converted.
"""

from collections.abc import Collection
from dataclasses import dataclass

from materica import shapes
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.value_shapes import (
    FORM_MEMBERS,
    Found,
    JsonObject,
    field_problems,
    invalid,
    is_status_object,
    number,
    or_status,
    record_problems,
    section_problems,
    unknown_token,
)
from materica.core.vocabulary import VOCABULARY, RecordFieldSpec
from materica.shapes import Suite

# The forms whose own member step 8 reads so far; another form a row allows waits for a step not built yet.
FORMS_READ = ("constant",)


@dataclass(frozen=True)
class RecordField:
    """A value field as stored, never mutated, with the section it sits in and its row of `record_format.md`
    section 4.1."""

    spec: RecordFieldSpec
    value: JsonValue
    section: JsonObject

    def specimen(self) -> JsonObject:
        """The specimen facts of a field that passed step 8: the section's, each overridden by the field's
        fact of that name (`record_format.md` section 4 item 2)."""
        value = _object(self.value)
        return {**_object(self.section.get("specimen", {})), **_object(value.get("specimen", {}))}


def find_field(record: JsonObject, spec: RecordFieldSpec) -> RecordField | Reason:
    """Step 7: the field `spec` names, in a material record that passed step 3, or `absent`."""
    section_name, _, name = spec.name.partition(".")
    sections = _object(_object(record["body"])["sections"])
    if section_name not in sections:
        return Reason("absent", detail=f"the record holds no section {section_name}")
    section = _object(sections[section_name])
    fields = _object(section["fields"])
    if name not in fields:
        return Reason("absent", detail=f"the section {section_name} holds no field {name}")
    return RecordField(spec, fields[name], section)


def form_problems(field: RecordField, record: JsonObject, claims: Collection[Suite]) -> Found:
    """Step 8: every reason the record's structure, the field's section and the field give; or
    `NotImplementedError` where the row allows the field's form and that form's own member waits for a step
    not built yet, whatever the rest holds."""
    found = record_problems(record) + section_problems(field.spec.section, field.section)
    if not isinstance(field.value, dict):
        return [*found, invalid(f"{field.spec.name} is not an object")]
    form, allowed = _form(field.value, field.spec, claims, found)
    if allowed and form not in FORMS_READ:
        raise NotImplementedError(f"the member of a field of form {form} is not read yet")
    found += field_problems(field.value, field.spec, form)
    if form == "constant" and allowed:
        _constant(field.value, field.spec.name, found)
    return found


def _form(
    field: JsonObject, spec: RecordFieldSpec, claims: Collection[Suite], found: Found
) -> tuple[str | None, bool]:
    """The field's form, where it is a token the reader knows, and whether its row allows it, a composition's
    basis included (`record_format.md` section 4.1)."""
    form = field.get("form")
    where = f"{spec.name}.form"
    if "form" not in field or not isinstance(form, str):
        found.append(invalid(f"{where} is missing or not a string"))
        return None, False
    if form not in VOCABULARY.token_lists["form"]:
        found.append(unknown_token(f"{where} holds {form!r}, which the reader knows for no form"))
        return None, False
    if form not in spec.forms:
        found.append(Reason("form_not_registered", detail=f"{where} is {form}, which its row does not allow"))
    if form == "parameter_set" and "family_evaluation" not in claims:
        found.append(Reason("family_suite_absent", detail=f"{where} is a parameter set"))
    return form, form in spec.forms and _basis_allowed(field, spec, form, found)


def _basis_allowed(field: JsonObject, spec: RecordFieldSpec, form: str, found: Found) -> bool:
    """Whether the basis of a form whose bases the row restricts (`composition (basis `mass_fraction`)`) is
    one the row allows. A basis of the form's own list that the row does not allow is `form_not_registered`;
    any other basis, or none, is the form's own member's to judge."""
    allowed = spec.bases.get(form)
    member = field.get(FORM_MEMBERS[form])
    basis = member.get("basis") if isinstance(member, dict) else None
    if allowed is None or basis not in VOCABULARY.token_lists.get(f"{form}_basis", ()) or basis in allowed:
        return True
    where = f"{spec.name}.{FORM_MEMBERS[form]}.basis"
    found.append(Reason("form_not_registered", detail=f"{where} is {basis}, which its row does not allow"))
    return False


def _constant(field: JsonObject, name: str, found: Found) -> None:
    """A constant's `value`: a number, or `withheld` in a reference-only value (`provenance.md` section 7)."""
    if "value" not in field:
        found.append(invalid(f"{name} holds no value"))
        return
    value = field["value"]
    before = len(found)
    or_status(number, shapes.ConstantField, "value")(value, f"{name}.value", found)
    if isinstance(value, dict) and value.get("status") == "withheld" and len(found) == before:
        found.append(Reason("withheld", detail=f"{name} is a reference-only value"))


def same_unit(stored: JsonValue, registered: JsonValue) -> bool:
    """`record_format.md` section 4.2: a string equal to the registered one code point for code point, or,
    where a status object is registered, a status object holding its `status` token, whatever its `reason`."""
    if isinstance(registered, dict):
        return is_status_object(stored) and _object(stored)["status"] == registered["status"]
    return isinstance(stored, str) and stored == registered


def unit_problems(field: RecordField) -> Found:
    """Step 9, for a field that passed step 8 (`read_side_contract.md` section 3): `unit_mismatch` for each
    unit other than the one registered for it: the field's; a known numeric condition's and its `plus_minus`
    entries', with that condition; a `unit` on a token condition, which registers none, with that condition;
    and a specimen fact's, against the unit its row fixes, wherever step 8 checks the fact (the section's
    specimen, the field's, and a derived value's inputs')."""
    value = _object(field.value)
    found: Found = []
    _compare_unit(value["unit"], field.spec.unit, f"{field.spec.name}.unit", None, found)
    for name, condition in _object(value["conditions"]).items():
        spec = VOCABULARY.conditions.get(name)
        if spec is None or is_status_object(condition):
            continue
        held = _object(condition)
        where = f"{field.spec.name}.conditions.{name}"
        if spec.unit is None:
            if "unit" in held:
                found.append(
                    _mismatch(f"{where} holds a unit, which a token condition does not register", name)
                )
            continue
        _compare_unit(held["unit"], spec.unit, f"{where}.unit", name, found)
        for index, entry in enumerate(_list(held.get("plus_minus", []))):
            _compare_unit(_object(entry)["unit"], spec.unit, f"{where}.plus_minus[{index}].unit", name, found)
    for where, specimen in _specimens(field):
        for name, fact in specimen.items():
            unit = VOCABULARY.facts[name].fixed.get("unit") if name in VOCABULARY.facts else None
            if unit is not None and not is_status_object(fact):
                _compare_unit(_object(fact)["unit"], unit, f"{where}.{name}.unit", None, found)
    return found


def _compare_unit(
    stored: JsonValue, registered: JsonValue, where: str, condition: str | None, found: Found
) -> None:
    if not same_unit(stored, registered):
        found.append(_mismatch(f"{where} is {stored!a}, not the registered {registered!a}", condition))


def _mismatch(detail: str, condition: str | None) -> Reason:
    return Reason("unit_mismatch", condition, detail)


def _specimens(field: RecordField) -> list[tuple[str, JsonObject]]:
    """Each specimen step 8 checks for `field`, and where it is: the section's, the field's, and a derived
    value's inputs'."""
    value = _object(field.value)
    section = field.spec.section
    found = [
        (where, _object(holder["specimen"]))
        for where, holder in (
            (f"body.sections.{section}.specimen", field.section),
            (f"{field.spec.name}.specimen", value),
        )
        if "specimen" in holder
    ]
    provenance = _object(value["provenance"])
    if provenance["origin"] == "derived":
        inputs = _list(_object(provenance["derivation"])["input_specimens"])
        found += [
            (
                f"{field.spec.name}.provenance.derivation.input_specimens[{index}].specimen",
                _object(_object(item)["specimen"]),
            )
            for index, item in enumerate(inputs)
        ]
    return found


def _list(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError(f"step 8 lets through no {type(value).__name__} here")
    return value


def _object(value: JsonValue) -> JsonObject:
    """`value`, which step 3 or step 8 found to be an object: the body of a material, its `sections`, a known
    section and its `fields`; a field that passed step 8 and the objects in it."""
    if not isinstance(value, dict):
        raise TypeError(f"steps 3 and 8 let through no {type(value).__name__} here")
    return value
