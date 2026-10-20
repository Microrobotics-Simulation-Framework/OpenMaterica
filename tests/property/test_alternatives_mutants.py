# SPDX-License-Identifier: Apache-2.0
"""Mutants of S4a's step 7 (`core/read.py`'s `_read_alternatives` and the rules it calls), each with one
fault, and the property of `test_alternatives_properties.py` that must kill each one. As in
`test_result_mutants.py`, each must die within the examples the `ci` profile gives a property, at both sizes,
at an example of an outcome it names, and records the examples its kill took as `examples_to_kill`.

A fault is injected where the core looks a name up when it runs: a module-level function of `read`.
"""

import dataclasses
import re
from collections.abc import Callable, Collection, Sequence
from typing import Any, NamedTuple

import pytest
from hypothesis import strategies as st

from materica.core import read
from materica.core.fields import RecordField
from materica.core.jsonio import JsonValue
from materica.core.read import FieldRead, Nominal, ReadRequest, ReadResult
from materica.core.reasons import Reason, merged, tagged
from materica.core.value_shapes import JsonObject, a_list, an_object
from materica.shapes import Suite, Want
from tests.property import alternatives_strategies as strategies
from tests.property import test_alternatives_properties as properties
from tests.property.alternatives_strategies import OUTCOMES, Alternatives
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.test_condition_mutants import kill
from tests.property.test_mutants import setting

# Each property that kills a mutant, by name: its examples at a size and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Any]], Callable[[Any], None]]] = {
    "HP27": (lambda size: strategies.alternatives(size), properties.check_outcome),
    # Planned searches of HP27, each where its mutant's fault shows, which HP27's own draws meet too seldom
    # for a safe margin (2026-10-19, at `ci`: 628 and 565 examples, 656 and a survivor, 1,990 and a
    # survivor, and under a nominal alone 15 and 739): a refusal by a fault of the request; an interval
    # under a nominal; intervals that stay under one beside an alternative set aside, stored first; and
    # evidence whose first alternative an implied condition sets aside.
    "HP27 with a request fault": (
        lambda size: strategies.alternatives(size, ("refused",), refusing_ways=("request_fault",)),
        properties.check_outcome,
    ),
    "HP27 under a nominal": (
        lambda size: strategies.alternatives(
            size, ("refused", "one_left", "no_pick"), forms=("interval",), under_a_nominal=True
        ),
        properties.check_outcome,
    ),
    "HP27 under a nominal, set aside first": (
        lambda size: strategies.alternatives(
            size, ("no_pick",), forms=("interval",), under_a_nominal=True, set_aside_first=True
        ),
        properties.check_outcome,
    ),
    "HP27 over evidence set aside first": (
        lambda size: strategies.alternatives(size, ("no_pick",), forms=("evidence",), set_aside_first=True),
        properties.check_outcome,
    ),
    # And, planned since the move onto main, evidence under `no_pick`: the units the entries give differ among
    # the alternatives that stay only where the form is evidence (a status object with another `reason`).
    "HP27 over evidence under no_pick": (
        lambda size: strategies.alternatives(size, ("no_pick",), forms=("evidence",)),
        properties.check_outcome,
    ),
    "HP28 order": (properties.reordered, properties.check_reordered),
    "HP28 wrapping": (properties.wrapped, properties.check_wrapped),
    "HP29 set aside": (
        lambda size: strategies.alternatives(size, added=True),
        properties.check_set_aside_added,
    ),
    "HP29 two staying": (
        lambda size: strategies.alternatives(size, ("want_mismatch", "no_pick")),
        properties.check_two_staying,
    ),
}


def outcome(example: Alternatives | tuple[Alternatives, Any]) -> str:
    drawn = example if isinstance(example, Alternatives) else example[0]
    return drawn.outcome


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # outcomes, one of which the example that kills it must show
    says: str  # a pattern the message of the assertion that kills it must match: what the fault changes


