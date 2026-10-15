# SPDX-License-Identifier: Apache-2.0
"""T1 (the S2 design, section 1.7): step 8's shapes, written by hand in `core/value_shapes.py` and
`core/fields.py`, against the writer schema's value-field `$defs` and the reader `$defs` generated from them.
Where a form's own member waits for a step not built yet (an interval, a composition, evidence, a table, which
`form_problems` will not answer), the "step 8 verdict" is not the code's: it is what the case files reading
that field expect, and with no such case file there is none. A table has none yet: the writer schema holds its
member as a placeholder until S3a writes it, and with it T1 on the table fixtures (the S3 design, section
6.5). So for 51 conformance examples, and for every variant of a drawn base of those forms, T1 holds the data
to the schemas, not step 8; it holds step 8 itself on the constants and on the forms a row does not allow.

It runs on every value field a registered field's row reads, with its section's `specimen`, in every material
record among the conformance inputs, and on one-fault variants of its bases: the full fields of
`tests/property/full_fields.py`, and one field of each row and each form it allows, drawn by the writer's
strategies (`tests/property/value_fields.py`), derandomised, so that every row's binding is varied. A variant
removes each member and list item, makes it `null` or gives it another JSON type, or renames a member by one
slip; a path two bases share is changed in the first. Since a read checks some members of a provenance object
by its origin (a `derivation` for origin `derived` alone), each provenance object of each base also takes each
other token of the origin's row, alone and beside each change inside it. Each example gets three verdicts:
- the writer schema's, which accepts where it accepts the field and the section's specimen;
- the reader `$defs`', alike;
- step 8's, read in the field's own record (so a slip in its envelope or section counts), which accepts where
  it gives none of `form_invalid`, `unknown_token` and `form_not_registered`. A `withheld` value is a refusal
  to read, not of a shape, and `family_suite_absent` follows the claims. Where a form's own member waits for a
  step not built yet, the verdict is as above: the case files' step-8 reasons where they end at step 8,
  acceptance where they end later.
Three relations hold, each but for listed exceptions:
1. what the writer schema accepts, step 8 accepts;
2. what step 8 refuses with `form_invalid`, the reader `$defs` refuse;
3. what the reader `$defs` refuse, step 8 refuses.
The design states the first two; the third is their converse, without which a step 8 that checks too little
would pass. The writer's verdict includes the binding of the field to its row (`vocabulary/fields.json`),
which the reader `$defs` leave out. The exceptions are grouped by kind (`EXCEPTIONS`), each with the reason no
JSON Schema states its rule here, a mark that shows a refusal is of the kind, and, by relation, the case files
whose read field breaks it; a field no case file reads, and a variant, is named instead. A variant renamed by
one slip is excepted from relation 2 by its change, since no schema sees a slip. Everything is computed from
the generated files when the test runs: a relation broken with no exception fails, and so do an exception
whose relation holds, as stale, and one whose refusal does not show its kind's mark. The origin variants'
control is the reader `$defs` of b8a597d, which checked a derivation beside every origin.
"""

import copy
import json
import re
from collections.abc import Callable, Iterator, Mapping
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import pytest
from hypothesis import Phase, given, settings
from referencing.jsonschema import DRAFT202012

from materica.core import jsonio
from materica.core.fields import RecordField, form_problems
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.value_shapes import BOUND
from materica.core.vocabulary import VOCABULARY
from scripts import gen_reader_schema
from tests.conformance import runner
from tests.property import value_fields
from tests.property.full_fields import full_fields, record_of
from tests.property.strategies import SMALL
from tests.spec_sync.schemas import REGISTRY, SCHEMA, validator
from tests.spec_sync.test_cases_md import sections

JsonObject = dict[str, JsonValue]
INPUTS = sorted(runner.CONFORMANCE.glob("*/inputs/*"))
REFUSALS = frozenset({"form_invalid", "unknown_token", "form_not_registered"})


class Kind(NamedTuple):
    """A kind of exception: why no JSON Schema states its rule here, and, by relation, the case files whose
    read field breaks it and the examples no case file reads that do; and `mark`, what shows a refusal is of
    this kind, in the details of step 8's reasons, or, where step 8 does not read the field yet, in the arm
    of the case file that reads it (`CASES.md`)."""

    reason: str
    case_files: Mapping[int, tuple[str, ...]]
    examples: Mapping[int, tuple[str, ...]] = MappingProxyType({})
    mark: str = ""  # a regular expression


