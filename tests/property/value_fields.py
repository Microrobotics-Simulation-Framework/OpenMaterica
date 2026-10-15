# SPDX-License-Identifier: Apache-2.0
"""Strategies for value fields: those the specification allows, and those it forbids by one fault.

A field is built from what the text gives, never from the writer schema, so that a fault in the writer schema
cannot move the oracle with it: its tokens from the vocabulary, which is generated from the specification's
tables and token lists; the specimen facts' members from `provenance.md` section 6.2's JSON shapes; and the
rest from the member tables and sentences of `record_format.md` sections 4 to 6, `provenance.md` sections 1 to
7 and `uncertainty.md` section 1, as each builder cites.

`fields` draws a field the text allows, whatever its name, and `bodies` a record body holding a registered
field in its place, a section's `fields` or an overlay's `replaces`, bound to its row of `record_format.md`
section 4.1: its forms, the bases it allows, its unit and its label, read from the vocabulary's rows, never
from the bindings the writer applies. `faulty_fields` draws, for one family of faults, a field or a body with
exactly one fault the text names, built on one planned so that the fault's place exists, and returns that
base beside it with the fault's name and place, so that a refusal can be traced to the fault.
"""

import copy
import functools
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from scripts.gen_vocabulary import SPECIFICATION, between, cell_of, codes, listed, only_code, prose, table
from tests.property import strategies
from tests.property.strategies import SIZE, Size
from tests.spec_sync.schemas import SCHEMA

Json = dict[str, JsonValue]


def mapping(value: JsonValue) -> Json:
    assert isinstance(value, dict)
    return value


def listing(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def _vocabulary(name: str) -> Json:
    return mapping(json.loads((SCHEMA / "vocabulary" / name).read_text(encoding="utf-8")))


def _lists(name: str) -> dict[str, list[str]]:
    """The file's lists of tokens; its other definitions bind names to their rows, and are no oracle."""
    return {
        list_name: [str(token) for token in listing(mapping(definition)["enum"])]
        for list_name, definition in mapping(_vocabulary(name)["$defs"]).items()
        if "enum" in mapping(definition)
    }


VOCABULARY_FILES = ("forms", "statistics", "provenance", "conditions", "specimen_facts", "fields", "labels")
# Every token list of the vocabulary, by its name in the `$defs` of its file.
LISTS: dict[str, list[str]] = {
    list_name: tokens for file in VOCABULARY_FILES for list_name, tokens in _lists(f"{file}.json").items()
}
CONDITIONS = mapping(_vocabulary("conditions.json")["conditions"])
# `record_format.md` section 4.1's rows, by `<section>.<field>`.
FIELDS = mapping(_vocabulary("fields.json")["fields"])
FACTS = mapping(_vocabulary("specimen_facts.json")["facts"])
NUMERIC_CONDITIONS = [name for name in CONDITIONS if mapping(CONDITIONS[name])["shape"] == "numeric"]
TOKEN_CONDITIONS = [name for name in CONDITIONS if name not in NUMERIC_CONDITIONS]
TOKEN_FACTS = [name for name in FACTS if listing(mapping(FACTS[name])["tokens"])]
# The units the text registers for conditions, beside a fact's own `s`: what a unit wrongly fixed would hold.
UNITS = sorted({str(mapping(CONDITIONS[name])["unit"]) for name in NUMERIC_CONDITIONS} | {"min", "h", "a"})

# `provenance.md` section 1 item 2, and item 5's table: the tokens a status object may hold at each place.
ANY_STATUS = ("unstated", "not_checked", "none", "not_applicable", "withheld")
NOT_WITHHELD = ANY_STATUS[:4]

# `record_format.md` section 5: the form's member is `value` for a constant, otherwise named like the form.
FORMS = LISTS["form"]


def form_member(form: str) -> str:
    return "value" if form == "constant" else form


# `uncertainty.md` section 1 rule 1: the members present exactly where `represents` calls for them.
CONDITIONAL = {
    "population": "population_level",
    "across_sources": "n_sources",
    "measurement": "precision_conditions",
}


def _members() -> tuple[list[str], list[str], list[str], dict[str, str], list[str]]:
    """The members the text's tables name: the statistics block's always present and an uncertainty's
    (`uncertainty.md` section 1), an evidence entry's (`record_format.md` section 4.3), the member each
    extraction method requires in the extraction object, and the provenance object's required members
    (`provenance.md` sections 2 and 3)."""
    uncertainty = (SPECIFICATION / "uncertainty.md").read_text(encoding="utf-8")
    rows = table(uncertainty, "## 1. The statistics block")
    conditional = codes(
        between(prose(uncertainty), "1. Every member is present", "each present exactly where")
    )
    assert set(conditional) == set(CONDITIONAL.values())
    block = [member for row in rows for member in codes(row["Member"]) if member not in conditional]
    sketch = re.match(r"`(\{[^`]*\})`", cell_of(rows, "relative_uncertainty"))
    assert sketch is not None
    record_format = prose((SPECIFICATION / "record_format.md").read_text(encoding="utf-8"))
    report = listed(record_format, "Each entry holds ", ". A device")
    provenance = (SPECIFICATION / "provenance.md").read_text(encoding="utf-8")
    extraction = {
        method: codes(row["Also requires"])[0]
        for row in table(provenance, "## 3. Extraction")
        for method in codes(row["Method"])
        if row["Also requires"].startswith("`") and "in the provenance object" not in row["Also requires"]
    }
    required = [
        only_code(row["Member"])
        for row in table(provenance, "## 2. The provenance object")
        if row["Required"] == "yes"
    ]
    return block, re.findall(r'"([a-z_]+)"', sketch[1]), report, extraction, required


BLOCK_MEMBERS, UNCERTAINTY_MEMBERS, ENTRY_MEMBERS, EXTRACTION_MEMBER, PROVENANCE_REQUIRED = _members()
# An evidence entry's members that hold the source's words: all but its `standard` and its `provenance`.
REPORT = tuple(member for member in ENTRY_MEMBERS if member not in ("standard", "provenance"))
# `provenance.md` section 7 item 2: the members a reference-only entry withholds, every one but `provenance`.
WITHHELD_WHOLE = tuple(member for member in ENTRY_MEMBERS if member != "provenance")


@dataclass(frozen=True)
class Plan:
    """What a field drawn must hold; None draws it. Each part named in `rich` is drawn with every optional
    member and every member that may hold a status object in its own shape (the parts: block, uncertainty,
    conditions, specimen, provenance, composition, evidence, label), so that each place a fault may change
    exists. A `minimal` plan leaves out what is optional outside those parts. `registered` draws the field
    for a registered name, bound to its row; `place` and `alternatives` say where a body holds it and whether
    it is the alternatives of several."""

    registered: str | None = None
    place: str | None = None
    alternatives: bool | None = None
    form: str | None = None
    withheld: bool | None = None
    represents: str | None = None
    origin: str | None = None
    method: str | None = None
    uncertainty: tuple[str, str] | None = None  # the relative uncertainty's distribution and represents
    rich: frozenset[str] = field(default_factory=frozenset[str])
    minimal: bool = False

    def full(self, part: str) -> bool:
        return part in self.rich


ANY = Plan()
MINIMAL = Plan(
    form="constant", withheld=False, origin="measured_by_contributor", method="own_measurement", minimal=True
)

TEXT = strategies.TEXT
NUMBERS = st.floats(allow_nan=False, allow_infinity=False)
NOT_NEGATIVE = st.floats(min_value=0.0, allow_nan=False, allow_infinity=False)
POSITIVE = st.floats(min_value=0.0, exclude_min=True, allow_nan=False, allow_infinity=False)
NEGATIVE = st.floats(max_value=0.0, exclude_max=True, allow_nan=False, allow_infinity=False)
NOT_POSITIVE = st.floats(max_value=0.0, allow_nan=False, allow_infinity=False)
# A whole number, as the reader gives it: a double with no fractional part (`record_format.md` 1 item 6).
WHOLE = st.integers(0, 10**9).map(float)
HASHES = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64).map(lambda digits: "sha256:" + digits)
RECORD_IDS = st.from_regex(r"[a-z0-9_]{1,8}/[A-Za-z0-9_.-]{1,8}", fullmatch=True)
VERSIONS = st.tuples(*[st.integers(0, 99)] * 3).map(lambda parts: ".".join(map(str, parts)))


def texts(draw: st.DrawFn, most: int) -> list[JsonValue]:
    found: list[JsonValue] = list(draw(st.lists(TEXT, max_size=most)))
    return found


def objects(size: Size) -> st.SearchStrategy[Json]:
    """Any JSON object: what a placeholder holds until its members are named."""
    return st.dictionaries(TEXT, strategies.json_values(size=size), max_size=size.members)


def placeholders(size: Size) -> st.SearchStrategy[Json]:
    """A placeholder beside a status object: any object but one holding `status`, which would be a status
    object (`provenance.md` section 1 item 5)."""
    return objects(size).map(lambda found: {name: value for name, value in found.items() if name != "status"})


def optional(draw: st.DrawFn, plan: Plan, part: str) -> bool:
    """Whether to draw an optional member of `part`."""
    return plan.full(part) or (not plan.minimal and draw(st.booleans()))


@st.composite
def status(draw: st.DrawFn, allowed: tuple[str, ...]) -> Json:
    found: Json = {"status": draw(st.sampled_from(allowed))}
    if draw(st.booleans()):
        found["reason"] = draw(TEXT)
    return found


def shape_or_status(
    draw: st.DrawFn, full: bool, shape: st.SearchStrategy[JsonValue], allowed: tuple[str, ...]
) -> JsonValue:
    """A member that may hold its shape or a status object: its shape in a part drawn in full."""
    return draw(shape) if full or draw(st.integers(0, 3)) else draw(status(allowed))


