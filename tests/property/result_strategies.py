# SPDX-License-Identifier: Apache-2.0
"""Strategies for the result's laws (`read_side_contract.md` section 2), the S2 design's HP1, HP2, HP6 and
HP11: reads that end at each step S2 builds, each drawn by its kind first, so that the feature audit holds
each kind to its draw floor.

A kind is a read the steps built decide: one whose record passes steps 1 to 10, under each `want` of plain
read; one with a fault of step 8's catalogue (`value_field_strategies.py`) or of steps 9 and 10's
(`condition_strategies.py`); one that ends before step 4 (no candidate, a pin no candidate states, an
unreadable source beside none, another schema version, an ill-formed one, a broken envelope), at step 5 (a
type no reader reads) or at step 7 (a field the record does not hold); and a field holding alternatives, each
of which the request meets, or whose list breaks its shape. Each knows whether its read reaches step 4, where
a reader without the hash suite labels it `hash_not_checked`.
"""

import copy
import json
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property.condition_strategies import FAULTS, Read, at, base_reads, faulty_reads, reference
from tests.property.strategies import DOUBLES, TEXT, Size
from tests.property.value_field_strategies import faulty_records, pinned

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

WITH_HASH: frozenset[Suite] = frozenset({"plain_read", "hash"})
WITHOUT_HASH: frozenset[Suite] = frozenset({"plain_read"})
# The `want`s of plain read: a constant gives `value` alone.
WANTS = ("value", "value", "value", "bounds", "components", "evidence")
BEFORE_STEP_4 = (
    "no_candidate",
    "pin_no_candidate_states",
    "unreadable_beside_none",
    "other_version",
    "ill_formed_version",
    "broken_envelope",
)
SHAPE_FAULTS = ("empty", "not_a_list", "not_an_object", "nested", "beside_a_member", "slip")
KINDS = (
    "met",
    "step_8_fault",
    "step_9_or_10_fault",
    "before_step_4",
    "step_5",
    "step_7",
    "alternatives",
    "alternatives_broken",
)
# The kinds whose read returns a value or alternative values.
VALUED = ("met", "alternatives")


class Drawn(NamedTuple):
    kind: str
    sources: tuple[bytes, ...]
    request: JsonObject
    claims: frozenset[Suite]
    reaches_step_4: bool
    record: JsonObject  # the target's record, as stored where a source holds it
    field: str  # `<section>.<field>`
    features: tuple[str, ...] = ()  # what a valued read's field was given to show (`enriched`)


def as_source(record: JsonObject) -> bytes:
    return json.dumps(record).encode()


def field_at(record: JsonObject, name: str) -> JsonObject:
    section, _, field = name.partition(".")
    return at(record, "body", "sections", section, "fields", field)


def with_want(request: JsonObject, want: str) -> JsonObject:
    changed = copy.deepcopy(request)
    requirement = changed["requirement"]
    assert isinstance(requirement, dict)
    requirement["want"] = want
    return changed


def from_read(kind: str, read: Read, want: str, claims: frozenset[Suite]) -> Drawn:
    return Drawn(
        kind, (as_source(read.record),), with_want(read.request, want), claims, True, read.record, read.field
    )


@st.composite
def met_reads(draw: Draw, size: Size, wants: tuple[str, ...] = WANTS) -> Drawn:
    read = draw(base_reads(size))
    return from_read(
        "met", read, draw(st.sampled_from(wants)), draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    )


@st.composite
def step_8_faults(draw: Draw, size: Size) -> Drawn:
    example = draw(faulty_records(size))
    record = pinned(example.record)
    request: JsonObject = {
        "target": {"record": reference(record), "field": example.field},
        "requirement": {"want": "value"},
    }
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn("step_8_fault", (as_source(record),), request, claims, True, record, example.field)


@st.composite
def step_9_or_10_faults(draw: Draw, size: Size) -> Drawn:
    faulty = draw(faulty_reads(tuple(FAULTS), size))
    return from_read(
        "step_9_or_10_fault", faulty.read, "value", draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    )