# For relation 2, S2a-1's 48 case files the reader `$defs` cannot refuse; for relation 1, the 12 of the
# review's 42 the writer still accepts once it binds each field to its row (the maintainer's ruling,
# 2026-10-15), PR-036's forms and PR-053's labels no longer among them. A variant renamed by one slip is
# excepted from relation 2 by its change.
EXCEPTIONS: dict[str, Kind] = {
    "slip": Kind(
        "a member one slip from a member named at its place (`record_format.md` section 10 item 5), in the "
        "field or in its record's envelope, body or section, which the value-field `$defs` do not see: a "
        "schema lists the names it allows, not the names near them",
        {
            1: (
                "PR-005.near_typo_crad",
                "PR-008.near_typo_section_fluids",
                "PR-008.near_typo_section_refuses_other_section",
                "PR-030.near_typo_body_extension",
                "PR-030.near_typo_field_name_dynamic_viscosty",
                "PR-030.near_typo_section_specimens",
            ),
            2: (
                "PR-005.near_typo_crad",
                "PR-008.near_typo_section_fluids",
                "PR-008.near_typo_section_refuses_other_section",
                "PR-030.near_typo_body_extension",
                "PR-030.near_typo_composition_stated_sums",
                "PR-030.near_typo_derivation_mixed_condition",
                "PR-030.near_typo_field_name_dynamic_viscosty",
                "PR-030.near_typo_field_specimne",
                "PR-030.near_typo_in_component",
                "PR-030.near_typo_in_derivation_input",
                "PR-030.near_typo_in_derivation_input_record",
                "PR-030.near_typo_in_evidence_entry",
                "PR-030.near_typo_in_fact_texts",
                "PR-030.near_typo_in_input_specimens_entry",
                "PR-030.near_typo_in_interval",
                "PR-030.near_typo_in_population_level",
                "PR-030.near_typo_in_provenance_sources",
                "PR-030.near_typo_in_source_keys",
                "PR-030.near_typo_in_standard",
                "PR-030.near_typo_in_statistics_means",
                "PR-030.near_typo_in_status_object",
                "PR-030.near_typo_in_uncertainty",
                "PR-030.near_typo_section_fact_tissue_stat",
                "PR-030.near_typo_section_specimens",
                "PR-108.near_typo_in_plus_minus_entry",
                "PR-108.near_typo_plus_minsu",
            ),
        },
        # The fluid field beside the one PR-008's case reads: the section's slip refuses it too.
        {
            1: ("water_near_typo_section_fluids_with_bulk fluid.dynamic_viscosity",),
            2: ("water_near_typo_section_fluids_with_bulk fluid.dynamic_viscosity",),
        },
        mark=r"one slip from",
    ),
    "range_order": Kind(
        "a range's or an interval's lower end above its upper: a schema does not compare members",
        {
            1: ("PR-045.condition_range_reversed", "PR-045.fact_range_reversed", "PR-050.lower_above_upper"),
            2: ("PR-045.condition_range_reversed", "PR-045.fact_range_reversed", "PR-050.lower_above_upper"),
        },
        mark=r"lo above hi|`lower` \d+ above `upper`",
    ),
    "input_index": Kind(
        "an `input_specimens` entry's `input` past the last input: a schema does not compare a member with "
        "the length of another",
        {
            1: ("PR-102.derivation_input_specimen_index_out_of_range",),
            2: ("PR-102.derivation_input_specimen_index_out_of_range",),
        },
        {
            1: (
                "across_sources removed provenance.derivation.inputs.0",
                "across_sources removed provenance.derivation.inputs.1",
            ),
            2: (
                "across_sources removed provenance.derivation.inputs.0",
                "across_sources removed provenance.derivation.inputs.1",
            ),
        },
        mark=r"past the last input",
    ),
    "repeated_component": Kind(
        "a composition naming one component twice: a schema does not compare list items' members",
        {1: ("PR-051.repeated_component",), 2: ("PR-051.repeated_component",)},
        mark=r"twice",
    ),
    "row_label": Kind(
        "a label the field's row does not name for the field and its form: the reader `$defs` leave the "
        "row's binding out, and the writer's binds the label to the field but not to its form",
        {
            1: ("PR-053.newtonian_label_on_interval",),
            2: (
                "PR-053.label_not_named_for_field",
                "PR-053.linear_label_on_viscosity",
                "PR-053.newtonian_label_on_interval",
            ),
        },
        mark=r"does not name for|names only on",
    ),
    "row_token": Kind(
        "a token the reader knows, in a member whose row does not allow it: the reader `$defs` take any "
        "string where the writer lists tokens, so that an unknown token is `unknown_token`",
        {
            2: (
                "PR-045.condition_token_of_another_row",
                "PR-154.student_t_in_block",
                "PR-154.uniform_in_block",
                "PR-158.reported_uncertainty_in_block_basis",
                "PR-158.uncertainty_represents_population",
            ),
        },
        mark=r"holds '[^']*', a token its row does not allow",
    ),
    "row_condition": Kind(
        "a registered condition under evidence: the reader `$defs` take any member of `conditions` there, "
        "where step 8 refuses a registered name and gives `unknown` for another",
        {2: ("PR-052.registered_condition_in_conditions",)},
        mark=r"a registered condition",
    ),
    "status_beside": Kind(
        "an object holding `status` beside a member of the shape it stands for, or beside any member where "
        "a number, string or token belongs (`provenance.md` section 1 item 5): the reader `$defs` allow "
        "members they do not name",
        {
            2: (
                "PR-110.condition_status_beside_basis",
                "PR-110.condition_status_beside_unit",
                "PR-110.evidence_unit_status_beside_other_member",
                "PR-110.interval_upper_status_beside_other_member",
                "PR-110.sd_status_beside_other_member",
            ),
        },
        mark=r"beside its status|a status object beside",
    ),
    "status_token": Kind(
        "a status token the member's row does not allow: the reader `$defs` take any string as a status",
        {2: ("PR-110.constant_value_unstated", "PR-110.interval_member_none")},
        mark=(
            r"holds the status '[a-z_]+', which its row does not allow"
            r'|`\{"status": "[a-z_]+"\}`, a token its row does not allow'
        ),
    ),
    "withheld_in_part": Kind(
        "an evidence entry withholding some of its members but not every one: the reader `$defs` take any "
        "status there",
        {2: ("PR-052.entry_partly_withheld",)},
        mark=r"withholding",
    ),
}

