# SPDX-License-Identifier: Apache-2.0
"""(12) The S2 design's HP12: the read agrees with the test-only reference model (`tests/reference/
read_model.py`), which is written from the text and imports nothing from `materica`, over reads drawn across
every step S2 builds (`model_strategies.py`), in five parts that run side by side, and over S3b-2's table
reads and S4d's tables among alternatives, in a part each.

Both are given the same sources, the same request text and the same claims. They agree where both give a
result and the two results are equal as `read_side_contract.md` section 2 compares them: the status, the
reasons as a set of their code, condition and alternative (a reason's `detail` is for people), the labels as
a set, the condition entries by name, the alternative values in order, and every other member as a JSON value,
numbers bit for bit. Where the implementation raises `NotImplementedError` for a step not built yet and the
model gives no verdict, or both refuse claims without plain read as a misuse, they agree that neither
decides. Anything else fails, but the known divergences, each listed by kind with its reason and held to
exactly what each side gives there:

- a step the implementation has not built that the model decides (`NOT_BUILT`): an overlay as the target,
  found by the implementation's own words for what it has not built, and held to what the draw holds and the
  model gives (a pick or an overlay in a request, which the implementation raises at, the model gives no
  verdict on);
- an open point on which the two read the text differently (`OPEN_POINTS`), planted by the draw alone: there
  the model must refuse, as its fail-closed reading does, and the model given the implementation's reading (a
  seeded fault of the model that is that reading, `tests/reference/mutants.py`) must agree with the
  implementation. None is listed today: the last, open point 1's record half, was ruled fail closed
  (maintainer, 2026-10-19), and the two read it alike since.
"""

import json
import math
from collections.abc import Callable, Mapping
from typing import Literal, NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core.read import read
from materica.core.record import RecordStore
from tests.property import model_strategies as strategies
from tests.property import table_alternatives_strategies as table_alternatives
from tests.property import table_read_strategies as table_reads
from tests.property.model_strategies import Example
from tests.property.strategies import SIZE, Size
from tests.property.support import feature, same
from tests.reference import read_model
from tests.reference.mutants import MUTANTS
from tests.reference.strict_json import JsonObject, JsonValue, NotStrictJson, parse


class Outcome(NamedTuple):
    kind: Literal["result", "not_yet", "misuse"]
    result: JsonValue = None  # the result, compared as section 2 compares it
    why: str = ""


# The counts a result writes as integers (the code design's rule 5), where an integer has no sign for zero.
COUNTS = ("n_specimens", "n_donors", "n_sources")


def counted(value: JsonValue) -> JsonValue:
    """`value` with each count of a statistics block, an input specimen's `input` and an alternative value's
    index as the integer rule 5 writes it: `-0` is 0."""
    if isinstance(value, list):
        return [counted(item) for item in value]
    if not isinstance(value, dict):
        return value
    whole = {
        name: member + 0.0
        if name in (*COUNTS, "input", "alternative") and isinstance(member, float)
        else member
        for name, member in value.items()
    }
    return {name: counted(member) for name, member in whole.items()}


def compared(result: JsonObject) -> JsonObject:
    """`result` with its sets in one order: the reasons without their details, the labels, each condition
    entry by name, and within each alternative value its labels and entries; and its counts and indexes as
    rule 5 writes them (`counted`)."""

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
    written = counted(found)
    assert isinstance(written, dict)
    return written


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
    return written_outcome(result.to_json())


def written_outcome(result: object) -> Outcome:
    """The outcome of a result the read gave, as its JSON is read back."""
    try:
        written = parse(json.dumps(result).encode())
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
    """read_side_contract.md:230-231 "Refuse a referenced record of a type the reader cannot read in its
    role" refuses at step 5 a target's record that is not a material; the implementation raises there until
    S4 (S4's decision 8, its case mapped to S4)."""
    refused = (
        isinstance(model.result, dict)
        and model.result.get("status") == "not_met"
        and model.result.get("reasons") == [{"code": "unknown_type"}]
    )
    return refused and any(record.get("record_type") == "overlay" for record in targets(example))


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
}


