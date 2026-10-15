# SPDX-License-Identifier: Apache-2.0
"""A record's value fields (`record_format.md` sections 5 and 6): finding the field a read names (step 7 of
`read_side_contract.md` section 3) and checking its form and shape (step 8).

Step 8 checks the form token against the field's row, a composition's basis included, then the members every
form shares (`value_shapes.py`), then the form's own member, where the row allows the form. Only a constant's
is read so far: a table, an interval, a composition or evidence the row allows raises `NotImplementedError`,
whatever the other members hold, rather than give an answer its own member could add a reason to (every reason
found is reported, `read_side_contract.md` section 2 item 2). A form the row does not allow is refused
whatever its own member holds, which the read neither uses nor returns.
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
    number,
    or_status,
    record_problems,
    section_problems,
    unknown_token,
)
from materica.core.vocabulary import VOCABULARY, RecordFieldSpec

# The forms whose own member step 8 reads so far; another form a row allows waits for a step not built yet.
FORMS_READ = ("constant",)


@dataclass(frozen=True)
class RecordField:
    """A value field as stored, never mutated, with the section it sits in and its row of `record_format.md`
    section 4.1."""

    spec: RecordFieldSpec
    value: JsonValue
    section: JsonObject


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


def form_problems(field: RecordField, record: JsonObject, claims: Collection[str]) -> Found:
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
    field: JsonObject, spec: RecordFieldSpec, claims: Collection[str], found: Found
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


def _object(value: JsonValue) -> JsonObject:
    """`value`, which step 3 found to be an object: the body of a material, its `sections`, a known section
    and its `fields`."""
    if not isinstance(value, dict):
        raise TypeError(f"step 3 lets through no {type(value).__name__} here")
    return value
