# SPDX-License-Identifier: Apache-2.0
"""Strategies for step 8's properties: records holding one constant value field that passes step 8, the
faults of step 8's catalogue, each with the reasons it must give, and the members a reader does not know.

A drawn field takes every member step 8 checks or leaves the optional ones out, each value-or-status member
as its own shape or as a status object its row allows, and anything at all in the members a read does not
check. Nothing is filtered. The tokens a status object holds come from `provenance.md` section 1 item 5's
table (`tests/spec_sync/status_rows.py`), never from step 8's own `value_shapes.status_row`.

The fault catalogue is written from the text (`read_side_contract.md` section 3, step 8; `provenance.md`
sections 1, 2, 5 and 6; `uncertainty.md` sections 1 and 4; `record_format.md` sections 2, 4, 5 and 10): each
fault sets one member, at one place, to what breaks one rule, and gives the codes the rule gives. A fault that
breaks no rule, a member step 8 must not check, gives none.
"""

import copy
from collections.abc import Callable
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY, ConditionSpec
from tests.property import records
from tests.property.strategies import DOUBLES, SIZE, TEXT, Size
from tests.spec_sync import status_rows

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

# The fields a constant may take, the one form whose own member step 8 reads so far.
CONSTANT_FIELDS = tuple(sorted(name for name, spec in VOCABULARY.fields.items() if "constant" in spec.forms))

NOT_NEGATIVE = DOUBLES.map(abs)
POSITIVE = DOUBLES.map(lambda number: abs(number) or 1.0)
PROBABILITIES = st.floats(min_value=0.0, max_value=1.0, exclude_min=True)
COUNTS = st.integers(0, 2**53).map(float)


def tokens(name: str) -> st.SearchStrategy[str]:
    return st.sampled_from(VOCABULARY.token_lists[name])


def status_object(token: str, reason: str | None) -> JsonObject:
    return {"status": token} if reason is None else {"status": token, "reason": reason}


def status_objects(definition: str, member: str) -> st.SearchStrategy[JsonObject]:
    """A status object with a token `member` of the writer's `definition` allows, with a reason or none."""
    return st.builds(status_object, st.sampled_from(status_rows.tokens(definition, member)), st.none() | TEXT)


def or_status(
    own: st.SearchStrategy[JsonValue], definition: str, member: str
) -> st.SearchStrategy[JsonValue]:
    return st.one_of(own, status_objects(definition, member))


@st.composite
def in_order(draw: Draw) -> list[JsonValue]:
    ends = sorted([draw(DOUBLES), draw(DOUBLES)])
    return [ends[0], ends[1]]


@st.composite
def based(draw: Draw) -> JsonObject:
    if draw(st.booleans()):
        return {"basis": "stated"}
    return {"basis": "inferred", "inferred_from": draw(TEXT)}


UNITS: st.SearchStrategy[JsonValue] = st.one_of(TEXT, status_objects("plus_minus_entry", "unit"))
PLUS_MINUS_KINDS = (["bound"], ["sd"], ["bound", "sd"], ["sd", "bound"], ["unstated"])


@st.composite
def plus_minus(draw: Draw) -> list[JsonValue]:
    entries: list[JsonValue] = []
    for kind in draw(st.sampled_from(PLUS_MINUS_KINDS)):
        stated_as: JsonValue = {"status": "unstated"} if kind == "unstated" else kind
        entries.append({"stated_as": stated_as, "value": draw(NOT_NEGATIVE), "unit": draw(UNITS)})
    return entries


@st.composite
def numeric_condition(draw: Draw) -> JsonObject:
    entry: JsonObject = {"unit": draw(UNITS), **draw(based())}
    if draw(st.booleans()):
        entry["value"] = draw(DOUBLES)
    else:
        entry["range"] = draw(in_order())
    if draw(st.booleans()):
        entry["plus_minus"] = draw(plus_minus())
    if draw(st.booleans()):
        entry["set_or_measured"] = draw(tokens("set_or_measured"))
    return entry


@st.composite
def token_condition(draw: Draw, spec: ConditionSpec) -> JsonObject:
    return {"token": draw(st.sampled_from(spec.tokens)), **draw(based())}


def condition(spec: ConditionSpec) -> st.SearchStrategy[JsonValue]:
    own: st.SearchStrategy[JsonValue] = (
        numeric_condition() if spec.shape == "numeric" else token_condition(spec)
    )
    return or_status(own, "conditions", spec.name)


CONDITIONS = {name: condition(spec) for name, spec in VOCABULARY.conditions.items()}


@st.composite
def conditions(draw: Draw, size: Size) -> JsonObject:
    """Some of the registered conditions, at most four of nine, and, in one draw in four, a name the reader
    does not know, holding anything. Step 8 checks each condition apart from the others, so a draw needs no
    more of them, and the catalogue's faults set the ones they break (S2a-2's review, Info finding I4)."""
    chosen = draw(st.lists(st.sampled_from(sorted(CONDITIONS)), unique=True, max_size=4))
    found: JsonObject = {name: draw(CONDITIONS[name]) for name in chosen}
    if draw(st.integers(0, 3)) == 0:
        found["x_" + draw(st.text("abcdefgh", min_size=3, max_size=6))] = draw(records.trees(size).values)
    return found


