# SPDX-License-Identifier: Apache-2.0
"""Mutants of S3a's table form through steps 8 and 9 (`core/fields.py`'s table reader, the slips and labels of
`core/value_shapes.py`), each with one fault, and the property of `test_table_form_properties.py` that must
kill each one, or its planned search: the S3 design's mutants of HP13 to HP16, one that lets a table's fault
refuse its record's other fields, and the code S3a's review found raising on an empty `x`. As in
`test_alternatives_mutants.py`, each must die within the examples the `ci` profile gives a property, at both
sizes, at an example of a fault, kind or way it names, and at the assertion it names, and records the examples
its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function or table of
`fields` or `value_shapes`, or the check `fields.OWN_MEMBERS` holds for a table.
"""

import collections
import itertools
import math
import re
import unicodedata
from collections.abc import Callable
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import fields, value_shapes
from materica.core.jsonio import JsonValue
from materica.core.slips import slipped
from materica.core.value_shapes import Found, JsonObject, invalid
from materica.core.vocabulary import VOCABULARY, RecordFieldSpec
from tests.property import table_form_strategies as strategies
from tests.property import test_table_form_properties as properties
from tests.property.condition_strategies import OTHER_UNITS
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.table_form_strategies import CATALOGUE
from tests.property.test_condition_mutants import kill

# Each property that kills a mutant, by name: its examples at a size, its check, and what an example drew.
Killer = tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None], Callable[[Any], str]]
ZERO_FAULTS = ("zero_edge_both_signs", "edges_zero_and_minus_zero")


def faults_of(part: str) -> Callable[[Size], st.SearchStrategy[strategies.Faulty]]:
    return lambda size: strategies.faulty_reads(part, size)


def fault_drawn(faulty: strategies.Faulty) -> str:
    return faulty.fault