@st.composite
def based(draw: st.DrawFn) -> Json:
    """`provenance.md` section 6: `stated`, or `inferred` with an `inferred_from` text."""
    if draw(st.booleans()):
        return {"basis": "stated"}
    return {"basis": "inferred", "inferred_from": draw(TEXT)}


@st.composite
def ranges(draw: st.DrawFn) -> list[JsonValue]:
    low, high = sorted(draw(st.lists(NUMBERS, min_size=2, max_size=2)))
    return [low, high]


def units() -> st.SearchStrategy[JsonValue]:
    """`record_format.md` section 4.2: a unit is a string or a status object, compared at step 9 alone."""
    return st.one_of(TEXT, status(ANY_STATUS))


def row_of(name: str) -> Json:
    return mapping(FIELDS[name])


def field_unit(name: str) -> st.SearchStrategy[JsonValue]:
    """Section 4.2: a field's unit equals its registered unit; one registered as a status object equals one
    holding the same token, whatever its reason."""
    unit = row_of(name)["unit"]
    return st.just(unit) if isinstance(unit, str) else status((str(mapping(unit)["status"]),))


# Conditions: `provenance.md` section 6.1 and its items 1, 6 and 7.


@st.composite
def plus_minus(draw: st.DrawFn, unit: str) -> list[JsonValue]:
    """Item 6: at most one entry of each kind, one of unstated kind alone, each in the condition's unit."""
    unstated: JsonValue = {"status": "unstated"}
    stated: list[JsonValue] = list(LISTS["stated_as"])
    kinds = draw(st.sampled_from([*([kind] for kind in stated), stated, [unstated]]))
    return [
        {"stated_as": kind, "value": draw(NOT_NEGATIVE), "unit": unit}
        for kind in draw(st.permutations(kinds))
    ]


def registered_unit(name: str) -> str:
    """The unit a numeric condition registers (section 6.1), which its `unit` and its `plus_minus` entries'
    hold: `record_format.md` section 4.2 holds a condition's unit to it as a field's to the field's."""
    return str(mapping(CONDITIONS[name])["unit"])


@st.composite
def numeric_condition(draw: st.DrawFn, plan: Plan, name: str) -> Json:
    found: Json = draw(based())
    if draw(st.booleans()):
        found["value"] = draw(NUMBERS)
    else:
        found["range"] = draw(ranges())
    found["unit"] = registered_unit(name)
    if optional(draw, plan, "conditions"):
        found["plus_minus"] = draw(plus_minus(registered_unit(name)))
    if optional(draw, plan, "conditions"):
        found["set_or_measured"] = draw(st.sampled_from(LISTS["set_or_measured"]))
    return found


@st.composite
def token_condition(draw: st.DrawFn, name: str) -> Json:
    return {**draw(based()), "token": draw(st.sampled_from(LISTS[f"{name}_token"]))}


@st.composite
def conditions(draw: st.DrawFn, plan: Plan) -> Json:
    if plan.full("conditions"):
        names = list(CONDITIONS)
    else:
        names = [] if plan.minimal else draw(st.lists(st.sampled_from(list(CONDITIONS)), unique=True))
    found: Json = {}
    for name in names:
        shape = numeric_condition(plan, name) if name in NUMERIC_CONDITIONS else token_condition(name)
        found[name] = shape_or_status(draw, plan.full("conditions"), shape, ANY_STATUS)
    return found


# Specimen facts: each member of a row's JSON shape, read from `provenance.md` section 6.2.


class FactMember(NamedTuple):
    name: str
    kind: str  # value, range, basis, whole, text, identifier, token or fixed
    fixed: str = ""  # a fixed member's value, or an identifier's prefix
    required_for: str = ""  # the token for which a member is required, where the row says so
    exactly_for: tuple[str, ...] = ()  # the tokens with which, and only with which, a member is present


FACT_ROWS = table(
    (SPECIFICATION / "provenance.md").read_text(encoding="utf-8"), "### 6.2 Specimen facts of schema 0.1.0"
)


def present_exactly(cell: str) -> dict[str, tuple[str, ...]]:
    """The members a row's sentence gives as present exactly with some tokens: "`text` ... is present exactly
    when `token` is `diseased` or `treated`"."""
    found = re.search(
        r"`([a-z_]+)`[^`]* is present exactly when `token` is (`[a-z_]+`(?:(?:,|, or| or) `[a-z_]+`)*)", cell
    )
    return {found[1]: tuple(codes(found[2]))} if found else {}


def fact_shapes() -> dict[str, list[list[FactMember]]]:
    """Each fact's shapes, each a list of its members: `{"value", "unit": "s", "basis"}` or `{...}`."""
    return {
        only_code(row["Name"]): [
            members_of(sketch, present_exactly(row["JSON shape"]))
            for sketch in re.findall(r"`(\{[^`]*\})`", row["JSON shape"])
        ]
        for row in FACT_ROWS
    }


def members_of(sketch: str, exactly: dict[str, tuple[str, ...]]) -> list[FactMember]:
    found: list[FactMember] = []
    for part in re.split(r', (?="[a-z_]+")', sketch.strip("{}")):
        name, _, value = part.partition(": ")
        name = name.strip('"')
        if not value:
            found.append(FactMember(name, "basis" if name == "basis" else "value"))
        elif value.startswith("["):
            found.append(FactMember(name, "range"))
        elif value == "<integer>":
            found.append(FactMember(name, "whole"))
        elif identifier := re.fullmatch(r'"([A-Z]+):<digits>"', value):
            found.append(FactMember(name, "identifier", identifier[1]))
        elif " | " in value:
            found.append(FactMember(name, "token"))
        elif value.startswith('"'):
            found.append(FactMember(name, "fixed", value.strip('"')))
        else:
            required = re.fullmatch(r"<[^,>]*, required for ([a-z_]+)>", value)
            found.append(
                FactMember(
                    name,
                    "text",
                    required_for=required[1] if required else "",
                    exactly_for=exactly.get(name, ()),
                )
            )
    return found


FACT_SHAPES = fact_shapes()


@st.composite
def fact(draw: st.DrawFn, name: str) -> Json:
    members = draw(st.sampled_from(FACT_SHAPES[name]))
    tokens = [member for member in members if member.kind == "token"]
    token = draw(st.sampled_from(LISTS[f"{name}_token"])) if tokens else ""
    found: Json = {member.name: token for member in tokens}
    values: dict[str, Callable[[], JsonValue]] = {
        "value": lambda: draw(NUMBERS),
        "range": lambda: draw(ranges()),
        "whole": lambda: draw(st.integers(1, 10**7).map(float)),
        "text": lambda: draw(TEXT),
    }
    for member in members:
        if member.kind == "basis":
            found |= draw(based())
        elif member.kind == "fixed":
            found[member.name] = member.fixed
        elif member.kind == "identifier":
            found[member.name] = f"{member.fixed}:{draw(st.integers(0, 10**7))}"
        elif member.kind in values and (
            token in member.exactly_for
            if member.exactly_for
            else not member.required_for or token == member.required_for or draw(st.booleans())
        ):
            found[member.name] = values[member.kind]()
    return found


@st.composite
def specimens(draw: st.DrawFn, full: bool) -> Json:
    names = list(FACTS) if full else draw(st.lists(st.sampled_from(list(FACTS)), unique=True))
    return {name: shape_or_status(draw, full, fact(name), ANY_STATUS) for name in names}


# The statistics block and its uncertainties: `uncertainty.md` section 1, its table and rules.


@st.composite
def uncertainty(draw: st.DrawFn, full: bool, kinds: tuple[str, str] | None = None) -> Json:
    distribution, represents = kinds or (
        draw(st.sampled_from([*LISTS["uncertainty_distribution"], "unstated"])),
        draw(st.sampled_from([*LISTS["uncertainty_represents"], "unstated"])),
    )
    coverage = draw(st.sampled_from(["factor", "probability", "both"]))
    probabilities = st.floats(min_value=0.0, max_value=1.0, exclude_min=True)
    found: Json = {
        "value": draw(NOT_NEGATIVE),
        "coverage_factor": draw(POSITIVE) if coverage != "probability" else draw(status(ANY_STATUS)),
        "coverage_probability": draw(probabilities) if coverage != "factor" else draw(status(ANY_STATUS)),
        "distribution": distribution if distribution != "unstated" else {"status": "unstated"},
        "dof": draw(POSITIVE) if distribution == "student_t" else draw(status(ANY_STATUS)),
        "basis": draw(st.sampled_from(LISTS["uncertainty_basis"])),
        "represents": represents if represents != "unstated" else {"status": "unstated"},
    }
    if represents == "measurement":
        found["precision_conditions"] = shape_or_status(
            draw, full, st.sampled_from(LISTS["precision_conditions"]), ("unstated",)
        )
    return found


@st.composite
def statistics_block(draw: st.DrawFn, plan: Plan) -> Json:
    full = plan.full("block")
    represents = plan.represents or draw(
        st.sampled_from([*LISTS["represents"], "unstated", "not_applicable"])
    )
    numbers = {"mean": NUMBERS, "sd": NOT_NEGATIVE, "min": NUMBERS, "max": NUMBERS}
    relative = uncertainty(plan.full("uncertainty"), plan.uncertainty)
    found: Json = {
        "central": shape_or_status(draw, full, st.sampled_from(LISTS["central"]), ("not_applicable",)),
        **{count: shape_or_status(draw, full, WHOLE, ANY_STATUS) for count in ("n_specimens", "n_donors")},
        **{member: shape_or_status(draw, full, number, ANY_STATUS) for member, number in numbers.items()},
        "distribution": shape_or_status(
            draw, full, st.sampled_from(LISTS["statistics_distribution"]), ("unstated",)
        ),
        "basis": shape_or_status(draw, full, st.sampled_from(LISTS["statistics_basis"]), ("not_applicable",)),
        "represents": represents if represents in LISTS["represents"] else {"status": represents},
        "dispersion": draw(st.sampled_from(LISTS["dispersion"])),
        "relative_uncertainty": draw(relative)
        if plan.uncertainty
        else shape_or_status(draw, full, relative, ANY_STATUS),
        "expanded_uncertainty": shape_or_status(draw, full, uncertainty(full), ANY_STATUS),
    }
    if represents == "population":
        level: Json = {
            "level": draw(st.sampled_from(LISTS["level"])),
            "within": draw(st.one_of(st.sampled_from(LISTS["level"]), status(("none",))))
            if not full
            else "donor",
        }
        found["population_level"] = shape_or_status(draw, full, st.just(level), ("unstated",))
    elif represents == "across_sources":
        found["n_sources"] = shape_or_status(draw, full, WHOLE, ANY_STATUS)
    elif represents == "measurement":
        found["precision_conditions"] = shape_or_status(
            draw, full, st.sampled_from(LISTS["precision_conditions"]), ("unstated",)
        )
    return found


