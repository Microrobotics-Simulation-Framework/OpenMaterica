# SPDX-License-Identifier: Apache-2.0
"""Strategies for the S2 design's HP12: reads drawn across every step S2 builds, for the implementation and
the reference model (`tests/reference/read_model.py`) to agree on, each drawn by its kind first.

A draw is the sources' bytes, the request's JSON text and the claims, and what it planted, by name, so that a
property can tell a planted open point from anything else. The kinds:

- **valued**: a constant, an interval, a composition or evidence that passes steps 1 to 8, under any `want` of
  section 6 (a form's own in half its draws but a constant's) and any claims, its value `-0`, its review read
  each way and a member the reader does not know where `result_strategies.enriched` draws them; its
  temperature met as drawn, at one of section 5's boundaries as HP7 draws them, or filled by an implied
  condition, the way drawn first; an interval in half the draws with a nominal of a way
  `result_strategies.NOMINAL_WAYS` names, and evidence's unit in half its draws with a reason;
- **alternatives**: two or three alternatives of one form the request meets, a list that breaks its shape,
  or alternatives each refused by one request fault (S4's decision 12); intervals in half the draws under
  `want: value` with a nominal located at the read, which none of them is given;
- **step 8**, **steps 9 and 10**: one fault of each step's catalogue, or two of two parts in one draw in four;
- **two of one step**: two faults of one of steps 0, 8, 9 and 10 that give two reasons, so that a step that
  stops at its first fault shows (the design's B5);
- **request**: one or two faults of step 0's catalogue below, written from `read_side_contract.md` section 1;
- **ends early**: a read that ends before step 4, at step 5 or at step 7, a store of `stores.worlds`, or an
  overlay as the target;
- **unpinned**: the rules the reference model's case-agreement leaves unpinned (its survivors and the faults
  one case file alone kills), and the open point on which the implementation and the model read the text
  differently (`OPEN_POINTS`).
"""

import copy
import json
from collections.abc import Callable
from typing import NamedTuple

from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from materica.shapes import Suite
from tests.property import condition_strategies as conditions
from tests.property import result_strategies as results
from tests.property import stores
from tests.property.condition_strategies import Read, at, base_reads, implying, in_vivo, repinned
from tests.property.strategies import DOUBLES, Size
from tests.property.value_field_strategies import FORM_FIELDS, faulty_records, pinned, slipped, specimen
from tests.property.value_field_strategies import WANTS as FORM_WANTS

JsonObject = dict[str, JsonValue]
Draw = st.DrawFn


class Example(NamedTuple):
    kind: str
    sources: tuple[bytes, ...]
    request: bytes  # the request's JSON text
    claims: frozenset[Suite]
    planted: tuple[str, ...] = ()  # the faults, ways or open points the draw planted, by name


# Each configuration of claims a case may run under (`tests/reference/cases.py`), plain read in every one.
BESIDE_PLAIN_READ: tuple[Suite, ...] = ("hash", "fits_and_reference_data", "family_evaluation")
CLAIMS: tuple[frozenset[Suite], ...] = tuple(
    frozenset({"plain_read", *(suite for bit, suite in enumerate(BESIDE_PLAIN_READ) if chosen >> bit & 1)})
    for chosen in range(2 ** len(BESIDE_PLAIN_READ))
)
# Section 6's `want`s, `value` drawn as often as all the others, which a constant cannot give.
WANTS = ("value",) * 8 + ("bounds", "components", "evidence", "reference_data", "fit", "coverage")


def text(request: JsonValue) -> bytes:
    return json.dumps(request).encode()


def example(kind: str, read: Read, claims: frozenset[Suite], *planted: str) -> Example:
    return Example(kind, (results.as_source(read.record),), text(read.request), claims, planted)


def wanting(read: Read, want: str) -> Read:
    return read._replace(request=results.with_want(read.request, want))


def fresh(read: Read) -> Read:
    """A read whose record and request may be changed in place."""
    return read._replace(record=copy.deepcopy(read.record), request=copy.deepcopy(read.request))


def field_of(read: Read) -> JsonObject:
    return results.field_at(read.record, read.field)


# Valued reads.


def with_implied_temperature(draw: Draw, read: Read) -> None:
    """An in-vivo specimen whose temperature the record leaves unstated or does not hold, filled by an implied
    condition at the operating value; or, in one draw in four, still stated, which the implied value never
    overrides. A row that requires no temperature (a composition's) has the request give one."""
    in_vivo(read)
    operating = at(read.request, "operating_conditions")
    if "temperature" not in operating:
        operating["temperature"] = {"value": 310.15, "unit": "K"}
        at(read.request, "requirement", "conditions")["temperature"] = {
            "tolerance": {"value": 1.0, "unit": "K"}
        }
    held = at(field_of(read), "conditions")
    way = draw(st.sampled_from(["unstated", "absent", "absent", "stated"]))
    if way == "unstated":
        held["temperature"] = {"status": "unstated"}
    elif way == "absent":
        held.pop("temperature", None)
    operated = at(read.request, "operating_conditions", "temperature")["value"]
    assert isinstance(operated, float)
    read.request["acceptances"] = [implying(read, "tissue_state", "in_vivo", operated)]


