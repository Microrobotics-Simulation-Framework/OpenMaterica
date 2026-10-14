# SPDX-License-Identifier: Apache-2.0
"""Strategies for records and versions: what the envelope check, step 2 and the read take.

A record is built valid for its type and then changed in one to three places, each chosen near a boundary
`record_format.md` section 1 item 2 draws: a member it checks removed or given another JSON type, a pattern's
near miss, the type that decides which body is checked, or a place it never checks. Other values are JSON
trees within `strategies.SIZE`.
"""

import copy
import functools
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.property import strategies
from tests.property.strategies import SIZE, Size

Place = tuple[str, ...]

KNOWN_SECTIONS = sorted(VOCABULARY.sections)
TYPES = ("material", "overlay", "interface", "acme:thing", "Material")
# A material or an overlay most often: the types whose bodies the reader checks.
DRAWN_TYPES = (*TYPES[:2], *TYPES[:2], *TYPES)
WELL_FORMED_HASH = "sha256:" + "0" * 64
NAMES = st.text(max_size=3)


def objects(size: Size) -> st.SearchStrategy[dict[str, JsonValue]]:
    return st.lists(st.tuples(NAMES, strategies.json_values(size=size)), max_size=size.members).map(
        dict[str, JsonValue]
    )


# Near misses: a string that matches its pattern, with at most one flaw that each pattern refuses, so that
# both sides of each boundary are drawn about as often.


@st.composite
def long_numbers(draw: st.DrawFn) -> str:
    """A number of 20 to 600 digits; the digits after the first come from a seeded Random, since a draw each
    would cost more than the rest of the example."""
    digits = draw(st.randoms(use_true_random=True)).choices("0123456789", k=draw(st.integers(19, 599)))
    return str(draw(st.integers(1, 9))) + "".join(digits)


NUMBERS = st.one_of(st.just("0"), st.integers(1, 10**6).map(str), long_numbers())
_NAMESPACES = st.text(alphabet="abcxyz09_", min_size=1, max_size=8)
_LOCAL_IDS = st.text(alphabet="aZz09_.-", min_size=1, max_size=8)
# Unicode digits that \d matches and [0-9] does not: Arabic-Indic three, fullwidth one.
_OTHER_DIGITS = ("\u0663", "\uff11")


@st.composite
def near_ids(draw: st.DrawFn) -> str:
    namespace, local = draw(_NAMESPACES), draw(_LOCAL_IDS)
    flaw = draw(st.sampled_from(["none", "none", "join", "insert", "end"]))
    if flaw == "join":
        return draw(
            st.sampled_from([namespace + local, f"{namespace}//{local}", f"/{local}", f"{namespace}/"])
        )
    if flaw == "insert":
        inserted = draw(st.sampled_from(["A", "-", ".", " ", "\xe9", *_OTHER_DIGITS]))
        namespace = namespace[:1] + inserted + namespace[1:]
    if flaw == "end":
        return draw(st.sampled_from(["{}\n", "{}\n", "{} ", "\n{}"])).format(f"{namespace}/{local}")
    return f"{namespace}/{local}"


@st.composite
def near_versions(draw: st.DrawFn) -> str:
    components = [draw(NUMBERS) for _ in range(3)]
    index = draw(st.integers(0, 2))
    flaws = ["none", "none", "leading_zero", "unicode_digit", "count", "empty", "sign", "affix", "separator"]
    flaw = draw(st.sampled_from(flaws))
    if flaw == "leading_zero":
        components[index] = "0" + components[index]
    elif flaw == "unicode_digit":
        components[index] = (
            components[index][:1] + draw(st.sampled_from(_OTHER_DIGITS)) + components[index][1:]
        )
    elif flaw == "count":
        components = components[:2] if draw(st.booleans()) else [*components, "0"]
    elif flaw == "empty":
        components[index] = ""
    elif flaw == "sign":
        components[index] = draw(st.sampled_from(["+", "-", " "])) + components[index]
    text = (
        draw(st.sampled_from([",", ".."])).join(components) if flaw == "separator" else ".".join(components)
    )
    if flaw == "affix":
        text = draw(st.sampled_from(["v{}", "{}\n", "{} ", "{}-rc1", "{}+b", "\n{}"])).format(text)
    return text