# The forms' members: `record_format.md` sections 4.3 and 6.


@st.composite
def interval(draw: st.DrawFn, full: bool) -> Json:
    """Item 1: numbers in order, at most one bound `{"status": "none"}`; item 2: its basis."""
    low, high = draw(ranges())
    one_sided: list[list[JsonValue]] = [[{"status": "none"}, high], [low, {"status": "none"}]]
    bounds = [low, high] if full else draw(st.sampled_from([[low, high], *one_sided]))
    return {"lower": bounds[0], "upper": bounds[1], "basis": draw(st.sampled_from(LISTS["interval_basis"]))}


@st.composite
def composition(draw: st.DrawFn, plan: Plan, size: Size) -> Json:
    """Items 1 to 5: a basis, a sum rule, a stated sum where given, one or more components, none twice; for a
    registered field, a basis its row allows (`record_format.md` section 4.1)."""
    bases = mapping(row_of(plan.registered).get("bases", {})).get("composition") if plan.registered else None
    chosen = draw(
        st.lists(st.sampled_from(LISTS["component"]), min_size=1, max_size=size.members, unique=True)
    )
    components: list[JsonValue] = []
    for component in chosen:
        entry: Json = {"component": component, "fraction": draw(st.floats(0.0, 1.0))}
        if optional(draw, plan, "composition"):
            entry["statistics"] = draw(statistics_block(replace(plan, represents=None, uncertainty=None)))
        components.append(entry)
    found: Json = {
        "basis": draw(
            st.sampled_from([str(basis) for basis in listing(bases)] if bases else LISTS["composition_basis"])
        ),
        "sum_rule": draw(st.sampled_from(LISTS["sum_rule"])),
        "components": components,
    }
    if optional(draw, plan, "composition"):
        found["stated_sum"] = draw(NUMBERS)
    return found


@st.composite
def evidence_entry(draw: st.DrawFn, plan: Plan, size: Size, *, withheld: bool) -> Json:
    """Section 4.3: every member present; a reference-only entry withheld whole, its provenance carrying the
    recipe (`provenance.md` section 7 item 2); `standard`'s `year` whole."""
    provenance = draw(provenances(replace(plan, origin=None, method=None), size, withheld=withheld))
    if withheld:
        return {
            **{member: {"status": "withheld"} for member in WITHHELD_WHOLE},
            "provenance": provenance,
        }
    full = plan.full("evidence")
    standard: Json = {"designation": draw(TEXT), "year": draw(st.integers(1900, 2100).map(float))}
    found: Json = {member: shape_or_status(draw, full, TEXT, NOT_WITHHELD) for member in REPORT}
    return {
        **found,
        "standard": shape_or_status(draw, full, st.just(standard), NOT_WITHHELD),
        "provenance": provenance,
    }


@st.composite
def evidence(draw: st.DrawFn, plan: Plan, size: Size, *, withheld: bool) -> list[JsonValue]:
    """At least one entry; where the plan withholds, one withheld whole among them."""
    kinds = [withheld and index == 0 for index in range(draw(st.integers(1, size.members)))]
    return [draw(evidence_entry(plan, size, withheld=kind)) for kind in draw(st.permutations(kinds))]


# Provenance: `provenance.md` sections 2 to 5 and 7.


@st.composite
def columns(draw: st.DrawFn) -> Json:
    """Section 2 item 2: a table's column, its header quoted and its index counted from 1 as printed."""
    return {"header": draw(TEXT), "index": float(draw(st.integers(1, 99)))}


@st.composite
def searches(draw: st.DrawFn) -> Json:
    """Section 2's row: the sources' own weighting where they have one, and what they are."""
    found: Json = {"inputs": draw(st.sampled_from(LISTS["search_inputs"]))}
    if draw(st.booleans()):
        found["weighting"] = draw(TEXT)
    return found


@st.composite
def locator(draw: st.DrawFn, plan: Plan) -> Json:
    """Section 2 items 2 and 7: its type, and where it is."""
    found: Json = {"type": draw(st.sampled_from(LISTS["locator_type"]))}
    members: dict[str, st.SearchStrategy[JsonValue]] = {
        "label": TEXT,
        "page": st.integers(1, 10**4).map(float),
        "column": columns(),
        "row": TEXT,
        "entry": TEXT,
    }
    for member, value in members.items():
        if optional(draw, plan, "provenance"):
            found[member] = draw(value)
    return found


def documents() -> st.SearchStrategy[Json]:
    return st.fixed_dictionaries({"identifier": TEXT, "version": TEXT})


@st.composite
def source(draw: st.DrawFn, plan: Plan) -> Json:
    return {"key": draw(TEXT), "document": draw(documents()), "locator": draw(locator(plan))}


@st.composite
def extraction(draw: st.DrawFn, plan: Plan, method: str, size: Size) -> Json:
    """Section 3: the method, with the member its row requires; `source_unit` and `conversion` (item 2)."""
    found: Json = {"method": method}
    if (member := EXTRACTION_MEMBER.get(method)) is not None:
        found[member] = draw(objects(size)) if member == "digitisation" else draw(TEXT)
    for member in ("source_unit", "conversion"):
        if optional(draw, plan, "provenance"):
            found[member] = draw(TEXT)
    return found


@st.composite
def evidence_record(draw: st.DrawFn, plan: Plan) -> Json:
    """Section 4: a quote or its hash, never both, with the locator, document and copy it was read at."""
    found: Json = {}
    quote = (
        "quote_sha256"
        if plan.full("provenance")
        else draw(st.sampled_from(["quote", "quote_sha256", "none"]))
    )
    if quote == "quote":
        found["quote"] = draw(TEXT)
    elif quote == "quote_sha256":
        found["quote_sha256"] = draw(HASHES)
    if optional(draw, plan, "provenance"):
        found["locator"] = draw(locator(plan))
    if optional(draw, plan, "provenance"):
        found["document"] = draw(documents())
    if optional(draw, plan, "provenance"):
        found["copy"] = {"sha256": draw(TEXT), "retrieved": draw(TEXT)}
    return found


@st.composite
def review(draw: st.DrawFn) -> Json:
    """Section 2's row: who checked, their ORCID, the date, independence and the checklist covered."""
    return {
        "result": draw(st.sampled_from(LISTS["review_result"])),
        "reviewer": draw(TEXT),
        "orcid": draw(TEXT),
        "date": draw(TEXT),
        "independent_of_extraction": draw(st.booleans()),
        "checklist": texts(draw, 3),
    }


@st.composite
def derivation_inputs(draw: st.DrawFn) -> Json:
    """Section 5 item 1: an input's record, pinned by id, version and content hash, and its field."""
    record: Json = {"id": draw(RECORD_IDS), "version": draw(VERSIONS), "content_hash": draw(HASHES)}
    return {"record": record, "field": draw(TEXT)}


@st.composite
def derivation(draw: st.DrawFn, plan: Plan, size: Size) -> Json:
    """Section 5: a method, pinned inputs, assumptions, each input's specimen facts by its index."""
    full = plan.full("provenance")
    inputs: list[JsonValue] = list(draw(st.lists(derivation_inputs(), min_size=1, max_size=size.members)))
    indices = draw(st.lists(st.integers(0, len(inputs) - 1), unique=True, min_size=1 if full else 0))
    found: Json = {
        "method": draw(TEXT),
        "inputs": inputs,
        "assumptions": texts(draw, size.members),
        "input_specimens": [{"input": float(index), "specimen": draw(specimens(False))} for index in indices],
    }
    if optional(draw, plan, "provenance"):
        found["mixed_conditions"] = draw(st.booleans())
    return found


@st.composite
def provenances(
    draw: st.DrawFn, plan: Plan, size: Size, *, withheld: bool = False, across_sources: bool = False
) -> Json:
    """Section 2's table: the four members required, each other where its row requires it; section 3's
    methods with what they require beside them; section 7 item 2's recipe for a withheld value."""
    full = plan.full("provenance")
    origin = plan.origin or draw(st.sampled_from(LISTS["origin"]))
    method = plan.method or draw(st.sampled_from(LISTS["extraction_method"]))
    found: Json = {
        "origin": origin,
        "extraction": draw(extraction(plan, method, size)),
        "assistance": {"status": "none"} if full else draw(st.one_of(status(("none",)), placeholders(size))),
        "review": draw(review()) if full else draw(st.one_of(status(("not_checked",)), review())),
    }
    required = {
        "source": origin == "measured_by_source",
        "derivation": origin == "derived" or method == "derivation",
        "formulation": origin == "evaluated_from_formulation" or method == "formulation",
        "search": across_sources,
        "recipe": withheld,
    }
    members: dict[str, st.SearchStrategy[JsonValue]] = {
        "source": source(plan),
        "evidence": evidence_record(plan),
        "derivation": derivation(plan, size),
        "formulation": objects(size),
        "search": searches(),
        "import": objects(size),
        "recipe": objects(size),
    }
    for member, value in members.items():
        if required.get(member) or full or (not plan.minimal and not draw(st.integers(0, 3))):
            found[member] = draw(value)
    return found


