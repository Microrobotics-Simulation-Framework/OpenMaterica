# SPDX-License-Identifier: Apache-2.0
"""(12) The S2 design's HP12: the read agrees with the test-only reference model (`tests/reference/
read_model.py`), which is written from the text and imports nothing from `materica`, over reads drawn across
every step S2 builds (`model_strategies.py`), in five parts that run side by side.

Both are given the same sources, the same request text and the same claims. They agree where both give a
result and the two results are equal as `read_side_contract.md` section 2 compares them: the status, the
reasons as a set of their code, condition and alternative (a reason's `detail` is for people), the labels as
a set, the condition entries by name, the alternative values in order, and every other member as a JSON value,
numbers bit for bit. Where the implementation raises `NotImplementedError` for a step not built yet and the
model gives no verdict, or both refuse claims without plain read as a misuse, they agree that neither
decides. Anything else fails, but the known divergences, each listed by kind with its reason and held to
exactly what each side gives there:

- a step the implementation has not built that the model decides (`NOT_BUILT`): an overlay as the target, a
  form S2b reads, an acceptance other than an implied condition; each found by the implementation's own words
  for what it has not built, and held to what the draw holds and the model gives;
- an open point on which the two read the text differently (`OPEN_POINTS`), planted by the draw alone: there
  the model must refuse, as its fail-closed reading does, and the model given the implementation's reading (a
  seeded fault of the model that is that reading, `tests/reference/mutants.py`) must agree with the
  implementation.
"""

import json
from collections.abc import Callable, Mapping
from typing import Literal, NamedTuple

import pytest
from hypothesis import given

from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from tests.property import model_strategies as strategies
from tests.property.model_strategies import Example
from tests.property.strategies import SIZE
from tests.property.support import feature, same
from tests.reference import read_model
from tests.reference.mutants import MUTANTS
from tests.reference.strict_json import JsonObject, JsonValue, NotStrictJson, parse


class Outcome(NamedTuple):
    kind: Literal["result", "not_yet", "misuse"]
    result: JsonValue = None  # the result, compared as section 2 compares it
    why: str = ""


def compared(result: JsonObject) -> JsonObject:
    """`result` with its sets in one order: the reasons without their details, the labels, each condition
    entry by name, and within each alternative value its labels and entries."""

    def key(value: JsonValue) -> str:
        return json.dumps(value, sort_keys=True)

    def entries(value: JsonValue) -> list[JsonValue]:
        assert isinstance(value, list), value
        return sorted(value, key=lambda entry: key(entry.get("name") if isinstance(entry, dict) else entry))

    def labels(value: JsonValue) -> list[JsonValue]:
        assert isinstance(value, list), value
        return sorted(value, key=key)

    found = dict(result)
    reasons = found["reasons"]
    assert isinstance(reasons, list), reasons
    found["reasons"] = sorted(
        (
            {name: member for name, member in reason.items() if name != "detail"}
            for reason in reasons
            if isinstance(reason, dict)
        ),
        key=key,
    )
    found["labels"] = labels(found["labels"])
    if "conditions" in found:
        found["conditions"] = entries(found["conditions"])
    values = found.get("alternative_values")
    if isinstance(values, list):
        found["alternative_values"] = [
            {
                **entry,
                **({"labels": labels(entry["labels"])} if "labels" in entry else {}),
                **({"conditions": entries(entry["conditions"])} if "conditions" in entry else {}),
            }
            for entry in values
            if isinstance(entry, dict)
        ]
    return found


def implementation_outcome(example: Example) -> Outcome:
    store = RecordStore()
    for number, source in enumerate(example.sources):
        store.add(f"source_{number}", source)
    try:
        result = read(example.request, store, claims=example.claims)
    except NotImplementedError as error:
        return Outcome("not_yet", why=str(error))
    except ValueError as error:
        if "plain_read" in example.claims:
            raise AssertionError(f"the read raised {error!r}") from error
        return Outcome("misuse", why=str(error))
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error
    try:
        written = parse(json.dumps(result.to_json()).encode())
    except NotStrictJson as fault:
        raise AssertionError(f"the result is no JSON value: {fault.fault}") from fault
    assert isinstance(written, dict), written
    return Outcome("result", compared(written))


