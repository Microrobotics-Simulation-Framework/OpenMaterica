# SPDX-License-Identifier: Apache-2.0
"""Mutants of the result (`core/read.py`'s steps 11 to 13, step 7 under decision 12 and the result's members,
and `core/conditions.py` where its reasons carry their condition), each with one fault, and the property of
`test_result_properties.py` that must kill each one. As in `test_condition_mutants.py`, each must die within
the examples the `ci` profile gives a property, at both sizes, at an example of a kind it names, and records
the examples its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function or name of `read`
or `conditions`.
"""

import copy
import dataclasses
import math
import re
import struct
import types
from collections.abc import Callable, Collection
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica import shapes
from materica.core import conditions, read, resolve
from materica.core.jsonio import JsonValue
from materica.core.read import FieldRead, ReadResult
from materica.core.reasons import Reason
from materica.core.resolve import Refused
from materica.core.status import ReadStatus, worst
from materica.core.value_shapes import JsonObject
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite, Want
from tests.property import test_result_properties as properties
from tests.property.result_strategies import (
    KINDS,
    REVIEWS,
    Drawn,
    drawn_reads,
    nominal_reads,
    unknown_at_step_10,
    valued_reads,
)
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting


def kind(drawn: Drawn) -> set[str]:
    return {drawn.kind, *drawn.features}


# Each property that kills a mutant, by name: its examples at a size and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None]]] = {
    "HP1": (drawn_reads, properties.check_totality),
    # A planned search of HP1: the reads of its `unknown_at_step_10` kind whose fault is a condition the
    # request gives no tolerance for, which step 10 gives as `condition_unchecked`.
    "HP1, an unchecked condition": (
        lambda size: unknown_at_step_10(size, ("unchecked",)),
        properties.check_totality,
    ),
    "HP2": (drawn_reads, properties.check_status_law),
    # A planned search of HP2: the reads under a nominal alone, whose mutants HP2's eleven kinds meet too
    # seldom for a safe margin (over twelve random seeds, one survived 2,000 examples).
    "HP2 under a nominal": (lambda size: drawn_reads(size, ("nominal",)), properties.check_status_law),
    "HP6": (valued_reads, properties.check_returned_as_stored),
    "HP6_nominal": (nominal_reads, properties.check_nominal_supplied),
    "HP11": (drawn_reads, properties.check_claims),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # kinds or features, one of which the example that kills it must show
    says: str = ""  # a pattern the message of the assertion that kills it must hold, where one is given


def injecting(*settings: Callable[[pytest.MonkeyPatch], None]) -> Callable[[pytest.MonkeyPatch], None]:
    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        for each in settings:
            each(monkeypatch)

    return inject


# The functions the faults wrap, taken before any replaces them.
COMPARED = conditions._compared  # pyright: ignore[reportPrivateUsage]
ORIGIN = read._origin  # pyright: ignore[reportPrivateUsage]
BY_WANT = read._by_want  # pyright: ignore[reportPrivateUsage]
COUNTED_MEMBER = read._counted_member  # pyright: ignore[reportPrivateUsage]
READ_VALUE_FIELD = read.read_value_field
FIELD_HINTS = read._FIELD_HINTS  # pyright: ignore[reportPrivateUsage]
ENDS = read._ends  # pyright: ignore[reportPrivateUsage]
STATUS = read._status  # pyright: ignore[reportPrivateUsage]
READ_ALTERNATIVES = read._read_alternatives  # pyright: ignore[reportPrivateUsage]
COUNTED = read._counted  # pyright: ignore[reportPrivateUsage]
RETURNED = read._returned  # pyright: ignore[reportPrivateUsage]
NOMINAL_READ = read._nominal_read  # pyright: ignore[reportPrivateUsage]
VALUE = read._value  # pyright: ignore[reportPrivateUsage]
RESOLVE = resolve.resolve_record


# HP1: the reason table.


def _unchecked_without_its_condition(
    name: str, condition: JsonObject, operating: Any, required: Any
) -> Reason | None:
    found = COMPARED(name, condition, operating, required)
    return (
        Reason("condition_unchecked") if found is not None and found.code == "condition_unchecked" else found
    )


def _origin_with_a_condition(provenance: JsonObject, name: str) -> list[Reason]:
    return [Reason(reason.code, "temperature", reason.detail) for reason in ORIGIN(provenance, name)]


def _status_of_any_code(reasons: Collection[Reason]) -> ReadStatus:
    """A status for a code the table does not hold too, `not_met`, so that the code reaches the result and the
    reason table's assertion, not the read's own look-up, finds it."""
    return worst(
        VOCABULARY.reasons[reason.code].status if reason.code in VOCABULARY.reasons else "not_met"
        for reason in reasons
    )