def at_a_boundary(draw: Draw, read: Read) -> None:
    """The temperature stated, operated and toleranced at one of section 5's boundaries, as HP7 draws them
    (`condition_strategies.numeric`), with a stated plus or minus of each kind in one draw in three."""
    numeric = draw(
        conditions.numeric(draw(st.sampled_from(conditions.ROWS)), draw(st.sampled_from(BOUNDARIES)))
    )
    entries = (
        conditions.plus_minus(draw(st.sampled_from(conditions.PLUS_MINUS_KINDS)), abs(draw(DOUBLES)))
        if draw(st.integers(0, 2)) == 0
        else None
    )
    at(field_of(read), "conditions")["temperature"] = conditions.stated("temperature", numeric, entries)
    at(read.request, "operating_conditions")["temperature"] = conditions.operating_of("temperature", numeric)
    at(read.request, "requirement", "conditions")["temperature"] = conditions.tolerance_of(
        "temperature", numeric
    )


BOUNDARIES = conditions.BOUNDARIES
VALUED_WAYS = ("as_drawn", "at_a_boundary", "implied")


def a_want(draw: Draw, form: str) -> str:
    """Any `want`, or, in half the draws of an interval or a composition, its own."""
    if form != "constant" and draw(st.booleans()):
        return FORM_WANTS[form]
    want: str = draw(st.sampled_from(WANTS))
    return want


NOMINAL_PLANTS = (*(f"nominal_{way}" for way in results.NOMINAL_WAYS), "nominal_over_alternatives")


@st.composite
def valued(
    draw: Draw,
    size: Size,
    ways: tuple[str, ...] = VALUED_WAYS,
    *,
    nominal: bool = False,
    unit_with_a_reason: bool = False,
    constant_under_bounds: bool = False,
) -> Example:
    """A valued read; for a planned search's, with `nominal`, an interval's with a nominal always, with
    `unit_with_a_reason`, evidence's with its unit a status object with a reason always, and with
    `constant_under_bounds`, a constant's under `want: bounds` always."""
    way = draw(st.sampled_from(ways))
    if constant_under_bounds:
        form, drawn_read = "constant", draw(base_reads(size, FORM_FIELDS["constant"], "constant"))
    elif nominal:
        form, drawn_read = "interval", draw(base_reads(size, FORM_FIELDS["interval"], "interval"))
    elif unit_with_a_reason:
        form, drawn_read = "evidence", draw(base_reads(size, FORM_FIELDS["evidence"], "evidence"))
    else:
        form, drawn_read = draw(results.form_reads(size))
    read = fresh(drawn_read)
    shown = draw(results.enriched(field_of(read)))
    if way == "at_a_boundary":
        at_a_boundary(draw, read)
    elif way == "implied":
        with_implied_temperature(draw, read)
    if draw(st.integers(0, 2)) == 0:
        beside_another_section(draw, read)
        shown = (*shown, "another_section")
    if form == "evidence" and (unit_with_a_reason or draw(st.booleans())):
        field_of(read)["unit"] = {"status": "not_applicable", "reason": "a list of test reports"}
        shown = (*shown, "unit_with_a_reason")
    read = wanting(repinned(read), "bounds" if constant_under_bounds else a_want(draw, form))
    if form == "interval" and (nominal or draw(st.booleans())):
        nominal_way = draw(st.sampled_from(results.NOMINAL_WAYS))
        read = wanting(read, "bounds" if nominal_way == "under_bounds" else "value")
        with_a_nominal(read, draw(results.nominal_for(read.record, read.field, nominal_way)))
        shown = (*shown, f"nominal_{nominal_way}")
    return example("valued", read, draw(st.sampled_from(CLAIMS)), way, *shown)


def with_a_nominal(read: Read, nominal: JsonObject) -> None:
    acceptances = read.request.setdefault("acceptances", [])
    assert isinstance(acceptances, list)
    acceptances.append(nominal)


def beside_another_section(draw: Draw, read: Read) -> None:
    """Another registered section, holding no field and a specimen of its own, which no read of this field
    looks at (HP4)."""
    sections = at(read.record, "body", "sections")
    others = sorted(set(VOCABULARY.sections) - set(sections))
    sections[draw(st.sampled_from(others))] = {"fields": {}, "specimen": draw(specimen())}


# Alternatives.

ALTERNATIVE_WAYS = ("met", "met", "broken", "request_fault")
# How a further alternative stands apart from the first beside its value, each in one draw in four: in a
# world the read meets, its unit spelled otherwise, which step 9 refuses in it alone, or a specimen fact the
# first does not hold; where the first raises a fault of the request, one of its own instead, two implied
# conditions that give its specimen size two values (S2a-4's review B, L1).
APART_WAYS = ("unit_apart", "specimen_apart", "request_faults_apart")