@st.composite
def near_hashes(draw: st.DrawFn) -> str:
    digits = draw(st.binary(min_size=32, max_size=32)).hex()
    flaw = draw(st.sampled_from(["none", "none", "uppercase", "prefix", "length", "letter", "end"]))
    index = draw(st.integers(0, 63))
    if flaw in ("uppercase", "letter"):
        replacement = draw(st.sampled_from("ABCDEF" if flaw == "uppercase" else ["g", " ", "\u0663"]))
        digits = digits[:index] + replacement + digits[index + 1 :]
    elif flaw == "length":
        digits = digits[1:] if draw(st.booleans()) else digits + "0"
    prefix = draw(st.sampled_from(["SHA256:", "sha256", "sha-256:", ""])) if flaw == "prefix" else "sha256:"
    return prefix + digits + (draw(st.sampled_from(["\n", " ", "\r\n"])) if flaw == "end" else "")


NEAR_MISSES = {
    "id": near_ids(),
    "version": near_versions(),
    "schema_version": near_versions(),
    "content_hash": near_hashes(),
}


# Valid records.


class Filler(NamedTuple):
    """What fills the places the checks never look into: JSON trees, or a few values of each JSON type."""

    values: st.SearchStrategy[JsonValue]
    objects: st.SearchStrategy[dict[str, JsonValue]]
    texts: st.SearchStrategy[str]


# Strategies are built once, here or by size: Hypothesis spends more building and checking a strategy than
# drawing from it.


@functools.cache
def trees(size: Size) -> Filler:
    return Filler(strategies.json_values(size=size), objects(size), strategies.TEXT)


# Copied as drawn, since a change may write into what they hold.
_SAMPLE_VALUES: list[JsonValue] = [None, True, 0.0, -0.0, "", "x", [], [None], {}, {"x": None}]
_SAMPLE_OBJECTS: list[dict[str, JsonValue]] = [{}, {"x": None}, {"a": [1.0], "b": {}}]
SAMPLES = Filler(
    st.sampled_from(_SAMPLE_VALUES).map(copy.deepcopy),
    st.sampled_from(_SAMPLE_OBJECTS).map(copy.deepcopy),
    st.sampled_from(["", "x", "\xe9", "a\nb"]),
)
_SECTION_NAMES = st.lists(
    st.sampled_from([*KNOWN_SECTIONS, "acoustic", "acme"]), min_size=1, max_size=4, unique=True
)
_SCOPE_OPTIONS: dict[str, JsonValue] = {
    "model": {"name": "model", "version": "0.3.0"},
    "model_configuration_hash": "x",
    "run": "1",
}


@st.composite
def bodies(draw: st.DrawFn, record_type: str, filler: Filler) -> dict[str, JsonValue]:
    if record_type == "material":
        sections: dict[str, JsonValue] = {}
        for name in draw(_SECTION_NAMES):
            if name in KNOWN_SECTIONS:
                section: dict[str, JsonValue] = {"fields": draw(filler.objects)}
                if draw(st.booleans()):
                    section["specimen"] = draw(filler.values)
                sections[name] = section
            else:
                sections[name] = draw(filler.values)
        body: dict[str, JsonValue] = {"sections": sections}
        if draw(st.booleans()):
            body["extensions"] = draw(filler.objects)
        return body
    if record_type == "overlay":
        scope: dict[str, JsonValue] = {"consumer": draw(filler.texts)}
        scope |= {name: copy.deepcopy(value) for name, value in _SCOPE_OPTIONS.items() if draw(st.booleans())}
        base: dict[str, JsonValue] = {
            "id": "conformance/water_fixture",
            "version": "1.0.0",
            "content_hash": WELL_FORMED_HASH,
        }
        return {"purpose": "fit", "base": base, "scope": scope, "replaces": draw(filler.objects)}
    return draw(filler.objects)


@st.composite
def records(draw: st.DrawFn, filler: Filler, record_type: str) -> dict[str, JsonValue]:
    record: dict[str, JsonValue] = {
        "schema_version": "0.1.0",
        "record_type": record_type,
        "id": "conformance/water_fixture",
        "version": "1.0.0",
        "name": draw(filler.texts),
        "licence": {"values": "CC0-1.0", "evidence": "excluded"},
        "content_hash": WELL_FORMED_HASH,
        "body": draw(bodies(record_type, filler)),
    }
    if draw(st.booleans()):
        record["card"] = draw(filler.texts)
    return record


# Changes near the envelope's boundaries.

ENVELOPE_MEMBERS = (
    "schema_version",
    "record_type",
    "id",
    "version",
    "name",
    "licence",
    "content_hash",
    "body",
)
_SCOPE = ("consumer", "model", "model_configuration_hash", "run")