# A variant renamed by one slip is the kind `slip` for relation 2, by construction.
SLIPPED = "slip"


class Example(NamedTuple):
    name: str  # the input and the field, or the full field, the change and the path
    field: str  # the registered field read
    value: JsonValue
    section: JsonObject  # the section it sits in, its `specimen` and the names of its fields
    record: JsonObject
    change: str = ""  # a variant's change
    origin: str = ""  # the token a variant's change sets its provenance object's origin to


# Step 8's verdict on an example: the codes it gives, or None where it has none.
Verdict = Callable[[Example], frozenset[str] | None]


@cache
def readers() -> dict[str, list[tuple[str, frozenset[str] | None]]]:
    """For each example a case file reads, named by its input and field, each such case file and the step-8
    verdict it expects: its reasons where it ends at step 8, none where it ends later, and None where it ends
    earlier."""
    ends = {
        f"{case}.{row['Variant'].strip('`')}.json": row["Ends at"]
        for case, (_, _, rows) in sections("plain_read").items()
        for row in rows
    }
    found: dict[str, list[tuple[str, frozenset[str] | None]]] = {}
    for case_file in runner.discover():
        target = case_file.request.get("target") if isinstance(case_file.request, dict) else None
        if case_file.operation != "read" or not isinstance(target, dict) or case_file.suite != "plain_read":
            continue
        pin, field = target.get("record"), target.get("field")
        end = ends[case_file.path.name]
        reasons = case_file.expected["reasons"]
        assert isinstance(reasons, list)
        codes = frozenset(str(reason["code"]) for reason in reasons if isinstance(reason, dict))
        verdict = codes if end == "8" else frozenset[str]() if end.isdigit() and int(end) > 8 else None
        for path in case_file.input_paths("records"):
            record = parsed(path)
            if isinstance(record, dict) and isinstance(pin, dict) and isinstance(field, str):
                if all(record.get(name) == pin.get(name) for name in ("id", "version", "content_hash")):
                    found.setdefault(f"{path.stem} {field}", []).append((case_file.path.stem, verdict))
    return found


def step_8(example: Example) -> frozenset[str] | None:
    spec = VOCABULARY.fields[example.field]
    try:
        found = form_problems(
            RecordField(spec, example.value, example.section), example.record, {"plain_read"}
        )
    except NotImplementedError:
        if field_shape(example.value) == "table_field":
            return None
        expected = [verdict for _, verdict in readers().get(example.name, []) if verdict is not None]
        return frozenset[str]().union(*expected) if expected else None
    return frozenset(reason.code for reason in found)


FORMS = VOCABULARY.token_lists["form"]
SHAPES = ("value_field", "specimen", *(f"{form}_field" for form in FORMS))
Validators = dict[str, Callable[[JsonValue], list[str]]]
WRITER: Validators = {shape: validator(f"record.writer.json#/$defs/{shape}") for shape in SHAPES}
READER: Validators = {shape: validator(f"record.reader.json#/$defs/{shape}") for shape in SHAPES}
# The reader `$defs` as they stood at b8a597d, which applied a derivation's shape beside every origin: what
# `gen_reader_schema.py` gives for the writer schema without the derivation's mark, which was that file but
# for the provenance object's description. T1's control for its origin variants.
BEFORE_THE_CONDITION = "reader before the derivation's condition"


@cache
def reader_before_the_condition() -> Validators:
    writer = json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8"))
    del writer["$defs"]["provenance"]["properties"]["derivation"][gen_reader_schema.WRITE_ONLY]
    reader = gen_reader_schema.reader_schema(writer)
    registry = REGISTRY.with_resource(str(reader["$id"]), DRAFT202012.create_resource(reader))
    return {shape: validator(f"record.reader.json#/$defs/{shape}", registry) for shape in SHAPES}


def validators(schemas: str) -> Validators:
    found: dict[str, Callable[[], Validators]] = {
        "writer": lambda: WRITER,
        "reader": lambda: READER,
        BEFORE_THE_CONDITION: reader_before_the_condition,
    }
    return found[schemas]()


def field_shape(field: JsonValue) -> str:
    """The definition a field is validated against: its form's, where `form` is a form token, which accepts
    exactly what `value_field` accepts there and is eight times faster. Every other form's definition then
    refuses the field by its `form`, and the `alternatives` definition by its holding `form`. Anything else is
    validated against `value_field` itself."""
    form = field.get("form") if isinstance(field, dict) else None
    return f"{form}_field" if form in FORMS else "value_field"


