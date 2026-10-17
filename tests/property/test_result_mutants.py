# SPDX-License-Identifier: Apache-2.0
"""Mutants of the result (`core/read.py`'s steps 11 to 13, step 7 under decision 12 and the result's members,
and `core/conditions.py` where its reasons carry their condition), each with one fault, and the property of
`test_result_properties.py` that must kill each one. As in `test_condition_mutants.py`, each must die within
the examples the `ci` profile gives a property, at both sizes, at an example of a kind it names, and records
the examples its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function or name of `read`
or `conditions`.
"""

import dataclasses
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
from materica.core.status import ReadStatus
from materica.core.value_shapes import JsonObject
from materica.shapes import Suite, Want
from tests.property import test_result_properties as properties
from tests.property.result_strategies import KINDS, REVIEWS, Drawn, drawn_reads, valued_reads
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting


def kind(drawn: Drawn) -> set[str]:
    return {drawn.kind, *drawn.features}


# Each property that kills a mutant, by name: its examples at a size and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None]]] = {
    "HP1": (drawn_reads, properties.check_totality),
    "HP2": (drawn_reads, properties.check_status_law),
    "HP6": (valued_reads, properties.check_returned_as_stored),
    "HP11": (drawn_reads, properties.check_claims),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # kinds or features, one of which the example that kills it must show


def injecting(*settings: Callable[[pytest.MonkeyPatch], None]) -> Callable[[pytest.MonkeyPatch], None]:
    def inject(monkeypatch: pytest.MonkeyPatch) -> None:
        for each in settings:
            each(monkeypatch)

    return inject


# The functions the faults wrap, taken before any replaces them.
COMPARED = conditions._compared  # pyright: ignore[reportPrivateUsage]
ORIGIN = read._origin  # pyright: ignore[reportPrivateUsage]
BY_WANT = read._by_want  # pyright: ignore[reportPrivateUsage]
ENDS = read._ends  # pyright: ignore[reportPrivateUsage]
STATUS = read._status  # pyright: ignore[reportPrivateUsage]
READ_ALTERNATIVES = read._read_alternatives  # pyright: ignore[reportPrivateUsage]
COUNTED = read._counted  # pyright: ignore[reportPrivateUsage]
RETURNED = read._returned  # pyright: ignore[reportPrivateUsage]
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


def _a_code_outside_the_table(field: JsonObject, name: str, want: Want) -> tuple[JsonValue, Reason | None]:
    value, mismatch = BY_WANT(field, name, want)
    return value, None if mismatch is None else Reason("want_unmet")  # type: ignore[arg-type]


def _unmerged(reasons: Collection[Reason]) -> tuple[Reason, ...]:
    return tuple(reasons)


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


def _negative_zero_as_zero(field: JsonObject, name: str, want: Want) -> tuple[JsonValue, Reason | None]:
    value, mismatch = BY_WANT(field, name, want)
    return (0.0 if value == 0.0 else value), mismatch


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


MUTANTS = [
    Mutant(
        "condition_unchecked_without_its_condition",
        "HP1",
        setting(conditions, "_compared", _unchecked_without_its_condition),
        ("step_9_or_10_fault", "unknown_at_step_10"),
    ),
    Mutant(
        "stated_without_origin_with_a_condition",
        "HP1",
        setting(read, "_origin", _origin_with_a_condition),
        ("met", "step_9_or_10_fault", "unknown_at_step_10"),
    ),
    Mutant("a_code_outside_the_table", "HP1", setting(read, "_by_want", _a_code_outside_the_table), ("met",)),
    Mutant("reasons_not_merged", "HP1", setting(read, "merged", _unmerged), ("step_8_fault",)),
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
        "negative_zero_as_zero", "HP6", setting(read, "_by_want", _negative_zero_as_zero), ("negative_zero",)
    ),
    Mutant(
        "unknown_members_returned", "HP6", setting(read, "_members", _every_member_kept), ("unknown_member",)
    ),
    # A review returned as the record holds it is caught as another review, or as the record's own object.
    Mutant("review_as_it_holds", "HP6", setting(read, "_review", _review_as_it_holds), REVIEWS),
    Mutant("counts_as_doubles", "HP6", setting(read, "_whole", _as_stored), ("met", "alternatives")),
    # The fault fuzz target 4 found against the reference model: a constant's statistics read by the block's
    # shape alone, so that the status object its row allows comes back empty.
    Mutant(
        "statistics_status_object_emptied",
        "HP6",
        setting(read, "_CONSTANT_STATISTICS", shapes.StatisticsBlock),
        ("statistics_withheld",),
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
            "step_8_fault",
            "step_9_or_10_fault",
            "unknown_at_step_10",
            "step_5",
            "step_7",
            "alternatives",
            "alternatives_broken",
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
    """At an example of one of the kinds or features it names."""
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    tried, example = kill(examples(size), check)
    record_property("examples_to_kill", tried)
    assert kind(example) & set(mutant.dies_at), kind(example)