# Each aspect of a record the reader schema checks: the record type it needs, if any, and its places.
ASPECTS: dict[str, tuple[str | None, tuple[Place, ...]]] = {
    "envelope": (None, tuple((name,) for name in ENVELOPE_MEMBERS)),
    "card": (None, (("card",),)),
    "licence": (None, (("licence", "values"), ("licence", "evidence"))),
    "material_body": ("material", (("body", "sections"), ("body", "extensions"))),
    "known_section": (
        "material",
        tuple(
            ("body", "sections", *place) for name in KNOWN_SECTIONS for place in ((name,), (name, "fields"))
        ),
    ),
    "overlay_body": ("overlay", tuple(("body", name) for name in ("purpose", "base", "scope", "replaces"))),
    "overlay_base": ("overlay", tuple(("body", "base", name) for name in ("id", "version", "content_hash"))),
    "overlay_scope": (
        "overlay",
        (
            *[("body", "scope", name) for name in _SCOPE],
            *[("body", "scope", "model", name) for name in ("name", "version")],
        ),
    ),
}
# The members whose strings near misses are written into: the three the reader schema's patterns check, and
# `schema_version`, which only step 2 does; and the overlay base's, which it checks as strings only.
PATTERNED: dict[str, tuple[str | None, tuple[Place, ...]]] = {
    "pattern": (None, (("id",), ("version",), ("schema_version",), ("content_hash",))),
    "base_pattern": ("overlay", tuple(("body", "base", name) for name in ("id", "version", "content_hash"))),
}
# The places it never checks, by the record type in which they lie unchecked.
_EVERYWHERE: tuple[Place, ...] = (("x_note",), ("licence", "x_note"), ("body", "x_note"))
UNCHECKED: dict[str, tuple[Place, ...]] = {
    "material": (
        *_EVERYWHERE,
        ("body", "sections", "acoustic"),
        ("body", "sections", "acme"),
        ("body", "extensions", "acme"),
        *[("body", "sections", name, "specimen") for name in KNOWN_SECTIONS],
        *[("body", "sections", name, "fields", "density") for name in KNOWN_SECTIONS],
    ),
    "overlay": (*_EVERYWHERE, ("body", "replaces", "fluid.dynamic_viscosity"), ("body", "scope", "x_note")),
}
OTHER_TYPES: st.SearchStrategy[JsonValue] = st.one_of(
    st.sampled_from([*TYPES, 1.0, None, ["material"]]), strategies.TEXT
)
CHANGES = ("removed", "retyped", "null", "near_miss", "record_type", "unchecked")
_PLACES = {name: st.sampled_from(places) for name, (_, places) in (ASPECTS | PATTERNED).items()}
_UNCHECKED_PLACES = {record_type: st.sampled_from(places) for record_type, places in UNCHECKED.items()}
_EVERYWHERE_PLACES = st.sampled_from(_EVERYWHERE)


class Envelope(NamedTuple):
    record: JsonValue
    changes: tuple[str, ...]  # what was changed, in order: a kind of CHANGES and the place
    planned: str = "mixed"  # the aspect, or the kind, of the one change planned; "mixed" for changes drawn


def at(record: JsonValue, place: Place) -> JsonValue:
    for step in place:
        record = record.get(step) if isinstance(record, dict) else None
    return record


@functools.cache
def other_type(kind: str, size: Size) -> st.SearchStrategy[JsonValue]:
    """A value not of the JSON type the Python type named `kind` stands for, and not null either, which a
    change of its own draws."""
    values: dict[str, st.SearchStrategy[JsonValue]] = {
        "bool": st.booleans(),
        "float": strategies.DOUBLES,
        "str": strategies.TEXT,
        "list": st.lists(trees(size).values, max_size=size.members),
        "dict": trees(size).objects,
    }
    return st.one_of([value for name, value in values.items() if name != kind])


def changed(record: JsonValue, place: Place, value: JsonValue | None, *, remove: bool = False) -> bool:
    """Sets or removes the member at `place`, where its parent is an object; whether it did."""
    parent = record
    for step in place[:-1]:
        parent = parent.get(step) if isinstance(parent, dict) else None
    if not isinstance(parent, dict) or (remove and place[-1] not in parent):
        return False
    if remove:
        del parent[place[-1]]
    else:
        parent[place[-1]] = value
    return True


Change = tuple[str, str]  # a kind of CHANGES, and the aspect it changes ("" for a kind with none)