# The writer binds each registered field to its row (its forms, unit and label) where a section holds it, in
# `vocabulary/fields.json`; the reader `$defs` leave the bindings out, since step 8 and 9 check the row.
ROW = {name: validator(f"vocabulary/fields.json#/$defs/{name}") for name in VOCABULARY.fields}


@cache
def accepted(schemas: str, field_name: str, text: str) -> bool:
    """Whether the schemas `schemas` names (`validators`) accept a field of `field_name` and its section's
    specimen, which `text` writes: validating is the slow part, and the controls ask again of the same
    values."""
    field, specimens = json.loads(text)
    checks = validators(schemas)
    bound = schemas != "writer" or not ROW[field_name](field)
    return (
        bound
        and not checks[field_shape(field)](field)
        and not any(checks["specimen"](specimen) for specimen in specimens)
    )


def failed(example: Example, verdict: Verdict, reader: str = "reader") -> list[int]:
    """The relations `example` breaks, by number, the reader `$defs` those `reader` names."""
    codes = verdict(example)
    if codes is None:
        return []
    specimen = [example.section["specimen"]] if "specimen" in example.section else []
    text = json.dumps([example.value, specimen])
    writer, read = accepted("writer", example.field, text), accepted(reader, example.field, text)
    broken: list[int] = []
    if writer and codes & REFUSALS:
        broken.append(1)
    if "form_invalid" in codes and read:
        broken.append(2)
    if not read and not codes & REFUSALS:
        broken.append(3)
    return broken


def excepted(example: Example, relation: int, exceptions: dict[str, Kind]) -> bool:
    """Whether a kind lists `example` for `relation`, by a case file that reads it or by its name; a variant
    renamed by one slip is excepted from relation 2 by its change."""
    if relation == 2 and example.change == SLIPPED:
        return True
    cases = {case for case, _ in readers().get(example.name, [])}
    return any(
        example.name in kind.examples.get(relation, ()) or cases & set(kind.case_files.get(relation, ()))
        for kind in exceptions.values()
    )


def problems(
    examples: list[Example], verdict: Verdict, exceptions: dict[str, Kind], reader: str = "reader"
) -> list[str]:
    """Each relation an example breaks with no exception for it."""
    return [
        f"relation {relation} fails on {example.name}"
        for example in examples
        for relation in failed(example, verdict, reader)
        if not excepted(example, relation, exceptions)
    ]


@cache
def arms() -> dict[str, str]:
    """Each plain-read case file's arm, as its `CASES.md` row states it."""
    return {
        f"{case}.{row['Variant'].strip('`')}": row["Arm"]
        for case, (_, _, rows) in sections("plain_read").items()
        for row in rows
    }


def refusal(example: Example, case: str | None) -> str:
    """What says why step 8 refuses `example`: the details of its reasons, or, where step 8 does not read the
    field yet, the arm of `case`, the case file that reads it."""
    spec = VOCABULARY.fields[example.field]
    try:
        found = form_problems(
            RecordField(spec, example.value, example.section), example.record, {"plain_read"}
        )
    except NotImplementedError:
        return arms()[case] if case is not None else ""
    return "; ".join(str(reason.detail) for reason in found)


def misplaced(examples: list[Example], exceptions: dict[str, Kind]) -> list[str]:
    """Each case file or example a kind lists whose refusal does not show the kind's mark: an exception
    listed under a kind whose reason does not explain it (the maintainer's ruling 3, "grouped by kind, each
    kind with its reason")."""
    by_name = {example.name: example for example in examples}
    found: list[str] = []
    for name, kind in exceptions.items():
        listed: set[tuple[str | None, str | None]] = {
            (case, None) for cases in kind.case_files.values() for case in cases
        }
        listed |= {(None, example) for named in kind.examples.values() for example in named}
        for case, named in sorted(listed, key=str):
            reading = [example for example, cases in readers().items() if case in {c for c, _ in cases}]
            for example in [named] if named is not None else reading:
                if example in by_name and not re.search(kind.mark, refusal(by_name[example], case)):
                    found.append(
                        f"{case or example}: listed under {name}, but its refusal is not of that kind"
                    )
    return found


def stale(examples: list[Example], verdict: Verdict, exceptions: dict[str, Kind]) -> list[str]:
    """Each kind without a reason, and each case file or example a kind lists that is listed twice, reads no
    example, or keeps its relation; an example is listed by name only where no case file reads it."""
    broken = {(example.name, relation) for example in examples for relation in failed(example, verdict)}
    names = {example.name for example in examples}
    read_by: dict[str, set[str]] = {}
    for name, reading in readers().items():
        for case, _ in reading:
            if name in names:
                read_by.setdefault(case, set()).add(name)
    found = [f"{name}: the kind has no reason" for name, kind in exceptions.items() if not kind.reason]
    listed: list[tuple[str, int]] = []
    for kind in exceptions.values():
        for relation, cases in kind.case_files.items():
            listed += [(case, relation) for case in cases]
            for case in cases:
                if case not in read_by:
                    found.append(f"{case}: reads no example")
                elif not any((name, relation) in broken for name in read_by[case]):
                    found.append(f"{case}: relation {relation} holds, so its exception is stale")
        for relation, named in kind.examples.items():
            listed += [(name, relation) for name in named]
            for name in named:
                if name not in names:
                    found.append(f"{name}: no such example")
                elif name in readers():
                    found.append(f"{name}: a case file reads it, so the case file is listed instead")
                elif (name, relation) not in broken:
                    found.append(f"{name}: relation {relation} holds, so its exception is stale")
    found += [
        f"{key[0]}: listed twice for relation {key[1]}"
        for key in sorted(set(listed))
        if listed.count(key) > 1
    ]
    return found