def apart(draw: Draw, read: Read, field: JsonObject, way: str) -> tuple[JsonObject, tuple[str, ...]]:
    """A further alternative of `field`, its own member drawn, and how else it stands apart, by name."""
    other = results.another_value(draw, field, read.field)
    if draw(st.integers(0, 3)):
        return other, ()
    if way == "request_fault":
        facts = at(other, "specimen")
        facts.pop("disease_and_treatment_state", None)
        facts["tissue_state"] = {"token": "ex_vivo_fresh", "basis": "stated"}
        facts["preservation"] = {"token": "refrigerated", "basis": "stated"}
        acceptances = read.request["acceptances"]
        assert isinstance(acceptances, list)
        if len(acceptances) == 2:
            for fact, token, size in (
                ("tissue_state", "ex_vivo_fresh", 0.001),
                ("preservation", "refrigerated", 0.002),
            ):
                implied = implying(read, fact, token, 0.0)
                implied["implies"] = {"specimen_size": {"value": size, "unit": "m"}}
                acceptances.append(implied)
        return other, ("request_faults_apart",)
    if draw(st.booleans()):
        other["unit"] = f"{other['unit']} "
        return other, ("unit_apart",)
    at(other, "specimen")["lot"] = {"text": "a second lot", "basis": "stated"}
    return other, ("specimen_apart",)


@st.composite
def alternatives(draw: Draw, size: Size, *, nominal: bool = False) -> Example:
    """Alternatives; with `nominal`, intervals the request meets under a nominal located at the read always, a
    planned search's."""
    way = "met" if nominal else draw(st.sampled_from(ALTERNATIVE_WAYS))
    claims = draw(st.sampled_from(CLAIMS))
    if way == "broken":
        drawn = draw(results.broken_alternatives(size))
        return Example("alternatives", drawn.sources, text(drawn.request), claims, (way,))
    if nominal:
        form, drawn_read = "interval", draw(base_reads(size, FORM_FIELDS["interval"], "interval"))
    else:
        form, drawn_read = draw(results.form_reads(size))
    read = fresh(drawn_read)
    field = field_of(read)
    if draw(st.integers(0, 3)):
        results.without_origin_s_reason(field)
    shown: tuple[str, ...] = (f"form_{form}",)
    if way == "request_fault":
        conditions.disagreeing(draw, read)
    else:
        shown = draw(results.enriched(field))
    held: list[JsonValue] = [results.without_withheld_reports(copy.deepcopy(field))]
    for _ in range(draw(st.integers(1, 2))):
        other, standing = apart(draw, read, field, way)
        held.append(other)
        shown = (*shown, *(name for name in standing if name not in shown))
    record = results.holding(read, {"alternatives": held})
    read = wanting(repinned(read._replace(record=record)), a_want(draw, form))
    if form == "interval" and way == "met" and (nominal or draw(st.booleans())):
        read = wanting(read, "value")
        acceptance: JsonObject = {
            "acceptance": "nominal",
            "record": conditions.reference(read.record),
            "field": read.field,
            "value": draw(DOUBLES),
        }
        with_a_nominal(read, acceptance)
        shown = (*shown, "nominal_over_alternatives")
    return example("alternatives", read, claims, way, *shown)


# Faults of steps 8 to 10.


@st.composite
def step_8_faults(draw: Draw, size: Size, among: tuple[str, ...] = ()) -> Example:
    """A record with one or two faults of step 8's catalogue (`value_field_strategies.faulty_records`), each
    named `region.name` among what the draw planted; the first among `among` where it names some, a mutant's
    planned search."""
    faulty = draw(faulty_records(size, among=among))
    record = pinned(faulty.record)
    request: JsonObject = {
        "target": {"record": conditions.reference(record), "field": faulty.field},
        "requirement": {"want": draw(st.sampled_from(WANTS))},
    }
    claims = draw(st.sampled_from(CLAIMS))
    return Example("step_8", (results.as_source(record),), text(request), claims, faulty.faults)


@st.composite
def step_9_or_10_faults(draw: Draw, size: Size, among: tuple[str, ...] = tuple(conditions.FAULTS)) -> Example:
    """A read with a fault of steps 9 and 10, its first among `among`: all of them, or a planned search's."""
    faulty = draw(conditions.faulty_reads(among, size))
    read = wanting(faulty.read, draw(st.sampled_from(WANTS)))
    return example("steps_9_and_10", read, draw(st.sampled_from(CLAIMS)), *faulty.faults)


# Step 0's catalogue: each fault changes a base read's request in place, where the text refuses it
# (`read_side_contract.md` section 1), or, for the near misses, where it does not. Its operating conditions
# and requirement hold `measurement_dimension`, a numeric condition, and `measurement_geometry`, a token one.

RequestFault = Callable[[Draw, JsonObject], None]
DIMENSION = ("operating_conditions", "measurement_dimension")
DIMENSION_TOLERANCE = ("requirement", "conditions", "measurement_dimension")
GEOMETRY_REQUIREMENT = ("requirement", "conditions", "measurement_geometry")


def object_at(request: JsonObject, *path: str) -> JsonObject | None:
    """The object at `path`, or None where another fault of the draw has removed or replaced it."""
    value: JsonValue = request
    for step in path:
        value = value.get(step) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else None


def setting_at(*path: str, value: JsonValue) -> RequestFault:
    def change(draw: Draw, request: JsonObject) -> None:
        holder = object_at(request, *path[:-1])
        if holder is not None:
            holder[path[-1]] = copy.deepcopy(value)

    return change


def removing_at(*path: str) -> RequestFault:
    def change(draw: Draw, request: JsonObject) -> None:
        holder = object_at(request, *path[:-1])
        if holder is not None:
            holder.pop(path[-1], None)

    return change