@st.composite
def fact_shape(draw: Draw, name: str) -> JsonObject:
    """A specimen fact of `name` in its row's shape (`provenance.md` section 6.2)."""
    tokens_of = VOCABULARY.facts[name].tokens
    shape: JsonObject
    if name == "species":
        shape = {"ncbi_taxon": draw(COUNTS), "label": draw(TEXT)}
    elif name == "anatomical_site":
        shape = {"uberon": draw(TEXT), "label": draw(TEXT)}
    elif name in ("post_mortem_interval", "donor_age"):
        # The row fixes the unit, `"unit": "s"`, which step 9 alone compares: step 8 takes any string or
        # status object there, as for every unit (a default for the maintainer, 2026-10-15).
        shape = {"unit": draw(st.one_of(st.just(VOCABULARY.facts[name].fixed["unit"]), UNITS))}
        if name == "post_mortem_interval" or draw(st.booleans()):
            shape["value"] = draw(DOUBLES)
        else:
            shape["range"] = draw(in_order())
    elif name == "disease_and_treatment_state":
        # `text` names the disease or the treatment, so it is there exactly beside those two.
        shape = {"token": draw(st.sampled_from(tokens_of))}
        if shape["token"] in ("diseased", "treated"):
            shape["text"] = draw(TEXT)
    elif tokens_of:
        shape = {"token": draw(st.sampled_from(tokens_of))}
        if shape["token"] == "other" or draw(st.booleans()):
            shape["text"] = draw(TEXT)
        if name in ("tissue_state", "supply_form"):
            shape.pop("text", None)
    else:
        shape = {"text": draw(TEXT)}
    # A row that fixes the basis (`mimics`, `"basis": "stated"`) leaves nothing to infer from.
    fixed_basis = VOCABULARY.facts[name].fixed.get("basis")
    return {**shape, **({"basis": fixed_basis} if fixed_basis else draw(based()))}


FACTS = {name: or_status(fact_shape(name), "specimen", name) for name in VOCABULARY.facts}


@st.composite
def specimen(draw: Draw) -> JsonObject:
    """Some of the specimen facts, at most four of eleven, for the reason `conditions` gives."""
    chosen = draw(st.lists(st.sampled_from(sorted(FACTS)), unique=True, max_size=4))
    return {name: draw(FACTS[name]) for name in chosen}


UNCERTAINTY_STATUSES = {
    name: status_objects("uncertainty", name) for name in ("coverage_factor", "coverage_probability", "dof")
}
UNCERTAINTY_PRECISION = or_status(tokens("precision_conditions"), "uncertainty", "precision_conditions")


@st.composite
def uncertainty(draw: Draw) -> JsonObject:
    """A relative or expanded uncertainty: at least one of its coverage factor and probability a number,
    `dof` a number exactly under `student_t`, and `precision_conditions` exactly where it represents a
    measurement."""
    distribution = draw(st.sampled_from(["normal", "student_t", "unstated"]))
    covered = draw(st.sampled_from(["factor", "probability", "both"]))
    represents = draw(st.sampled_from(["measurement", "estimate", "unstated"]))
    factor = UNCERTAINTY_STATUSES["coverage_factor"] if covered == "probability" else POSITIVE
    probability = UNCERTAINTY_STATUSES["coverage_probability"] if covered == "factor" else PROBABILITIES
    entry: JsonObject = {
        "value": draw(NOT_NEGATIVE),
        "coverage_factor": draw(factor),
        "coverage_probability": draw(probability),
        "distribution": {"status": "unstated"} if distribution == "unstated" else distribution,
        "dof": draw(POSITIVE if distribution == "student_t" else UNCERTAINTY_STATUSES["dof"]),
        "basis": draw(tokens("uncertainty_basis")),
        "represents": {"status": "unstated"} if represents == "unstated" else represents,
    }
    if represents == "measurement":
        entry["precision_conditions"] = draw(UNCERTAINTY_PRECISION)
    return entry


REPRESENTS = ("population", "estimate", "measurement", "across_sources", "unstated", "not_applicable")


def population_level(level: str, within: JsonValue) -> JsonObject:
    return {"level": level, "within": within}


LEVELS = st.builds(
    population_level, tokens("level"), or_status(tokens("level"), "population_level", "within")
)
OWN_BLOCK_MEMBERS: dict[str, st.SearchStrategy[JsonValue]] = {
    "central": tokens("central"),
    "n_specimens": COUNTS,
    "n_donors": COUNTS,
    "mean": DOUBLES,
    "sd": NOT_NEGATIVE,
    "min": DOUBLES,
    "max": DOUBLES,
    "distribution": tokens("statistics_distribution"),
    "basis": tokens("statistics_basis"),
    "relative_uncertainty": uncertainty(),
    "expanded_uncertainty": uncertainty(),
    "population_level": LEVELS,
    "n_sources": COUNTS,
    "precision_conditions": tokens("precision_conditions"),
}
BLOCK_MEMBERS = {name: or_status(own, "statistics_block", name) for name, own in OWN_BLOCK_MEMBERS.items()}
CONDITIONAL = {
    "population": "population_level",
    "across_sources": "n_sources",
    "measurement": "precision_conditions",
}


@st.composite
def statistics(draw: Draw) -> JsonObject:
    """A statistics block, each member its row's shape or a status object, with the conditional member its
    `represents` calls for."""
    represents = draw(st.sampled_from(REPRESENTS))
    block: JsonObject = {
        name: draw(strategy) for name, strategy in BLOCK_MEMBERS.items() if name not in CONDITIONAL.values()
    }
    block["represents"] = (
        {"status": represents} if represents in ("unstated", "not_applicable") else represents
    )
    block["dispersion"] = draw(tokens("dispersion"))
    if represents in CONDITIONAL:
        block[CONDITIONAL[represents]] = draw(BLOCK_MEMBERS[CONDITIONAL[represents]])
    return block


PIN = "sha256:" + "0" * 64


@st.composite
def derivation(draw: Draw) -> JsonObject:
    inputs = [
        {"record": {"id": draw(TEXT), "version": draw(TEXT), "content_hash": PIN}, "field": draw(TEXT)}
        for _ in range(draw(st.integers(1, 3)))
    ]
    specimens = [
        {"input": float(draw(st.integers(0, len(inputs) - 1))), "specimen": draw(specimen())}
        for _ in range(draw(st.integers(0, 2)))
    ]
    entry: JsonObject = {
        "method": draw(TEXT),
        "inputs": inputs,  # type: ignore[dict-item]  # a list of objects is a JSON value
        "assumptions": draw(st.lists(TEXT, max_size=2)),  # type: ignore[dict-item]
        "input_specimens": specimens,  # type: ignore[dict-item]
    }
    if draw(st.booleans()):
        entry["mixed_conditions"] = draw(st.booleans())
    return entry