# The examples.


def fields_of(name: str, record: JsonValue) -> Iterator[Example]:
    """Every value field a registered field's row reads in a material record, but one holding alternatives,
    each of which step 7 reads apart."""
    body = record.get("body") if isinstance(record, dict) else None
    sections = body.get("sections") if isinstance(body, dict) else None
    if not (
        isinstance(record, dict) and record.get("record_type") == "material" and isinstance(sections, dict)
    ):
        return
    for section_name, section in sections.items():
        fields = section.get("fields") if isinstance(section, dict) else None
        for field_name, value in fields.items() if isinstance(fields, dict) else ():
            field = f"{section_name}.{field_name}"
            if field in VOCABULARY.fields and not (isinstance(value, dict) and "alternatives" in value):
                assert isinstance(section, dict)
                yield Example(f"{name} {field}", field, value, section, record)


@cache
def input_examples() -> list[Example]:
    found: list[Example] = []
    for path in INPUTS:
        value = parsed(path)
        if not isinstance(value, Reason):
            found += fields_of(path.stem, value)
    return found


@cache
def parsed(path: Path) -> JsonValue | Reason:
    return jsonio.parse(path.read_bytes())


def paths(value: JsonValue, here: tuple[str | int, ...] = ()) -> Iterator[tuple[str | int, ...]]:
    steps: list[tuple[str | int, JsonValue]] = []
    if isinstance(value, dict):
        steps = list(value.items())
    elif isinstance(value, list):
        steps = list(enumerate(value))
    for step, member in steps:
        yield (*here, step)
        yield from paths(member, (*here, step))