def slipping_at(*path: str) -> RequestFault:
    """A member one slip from one the request's shape names at `path`, beside it or in its place."""

    def change(draw: Draw, request: JsonObject) -> None:
        holder = object_at(request, *path)
        if holder:
            name = draw(st.sampled_from(sorted(holder)))
            slip = slipped(name, draw(st.sampled_from(SLIP_KINDS)))
            holder[slip] = holder[name] if draw(st.booleans()) else holder.pop(name)

    return change


SLIP_KINDS = ("inserted", "deleted", "substituted", "swapped", "plural", "underscore")


def implied_with(**members: JsonValue) -> RequestFault:
    """An implied condition located at the read, a numeric value for `measurement_dimension`, with `members`
    changed."""

    def change(draw: Draw, request: JsonObject) -> None:
        target = object_at(request, "target") or {}
        implied: JsonObject = {
            "acceptance": "implied_condition",
            "record": copy.deepcopy(target.get("record")),
            "field": copy.deepcopy(target.get("field")),
            "fact": "tissue_state",
            "token": "in_vivo",
            "implies": {"measurement_dimension": {"value": 1.0, "unit": "m"}},
            "reason": "a property's",
        }
        implied.update(copy.deepcopy(members))
        acceptances = request.setdefault("acceptances", [])
        if isinstance(acceptances, list):
            acceptances.append(implied)

    return change


def nominal_with(**members: JsonValue) -> RequestFault:
    """A nominal located at the read, for its field, with `members` changed, None removing one."""

    def change(draw: Draw, request: JsonObject) -> None:
        target = object_at(request, "target") or {}
        nominal: JsonObject = {
            "acceptance": "nominal",
            "record": copy.deepcopy(target.get("record")),
            "field": copy.deepcopy(target.get("field")),
            "value": 0.0007,
            "basis": "a property's",
        }
        nominal.update(copy.deepcopy(members))
        acceptances = request.setdefault("acceptances", [])
        if isinstance(acceptances, list):
            acceptances.append({name: held for name, held in nominal.items() if held is not None})

    return change


def two_nominals_for_one_field(draw: Draw, request: JsonObject) -> None:
    """Two nominals naming the read's field, the second located at a region: refused whatever else each
    holds."""
    nominal_with()(draw, request)
    nominal_with(record=None, region="lumen")(draw, request)


NOT_NUMBERS: list[JsonValue] = ["1.0", None, True, [1.0]]


def not_a_number(draw: Draw, request: JsonObject) -> None:
    setting_at(*DIMENSION, "value", value=draw(st.sampled_from(NOT_NUMBERS)))(draw, request)