# A value field: `record_format.md` section 5.


@st.composite
def form_fields(draw: st.DrawFn, plan: Plan = ANY, size: Size = SIZE) -> Json:
    forms = [str(form) for form in listing(row_of(plan.registered)["forms"])] if plan.registered else FORMS
    form = plan.form or draw(st.sampled_from(forms))
    withheld = plan.withheld if plan.withheld is not None else not draw(st.integers(0, 4))
    found: Json = {"form": form, "unit": draw(field_unit(plan.registered) if plan.registered else units())}
    across_sources = False
    if form == "evidence":
        found["evidence"] = draw(evidence(plan, size, withheld=withheld))
        found["conditions"] = {}
    else:
        if withheld:
            member: JsonValue = {"status": "withheld"}
        elif form == "constant":
            member = draw(NUMBERS)
        elif form == "interval":
            member = draw(interval(plan.full("block")))
        elif form == "composition":
            member = draw(composition(plan, size))
        else:
            member = draw(placeholders(size))
        found[form_member(form)] = member
        found["conditions"] = draw(conditions(plan))
        if withheld:
            found["statistics"] = {"status": "withheld"}
        elif form == "reference_data" and not plan.rich and not draw(st.integers(0, 3)):
            found["statistics"] = {"status": "not_applicable"}
        else:
            found["statistics"] = block = draw(statistics_block(plan))
            across_sources = block["represents"] == "across_sources"
    provenance = draw(
        provenances(plan, size, withheld=withheld and form != "evidence", across_sources=across_sources)
    )
    found["provenance"] = provenance
    if provenance["origin"] == "fitted" or mapping(provenance["extraction"])["method"] == "fit":
        found["fit"] = draw(objects(size))
    elif optional(draw, plan, "fit"):
        found["fit"] = draw(objects(size))
    if plan.full("specimen") or (not plan.minimal and draw(st.booleans())):
        found["specimen"] = draw(specimens(plan.full("specimen")))
    labels = (
        [str(label) for label in [row_of(plan.registered).get("label")] if label]
        if plan.registered
        else LISTS["label"]
    )
    if labels and optional(draw, plan, "label"):
        found["label"] = draw(st.sampled_from(labels))
    return found


@st.composite
def fields(draw: st.DrawFn, size: Size = SIZE) -> JsonValue:
    """A value field the text allows: of one form, or, one time in six, the alternatives of one."""
    if draw(st.integers(0, 5)):
        return draw(form_fields(ANY, size))
    alternatives: list[JsonValue] = list(
        draw(st.lists(form_fields(ANY, size), min_size=1, max_size=size.members))
    )
    return {"alternatives": alternatives}


# A registered field in its place: `record_format.md` sections 4 and 4.4.

PLACES = ("fields", "replaces")
PURPOSES = listed(
    prose((SPECIFICATION / "record_format.md").read_text(encoding="utf-8")), "1. `purpose` is ", "."
)


@st.composite
def registered_values(draw: st.DrawFn, plan: Plan, size: Size = SIZE) -> JsonValue:
    """A value field of `plan.registered`: of one form, or the alternatives of one or more, each bound to its
    row."""
    if not (plan.alternatives if plan.alternatives is not None else not draw(st.integers(0, 5))):
        return draw(form_fields(plan, size))
    alternatives: list[JsonValue] = list(
        draw(st.lists(form_fields(plan, size), min_size=1, max_size=size.members))
    )
    return {"alternatives": alternatives}


@st.composite
def bodies(draw: st.DrawFn, plan: Plan = ANY, size: Size = SIZE) -> Json:
    """A material body holding a registered field in its section's `fields`, or an overlay body replacing
    one."""
    name = plan.registered or draw(st.sampled_from(list(FIELDS)))
    value = draw(registered_values(replace(plan, registered=name), size))
    if (plan.place or draw(st.sampled_from(PLACES))) == "fields":
        section, _, field = name.partition(".")
        return {"sections": {section: {"fields": {field: value}}}}
    base: Json = {"id": draw(RECORD_IDS), "version": draw(VERSIONS), "content_hash": draw(HASHES)}
    scope: Json = {"consumer": draw(TEXT)}
    return {
        "purpose": draw(st.sampled_from(PURPOSES)),
        "base": base,
        "scope": scope,
        "replaces": {name: value},
    }


def placed(body: Json) -> tuple[Json, str, str]:
    """The map holding a body's one field, its name there, and its registered name, `<section>.<field>`."""
    if "sections" in body:
        ((section, held),) = mapping(body["sections"]).items()
        fields = mapping(mapping(held)["fields"])
        (name,) = fields
        return fields, name, f"{section}.{name}"
    replaces = mapping(body["replaces"])
    (name,) = replaces
    return replaces, name, name


# Faults: each one change the text says breaks a field's shape, on a field planned so that its place exists.


class Faulty(NamedTuple):
    fault: str
    place: str
    base: Json
    field: JsonValue


# A fault's change: given the draw and a copy of the base, it changes the copy in place and says where.
Change = Callable[[st.DrawFn, Json], str]


@dataclass(frozen=True)
class Fault:
    name: str
    family: str
    plan: Plan
    change: Change


FAULTS: list[Fault] = []


def fault(name: str, family: str, plan: Plan) -> Callable[[Change], Change]:
    def register(change: Change) -> Change:
        FAULTS.append(Fault(name, family, plan, change))
        return change

    return register


def block(found: Json) -> Json:
    return mapping(found["statistics"])


def relative(found: Json) -> Json:
    return mapping(block(found)["relative_uncertainty"])


def provenance(found: Json) -> Json:
    return mapping(found["provenance"])


def condition(found: Json, name: str) -> Json:
    return mapping(mapping(found["conditions"])[name])


def numeric(found: Json) -> Json:
    return condition(found, NUMERIC_CONDITIONS[0])


def specimen_fact(found: Json, name: str) -> Json:
    return mapping(mapping(found["specimen"])[name])


def removed(draw: st.DrawFn, found: Json, members: tuple[str, ...] | list[str], where: str) -> str:
    member = draw(st.sampled_from(sorted(set(members) & set(found))))
    del found[member]
    return f"{where}.{member}"


BLOCK = replace(MINIMAL, rich=frozenset({"block"}), represents="estimate")
UNCERTAIN = replace(BLOCK, rich=frozenset({"block", "uncertainty"}), uncertainty=("normal", "estimate"))
STUDENT = replace(UNCERTAIN, uncertainty=("student_t", "estimate"))
CONDITIONS_PLAN = replace(MINIMAL, rich=frozenset({"conditions"}))
SPECIMEN_PLAN = replace(MINIMAL, rich=frozenset({"specimen"}))
PROVENANCE_PLAN = replace(MINIMAL, origin="measured_by_source", rich=frozenset({"provenance"}))


# The statistics block: `uncertainty.md` section 1 and step 8's checks of values.

fault("negative_sd", "statistics", BLOCK)(
    lambda draw, found: block(found).update(sd=draw(NEGATIVE)) or "statistics.sd"
)
for _represents, _member in CONDITIONAL.items():

    @fault(f"{_member}_missing", "statistics", replace(BLOCK, represents=_represents))
    def _missing(draw: st.DrawFn, found: Json, member: str = _member) -> str:
        del block(found)[member]
        return f"statistics.{member}"


@fault("conditional_member_elsewhere", "statistics", BLOCK)
def _elsewhere(draw: st.DrawFn, found: Json) -> str:
    extra: dict[str, JsonValue] = {
        "population_level": {"status": "unstated"},
        "n_sources": 3.0,
        "precision_conditions": {"status": "unstated"},
    }
    member = draw(st.sampled_from(sorted(extra)))
    block(found)[member] = extra[member]
    return f"statistics.{member}"


fault("block_member_missing", "statistics", BLOCK)(
    lambda draw, found: removed(draw, block(found), BLOCK_MEMBERS, "statistics")
)
fault("block_member_unknown", "statistics", BLOCK)(
    lambda draw, found: block(found).update(mode=draw(NUMBERS)) or "statistics.mode"
)


@fault("count_negative", "statistics", BLOCK)
def _count_negative(draw: st.DrawFn, found: Json) -> str:
    count = draw(st.sampled_from(["n_specimens", "n_donors"]))
    block(found)[count] = -float(draw(st.integers(1, 10**6)))
    return f"statistics.{count}"


@fault("count_not_whole", "statistics", BLOCK)
def _count_not_whole(draw: st.DrawFn, found: Json) -> str:
    count = draw(st.sampled_from(["n_specimens", "n_donors"]))
    block(found)[count] = draw(st.integers(0, 10**6)) + 0.5
    return f"statistics.{count}"


@fault(
    "component_block_negative_sd",
    "statistics",
    replace(BLOCK, form="composition", rich=frozenset({"block", "composition"})),
)
def _component_sd(draw: st.DrawFn, found: Json) -> str:
    component = mapping(listing(mapping(found["composition"])["components"])[0])
    mapping(component["statistics"])["sd"] = draw(NEGATIVE)
    return "composition.components[0].statistics.sd"


# The relative or expanded uncertainty: `uncertainty.md` section 1's list and step 8.


@fault("coverage_probability_above_one", "uncertainty", UNCERTAIN)
def _probability_above_one(draw: st.DrawFn, found: Json) -> str:
    above_one = st.floats(min_value=1.0, exclude_min=True, allow_nan=False, allow_infinity=False)
    relative(found).update(coverage_factor=2.0, coverage_probability=draw(above_one))
    return "relative_uncertainty.coverage_probability"


@fault("coverage_probability_not_positive", "uncertainty", UNCERTAIN)
def _probability_not_positive(draw: st.DrawFn, found: Json) -> str:
    relative(found).update(coverage_factor=2.0, coverage_probability=draw(NOT_POSITIVE))
    return "relative_uncertainty.coverage_probability"