# The open points on which the implementation reads the text otherwise than the model, which fails closed
# (`read_model.OPEN_POINTS`): each by the model's seeded fault that reads it as the implementation does. None
# is left. Open point 1's record half, a record condition holding a member of the other kind, was the last:
# the maintainer ruled it fail closed (2026-10-19, `provenance.md` section 6.1 item 1), and the implementation
# refuses it since, as its request half (the token ruling, 2026-10-18) and a slip of a declaration's name
# (which the text decides, ruled with S2a-4's review) were already read alike. `test_model_controls.py` holds
# the check of an open point to failing, on that point as the implementation read it before its ruling.
class OpenPoint(NamedTuple):
    refused: str  # the reason the model's fail-closed reading refuses with
    reading: str  # the model's seeded fault that reads the point as the implementation does


OPEN_POINTS: Mapping[str, OpenPoint] = {}


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
    return check_outcome(example, implementation_outcome(example))


def check_outcome(example: Example, implementation: Outcome) -> str:
    """`check_agreement` on the implementation's outcome of `example`, read once already."""
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


# The parts, each drawing its kinds first; the first two draw, after the kind and inside a kind that can
# hold it, the region each holds to a floor (`model_strategies.REGIONS`), so that their kinds stay drawn
# alike: over 96 runs at `ci` (2026-10-20, derandomised, each its own stream) each kind showed in 0.495 to
# 0.505 of the examples, and falls below its floor at one half, 440 of 2,000 examples, with a probability of
# 9e-7 by `audits.py`'s model at that half and below 1e-23 at the variance measured (5.7 to 6.3 times a
# binomial count's).

PARTS: dict[str, tuple[str, ...]] = {
    "valued": ("valued", "alternatives"),
    "faults": ("step_8", "steps_9_and_10"),
    "early": ("request", "ends_early"),
}
STEPS = tuple(f"step_{step}" for step in strategies.STEPS)


def checked(example: Example, shown: str) -> None:
    feature(shown)
    check_agreement(example)


def gives(outcome: Outcome, code: str, *on: str) -> bool:
    """Whether the implementation's result holds a reason of `code`, on one of the conditions `on` where it
    names some."""
    result = outcome.result
    reasons = result.get("reasons") if isinstance(result, dict) else None
    return isinstance(reasons, list) and any(
        isinstance(reason, dict) and reason.get("code") == code and (not on or reason.get("condition") in on)
        for reason in reasons
    )


def at(value: JsonValue, *path: str) -> JsonValue:
    """The member at `path`, or None where a step of it is no object or holds no such member."""
    for step in path:
        value = value.get(step) if isinstance(value, dict) else None
    return value


def forms_read(example: Example) -> set[JsonValue]:
    """The forms of the field the request names, in each record its pin names: the field's own, or each of its
    alternatives' (S4a's draws hold a constant among the alternatives of a field drawn as another form)."""
    name = at(request_of(example), "target", "field")
    section, _, field = name.partition(".") if isinstance(name, str) else ("", "", "")
    forms: set[JsonValue] = set()
    for record in targets(example):
        value = at(record, "body", "sections", section, "fields", field)
        alternatives = at(value, "alternatives")
        held = alternatives if isinstance(alternatives, list) else [value]
        forms.update(at(each, "form") for each in held)
    return forms


def normalising_changes(value: JsonValue) -> bool:
    """Whether `value` is a composition's that a read which normalised it would change: one that states its
    sum, or whose fractions dividing each by their sum changes."""
    components = at(value, "components")
    if not isinstance(components, list):
        return False
    if isinstance(value, dict) and "stated_sum" in value:
        return True
    fractions = [fraction for each in components if isinstance(fraction := at(each, "fraction"), float)]
    total = math.fsum(fractions)
    return bool(total) and any(fraction / total != fraction for fraction in fractions)


def components_not_normalised(implementation: Outcome) -> bool:
    """Whether the read gives, as its value or an alternative's, a composition's components that a read which
    normalised them would change (`components_normalised`)."""
    result = implementation.result
    entries = at(result, "alternative_values")
    held = entries if isinstance(entries, list) else []
    given_ = [at(result, "value"), *(at(entry, "value") for entry in held)]
    return any(normalising_changes(value) for value in given_)


