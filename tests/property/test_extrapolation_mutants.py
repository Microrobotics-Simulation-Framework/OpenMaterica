# SPDX-License-Identifier: Apache-2.0
"""Mutants of S3c's extrapolation (`core/read.py`'s step 0 for an extrapolation, `form_range` at step 11, and
the read past it), each with one fault, and the property of `test_extrapolation_properties.py` that must kill
it: the S3 design's mutants of HP24 to HP26 and of its monotonicity property over an extrapolation (sections
6.7 and 6.8). As in `test_table_read_mutants.py`, each must die within the examples the `ci` profile gives a
property, at both sizes, at an example of a way it names, and at the assertion it names, and records the
examples its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function of `read` or
`evaluate`, or a method of `read.Extrapolation`.
"""

import dataclasses
import re
from collections.abc import Callable
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import evaluate
from materica.core import read as read_module
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.read import Extrapolation, FieldRead, FormRange, ReadRequest
from materica.core.reasons import Reason
from materica.core.slips import slipped
from materica.core.value_shapes import JsonObject
from tests.property import extrapolation_strategies as strategies
from tests.property import test_extrapolation_properties as properties
from tests.property import test_table_read_mutants as table_read_mutants
from tests.property.extrapolation_strategies import (
    APPLIED_WAYS,
    ELSEWHERE_WAYS,
    READ_SHAPE_WAYS,
    REFUSED_SHAPE_WAYS,
    TWO_WAYS,
)
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill

# Each property that kills a mutant, by name: its examples at a size, its check, and the way an example drew.
Killer = tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None], Callable[[Any], str]]


def way_of(example: strategies.Extrapolated) -> str:
    return example.way