REQUEST_FAULTS: dict[str, RequestFault] = {
    "not_an_object": lambda draw, request: request.clear(),
    "target_missing": removing_at("target"),
    "field_missing": removing_at("target", "field"),
    "record_missing": removing_at("target", "record"),
    "pin_member_not_a_string": setting_at("target", "record", "version", value=1.0),
    "field_off_its_pattern": setting_at("target", "field", value="Fluid.dynamic_viscosity"),
    "field_without_its_section": setting_at("target", "field", value="dynamic_viscosity"),
    "field_unregistered": setting_at("target", "field", value="fluid.surface_tension"),
    "requirement_missing": removing_at("requirement"),
    "want_missing": removing_at("requirement", "want"),
    "want_unknown": setting_at("requirement", "want", value="values"),
    "want_not_a_string": setting_at("requirement", "want", value=1.0),
    "tolerance_below_zero": setting_at(*DIMENSION_TOLERANCE, "tolerance", "value", value=-1.0),
    "tolerance_not_a_number": setting_at(*DIMENSION_TOLERANCE, "tolerance", "value", value="0"),
    "tolerance_unit_another": setting_at(*DIMENSION_TOLERANCE, "tolerance", "unit", value="mm"),
    "tolerance_unit_not_a_string": setting_at(*DIMENSION_TOLERANCE, "tolerance", "unit", value=1.0),
    "tolerance_without_its_operating_condition": removing_at(*DIMENSION),
    "operating_conditions_not_an_object": setting_at("operating_conditions", value=[]),
    "operating_value_not_a_number": not_a_number,
    "operating_unit_another": setting_at(*DIMENSION, "unit", value="cm"),
    "operating_unit_kelvin_sign": setting_at("operating_conditions", "temperature", "unit", value="\u212a"),
    "operating_unit_not_a_string": setting_at(*DIMENSION, "unit", value={"status": "unstated"}),
    "operating_range_reversed": setting_at(*DIMENSION, value={"range": [2.0, 1.0], "unit": "m"}),
    "operating_range_of_one_number": setting_at(*DIMENSION, value={"range": [1.0], "unit": "m"}),
    "operating_value_and_range": setting_at(
        *DIMENSION, value={"value": 1.0, "range": [1.0, 2.0], "unit": "m"}
    ),
    "operating_for_a_token_condition": setting_at(
        "operating_conditions", "measurement_geometry", value={"value": 1.0, "unit": "m"}
    ),
    "tolerance_for_a_token_condition": setting_at(
        *GEOMETRY_REQUIREMENT, value={"tolerance": {"value": 1.0, "unit": "m"}}
    ),
    "accept_for_a_numeric_condition": setting_at(*DIMENSION_TOLERANCE, value={"accept": ["tube"]}),
    "accept_not_a_list": setting_at(*GEOMETRY_REQUIREMENT, "accept", value="tube"),
    "condition_not_registered": setting_at(
        "requirement", "conditions", "x_pressure", value={"tolerance": {"value": 1.0, "unit": "Pa"}}
    ),
    "operating_condition_not_registered": setting_at(
        "operating_conditions", "x_pressure", value={"value": 1.0, "unit": "Pa"}
    ),
    "requirement_holds_a_label": setting_at("requirement", "label", value="materica.fluid.newtonian.v1"),
    "requirement_holds_represents": setting_at("requirement", "represents", value="population"),
    "slip_in_the_request": slipping_at(),
    "slip_in_the_target": slipping_at("target"),
    "slip_in_the_pin": slipping_at("target", "record"),
    "slip_in_the_requirement": slipping_at("requirement"),
    "slip_in_a_tolerance": slipping_at(*DIMENSION_TOLERANCE, "tolerance"),
    "slip_in_an_operating_condition": slipping_at(*DIMENSION),
    "acceptances_not_a_list": setting_at("acceptances", value={}),
    "acceptance_of_no_kind": setting_at("acceptances", value=[{"acceptance": "waiver", "reason": "r"}]),
    "acceptance_not_an_object": setting_at("acceptances", value=[1.0]),
    "nominal_value_not_a_number": nominal_with(value="0.0007"),
    "nominal_value_missing": nominal_with(value=None),
    "nominal_field_unregistered": nominal_with(field="bulk.porosity"),
    "nominal_slip": nominal_with(vaule=0.0007),
    "two_nominals_for_one_field": two_nominals_for_one_field,
    "implied_fact_without_tokens": implied_with(fact="post_mortem_interval"),
    "implied_token_not_its_facts": implied_with(token="tube"),
    "implied_condition_not_registered": implied_with(implies={"x_pressure": {"value": 1.0, "unit": "Pa"}}),
    "implied_status_object": implied_with(implies={"measurement_dimension": {"status": "unstated"}}),
    "implied_plus_minus": implied_with(
        implies={
            "measurement_dimension": {
                "value": 1.0,
                "unit": "m",
                "plus_minus": [{"stated_as": "bound", "value": 0.0, "unit": "m"}],
            }
        }
    ),
    "implied_unit_another": implied_with(implies={"measurement_dimension": {"value": 1.0, "unit": "mm"}}),
    "implied_token_outside_its_row": implied_with(implies={"measurement_geometry": {"token": "pipe"}}),
    # Near misses, which the text reads: a tolerance of `-0`, members it ignores, a want of a claimed suite.
    "tolerance_minus_zero": setting_at(*DIMENSION_TOLERANCE, "tolerance", "value", value=-0.0),
    "unit_beside_an_accept_list": setting_at(*GEOMETRY_REQUIREMENT, "unit", value="m"),
    "member_named_nowhere": setting_at("requirement", "x_note", value="anything"),
    "nominal_for_another_field": nominal_with(field="bulk.density"),
    "nominal_basis_and_params_anything": nominal_with(basis=1.0, params={"a": 1.0}),
    "want_of_the_fits_suite": setting_at("requirement", "want", value="reference_data"),
}
# Faults that leave nothing else of the request to find, which two faults of one step never pair.
WHOLE_REQUEST = (
    "not_an_object",
    "target_missing",
    "requirement_missing",
    "operating_conditions_not_an_object",
)
# Request texts step 0 refuses before reading any member (`record_format.md` section 1 item 6).
NOT_JSON = (
    b"",
    b'{"target": ',
    b'{"a": 1, "a": 2}',
    b"\xef\xbb\xbf{}",
    b'{"x": "\\ud800"}',
    b"[" * 65 + b"]" * 65,
)


def faulted(draw: Draw, read: Read, names: tuple[str, ...]) -> Read:
    request = copy.deepcopy(read.request)
    for name in names:
        REQUEST_FAULTS[name](draw, request)
    return read._replace(request=request)


# Step 0's faults of a nominal, among which a planned search draws its first fault.
NOMINAL_REQUEST_FAULTS = tuple(sorted(name for name in REQUEST_FAULTS if "nominal" in name))


@st.composite
def request_faults(draw: Draw, size: Size, among: tuple[str, ...] = ()) -> Example:
    """One fault of step 0's catalogue, two in one draw in four, or a text that is no JSON in one in
    sixteen; with `among`, a planned search's, the first fault one of those it names, and always JSON."""
    read = draw(base_reads(size))
    claims = draw(st.sampled_from(CLAIMS))
    if not among and draw(st.integers(0, 15)) == 0:
        source = results.as_source(read.record)
        return Example("request", (source,), draw(st.sampled_from(NOT_JSON)), claims, ("not_json",))
    first = draw(st.sampled_from(among or sorted(REQUEST_FAULTS)))
    names: tuple[str, ...] = (first,)
    if draw(st.integers(0, 3)) == 0:
        names += (draw(st.sampled_from(sorted(set(REQUEST_FAULTS) - {first}))),)
    return example(
        "request", faulted(draw, wanting(read, draw(st.sampled_from(WANTS))), names), claims, *names
    )