def request_faults_of_two_alternatives(example: Example, implementation: Outcome) -> bool:
    """Whether alternatives are refused by faults of the request alone (`request_incomplete`), on two
    conditions or more: the faults of more than one alternative, which step 7 gives together
    (`request_faults_of_the_first_alternative_alone`)."""
    reasons = at(implementation.result, "reasons")
    found = [reason for reason in reasons if isinstance(reason, dict)] if isinstance(reasons, list) else []
    return (
        example.kind == "alternatives"
        and at(implementation.result, "status") == "not_met"
        and bool(found)
        and all(reason.get("code") == "request_incomplete" for reason in found)
        and len({json.dumps(reason.get("condition")) for reason in found}) >= 2
    )


def a_constant_refused_bounds(example: Example, implementation: Outcome) -> bool:
    """Whether a constant's read under `want: bounds` reached step 13, which refuses it (`want_mismatch`)."""
    want = at(request_of(example), "requirement", "want")
    return "constant" in forms_read(example) and want == "bounds" and gives(implementation, "want_mismatch")


# HP12's draws of S4a's alternatives (`standing`): two of the alternatives kind's six ways, the kind drawn in
# half the examples, so 1/6 by the draw. Over 12 runs at `ci`, the draws alone (2026-10-19, seeds 1000 to
# 1011), their shares were 0.119 to 0.178 (mean 0.157); the chance is declared below the least, as the forms'
# are, and its floor, 30 examples, is below every run's count (237 to 356).
STANDING_CHANCE = 0.10
# A member the reader does not know, which `result_strategies.enriched` plants in half the draws of the field
# `valued` and `alternatives` read, and the region's draws always (`model_strategies.REGIONS`): where
# `unknown_members_returned` shows, which its planned search draws always, held by its chance as HP6 holds it,
# below its least share over 96 runs at `ci` (2026-10-20, derandomised, each its own stream; mean 0.354, least
# 0.294). By `audits.py`'s model, 250 draws each shown in 5 examples, a run falls below its floor of 110
# examples with a probability of 3e-23, and with 3e-42 at the variance measured (5.6 times a binomial
# count's).
UNKNOWN_MEMBER_CHANCE = 0.2