# The functions the faults wrap, taken before any replaces them.
READ_ALTERNATIVES = read._read_alternatives  # pyright: ignore[reportPrivateUsage]
STANDING = read._standing  # pyright: ignore[reportPrivateUsage]
FOUND_READING = read._found_reading  # pyright: ignore[reportPrivateUsage]
RESTING_ON = read._resting_on  # pyright: ignore[reportPrivateUsage]
STATUS = read._status  # pyright: ignore[reportPrivateUsage]
GIVES = read._gives  # pyright: ignore[reportPrivateUsage]


def _refusal_sets_aside(found: FieldRead) -> str:
    standing = STANDING(found)
    return "set_aside" if standing == "refuses" and not found.request_fault else standing


def _cannot_give_sets_aside(found: FieldRead) -> str:
    standing = STANDING(found)
    return "set_aside" if standing == "stays" and found.want_mismatch is not None else standing


def _request_fault_sets_aside(found: FieldRead) -> str:
    return "set_aside" if found.request_fault else STANDING(found)


def _set_aside_refuses(found: FieldRead) -> str:
    return "refuses" if found.conditions_not_met else STANDING(found)


def _read_alone(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    nominal: Nominal | None,
) -> list[FieldRead]:
    """Each alternative of `field` read alone, as step 7 reads it, with its stored index."""
    return [
        dataclasses.replace(
            read.read_value_field(
                RecordField(field.spec, alternative, field.section), record, request, claims, nominal
            ),
            alternative=index,
        )
        for index, alternative in enumerate(a_list(an_object(field.value)["alternatives"]))
    ]


