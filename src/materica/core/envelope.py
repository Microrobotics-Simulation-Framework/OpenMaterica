# SPDX-License-Identifier: Apache-2.0
"""The reader schema's checks, written by hand (`record_format.md` section 1 item 2), so that the core reads
records with no JSON Schema validator.

`schema/0.1/record.reader.json` states the same checks for other languages. Tests hold the two to agreement,
on every conformance input and on records drawn near each boundary of the item.
"""

from materica.core.identifiers import CONTENT_HASH, RECORD_ID, VERSION, Version
from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY

SCHEMA_VERSION = Version("0", "1", "0")
"""The schema version these checks are the reader schema of."""

Members = dict[str, type[object]]

_KINDS: dict[type[object], str] = {str: "a string", dict: "an object"}
_ENVELOPE: Members = {
    "schema_version": str,
    "record_type": str,
    "id": str,
    "version": str,
    "name": str,
    "licence": dict,
    "content_hash": str,
    "body": dict,
}
_PATTERNS = {"id": RECORD_ID, "version": VERSION, "content_hash": CONTENT_HASH}


def envelope_problems(record: JsonValue) -> list[str]:
    """Each way `record` breaks the reader schema of schema 0.1, in words: none where it passes.

    The body is checked by its `record_type`: a material's sections, as far as this version knows them, and an
    overlay's members. A body of another type, a section of another name, `extensions`' contents, a section's
    `specimen` and every value field are left unchecked.
    """
    if not isinstance(record, dict):
        return ["the record is not an object"]
    problems = _members(record, "", _ENVELOPE, {"card": str})
    for name, pattern in _PATTERNS.items():
        value = record.get(name)
        if isinstance(value, str) and not pattern.fullmatch(value):
            problems.append(f"{name} does not match its pattern: {value!r}")
    licence, body = record.get("licence"), record.get("body")
    if isinstance(licence, dict):
        problems += _members(licence, "licence.", {"values": str, "evidence": str})
    if isinstance(body, dict) and record.get("record_type") == "material":
        problems += _material_body(body)
    elif isinstance(body, dict) and record.get("record_type") == "overlay":
        problems += _overlay_body(body)
    return problems


def _material_body(body: dict[str, JsonValue]) -> list[str]:
    problems = _members(body, "body.", {"sections": dict}, {"extensions": dict})
    sections = body.get("sections")
    if isinstance(sections, dict):
        for name in sorted(VOCABULARY.sections & sections.keys()):
            section = sections[name]
            if isinstance(section, dict):
                problems += _members(section, f"body.sections.{name}.", {"fields": dict})
            else:
                problems.append(f"body.sections.{name} is not an object")
    return problems


def _overlay_body(body: dict[str, JsonValue]) -> list[str]:
    problems = _members(body, "body.", {"purpose": str, "base": dict, "scope": dict, "replaces": dict})
    base, scope = body.get("base"), body.get("scope")
    if isinstance(base, dict):
        problems += _members(base, "body.base.", {"id": str, "version": str, "content_hash": str})
    if isinstance(scope, dict):
        optional: Members = {"model": dict, "model_configuration_hash": str, "run": str}
        problems += _members(scope, "body.scope.", {"consumer": str}, optional)
        model = scope.get("model")
        if isinstance(model, dict):
            problems += _members(model, "body.scope.model.", {"name": str, "version": str})
    return problems


def _members(
    value: dict[str, JsonValue], where: str, required: Members, optional: Members | None = None
) -> list[str]:
    problems: list[str] = []
    for name, kind in (required | (optional or {})).items():
        if name not in value:
            if name in required:
                problems.append(f"{where}{name} is missing")
        elif not isinstance(value[name], kind):
            problems.append(f"{where}{name} is not {_KINDS[kind]}")
    return problems