# The form of the field read, drawn after the kind: a constant twice as often as an interval, a composition or
# evidence (`value_field_strategies.READ_FORMS`). About a tenth of the examples show no form, so each is
# declared by its chance measured, not its nominal one: over 22 runs at `ci` (2026-10-18, S2b-2's review, L2),
# their least shares were 0.319, 0.150, 0.128 and 0.133 (means 0.354, 0.177, 0.166, 0.175; the review's 22
# runs, 0.292, 0.145, 0.124, 0.112), and each falls below the draw floor of the chance declared with a
# probability below 1e-12 by `audits.py`'s cluster model at the variance measured (4.1 to 9.9 times a binomial
# count's). Since the region below is drawn (2026-10-20), an interval, a composition and evidence show in
# 0.154 to 0.158 of the examples over 96 runs, their least shares 0.102, 0.107 and 0.107, and `standing` in
# 0.147, its least 0.093: below the chances of the three and `standing`, though each falls below its floor
# with a probability below 1e-10 at the variance measured. The region takes about one draw in seven of each
# kind, and the share it leaves cannot hold the four with the constant's under `want: value`, which no other
# draw gives (README, "The regions held to a floor"). A constant's read under `want: bounds` that reaches step
# 13, where the mutant that gives a constant's value there shows (`model_strategies.REGIONS`), by its chance,
# below its least share over 96 runs at `ci` (2026-10-20, derandomised, each its own stream; mean 0.157, least
# 0.116). By `audits.py`'s model, 250 draws each shown in 5 examples, a run falls below its floor of 20
# examples with a probability of 5e-15, and with 6e-22 at the variance measured (5.7 times a binomial
# count's). A composition's components that a normalising read would change and alternatives refused by
# request faults on two conditions or more, where `components_normalised` and
# `request_faults_of_the_first_alternative_alone` show, are too thin for a floor at `ci`, and each is held to
# one at `deep` alone (`deep_chances`; README, "The regions held to a floor"). Over 24 runs at `ci`
# (2026-10-21, derandomised, each its own stream) both showed in 0.036 of the examples, least 0.0085 and
# 0.0195, a count varying 7.3 and 8.7 times a binomial count's, and over 16 runs of 2,000 at `deep`'s size in
# 0.036 (least 0.014 and 0.019; a run of 20,000 takes about 15 minutes, too long to measure here). Each is
# declared by a chance at or below its least, 0.008 and 0.019, whose floors at `deep` are 15 and 95 examples
# of 20,000. A correct run falls below them with a probability of 4.3e-7 and 7.3e-7 by `audits.py`'s model at
# those chances (2,500 draws each shown in 5 examples), and of at most 7e-35 and 6e-22 at the means and
# variances measured, scaled to `deep`'s examples.
@pytest.mark.deep_chances(components_not_normalised=0.008, request_faults_of_two_alternatives=0.019)
@pytest.mark.chances(
    form_constant=0.29,
    form_interval=0.14,
    form_composition=0.12,
    form_evidence=0.11,
    standing=STANDING_CHANCE,
    constant_refused_bounds=0.09,
    unknown_member=UNKNOWN_MEMBER_CHANCE,
)
@pytest.mark.drawn(*PARTS["valued"])
@given(strategies.drawn(SIZE, PARTS["valued"]))
def test_the_read_agrees_with_the_model_on_values_and_alternatives(example: Example) -> None:
    for planted in example.planted:
        feature(planted, planted.startswith("form_") or planted in ("standing", "unknown_member"))
    implementation = implementation_outcome(example)
    feature("constant_refused_bounds", a_constant_refused_bounds(example, implementation))
    feature("components_not_normalised", components_not_normalised(implementation))
    feature("request_faults_of_two_alternatives", request_faults_of_two_alternatives(example, implementation))
    feature(example.kind)
    check_outcome(example, implementation)


# The units of steps 9 and 10 that the model's faults pass (`plus_minus_units_unchecked` and
# `token_condition_unit_accepted`), by the region where each shows: a read that plants the fault and whose
# result gives `unit_mismatch` on the condition holding the unit. A read that ends before step 9, at a `want`
# its field's form cannot give (`want_mismatch`), gives none.
UNIT_REFUSALS: dict[str, tuple[str, str]] = {
    "plus_minus_unit_refused": ("unit_plus_minus", "temperature"),
    "token_condition_unit_refused": ("unit_token_condition", "measurement_geometry"),
}


def refuses_its_planted_unit(example: Example, implementation: Outcome, region: str) -> bool:
    fault, condition = UNIT_REFUSALS[region]
    return fault in example.planted and gives(implementation, "unit_mismatch", condition)