# Two faults of one step that give two reasons, the step drawn first.

STEPS = (0, 8, 9, 10)
# Step 9's places by the condition a mismatch there carries: two of two conditions give two reasons.
UNIT_PLACES_BY_CONDITION = {
    None: ("field", "field_fact", "section_fact", "input_fact"),
    "temperature": ("condition", "plus_minus"),
    "measurement_geometry": ("token_condition",),
}
# Step 10's faults that leave the step to run its checks: two of two conditions give two reasons.
STEP_10 = ("outside", "range_outside", "not_accepted", "unchecked", "unstated", "unknown_name", "uncertain")


@st.composite
def two_faults_of_one_step(draw: Draw, size: Size) -> Example:
    step = draw(st.sampled_from(STEPS))
    claims = draw(st.sampled_from(CLAIMS))
    if step == 8:
        drawn = draw(faulty_records(size, faults=2, two_codes=True))
        record = pinned(drawn.record)
        request: JsonObject = {
            "target": {"record": conditions.reference(record), "field": drawn.field},
            "requirement": {"want": "value"},
        }
        return Example(
            "two_of_one_step", (results.as_source(record),), text(request), claims, ("step_8", *drawn.faults)
        )
    read = fresh(draw(base_reads(size)))
    if step == 0:
        first = draw(st.sampled_from(sorted(set(REQUEST_FAULTS) - set(WHOLE_REQUEST))))
        second = draw(st.sampled_from(sorted(set(REQUEST_FAULTS) - {first, *WHOLE_REQUEST})))
        return example(
            "two_of_one_step", faulted(draw, read, (first, second)), claims, "step_0", first, second
        )
    if step == 9:
        held = draw(
            st.lists(st.sampled_from(list(UNIT_PLACES_BY_CONDITION)), min_size=2, max_size=2, unique=True)
        )
        names = tuple(f"unit_{draw(st.sampled_from(UNIT_PLACES_BY_CONDITION[each]))}" for each in held)
    else:
        first = draw(st.sampled_from(STEP_10))
        group = conditions.FAULTS[first].group
        names = (
            first,
            draw(st.sampled_from([name for name in STEP_10 if conditions.FAULTS[name].group != group])),
        )
    for name in names:
        conditions.FAULTS[name].change(draw, read)
    return example("two_of_one_step", repinned(read), claims, f"step_{step}", *names)


# Reads that end before step 8.

EARLY_WAYS = ("before_step_4", "step_5", "step_7", "stores")


@st.composite
def ends_early(draw: Draw, size: Size) -> Example:
    way = draw(st.sampled_from(EARLY_WAYS))
    if way == "stores":
        world = draw(stores.worlds())
        return Example("ends_early", world.sources, text(world.request), world.claims, (way, world.case))
    builder = {
        "before_step_4": results.before_step_4,
        "step_5": results.at_step_5,
        "step_7": results.at_step_7,
    }
    drawn: results.Drawn = draw(builder[way](size))
    request = results.with_want(drawn.request, draw(st.sampled_from(WANTS)))
    return Example("ends_early", drawn.sources, text(request), draw(st.sampled_from(CLAIMS)), (way,))


# The rules the model's case-agreement leaves unpinned (`tests/reference/README.md`, "The mutant table"), and
# the open point the implementation and the model read differently: open point 1's record half, a record
# condition holding a member of the other kind. Its request half, and a slip of a name a declaration gives a
# requirement, the text decides, and both read them alike (the fix round of S2a-4's review, and the
# maintainer's ruling of 2026-10-18 for the request half).

OPEN_POINTS = ("members_of_the_other_kind",)
OTHER_KIND: dict[str, tuple[str, JsonValue]] = {
    "temperature": ("token", "tube"),
    "measurement_geometry": ("value", 1.0),
}
# In an implied condition's `implies`, a member of the other kind's shape, or one slip from one, beside a
# value of the condition's own kind.
IMPLIED_OTHER_KIND: dict[str, list[JsonObject]] = {
    "temperature": [{"token": "tube"}, {"tokens": "tube"}, {"tokn": "tube"}],
    "measurement_geometry": [
        {"value": 1.0},
        {"range": [1.0, 2.0]},
        {"unit": "m"},
        {"valeu": 1.0},
        {"units": "m"},
    ],
}


def plural_of_two_characters(draw: Draw, read: Read) -> None:
    """A member a place names made plural by `es`, or, in one draw in two, a final `y` by `ies`, in a name
    that ends in `y` (`body` at the envelope, or an uncertainty in the statistics block): one slip
    (`record_format.md` section 10), which no single character inserted, deleted or substituted makes."""
    field = field_of(read)
    places = {
        "field": field,
        "statistics": at(field, "statistics"),
        "provenance": at(field, "provenance"),
        "condition": at(field, "conditions", "measurement_dimension"),
        "envelope": read.record,
    }
    if draw(st.booleans()):
        ending_in_y = [
            (holder, name) for holder, place in places.items() for name in place if name.endswith("y")
        ]
        holder, name = draw(st.sampled_from(sorted(ending_in_y)))
        places[holder][name[:-1] + "ies"] = copy.deepcopy(places[holder][name])
        return
    place = places[draw(st.sampled_from(["field", "statistics", "provenance", "condition"]))]
    name = draw(st.sampled_from(sorted(name for name in place if not name.endswith("y"))))
    place[name + "es"] = copy.deepcopy(place[name])