def _a_code_outside_the_table(field: JsonObject, name: str, form: str, want: Want) -> Reason | None:
    mismatch = BY_WANT(field, name, form, want)
    return None if mismatch is None else Reason("want_unmet")  # type: ignore[arg-type]


def _unmerged(reasons: Collection[Reason]) -> tuple[Reason, ...]:
    return tuple(reasons)


def _a_forms_mismatch_outside_the_table(field: JsonObject, name: str, form: str, want: Want) -> Reason | None:
    mismatch = BY_WANT(field, name, form, want)
    return Reason("form_unmet") if mismatch is not None and form != "constant" else mismatch  # type: ignore[arg-type]


# HP2: the status law and the members present.


def _conditions_never_end(found: list[Reason]) -> bool:
    return ENDS([reason for reason in found if not reason.code.startswith("condition_")])


def _value_whatever_the_status(status: ReadStatus, found: FieldRead) -> bool:
    return found.value is not None


def _best_status(reasons: Collection[Reason]) -> ReadStatus:
    order: tuple[ReadStatus, ...] = ("not_met", "unknown", "met")
    return order[max((order.index(STATUS((reason,))) for reason in reasons), default=2)]


def _conditions_beside_no_pick(*arguments: Any) -> ReadResult:
    result: ReadResult = READ_ALTERNATIVES(*arguments)
    if result.alternative_values is None:
        return result
    return dataclasses.replace(result, conditions=result.alternative_values[0].conditions)


def _no_unit_beside_alternative_values(*arguments: Any) -> ReadResult:
    result: ReadResult = READ_ALTERNATIVES(*arguments)
    return dataclasses.replace(result, unit=None)


def _no_statistics_beside_a_composition(*arguments: Any) -> FieldRead:
    """A composition's spread read as its components' alone, so the field's block is not returned."""
    found: FieldRead = READ_VALUE_FIELD(*arguments)
    if isinstance(found.member, dict) and "components" in found.member:
        return dataclasses.replace(found, statistics=None)
    return found


def _a_nominal_inside_wherever_it_lies(
    interval: JsonObject, name: str, nominal: read.Nominal
) -> tuple[Reason, read.Nominal | None]:
    return Reason("want_mismatch"), nominal


def _nominal_invalid_as_want_mismatch(
    interval: JsonObject, name: str, nominal: read.Nominal
) -> tuple[Reason, read.Nominal | None]:
    found, supplied = NOMINAL_READ(interval, name, nominal)
    return (found if supplied is not None else Reason("want_mismatch")), supplied


def _located_by_its_field(named: str, location: JsonObject, field: str, record: Any) -> bool:
    return named == field


def _applied_wherever_a_nominal_applies(*arguments: Any) -> FieldRead:
    """`applied` naming the nominal that applies to the read whether or not it supplied the value."""
    found: FieldRead = READ_VALUE_FIELD(*arguments)
    nominal = arguments[4] if len(arguments) > 4 else None
    if nominal is None or nominal.index in found.applied:
        return found
    return dataclasses.replace(found, applied=tuple(sorted((*found.applied, nominal.index))))


def _value_unless_not_met(status: ReadStatus, found: FieldRead) -> bool:
    """Section 2 item 3 without its exception: no value under `not_met`, a nominal's included."""
    return found.value is not None and status != "not_met"


# HP6: returned as stored.


def _expanded_uncertainty_divided_by_its_k(statistics: JsonObject) -> JsonObject:
    block = COUNTED(statistics)
    expanded = block.get("expanded_uncertainty")
    if isinstance(expanded, dict):
        value, factor = expanded.get("value"), expanded.get("coverage_factor")
        if isinstance(value, float) and isinstance(factor, float) and factor:
            expanded["value"] = value / factor
    return block


def _shared_where_nothing_is_left_out(value: JsonValue, shape: object) -> JsonValue:
    returned = RETURNED(value, shape)
    return value if returned == value else returned


def _negative_zero_as_zero(member: JsonValue) -> JsonValue:
    returned = COUNTED_MEMBER(member)
    return 0.0 if returned == 0.0 else returned


def _upper_none_as_infinity(member: JsonValue) -> JsonValue:
    """The S2 design's HP6 mutant: an interval's `upper: none` read as infinity."""
    returned = COUNTED_MEMBER(member)
    upper = returned.get("upper") if isinstance(returned, dict) else None
    if isinstance(returned, dict) and isinstance(upper, dict) and upper.get("status") == "none":
        returned["upper"] = math.inf
    return returned


