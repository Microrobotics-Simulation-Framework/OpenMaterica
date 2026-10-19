# SPDX-License-Identifier: Apache-2.0
"""Strategies for S4a's properties, HP27 to HP29: a field holding alternatives, read with no pick and no
overlay (`read_side_contract.md` section 3, step 7), its outcome drawn first, so that the feature audit holds
each to its draw floor.

The outcome is one of step 7's five: a refusal, every alternative set aside, the one left, `want_mismatch`
where two or more stay and none has a form `want` can give, and `no_pick`. The draw builds what gives it: a
base read that passes steps 1 to 10 (`condition_strategies.base_reads`), of a form drawn second, and one to
five alternatives, each the base field with its own member drawn afresh and changed by a way drawn for its
standing:

- staying: as drawn (`met`); a value stated without origin (`without_origin`, step 12's `unknown`); a
  condition of a name the reader does not know (`unknown_name`, step 10's `unknown`); a field that takes a
  constant and an interval held in the other form (`other_form`); evidence's unit with another `reason`
  (`reason_apart`);
- set aside: a numeric condition one double off the operating value its tolerance of 0 holds to
  (`outside`), or a token the request does not accept (`not_accepted`), each step 10's `not_met`, in a field
  that takes a constant and an interval held in either form, the other in half the draws, since a set-aside
  alternative's form decides nothing; evidence, which holds no registered condition, by an implied
  temperature one double off the operating one, which a fact its specimen states lets apply
  (`implied_outside`), the others then holding no temperature (`condition_unstated`), which the requirement
  names;
- refusing: a unit other than the registered one (`unit`, step 9), a form token the reader does not know
  (`form_token`) or a missing provenance (`member_missing`, both step 8), or two implied conditions that
  disagree in it alone (`request_fault`, step 10's fault of the request).

The ways are placed in a stored order drawn too. Each way's standing is the one the text gives it, so the
drawn outcome is the draw's: `want_mismatch` takes a `want` neither form gives and no nominal, and `no_pick`
the base form's own, its first staying alternative of that form. HP27 still decides each draw from the text,
by its oracle, not from the drawn outcome.
"""

import copy
import math
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import result_strategies as results
from tests.property.condition_strategies import Read, at, base_reads, held, implying, listed, reference
from tests.property.strategies import DOUBLES, TEXT, Size
from tests.property.value_field_strategies import FORM_FIELDS, own_member
from tests.property.value_field_strategies import WANTS as FORM_WANTS

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn

OUTCOMES = ("refused", "all_set_aside", "one_left", "want_mismatch", "no_pick")
STAYING = ("met", "without_origin", "unknown_name", "other_form", "reason_apart")
SET_ASIDE = ("outside", "not_accepted", "implied_outside")
REFUSING = ("unit", "form_token", "member_missing", "request_fault")
WAYS = (*STAYING, *SET_ASIDE, *REFUSING)
# The fields that take a constant and an interval, whose alternatives may be either.
TWO_FORMS = tuple(sorted(set(FORM_FIELDS["constant"]) & set(FORM_FIELDS["interval"])))
# The wants of plain read (`read_side_contract.md` section 6).
WANTS = ("value", "bounds", "components", "evidence")
# The facts two implied conditions that disagree name, and the one an implied temperature that sets evidence
# aside names; a base's own are removed, so that only the alternatives drawn to state them meet them.
IMPLYING_FACTS = {"tissue_state": "in_vivo", "disease_and_treatment_state": "normal"}
SETTING_ASIDE_FACT = ("preservation", "refrigerated")


class Alternatives(NamedTuple):
    outcome: str  # the outcome drawn first, one of OUTCOMES
    form: str  # the base field's form
    ways: tuple[str, ...]  # each stored alternative's way, in stored order
    record: JsonObject  # holding the alternatives, pinned by its hash
    request: JsonObject  # pinned to `record`, its acceptances located at it
    claims: frozenset[Suite]
    field: str  # `<section>.<field>`
    nominal: bool  # whether a nominal the request carries applies to the read
    added: int | None = None  # where drawn with a further alternative set aside, its stored index

    @property
    def stored(self) -> list[JsonValue]:
        holder = results.field_at(self.record, self.field)
        alternatives = holder["alternatives"]
        assert isinstance(alternatives, list)
        return alternatives


def counts(draw: Draw, outcome: str) -> tuple[int, int, int]:
    """How many alternatives refuse, are set aside and stay, for `outcome`, at most five in all."""
    if outcome == "refused":
        return draw(st.integers(1, 2)), draw(st.integers(0, 1)), draw(st.integers(0, 2))
    if outcome == "all_set_aside":
        return 0, draw(st.integers(1, 3)), 0
    if outcome == "one_left":
        return 0, draw(st.integers(0, 2)), 1
    return 0, draw(st.integers(0, 1)), draw(st.integers(2, 3))


# The base forms, a constant twice as often as each other form, as `READ_FORMS` draws them.
FORMS = ("constant", "constant", "interval", "composition", "evidence")