OFF_ROW_MEMBERS: list[JsonValue] = [{}, [], 1.0, {"lower": "x"}, {"components": [{"fraction": "x"}]}]


def form_off_its_row(draw: Draw, read: Read) -> None:
    """A form the field's row does not allow, its own member well formed or not, which the read neither uses
    nor checks (`read_side_contract.md` section 3, step 8)."""
    field = field_of(read)
    others = sorted(
        set(("table", "interval", "composition", "evidence")) - set(VOCABULARY.fields[read.field].forms)
    )
    form = draw(st.sampled_from(others or ["spline"]))
    field["form"] = form
    field[form] = draw(st.sampled_from(OFF_ROW_MEMBERS))
    if draw(st.booleans()):
        del field["value"]


def composition_basis_off_its_row(draw: Draw, read: Read) -> None:
    """The base field moved to `bulk.elemental_composition` as a composition whose basis its row does not
    allow, its components broken: refused as a form the row does not allow is."""
    field = field_of(read)
    section, _, name = read.field.partition(".")
    del at(read.record, "body", "sections", section, "fields")[name]
    field.pop("value")
    field.pop("label", None)
    field["form"] = "composition"
    field["unit"] = "1"
    basis = draw(st.sampled_from(["volume_fraction", "mole_fraction"]))
    field["composition"] = {"basis": basis, "sum_rule": "partial", "components": [{"fraction": "x"}]}
    bulk = at(read.record, "body", "sections").setdefault("bulk", {"fields": {}})
    assert isinstance(bulk, dict)
    at(bulk, "fields")["elemental_composition"] = field
    at(read.request, "target")["field"] = "bulk.elemental_composition"


def broken_status_object(draw: Draw, read: Read) -> None:
    """A status object holding a token the reader does not know that breaks its shape."""
    field = field_of(read)
    broken: JsonObject = {"status": "x_unknown"}
    broken.update(draw(st.sampled_from([{"value": 1.0}, {"reason": 1.0}, {"reasons": "x"}, {"note": "x"}])))
    place = draw(st.sampled_from(["sd", "relative_uncertainty", "condition", "fact"]))
    if place == "condition":
        at(field, "conditions")["measurement_dimension"] = broken
    elif place == "fact":
        at(field, "specimen")["post_mortem_interval"] = broken
    else:
        at(field, "statistics")[place] = broken


def alternatives_slip_beside(draw: Draw, read: Read) -> None:
    """A member one slip from `alternatives` beside a value field's members (open point
    `alternatives_named_at_a_field`, which the two read alike)."""
    field_of(read)[
        draw(st.sampled_from(["alternative", "alternativess", "alternatives_", "altenratives"]))
    ] = []


def other_kind(draw: Draw, read: Read) -> None:
    """Open point `members_of_the_other_kind`: a numeric condition holding `token`, or a token condition
    holding `value`."""
    name = draw(st.sampled_from(sorted(OTHER_KIND)))
    member, value = OTHER_KIND[name]
    at(field_of(read), "conditions", name)[member] = value


def implied_member_of_the_other_kind(draw: Draw, read: Read) -> None:
    """Open point 1's request half, which the text decides (`read_side_contract.md` section 1, "It breaks
    its shape too", the maintainer's ruling of 2026-10-18) and both read alike: an implied condition located
    at the read that gives a numeric condition a `token`, or a token condition a `value`, `range` or `unit`,
    or a member one slip from one, is refused at step 0 with that condition."""
    in_vivo(read)
    implied = implying(read, "tissue_state", "in_vivo", 310.15)
    name = draw(st.sampled_from(sorted(IMPLIED_OTHER_KIND)))
    own: JsonObject = {"value": 310.15, "unit": "K"} if name == "temperature" else {"token": "tube"}
    implied["implies"] = {name: {**own, **copy.deepcopy(draw(st.sampled_from(IMPLIED_OTHER_KIND[name])))}}
    read.request["acceptances"] = [implied]


def declaration_name_slip(draw: Draw, read: Read) -> None:
    """A member one slip from `field` in a requirement, or from `reason` or `consequence` in a requirement
    condition, which `declarations.md` section 1 names there: refused, as the text says (S2a-4's review, M1),
    and both read it alike."""
    if draw(st.booleans()):
        at(read.request, "requirement")[draw(st.sampled_from(["fields", "feld", "fiedl"]))] = "x"
    else:
        name = draw(st.sampled_from(["reasons", "reaso", "consequences", "consequense"]))
        at(read.request, "requirement", "conditions", "temperature")[name] = "x"


def declaration_names_held(draw: Draw, read: Read) -> None:
    """`field` in a requirement, and `reason` and `consequence` in a requirement condition, which a read
    ignores, as the two agree."""
    at(read.request, "requirement")["field"] = read.field
    held = at(read.request, "requirement", "conditions", "temperature")
    held["reason"] = "viscosity falls about 2 % per kelvin"
    held["consequence"] = "1 K moves drag by about 2 %"