@st.composite
def provenance(draw: Draw, size: Size) -> JsonObject:
    """`origin`, `source` where it requires one and in one other draw in two, `derivation` where derived; and
    anything at all in the members a read does not check."""
    anything = records.trees(size).values
    origin = draw(tokens("origin"))
    entry: JsonObject = {
        "origin": origin,
        "extraction": draw(anything),
        "assistance": draw(anything),
        "review": draw(anything),
    }
    if origin == "measured_by_source" or draw(st.booleans()):
        entry["source"] = {"key": draw(TEXT), "document": draw(anything), "locator": draw(anything)}
    if origin == "derived":
        entry["derivation"] = draw(derivation())
    return entry


class Example(NamedTuple):
    record: JsonObject
    field: str  # the field read, `<section>.<field>`
    faults: tuple[str, ...]  # the catalogue's faults, by name
    expected: frozenset[str]  # the codes step 8 must give; none where it must pass the field


@st.composite
def fields(draw: Draw, size: Size, names: tuple[str, ...] = CONSTANT_FIELDS) -> tuple[str, JsonObject]:
    """A registered field's name, of `names`, and a constant of it that passes step 8."""
    name = draw(st.sampled_from(names))
    spec = VOCABULARY.fields[name]
    field: JsonObject = {
        "form": "constant",
        "unit": spec.unit if draw(st.integers(0, 3)) else draw(UNITS),
        "value": draw(DOUBLES),
        "conditions": draw(conditions(size)),
        "statistics": draw(statistics()),
        "provenance": draw(provenance(size)),
    }
    if draw(st.booleans()):
        field["specimen"] = draw(specimen())
    if spec.label is not None and draw(st.booleans()):
        field["label"] = spec.label
    if draw(st.integers(0, 3)) == 0:
        field["fit"] = draw(records.trees(size).values)
    return name, field


@st.composite
def valid_records(draw: Draw, size: Size = SIZE) -> Example:
    name, field = draw(fields(size))
    section, _, field_name = name.partition(".")
    members: JsonObject = {"fields": {field_name: field}}
    if draw(st.booleans()):
        members["specimen"] = draw(specimen())
    record: JsonObject = {
        "schema_version": "0.1.0",
        "record_type": "material",
        "id": "conformance/field_fixture",
        "version": "1.0.0",
        "name": draw(TEXT),
        "licence": {"values": "CC0-1.0", "evidence": "excluded"},
        "content_hash": PIN,
        "body": {"sections": {section: members}},
    }
    return Example(record, name, (), frozenset())


def pinned(record: JsonObject) -> JsonObject:
    """`record` with its content hash recomputed, so that a request pins it."""
    return {**record, "content_hash": content_hash(record)}


# Where a fault or an addition goes.


def body(record: JsonObject) -> JsonObject:
    found = record["body"]
    assert isinstance(found, dict)
    return found


def section_of(example: Example) -> JsonObject:
    sections = body(example.record)["sections"]
    assert isinstance(sections, dict)
    found = sections[example.field.partition(".")[0]]
    assert isinstance(found, dict)
    return found


def field_of(example: Example) -> JsonObject:
    found = section_of(example)["fields"]
    assert isinstance(found, dict)
    field = found[example.field.partition(".")[2]]
    assert isinstance(field, dict)
    return field


def member(value: JsonObject, name: str) -> JsonObject:
    found = value[name]
    assert isinstance(found, dict)
    return found


# One slip, by each of `record_format.md` section 10's kinds.

SLIPS = ("inserted", "deleted", "substituted", "swapped", "plural", "underscore")


def slipped(name: str, kind: str) -> str:
    """`name` changed by one slip of `kind`; one that would give back `name` itself is made by a character
    inserted."""
    if kind == "deleted" and len(name) > 1:
        return name[:-1]
    if kind == "substituted":
        return name[:-1] + ("q" if name[-1] != "q" else "z")
    if kind == "swapped" and len(name) > 1 and name[-1] != name[-2]:
        return name[:-2] + name[-1] + name[-2]
    if kind == "plural":
        return name[:-1] + "ies" if name.endswith("y") else name + "s"
    if kind == "underscore":
        return name.replace("_", "", 1) if "_" in name else name[:1] + "_" + name[1:]
    return name + "q"


# The fault catalogue. A fault changes the record in place and gives the codes its rule gives: one change at
# one place, its region, so that two faults of two regions never meet.

INVALID = frozenset({"form_invalid"})
UNKNOWN = frozenset({"unknown_token"})
NOTHING = frozenset[str]()
Fault = Callable[[Draw, Example], frozenset[str]]


def setting(
    place: Callable[[Example], JsonObject], name: str, value: JsonValue, codes: frozenset[str]
) -> Fault:
    """A fault that sets `name` in the object `place` finds to `value`."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        place(example)[name] = copy.deepcopy(value)
        return codes

    return fault


def block(example: Example) -> JsonObject:
    return member(field_of(example), "statistics")


def provenance_of(example: Example) -> JsonObject:
    return member(field_of(example), "provenance")


def conditions_of(example: Example) -> JsonObject:
    return member(field_of(example), "conditions")


def specimen_of(example: Example) -> JsonObject:
    field = field_of(example)
    field.setdefault("specimen", {})
    return member(field, "specimen")


def section_specimen_of(example: Example) -> JsonObject:
    section = section_of(example)
    section.setdefault("specimen", {})
    return member(section, "specimen")


def renaming(place: Callable[[Example], JsonObject], kind: str, among: tuple[str, ...] = ()) -> Fault:
    """A member of the object `place` finds, of `among` where given, renamed by one slip of `kind`: a member
    no other region's fault reaches into."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        found = place(example)
        name = draw(st.sampled_from(sorted(name for name in found if name in (among or found))))
        new = slipped(name, kind)
        found[new if new not in found else name + "q"] = found.pop(name)
        return INVALID

    return fault


