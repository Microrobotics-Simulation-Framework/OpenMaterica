# SPDX-License-Identifier: Apache-2.0
"""Reads under a request's `extrapolation` (`declarations.md` section 4.1; `read_side_contract.md` sections 1,
2, 3 and 5), for the S3 design's HP24 to HP26 and its monotonicity property over an extrapolation
(`test_extrapolation_properties.py`).

A read is a table read that `table_read_strategies.py` draws, at a place its way names, beside the request's
acceptances: an extrapolation, drawn here, and for HP25 a second one. The extrapolation's `method` is one of
the vocabulary's tokens (generated from `declarations.md` section 4.1), its `law` any text of at least one
character, and its `basis` and `reason` each any JSON value or absent, which a read ignores (section 1); each
of these draws is held by a mutant that shows nowhere else (`test_extrapolation_mutants.py`).

Each property draws a way first, the place its rule tells apart, and builds the read for it, so that the
feature audit holds each way to its draw floor:
- HP24, where an extrapolation applies: one double outside the readable range, far outside it, outside a
  narrower `source_range` (inside `x`), and outside it with the value stated without origin, whose step-12
  reason only a read the extrapolation lets on reaches, the field holding the `label` its row names for a
  table over the axis drawn, where it names one, which step 12 adds too;
- HP24, where one does not apply although it names the read: inside the readable range, at an edge inside
  it, at an edge outside it, outside it beyond an edge, and outside it under another `want` of plain read's,
  `bounds`, `components` or `evidence`;
- HP25, where one is located elsewhere: at another field, another record, a region, an interval, or nowhere;
  and two that name one field: both at the read, one of them elsewhere, both elsewhere, and, as the control,
  two naming two fields;
- HP26, step 0's shape: `method` missing or not one of its tokens, `law` missing, not text or empty, each
  refused; and `law` of white space alone, `basis` and `reason` of any value, a member no document names, each
  read, and a member one slip from a named one, refused. Within a way, each list a value is drawn from (the
  methods that are no token, the laws of white space, the laws that are no text, and a slip's name and the
  place of its character) holds kinds of value a mutant shows at alone, one kind each;
- the monotonicity property: HP21's reads inside, at an end and outside a table the request can meet, with and
  without an extrapolation at the read."""

import copy
import json
from typing import NamedTuple, cast

from hypothesis import strategies as st

from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import ReadResult, read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from tests.property import table_read_strategies as tables
from tests.property.strategies import SIZE, Size
from tests.property.table_read_strategies import MetWorld, TableRead, request_of, table_field
from tests.property.value_fields import Json, mapping, row_of