def review_of_both_shapes(draw: Draw, read: Read) -> None:
    """A review holding members of both shapes `provenance.md` section 2 item 6 reads: a reviewed review
    beside a status object's `reason`, which a result leaves out, since a reviewed review names none; or one
    holding both `status` and `result`, which reads as `{"status": "not_checked"}`."""
    provenance = at(field_of(read), "provenance")
    if draw(st.booleans()):
        provenance["review"] = {"result": "reviewed", "reason": "a status object's", "date": "2026-10-17"}
    else:
        provenance["review"] = {"status": "not_checked", "reason": "not yet", "result": "reviewed"}


def implied_zero_beside_minus_zero(draw: Draw, read: Read) -> None:
    """Two implied conditions supplying `0` and `-0`, or a value and the range `[v, v]`: they disagree."""
    in_vivo(read)
    first: JsonObject = implying(read, "tissue_state", "in_vivo", 0.0)
    second: JsonObject = implying(read, "disease_and_treatment_state", "normal", -0.0)
    if draw(st.booleans()):
        value = draw(DOUBLES)
        at(first, "implies")["temperature"] = {"value": value, "unit": "K"}
        at(second, "implies")["temperature"] = {"range": [value, value], "unit": "K"}
    read.request["acceptances"] = [first, second]


def another_forms_member_slipped(draw: Draw, read: Read) -> None:
    """A member one slip from another form's own member beside a constant, which names `value` alone at its
    place (`record_format.md` section 5): ignored, as a member the reader does not know. Fuzz target 4 found
    the model refusing it."""
    field_of(read)[draw(st.sampled_from(["tablW", "intervals", "compositon", "evidenc", "power_lav"]))] = 1.0


def checks_beside_a_broken_object(draw: Draw, read: Read) -> None:
    """A token the reader does not know beside a fault of the object that holds it, both of which step 8
    checks (`read_side_contract.md` section 2 item 2, "Each step makes all its checks"): a population level's
    unknown `level` beside a slip of `within`, or an uncertainty's `dof` held as a status object of an unknown
    token under a Student's t distribution, which wants a number; or a `plus_minus` entry whose `stated_as`
    holds a status token the reader does not know, beside an entry of a stated kind, which is no entry of
    unstated kind (`provenance.md` section 6.1 item 6). Fuzz target 4 found the model reading the three
    otherwise."""
    statistics = at(field_of(read), "statistics")
    way = draw(st.sampled_from(["population_level", "dof", "plus_minus"]))
    if way == "population_level":
        statistics["represents"] = "population"
        statistics["population_level"] = {"level": "patient", "w[thin": {"status": "none"}}
    elif way == "plus_minus":
        at(field_of(read), "conditions", "measurement_dimension")["plus_minus"] = [
            {"stated_as": {"status": "x_unknown"}, "value": 0.0, "unit": "m"},
            {"stated_as": "sd", "value": 0.0, "unit": "m"},
        ]
    else:
        statistics["expanded_uncertainty"] = {
            "value": 4e-06,
            "coverage_factor": 2.3,
            "distribution": "student_t",
            "dof": {"status": "x_unknown"},
            "basis": "reported_uncertainty",
            "represents": "estimate",
        }


PLANTS: dict[str, Callable[[Draw, Read], None]] = {
    "plural_of_two_characters": plural_of_two_characters,
    "checks_beside_a_broken_object": checks_beside_a_broken_object,
    "another_forms_member_slipped": another_forms_member_slipped,
    "form_off_its_row": form_off_its_row,
    "composition_basis_off_its_row": composition_basis_off_its_row,
    "broken_status_object": broken_status_object,
    "alternatives_slip_beside": alternatives_slip_beside,
    "implied_zero_beside_minus_zero": implied_zero_beside_minus_zero,
    "declaration_names_held": declaration_names_held,
    "review_of_both_shapes": review_of_both_shapes,
    "members_of_the_other_kind": other_kind,
    "implied_member_of_the_other_kind": implied_member_of_the_other_kind,
    "names_a_declaration_gives_a_requirement": declaration_name_slip,
}


@st.composite
def unpinned(draw: Draw, size: Size) -> Example:
    name = draw(st.sampled_from(sorted(PLANTS)))
    read = fresh(draw(base_reads(size)))
    PLANTS[name](draw, read)
    return example("unpinned", repinned(read), draw(st.sampled_from(CLAIMS)), name)


BUILDERS: dict[str, Callable[[Size], st.SearchStrategy[Example]]] = {
    "valued": valued,
    "alternatives": alternatives,
    "step_8": step_8_faults,
    "steps_9_and_10": step_9_or_10_faults,
    "two_of_one_step": two_faults_of_one_step,
    "request": request_faults,
    "ends_early": ends_early,
    "unpinned": unpinned,
}
KINDS = tuple(BUILDERS)


@st.composite
def drawn(draw: Draw, size: Size, kinds: tuple[str, ...] = KINDS) -> Example:
    """A read of one of `kinds`, the kind drawn first."""
    example_: Example = draw(BUILDERS[draw(st.sampled_from(kinds))](size))
    return example_