def model_outcome(example: Example) -> Outcome:
    request: JsonValue | NotStrictJson
    try:
        request = parse(example.request)
    except NotStrictJson as fault:
        request = fault
    try:
        given_ = read_model.read(request, list(example.sources), example.claims)
    except ValueError as error:
        if "plain_read" in example.claims:
            raise AssertionError(f"the model raised {error!r}") from error
        return Outcome("misuse", why=str(error))
    if isinstance(given_, read_model.NoVerdict):
        return Outcome("not_yet", why=given_.why)
    return Outcome("result", compared(given_))


def agree(implementation: Outcome, model: Outcome) -> bool:
    return implementation.kind == model.kind and (
        implementation.kind != "result" or same(implementation.result, model.result)
    )


def described(implementation: Outcome, model: Outcome) -> str:
    return f"the implementation gives {implementation}, the model {model}"


# The known divergences. A step the implementation has not built, which the model decides: each found by the
# implementation's own words for what it has not built, and held to what the draw holds and the model gives.


def request_of(example: Example) -> JsonValue:
    try:
        return parse(example.request)
    except NotStrictJson:
        return None


def targets(example: Example) -> list[JsonObject]:
    """The records among the sources that the request's pin names."""
    request = request_of(example)
    target = request.get("target") if isinstance(request, dict) else None
    pin = target.get("record") if isinstance(target, dict) else None
    found: list[JsonObject] = []
    for source in example.sources:
        try:
            record = parse(source)
        except NotStrictJson:
            continue
        if isinstance(record, dict) and isinstance(pin, dict):
            if all(record.get(member) == pin.get(member) for member in ("id", "version", "content_hash")):
                found.append(record)
    return found


def an_overlay_as_the_target(example: Example, model: Outcome) -> bool:
    """`read_side_contract.md:209-210` refuses at step 5 a target's record that is not a material; the
    implementation raises there until S4 (S4's decision 8, its case mapped to S4)."""
    refused = (
        isinstance(model.result, dict)
        and model.result.get("status") == "not_met"
        and model.result.get("reasons") == [{"code": "unknown_type"}]
    )
    return refused and any(record.get("record_type") == "overlay" for record in targets(example))


def forms_held(example: Example) -> set[str]:
    """The forms the read field, and each alternative it holds, hold where its row allows them."""
    request = request_of(example)
    target = request.get("target") if isinstance(request, dict) else None
    name = target.get("field") if isinstance(target, dict) else None
    if not isinstance(name, str) or name not in VOCABULARY.fields:
        return set()
    section, _, field_name = name.partition(".")
    forms: set[str] = set()
    for record in targets(example):
        body = record.get("body")
        sections = body.get("sections") if isinstance(body, dict) else None
        held = sections.get(section) if isinstance(sections, dict) else None
        fields = held.get("fields") if isinstance(held, dict) else None
        field = fields.get(field_name) if isinstance(fields, dict) else None
        values = field.get("alternatives") if isinstance(field, dict) else None
        for value in values if isinstance(values, list) else [field]:
            if isinstance(value, dict) and value.get("form") in VOCABULARY.fields[name].forms:
                forms.add(str(value["form"]))
    return forms


def a_form_s2b_reads(example: Example, model: Outcome) -> bool:
    """A form its row allows whose own member S2b-1 (intervals, compositions) or S2b-2 (evidence) reads."""
    return bool(forms_held(example) & {"interval", "composition", "evidence"})


def an_acceptance_s2b_reads(example: Example, model: Outcome) -> bool:
    """An acceptance other than an implied condition, whose checks S2b-2 (nominals), S3 and S4 build: the
    implementation raises whatever else the request holds."""
    request = request_of(example)
    acceptances = request.get("acceptances") if isinstance(request, dict) else None
    return isinstance(acceptances, list) and any(
        not (isinstance(entry, dict) and entry.get("acceptance") == "implied_condition")
        for entry in acceptances
    )


class NotBuilt(NamedTuple):
    said: str  # how the implementation's `NotImplementedError` begins
    holds: Callable[[Example, Outcome], bool]
    why: str