def _bounds_without_their_basis(member: JsonValue) -> JsonValue:
    returned = COUNTED_MEMBER(member)
    if isinstance(returned, dict) and "lower" in returned:
        returned.pop("basis", None)
    return returned


def _components_normalised(member: JsonValue) -> JsonValue:
    """Fractions scaled to sum to one, the stated sum dropped (`record_format.md` section 6, composition item
    2: nothing is normalised)."""
    returned = COUNTED_MEMBER(member)
    if not (isinstance(returned, dict) and isinstance(components := returned.get("components"), list)):
        return returned
    fractions = [component.get("fraction") for component in components if isinstance(component, dict)]
    total = math.fsum(fraction for fraction in fractions if isinstance(fraction, float))
    for component in components:
        if isinstance(component, dict) and isinstance(fraction := component.get("fraction"), float) and total:
            component["fraction"] = fraction / total
    returned.pop("stated_sum", None)
    return returned


def _components_copied_as_stored(member: JsonValue) -> JsonValue:
    """A form's member returned without rule 5's integers in a component's statistics block."""
    return copy.deepcopy(member)


def _every_member_kept(shape: object, *, status: bool) -> None:
    return None


def _review_as_it_holds(review: JsonValue) -> JsonObject:
    return review if isinstance(review, dict) else {"status": "not_checked"}


def _as_stored(number: JsonValue) -> JsonValue:
    return number


def _shared(value: object) -> object:
    return value


SHALLOW = types.SimpleNamespace(deepcopy=_shared)


# HP11: claims.


def _a_reports_review_as_it_holds(value: JsonValue, shape: object) -> JsonValue:
    returned = RETURNED(value, shape)
    if shape is shapes.Provenance and isinstance(value, dict) and isinstance(returned, dict):
        returned["review"] = copy.deepcopy(value.get("review"))
    return returned


def _a_reports_provenance_cut_to_a_results(value: JsonValue, shape: object) -> JsonValue:
    returned = RETURNED(value, shape)
    if shape is shapes.Provenance and isinstance(returned, dict):
        return {name: member for name, member in returned.items() if name in ("origin", "review")}
    return returned


def _reports_returned_whole(value: JsonValue, shape: object) -> JsonValue:
    """Evidence's list copied as the record holds it, a member the reader does not know in a report kept."""
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, dict) and "provenance" in item for item in value)
    ):
        return copy.deepcopy(value)
    return RETURNED(value, shape)


def _a_nominal_as_a_single(
    member: JsonValue, mismatch: Reason | None, supplied: read.Nominal | None
) -> JsonValue:
    """A nominal's value rounded to single precision, as a `float` attribute would hold it."""
    found = VALUE(member, mismatch, supplied)
    return struct.unpack(">f", struct.pack(">f", found))[0] if supplied is not None else found


def _assumption_without_its_kind(self: read.Nominal) -> JsonObject:
    return {"value": self.value}


def _applied_without_the_nominal(*arguments: Any) -> FieldRead:
    found: FieldRead = READ_VALUE_FIELD(*arguments)
    nominal = arguments[4] if len(arguments) > 4 else None
    return (
        found
        if nominal is None
        else dataclasses.replace(
            found, applied=tuple(index for index in found.applied if index != nominal.index)
        )
    )


def _labelled_before_step_4(reference: Any, store: Any, claims: Collection[Suite]) -> Any:
    resolved = RESOLVE(reference, store, claims)
    if isinstance(resolved, Refused) and "hash" not in claims:
        return dataclasses.replace(resolved, labels=("hash_not_checked",))
    return resolved


def _labelled_beside_the_hash_suite(reference: Any, store: Any, claims: Collection[Suite]) -> Any:
    resolved = RESOLVE(reference, store, claims)
    if not isinstance(resolved, Refused) and "hash_not_checked" not in resolved.labels:
        return dataclasses.replace(resolved, labels=(*resolved.labels, "hash_not_checked"))
    return resolved


# HP1's reason-table assertion, which a code outside the table must reach (PR #37's review, L1).
OUTSIDE_THE_TABLE = r"is no code of the table"

