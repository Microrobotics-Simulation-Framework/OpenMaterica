# SPDX-License-Identifier: Apache-2.0
"""Strategies for the S2 design's HP4 and HP10: a read beside a record changed where the read must not look,
or written out again in another byte form.

HP4 (isolation, `read_side_contract.md` section 3, steps 7 and 8; PR-033, PR-045): a constant, an interval
or a composition that passes steps 1 to 8 (`result_strategies.form_reads`), read under the `want` its form
gives, beside a fault elsewhere in its record, the way drawn first:
another registered field holding a field of step 8's catalogue with its fault, or any JSON value; a field
name no row registers, more than one slip from every registered one, holding anything; or another section's
`specimen`, with its facts or with a fault of its own. Or a fault in the read field's own section's
`specimen`, which refuses the read.

HP10 (the byte form never matters; PR-047): any read HP12 draws (`model_strategies.py`), its sources and its
request written again, member order, whitespace, escapes and number spellings drawn (`strategies.render`).
"""

import copy
import json
import random
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import model_strategies, records
from tests.property import result_strategies as results
from tests.property.condition_strategies import Read, at, reference
from tests.property.model_strategies import Example
from tests.property.strategies import WRITINGS, Size, render
from tests.property.value_field_strategies import WANTS, faulty_records, pinned, specimen
from tests.reference.strict_json import NotStrictJson, parse

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

ELSEWHERE = ("another_field", "unknown_field", "another_section_specimen")
SECTIONS = sorted(VOCABULARY.sections)
# A field name of a registered section that no row registers, more than one slip from every registered one.
UNKNOWN_FIELD = "x_quantity_no_row_registers"


class Isolated(NamedTuple):
    way: str
    claims: frozenset[Suite]
    base: Read  # the read with nothing changed elsewhere
    changed: JsonObject  # its record, changed where the way says, and pinned again


def changed_record(read: Read, change: JsonObject) -> JsonObject:
    """`read`'s record with `change`'s sections merged in, field by field, and pinned again."""
    record = copy.deepcopy(read.record)
    sections = at(record, "body", "sections")
    for name, section in change.items():
        assert isinstance(section, dict)
        held = sections.setdefault(name, {"fields": {}})
        assert isinstance(held, dict)
        fields = section.get("fields", {})
        assert isinstance(fields, dict)
        at(held, "fields").update(fields)
        if "specimen" in section:
            held["specimen"] = section["specimen"]
    return pinned(record)


# A section's specimen with a fault step 8 finds: a fact not of its shape, a fact name one slip from a
# registered one, a token the reader knows for no fact of that name, or no object at all.
FAULTY_SPECIMENS: list[JsonValue] = [
    {"post_mortem_interval": {"value": "60", "unit": "s", "basis": "stated"}},
    {"post_mortem_intervals": {"value": 60.0, "unit": "s", "basis": "stated"}},
    {"tissue_state": {"token": "x_unknown_state", "basis": "stated"}},
    {"tissue_state": {"status": "unstated", "token": "in_vivo"}},
    [],
]


@st.composite
def fault_elsewhere(draw: Draw, way: str, read: Read, size: Size) -> JsonObject:
    """The sections to merge into `read`'s record for `way`."""
    target_section = read.field.partition(".")[0]
    if way == "another_field":
        name = draw(st.sampled_from(sorted(set(VOCABULARY.fields) - {read.field})))
        section, _, field = name.partition(".")
        held: JsonValue
        if draw(st.booleans()):
            example = draw(faulty_records(size))
            example_section, _, example_field = example.field.partition(".")
            held = copy.deepcopy(
                at(example.record, "body", "sections", example_section, "fields", example_field)
            )
        else:
            held = draw(records.trees(size).values)
        return {section: {"fields": {field: held}}}
    if way == "unknown_field":
        return {target_section: {"fields": {UNKNOWN_FIELD: draw(records.trees(size).values)}}}
    others = [name for name in SECTIONS if name != target_section]
    section_specimen: JsonValue = (
        draw(specimen()) if draw(st.booleans()) else draw(st.sampled_from(FAULTY_SPECIMENS))
    )
    return {draw(st.sampled_from(others)): {"fields": {}, "specimen": copy.deepcopy(section_specimen)}}


@st.composite
def form_read(draw: Draw, size: Size) -> Read:
    """A read of a field of a form drawn first, under the `want` its form gives."""
    form, read = draw(results.form_reads(size))
    return read._replace(request=results.with_want(read.request, WANTS[form]))


@st.composite
def isolated(draw: Draw, size: Size) -> Isolated:
    way = draw(st.sampled_from(ELSEWHERE))
    read = draw(form_read(size))
    changed = changed_record(read, draw(fault_elsewhere(way, read, size)))
    claims = draw(st.sampled_from(model_strategies.CLAIMS))
    return Isolated(way, claims, read, changed)


@st.composite
def own_section_faulted(draw: Draw, size: Size) -> Isolated:
    """A fault in the read field's own section's `specimen`."""
    read = draw(form_read(size))
    section, _, _ = read.field.partition(".")
    change: JsonObject = {section: {"specimen": copy.deepcopy(draw(st.sampled_from(FAULTY_SPECIMENS)))}}
    claims = draw(st.sampled_from(model_strategies.CLAIMS))
    return Isolated("own_section_specimen", claims, read, changed_record(read, change))


def repointed(request: JsonObject, record: JsonObject) -> bytes:
    changed = copy.deepcopy(request)
    at(changed, "target")["record"] = reference(record)
    return json.dumps(changed).encode()


# HP10.


def reordered(writing: random.Random, value: JsonValue) -> JsonValue:
    """`value` with every object's members in an order `writing` draws."""
    if isinstance(value, list):
        return [reordered(writing, item) for item in value]
    if isinstance(value, dict):
        names = list(value)
        writing.shuffle(names)
        return {name: reordered(writing, value[name]) for name in names}
    return value


def rewritten(writing: random.Random, data: bytes) -> bytes:
    """`data` written again as JSON text of the same value, where it is one; as it is, where not."""
    try:
        value = parse(data)
    except NotStrictJson:
        return data
    return render(writing, reordered(writing, value)).encode()


class Rewritten(NamedTuple):
    original: Example
    rewritten: Example


REWRITTEN_KINDS = ("valued", "alternatives", "step_8", "steps_9_and_10", "request", "ends_early")


@st.composite
def rewritten_reads(draw: Draw, size: Size) -> Rewritten:
    """A read HP12 draws and the same read written again. Sources identical byte for byte are written again
    alike: two copies of a pin whose bytes differ are another read (`read_side_contract.md` section 3, step
    1)."""
    original = draw(model_strategies.drawn(size, REWRITTEN_KINDS))
    writing = draw(WRITINGS)
    again = {source: rewritten(writing, source) for source in dict.fromkeys(original.sources)}
    sources = tuple(again[source] for source in original.sources)
    return Rewritten(
        original, original._replace(sources=sources, request=rewritten(writing, original.request))
    )