def repinned(record: JsonObject) -> JsonObject:
    return {**record, "content_hash": content_hash(record)}


@st.composite
def before_step_4(draw: Draw, size: Size) -> Drawn:
    """A read that ends at step 1, 2 or 3 (`read_side_contract.md` section 3), the way drawn first."""
    way = draw(st.sampled_from(BEFORE_STEP_4))
    read = draw(base_reads(size))
    record = copy.deepcopy(read.record)
    request = copy.deepcopy(read.request)
    sources: list[bytes] = [as_source(record)]
    if way == "no_candidate":
        sources = [as_source(repinned({**record, "id": "conformance/another_fixture"}))]
    elif way == "pin_no_candidate_states":
        at(request, "target", "record")["content_hash"] = "sha256:" + "a" * 64
    elif way == "unreadable_beside_none":
        sources = [b"[]", as_source(repinned({**record, "version": "9.0.0"}))]
    elif way == "other_version":
        record = repinned({**record, "schema_version": "0.2.0"})
    elif way == "ill_formed_version":
        record = repinned({**record, "schema_version": "0.1"})
    else:
        del record["name"]
        record = repinned(record)
    if way in ("other_version", "ill_formed_version", "broken_envelope"):
        sources = [as_source(record)]
        at(request, "target")["record"] = reference(record)
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn("before_step_4", tuple(sources), request, claims, False, record, read.field)


@st.composite
def at_step_5(draw: Draw, size: Size) -> Drawn:
    read = draw(base_reads(size))
    record = repinned({**read.record, "record_type": draw(st.sampled_from(["interface", "acme:thing"]))})
    request = target_of(read.request, record)
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn("step_5", (as_source(record),), request, claims, True, record, read.field)


@st.composite
def at_step_7(draw: Draw, size: Size) -> Drawn:
    """A field the record does not hold, in a section it holds or not."""
    read = draw(base_reads(size))
    others = sorted(name for name in VOCABULARY.fields if name != read.field)
    request = copy.deepcopy(read.request)
    at(request, "target")["field"] = draw(st.sampled_from(others))
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn("step_7", (as_source(read.record),), request, claims, True, read.record, read.field)


def without_origin_s_reason(field: JsonObject) -> None:
    """A value stated without origin gives step 12's reason, which would be each alternative's own, which S4
    reads: another origin in its place."""
    provenance = at(field, "provenance")
    if provenance["origin"] == "stated_without_origin":
        provenance["origin"] = "measured_by_contributor"


def holding(read: Read, held: JsonValue) -> JsonObject:
    record = copy.deepcopy(read.record)
    section, _, name = read.field.partition(".")
    at(record, "body", "sections", section, "fields")[name] = held
    return repinned(record)


def target_of(request: JsonObject, record: JsonObject) -> JsonObject:
    changed = copy.deepcopy(request)
    at(changed, "target")["record"] = reference(record)
    return changed


@st.composite
def alternatives(draw: Draw, size: Size, wants: tuple[str, ...] = WANTS) -> Drawn:
    """Two or three alternatives, each the base read's field with a value of its own, which the request
    meets: `no_pick` under `want: value`, `want_mismatch` under any other."""
    read = draw(base_reads(size))
    field = field_at(read.record, read.field)
    without_origin_s_reason(field)
    count = draw(st.integers(2, 3))
    held: list[JsonValue] = [{**copy.deepcopy(field), "value": draw(DOUBLES)} for _ in range(count)]
    record = holding(read, {"alternatives": held})
    request = with_want(target_of(read.request, record), draw(st.sampled_from(wants)))
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn("alternatives", (as_source(record),), request, claims, True, record, read.field)