def removing(place: Callable[[Example], JsonObject], names: tuple[str, ...]) -> Fault:
    def fault(draw: Draw, example: Example) -> frozenset[str]:
        place(example).pop(draw(st.sampled_from(names)), None)
        return INVALID

    return fault


def nulling(place: Callable[[Example], JsonObject], names: tuple[str, ...]) -> Fault:
    def fault(draw: Draw, example: Example) -> frozenset[str]:
        place(example)[draw(st.sampled_from(names))] = None
        return INVALID

    return fault


def uncertainty_fault(change: JsonObject, codes: frozenset[str] = INVALID) -> Fault:
    """A relative uncertainty valid but for `change`."""
    base: JsonObject = {
        "value": 0.02,
        "coverage_factor": 2.0,
        "coverage_probability": {"status": "unstated"},
        "distribution": "normal",
        "dof": {"status": "not_applicable"},
        "basis": "reported_uncertainty",
        "represents": "estimate",
    }
    return setting(block, "relative_uncertainty", {**base, **change}, codes)


def represents_without(member_name: str, represents: str) -> Fault:
    """`represents` set to call for `member_name`, which is taken away, or not to, and the member set."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        found = block(example)
        for conditional in ("population_level", "n_sources", "precision_conditions"):
            found.pop(conditional, None)
        found["represents"] = represents
        if represents != {"population_level": "population", "n_sources": "across_sources"}.get(
            member_name, "measurement"
        ):
            found[member_name] = {"status": "unstated"}
        return INVALID

    return fault


def represents_missing(draw: Draw, example: Example) -> frozenset[str]:
    """No `represents`, nor any member it would call for: `represents` is required on its own account."""
    found = block(example)
    for name in ("represents", "population_level", "n_sources", "precision_conditions"):
        found.pop(name, None)
    return INVALID


def record_slip(where: str) -> Fault:
    """A member one slip from one named in the record's envelope, body, section names, section members or a
    section's field names, beside the named one: it refuses every field read from the record or section."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        section, _, field_name = example.field.partition(".")
        kind = draw(st.sampled_from(SLIPS))
        place, name = {
            "envelope": (example.record, draw(st.sampled_from(["card", "name", "licence", "body"]))),
            "body": (body(example.record), "extensions"),
            "sections": (member(body(example.record), "sections"), section),
            "section": (section_of(example), draw(st.sampled_from(["specimen", "fields"]))),
            "fields": (member(section_of(example), "fields"), field_name),
        }[where]
        new = slipped(name, kind)
        place[new if new not in place else name + "q"] = {}
        return INVALID

    return fault


def label_of_another_field(draw: Draw, example: Example) -> frozenset[str]:
    """A label the reader knows that the field's row does not name."""
    own = VOCABULARY.fields[example.field].label
    field_of(example)["label"] = draw(
        st.sampled_from([label for label in VOCABULARY.token_lists["label"] if label != own])
    )
    return INVALID


STATISTICS_REQUIRED = (
    "central",
    "n_specimens",
    "n_donors",
    "mean",
    "sd",
    "min",
    "max",
    "distribution",
    "basis",
    "represents",
    "dispersion",
    "relative_uncertainty",
    "expanded_uncertainty",
)
TEMPERATURE: JsonObject = {"value": 310.15, "unit": "K", "basis": "stated"}
UNSTATED: JsonObject = {"status": "unstated"}


def represented(
    represents: str, member_name: str, value: JsonValue, codes: frozenset[str] = INVALID
) -> Fault:
    """A block whose `represents` holds `represents`, with the one conditional member it calls for set to
    `value` (`uncertainty.md` section 1)."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        found = block(example)
        for conditional in ("population_level", "n_sources", "precision_conditions"):
            found.pop(conditional, None)
        found["represents"] = represents
        found[member_name] = copy.deepcopy(value)
        return codes

    return fault


def level(within: JsonValue, level_token: JsonValue = "specimen", codes: frozenset[str] = INVALID) -> Fault:
    return represented("population", "population_level", {"level": level_token, "within": within}, codes)


def slipping_beside(place: Callable[[Example], JsonObject], kind: str, among: tuple[str, ...] = ()) -> Fault:
    """A member one slip of `kind` from a member named at the place `place` finds, of `among` where given,
    beside it (or alone, for an optional member the place does not hold): it is refused for the slip alone,
    whatever else the place holds (`record_format.md` section 10 item 5)."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        found = place(example)
        name = draw(st.sampled_from(sorted(among or found)))
        new = slipped(name, kind)
        found[new if new not in found and new not in among else name + "q"] = copy.deepcopy(
            found.get(name, {})
        )
        return INVALID

    return fault


# A derivation valid by `provenance.md` section 5, which a fault of the derivation's regions breaks in one
# place.
DERIVATION: JsonObject = {
    "method": "arrhenius_mixing",
    "inputs": [
        {"record": {"id": "conformance/a", "version": "1.0.0", "content_hash": PIN}, "field": "x.y"},
        {"record": {"id": "conformance/b", "version": "1.0.0", "content_hash": PIN}, "field": "x.y"},
    ],
    "assumptions": ["ideal mixing"],
    "input_specimens": [{"input": 1.0, "specimen": {"lot": {"text": "B-17", "basis": "stated"}}}],
    "mixed_conditions": True,
}