@fault("coverage_factor_not_positive", "uncertainty", UNCERTAIN)
def _factor_not_positive(draw: st.DrawFn, found: Json) -> str:
    relative(found).update(coverage_factor=draw(NOT_POSITIVE), coverage_probability=0.95)
    return "relative_uncertainty.coverage_factor"


@fault("no_coverage_number", "uncertainty", UNCERTAIN)
def _no_coverage(draw: st.DrawFn, found: Json) -> str:
    relative(found).update(
        coverage_factor=draw(status(ANY_STATUS)), coverage_probability=draw(status(ANY_STATUS))
    )
    return "relative_uncertainty.coverage_factor"


fault("uncertainty_value_negative", "uncertainty", UNCERTAIN)(
    lambda draw, found: relative(found).update(value=draw(NEGATIVE)) or "relative_uncertainty.value"
)
fault("dof_not_positive", "uncertainty", STUDENT)(
    lambda draw, found: relative(found).update(dof=draw(NOT_POSITIVE)) or "relative_uncertainty.dof"
)
fault("dof_beside_another_distribution", "uncertainty", UNCERTAIN)(
    lambda draw, found: relative(found).update(dof=draw(POSITIVE)) or "relative_uncertainty.dof"
)
fault("dof_missing_for_student_t", "uncertainty", STUDENT)(
    lambda draw, found: relative(found).update(dof=draw(status(ANY_STATUS))) or "relative_uncertainty.dof"
)


@fault(
    "uncertainty_precision_missing", "uncertainty", replace(UNCERTAIN, uncertainty=("normal", "measurement"))
)
def _precision_missing(draw: st.DrawFn, found: Json) -> str:
    del relative(found)["precision_conditions"]
    return "relative_uncertainty.precision_conditions"


fault("uncertainty_precision_elsewhere", "uncertainty", UNCERTAIN)(
    lambda draw, found: (
        relative(found).update(precision_conditions="repeatability")
        or "relative_uncertainty.precision_conditions"
    )
)
fault("uncertainty_member_missing", "uncertainty", UNCERTAIN)(
    lambda draw, found: removed(draw, relative(found), UNCERTAINTY_MEMBERS, "relative_uncertainty")
)
fault("uncertainty_member_unknown", "uncertainty", UNCERTAIN)(
    lambda draw, found: relative(found).update(k=2.0) or "relative_uncertainty.k"
)


# Tokens: a token of another member's list, or of none, where a list is closed (`record_format.md` section 10
# item 3; `uncertainty.md` section 4: `student_t` in a block's `distribution`).

# The lists held by members of each name, the first place a token known for a member of that name comes from.
SAME_NAME = {
    "distribution": ("statistics_distribution", "uncertainty_distribution", "distribution"),
    "basis": (
        "statistics_basis",
        "uncertainty_basis",
        "interval_basis",
        "composition_basis",
        "basis",
        "mimics_basis",
    ),
    "represents": ("represents", "uncertainty_represents"),
    "token": tuple(name for name in LISTS if name.endswith("_token")),
    "unit": ("post_mortem_interval_unit", "donor_age_unit"),
    "label": ("label", "result_label"),
}
CHOOSERS = st.randoms(use_true_random=True)
EVERY_TOKEN = sorted({token for tokens in LISTS.values() for token in tokens})
INVENTED = ("porous", "Mean", "mean ", "element:Zz", "H", "not_a_token")


@st.composite
def foreign(draw: st.DrawFn, own: list[str], member: str, extra: tuple[str, ...] = ()) -> str:
    """A token outside `own`: two times in three from another list held by a member of the same name, where
    one has a token `own` lacks; otherwise from any list, `extra`, or none."""
    others = [
        [token for token in LISTS[name] if token not in own]
        for name in SAME_NAME.get(member, ())
        if set(LISTS[name]) - set(own)
    ]
    # A seeded Random, as `strategies.WRITINGS`: Hypothesis repeats an earlier choice far more often than its
    # share, which would leave a list's one token unreached; the seed is drawn, so a failure replays.
    chooser = draw(CHOOSERS)
    if others and chooser.random() < 2 / 3:
        return chooser.choice(chooser.choice(others))
    return chooser.choice([token for token in (*EVERY_TOKEN, *extra, *INVENTED) if token not in own])


Locate = Callable[[Json], tuple[Json, str]]


def at(container: Callable[[Json], Json], member: str) -> Locate:
    """The place of `member` in the object `container` finds in a field."""
    return lambda found: (container(found), member)


def itself(found: Json) -> Json:
    return found


def interval_of(found: Json) -> Json:
    return mapping(found["interval"])


def token_fault(place: str, plan: Plan, locate: Locate, own: str, extra: tuple[str, ...] = ()) -> None:
    def change(draw: st.DrawFn, found: Json) -> str:
        container, member = locate(found)
        container[member] = draw(foreign(LISTS[own], member, extra))
        return place

    statistics = place.startswith(("statistics.", "population_level.", "relative_uncertainty."))
    FAULTS.append(
        Fault(f"foreign_token_{place}", "statistics_tokens" if statistics else "tokens", plan, change)
    )


COMPOSITION = replace(MINIMAL, form="composition")
INTERVAL = replace(MINIMAL, form="interval")
token_fault("form", MINIMAL, lambda found: (found, "form"), "form")
for _member, _own in (
    ("central", "central"),
    ("distribution", "statistics_distribution"),
    ("dispersion", "dispersion"),
):
    token_fault(f"statistics.{_member}", BLOCK, at(block, _member), _own)
token_fault("statistics.basis", BLOCK, lambda found: (block(found), "basis"), "statistics_basis")
token_fault("statistics.represents", BLOCK, lambda found: (block(found), "represents"), "represents")
POPULATION = replace(BLOCK, represents="population")
token_fault(
    "population_level.level",
    POPULATION,
    lambda found: (mapping(block(found)["population_level"]), "level"),
    "level",
)
token_fault(
    "population_level.within",
    POPULATION,
    lambda found: (mapping(block(found)["population_level"]), "within"),
    "level",
)
token_fault(
    "statistics.precision_conditions",
    replace(BLOCK, represents="measurement"),
    lambda found: (block(found), "precision_conditions"),
    "precision_conditions",
)
for _member, _own in (
    ("distribution", "uncertainty_distribution"),
    ("basis", "uncertainty_basis"),
    ("represents", "uncertainty_represents"),
):
    token_fault(
        f"relative_uncertainty.{_member}",
        UNCERTAIN,
        at(relative, _member),
        _own,
    )
token_fault(
    "relative_uncertainty.precision_conditions",
    replace(UNCERTAIN, uncertainty=("normal", "measurement")),
    lambda found: (relative(found), "precision_conditions"),
    "precision_conditions",
)
token_fault("interval.basis", INTERVAL, lambda found: (mapping(found["interval"]), "basis"), "interval_basis")
token_fault(
    "composition.basis",
    COMPOSITION,
    lambda found: (mapping(found["composition"]), "basis"),
    "composition_basis",
)
token_fault(
    "composition.sum_rule", COMPOSITION, lambda found: (mapping(found["composition"]), "sum_rule"), "sum_rule"
)
token_fault(
    "composition.component",
    COMPOSITION,
    lambda found: (mapping(listing(mapping(found["composition"])["components"])[0]), "component"),
    "component",
)
for _name in TOKEN_CONDITIONS:
    token_fault(
        f"conditions.{_name}.token",
        CONDITIONS_PLAN,
        at(functools.partial(condition, name=_name), "token"),
        f"{_name}_token",
    )
for _name in TOKEN_FACTS:
    token_fault(
        f"specimen.{_name}.token",
        SPECIMEN_PLAN,
        at(functools.partial(specimen_fact, name=_name), "token"),
        f"{_name}_token",
    )
for _name, _entry in FACTS.items():
    for _member in sorted(set(mapping(_entry)) - {"tokens"}):
        token_fault(
            f"specimen.{_name}.{_member}",
            SPECIMEN_PLAN,
            at(functools.partial(specimen_fact, name=_name), _member),
            f"{_name}_{_member}",
            tuple(UNITS),
        )
token_fault("conditions.basis", CONDITIONS_PLAN, lambda found: (numeric(found), "basis"), "basis")
token_fault(
    "plus_minus.stated_as",
    CONDITIONS_PLAN,
    lambda found: (mapping(listing(numeric(found)["plus_minus"])[0]), "stated_as"),
    "stated_as",
)
token_fault(
    "conditions.set_or_measured",
    CONDITIONS_PLAN,
    lambda found: (numeric(found), "set_or_measured"),
    "set_or_measured",
)
token_fault("provenance.origin", MINIMAL, lambda found: (provenance(found), "origin"), "origin")
token_fault(
    "extraction.method",
    MINIMAL,
    lambda found: (mapping(provenance(found)["extraction"]), "method"),
    "extraction_method",
)
token_fault(
    "source.locator.type",
    PROVENANCE_PLAN,
    lambda found: (mapping(mapping(provenance(found)["source"])["locator"]), "type"),
    "locator_type",
)
token_fault(
    "review.result",
    PROVENANCE_PLAN,
    lambda found: (mapping(provenance(found)["review"]), "result"),
    "review_result",
)
token_fault(
    "search.inputs",
    replace(BLOCK, represents="across_sources"),
    lambda found: (mapping(provenance(found)["search"]), "inputs"),
    "search_inputs",
)
token_fault("label", replace(MINIMAL, rich=frozenset({"label"})), lambda found: (found, "label"), "label")


# Status objects: a token its row in `provenance.md` section 1 item 5's table does not allow, a status object
# where none may stand, and one holding a member beside `status` and `reason`.


def status_fault(place: str, plan: Plan, locate: Locate, allowed: tuple[str, ...]) -> None:
    def change(draw: st.DrawFn, found: Json) -> str:
        container, member = locate(found)
        others = [token for token in ANY_STATUS if token not in allowed]
        container[member] = {"status": draw(st.sampled_from([*others, "pending"]))}
        return place

    FAULTS.append(Fault(f"status_not_allowed_{place}", "status", plan, change))