KILLERS: dict[str, Killer] = {
    "HP24": (lambda size: strategies.applied(size), properties.check_applied, way_of),
    "HP24 not applied": (lambda size: strategies.not_applied(size), properties.check_not_applied, way_of),
    # A planned search of HP24 where it does not apply: across an edge alone, the way that draws an edge
    # on the readable range's end (in half its draws), where the mutants of step 11's report on such an
    # edge show, a report that has a reader in a result since S3c.
    "HP24 not applied, across an edge": (
        lambda size: strategies.not_applied(size, ("across_an_edge",)),
        properties.check_not_applied,
        way_of,
    ),
    "HP25": (lambda size: strategies.elsewhere(size), properties.check_elsewhere, way_of),
    "HP25 two": (lambda size: strategies.two(size), properties.check_two, way_of),
    "HP26 refused": (lambda size: strategies.refused_shapes(size), properties.check_refused_shape, way_of),
    "HP26 read": (lambda size: strategies.read_shapes(size), properties.check_read_shape, way_of),
    "monotonicity": (
        lambda size: strategies.monotone_worlds(size),
        properties.check_monotone,
        lambda example: example.world.way,
    ),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # the ways one of which the example that kills it must show
    says: str  # a pattern the message of the assertion that kills it must match


def replacing(owner: object, name: str, value: object) -> Callable[[pytest.MonkeyPatch], None]:
    return lambda monkeypatch: monkeypatch.setattr(owner, name, value)


# The functions the faults wrap, taken before any replaces them.
FORM_RANGE = read_module.form_range
RANGE_REPORT = read_module.range_report
READ_VALUE_FIELD = read_module.read_value_field
EXTRAPOLATION = read_module._extrapolation  # pyright: ignore[reportPrivateUsage]
ACCEPTANCES = read_module._acceptances  # pyright: ignore[reportPrivateUsage]
LOCATED_AT = Extrapolation.located_at
# S3b-2's two mutants of step 11's report on an edge on the readable range's end.
LOWER_END_NOT_ACROSS = (
    table_read_mutants._an_edge_on_the_lower_end_not_across  # pyright: ignore[reportPrivateUsage]
)
UPPER_END_NOT_ACROSS = (
    table_read_mutants._an_edge_on_the_upper_end_not_across  # pyright: ignore[reportPrivateUsage]
)


def _numbers(table: JsonObject, name: str) -> list[float]:
    found = table.get(name)
    return [float(number) for number in found if isinstance(number, float)] if isinstance(found, list) else []


def _source_range(table: JsonObject) -> list[float] | None:
    return _numbers(table, "source_range") if "source_range" in table else None


def _axis_value(table: JsonObject, request: ReadRequest) -> float | None:
    operating = request.operating_conditions.get(str(table["axis"]))
    return operating["value"] if operating is not None and "value" in operating else None  # type: ignore[typeddict-item]


def _scheme(table: JsonObject) -> evaluate.Scheme:
    return "loglog" if table["scheme"] == "loglog" else "linear"


def _nearest_end(table: JsonObject, at: float) -> float:
    low, high = evaluate.readable_range(_numbers(table, "x"), _source_range(table))
    return low if at < low else high


def _covered(table: JsonObject, request: ReadRequest, report: FormRange) -> FormRange:
    """`report` covered by the request's extrapolation, whatever step 11 found, with the value at the readable
    range's nearest end as the read gives it outside (one side of an edge where the end lies on one)."""
    at = _axis_value(table, request)
    extrapolation = request.extrapolation()
    if at is None or extrapolation is None:
        return report
    x, y = _numbers(table, "x"), _numbers(table, "y")
    value = evaluate.value(x, y, _scheme(table), _nearest_end(table, at))
    return dataclasses.replace(report, value=value, extrapolation=extrapolation)


# HP24's, where it applies.


def _without(code: str, replacement: Reason | None = None) -> Callable[..., FieldRead]:
    """`read_value_field` with `code` taken from a read an extrapolation covers, or put in its place."""

    def mutated(
        field: RecordField, record: JsonObject, request: ReadRequest, claims: Any, nominal: Any = None
    ) -> FieldRead:
        found = READ_VALUE_FIELD(field, record, request, claims, nominal)
        if found.form_range is None or found.form_range.extrapolation is None:
            return found
        kept = tuple(reason for reason in found.reasons if reason.code != code)
        if replacement is not None:
            axis = found.form_range.reasons[0].condition
            kept = (*kept, dataclasses.replace(replacement, condition=axis))
        return dataclasses.replace(found, reasons=kept)

    return mutated


def _extrapolated_linearly(table: JsonObject, request: ReadRequest) -> FormRange:
    """Under an extrapolation, the value extrapolated linearly by the slope of the interval at the readable
    range's nearest end, as a consumer's law might, in place of the end value."""
    found = FORM_RANGE(table, request)
    at = _axis_value(table, request)
    if found.extrapolation is None or found.value is None or at is None:
        return found
    x, y = _numbers(table, "x"), _numbers(table, "y")
    end = _nearest_end(table, at)
    below, above = evaluate.interval(x, end)
    if below == above:
        # The end on a knot: the interval beside it on the read's side, or, where none lies there (a readable
        # range of one point at an end of `x`), the other.
        inward = below + 1 < len(x) and (at < end or below == 0)
        below, above = (below, below + 1) if inward else (below - 1, below)
    slope = (y[above] - y[below]) / (x[above] - x[below])
    value = found.value + slope * (at - end)
    return dataclasses.replace(found, value=value if value == value else found.value)


def _the_far_end(table: JsonObject, request: ReadRequest) -> FormRange:
    """Under an extrapolation, the value at the readable range's far end."""
    found = FORM_RANGE(table, request)
    at = _axis_value(table, request)
    if found.extrapolation is None or at is None:
        return found
    low, high = evaluate.readable_range(_numbers(table, "x"), _source_range(table))
    far = high if at < low else low
    if far in _numbers(table, "edges"):
        return found
    return dataclasses.replace(
        found, value=evaluate.value(_numbers(table, "x"), _numbers(table, "y"), _scheme(table), far)
    )


def _end_value_at_x(table: JsonObject, request: ReadRequest) -> FormRange:
    """Under an extrapolation, the end value taken at `x[0]` or `x[-1]` where `source_range` narrows the
    range."""
    found = FORM_RANGE(table, request)
    at = _axis_value(table, request)
    if found.extrapolation is None or at is None:
        return found
    x, y = _numbers(table, "x"), _numbers(table, "y")
    low, _ = evaluate.readable_range(x, _source_range(table))
    return dataclasses.replace(found, value=y[0] if at < low else y[-1])


def _steps_12_and_13_skipped(
    field: RecordField, record: JsonObject, request: ReadRequest, claims: Any, nominal: Any = None
) -> FieldRead:
    """A read an extrapolation covers given its value, but not step 12's reasons and labels."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    if found.form_range is None or found.form_range.extrapolation is None:
        return found
    reasons = tuple(reason for reason in found.reasons if reason.code != "stated_without_origin")
    return dataclasses.replace(found, reasons=reasons, labels=())


@dataclasses.dataclass(frozen=True)
class _WithAMember(Extrapolation):
    """An extrapolation whose `assumption` holds one more of the request's members, where it holds it."""

    held: dict[str, JsonValue] = dataclasses.field(default_factory=dict[str, JsonValue])

    def assumption(self) -> Any:
        return {**super().assumption(), **self.held}


def _in_the_assumption(name: str) -> Callable[..., Extrapolation | None]:
    """`_extrapolation`, its `assumption` holding the request's `name` too."""

    def mutated(index: int, entry: dict[str, JsonValue], found: list[Reason]) -> Extrapolation | None:
        checked = EXTRAPOLATION(index, entry, found)
        if checked is None:
            return None
        members = (checked.index, checked.field, checked.location, checked.method, checked.law)
        return _WithAMember(*members, held={name: entry[name]} if name in entry else {})

    return mutated


def _the_method_read_as_constant(self: Extrapolation) -> Any:
    """`assumption` naming the method `constant`, whatever the request gives."""
    return {"acceptance": "extrapolation", "method": "constant", "law": self.law}


# HP24's, where it does not apply.

END_BY_STRICT_INEQUALITY = (
    table_read_mutants._ends_by_strict_inequality  # pyright: ignore[reportPrivateUsage]
)


def _applied_under_any_want(table: JsonObject, request: ReadRequest) -> FormRange:
    """An extrapolation applied under any `want`, as under `want: value`."""
    return FORM_RANGE(table, dataclasses.replace(request, want="value"))


def _applied_at_an_edge_outside(table: JsonObject, request: ReadRequest) -> FormRange:
    """At an edge outside the readable range, the extrapolation applied: the range checked before the edge."""
    found = FORM_RANGE(table, request)
    codes = {reason.code for reason in found.reasons}
    if {"at_edge", "outside_range"} <= codes and request.want == "value":
        return _covered(table, request, found)
    return found


def _an_edge_read_under_an_extrapolation(table: JsonObject, request: ReadRequest) -> FormRange:
    """At an edge inside the readable range, under an extrapolation, the read taken on with the value below
    the edge."""
    found = FORM_RANGE(table, request)
    at = _axis_value(table, request)
    codes = {reason.code for reason in found.reasons}
    if codes == {"at_edge"} and at is not None and request.extrapolation() is not None:
        x, y = _numbers(table, "x"), _numbers(table, "y")
        return FormRange(value=y[x.index(at)])
    return found


def _applied_across_an_edge(table: JsonObject, request: ReadRequest) -> FormRange:
    """Beyond an edge outside the readable range or on its end, the extrapolation applied: the edges between
    the read and the range's end not looked at."""
    found = FORM_RANGE(table, request)
    if found.outside_alone and not found.coverable and request.want == "value":
        return _covered(table, request, found)
    return found


def _applied_inside_the_range(
    field: RecordField, record: JsonObject, request: ReadRequest, claims: Any, nominal: Any = None
) -> FieldRead:
    """An extrapolation of the read's field at its record applied to any read of its table, inside the range
    too: its `assumption` given and its index in `applied`."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    extrapolation = request.extrapolation()
    if extrapolation is None or found.table is None or found.form_range is not None:
        return found
    return dataclasses.replace(
        found, applied=(*found.applied, extrapolation.index), assumption=extrapolation.assumption()
    )


# HP25's.


def _applied_at_the_first_index(
    field: RecordField, record: JsonObject, request: ReadRequest, claims: Any, nominal: Any = None
) -> FieldRead:
    """`applied` holding the first acceptance's index, whichever one covered the read."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    if found.form_range is None or found.form_range.extrapolation is None:
        return found
    return dataclasses.replace(found, applied=(0,))


def _location_ignored(self: Extrapolation, field: str, record: Any) -> bool:
    """An extrapolation applied wherever it is located, or with no location, at the read's field."""
    return self.field == field


def _field_ignored(self: Extrapolation, field: str, record: Any) -> bool:
    """An extrapolation applied at the read's record whatever field it names."""
    return LOCATED_AT(dataclasses.replace(self, field=field), field, record)


def _two_read(order: int) -> Callable[..., Any]:
    """Two extrapolations naming one field read, not refused: the first or, `order` -1, the second applied."""

    def mutated(acceptances: list[JsonValue], found: list[Reason]) -> Any:
        before = len(found)
        implied, nominals, extrapolations = ACCEPTANCES(acceptances, found)
        found[before:] = [
            reason for reason in found[before:] if "two extrapolations" not in (reason.detail or "")
        ]
        return implied, nominals, extrapolations[::order]

    return mutated


# HP26's.


def _reshaped(change: Callable[[dict[str, JsonValue]], dict[str, JsonValue] | None]) -> Callable[..., Any]:
    """`_extrapolation` on the entry `change` gives, or refusing it where `change` gives None."""

    def mutated(index: int, entry: dict[str, JsonValue], found: list[Reason]) -> Extrapolation | None:
        changed = change(dict(entry))
        if changed is None:
            found.append(Reason("request_incomplete", detail="refused by the mutant"))
            return None
        checked = EXTRAPOLATION(index, changed, found)
        if checked is None:
            return None
        law, method = entry.get("law", checked.law), entry.get("method", checked.method)
        return dataclasses.replace(checked, law=law, method=method)  # type: ignore[arg-type]

    return mutated


def _law_optional_under_constant(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if entry.get("method") == "constant" and "law" not in entry:
        entry["law"] = "the end value held"
    return entry


def _an_empty_law_accepted(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if entry.get("law") == "":
        entry["law"] = " "
    return entry


def _law_of_any_type(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if "law" in entry and not isinstance(entry["law"], str):
        entry["law"] = "any law"
    return entry


def _method_unchecked(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if entry.get("method") not in strategies.METHODS:
        entry["method"] = "constant"
    return entry


def _white_space_refused(entry: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    law = entry.get("law")
    return None if isinstance(law, str) and law and not law.strip() else entry


def _basis_checked(entry: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    return None if "basis" in entry and not isinstance(entry["basis"], str) else entry


def _a_slip_ignored(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    named = strategies.NAMED
    return {name: member for name, member in entry.items() if name in named or not slipped([name], named)}


def _an_unknown_member_refused(entry: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    return None if any(name not in strategies.NAMED for name in entry) else entry


def _a_law_outside_ascii_refused(entry: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    law = entry.get("law")
    return None if isinstance(law, str) and not law.isascii() else entry


def _shape_unchecked_off_a_record(entry: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """An extrapolation with no record, or located at a region or an interval too, where no plain read could
    apply it, taken whatever its method and law."""
    if "record" in entry and "region" not in entry and "interval" not in entry:
        return entry
    return {**entry, "method": "constant", "law": "any law"}


# The monotonicity property's.


def _status_met(
    field: RecordField, record: JsonObject, request: ReadRequest, claims: Any, nominal: Any = None
) -> FieldRead:
    """Under an extrapolation that covers the read, `met`: every reason dropped."""
    found = READ_VALUE_FIELD(field, record, request, claims, nominal)
    if found.form_range is None or found.form_range.extrapolation is None:
        return found
    return dataclasses.replace(found, reasons=())


APPLIED_ON_ANY_SIDE = APPLIED_WAYS
MUTANTS = [
    # HP24's, where it applies (the S3 design's sections 6.7 and 6.8).
    Mutant(
        "status_met_under_an_extrapolation",
        "HP24",
        replacing(read_module, "read_value_field", _status_met),
        APPLIED_ON_ANY_SIDE,
        "^the [a-z_]+ read under an extrapolation: met(\n|$)",
    ),
    Mutant(
        "status_unknown_under_an_extrapolation",
        "HP24",
        replacing(read_module, "read_value_field", _without("outside_range", Reason("range_unstated"))),
        APPLIED_ON_ANY_SIDE,
        "^the [a-z_]+ read under an extrapolation: unknown(\n|$)",
    ),
    Mutant(
        "extrapolated_linearly",
        "HP24",
        replacing(read_module, "form_range", _extrapolated_linearly),
        APPLIED_ON_ANY_SIDE,
        "read's value .*, not the end value",
    ),
    Mutant(
        "the_far_ends_value",
        "HP24",
        replacing(read_module, "form_range", _the_far_end),
        APPLIED_ON_ANY_SIDE,
        "read's value .*, not the end value",
    ),
    Mutant(
        "end_value_at_x_where_source_range_narrows",
        "HP24",
        replacing(read_module, "form_range", _end_value_at_x),
        APPLIED_ON_ANY_SIDE,
        "read's value .*, not the end value",
    ),
    Mutant(
        "steps_12_and_13_skipped",
        "HP24",
        replacing(read_module, "read_value_field", _steps_12_and_13_skipped),
        ("stated_without_origin",),
        "^the stated_without_origin read's reasons under an extrapolation",
    ),
    Mutant(
        "basis_in_the_assumption",
        "HP24",
        replacing(read_module, "_extrapolation", _in_the_assumption("basis")),
        APPLIED_ON_ANY_SIDE,
        "read's assumption",
    ),
    # Each of `extrapolation_strategies.extrapolations`'s draws held by a mutant that shows there alone: its
    # `reason` (which the extrapolation holds in some draws), its method `consumer_law`, and a law outside
    # ASCII.
    Mutant(
        "reason_in_the_assumption",
        "HP24",
        replacing(read_module, "_extrapolation", _in_the_assumption("reason")),
        APPLIED_ON_ANY_SIDE,
        "read's assumption",
    ),
    Mutant(
        "the_method_read_as_constant",
        "HP24",
        replacing(Extrapolation, "assumption", _the_method_read_as_constant),
        APPLIED_ON_ANY_SIDE,
        "read's assumption",
    ),
    Mutant(
        "a_law_outside_ascii_refused",
        "HP24",
        replacing(read_module, "_extrapolation", _reshaped(_a_law_outside_ascii_refused)),
        APPLIED_ON_ANY_SIDE,
        "read under an extrapolation: not_met|read's reasons under an extrapolation",
    ),
    # HP24's, where it does not apply.
    Mutant(
        "applied_under_want_bounds",
        "HP24 not applied",
        replacing(read_module, "form_range", _applied_under_any_want),
        ("under_another_want",),
        "^the under_another_want read changed",
    ),
    Mutant(
        "applied_at_an_edge_outside_the_readable_range",
        "HP24 not applied",
        replacing(read_module, "form_range", _applied_at_an_edge_outside),
        ("at_an_edge_outside",),
        "^the at_an_edge_outside read changed",
    ),
    Mutant(
        "an_edge_read_under_an_extrapolation",
        "HP24 not applied",
        replacing(read_module, "form_range", _an_edge_read_under_an_extrapolation),
        ("at_an_edge_inside",),
        "^the at_an_edge_inside read changed",
    ),
    Mutant(
        "applied_across_an_edge",
        "HP24 not applied",
        replacing(read_module, "form_range", _applied_across_an_edge),
        ("across_an_edge",),
        "^the across_an_edge read changed",
    ),
    # The readable range's ends, which HP24 draws inside the range in half its draws there: a read at an end
    # read as outside, so that an extrapolation covers it.
    Mutant(
        "an_end_read_as_outside",
        "HP24 not applied",
        replacing(evaluate, "in_readable_range", END_BY_STRICT_INEQUALITY),
        ("inside_the_range",),
        "^the inside_the_range read changed",
    ),
    Mutant(
        "applied_inside_the_range",
        "HP24 not applied",
        replacing(read_module, "read_value_field", _applied_inside_the_range),
        ("inside_the_range",),
        "^the inside_the_range read changed",
    ),
    # Step 11's report on an edge on the readable range's end read as none between the read and the range
    # (S3b-2's two mutants of `evaluate.beyond_an_edge`), which HP20 searches in the report and HP24 now in a
    # result: under an extrapolation, a read beyond such an edge is given the end value.
    Mutant(
        "an_edge_on_the_lower_end_read_as_none_between",
        "HP24 not applied, across an edge",
        replacing(evaluate, "beyond_an_edge", LOWER_END_NOT_ACROSS),
        ("across_an_edge",),
        "^the across_an_edge read changed",
    ),
    Mutant(
        "an_edge_on_the_upper_end_read_as_none_between",
        "HP24 not applied, across an edge",
        replacing(evaluate, "beyond_an_edge", UPPER_END_NOT_ACROSS),
        ("across_an_edge",),
        "^the across_an_edge read changed",
    ),
    # HP25's.
    Mutant(
        "the_location_ignored",
        "HP25",
        replacing(Extrapolation, "located_at", _location_ignored),
        ELSEWHERE_WAYS[1:],
        "^the (another_record|a_region|an_interval|no_location) read changed",
    ),
    Mutant(
        "the_field_ignored",
        "HP25",
        replacing(Extrapolation, "located_at", _field_ignored),
        ("another_field",),
        "^the another_field read changed",
    ),
    Mutant(
        "two_read_the_first_applied",
        "HP25 two",
        replacing(read_module, "_acceptances", _two_read(1)),
        TWO_WAYS[:3],
        "^two extrapolations naming one field",
    ),
    Mutant(
        "two_read_the_second_applied",
        "HP25 two",
        replacing(read_module, "_acceptances", _two_read(-1)),
        TWO_WAYS[:3],
        "^two extrapolations naming one field",
    ),
    # The two extrapolations' order, which `extrapolation_strategies.two` draws: the one that applies second.
    Mutant(
        "applied_at_the_first_index",
        "HP25 two",
        replacing(read_module, "read_value_field", _applied_at_the_first_index),
        ("each_its_own_field",),
        "^two for two fields applied",
    ),
    # HP26's.
    Mutant(
        "law_optional_under_constant",
        "HP26 refused",
        replacing(read_module, "_extrapolation", _reshaped(_law_optional_under_constant)),
        ("law_missing",),
        "^an extrapolation with its law_missing",
    ),
    Mutant(
        "an_empty_law_accepted",
        "HP26 refused",
        replacing(read_module, "_extrapolation", _reshaped(_an_empty_law_accepted)),
        ("law_empty",),
        "^an extrapolation with its law_empty",
    ),
    Mutant(
        "a_law_of_any_type",
        "HP26 refused",
        replacing(read_module, "_extrapolation", _reshaped(_law_of_any_type)),
        ("law_not_text",),
        "^an extrapolation with its law_not_text",
    ),
    Mutant(
        "the_method_unchecked",
        "HP26 refused",
        replacing(read_module, "_extrapolation", _reshaped(_method_unchecked)),
        ("method_missing", "method_unknown"),
        "^an extrapolation with its method_(missing|unknown)",
    ),
    # `extrapolation_strategies.refused_shapes` locates the extrapolation elsewhere in half its draws:
    # "whatever field or location it names" (`read_side_contract.md` section 1).
    Mutant(
        "shape_unchecked_off_a_record",
        "HP26 refused",
        replacing(read_module, "_extrapolation", _reshaped(_shape_unchecked_off_a_record)),
        REFUSED_SHAPE_WAYS,
        "^an extrapolation with its",
    ),
    Mutant(
        "a_law_of_white_space_refused",
        "HP26 read",
        replacing(read_module, "_extrapolation", _reshaped(_white_space_refused)),
        ("law_white_space",),
        "^an extrapolation with its law_white_space",
    ),
    Mutant(
        "basis_checked",
        "HP26 read",
        replacing(read_module, "_extrapolation", _reshaped(_basis_checked)),
        READ_SHAPE_WAYS[:3],
        "^an extrapolation with its (law_white_space|basis_and_reason_any|an_unknown_member) read as",
    ),
    Mutant(
        "a_slip_ignored",
        "HP26 read",
        replacing(read_module, "_extrapolation", _reshaped(_a_slip_ignored)),
        ("a_slip_of_a_member",),
        "^an extrapolation holding a slip",
    ),
    Mutant(
        "an_unknown_member_refused",
        "HP26 read",
        replacing(read_module, "_extrapolation", _reshaped(_an_unknown_member_refused)),
        ("an_unknown_member",),
        "^an extrapolation with its an_unknown_member read as",
    ),
    # The monotonicity property's (the S3 design's section 6.7 of v1: "status set to `met`").
    Mutant(
        "monotone_status_met",
        "monotonicity",
        replacing(read_module, "read_value_field", _status_met),
        ("one_double_outside", "far_outside"),
        "^an extrapolation turned a read not_met",
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_extrapolation_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the ways it names, and at the assertion it names."""
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