def deriving(change: Callable[[JsonObject], None], codes: frozenset[str] = INVALID) -> Fault:
    """A derived value whose derivation is valid but for `change`."""

    def fault(draw: Draw, example: Example) -> frozenset[str]:
        found = provenance_of(example)
        found["origin"] = "derived"
        derivation = copy.deepcopy(DERIVATION)
        change(derivation)
        found["derivation"] = derivation
        return codes

    return fault


def setting_in(*path: str | int, value: JsonValue) -> Callable[[JsonObject], None]:
    """A change that sets the member or item at `path` inside a derivation to `value`."""

    def change(derivation: JsonObject) -> None:
        parent: JsonValue = derivation
        for step in path[:-1]:
            parent = parent[step] if isinstance(parent, dict) else parent[int(step)]  # type: ignore[index]
        if isinstance(parent, dict):
            parent[str(path[-1])] = copy.deepcopy(value)
        else:
            assert isinstance(parent, list)
            parent[int(path[-1])] = copy.deepcopy(value)

    return change


def dropping(*path: str) -> Callable[[JsonObject], None]:
    def change(derivation: JsonObject) -> None:
        parent: JsonValue = derivation
        for step in path[:-1]:
            parent = parent[step] if isinstance(parent, dict) else parent[int(step)]  # type: ignore[index]
        assert isinstance(parent, dict)
        del parent[path[-1]]

    return change


def derivation_missing(draw: Draw, example: Example) -> frozenset[str]:
    """A derived value without its derivation, which origin `derived` requires (`provenance.md` section 5)."""
    found = provenance_of(example)
    found["origin"] = "derived"
    found.pop("derivation", None)
    return INVALID


def source_missing_for_its_origin(draw: Draw, example: Example) -> frozenset[str]:
    """A value measured by its source, without the source (`provenance.md` section 2)."""
    found = provenance_of(example)
    found["origin"] = "measured_by_source"
    found.pop("source", None)
    return INVALID


def no_inputs(derivation: JsonObject) -> None:
    derivation["inputs"] = []
    derivation["input_specimens"] = []


def form_unknown(draw: Draw, example: Example) -> frozenset[str]:
    """A form token the reader does not know (`unknown_token`), beside the row's label where the row names
    one: the row names it for no such form (`form_invalid`, the decision log's literal reading)."""
    field = field_of(example)
    field["form"] = "spline"
    label = VOCABULARY.fields[example.field].label
    if label is None:
        field.pop("label", None)
        return UNKNOWN
    field["label"] = label
    return UNKNOWN | INVALID


def form_unknown_beside_a_slip(draw: Draw, example: Example) -> frozenset[str]:
    """A form token the reader does not know, beside a member one slip from another form's own member, which
    is named at a field's place when the form is unknown."""
    field = field_of(example)
    field["form"] = "spline"
    field.pop("label", None)
    field[draw(st.sampled_from(["intervals", "compositon", "tabel", "evidences"]))] = {}
    return UNKNOWN | INVALID


def licence_slip(draw: Draw, example: Example) -> frozenset[str]:
    licence = member(example.record, "licence")
    name = draw(st.sampled_from(["values", "evidence"]))
    licence[slipped(name, draw(st.sampled_from(SLIPS)))] = "CC0-1.0"
    return INVALID