# A result holding `condition_unchecked`, where HP1's mutant that drops that reason's condition shows
# (`model_strategies.REGIONS`), by its chance, which is at its least share, not clear of it: over 96 runs at
# `ci` (2026-10-20, derandomised, each its own stream) the mean was 0.132 and the least 0.093, and over 20
# more on other streams (2026-10-21) the least was 0.0795 (159 of 2,000 examples), under the chance. By
# `audits.py`'s model, 250 draws each shown in 5 examples, a run falls below its floor of 15 examples (against
# that least count of 159) with a probability of 4e-13, with 3e-19 at the variance of the 96 runs (5.6 times a
# binomial count's) and with 5e-11 at that of the 20 (10.4 times). The region takes about a quarter of the
# draws of steps 9 and 10, the one kind that can hold it, so each of their first faults shows in about three
# quarters of its share on main.
# The two refused units (`UNIT_REFUSALS`), too thin for a floor at `ci`, each held to one at `deep` alone
# (`deep_chances`; README, "The regions held to a floor"). Over 24 runs at `ci` (2026-10-21, derandomised,
# each its own stream) they showed in 0.0247 and 0.0255 of the examples, least 0.0105 and 0.0075, a count
# varying 3.8 and 6.1 times a binomial count's, and over 4 runs at `deep` in 0.0256 and 0.0283 (least 0.0226
# and 0.0260). Each is declared by a chance below its least at `ci`, 0.01 and 0.007, whose floors at `deep`
# are 25 and 10 examples of 20,000. A correct run falls below them with a probability of 2.4e-7 and 4.4e-7 by
# `audits.py`'s model at those chances (2,500 draws each shown in 5 examples), and of 3e-47 and 3e-35 at the
# means and variances measured at `ci`, scaled to `deep`'s examples.
@pytest.mark.deep_chances(plus_minus_unit_refused=0.01, token_condition_unit_refused=0.007)
@pytest.mark.chances(condition_unchecked=0.08)
@pytest.mark.drawn(*PARTS["faults"])
@given(strategies.drawn(SIZE, PARTS["faults"]))
def test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10(example: Example) -> None:
    implementation = implementation_outcome(example)
    feature("condition_unchecked", gives(implementation, "condition_unchecked"))
    for region in UNIT_REFUSALS:
        feature(region, refuses_its_planted_unit(example, implementation, region))
    feature(example.kind)
    check_outcome(example, implementation)


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


# A table read to the end (S3b-2): one of the five kinds drawn first, four of HP20 to HP23's families and a
# table beside a constant among alternatives, then the family's way, which the example plants, its `want`, a
# tolerance on the axis across the range in half those draws, the regions drawn beside it, a member the reader
# does not know and a field stated without origin, which it plants too, and the claims, with and without the
# hash suite.
# The model reads a table with the reference evaluator's `exact` mode; the implementation with
# `core/evaluate.py`.
TABLE_KINDS = (*table_reads.TABLE_KINDS, table_reads.ALTERNATIVES_KIND)


@st.composite
def tables_read(draw: st.DrawFn, size: Size = SIZE, kinds: tuple[str, ...] = TABLE_KINDS) -> Example:
    kind, drawn = draw(table_reads.table_reads(size, kinds))
    claims = draw(st.sampled_from(strategies.CLAIMS))
    request = json.dumps(table_reads.request_of(drawn)).encode()
    return Example(
        kind, (table_reads.source_of(drawn),), request, claims, (drawn.way, drawn.want, *drawn.planted)
    )


@pytest.mark.drawn(*TABLE_KINDS)
@given(tables_read())
def test_the_read_agrees_with_the_model_on_tables(example: Example) -> None:
    checked(example, example.kind)


# S4d's part: a table among alternatives whose read gives a reason at step 11
# (`table_alternatives_strategies.py`), its part drawn first, of HP39's two (`KEPT_OR_SET_ASIDE`, `REFUSES`),
# then, as HP39 draws them, the others' outcome among S4a's five and the table's way among the part's four,
# each by chance; the example plants the way and the others' outcome, so that a planned search of a way names
# it.
TABLE_ALTERNATIVE_PARTS: dict[str, tuple[str, ...]] = {
    "kept_or_set_aside": table_alternatives.KEPT_OR_SET_ASIDE,
    "refuses": table_alternatives.REFUSES,
}


@st.composite
def tables_among_alternatives(
    draw: st.DrawFn, size: Size = SIZE, ways: tuple[str, ...] | None = None
) -> Example:
    """A part drawn first, then the table's way among its ways; or, for a planned search, among `ways`."""
    part = draw(st.sampled_from(sorted(TABLE_ALTERNATIVE_PARTS)))
    drawn = draw(table_alternatives.table_alternatives(size, ways or TABLE_ALTERNATIVE_PARTS[part]))
    return Example(
        part,
        (json.dumps(drawn.drawn.record).encode(),),
        json.dumps(drawn.drawn.request).encode(),
        drawn.drawn.claims,
        (drawn.way, drawn.others),
    )


@pytest.mark.drawn(*TABLE_ALTERNATIVE_PARTS)
@given(tables_among_alternatives())
def test_the_read_agrees_with_the_model_on_tables_among_alternatives(example: Example) -> None:
    checked(example, example.kind)