KILLERS: dict[str, Killer] = {
    **{f"HP13 {part}": (faults_of(part), properties.check_one_fault, fault_drawn) for part in CATALOGUE},
    # Planned searches of HP13, each drawing alone the faults its mutant dies at, where HP13's own draws first
    # met another assertion or met the fault late (the S3a review, M4 and L3: over 40 streams a size,
    # `zero_and_minus_zero_by_sign_bit` first failed at the base on 15 of 80, and
    # `axis_condition_held_as_a_value_accepted` died as late as the 489th example). The first draws an edge at
    # zero held as `-0` and `0`, near miss or fault, on a base whose zeros are each held as `0`, which a
    # reader comparing zeros by their sign bit does not refuse; the second the near miss alone, on any base;
    # the third the axis condition held as a value, the way of `axis_condition_held_otherwise` it shows in.
    "HP13 edges, signed zeros on a base held alike": (
        lambda size: strategies.faulty_reads("edges", size, only=ZERO_FAULTS, zeros_alike=True),
        properties.check_one_fault,
        fault_drawn,
    ),
    "HP13 edges, the zero edge's near miss": (
        lambda size: strategies.faulty_reads("edges", size, only=("zero_edge_both_signs",)),
        properties.check_one_fault,
        fault_drawn,
    ),
    "HP13 tokens, the axis condition held as a value": (
        strategies.axis_conditions_held_as_a_value,
        properties.check_one_fault,
        fault_drawn,
    ),
    "HP14": (strategies.added_members, properties.check_added, lambda added: added.kind),
    "HP15": (strategies.other_axis_units, properties.check_other_axis_unit, lambda drawn: drawn.kind),
    "HP16": (strategies.labelled_tables, properties.check_label, lambda labelled: labelled.way),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # the faults, kinds or ways one of which the example that kills it must show
    says: str  # a pattern the message of the assertion that kills it must match


def replacing(module: object, name: str, value: object) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setattr(module, name, value)


def replacing_item(mapping: dict[str, Any], key: str, value: object) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setitem(mapping, key, value)


def both(*injections: Callable[[pytest.MonkeyPatch], None]) -> Callable[[pytest.MonkeyPatch], None]:
    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        for injection in injections:
            injection(monkeypatch)

    return inject


# The functions the faults wrap, taken before any replaces them.
ABSCISSAE = fields._abscissae  # pyright: ignore[reportPrivateUsage]
SHARES = fields._shares_a_value_no_edge  # pyright: ignore[reportPrivateUsage]
AXIS_CONDITION = fields._axis_condition  # pyright: ignore[reportPrivateUsage]
RECORD_PROBLEMS = value_shapes.record_problems
COMPARE_UNIT = fields._compare_unit  # pyright: ignore[reportPrivateUsage]
SAME_UNIT = fields.same_unit
SLIPPED = slipped


def _y_length_unchecked(x: list[float], y: list[float], where: str, found: Found) -> None:
    return None


def _strictly_increasing(x: list[float], edges: list[float] | None, where: str, found: Found) -> None:
    """The S3 design's "`x` required strictly increasing (refuses edges)"."""
    ABSCISSAE(x, edges, where, found)
    if any(later <= earlier for earlier, later in itertools.pairwise(x)):
        found.append(invalid(f"{where}.x does not increase strictly"))


def _edge_at_an_end_accepted(x: list[float], edges: list[float] | None, where: str, found: Found) -> None:
    """Each edge between `x[0]` and `x[-1]` taken inclusive."""
    kept: Found = []
    ABSCISSAE(x, edges, where, kept)
    found.extend(reason for reason in kept if "not strictly between" not in str(reason.detail))
    for edge in edges or ():
        if not (x and x[0] <= edge <= x[-1]):
            found.append(invalid(f"{where}.edges holds {edge!r} outside x's ends"))


def _zero_accepted_in_log_log(scheme: JsonValue, values: list[float], where: str, found: Found) -> None:
    """`>=` for `>`: a log-log table's zero taken as positive."""
    if scheme == "loglog" and any(value < 0 for value in values):
        found.append(invalid(f"{where} is log-log and holds a negative x or y"))


def _any_scheme(value: JsonValue, where: str, found: Found) -> None:
    """An unknown scheme read as linear: any string taken."""
    if not isinstance(value, str):
        found.append(invalid(f"{where} is not a token"))


def _axis_condition_value_accepted(field: JsonObject, name: str, found: Found) -> None:
    """An axis condition held as a value (`value` or `range`) taken as the axis's own."""
    table, conditions = field.get("table"), field.get("conditions")
    axis = table.get("axis") if isinstance(table, dict) else None
    held = conditions.get(axis) if isinstance(conditions, dict) and isinstance(axis, str) else None
    if isinstance(held, dict) and ("value" in held or "range" in held):
        return
    AXIS_CONDITION(field, name, found)


def _by_sign_bit(x: list[float], edges: list[float] | None, where: str, found: Found) -> None:
    """`-0` and `0` compared by sign bit, as two numbers, in `x` and in `edges`."""
    signed_x = [(value, math.copysign(1.0, value)) for value in x]
    signed_edges = [(edge, math.copysign(1.0, edge)) for edge in edges or ()]
    for edge in signed_edges:
        at = [index for index, value in enumerate(signed_x) if value == edge]
        if not (x and x[0] < edge[0] < x[-1]):
            found.append(invalid(f"{where}.edges holds {edge[0]!r}, not strictly between x's ends"))
        if len(at) != 2 or at[1] != at[0] + 1:
            found.append(invalid(f"{where}.edges holds {edge[0]!r}, which x does not hold twice in a row"))
    if len(set(signed_x)) < 2 or any(later < earlier for earlier, later in itertools.pairwise(x)):
        found.append(invalid(f"{where}.x is out of order or of one value"))
    if any(signed_x.count(value) > 1 and value not in signed_edges for value in signed_x):
        found.append(invalid(f"{where}.x repeats a value that is no edge"))


def _edges_once_by_sign_bit(edges: list[float], where: str, found: Found) -> None:
    if len({(edge, math.copysign(1.0, edge)) for edge in edges}) < len(edges):
        found.append(invalid(f"{where}.edges lists a number twice"))


def _token_condition_axis_invalid(value: JsonValue, where: str, found: Found) -> None:
    """A token condition's name as axis given `form_invalid`, as a token known for another member."""
    if isinstance(value, str) and value in VOCABULARY.conditions:
        if value not in VOCABULARY.token_lists["axis"]:
            found.append(invalid(f"{where} names a token condition"))
            return
    value_shapes.token_problems(value, "axis", VOCABULARY.token_lists["axis"], where, found)


def _nothing(*arguments: object) -> None:
    return None


def _only_at_an_edge_refused(
    source_range: list[float], x: list[float], edges: list[float], where: str, found: Found
) -> None:
    """A `source_range` disjoint from `x`'s range accepted: only one meeting it at an edge refused."""
    lo, hi = source_range
    if not x:
        return
    shared_lo, shared_hi = max(lo, x[0]), min(hi, x[-1])
    if shared_lo == shared_hi and shared_lo in edges:
        found.append(invalid(f"{where} meets x's range only at an edge"))


def _disjoint_alone_refused(
    source_range: list[float], x: list[float], edges: list[float], where: str, found: Found
) -> None:
    """A `source_range` meeting `x`'s range only at an edge accepted: only a disjoint one refused."""
    lo, hi = source_range
    if x and lo <= hi and max(lo, x[0]) > min(hi, x[-1]):
        found.append(invalid(f"{where} is disjoint from x's range"))


def _ends_of_any_x_read(x: list[float], edges: list[float] | None, where: str, found: Found) -> None:
    """S3a's `_abscissae` as its review found it (H1): each edge compared with `x[0]` and `x[-1]`, whatever
    `x` holds."""
    if len(set(x)) < 2:
        found.append(invalid(f"{where}.x holds fewer than two distinct values"))
    if any(later < earlier for earlier, later in itertools.pairwise(x)):
        found.append(invalid(f"{where}.x decreases"))
    for edge in edges or ():
        at = [index for index, value in enumerate(x) if value == edge]
        if not x[0] < edge < x[-1]:
            found.append(invalid(f"{where}.edges holds {edge!r}, not strictly between x's ends"))
        if len(at) != 2 or at[1] != at[0] + 1:
            found.append(invalid(f"{where}.edges holds {edge!r}, which x does not hold twice in a row"))
    held = collections.Counter(x)
    if repeated := sorted(value for value, count in held.items() if count > 1 and value not in (edges or ())):
        found.append(invalid(f"{where}.x repeats {repeated}, which are no edges"))


def _shares_with_the_ends_of_any_x(
    source_range: list[float], x: list[float], edges: list[float], where: str, found: Found
) -> None:
    """S3a's `_shares_a_value_no_edge` as its review found it (H1): `x`'s ends read whatever `x` holds."""
    lo, hi = source_range
    if lo > hi:
        return
    shared_lo, shared_hi = max(lo, x[0]), min(hi, x[-1])
    if shared_lo > shared_hi or (shared_lo == shared_hi and shared_lo in edges):
        found.append(invalid(f"{where} shares no value that is no edge with x's range"))


def _points_invalid(entry: JsonObject, where: str, found: Found) -> None:
    """`points` given `form_invalid` in place of `points_unsupported`."""
    if "points" in entry:
        found.append(invalid(f"{where} holds points"))


def _table_faults_of_the_record(record: JsonObject) -> Found:
    """A table's fault refusing every field read from its record: each table of the record checked with the
    record's structure."""
    found = RECORD_PROBLEMS(record)
    body = record.get("body")
    sections = body.get("sections") if isinstance(body, dict) else None
    for section in sections.values() if isinstance(sections, dict) else ():
        held = section.get("fields") if isinstance(section, dict) else None
        for value in held.values() if isinstance(held, dict) else ():
            if isinstance(value, dict) and value.get("form") == "table":
                fields.table(value.get("table"), "a table of the record", found)
    return found


def _slipped_but(name: str) -> Callable[..., list[tuple[str, str]]]:
    """The slips, a slip of `name` among them ignored."""

    def slipped(members: Any, named: Any) -> list[tuple[str, str]]:
        return [(member, near) for member, near in SLIPPED(members, named) if near != name]

    return slipped


def _compare_unit_without_the_axis(
    stored: JsonValue, registered: JsonValue, where: str, condition: str | None, found: Found
) -> None:
    """The reason of a table's `axis_unit` given without the axis as its condition."""
    COMPARE_UNIT(stored, registered, where, None if where.endswith(".axis_unit") else condition, found)


def _same_unit_under_nfkc(stored: JsonValue, registered: JsonValue) -> bool:
    if isinstance(stored, str) and isinstance(registered, str):
        return unicodedata.normalize("NFKC", stored) == unicodedata.normalize("NFKC", registered)
    return SAME_UNIT(stored, registered)


def _label_blind_to_the_axis(spec: RecordFieldSpec, form: str | None, field: JsonObject) -> bool:
    """The label taken on a table of any axis, where the row names one."""
    if form == "constant":
        return spec.label is not None
    return form == "table" and spec.label is not None


TABLE_CHECK = fields.TABLE

MUTANTS = [
    Mutant(
        "y_length_unchecked",
        "HP13 knots",
        replacing(fields, "_one_y_for_each_x", _y_length_unchecked),
        ("y_longer", "y_shorter"),
        "^the fault",
    ),
    Mutant(
        "x_strictly_increasing",
        "HP13 edges, the zero edge's near miss",
        replacing(fields, "_abscissae", _strictly_increasing),
        ("zero_edge_both_signs",),
        "^the fault zero_edge_both_signs",
    ),
    Mutant(
        "edge_at_an_end_accepted",
        "HP13 edges",
        replacing(fields, "_abscissae", _edge_at_an_end_accepted),
        ("edge_at_an_end",),
        "^the fault edge_at_an_end",
    ),
    Mutant(
        "zero_accepted_in_log_log",
        "HP13 edges",
        replacing(fields, "_positive_where_log_log", _zero_accepted_in_log_log),
        ("log_log_not_positive",),
        "^the fault log_log_not_positive",
    ),
    Mutant(
        "unknown_scheme_read_as_linear",
        "HP13 tokens",
        replacing_item(TABLE_CHECK, "scheme", _any_scheme),
        ("scheme_unknown",),
        "^the fault scheme_unknown",
    ),
    Mutant(
        "axis_condition_held_as_a_value_accepted",
        "HP13 tokens, the axis condition held as a value",
        replacing(fields, "_axis_condition", _axis_condition_value_accepted),
        ("axis_condition_held_otherwise",),
        "^the fault axis_condition_held_otherwise",
    ),
    Mutant(
        "zero_and_minus_zero_by_sign_bit",
        "HP13 edges, signed zeros on a base held alike",
        both(
            replacing(fields, "_abscissae", _by_sign_bit),
            replacing(fields, "_edges_once", _edges_once_by_sign_bit),
        ),
        ("zero_edge_both_signs", "edges_zero_and_minus_zero"),
        "^the fault (zero_edge_both_signs|edges_zero_and_minus_zero)",
    ),
    Mutant(
        "token_condition_axis_form_invalid",
        "HP13 tokens",
        replacing_item(TABLE_CHECK, "axis", _token_condition_axis_invalid),
        ("axis_token_condition",),
        "^the fault axis_token_condition",
    ),
    Mutant(
        "source_range_unchecked",
        "HP13 source_range_and_points",
        both(
            replacing_item(fields.TABLE_OPTIONAL, "source_range", _nothing),
            replacing(fields, "_shares_a_value_no_edge", _nothing),
        ),
        (
            "source_range_reversed",
            "source_range_disjoint",
            "source_range_only_at_an_edge",
            "source_range_not_two_numbers",
        ),
        "^the fault source_range",
    ),
    Mutant(
        "disjoint_source_range_accepted",
        "HP13 source_range_and_points",
        replacing(fields, "_shares_a_value_no_edge", _only_at_an_edge_refused),
        ("source_range_disjoint",),
        "^the fault source_range_disjoint",
    ),
    Mutant(
        "points_ignored",
        "HP13 source_range_and_points",
        replacing(fields, "_points", _nothing),
        ("points", "points_null"),
        "^the fault points",
    ),
    Mutant(
        "source_range_meeting_x_only_at_an_edge_accepted",
        "HP13 source_range_and_points",
        replacing(fields, "_shares_a_value_no_edge", _disjoint_alone_refused),
        ("source_range_only_at_an_edge",),
        "^the fault source_range_only_at_an_edge",
    ),
    Mutant(
        "ends_of_an_empty_x_read",
        "HP13 source_range_and_points",
        both(
            replacing(fields, "_abscissae", _ends_of_any_x_read),
            replacing(fields, "_shares_a_value_no_edge", _shares_with_the_ends_of_any_x),
        ),
        ("x_empty_beside_edges_or_a_source_range",),
        "^the fault x_empty_beside_edges_or_a_source_range: Outcome[(]status=.raised IndexError",
    ),
    Mutant(
        "points_form_invalid",
        "HP13 source_range_and_points",
        replacing(fields, "_points", _points_invalid),
        ("points", "points_null"),
        "^the fault points",
    ),
    Mutant(
        "a_tables_fault_refuses_its_records_other_fields",
        "HP13 knots",
        replacing(fields, "record_problems", _table_faults_of_the_record),
        tuple(CATALOGUE["knots"]),
        "^the neighbour",
    ),
    Mutant(
        "edge_slip_ignored",
        "HP14",
        replacing(value_shapes, "slipped", _slipped_but("edges")),
        strategies.KINDS[1:],
        r"^the member '[a-z_]*' \(",
    ),
    Mutant(
        "point_slip_ignored",
        "HP14",
        replacing(fields, "TABLE_RESERVED", ()),
        strategies.KINDS[1:],
        r"^the member '[a-z_]*' \(",
    ),
    Mutant(
        "axis_unit_reason_without_its_condition",
        "HP15",
        replacing(fields, "_compare_unit", _compare_unit_without_the_axis),
        OTHER_UNITS,
        "^the axis unit",
    ),
    Mutant(
        "axis_unit_compared_under_nfkc",
        "HP15",
        replacing(fields, "same_unit", _same_unit_under_nfkc),
        ("compatibility_equal",),
        "^the axis unit compatibility_equal",
    ),
    Mutant(
        "label_blind_to_the_axis",
        "HP16",
        replacing(value_shapes, "label_allowed", _label_blind_to_the_axis),
        ("on_its_rows_axis",),
        "^the label on_its_rows_axis",
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_table_form_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the faults, kinds or ways it names, and at the assertion it names."""
    mutant.inject(monkeypatch)
    examples, check, drew = KILLERS[mutant.killer]
    said: list[str] = []

    def checked(example: Any) -> None:
        try:
            check(example)
        except AssertionError as error:
            said.append(str(error))
            raise

    tried, example = kill(examples(size), checked)
    record_property("examples_to_kill", tried)
    assert drew(example) in mutant.dies_at, drew(example)
    assert re.search(mutant.says, said[0]), said[0]