status_fault("value", MINIMAL, lambda found: (found, "value"), ("withheld",))
status_fault("interval", INTERVAL, lambda found: (found, "interval"), ("withheld",))
for _form in ("table", "power_law", "parameter_set", "reference_data"):
    status_fault(_form, replace(MINIMAL, form=_form), at(itself, _form), ("withheld",))
status_fault("statistics", MINIMAL, lambda found: (found, "statistics"), ("withheld",))
status_fault(
    "reference_data.statistics",
    replace(MINIMAL, form="reference_data"),
    lambda found: (found, "statistics"),
    ("withheld", "not_applicable"),
)
for _member, _allowed in (
    ("central", ("not_applicable",)),
    ("basis", ("not_applicable",)),
    ("represents", ("unstated", "not_applicable")),
    ("distribution", ("unstated",)),
    ("dispersion", ()),
):
    status_fault(f"statistics.{_member}", BLOCK, at(block, _member), _allowed)
status_fault("population_level", POPULATION, lambda found: (block(found), "population_level"), ("unstated",))
status_fault(
    "population_level.within",
    POPULATION,
    lambda found: (mapping(block(found)["population_level"]), "within"),
    ("none",),
)
for _member in ("distribution", "represents"):
    status_fault(
        f"relative_uncertainty.{_member}",
        UNCERTAIN,
        at(relative, _member),
        ("unstated",),
    )
for _member in ("lower", "upper"):
    status_fault(
        f"interval.{_member}",
        replace(INTERVAL, rich=frozenset({"block"})),
        at(interval_of, _member),
        ("none",),
    )
status_fault(
    "plus_minus.stated_as",
    CONDITIONS_PLAN,
    lambda found: (mapping(listing(numeric(found)["plus_minus"])[0]), "stated_as"),
    ("unstated",),
)
status_fault(
    "conditions.token", CONDITIONS_PLAN, lambda found: (condition(found, TOKEN_CONDITIONS[0]), "token"), ()
)
status_fault(
    "evidence.endpoint",
    replace(MINIMAL, form="evidence", rich=frozenset({"evidence"})),
    lambda found: (mapping(listing(found["evidence"])[0]), "endpoint"),
    NOT_WITHHELD,
)
status_fault("provenance.review", MINIMAL, lambda found: (provenance(found), "review"), ("not_checked",))
status_fault("provenance.assistance", MINIMAL, lambda found: (provenance(found), "assistance"), ("none",))
status_fault("provenance.origin", MINIMAL, lambda found: (provenance(found), "origin"), ())


@fault("status_beside_a_member", "status", CONDITIONS_PLAN)
def _status_beside(draw: st.DrawFn, found: Json) -> str:
    mapping(found["conditions"])[NUMERIC_CONDITIONS[0]] = {"status": "unstated", "value": draw(NUMBERS)}
    return f"conditions.{NUMERIC_CONDITIONS[0]}"


@fault("status_reason_not_text", "status", CONDITIONS_PLAN)
def _reason(draw: st.DrawFn, found: Json) -> str:
    mapping(found["conditions"])[NUMERIC_CONDITIONS[0]] = {"status": "unstated", "reason": draw(NUMBERS)}
    return f"conditions.{NUMERIC_CONDITIONS[0]}"


# Conditions: `provenance.md` section 6.1 items 1 and 6, and section 6's basis.


@fault("condition_value_and_range", "conditions", CONDITIONS_PLAN)
def _value_and_range(draw: st.DrawFn, found: Json) -> str:
    numeric(found).update(value=draw(NUMBERS), range=draw(ranges()))
    return f"conditions.{NUMERIC_CONDITIONS[0]}"


@fault("condition_neither_value_nor_range", "conditions", CONDITIONS_PLAN)
def _neither(draw: st.DrawFn, found: Json) -> str:
    for member in ("value", "range"):
        numeric(found).pop(member, None)
    return f"conditions.{NUMERIC_CONDITIONS[0]}"


@fault("condition_range_not_two", "conditions", CONDITIONS_PLAN)
def _range_length(draw: st.DrawFn, found: Json) -> str:
    numeric(found).pop("value", None)
    lengths: list[JsonValue] = [[], [0.0], [0.0, 1.0, 2.0]]
    numeric(found)["range"] = draw(st.sampled_from(lengths))
    return f"conditions.{NUMERIC_CONDITIONS[0]}.range"


@fault("plus_minus_two_of_a_kind", "conditions", CONDITIONS_PLAN)
def _two_of_a_kind(draw: st.DrawFn, found: Json) -> str:
    kind = draw(st.sampled_from(LISTS["stated_as"]))
    unit = registered_unit(NUMERIC_CONDITIONS[0])
    numeric(found)["plus_minus"] = [{"stated_as": kind, "value": 1.0, "unit": unit} for _ in range(2)]
    return "plus_minus"


@fault("plus_minus_unstated_beside_stated", "conditions", CONDITIONS_PLAN)
def _unstated_beside(draw: st.DrawFn, found: Json) -> str:
    stated = draw(st.sampled_from(LISTS["stated_as"]))
    unit = registered_unit(NUMERIC_CONDITIONS[0])
    numeric(found)["plus_minus"] = [
        {"stated_as": stated, "value": 1.0, "unit": unit},
        {"stated_as": {"status": "unstated"}, "value": 1.0, "unit": unit},
    ]
    return "plus_minus"


fault("plus_minus_empty", "conditions", CONDITIONS_PLAN)(
    lambda draw, found: numeric(found).update(plus_minus=[]) or "plus_minus"
)


@fault("plus_minus_value_negative", "conditions", CONDITIONS_PLAN)
def _plus_minus_negative(draw: st.DrawFn, found: Json) -> str:
    mapping(listing(numeric(found)["plus_minus"])[0])["value"] = draw(NEGATIVE)
    return "plus_minus[0].value"


@fault("condition_unregistered", "conditions", CONDITIONS_PLAN)
def _unregistered(draw: st.DrawFn, found: Json) -> str:
    name = draw(st.sampled_from(["humidity", "frequency", "temperatures", "Temperature"]))
    mapping(found["conditions"])[name] = {"value": 1.0, "unit": "1", "basis": "stated"}
    return f"conditions.{name}"


fault("condition_member_unknown", "conditions", CONDITIONS_PLAN)(
    lambda draw, found: numeric(found).update(note=draw(TEXT)) or f"conditions.{NUMERIC_CONDITIONS[0]}.note"
)
fault("token_condition_unit", "conditions", CONDITIONS_PLAN)(
    lambda draw, found: (
        condition(found, TOKEN_CONDITIONS[0]).update(unit="1") or f"conditions.{TOKEN_CONDITIONS[0]}.unit"
    )
)


@fault("condition_member_missing", "conditions", CONDITIONS_PLAN)
def _condition_member_missing(draw: st.DrawFn, found: Json) -> str:
    if draw(st.booleans()):
        return removed(draw, numeric(found), ["unit", "basis"], f"conditions.{NUMERIC_CONDITIONS[0]}")
    return removed(
        draw, condition(found, TOKEN_CONDITIONS[0]), ["token", "basis"], f"conditions.{TOKEN_CONDITIONS[0]}"
    )


@fault("condition_inferred_without_inferred_from", "conditions", CONDITIONS_PLAN)
def _condition_inferred(draw: st.DrawFn, found: Json) -> str:
    numeric(found)["basis"] = "inferred"
    numeric(found).pop("inferred_from", None)
    return f"conditions.{NUMERIC_CONDITIONS[0]}.inferred_from"


# Specimen facts: `provenance.md` section 6.2 and its item 1.


@fault("fact_unregistered", "specimen", SPECIMEN_PLAN)
def _fact_unregistered(draw: st.DrawFn, found: Json) -> str:
    name = draw(st.sampled_from(["colour", "lots", "Species", "porosity"]))
    mapping(found["specimen"])[name] = {"text": "x", "basis": "stated"}
    return f"specimen.{name}"


@fault("fact_member_missing", "specimen", SPECIMEN_PLAN)
def _fact_member_missing(draw: st.DrawFn, found: Json) -> str:
    name = draw(st.sampled_from(sorted(FACTS)))
    present = specimen_fact(found, name)
    required = next(
        names
        for names in (
            [member.name for member in shape if not (member.required_for or member.exactly_for)]
            for shape in FACT_SHAPES[name]
        )
        if set(names) <= set(present)
    )
    return removed(draw, present, required, f"specimen.{name}")


@fault("fact_member_unknown", "specimen", SPECIMEN_PLAN)
def _fact_member_unknown(draw: st.DrawFn, found: Json) -> str:
    name = draw(st.sampled_from(sorted(FACTS)))
    specimen_fact(found, name)["note"] = draw(TEXT)
    return f"specimen.{name}.note"


@fault("preservation_other_without_text", "specimen", SPECIMEN_PLAN)
def _preservation(draw: st.DrawFn, found: Json) -> str:
    mapping(found["specimen"])["preservation"] = {"token": "other", "basis": "stated"}
    return "specimen.preservation.text"


# Section 6.2's rows: a member present exactly with some of its fact's tokens (a disease or treatment
# state's `text`, with `diseased` and `treated`).
EXACTLY = {
    (name, member.name): member.exactly_for
    for name, shapes in FACT_SHAPES.items()
    for shape in shapes
    for member in shape
    if member.exactly_for
}


@fault("fact_member_beside_another_token", "specimen", SPECIMEN_PLAN)
def _beside_another_token(draw: st.DrawFn, found: Json) -> str:
    (name, member), tokens = draw(st.sampled_from(sorted(EXACTLY.items())))
    present = specimen_fact(found, name)
    present["token"] = draw(
        st.sampled_from([token for token in LISTS[f"{name}_token"] if token not in tokens])
    )
    present[member] = draw(TEXT)
    return f"specimen.{name}.{member}"


