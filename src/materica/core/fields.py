# SPDX-License-Identifier: Apache-2.0
"""A record's value fields (`record_format.md` sections 5 and 6): finding the field a read names (step 7 of
`read_side_contract.md` section 3) and checking its form and shape (step 8).

Step 8 checks the form token against the field's row, then the members every form shares (`value_shapes.py`),
then the form's own member. Only a constant's is read so far: a table, an interval, a composition and evidence
raise `NotImplementedError` once the shared checks find nothing, rather than give an answer their own member
could change. A form no row of schema 0.1 allows is refused whatever its member holds.
"""

from collections.abc import Collection
from dataclasses import dataclass

from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.value_shapes import (
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

# The forms whose own member a step not built yet reads.
FORMS_NOT_READ_YET = ("table", "interval", "composition", "evidence")


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
    """Step 8: every reason the record's structure, the field's section and the field give, or
    `NotImplementedError` where they give none and the form's own member waits for a step not built yet."""
    found = record_problems(record) + section_problems(field.spec.section, field.section)
    if not isinstance(field.value, dict):
        return [*found, invalid(f"{field.spec.name} is not an object")]
    form = _form(field.value, field.spec, claims, found)
    found += field_problems(field.value, field.spec, form)
    if form in FORMS_NOT_READ_YET and not found:
        raise NotImplementedError(f"the member of a field of form {form} is not read yet")
    if form == "constant":
        _constant(field.value, field.spec.name, found)
    return found


def _form(field: JsonObject, spec: RecordFieldSpec, claims: Collection[str], found: Found) -> str | None:
    """The field's form, where it is a token the reader knows, whether or not its row allows it."""
    form = field.get("form")
    where = f"{spec.name}.form"
    if "form" not in field or not isinstance(form, str):
        found.append(invalid(f"{where} is missing or not a string"))
        return None
    if form not in VOCABULARY.token_lists["form"]:
        found.append(unknown_token(f"{where} holds {form!r}, which the reader knows for no form"))
        return None
    if form not in spec.forms:
        found.append(Reason("form_not_registered", detail=f"{where} is {form}, which its row does not allow"))
    if form == "parameter_set" and "family_evaluation" not in claims:
        found.append(Reason("family_suite_absent", detail=f"{where} is a parameter set"))
    return form


def _constant(field: JsonObject, name: str, found: Found) -> None:
    """A constant's `value`: a number, or `withheld` in a reference-only value (`provenance.md` section 7)."""
    if "value" not in field:
        found.append(invalid(f"{name} holds no value"))
        return
    value = field["value"]
    before = len(found)
    or_status(number, ("withheld",))(value, f"{name}.value", found)
    if isinstance(value, dict) and value.get("status") == "withheld" and len(found) == before:
        found.append(Reason("withheld", detail=f"{name} is a reference-only value"))


def _object(value: JsonValue) -> JsonObject:
    """`value`, which step 3 found to be an object: the body of a material, its `sections`, a known section
    and its `fields`."""
    if not isinstance(value, dict):
        raise TypeError(f"step 3 lets through no {type(value).__name__} here")
    return value