# By region: each fault's name, and the fault. Every fault is written from the text: `read_side_contract.md`
# section 3, step 8, and the sections it names.
CATALOGUE: dict[str, dict[str, Fault]] = {
    "statistics_tokens": {
        "central_unknown": setting(block, "central", "mode", UNKNOWN),
        "basis_of_a_condition": setting(block, "basis", "stated", INVALID),
        "distribution_of_an_uncertainty": setting(block, "distribution", "student_t", INVALID),
        "distribution_of_a_declaration": setting(block, "distribution", "uniform", INVALID),
        "distribution_unknown": setting(block, "distribution", "weibull", UNKNOWN),
        "basis_of_another_member": setting(block, "basis", "reported_uncertainty", INVALID),
        "dispersion_status": setting(block, "dispersion", {"status": "unstated"}, INVALID),
        # A population level's tokens (`uncertainty.md` section 1): `level`, and `within`, from the levels.
        "level_unknown": level({"status": "none"}, "cohort", UNKNOWN),
        "within_unknown": level("cohort", "specimen", UNKNOWN),
        "precision_conditions_unknown": represented(
            "measurement", "precision_conditions", "lab_to_lab", UNKNOWN
        ),
    },
    "statistics_numbers": {
        "sd_negative": setting(block, "sd", -0.5, INVALID),
        "count_not_whole": setting(block, "n_specimens", 12.5, INVALID),
        "count_negative": setting(block, "n_donors", -1.0, INVALID),
        # `n_sources` is a count too (`read_side_contract.md` section 3, step 8).
        "n_sources_not_whole": represented("across_sources", "n_sources", 2.5),
        "n_sources_negative": represented("across_sources", "n_sources", -3.0),
        # `mean` is a number or a status object (`uncertainty.md` section 1).
        "mean_not_a_number": setting(block, "mean", "0.000692", INVALID),
    },
    "statistics_statuses": {
        "status_unknown": setting(block, "sd", {"status": "pending"}, UNKNOWN),
        "status_not_allowed": setting(block, "central", {"status": "unstated"}, INVALID),
        "status_beside_a_member": setting(block, "mean", {"status": "none", "note": "x"}, INVALID),
        "status_not_a_string": setting(block, "n_donors", {"status": 3.0}, INVALID),
        "reason_not_a_string": setting(block, "min", {"status": "unstated", "reason": 5.0}, INVALID),
        "uncertainty_status_beside_a_member": setting(
            block, "expanded_uncertainty", {"status": "none", "value": 0.1}, INVALID
        ),
        # Beside `status`, a member the uncertainty does not define is ignored (`provenance.md` section 1).
        "uncertainty_status_beside_an_unknown_member": setting(
            block, "expanded_uncertainty", {"status": "none", "note": "x"}, NOTHING
        ),
        # ... but not one a slip from `status` or `reason` (`record_format.md` section 10 item 5).
        "status_slip": setting(block, "expanded_uncertainty", {"status": "none", "reasn": "x"}, INVALID),
        # A population level's `within` holds `none` alone of the statuses (`provenance.md` section 1).
        "within_status_not_allowed": level(UNSTATED),
        # A constant's block holds `withheld` alone of the statuses; `not_applicable` is reference data's.
        "block_status_not_allowed": setting(field_of, "statistics", {"status": "not_applicable"}, INVALID),
    },
    "statistics_members": {
        "member_missing": removing(block, STATISTICS_REQUIRED),
        "member_null": nulling(block, STATISTICS_REQUIRED),
        "represents_missing": represents_missing,
        "population_level_missing": represents_without("population_level", "population"),
        "population_level_elsewhere": represents_without("population_level", "estimate"),
        "n_sources_elsewhere": represents_without("n_sources", "population"),
        "precision_conditions_missing": represents_without("precision_conditions", "measurement"),
    },
    "statistics_slips": {
        **{f"slip_{kind}": renaming(block, kind) for kind in SLIPS},
    },
    "statistics_slips_beside": {
        **{f"slip_beside_{kind}": slipping_beside(block, kind) for kind in SLIPS},
    },
    "uncertainty": {
        "dof_under_normal": uncertainty_fault({"dof": 8.0}),
        "dof_status_under_student_t": uncertainty_fault({"distribution": "student_t"}),
        "no_coverage_number": uncertainty_fault({"coverage_factor": {"status": "unstated"}}),
        "coverage_probability_above_one": uncertainty_fault({"coverage_probability": 1.5}),
        "coverage_factor_zero": uncertainty_fault({"coverage_factor": 0.0}),
        "uncertainty_value_negative": uncertainty_fault({"value": -0.02}),
        "uncertainty_precision_missing": uncertainty_fault({"represents": "measurement"}),
        "dof_zero": uncertainty_fault({"distribution": "student_t", "dof": 0.0}),
        "coverage_probability_zero": uncertainty_fault({"coverage_probability": 0.0}),
    },
    "uncertainty_tokens": {
        "uncertainty_represents_of_the_block": uncertainty_fault({"represents": "population"}),
        "uncertainty_represents_unknown": uncertainty_fault({"represents": "sample"}, UNKNOWN),
        "uncertainty_precision_unknown": uncertainty_fault(
            {"represents": "measurement", "precision_conditions": "lab_to_lab"}, UNKNOWN
        ),
        "uncertainty_basis_unknown": uncertainty_fault({"basis": "guess"}, UNKNOWN),
        "uncertainty_basis_of_the_block": uncertainty_fault({"basis": "reported_sd"}),
    },
    "conditions": {
        "range_reversed": setting(
            conditions_of,
            "temperature",
            {"range": [312.0, 310.0], "unit": "K", **{"basis": "stated"}},
            INVALID,
        ),
        "range_reversed_on_shear_rate": setting(
            conditions_of, "shear_rate", {"range": [1000.0, 10.0], "unit": "1/s", "basis": "stated"}, INVALID
        ),
        "value_and_range": setting(
            conditions_of, "temperature", {**TEMPERATURE, "range": [1.0, 2.0]}, INVALID
        ),
        # A numeric condition holds a value or a range (`provenance.md` section 6.1 item 1).
        "neither_value_nor_range": setting(
            conditions_of, "temperature", {"unit": "K", "basis": "stated"}, INVALID
        ),
        "plus_minus_empty": setting(conditions_of, "temperature", {**TEMPERATURE, "plus_minus": []}, INVALID),
        "plus_minus_two_bounds": setting(
            conditions_of,
            "temperature",
            {
                **TEMPERATURE,
                "plus_minus": [
                    {"stated_as": "bound", "value": 0.5, "unit": "K"},
                    {"stated_as": "bound", "value": 0.2, "unit": "K"},
                ],
            },
            INVALID,
        ),
        "plus_minus_unstated_beside_sd": setting(
            conditions_of,
            "temperature",
            {
                **TEMPERATURE,
                "plus_minus": [
                    {"stated_as": {"status": "unstated"}, "value": 0.5, "unit": "K"},
                    {"stated_as": "sd", "value": 0.1, "unit": "K"},
                ],
            },
            INVALID,
        ),
        "plus_minus_negative": setting(
            conditions_of,
            "temperature",
            {**TEMPERATURE, "plus_minus": [{"stated_as": "bound", "value": -0.5, "unit": "K"}]},
            INVALID,
        ),
        "plus_minus_unit_not_a_string": setting(
            conditions_of,
            "temperature",
            {**TEMPERATURE, "plus_minus": [{"stated_as": "bound", "value": 0.5, "unit": 1.0}]},
            INVALID,
        ),
        "unit_null": setting(conditions_of, "temperature", {**TEMPERATURE, "unit": None}, INVALID),
        "plus_minus_slip": setting(conditions_of, "temperature", {**TEMPERATURE, "plus_minsu": []}, INVALID),
        "value_not_a_number": setting(
            conditions_of, "temperature", {**TEMPERATURE, "value": "310.15"}, INVALID
        ),
    },
    "condition_tokens": {
        "token_of_another_row": setting(
            conditions_of, "density_kind", {"token": "tube", "basis": "stated"}, INVALID
        ),
        "token_unknown": setting(
            conditions_of, "density_kind", {"token": "porous", "basis": "stated"}, UNKNOWN
        ),
        # A condition's `token` knows the facts' tokens too: a member named `token` (step 8).
        "token_of_a_fact": setting(
            conditions_of, "density_kind", {"token": "stock", "basis": "stated"}, INVALID
        ),
        "set_or_measured_null": setting(
            conditions_of, "temperature", {**TEMPERATURE, "set_or_measured": None}, INVALID
        ),
        "set_or_measured_unknown": setting(
            conditions_of, "temperature", {**TEMPERATURE, "set_or_measured": "nominal"}, UNKNOWN
        ),
        "inferred_from_missing": setting(
            conditions_of, "temperature", {**TEMPERATURE, "basis": "inferred"}, INVALID
        ),
        "basis_unknown": setting(conditions_of, "temperature", {**TEMPERATURE, "basis": "guessed"}, UNKNOWN),
        "status_beside_unit": setting(
            conditions_of, "shear_rate", {"status": "unstated", "unit": "1/s"}, INVALID
        ),
        # A condition's status object refuses the members of either shape (`provenance.md` section 1).
        "status_beside_a_token": setting(
            conditions_of, "temperature", {"status": "unstated", "token": "apparent"}, INVALID
        ),
        # A token condition's `unit` is a string or a status object; step 9 refuses it.
        "token_condition_unit_not_a_string": setting(
            conditions_of, "measurement_geometry", {"token": "tube", "unit": 5.0, "basis": "stated"}, INVALID
        ),
        "name_unknown": setting(conditions_of, "temprature", {"value": "anything"}, NOTHING),
    },
    "specimen": {
        "fact_not_its_shape": setting(specimen_of, "preparation", "sliced", INVALID),
        "fact_range_reversed": setting(
            specimen_of, "donor_age", {"range": [3.0e8, 1.0e8], "unit": "s", "basis": "stated"}, INVALID
        ),
        "fact_other_without_text": setting(
            specimen_of, "preservation", {"token": "other", "basis": "stated"}, INVALID
        ),
        "fact_taxon_not_whole": setting(
            specimen_of, "species", {"ncbi_taxon": 9606.5, "label": "x", "basis": "stated"}, INVALID
        ),
        "fact_name_slip": setting(
            specimen_of, "tissue_stat", {"token": "in_vivo", "basis": "stated"}, INVALID
        ),
        "specimen_null": setting(field_of, "specimen", None, INVALID),
        "fact_text_beside_normal": setting(
            specimen_of,
            "disease_and_treatment_state",
            {"token": "normal", "text": "x", "basis": "stated"},
            INVALID,
        ),
        "fact_treated_without_text": setting(
            specimen_of, "disease_and_treatment_state", {"token": "treated", "basis": "stated"}, INVALID
        ),
        # A fact's unit is compared at step 9 alone, so neither of these refuses at step 8.
        "fact_unit_not_its_rows": setting(
            specimen_of, "post_mortem_interval", {"value": 1.0, "unit": "min", "basis": "stated"}, NOTHING
        ),
        "fact_unit_status_any_token": setting(
            specimen_of,
            "donor_age",
            {"value": 1.0e9, "unit": {"status": "approximate"}, "basis": "stated"},
            NOTHING,
        ),
        # Each member of a row's shape, of its type (`provenance.md` section 6.2).
        "species_label_not_a_string": setting(
            specimen_of, "species", {"ncbi_taxon": 9606.0, "label": 5.0, "basis": "stated"}, INVALID
        ),
        "uberon_not_a_string": setting(
            specimen_of, "anatomical_site", {"uberon": 2107.0, "label": "liver", "basis": "stated"}, INVALID
        ),
        "lot_text_not_a_string": setting(specimen_of, "lot", {"text": 17.0, "basis": "stated"}, INVALID),
        "fact_value_not_a_number": setting(
            specimen_of, "post_mortem_interval", {"value": "60", "unit": "s", "basis": "stated"}, INVALID
        ),
    },
    "specimen_tokens": {
        "fact_token_unknown": setting(
            specimen_of, "tissue_state", {"token": "cultured", "basis": "stated"}, UNKNOWN
        ),
        "fact_token_of_another_fact": setting(
            specimen_of, "tissue_state", {"token": "stock", "basis": "stated"}, INVALID
        ),
        # A fact's `token` knows the conditions' tokens too: a member named `token` (step 8).
        "fact_token_of_a_condition": setting(
            specimen_of, "tissue_state", {"token": "tube", "basis": "stated"}, INVALID
        ),
        "fact_status_beside_its_token": setting(
            specimen_of, "tissue_state", {"status": "unstated", "token": "in_vivo"}, INVALID
        ),
        "fact_basis_not_its_rows": setting(
            specimen_of, "mimics", {"text": "x", "basis": "inferred", "inferred_from": "y"}, INVALID
        ),
        # `basis` takes `stated` or `inferred` (`provenance.md` section 6); `reported_sd` is a block's.
        "fact_basis_of_another_member": setting(
            specimen_of, "lot", {"text": "x", "basis": "reported_sd"}, INVALID
        ),
    },
    "section_specimen": {
        "section_fact_not_its_shape": setting(section_specimen_of, "lot", "B-17", INVALID),
        "section_fact_name_slip": setting(
            section_specimen_of, "lots", {"text": "x", "basis": "stated"}, INVALID
        ),
        "section_specimen_null": setting(section_of, "specimen", None, INVALID),
    },
    "provenance": {
        "origin_unknown": setting(provenance_of, "origin", "estimated", UNKNOWN),
        "origin_missing": removing(provenance_of, ("origin",)),
        "source_key_not_a_string": setting(provenance_of, "source", {"key": 5.0}, INVALID),
        "source_slip": setting(provenance_of, "sources", {"key": "x"}, INVALID),
        "unchecked_member_broken": setting(provenance_of, "extraction", None, NOTHING),
        "source_null": setting(provenance_of, "source", None, INVALID),
        # `source` is present for origin `measured_by_source`, its `key` wherever present (step 8).
        "source_missing_for_its_origin": source_missing_for_its_origin,
        "source_key_missing": setting(provenance_of, "source", {"document": {"identifier": "x"}}, INVALID),
    },
    "derivation": {
        "derivation_missing": derivation_missing,
        "method_not_a_string": deriving(setting_in("method", value=5.0)),
        # With no input, no input specimen either, which would else be past the last input and refuse alone.
        "inputs_empty": deriving(no_inputs),
        "assumptions_not_texts": deriving(setting_in("assumptions", value=["ideal mixing", 5.0])),
        "input_specimens_missing": deriving(dropping("input_specimens")),
        "mixed_conditions_not_a_boolean": deriving(setting_in("mixed_conditions", value="yes")),
        "slip_beside_assumptions": deriving(setting_in("assumption", value=[])),
    },
    "derivation_inputs": {
        "input_record_member_missing": deriving(dropping("inputs", "0", "record", "content_hash")),
        "input_field_not_a_string": deriving(setting_in("inputs", 0, "field", value=5.0)),
        "input_index_not_whole": deriving(setting_in("input_specimens", 0, "input", value=0.5)),
        "input_index_negative": deriving(setting_in("input_specimens", 0, "input", value=-1.0)),
        "input_index_past_the_last": deriving(setting_in("input_specimens", 0, "input", value=2.0)),
        "input_fact_broken": deriving(setting_in("input_specimens", 0, "specimen", value={"lot": "B-17"})),
    },
    "field": {
        "unit_null": setting(field_of, "unit", None, INVALID),
        "unit_status_beside_a_member": setting(
            field_of, "unit", {"status": "unstated", "note": "x"}, INVALID
        ),
        "value_withheld": setting(field_of, "value", {"status": "withheld"}, frozenset({"withheld"})),
        "value_status_not_allowed": setting(field_of, "value", {"status": "unstated"}, INVALID),
        "value_not_a_number": setting(field_of, "value", "0.000692", INVALID),
        "label_unknown": setting(field_of, "label", "materica.fluid.bingham.v1", UNKNOWN),
        "label_of_another_field": label_of_another_field,
        "label_null": setting(field_of, "label", None, INVALID),
    },
    "field_slips": {
        **{f"slip_{kind}": renaming(field_of, kind, ("form", "unit", "value")) for kind in SLIPS},
    },
    "field_slips_optional": {
        **{f"slip_{kind}": slipping_beside(field_of, kind, ("specimen", "label", "fit")) for kind in SLIPS},
    },
    "field_form": {
        "form_unknown_beside_the_label": form_unknown,
        "form_unknown_beside_a_slip": form_unknown_beside_a_slip,
    },
    "record": {
        "envelope_slip": record_slip("envelope"),
        "body_slip": record_slip("body"),
        "section_name_slip": record_slip("sections"),
        "section_member_slip": record_slip("section"),
        "field_name_slip": record_slip("fields"),
        "licence_slip": licence_slip,
    },
}
REGIONS = tuple(CATALOGUE)