@fault("fact_member_missing_for_its_token", "specimen", SPECIMEN_PLAN)
def _missing_for_its_token(draw: st.DrawFn, found: Json) -> str:
    (name, member), tokens = draw(st.sampled_from(sorted(EXACTLY.items())))
    present = specimen_fact(found, name)
    present["token"] = draw(st.sampled_from(tokens))
    present.pop(member, None)
    return f"specimen.{name}.{member}"


@fault("fact_inferred_without_inferred_from", "specimen", SPECIMEN_PLAN)
def _fact_inferred(draw: st.DrawFn, found: Json) -> str:
    present = specimen_fact(found, "species")
    present["basis"] = "inferred"
    present.pop("inferred_from", None)
    return "specimen.species.inferred_from"


fault("species_taxon_not_whole", "specimen", SPECIMEN_PLAN)(
    lambda draw, found: (
        specimen_fact(found, "species").update(ncbi_taxon=9606.5) or "specimen.species.ncbi_taxon"
    )
)


@fault("uberon_malformed", "specimen", SPECIMEN_PLAN)
def _uberon(draw: st.DrawFn, found: Json) -> str:
    malformed = draw(
        st.sampled_from(["UBERON_0002107", "uberon:0002107", "UBERON:12a", "UBERON:", "UBERON:1\n"])
    )
    specimen_fact(found, "anatomical_site")["uberon"] = malformed
    return "specimen.anatomical_site.uberon"


@fault("fact_value_and_range", "specimen", SPECIMEN_PLAN)
def _fact_value_and_range(draw: st.DrawFn, found: Json) -> str:
    mapping(found["specimen"])["donor_age"] = {
        "value": 1.0,
        "range": [0.0, 2.0],
        "unit": "s",
        "basis": "stated",
    }
    return "specimen.donor_age"


# The forms and the value field: `record_format.md` sections 4.3, 5 and 6, and `provenance.md` section 7.

EVIDENCE = replace(MINIMAL, form="evidence")
WITHHELD_EVIDENCE = replace(EVIDENCE, withheld=True)
fault("interval_both_none", "forms", INTERVAL)(
    lambda draw, found: (
        mapping(found["interval"]).update(lower={"status": "none"}, upper={"status": "none"}) or "interval"
    )
)
fault("interval_member_missing", "forms", INTERVAL)(
    lambda draw, found: removed(draw, mapping(found["interval"]), ["lower", "upper", "basis"], "interval")
)
fault("composition_without_component", "forms", COMPOSITION)(
    lambda draw, found: mapping(found["composition"]).update(components=[]) or "composition.components"
)


@fault("fraction_outside_zero_to_one", "forms", COMPOSITION)
def _fraction(draw: st.DrawFn, found: Json) -> str:
    fraction = draw(st.one_of(NEGATIVE, st.floats(min_value=1.0, exclude_min=True, allow_infinity=False)))
    mapping(listing(mapping(found["composition"])["components"])[0])["fraction"] = fraction
    return "composition.components[0].fraction"


fault("composition_member_missing", "forms", COMPOSITION)(
    lambda draw, found: removed(
        draw, mapping(found["composition"]), ["basis", "sum_rule", "components"], "composition"
    )
)
fault("evidence_empty", "forms", EVIDENCE)(lambda draw, found: found.update(evidence=[]) or "evidence")


@fault("evidence_entry_partly_withheld", "forms", WITHHELD_EVIDENCE)
def _partly(draw: st.DrawFn, found: Json) -> str:
    entry = next(
        mapping(item)
        for item in listing(found["evidence"])
        if mapping(item)["endpoint"] == {"status": "withheld"}
    )
    member = draw(st.sampled_from(WITHHELD_WHOLE))
    entry[member] = {"status": "unstated"}
    return f"evidence[].{member}"


@fault("evidence_entry_member_missing", "forms", EVIDENCE)
def _entry_member(draw: st.DrawFn, found: Json) -> str:
    return removed(draw, mapping(listing(found["evidence"])[0]), ENTRY_MEMBERS, "evidence[0]")


@fault("standard_year_not_whole", "forms", replace(EVIDENCE, rich=frozenset({"evidence"})))
def _year(draw: st.DrawFn, found: Json) -> str:
    mapping(mapping(listing(found["evidence"])[0])["standard"])["year"] = 2009.5
    return "evidence[0].standard.year"


@fault("evidence_beside_a_block", "forms", EVIDENCE)
def _evidence_block(draw: st.DrawFn, found: Json) -> str:
    found["statistics"] = draw(statistics_block(BLOCK))
    return "statistics"


@fault("evidence_under_a_condition", "forms", EVIDENCE)
def _evidence_condition(draw: st.DrawFn, found: Json) -> str:
    found["conditions"] = {NUMERIC_CONDITIONS[0]: {"status": "unstated"}}
    return "conditions"


@fault("alternatives_empty", "forms", MINIMAL)
def _alternatives_empty(draw: st.DrawFn, found: Json) -> str:
    found.clear()
    found["alternatives"] = []
    return "alternatives"


@fault("alternatives_beside_a_member", "forms", MINIMAL)
def _alternatives_beside(draw: st.DrawFn, found: Json) -> str:
    member = draw(st.sampled_from(sorted(found)))
    alternative = copy.deepcopy(found)
    kept = found[member]
    found.clear()
    found.update({"alternatives": [alternative], member: kept})
    return f"alternatives beside {member}"


@fault("field_member_missing", "forms", MINIMAL)
def _field_member(draw: st.DrawFn, found: Json) -> str:
    return removed(draw, found, ["form", "unit", "value", "conditions", "statistics", "provenance"], "field")


fault("field_member_unknown", "forms", MINIMAL)(
    lambda draw, found: found.update(note=draw(TEXT)) or "field.note"
)
NOT_NUMBERS: list[JsonValue] = ["1.0", True, [1.0]]
fault("constant_value_not_a_number", "forms", MINIMAL)(
    lambda draw, found: found.update(value=draw(st.sampled_from(NOT_NUMBERS))) or "value"
)


def without_recipe(draw: st.DrawFn, found: Json) -> str:
    del provenance(found)["recipe"]
    return "provenance.recipe"


for _form in FORMS:
    if _form != "evidence":
        fault(f"withheld_{_form}_without_recipe", "forms", replace(MINIMAL, form=_form, withheld=True))(
            without_recipe
        )


@fault("withheld_entry_without_recipe", "forms", WITHHELD_EVIDENCE)
def _entry_no_recipe(draw: st.DrawFn, found: Json) -> str:
    entry = next(
        mapping(item)
        for item in listing(found["evidence"])
        if mapping(item)["endpoint"] == {"status": "withheld"}
    )
    del mapping(entry["provenance"])["recipe"]
    return "evidence[].provenance.recipe"


# Provenance: `provenance.md` sections 2 to 5 and 7.


def provenance_removed(name: str, plan: Plan, member: str) -> None:
    def change(draw: st.DrawFn, found: Json) -> str:
        del (found if member == "fit" else provenance(found))[member]
        return member

    FAULTS.append(Fault(name, "provenance", plan, change))


provenance_removed("source_missing", replace(MINIMAL, origin="measured_by_source"), "source")
provenance_removed("derivation_missing", replace(MINIMAL, origin="derived"), "derivation")
provenance_removed(
    "formulation_missing", replace(MINIMAL, origin="evaluated_from_formulation"), "formulation"
)
provenance_removed("fit_missing", replace(MINIMAL, origin="fitted"), "fit")
provenance_removed(
    "derivation_missing_for_its_extraction", replace(MINIMAL, method="derivation"), "derivation"
)
provenance_removed(
    "formulation_missing_for_its_extraction", replace(MINIMAL, method="formulation"), "formulation"
)
provenance_removed("fit_missing_for_its_extraction", replace(MINIMAL, method="fit"), "fit")
provenance_removed("search_missing", replace(BLOCK, represents="across_sources"), "search")


@fault("extraction_member_missing", "provenance", replace(MINIMAL, method=None))
def _extraction_member(draw: st.DrawFn, found: Json) -> str:
    method = draw(st.sampled_from(sorted(EXTRACTION_MEMBER)))
    member = EXTRACTION_MEMBER[method]
    provenance(found)["extraction"] = {"method": method}
    return f"extraction.{member}"


@fault("review_member_missing", "provenance", PROVENANCE_PLAN)
def _review_member(draw: st.DrawFn, found: Json) -> str:
    present = mapping(provenance(found)["review"])
    return removed(draw, present, sorted(present), "review")


@fault("quote_beside_its_hash", "provenance", PROVENANCE_PLAN)
def _quote(draw: st.DrawFn, found: Json) -> str:
    mapping(provenance(found)["evidence"])["quote"] = draw(TEXT)
    return "evidence.quote"


@fault("quote_hash_malformed", "provenance", PROVENANCE_PLAN)
def _quote_hash(draw: st.DrawFn, found: Json) -> str:
    malformed = draw(
        st.sampled_from(["sha256:" + "0" * 63, "sha256:" + "A" * 64, "0" * 64, "sha256:" + "0" * 64 + "\n"])
    )
    mapping(provenance(found)["evidence"])["quote_sha256"] = malformed
    return "evidence.quote_sha256"


DERIVED = replace(MINIMAL, origin="derived", rich=frozenset({"provenance"}))


def derivation_of(found: Json) -> Json:
    return mapping(provenance(found)["derivation"])


fault("derivation_without_input", "provenance", DERIVED)(
    lambda draw, found: derivation_of(found).update(inputs=[]) or "derivation.inputs"
)
fault("derivation_member_missing", "provenance", DERIVED)(
    lambda draw, found: removed(
        draw, derivation_of(found), ["method", "inputs", "assumptions", "input_specimens"], "derivation"
    )
)