@st.composite
def broken_alternatives(draw: Draw, size: Size) -> Drawn:
    """A list of alternatives that breaks its shape (`record_format.md` section 5), the way drawn first."""
    way = draw(st.sampled_from(SHAPE_FAULTS))
    read = draw(base_reads(size))
    field = field_at(read.record, read.field)
    holder: JsonObject = {"alternatives": [copy.deepcopy(field), copy.deepcopy(field)]}
    if way == "empty":
        holder["alternatives"] = []
    elif way == "not_a_list":
        holder["alternatives"] = copy.deepcopy(field)
    elif way == "not_an_object":
        holder["alternatives"] = [copy.deepcopy(field), draw(DOUBLES)]
    elif way == "nested":
        holder["alternatives"] = [copy.deepcopy(field), {"alternatives": [copy.deepcopy(field)]}]
    elif way == "beside_a_member":
        member = draw(st.sampled_from(sorted(set(field) - {"specimen"})))
        holder[member] = copy.deepcopy(field[member])
    else:
        holder["alternative"] = []
    record = holding(read, holder)
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    return Drawn(
        "alternatives_broken",
        (as_source(record),),
        target_of(read.request, record),
        claims,
        True,
        record,
        read.field,
    )


BUILDERS = {
    "met": met_reads,
    "step_8_fault": step_8_faults,
    "step_9_or_10_fault": step_9_or_10_faults,
    "before_step_4": before_step_4,
    "step_5": at_step_5,
    "step_7": at_step_7,
    "alternatives": alternatives,
    "alternatives_broken": broken_alternatives,
}


# What a field a read returns from is given to show, each in a share of draws: its value `-0`; a review of
# each way `provenance.md` section 2 item 6 reads one (any value, a known result, a status object); and a
# member the reader does not know, in its statistics block, a fact of its specimen or a condition.
REVIEWS = ("review_anything", "review_reviewed", "review_not_checked")
UNKNOWN_PLACES = ("statistics", "fact", "condition")


@st.composite
def enriched(draw: Draw, field: JsonObject) -> tuple[str, ...]:
    """`field` changed to show what it is drawn to, which it returns, by name."""
    shown: list[str] = []
    if draw(st.integers(0, 3)) == 0:
        field["value"] = -0.0
        shown.append("negative_zero")
    review = draw(st.sampled_from(REVIEWS))
    shown.append(review)
    provenance = at(field, "provenance")
    if review == "review_reviewed":
        provenance["review"] = {
            "result": "reviewed",
            "reviewer": draw(TEXT),
            "date": "2026-10-17",
            "independent_of_extraction": draw(st.booleans()),
            "checklist": ["value", "unit"],
        }
    elif review == "review_not_checked":
        provenance["review"] = {"status": "not_checked", "reason": draw(TEXT)}
    if draw(st.booleans()):
        place = draw(st.sampled_from(UNKNOWN_PLACES))
        holder = {
            "statistics": lambda: at(field, "statistics"),
            "fact": lambda: at(field, "specimen", "post_mortem_interval"),
            "condition": lambda: at(field, "conditions", "measurement_geometry"),
        }[place]()
        holder["x_unknown_member"] = draw(DOUBLES)
        shown.append("unknown_member")
    return tuple(shown)


@st.composite
def drawn_reads(draw: Draw, size: Size, kinds: tuple[str, ...] = KINDS) -> Drawn:
    """A read of one of `kinds`, the kind drawn first."""
    kind = draw(st.sampled_from(kinds))
    drawn: Drawn = draw(BUILDERS[kind](size))
    return drawn


@st.composite
def valued_reads(draw: Draw, size: Size) -> Drawn:
    """A read that returns a value or alternative values, under `want: value`, the kind drawn first: a met
    constant, or alternatives, each the field `enriched` gave what it shows."""
    kind = draw(st.sampled_from(VALUED))
    read = draw(base_reads(size))
    field = field_at(read.record, read.field)
    without_origin_s_reason(field)
    shown = draw(enriched(field))
    if kind == "met":
        record = repinned(read.record)
    else:
        held: list[JsonValue] = [copy.deepcopy(field)]
        held += [{**copy.deepcopy(field), "value": draw(DOUBLES)} for _ in range(draw(st.integers(1, 2)))]
        record = holding(read, {"alternatives": held})
    claims = draw(st.sampled_from((WITH_HASH, WITHOUT_HASH)))
    request = with_want(target_of(read.request, record), "value")
    return Drawn(kind, (as_source(record),), request, claims, True, record, read.field, shown)