def set_aside_ways(form: str) -> tuple[str, ...]:
    return ("implied_outside",) if form == "evidence" else ("outside", "not_accepted")


def staying_ways(form: str, field: str, *, giving: bool = False) -> tuple[str, ...]:
    """The ways an alternative of `form` stays; with `giving`, only those that keep the base form, which the
    `want` of `no_pick` gives."""
    ways = ["met", "without_origin", "unknown_name"]
    if field in TWO_FORMS and not giving:
        ways.append("other_form")
    if form == "evidence":
        ways.append("reason_apart")
    return tuple(ways)


def want_for(draw: Draw, outcome: str, form: str, field: str) -> str:
    """`want_mismatch` takes a `want` that neither form the field may hold gives; `no_pick` the base form's
    own, so that at least one alternative that stays gives it; any other outcome any `want`."""
    if outcome == "want_mismatch":
        given = {FORM_WANTS[form], *(("value", "bounds") if field in TWO_FORMS else ())}
        return draw(st.sampled_from([want for want in WANTS if want not in given]))
    if outcome == "no_pick":
        return FORM_WANTS[form]
    return draw(st.sampled_from(WANTS))


def without_implying_facts(read_record: JsonObject, field: str) -> None:
    section, _, name = field.partition(".")
    held = at(read_record, "body", "sections", section)
    for specimen in (held.get("specimen"), at(held, "fields", name).get("specimen")):
        if isinstance(specimen, dict):
            for fact in (*IMPLYING_FACTS, SETTING_ASIDE_FACT[0]):
                specimen.pop(fact, None)


def next_to(value: float) -> float:
    """A double next to `value`, finite."""
    found = math.nextafter(value, math.inf)
    return found if math.isfinite(found) else math.nextafter(value, -math.inf)


def in_the_other_form(draw: Draw, alternative: JsonObject, field: str) -> None:
    """A constant held as an interval, or an interval as a constant; an interval carries no label (the
    field's row gives its label to a constant or a table alone)."""
    if alternative["form"] == "constant":
        del alternative["value"]
        alternative.pop("label", None)
        alternative["form"] = "interval"
        alternative["interval"] = draw(own_member("interval", field))
    else:
        del alternative["interval"]
        alternative["form"] = "constant"
        alternative["value"] = draw(DOUBLES)


def changed(draw: Draw, alternative: JsonObject, way: str, request: JsonObject, field: str) -> None:
    """`alternative`, a copy of the base field, changed by `way`; a fault of the request adds its two implied
    conditions to `request`."""
    if way == "without_origin":
        at(alternative, "provenance")["origin"] = "stated_without_origin"
    elif way == "unknown_name":
        name = "x_" + draw(st.text("abcdefgh", min_size=1, max_size=6))
        at(alternative, "conditions")[name] = {"value": 1.0, "unit": "bar", "basis": "stated"}
    elif way == "other_form":
        in_the_other_form(draw, alternative, field)
    elif way == "reason_apart":
        alternative["unit"] = {**at(alternative, "unit"), "reason": draw(TEXT)}
    elif way == "outside":
        operated = at(request, "operating_conditions", "measurement_dimension")["value"]
        assert isinstance(operated, float)
        at(alternative, "conditions")["measurement_dimension"] = {
            "value": next_to(operated),
            "unit": "m",
            "basis": "stated",
        }
    elif way == "not_accepted":
        accepted = at(request, "requirement", "conditions", "measurement_geometry")["accept"]
        assert isinstance(accepted, list)
        others = [
            token for token in VOCABULARY.conditions["measurement_geometry"].tokens if token not in accepted
        ]
        at(alternative, "conditions")["measurement_geometry"] = {
            "token": draw(st.sampled_from(others)),
            "basis": "stated",
        }
    elif way == "unit":
        unit = alternative["unit"]
        alternative["unit"] = f"{unit} " if isinstance(unit, str) else "1"
    elif way == "form_token":
        alternative["form"] = "spline"
    elif way == "member_missing":
        del alternative["provenance"]
    elif way == "implied_outside":
        fact, token = SETTING_ASIDE_FACT
        stated_facts(alternative)[fact] = {"token": token, "basis": "stated"}
    elif way == "request_fault":
        stated_facts(alternative).update(
            {fact: {"token": token, "basis": "stated"} for fact, token in IMPLYING_FACTS.items()}
        )


def stated_facts(alternative: JsonObject) -> JsonObject:
    facts = alternative.setdefault("specimen", {})
    assert isinstance(facts, dict)
    return facts


def with_an_implied_temperature_outside(draw: Draw, read: Read, request: JsonObject) -> JsonValue:
    """For evidence, an operating temperature, a tolerance of 0 on it, and the implied condition located at
    the read that gives an alternative stating `SETTING_ASIDE_FACT` a temperature one double off it."""
    operated = draw(DOUBLES)
    request["operating_conditions"] = {"temperature": {"value": operated, "unit": "K"}}
    requirement = at(request, "requirement")
    requirement["conditions"] = {"temperature": {"tolerance": {"value": 0.0, "unit": "K"}}}
    fact, token = SETTING_ASIDE_FACT
    return implying(read, fact, token, next_to(operated))