# An extrapolation's methods, as the vocabulary generates them from `declarations.md` section 4.1.
METHODS = VOCABULARY.token_lists["extrapolation_method"]
# Text of at least one character, which a reader does not judge (`declarations.md` section 4.1): any text,
# so that one outside ASCII is drawn as often as it falls; and white space alone, which HP26 draws as a way of
# its own, of three kinds, each held by a mutant that shows at it alone: ASCII's spaces, one or several;
# ASCII's tab and newline; and white space outside ASCII, which readers that take Unicode's list of white
# space and those that take ASCII's tell apart.
LAWS = st.text(min_size=1, max_size=12)
WHITE_SPACE = (" ", "\t", "\n", "\N{NO-BREAK SPACE}", "\N{IDEOGRAPHIC SPACE}", "   ")
# A JSON value of any type but a string, of each of JSON's five other kinds, each held as a `law` by a mutant
# that shows at it alone; and any JSON value, for the members a read ignores.
NOT_TEXT = cast(
    st.SearchStrategy[JsonValue],
    st.one_of(
        st.none(),
        st.booleans(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.lists(st.text(max_size=4), max_size=2),
        st.dictionaries(st.text(max_size=4), st.text(max_size=4), max_size=2),
    ),
)
IGNORED: st.SearchStrategy[JsonValue] = st.one_of(NOT_TEXT, st.text(max_size=8))

APPLIED_WAYS = (
    "one_double_outside",
    "far_outside",
    "outside_a_narrower_source_range",
    "stated_without_origin",
)
NOT_APPLIED_WAYS = (
    "inside_the_range",
    "at_an_edge_inside",
    "at_an_edge_outside",
    "across_an_edge",
    "under_another_want",
)
# The `want`s of plain read but `value` (`read_side_contract.md` section 6), under which an extrapolation is
# not applied: "Under any other `want`" (section 5).
OTHER_WANTS = ("bounds", "components", "evidence")
ELSEWHERE_WAYS = ("another_field", "another_record", "a_region", "an_interval", "no_location")
TWO_WAYS = ("both_at_the_read", "one_at_the_read_one_elsewhere", "both_elsewhere", "each_its_own_field")
REFUSED_SHAPE_WAYS = ("method_missing", "method_unknown", "law_missing", "law_not_text", "law_empty")
READ_SHAPE_WAYS = ("law_white_space", "basis_and_reason_any", "an_unknown_member", "a_slip_of_a_member")
MONOTONE_WAYS = tables.RANGE_WAYS[:4]

# The members named at an extrapolation's place (`declarations.md` section 4.1; `read_side_contract.md`
# section 1), from the text: every acceptance's kind, location, field, reason and basis, and its own method
# and law. A slip is drawn of each, its character put before the name, inside it or after it; each kind of
# member and each place is held by a mutant that shows at it alone.
NAMED = ("acceptance", "record", "region", "interval", "field", "reason", "basis", "method", "law")
# A field other than any the reads draw, whose row the vocabulary registers.
OTHER_FIELD = "bulk.elemental_composition"
# A member more than one slip from every named one (`record_format.md` section 10).
UNKNOWN_MEMBER = "curation_note"
# Methods one change from a token, or none of them: a capital, a space for the underscore, another word, a
# space added, the empty string, and values that are no string. Each kind is held by a mutant that shows at it
# alone; the capital by the fuzz control's own fault, a method compared ignoring case.
NOT_METHODS: tuple[JsonValue, ...] = (
    "Constant",
    "consumer law",
    "linear",
    "clamp",
    "",
    "constant ",
    1.0,
    None,
)


class Extrapolated(NamedTuple):
    """A table read and the request's acceptances: the way drawn; the table read, its place, `want` and
    origin; the extrapolation drawn at the read, or None; and the acceptances the request holds, that one
    among them where it applies."""

    way: str
    drawn: TableRead
    extrapolation: Json | None
    acceptances: tuple[JsonValue, ...]


def pin_of(drawn: TableRead) -> Json:
    """The read's record, as a reference pins it: its id, version and content hash."""
    return {
        "id": drawn.record["id"],
        "version": drawn.record["version"],
        "content_hash": content_hash(drawn.record),
    }


def request_with(drawn: TableRead, acceptances: tuple[JsonValue, ...]) -> Json:
    """`drawn`'s request with `acceptances`, none where they are none."""
    request = request_of(drawn)
    if acceptances:
        request["acceptances"] = list(copy.deepcopy(acceptances))
    return request


def read_with(drawn: TableRead, acceptances: tuple[JsonValue, ...]) -> ReadResult:
    """The read of `drawn` under `acceptances`. A read never raises for what a request holds
    (`read_side_contract.md` section 2 item 1), so a raise fails the property that reads it."""
    store = RecordStore()
    store.add("record", json.dumps({**drawn.record, "content_hash": content_hash(drawn.record)}).encode())
    try:
        return read(request_with(drawn, acceptances), store)
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error


@st.composite
def extrapolations(draw: st.DrawFn, drawn: TableRead) -> Json:
    """An extrapolation of `drawn`'s field located at its record, `method` and `law` drawn, `basis` and
    `reason` any value or absent."""
    found: Json = {
        "acceptance": "extrapolation",
        "record": pin_of(drawn),
        "field": drawn.field,
        "method": draw(st.sampled_from(METHODS)),
        "law": draw(LAWS),
    }
    for name in ("basis", "reason"):
        if draw(st.booleans()):
            found[name] = draw(IGNORED)
    return found


def labelled(drawn: TableRead) -> TableRead:
    """`drawn` with its field's `label`, where the field's row names one that a table over the drawn axis may
    hold (`vocabulary/fields.json`: `label`, and `label_not_on_axis`, the axis it may not be held over): the
    label step 12 adds (`read_side_contract.md` section 2, the `labels` row: "and the field's `label`")."""
    row = row_of(drawn.field)
    label, not_on = row.get("label"), row.get("label_not_on_axis")
    if not isinstance(label, str) or not isinstance(not_on, str) or not_on == drawn.axis:
        return drawn
    record = copy.deepcopy(drawn.record)
    table_field(drawn._replace(record=record))["label"] = label
    return drawn._replace(record=record)


# The places outside the readable range that HP25 and HP26 read at, where an extrapolation at the read would
# apply: HP21's one double and far outside, which `table_read_strategies.range_reads` draws between itself.
OUTSIDE = tables.RANGE_WAYS[2:4]


@st.composite
def applied(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = APPLIED_WAYS) -> Extrapolated:
    """HP24 where the extrapolation applies: a read outside the readable range, at no edge and across none
    (HP21's outside ways), under `want: value`; with the value stated without origin, one double outside, the
    field holding its row's `label` where the row names one for a table over the axis."""
    way = draw(st.sampled_from(ways))
    drawn = draw(tables.range_reads(size, ("one_double_outside" if way == "stated_without_origin" else way,)))
    if way == "stated_without_origin":
        drawn = labelled(tables.stated_without_origin(drawn))
    extrapolation = draw(extrapolations(drawn))
    return Extrapolated(way, drawn, extrapolation, (extrapolation,))


@st.composite
def not_applied(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = NOT_APPLIED_WAYS) -> Extrapolated:
    """HP24 where an extrapolation at the read does not apply: strictly inside the readable range or at an end
    of it (HP21's two ways, which `range_reads` draws between itself), at an edge inside or outside it and
    beyond one, the edge outside the range or on its end (HP20's), and outside it under another `want`, one
    of `OTHER_WANTS`."""
    way = draw(st.sampled_from(ways))
    if way == "inside_the_range":
        drawn = draw(tables.range_reads(size, tables.RANGE_WAYS[:2]))
    elif way == "under_another_want":
        drawn = draw(tables.range_reads(size, OUTSIDE))._replace(want=draw(st.sampled_from(OTHER_WANTS)))
    else:
        drawn = draw(tables.edge_reads(size, (way,)))
    extrapolation = draw(extrapolations(drawn))
    return Extrapolated(way, drawn, extrapolation, (extrapolation,))


def located(extrapolation: Json, way: str, drawn: TableRead) -> Json:
    """`extrapolation` moved elsewhere by `way`: another field, another record (another version of the read's,
    its hash recomputed), a region, an interval beside the read's record, or no location."""
    moved = copy.deepcopy(extrapolation)
    if way == "another_field":
        moved["field"] = OTHER_FIELD
    elif way == "another_record":
        other = {**drawn.record, "version": "9.9.9"}
        moved["record"] = {
            "id": other["id"],
            "version": other["version"],
            "content_hash": content_hash(other),
        }
    elif way == "a_region":
        del moved["record"]
        moved["region"] = "lumen"
    elif way == "an_interval":
        moved["interval"] = 0.0
    else:
        del moved["record"]
    return moved


@st.composite
def elsewhere(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = ELSEWHERE_WAYS) -> Extrapolated:
    """HP25 where the extrapolation is located elsewhere, for a read it would cover at the read, outside the
    readable range."""
    way = draw(st.sampled_from(ways))
    drawn = draw(tables.range_reads(size, OUTSIDE))
    extrapolation = located(draw(extrapolations(drawn)), way, drawn)
    return Extrapolated(way, drawn, None, (extrapolation,))


@st.composite
def two(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = TWO_WAYS) -> Extrapolated:
    """HP25's two extrapolations: both naming the read's field, at the read, one of them with no location, or
    one at a region and one with none, each refused whatever location it holds; and, the control, the second
    for another field, both read, the one at the read applied. In an order drawn, so that the one that applies
    is the second in half the draws. The read lies outside the readable range, where one at the read would
    apply."""
    way = draw(st.sampled_from(ways))
    drawn = draw(tables.range_reads(size, OUTSIDE))
    first, second = draw(extrapolations(drawn)), draw(extrapolations(drawn))
    if way == "one_at_the_read_one_elsewhere":
        second = located(second, "no_location", drawn)
    elif way == "both_elsewhere":
        first, second = located(first, "a_region", drawn), located(second, "no_location", drawn)
    elif way == "each_its_own_field":
        second = located(second, "another_field", drawn)
    pair = (first, second) if draw(st.booleans()) else (second, first)
    return Extrapolated(way, drawn, first if way == "each_its_own_field" else None, pair)


@st.composite
def refused_shapes(
    draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = REFUSED_SHAPE_WAYS
) -> Extrapolated:
    """HP26's refusals: `method` missing or not one of its tokens, `law` missing, not text or empty, on an
    extrapolation at the read or, in half the draws, with no location ("whatever field or location it
    names"), each refused at step 0."""
    way = draw(st.sampled_from(ways))
    drawn = draw(tables.range_reads(size, OUTSIDE))
    extrapolation = draw(extrapolations(drawn))
    if way == "method_missing":
        del extrapolation["method"]
    elif way == "method_unknown":
        extrapolation["method"] = draw(st.sampled_from(NOT_METHODS))
    elif way == "law_missing":
        del extrapolation["law"]
    elif way == "law_not_text":
        extrapolation["law"] = draw(NOT_TEXT)
    else:
        extrapolation["law"] = ""
    if draw(st.booleans()):
        extrapolation = located(extrapolation, "no_location", drawn)
    return Extrapolated(way, drawn, None, (extrapolation,))


@st.composite
def read_shapes(draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = READ_SHAPE_WAYS) -> Extrapolated:
    """HP26's members a read takes or refuses beside a shape it keeps: `law` of white space alone, read;
    `basis` and `reason` of any value, read; a member no document names, read; and a member one slip from a
    named one beside it, the name with a character added (`record_format.md` section 10), refused."""
    way = draw(st.sampled_from(ways))
    drawn = draw(tables.range_reads(size, OUTSIDE))
    extrapolation = draw(extrapolations(drawn))
    if way == "law_white_space":
        extrapolation["law"] = draw(st.sampled_from(WHITE_SPACE))
    elif way == "basis_and_reason_any":
        extrapolation["basis"], extrapolation["reason"] = draw(IGNORED), draw(IGNORED)
    elif way == "an_unknown_member":
        extrapolation[UNKNOWN_MEMBER] = draw(IGNORED)
    else:
        named = draw(st.sampled_from(NAMED))
        at = draw(st.integers(0, len(named)))
        extrapolation[named[:at] + "x" + named[at:]] = draw(IGNORED)
    return Extrapolated(way, drawn, extrapolation, (extrapolation,))


def read_world(world: MetWorld, acceptances: tuple[JsonValue, ...]) -> ReadResult:
    """The read of `world`'s request, without its tolerance on the axis, under `acceptances`."""
    store = RecordStore()
    store.add("record", json.dumps(world.plain).encode())
    request = copy.deepcopy(world.request)
    if acceptances:
        request["acceptances"] = list(copy.deepcopy(acceptances))
    try:
        return read(request, store)
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error


class MonotoneWorld(NamedTuple):
    """The monotonicity property's world: a table read the request can meet, at a place its way names
    (`table_read_strategies.met_worlds`), and the extrapolation added at the read."""

    world: MetWorld
    extrapolation: Json


@st.composite
def monotone_worlds(
    draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] = MONOTONE_WAYS
) -> MonotoneWorld:
    world = draw(tables.met_worlds(size, ways))
    pin = mapping(mapping(world.request["target"])["record"])
    extrapolation: Json = {
        "acceptance": "extrapolation",
        "record": copy.deepcopy(pin),
        "field": world.field,
        "method": draw(st.sampled_from(METHODS)),
        "law": draw(LAWS),
    }
    return MonotoneWorld(world, extrapolation)