MUTANTS = [
    # `condition` is on "every `condition_*` reason" (`read_side_contract.md` section 2 item 2), whatever
    # the read's kind: a fault of step 8's catalogue that step 8 passes (an unknown condition name) reaches
    # step 10, where a condition the record states and the request gives no tolerance or accept list for
    # gives `condition_unchecked`, so HP1 whole killed this at a step 8 fault as well. Over 24 seeds it
    # took up to 1,064 examples that way (2026-10-19), so its search is planned.
    Mutant(
        "condition_unchecked_without_its_condition",
        "HP1, an unchecked condition",
        setting(conditions, "_compared", _unchecked_without_its_condition),
        ("unknown_at_step_10",),
    ),
    Mutant(
        "stated_without_origin_with_a_condition",
        "HP1",
        setting(read, "_origin", _origin_with_a_condition),
        ("met", "met_own_member", "nominal", "step_9_or_10_fault", "unknown_at_step_10"),
    ),
    # Step 13 gives an interval or a composition read under `value` "`not_met` (`want_mismatch`)"
    # (`read_side_contract.md` section 6), whatever the read's kind: a fault of step 8's catalogue that step 8
    # passes ("a provenance member a read does not check, broken or `null` (`"extraction": null`), does not
    # refuse the field", `provenance.md`'s PR-109) leaves a step 8 fault's read of either form, which is read
    # under `value`, to reach it where steps 9 and 10 do not end the read, so this dies at a step 8 fault as
    # well. And "An acceptance applies only to a read of the field it names and, an overlay aside (it names no
    # location), only at the read's own location" (section 1): an interval read under `value` beside a nominal
    # for another field, beside a region or with no location is read as without it, and reaches the same
    # `want_mismatch`, so this dies at a nominal located elsewhere as well.
    Mutant(
        "a_code_outside_the_table",
        "HP1",
        injecting(
            setting(read, "_by_want", _a_code_outside_the_table),
            setting(read, "_status", _status_of_any_code),
        ),
        ("met", "step_8_fault", "nominal_elsewhere"),
        OUTSIDE_THE_TABLE,
    ),
    # A reason "appears at most once in a result" (section 2 item 2), at any step: step 9's faults of the
    # field's unit and of a fact's each give `unit_mismatch` with no condition, one reason found twice, so
    # this dies at a fault of steps 9 and 10 as well.
    Mutant(
        "reasons_not_merged",
        "HP1",
        setting(read, "merged", _unmerged),
        ("step_8_fault", "step_9_or_10_fault"),
    ),
    # A step 8 fault's read of an interval or a composition reaches step 13's `want_mismatch` as for
    # `a_code_outside_the_table` (above), so this dies at a step 8 fault as well.
    Mutant(
        "a_forms_mismatch_outside_the_table",
        "HP1",
        injecting(
            setting(read, "_by_want", _a_forms_mismatch_outside_the_table),
            setting(read, "_status", _status_of_any_code),
        ),
        ("form_interval", "form_composition", "form_evidence", "step_8_fault"),
        OUTSIDE_THE_TABLE,
    ),
    Mutant(
        "value_beside_condition_outside",
        "HP2",
        injecting(
            setting(read, "_ends", _conditions_never_end),
            setting(read, "_value_returned", _value_whatever_the_status),
        ),
        ("step_9_or_10_fault", "unknown_at_step_10"),
    ),
    Mutant("best_status", "HP2", setting(read, "_status", _best_status), KINDS),
    Mutant(
        "conditions_beside_no_pick",
        "HP2",
        setting(read, "_read_alternatives", _conditions_beside_no_pick),
        ("alternatives",),
    ),
    Mutant(
        "no_unit_beside_alternative_values",
        "HP2",
        setting(read, "_read_alternatives", _no_unit_beside_alternative_values),
        ("alternatives",),
    ),
    Mutant(
        "no_statistics_beside_a_composition",
        "HP2",
        setting(read, "read_value_field", _no_statistics_beside_a_composition),
        ("form_composition",),
    ),
    # S2b-2's: a nominal (`read_side_contract.md` sections 1, 2 and 6).
    Mutant(
        "a_nominal_applied_outside_its_bounds",
        "HP2 under a nominal",
        setting(read, "_nominal_read", _a_nominal_inside_wherever_it_lies),
        ("nominal_outside",),
    ),
    Mutant(
        "nominal_invalid_as_want_mismatch",
        "HP2 under a nominal",
        setting(read, "_nominal_read", _nominal_invalid_as_want_mismatch),
        ("nominal_outside",),
    ),
    Mutant(
        "a_nominal_applied_wherever_it_is_located",
        "HP2 under a nominal",
        setting(read, "located_at", _located_by_its_field),
        ("nominal_elsewhere",),
    ),
    Mutant(
        "applied_names_a_nominal_that_supplied_nothing",
        "HP2 under a nominal",
        setting(read, "read_value_field", _applied_wherever_a_nominal_applies),
        ("nominal_outside", "nominal_under_bounds"),
    ),
    Mutant(
        "a_nominals_value_dropped_under_not_met",
        "HP2 under a nominal",
        setting(read, "_value_returned", _value_unless_not_met),
        ("nominal_inside", "nominal_on_a_bound"),
    ),
    Mutant(
        "expanded_uncertainty_divided_by_its_k",
        "HP6",
        setting(read, "_counted", _expanded_uncertainty_divided_by_its_k),
        ("met", "alternatives"),
    ),
    Mutant(
        "results_share_the_record",
        "HP6",
        setting(read, "_returned", _shared_where_nothing_is_left_out),
        ("met", "alternatives"),
    ),
    Mutant("json_shares_the_result", "HP6", setting(read, "copy", SHALLOW), ("met", "alternatives")),
    Mutant(
        "negative_zero_as_zero",
        "HP6",
        setting(read, "_counted_member", _negative_zero_as_zero),
        ("negative_zero",),
    ),
    # Evidence's reports carry members no shape defines in their provenance's unchecked members, as drawn.
    Mutant(
        "unknown_members_returned",
        "HP6",
        setting(read, "_members", _every_member_kept),
        ("unknown_member", "form_evidence"),
    ),
    Mutant(
        "upper_none_as_infinity",
        "HP6",
        setting(read, "_counted_member", _upper_none_as_infinity),
        ("form_interval",),
    ),
    Mutant(
        "bounds_without_their_basis",
        "HP6",
        setting(read, "_counted_member", _bounds_without_their_basis),
        ("form_interval",),
    ),
    Mutant(
        "components_normalised",
        "HP6",
        setting(read, "_counted_member", _components_normalised),
        ("form_composition",),
    ),
    Mutant(
        "component_counts_as_doubles",
        "HP6",
        setting(read, "_counted_member", _components_copied_as_stored),
        ("form_composition",),
    ),
    # A review returned as the record holds it is caught as another review, or as the record's own object.
    Mutant("review_as_it_holds", "HP6", setting(read, "_review", _review_as_it_holds), REVIEWS),
    Mutant("counts_as_doubles", "HP6", setting(read, "_whole", _as_stored), ("met", "alternatives")),
    # The fault fuzz target 4 found against the reference model: a field's statistics read by the block's
    # shape alone, so that the status object its row allows comes back empty.
    Mutant(
        "statistics_status_object_emptied",
        "HP6",
        setting(
            read,
            "_FIELD_HINTS",
            {form: {**hints, "statistics": shapes.StatisticsBlock} for form, hints in FIELD_HINTS.items()},
        ),
        ("statistics_withheld",),
    ),
    # S2b-2's: evidence (`record_format.md` section 4.3 item 2) and a nominal's value and assumption.
    Mutant(
        "a_reports_review_as_it_holds",
        "HP6",
        setting(read, "_returned", _a_reports_review_as_it_holds),
        ("form_evidence",),
    ),
    Mutant(
        "a_reports_provenance_cut_to_a_results",
        "HP6",
        setting(read, "_returned", _a_reports_provenance_cut_to_a_results),
        ("form_evidence",),
    ),
    Mutant(
        "unknown_members_kept_in_a_report",
        "HP6",
        setting(read, "_returned", _reports_returned_whole),
        ("form_evidence",),
    ),
    Mutant(
        "a_nominal_as_a_single", "HP6_nominal", setting(read, "_value", _a_nominal_as_a_single), ("nominal",)
    ),
    Mutant(
        "an_assumption_without_its_kind",
        "HP6_nominal",
        setting(read.Nominal, "assumption", _assumption_without_its_kind),
        ("nominal",),
    ),
    Mutant(
        "applied_without_the_nominal",
        "HP6_nominal",
        setting(read, "read_value_field", _applied_without_the_nominal),
        ("nominal",),
    ),
    Mutant(
        "labelled_before_step_4",
        "HP11",
        setting(read, "resolve_record", _labelled_before_step_4),
        ("before_step_4",),
    ),
    Mutant(
        "labelled_beside_the_hash_suite",
        "HP11",
        setting(read, "resolve_record", _labelled_beside_the_hash_suite),
        (
            "met",
            "met_own_member",
            "step_8_fault",
            "step_9_or_10_fault",
            "unknown_at_step_10",
            "step_5",
            "step_7",
            "alternatives",
            "alternatives_broken",
            "nominal",
        ),
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_result_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the kinds or features it names, and at the assertion it names, where it names
    one."""
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    said: list[str] = []

    def checked(drawn: Drawn) -> None:
        try:
            check(drawn)
        except AssertionError as error:
            said.append(str(error))
            raise

    tried, example = kill(examples(size), checked)
    record_property("examples_to_kill", tried)
    assert kind(example) & set(mutant.dies_at), kind(example)
    assert re.search(mutant.says, said[0]), said[0]