@st.composite
def disagreeing(draw: Draw, read: Read) -> list[JsonValue]:
    """Two implied conditions located at the read, one for each of `IMPLYING_FACTS`, giving the temperature
    two values: where an alternative's specimen states both, they end its read at step 10 (section 1)."""
    first = draw(DOUBLES)
    second = next_to(first)
    found: list[JsonValue] = []
    for (fact, token), value in zip(IMPLYING_FACTS.items(), (first, second), strict=True):
        found.append(implying(read, fact, token, value))
    return found


def pinned_to(request: JsonObject, record: JsonObject, old: JsonObject) -> JsonObject:
    """`request` with its target, and each acceptance located at the record `old` pins, pinning `record`."""
    changed_request = copy.deepcopy(request)
    at(changed_request, "target")["record"] = reference(record)
    for acceptance in held(listed(changed_request.get("acceptances"))):
        if acceptance.get("record") == old:
            acceptance["record"] = reference(record)
    return changed_request


@st.composite
def alternatives(
    draw: Draw,
    size: Size,
    outcomes: tuple[str, ...] = OUTCOMES,
    *,
    added: bool = False,
    forms: tuple[str, ...] = FORMS,
    refusing_ways: tuple[str, ...] = REFUSING,
    under_a_nominal: bool = False,
    set_aside_first: bool = False,
) -> Alternatives:
    """A field holding alternatives, its outcome drawn first among `outcomes`, then its form among `forms`,
    its read, the counts and ways of each standing, and their stored order; with `added`, one more
    alternative, set aside, at a stored index drawn. A planned search narrows the draw: the ways an
    alternative refuses by; a nominal that applies to the read under `want: value` always (`under_a_nominal`,
    for a form a nominal applies to); or an alternative set aside stored first (`set_aside_first`)."""
    outcome = draw(st.sampled_from(outcomes))
    form = draw(st.sampled_from(forms))
    read = draw(base_reads(size, FORM_FIELDS[form], form))
    without_implying_facts(read.record, read.field)
    field = results.without_withheld_reports(results.field_at(read.record, read.field))
    results.without_origin_s_reason(field)
    refusing, set_aside, staying = counts(draw, outcome)
    set_aside = max(set_aside, int(set_aside_first))
    giving = outcome == "no_pick"
    ways = [
        *(draw(st.sampled_from(refusing_ways)) for _ in range(refusing)),
        *(draw(st.sampled_from(set_aside_ways(form))) for _ in range(set_aside)),
        *(
            draw(st.sampled_from(staying_ways(form, read.field, giving=giving and number == 0)))
            for number in range(staying)
        ),
    ]
    ways = draw(st.permutations(ways))
    if set_aside_first:
        first = next(index for index, way in enumerate(ways) if way in SET_ASIDE)
        ways.insert(0, ways.pop(first))
    position = None
    if added:
        position = draw(st.integers(0, len(ways)))
        ways.insert(position, draw(st.sampled_from(set_aside_ways(form))))
    want = "value" if under_a_nominal else want_for(draw, outcome, form, read.field)
    request = results.with_want(read.request, want)
    acceptances: list[JsonValue] = []
    if "request_fault" in ways:
        acceptances += draw(disagreeing(read))
    if "implied_outside" in ways:
        acceptances.append(with_an_implied_temperature_outside(draw, read, request))
    nominal = want == "value" and read.field in TWO_FORMS and (under_a_nominal or draw(st.booleans()))
    if nominal:
        acceptances.append(
            {
                "acceptance": "nominal",
                "record": reference(read.record),
                "field": read.field,
                "value": draw(DOUBLES),
            }
        )
    if acceptances:
        request["acceptances"] = acceptances
    stored: list[JsonValue] = []
    for way in ways:
        alternative = results.another_value(draw, field, read.field)
        changed(draw, alternative, way, request, read.field)
        if way in SET_ASIDE and read.field in TWO_FORMS and draw(st.booleans()):
            in_the_other_form(draw, alternative, read.field)
        stored.append(alternative)
    record = results.holding(read, {"alternatives": stored})
    claims = draw(st.sampled_from((results.WITH_HASH, results.WITHOUT_HASH)))
    return Alternatives(
        outcome,
        form,
        tuple(ways),
        record,
        pinned_to(request, record, reference(read.record)),
        claims,
        read.field,
        nominal,
        position,
    )


def holding(drawn: Alternatives, held: JsonValue) -> tuple[JsonObject, JsonObject]:
    """The drawn record with `held` in its field's place, a value field or `{"alternatives": [...]}`, pinned
    by its hash, and the drawn request pinned to it."""
    record = copy.deepcopy(drawn.record)
    section, _, name = drawn.field.partition(".")
    at(record, "body", "sections", section, "fields")[name] = copy.deepcopy(held)
    record = results.repinned(record)
    return record, pinned_to(drawn.request, record, reference(drawn.record))