@fault("input_specimen_index_not_whole", "provenance", DERIVED)
def _input_index(draw: st.DrawFn, found: Json) -> str:
    indices: list[JsonValue] = [-1.0, 0.5, "0"]
    index = draw(st.sampled_from(indices))
    mapping(listing(derivation_of(found)["input_specimens"])[0])["input"] = index
    return "derivation.input_specimens[0].input"


@fault("input_record_malformed", "provenance", DERIVED)
def _input_record(draw: st.DrawFn, found: Json) -> str:
    record = mapping(mapping(listing(derivation_of(found)["inputs"])[0])["record"])
    member, value = draw(
        st.sampled_from([("id", "MAT-0001"), ("version", "1.0"), ("content_hash", "sha256:0")])
    )
    record[member] = value
    return f"derivation.inputs[0].record.{member}"


def locator_of(found: Json) -> Json:
    return mapping(mapping(provenance(found)["source"])["locator"])


fault("locator_page_not_whole", "provenance", PROVENANCE_PLAN)(
    lambda draw, found: locator_of(found).update(page=5.5) or "source.locator.page"
)


@fault("column_index_below_one", "provenance", PROVENANCE_PLAN)
def _column(draw: st.DrawFn, found: Json) -> str:
    mapping(locator_of(found)["column"])["index"] = draw(st.sampled_from([0.0, -1.0]))
    return "source.locator.column.index"


fault("provenance_member_missing", "provenance", MINIMAL)(
    lambda draw, found: removed(draw, provenance(found), PROVENANCE_REQUIRED, "provenance")
)
fault("provenance_member_unknown", "provenance", MINIMAL)(
    lambda draw, found: provenance(found).update(note=draw(TEXT)) or "provenance.note"
)
fault("source_member_missing", "provenance", PROVENANCE_PLAN)(
    lambda draw, found: removed(
        draw, mapping(provenance(found)["source"]), ["key", "document", "locator"], "source"
    )
)
fault("copy_member_missing", "provenance", PROVENANCE_PLAN)(
    lambda draw, found: removed(
        draw, mapping(mapping(provenance(found)["evidence"])["copy"]), ["sha256", "retrieved"], "copy"
    )
)
fault("mixed_conditions_not_boolean", "provenance", DERIVED)(
    lambda draw, found: derivation_of(found).update(mixed_conditions="yes") or "derivation.mixed_conditions"
)


# A unit other than the one registered: another registered unit, one a slip away, or a status object, as a
# writer converting from the source's unit, or not at all, might write it (`record_format.md` section 4.2).
REGISTERED_UNITS = sorted(
    {str(row["unit"]) for row in map(mapping, FIELDS.values()) if isinstance(row["unit"], str)}
    | {registered_unit(name) for name in NUMERIC_CONDITIONS}
    | {"s"}
)


@st.composite
def foreign_unit(draw: st.DrawFn, own: JsonValue) -> JsonValue:
    chooser = draw(CHOOSERS)
    if isinstance(own, str):
        slips: list[JsonValue] = [own + " ", own.upper(), own.replace("/", "."), "Cel", "kg/m^3"]
        statuses: list[JsonValue] = [{"status": token} for token in ANY_STATUS]
    else:
        slips = [str(mapping(own)["status"])]
        statuses = [{"status": token} for token in ANY_STATUS if token != mapping(own)["status"]]
    others: list[JsonValue] = [unit for unit in REGISTERED_UNITS if unit != own]
    return chooser.choice(
        [unit for unit in chooser.choice([others, slips, statuses]) if unit != own] or others
    )


# Conditions: a numeric condition's unit, and its `plus_minus` entries', are its registered unit
# (`provenance.md` section 6.1 items 1 and 6, `record_format.md` section 4.2).


@fault("condition_unit_not_registered", "conditions", CONDITIONS_PLAN)
def _condition_unit(draw: st.DrawFn, found: Json) -> str:
    numeric(found)["unit"] = draw(foreign_unit(registered_unit(NUMERIC_CONDITIONS[0])))
    return f"conditions.{NUMERIC_CONDITIONS[0]}.unit"


@fault("plus_minus_unit_not_registered", "conditions", CONDITIONS_PLAN)
def _plus_minus_unit(draw: st.DrawFn, found: Json) -> str:
    entry = mapping(listing(numeric(found)["plus_minus"])[0])
    entry["unit"] = draw(foreign_unit(registered_unit(NUMERIC_CONDITIONS[0])))
    return f"conditions.{NUMERIC_CONDITIONS[0]}.plus_minus[0].unit"


# The binding of a field to its row (`record_format.md` section 4.1, maintainer 2026-10-15): in a body, a
# field under a name its section does not register, or holding a form, a unit, a label or a composition's
# basis its row does not give, in the field or in one of its alternatives.

ONE = Plan(alternatives=False)
SEVERAL = Plan(alternatives=True)


def held(found: Json, alternative: bool) -> tuple[Json, str]:
    """The field a fault changes, the body's field or the first of its alternatives, and its registered
    name."""
    container, name, registered = placed(found)
    value = mapping(container[name])
    return (mapping(listing(value["alternatives"])[0]) if alternative else value), registered


@fault("field_unregistered", "binding", replace(ONE, place="fields"))
def _field_unregistered(draw: st.DrawFn, found: Json) -> str:
    container, name, registered = placed(found)
    section = registered.partition(".")[0]
    own = [other.partition(".")[2] for other in FIELDS if other.startswith(f"{section}.")]
    elsewhere = [other.partition(".")[2] for other in FIELDS if not other.startswith(f"{section}.")]
    slips = [name + "s", name.replace("_", ""), name[1] + name[0] + name[2:], "specimen", "porosity"]
    chooser = draw(CHOOSERS)
    unregistered = chooser.choice([other for other in chooser.choice([elsewhere, slips]) if other not in own])
    container[unregistered] = container.pop(name)
    return f"sections.{section}.fields.{unregistered}"


@fault("replaced_field_unregistered", "binding", replace(ONE, place="replaces"))
def _replaced_unregistered(draw: st.DrawFn, found: Json) -> str:
    container, name, _ = placed(found)
    section, _, field_name = name.partition(".")
    others = [other for other in FIELDS if other.partition(".")[0] != section]
    swapped = [f"{other.partition('.')[0]}.{field_name}" for other in others]
    slips = [f"{section}.{field_name}s", f"{section}s.{field_name}", "thermal.conductivity"]
    chooser = draw(CHOOSERS)
    unregistered = chooser.choice(
        [other for other in chooser.choice([swapped, slips]) if other not in FIELDS]
    )
    container[unregistered] = container.pop(name)
    return f"replaces.{unregistered}"


def binding_fault(
    name: str, plan: Plan, alternative: bool, change: Callable[[st.DrawFn, Json, str], str]
) -> None:
    def changed(draw: st.DrawFn, found: Json) -> str:
        value, registered = held(found, alternative)
        return ("alternatives[0]." if alternative else "") + change(draw, value, registered)

    FAULTS.append(Fault(f"alternative_{name}" if alternative else name, "binding", plan, changed))


def _form_unregistered(draw: st.DrawFn, value: Json, registered: str) -> str:
    """A field of a form its row does not register, otherwise as the text allows: its unit, no label."""
    own = [str(form) for form in listing(row_of(registered)["forms"])]
    other = draw(st.sampled_from([form for form in FORMS if form not in own]))
    fresh = draw(form_fields(Plan(form=other, withheld=False, minimal=True)))
    value.clear()
    value.update(fresh, unit=row_of(registered)["unit"])
    value.pop("label", None)
    return "form"


def _unit_unregistered(draw: st.DrawFn, value: Json, registered: str) -> str:
    value["unit"] = draw(foreign_unit(row_of(registered)["unit"]))
    return "unit"


def _label_unregistered(draw: st.DrawFn, value: Json, registered: str) -> str:
    value["label"] = draw(
        st.sampled_from([label for label in LISTS["label"] if label != row_of(registered).get("label")])
    )
    return "label"


for _alternative, _plan in ((False, ONE), (True, SEVERAL)):
    binding_fault("form_not_registered", _plan, _alternative, _form_unregistered)
    binding_fault("unit_not_registered", _plan, _alternative, _unit_unregistered)
    binding_fault("label_not_registered", _plan, _alternative, _label_unregistered)


@fault(
    "composition_basis_not_allowed",
    "binding",
    replace(ONE, registered="bulk.elemental_composition", form="composition", withheld=False),
)
def _basis(draw: st.DrawFn, found: Json) -> str:
    value, registered = held(found, False)
    allowed = listing(mapping(row_of(registered)["bases"])["composition"])
    mapping(value["composition"])["basis"] = draw(
        st.sampled_from([basis for basis in LISTS["composition_basis"] if basis not in allowed])
    )
    return "composition.basis"


FAMILIES = sorted({fault.family for fault in FAULTS})


@functools.cache
def _faults(family: str, only: tuple[str, ...]) -> st.SearchStrategy[Fault]:
    """The faults of `family`, or those of them named in `only`, each drawn with the same chance: Hypothesis
    draws `sampled_from`'s index uniformly, its pool of constants holding no integer below 100. A seed drawn
    for `CHOOSERS` would not do: Hypothesis draws it mostly among small integers and its constants, so that
    some seeds recur, each choosing the same fault (a fault's chance from 0.91 to 1.27 times its share among
    27, over 200,000 seeds, 2026-10-15)."""
    return st.sampled_from(
        [fault for fault in FAULTS if fault.family == family and (not only or fault.name in only)]
    )


@st.composite
def faulty_fields(draw: st.DrawFn, family: str, size: Size = SIZE, only: tuple[str, ...] = ()) -> Faulty:
    """A field the text allows, and the same field with one fault of `family`, drawn among them alike, or
    among those named in `only`."""
    chosen = draw(_faults(family, only))
    base = draw(bodies(chosen.plan, size) if family == "binding" else form_fields(chosen.plan, size))
    changed = copy.deepcopy(base)
    place = chosen.change(draw, changed)
    return Faulty(chosen.name, place, base, changed)