def another_type(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return []
    if isinstance(value, list):
        return {}
    return 1.0 if isinstance(value, str) else "x"


def child(value: JsonValue, step: str | int) -> JsonValue:
    """The member or item at `step`, which `paths` found there."""
    if isinstance(value, dict) and isinstance(step, str):
        return value[step]
    assert isinstance(value, list)
    assert isinstance(step, int)
    return value[step]


def fluid_section(record: JsonObject) -> JsonObject:
    section = child(child(child(record, "body"), "sections"), "fluid")
    assert isinstance(section, dict)
    return section


def changed(field: JsonValue, path: tuple[str | int, ...], change: str) -> JsonValue | None:
    """`field` with `change` made at `path`, or None where the change does not apply there."""
    copied = copy.deepcopy(field)
    parent = copied
    for step in path[:-1]:
        parent = child(parent, step)
    last = path[-1]
    if isinstance(parent, dict) and isinstance(last, str):
        if change == SLIPPED:
            parent[last + "x"] = parent.pop(last)
        elif change == "removed":
            del parent[last]
        else:
            parent[last] = None if change == "null" else another_type(parent[last])
    elif isinstance(parent, list) and isinstance(last, int) and change != SLIPPED:
        if change == "removed":
            del parent[last]
        else:
            parent[last] = None if change == "null" else another_type(parent[last])
    else:
        return None
    return copied


CHANGES = ("removed", "null", "retyped", SLIPPED)
# A provenance object's `origin` set to another token of its row: alone, and beside each change inside the
# object, since a read checks some of its members by the origin (a `derivation` for origin `derived`).
ORIGIN = "origin"
ORIGINS = VOCABULARY.token_lists["origin"]
Path_ = tuple[str | int, ...]


def value_at(field: JsonValue, path: Path_) -> JsonValue:
    for step in path:
        field = child(field, step)
    return field


def is_provenance(value: JsonValue) -> bool:
    return isinstance(value, dict) and ORIGIN in value


def provenance_of(field: JsonValue, path: Path_) -> Path_ | None:
    """The path of the innermost provenance object that `path` lies inside, or None where there is none or
    `path` is its `origin`."""
    for end in range(len(path) - 1, -1, -1):
        if is_provenance(value_at(field, path[:end])):
            return path[:end] if path[end] != ORIGIN else None
    return None


def other_origins(field: JsonValue, provenance: Path_) -> list[str]:
    return [token for token in ORIGINS if token != child(value_at(field, provenance), ORIGIN)]


def with_origin(field: JsonValue, provenance: Path_, token: str) -> JsonValue:
    copied = copy.deepcopy(field)
    found = value_at(copied, provenance)
    assert isinstance(found, dict)
    found[ORIGIN] = token
    return copied


# Every part of a field the writer's strategies draw in full where a plan names it.
RICH = frozenset(
    {"block", "uncertainty", "conditions", "specimen", "provenance", "composition", "evidence", "label"}
)


def drawn(name: str, form: str) -> JsonObject:
    """A field of `name`'s row and of `form`, each part in full, as the writer's strategies
    (`tests/property/value_fields.py`, written from the text for the writer schema's properties) draw it:
    derandomised, so the same on every run of one Hypothesis version."""
    found: list[JsonObject] = []
    plan = value_fields.Plan(registered=name, form=form, withheld=False, rich=RICH)

    @settings(derandomize=True, database=None, max_examples=1, phases=[Phase.generate], deadline=None)
    @given(value_fields.form_fields(plan, SMALL))
    def first(field: JsonObject) -> None:
        found.append(field)

    first()
    return found[0]


@cache
def bases() -> dict[str, tuple[str, JsonObject]]:
    """The fields varied, by name: the full fields, then one field of each row and each form it allows,
    drawn (S2a-2's review, L2: S2's inputs vary every row's binding, not one field's)."""
    found = {name: ("fluid.dynamic_viscosity", field) for name, field in full_fields().items()}
    for name, spec in VOCABULARY.fields.items():
        for form in spec.forms:
            found[f"{name} {form}"] = (name, drawn(name, form))
    return found


def variant(registered: str, name: str, value: JsonValue, change: str, origin: str = "") -> Example:
    """An example of the field `registered`, `value`, alone in its section of a material record."""
    section_name, _, field_name = registered.partition(".")
    section: JsonObject = {"fields": {field_name: value}}
    record: JsonObject = {"record_type": "material", "body": {"sections": {section_name: section}}}
    return Example(name, registered, value, section, record, change, origin)


@cache
def variant_examples() -> list[Example]:
    """Each change at each path of the bases, once: a path two bases share is changed in the first. Each
    provenance object of each base takes each other origin, and so does each change inside it."""
    seen: set[tuple[str, Path_]] = set()
    found: list[Example] = []
    for base, (registered, field) in bases().items():
        for path in paths(field):
            where = ".".join(map(str, path))
            if is_provenance(value_at(field, path)):
                for token in other_origins(field, path):
                    varied = with_origin(field, path, token)
                    found.append(
                        variant(registered, f"{base} {ORIGIN} {where} {token}", varied, ORIGIN, token)
                    )
            for change in CHANGES:
                value = changed(field, path, change)
                if value is None or (change, path) in seen:
                    continue
                seen.add((change, path))
                name = f"{base} {change} {where}"
                found.append(variant(registered, name, value, change))
                if (provenance := provenance_of(field, path)) is not None:
                    for token in other_origins(field, provenance):
                        varied = with_origin(value, provenance, token)
                        found.append(
                            variant(registered, f"{name} with origin {token}", varied, change, token)
                        )
    return found


def all_examples() -> list[Example]:
    return input_examples() + variant_examples()


# The checks, spread over the workers in shares.

SHARES = 12


@pytest.mark.parametrize("share", range(SHARES))
def test_step_8_agrees_with_the_writer_schema_and_the_reader_defs(share: int) -> None:
    assert problems(all_examples()[share::SHARES], step_8, EXCEPTIONS) == []


def test_every_exception_is_still_one() -> None:
    assert stale(all_examples(), step_8, EXCEPTIONS) == []


def test_every_exception_is_of_its_kind() -> None:
    assert misplaced(all_examples(), EXCEPTIONS) == []


def test_an_exception_under_another_kind_is_found() -> None:
    """S2a-2's review, L1: `PR-050.lower_above_upper` moved from `range_order` to `status_token` passed both
    the relations and the stale check."""
    order, token = EXCEPTIONS["range_order"], EXCEPTIONS["status_token"]
    moved = {
        **EXCEPTIONS,
        "range_order": order._replace(
            case_files={
                relation: tuple(case for case in cases if case != "PR-050.lower_above_upper")
                for relation, cases in order.case_files.items()
            }
        ),
        "status_token": token._replace(case_files={2: (*token.case_files[2], "PR-050.lower_above_upper")}),
    }
    assert misplaced(all_examples(), moved) == [
        "PR-050.lower_above_upper: listed under status_token, but its refusal is not of that kind"
    ]
    a_slip_under_input_index = {
        "input_index": EXCEPTIONS["input_index"]._replace(case_files={2: ("PR-005.near_typo_crad",)})
    }
    assert misplaced(all_examples(), a_slip_under_input_index) == [
        "PR-005.near_typo_crad: listed under input_index, but its refusal is not of that kind"
    ]


def full_examples() -> list[Example]:
    found: list[Example] = []
    for name, field in full_fields().items():
        record = record_of(field)
        section = fluid_section(record)
        found.append(Example(name, "fluid.dynamic_viscosity", field, section, record))
    return found


def base_examples() -> list[Example]:
    found: list[Example] = []
    for name, (registered, field) in bases().items():
        record = record_of(field, registered)
        section_name = registered.partition(".")[0]
        section = child(child(child(record, "body"), "sections"), section_name)
        assert isinstance(section, dict)
        found.append(Example(name, registered, field, section, record))
    return found


def test_the_bases_are_valid_and_pass_step_8() -> None:
    """Each base the variants change, the full fields and the drawn ones; a drawn field of a form whose own
    member waits for S2b or S3 has no step-8 verdict yet."""
    for example in base_examples():
        assert WRITER["value_field"](example.value) == [], example.name
        assert ROW[example.field](example.value) == [], example.name
        assert step_8(example) in (frozenset(), frozenset({"withheld"}), None), example.name
    forms = {str(example.value["form"]) for example in base_examples() if isinstance(example.value, dict)}
    assert forms == {"constant", "table", "interval", "composition", "evidence"}


def disagreements(
    schemas: Validators, examples: list[Example], shape_of: Callable[[JsonValue], str]
) -> Iterator[str]:
    """The examples a field's form definition, as `shape_of` picks it, and `value_field` judge apart."""
    for example in examples:
        if (not schemas[shape_of(example.value)](example.value)) != (
            not schemas["value_field"](example.value)
        ):
            yield example.name


# Every example, in the shares the relations take (S2a-2's review, M5: the shortcut had been checked on every
# 14th example, from every 7th before).
@pytest.mark.parametrize("share", range(SHARES))
@pytest.mark.parametrize("schemas", [WRITER, READER], ids=["writer", "reader"])
def test_a_form_definition_accepts_what_value_field_accepts(schemas: Validators, share: int) -> None:
    assert list(disagreements(schemas, all_examples()[share::SHARES], field_shape)) == []


def test_a_form_definition_picked_wrongly_disagrees() -> None:
    """Over every example, to the first disagreement."""

    def interval(field: JsonValue) -> str:
        return "interval_field" if field_shape(field) != "value_field" else "value_field"

    assert next(disagreements(WRITER, all_examples(), interval), None) is not None


def test_every_kind_lists_an_exception_and_every_change_is_made() -> None:
    """Every change, alone and with each origin; and each origin alone."""
    assert all(kind.case_files or kind.examples for kind in EXCEPTIONS.values())
    made = {(example.change, example.origin) for example in variant_examples()}
    for change in CHANGES:
        assert {origin for made_change, origin in made if made_change == change} == {"", *ORIGINS}
    assert {origin for made_change, origin in made if made_change == ORIGIN} == set(ORIGINS)
    assert {change for change, _ in made} == {*CHANGES, ORIGIN}


def test_the_origin_variants_find_a_derivation_checked_beside_every_origin() -> None:
    """The control for the origin variants: the reader `$defs` of b8a597d break relation 3, and only on a
    variant whose origin was changed, where step 8 does not read the derivation that those `$defs` refuse.
    The variants of a derived value's derivation, alone and with each origin."""
    derivation = [
        example
        for example in variant_examples()
        if example.name.startswith("across_sources ") and " provenance.derivation" in example.name
    ]
    found = problems(derivation, step_8, EXCEPTIONS, BEFORE_THE_CONDITION)
    assert found
    assert all(problem.startswith("relation 3 ") and " with origin " in problem for problem in found), found
    assert problems(derivation, step_8, EXCEPTIONS) == []


# Controls: step 8 with one fault, and exceptions with one fault. Each must make the check fail.


def refusing_inferred_from(example: Example) -> frozenset[str] | None:
    codes = step_8(example)
    if codes is not None and '"inferred_from"' in json.dumps(example.value):
        return codes | {"form_invalid"}
    return codes


def refusing_a_coverage_factor_of_2_306(example: Example) -> frozenset[str] | None:
    codes = step_8(example)
    if codes is not None and '"coverage_factor": 2.306' in json.dumps(example.value):
        return codes | {"form_invalid"}
    return codes


def blind_to_a_counts_type(example: Example) -> frozenset[str] | None:
    """Step 8, but never refusing a field whose `n_donors` is neither a number nor an object."""
    codes = step_8(example)
    statistics = example.value.get("statistics") if isinstance(example.value, dict) else None
    donors = statistics.get("n_donors") if isinstance(statistics, dict) else 4.0
    return frozenset() if codes is not None and not isinstance(donors, float | dict) else codes


def counts_retyped() -> list[Example]:
    return [example for example in variant_examples() if example.name.endswith("statistics.n_donors")]


@pytest.mark.parametrize(
    ("verdict", "examples", "relation"),
    [
        pytest.param(refusing_inferred_from, full_examples, 1, id="refusing_what_the_writer_accepts"),
        pytest.param(
            refusing_a_coverage_factor_of_2_306, full_examples, 2, id="refusing_what_the_reader_accepts"
        ),
        pytest.param(blind_to_a_counts_type, counts_retyped, 3, id="accepting_what_the_reader_refuses"),
    ],
)
def test_each_relation_can_fail(
    verdict: Verdict, examples: Callable[[], list[Example]], relation: int
) -> None:
    found = problems(examples(), verdict, EXCEPTIONS)
    assert any(problem.startswith(f"relation {relation} ") for problem in found), found


def test_an_exception_missing_stale_misplaced_twice_or_unreasoned_is_found() -> None:
    reversed_fact = "water_fact_range_reversed fluid.dynamic_viscosity"
    reversed_case = "PR-045.fact_range_reversed"
    examples = [example for example in input_examples() if example.name == reversed_fact]
    order = EXCEPTIONS["range_order"]
    without = {
        **EXCEPTIONS,
        "range_order": order._replace(
            case_files={
                relation: tuple(case for case in cases if case != reversed_case)
                for relation, cases in order.case_files.items()
            }
        ),
    }
    assert problems(examples, step_8, without) == [
        f"relation 1 fails on {reversed_fact}",
        f"relation 2 fails on {reversed_fact}",
    ]
    fixture = "water_fixture fluid.dynamic_viscosity"
    water = [example for example in input_examples() if example.name == fixture]
    fixture_case = readers()[fixture][0][0]
    listing_the_fixture = {"slip": Kind("a reason", {2: (fixture_case,)})}
    assert stale(water, step_8, listing_the_fixture) == [
        f"{fixture_case}: relation 2 holds, so its exception is stale"
    ]
    assert stale(examples, step_8, listing_the_fixture) == [f"{fixture_case}: reads no example"]
    assert stale(examples, step_8, {"range_order": Kind("", {1: (reversed_case,)})}) == [
        "range_order: the kind has no reason"
    ]
    twice = {"a": Kind("a reason", {1: (reversed_case,)}), "b": Kind("a reason", {1: (reversed_case,)})}
    assert stale(examples, step_8, twice) == [f"{reversed_case}: listed twice for relation 1"]
    assert stale(examples, step_8, {"range_order": Kind("a reason", {}, {1: (reversed_fact,)})}) == [
        f"{reversed_fact}: a case file reads it, so the case file is listed instead"
    ]
    assert stale(examples, step_8, {"slip": Kind("a reason", {}, {1: ("no such field",)})}) == [
        "no such field: no such example"
    ]


# The token lists known for a member of each name (`value_shapes.BOUND`), against those the writer schema
# binds to a member of that name: a list missing from `BOUND` would turn a known token into `unknown_token`,
# and one too many a token the reader knows for no member of that name into `form_invalid`.

# Member names the writer binds to a token list that step 8 does not read from, with the reason.
NOT_READ = {
    "component": "a composition's member, read with the form's own member (S2b-1)",
    "sum_rule": "a composition's member, read with the form's own member (S2b-1)",
    "inputs": "a search's, which a read does not check",
    "method": "an extraction's, which a read does not check",
    "result": "a review's, which never refuses a field",
    "type": "a locator's, which a read does not check",
    "unit": (
        "a specimen fact's fixed unit, `s`, which step 9 compares (`read_side_contract.md` section 3, "
        "step 9, a default for the maintainer): step 8 checks only that it is a string or a status object"
    ),
}
# Lists `BOUND` holds that no record member binds: a declaration's distributions (`uncertainty.md` section 4),
# and the form tokens, which each form's definition holds as a constant (`test_value_fields.py` checks them).
NOT_IN_A_RECORD = {"distribution": {"distribution"}, "form": {"form"}}


def writer_bindings(node: JsonValue, name: str | None = None) -> dict[str, set[str]]:
    """Each member name the writer schema binds to a vocabulary token list, and the lists, by `$ref`."""
    found: dict[str, set[str]] = {}
    if isinstance(node, list):
        for item in node:
            for member, lists in writer_bindings(item, name).items():
                found.setdefault(member, set()).update(lists)
        return found
    if not isinstance(node, dict):
        return found
    reference = node.get("$ref")
    listed = reference.rpartition("/")[2] if isinstance(reference, str) else None
    if listed in VOCABULARY.token_lists and name is not None:
        found.setdefault(name, set()).add(listed)
    for keyword, value in node.items():
        below = name if keyword in ("anyOf", "oneOf", "items") else None
        if keyword == "properties" and isinstance(value, dict):
            parts = [writer_bindings(member_node, member) for member, member_node in value.items()]
        else:
            parts = [writer_bindings(value, below)]
        for part in parts:
            for found_member, lists in part.items():
                found.setdefault(found_member, set()).update(lists)
    return found


def binding_differences(bound: dict[str, tuple[str, ...]], writer: dict[str, set[str]]) -> list[str]:
    differences: list[str] = []
    for name in sorted((bound.keys() | writer.keys()) - NOT_READ.keys() - {"token"}):
        expected = writer.get(name, set()) | NOT_IN_A_RECORD.get(name, set())
        if set(bound.get(name, ())) != expected:
            differences.append(
                f"{name}: BOUND has {sorted(bound.get(name, ()))}, the writer {sorted(expected)}"
            )
    return differences


WRITER_SCHEMA = json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8"))


def test_the_token_lists_known_by_member_name_are_the_writer_schemas() -> None:
    writer = writer_bindings(WRITER_SCHEMA)
    assert binding_differences(BOUND, writer) == []
    assert NOT_READ.keys() <= writer.keys()
    assert writer["token"] <= {name for name in VOCABULARY.token_lists if name.endswith("_token")}


def test_a_token_list_missing_or_extra_is_found() -> None:
    writer = writer_bindings(WRITER_SCHEMA)
    missing = {**BOUND, "basis": tuple(name for name in BOUND["basis"] if name != "interval_basis")}
    extra = {**BOUND, "central": ("central", "dispersion")}
    assert binding_differences(missing, writer) != []
    assert binding_differences(extra, writer) != []