NOT_BUILT = {
    "an overlay as the target": NotBuilt(
        "a read whose target is an overlay",
        an_overlay_as_the_target,
        "S4's decision 8: S4 builds step 5's refusal of an overlay as the target, which the model gives",
    ),
    "a form S2b reads": NotBuilt(
        "the member of a field of form",
        a_form_s2b_reads,
        "S2b-1 reads intervals and compositions, S2b-2 evidence; the model reads all three",
    ),
    "an acceptance S2b reads": NotBuilt(
        "a request's acceptances other than implied conditions",
        an_acceptance_s2b_reads,
        "S2b-2 checks a nominal, S3 and S4 the others; the model refuses a broken one or an unknown kind",
    ),
}


# The open points on which the implementation reads the text otherwise than the model, which fails closed
# (`read_model.OPEN_POINTS`): each by the model's seeded fault that reads it as the implementation does. The
# text leaves both open; the maintainer rules (the decision log, phase B).
class OpenPoint(NamedTuple):
    refused: str  # the reason the model's fail-closed reading refuses with
    reading: str  # the model's seeded fault that reads the point as the implementation does


OPEN_POINTS: Mapping[str, OpenPoint] = {
    "members_of_the_other_kind": OpenPoint("form_invalid", "members_of_the_other_kind_ignored"),
    "names_a_declaration_gives_a_requirement": OpenPoint(
        "request_incomplete", "declaration_names_not_named_in_a_request"
    ),
}


def refusals(outcome: Outcome) -> list[JsonValue]:
    """The codes of a `not_met` result, none for any other outcome."""
    result = outcome.result
    if not (isinstance(result, dict) and result.get("status") == "not_met"):
        return []
    reasons = result.get("reasons")
    return (
        [reason.get("code") for reason in reasons if isinstance(reason, dict)]
        if isinstance(reasons, list)
        else []
    )


def check_agreement(example: Example) -> str:
    """The implementation and the model agree on `example`, or diverge as a known divergence says; the
    outcome, by name."""
    implementation = implementation_outcome(example)
    model = model_outcome(example)
    open_points = [name for name in example.planted if name in OPEN_POINTS]
    if open_points:
        (name,) = open_points
        point = OPEN_POINTS[name]
        assert point.refused in refusals(model), (
            f"{name}: the model does not refuse it as it reads it: {model}"
        )
        with MUTANTS[point.reading].applied():
            reading = model_outcome(example)
        assert agree(implementation, reading), f"{name}: {described(implementation, reading)}"
        return "open_point"
    if implementation.kind == "not_yet" and model.kind == "result":
        kinds = [kind for kind, built in NOT_BUILT.items() if implementation.why.startswith(built.said)]
        assert kinds, f"a step not built that no divergence lists: {described(implementation, model)}"
        assert NOT_BUILT[kinds[0]].holds(example, model), f"{kinds[0]}, not as listed: {model}"
        return "not_built"
    assert agree(implementation, model), described(implementation, model)
    return {"result": "agrees", "not_yet": "neither_decides", "misuse": "misuse"}[model.kind]


# The parts, each drawing its kinds first.

PARTS: dict[str, tuple[str, ...]] = {
    "valued": ("valued", "alternatives"),
    "faults": ("step_8", "steps_9_and_10"),
    "early": ("request", "ends_early"),
}
STEPS = tuple(f"step_{step}" for step in strategies.STEPS)


def checked(example: Example, shown: str) -> None:
    feature(shown)
    check_agreement(example)


@pytest.mark.drawn(*PARTS["valued"])
@given(strategies.drawn(SIZE, PARTS["valued"]))
def test_the_read_agrees_with_the_model_on_values_and_alternatives(example: Example) -> None:
    checked(example, example.kind)


@pytest.mark.drawn(*PARTS["faults"])
@given(strategies.drawn(SIZE, PARTS["faults"]))
def test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10(example: Example) -> None:
    checked(example, example.kind)


@pytest.mark.drawn(*STEPS)
@given(strategies.two_faults_of_one_step(SIZE))
def test_the_read_agrees_with_the_model_on_two_faults_of_one_step(example: Example) -> None:
    checked(example, example.planted[0])


@pytest.mark.drawn(*PARTS["early"])
@given(strategies.drawn(SIZE, PARTS["early"]))
def test_the_read_agrees_with_the_model_on_requests_and_reads_that_end_early(example: Example) -> None:
    checked(example, example.kind)


@pytest.mark.drawn(*strategies.PLANTS)
@given(strategies.unpinned(SIZE))
def test_the_read_agrees_with_the_model_where_no_case_pins_a_rule(example: Example) -> None:
    checked(example, example.planted[0])