# The faults that give `unknown_token` alone, by region and name; every other fault gives `form_invalid`,
# `withheld`, `unknown_token` with `form_invalid`, or nothing.
TOKEN_FAULTS = tuple(
    (region, name)
    for region, faults in CATALOGUE.items()
    for name in sorted(faults)
    if name.endswith("unknown")
)
PASSING_FAULTS = {
    ("condition_tokens", "name_unknown"),
    ("provenance", "unchecked_member_broken"),
    ("specimen", "fact_unit_not_its_rows"),
    ("specimen", "fact_unit_status_any_token"),
    ("statistics_statuses", "uncertainty_status_beside_an_unknown_member"),
}
# The part of the record each region's faults change: two faults of a draw never meet in one.
GROUPS = {
    "statistics": ("statistics_", "uncertainty"),
    "conditions": ("condition",),
    "specimen": ("specimen", "section_specimen"),
    "provenance": ("provenance", "derivation"),
    "field": ("field",),
    "record": ("record",),
}


def group(region: str) -> str:
    return next(name for name, prefixes in GROUPS.items() if region.startswith(prefixes))


@st.composite
def faulty_records(
    draw: Draw, size: Size = SIZE, faults: int | None = None, among: tuple[str, ...] = ()
) -> Example:
    """A valid record with one fault of the catalogue; or, in one draw in four, two of two parts of the
    record, half of those a token fault beside another, so that the two give two codes. Where `among` names
    faults (`region.name`), the first fault is one of them: a mutant's planned search."""
    example = draw(valid_records(size))
    mode = draw(st.sampled_from(["one", "one", "one", "two", "two_codes", "one", "one", "one"]))
    if faults is not None:
        mode = "one" if faults == 1 else "two"
    planned = [(fault.partition(".")[0], fault.partition(".")[2]) for fault in among]
    if mode == "one":
        region = draw(st.sampled_from(REGIONS))
        chosen = [(region, draw(st.sampled_from(sorted(CATALOGUE[region]))))]
        if planned:
            chosen = [draw(st.sampled_from(planned))]
    else:
        first = draw(st.sampled_from(TOKEN_FAULTS)) if mode == "two_codes" and not planned else None
        if planned:
            first = draw(st.sampled_from(planned))
        if first is None:
            region = draw(st.sampled_from(REGIONS))
            first = (region, draw(st.sampled_from(sorted(CATALOGUE[region]))))
        others = [
            (region, name)
            for region, faults_of in CATALOGUE.items()
            if group(region) != group(first[0])
            for name in sorted(faults_of)
            if mode == "two" or ((region, name) not in TOKEN_FAULTS and (region, name) not in PASSING_FAULTS)
        ]
        chosen = [first, draw(st.sampled_from(others))]
    faulty = example._replace(record=copy.deepcopy(example.record))
    expected: frozenset[str] = NOTHING
    for region, name in chosen:
        expected |= CATALOGUE[region][name](draw, faulty)
    return faulty._replace(faults=tuple(f"{region}.{name}" for region, name in chosen), expected=expected)