def _set_aside_beside_the_one_left(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """The set-aside alternatives' reasons reported beside the one left."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if result.conditions is None or result.alternative_values is not None:
        return result
    aside = [
        reason
        for found in _read_alone(field, record, request, claims, nominal)
        if STANDING(found) == "set_aside"
        for reason in FOUND_READING(found)
    ]
    reasons = merged((*result.reasons, *aside))
    return dataclasses.replace(result, status=STATUS(reasons), reasons=reasons)


def _the_one_left_untagged(left: FieldRead) -> tuple[Reason, ...]:
    return left.found


def _every_reason_beside_two_or_more(staying: Sequence[FieldRead]) -> tuple[Reason, ...]:
    return tuple(reason for found in staying for reason in FOUND_READING(found))


def _no_reason_beside_two_or_more(staying: Sequence[FieldRead]) -> tuple[Reason, ...]:
    return ()


def _set_aside_dropped_where_refused(reads: Sequence[FieldRead]) -> tuple[Reason, ...]:
    return tuple(
        reason for found in reads if STANDING(found) != "set_aside" for reason in FOUND_READING(found)
    )


def _waiting_dropped_where_refused(reads: Sequence[FieldRead]) -> tuple[Reason, ...]:
    return tuple(
        reason for found in reads for reason in FOUND_READING(dataclasses.replace(found, want_mismatch=None))
    )


def _read_up_to_the_first_refusal(reads: Sequence[FieldRead]) -> tuple[Reason, ...]:
    """The outcome decided in reading order: the reading stops at the first alternative that refuses."""
    standings = [STANDING(found) for found in reads]
    last = standings.index("refuses") + 1 if "refuses" in standings else len(reads)
    return tuple(reason for found in reads[:last] for reason in FOUND_READING(found))


def _request_fault_tagged(found: FieldRead) -> tuple[Reason, ...]:
    assert found.alternative is not None
    return tagged(found.found, found.alternative)


def _index_among_those_that_stay(*arguments: Any) -> ReadResult:
    """Each index counted among the alternatives that stay, in the entries and the reasons of a result that
    rests on them: under `no_pick` and `want_mismatch` the stayers' own, and the one left's."""
    result: ReadResult = READ_ALTERNATIVES(*arguments)
    staying = [entry.alternative for entry in result.alternative_values or ()]
    indexes = sorted({reason.alternative for reason in result.reasons if reason.alternative is not None})
    if not staying and (result.conditions is None or len(indexes) != 1):
        return result
    rank = {index: number for number, index in enumerate(staying or indexes)}

    def ranked(reason: Reason) -> Reason:
        if reason.alternative is None:
            return reason
        return dataclasses.replace(reason, alternative=rank.get(reason.alternative, reason.alternative))

    entries = tuple(
        dataclasses.replace(entry, alternative=rank[entry.alternative])
        for entry in result.alternative_values or ()
        if entry.alternative is not None
    )
    return dataclasses.replace(
        result,
        reasons=tuple(map(ranked, result.reasons)),
        alternative_values=entries or result.alternative_values,
    )


def _gives_by_the_first_stored_form(
    found: FieldRead, stored: list[JsonValue], want: Want, nominal: Nominal | None
) -> bool:
    """Whether `want` can give a staying alternative, an interval under a nominal judged by the first stored
    alternative's form, not its own."""
    return GIVES(dataclasses.replace(found, alternative=0), stored, want, nominal)


def _nominal_dropped_over_alternatives(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    return READ_ALTERNATIVES(field, record, request, claims, labels, None)


def _the_last_staying_unit(*arguments: Any) -> ReadResult:
    result: ReadResult = READ_ALTERNATIVES(*arguments)
    if not result.alternative_values:
        return result
    last = result.alternative_values[-1].unit
    entries = tuple(dataclasses.replace(entry, unit=last) for entry in result.alternative_values)
    return dataclasses.replace(result, alternative_values=entries)


def _the_first_stored_unit(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """Under `no_pick`, every entry's unit the first stored alternative's, set aside or not."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if not result.alternative_values:
        return result
    first = an_object(a_list(an_object(field.value)["alternatives"])[0])["unit"]
    entries = tuple(dataclasses.replace(entry, unit=first) for entry in result.alternative_values)
    return dataclasses.replace(result, alternative_values=entries)


def _labels_kept_where_refused(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if result.value is not None or result.alternative_values is not None or result.conditions is not None:
        return result
    alternatives = a_list(an_object(field.value).get("alternatives", []))
    found = [
        label
        for alternative in alternatives
        if isinstance(alternative, dict)
        for label in read.read_value_field(
            RecordField(field.spec, alternative, field.section), record, request, claims, nominal
        ).labels
    ]
    return dataclasses.replace(result, labels=tuple(dict.fromkeys((*result.labels, *found))))


def _the_first_staying_read(
    field: RecordField,
    record: JsonObject,
    request: ReadRequest,
    claims: Collection[Suite],
    labels: tuple[str, ...],
    nominal: Nominal | None,
) -> ReadResult:
    """With several alternatives left, the first is read (the fail-closed spike's `first_alternative`)."""
    result = READ_ALTERNATIVES(field, record, request, claims, labels, nominal)
    if not result.alternative_values:
        return result
    first = result.alternative_values[0]
    return RESTING_ON(first, FOUND_READING(first), labels)


NOT_SET_ASIDE = tuple(outcome for outcome in OUTCOMES if outcome != "all_set_aside")
TWO_OR_MORE = ("want_mismatch", "no_pick")

MUTANTS: list[Mutant] = [
    Mutant(
        "refusal_sets_aside",
        "HP27",
        setting(read, "_standing", _refusal_sets_aside),
        ("refused",),
        "^(status|reasons)",
    ),
    Mutant(
        "cannot_give_sets_aside",
        "HP27",
        setting(read, "_standing", _cannot_give_sets_aside),
        NOT_SET_ASIDE,
        "^(status|reasons|members)",
    ),
    Mutant(
        "request_fault_sets_aside",
        "HP27 with a request fault",
        setting(read, "_standing", _request_fault_sets_aside),
        ("refused",),
        "^(status|reasons)",
    ),
    Mutant(
        "set_aside_reasons_beside_the_one_left",
        "HP27",
        setting(read, "_read_alternatives", _set_aside_beside_the_one_left),
        ("one_left",),
        "^(status|reasons)",
    ),
    Mutant(
        "waiting_reasons_beside_two_or_more",
        "HP27",
        setting(read, "_reported_beside_two_or_more", _every_reason_beside_two_or_more),
        TWO_OR_MORE,
        "^(status|reasons)",
    ),
    Mutant(
        "unknown_reasons_dropped_beside_two_or_more",
        "HP27",
        setting(read, "_reported_beside_two_or_more", _no_reason_beside_two_or_more),
        TWO_OR_MORE,
        "^reasons",
    ),
    Mutant(
        "set_aside_reasons_dropped_where_refused",
        "HP27",
        setting(read, "_reported_where_refused", _set_aside_dropped_where_refused),
        ("refused", "all_set_aside"),
        "^(status|reasons)",
    ),
    Mutant(
        "waiting_reasons_dropped_where_refused",
        "HP27",
        setting(read, "_reported_where_refused", _waiting_dropped_where_refused),
        ("refused",),
        "^reasons",
    ),
    Mutant(
        "index_among_those_that_stay",
        "HP27",
        setting(read, "_read_alternatives", _index_among_those_that_stay),
        ("one_left", "no_pick"),
        "^(reasons|alternative_values)",
    ),
    Mutant(
        "request_fault_tagged",
        "HP27",
        setting(read, "_found_reading", _request_fault_tagged),
        ("refused",),
        "^reasons",
    ),
    Mutant(
        "gives_reads_the_first_stored_form",
        "HP27 under a nominal, set aside first",
        setting(read, "_gives", _gives_by_the_first_stored_form),
        ("no_pick",),
        "^status",
    ),
    Mutant(
        "nominal_dropped_over_alternatives",
        "HP27 under a nominal",
        setting(read, "_read_alternatives", _nominal_dropped_over_alternatives),
        ("refused", "one_left"),
        "^(status|reasons|members)",
    ),
    Mutant(
        "the_last_staying_unit",
        "HP27 over evidence under no_pick",
        setting(read, "_read_alternatives", _the_last_staying_unit),
        ("no_pick",),
        "^alternative_values",
    ),
    Mutant(
        "the_first_stored_unit",
        "HP27 over evidence set aside first",
        setting(read, "_read_alternatives", _the_first_stored_unit),
        ("no_pick",),
        "^alternative_values",
    ),
    Mutant(
        "labels_kept_where_refused",
        "HP27",
        setting(read, "_read_alternatives", _labels_kept_where_refused),
        ("refused", "want_mismatch"),
        "^labels",
    ),
    Mutant(
        "outcome_decided_in_reading_order",
        "HP28 order",
        setting(read, "_reported_where_refused", _read_up_to_the_first_refusal),
        ("refused",),
        "^reasons, reordered",
    ),
    Mutant(
        "the_one_left_untagged",
        "HP28 wrapping",
        setting(read, "_reported_of_the_one_left", _the_one_left_untagged),
        OUTCOMES,
        "^reasons",
    ),
    Mutant(
        "set_aside_refuses",
        "HP29 set aside",
        setting(read, "_standing", _set_aside_refuses),
        NOT_SET_ASIDE,
        "^(status|its reasons|reasons and members)",
    ),
    Mutant(
        "the_first_staying_read",
        "HP29 two staying",
        setting(read, "_read_alternatives", _the_first_staying_read),
        ("no_pick",),
        "two or more alternatives that stay give met",
    ),
]


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_alternatives_mutant_is_killed(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """At an example of one of the outcomes it names, and at the assertion it names."""
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    said: list[str] = []

    def checked(example: Any) -> None:
        try:
            check(example)
        except AssertionError as error:
            said.append(str(error))
            raise

    tried, example = kill(examples(size), checked)
    record_property("examples_to_kill", tried)
    assert outcome(example) in mutant.dies_at, outcome(example)
    assert re.search(mutant.says, said[0]), said[0]