_COUNTS = st.sampled_from([1, 1, 1, 1, 1, 2, 3])
_KINDS = st.sampled_from([*CHANGES, "near_miss"])
_CHECKED_ASPECTS = st.sampled_from(sorted(ASPECTS))
_PATTERNED_ASPECTS = st.sampled_from(["pattern", "pattern", "base_pattern"])
_DRAWN_TYPES = st.sampled_from(DRAWN_TYPES)


@st.composite
def random_changes(draw: st.DrawFn) -> Change:
    """A change drawn at random; near misses twice as often as the rest, since each pattern has many flaws."""
    kind = draw(_KINDS)
    if kind in CHANGES[:3]:
        return kind, draw(_CHECKED_ASPECTS)
    if kind == "near_miss":
        return kind, draw(_PATTERNED_ASPECTS)
    return kind, ""


@st.composite
def envelopes(draw: st.DrawFn, size: Size = SIZE, planned: Change | None = None) -> Envelope:
    """A record changed by `planned`, of the type it needs; without one, changed by one to three changes
    drawn at random, one most often, since a second may refuse the record whatever the first did."""
    plan = [planned] if planned is not None else [draw(random_changes()) for _ in range(draw(_COUNTS))]
    wanted = {(ASPECTS | PATTERNED)[aspect][0] for _, aspect in plan if aspect} - {None}
    record_type = str(wanted.pop()) if len(wanted) == 1 else draw(_DRAWN_TYPES)
    # A record with a change planned varies in its structure only; one changed at random, in content too.
    record: JsonValue = draw(records(trees(size) if planned is None else SAMPLES, record_type))
    changes: list[str] = []
    for kind, aspect in plan:
        if kind == "unchecked":
            place = draw(_UNCHECKED_PLACES.get(record_type, _EVERYWHERE_PLACES))
            done = changed(record, place, draw(trees(size).values))
        elif kind == "record_type":
            place = ("record_type",)
            done = changed(record, place, draw(OTHER_TYPES))
        elif kind == "near_miss":
            place = draw(_PLACES[aspect])
            done = changed(record, place, draw(NEAR_MISSES[place[-1]]))
        else:
            # `null` is a value of its own, read by where it is, never as an absent member (section 1 item 5).
            place = draw(_PLACES[aspect])
            value = draw(other_type(type(at(record, place)).__name__, size)) if kind == "retyped" else None
            done = changed(record, place, value, remove=kind == "removed")
        if done:
            changes.append(f"{kind} {'.'.join(place)}")
    return Envelope(record, tuple(changes), "mixed" if planned is None else planned[1] or planned[0])


_CHECKED_KINDS = st.sampled_from(CHANGES[:3])


@st.composite
def sweeps(draw: st.DrawFn, size: Size = SIZE) -> list[Envelope]:
    """A record changed at each aspect, by removal, another type or null there; one with a near miss in each
    patterned aspect; one of another record type; one with a place left unchecked; and one changed at random.

    So each example reaches every boundary. Drawn one change at a time, the rarer ones came up in under 1% of
    examples, and the search that kills a mutant took up to 1,900 examples to meet them.
    """
    planned: list[Change] = [(draw(_CHECKED_KINDS), aspect) for aspect in ASPECTS]
    planned += [("near_miss", aspect) for aspect in PATTERNED] + [("record_type", ""), ("unchecked", "")]
    return [draw(envelopes(size, change)) for change in planned] + [draw(envelopes(size))]


class VersionPair(NamedTuple):
    first: str
    second: str


@st.composite
def version_pairs(draw: st.DrawFn) -> VersionPair:
    """Two versions that match, the second most often the first with one component changed: one digit, so that
    long numbers differ only far from their start; one digit more or fewer; or the whole component."""
    first = [draw(NUMBERS) for _ in range(3)]
    second = list(first)
    index = draw(st.integers(0, 2))
    component = second[index]
    change = draw(st.sampled_from(["digit", "digit", "longer", "shorter", "number", "none"]))
    if change == "digit" and len(component) > 1:
        position = draw(st.integers(1, len(component) - 1))
        second[index] = component[:position] + str(draw(st.integers(0, 9))) + component[position + 1 :]
    elif change == "longer" and component != "0":
        second[index] = component + str(draw(st.integers(0, 9)))
    elif change == "shorter" and len(component) > 1:
        second[index] = component[:-1]
    elif change == "number":
        second[index] = draw(NUMBERS)
    return VersionPair(".".join(first), ".".join(second))
