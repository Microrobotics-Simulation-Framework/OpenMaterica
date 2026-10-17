# SPDX-License-Identifier: Apache-2.0
"""(8) Step 8's laws (`read_side_contract.md` section 3, step 8), over records holding a constant, an interval
or a composition drawn from `value_field_strategies.py`. The mutants they kill are in
`test_value_field_mutants.py`.

- **HP3, one fault, one refusal.** A field that passes step 8, given one fault of the catalogue, is refused
  with exactly the codes the fault's rule gives and no other, `not_met`; given a fault that breaks no rule
  step 8 checks (a condition name the reader does not know, a member it does not check, broken), it still
  passes. In a quarter of the draws, two faults of two regions give the codes of both: each step makes all its
  checks.
- **The label's rule** (`record_format.md` section 4.1, "Labels"): the row's label goes on a constant, and on
  a table whose axis is not the condition its Label cell names, and on no other form. A read reaches a label
  on a table only once S3 reads tables, so the property calls step 8's shared check of a field's members,
  `value_shapes.field_problems`, as `fields.form_problems` calls it; its oracle reads the Label column itself.
- **HP5, ignorance.** Members the reader does not know, added where they may go, never change the outcome,
  whether the field passes step 8 or a fault refuses it: a name more than one slip from every member named at
  its place is ignored, two slips off included. The pin is recomputed. As the S2 design says, no member is
  added to a `conditions` map, where a new name is a condition, nor to a status object.

A read that passes step 8 is refused at step 9 or 10, which a drawn field's units and conditions decide, or
goes on to steps 11 to 13, which give a drawn field's own member under the `want` its form gives: either is
the outcome "past step 8".
"""

import copy
import json
import re
from typing import NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core import value_shapes
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.vocabulary import VOCABULARY
from scripts.gen_vocabulary import SPECIFICATION
from tests.property import records
from tests.property.condition_oracle import AFTER_STEP_8
from tests.property.strategies import SIZE, Size
from tests.property.support import feature
from tests.property.value_field_strategies import (
    REGION_FORMS,
    REGIONS,
    WANTS,
    Example,
    JsonObject,
    faulty_records,
    fields,
    pinned,
    valid_records,
)

PAST_STEP_8 = "past step 8"


class Outcome(NamedTuple):
    status: str  # the result's, or PAST_STEP_8
    codes: frozenset[str]


def want_of(record: JsonObject, field: str) -> str:
    """The `want` that gives the own member of the form `field` holds in `record`, `value` where it holds
    none step 8 reads (`read_side_contract.md` section 6)."""
    section, _, name = field.partition(".")
    found: JsonValue = record
    for step in ("body", "sections", section, "fields", name, "form"):
        found = found.get(step) if isinstance(found, dict) else None
    return WANTS.get(found, "value") if isinstance(found, str) else "value"


def outcome(record: JsonObject, field: str) -> Outcome:
    """The read of `field` in `record`, pinned by its recomputed hash, under the `want` its form gives."""
    record = pinned(record)
    store = RecordStore()
    store.add("record", json.dumps(record).encode())
    pin = {member: record[member] for member in ("id", "version", "content_hash")}
    requirement: JsonObject = {"want": want_of(record, field)}
    request: JsonObject = {"target": {"record": pin, "field": field}, "requirement": requirement}
    try:
        result = read(request, store)
    except NotImplementedError:
        return Outcome(PAST_STEP_8, frozenset())
    codes = frozenset(reason.code for reason in result.reasons)
    return Outcome(PAST_STEP_8, frozenset()) if codes <= AFTER_STEP_8 else Outcome(result.status, codes)


# HP3: one fault, one refusal.


def check_one_fault(example: Example) -> None:
    found = outcome(example.record, example.field)
    expected = Outcome("not_met", example.expected) if example.expected else Outcome(PAST_STEP_8, frozenset())
    assert found == expected, example.faults


def form_feature(example: Example) -> None:
    feature(f"form_{example.form}")


def fault_features(example: Example) -> None:
    feature(f"region_{example.faults[0].partition('.')[0]}")
    form_feature(example)
    feature("two_faults", len(example.faults) == 2)
    feature("passes", not example.expected)
    feature("unknown_token", "unknown_token" in example.expected)
    feature("two_codes", len(example.expected) == 2)


# HP3 draws its first fault among a part of the regions, the regions taken in turn, each part a property of
# its own; `region_<region>` is the region of an example's first fault. Drawn among all 21 regions, after the
# record, a region was the first fault's in 1.7% to 24% of examples at `ci` (2026-10-15), too seldom for the
# feature audit to judge it there (`audits.draw_floor`): from the measured clusters, the least shares of 14
# regions failed a `ci` run with a probability of 1.2e-6 to 1.3e-3 each, about 4.7e-3 in all (at most 5.8e-3),
# and one failed in 64 runs. In a part, each region is declared by its chance: its share at `ci` over 64 runs,
# rounded down to two places, at least 7/8 of an even share among the part's regions (the draws of one fault,
# and of two faults the first) and more for those holding token faults, which the draws of two faults that
# give two codes take first. A part's regions now fall below their draw floors at `ci` with a probability of
# about 1e-8 in all.
# The forms' own regions are a part of their own, S2b-1's, so that the first two parts and their measured
# chances stand as they were.
OWN_REGIONS = tuple(region for region in REGIONS if region in REGION_FORMS)
SHARED_REGIONS = tuple(region for region in REGIONS if region not in REGION_FORMS)
HP3_PARTS = (SHARED_REGIONS[0::2], SHARED_REGIONS[1::2], OWN_REGIONS)
HP3_CHANCES = {
    "statistics_tokens": 0.18,
    "statistics_numbers": 0.08,
    "statistics_statuses": 0.09,
    "statistics_members": 0.08,
    "statistics_slips": 0.07,
    "statistics_slips_beside": 0.08,
    "uncertainty": 0.07,
    "uncertainty_tokens": 0.15,
    "conditions": 0.07,
    "condition_tokens": 0.12,
    "specimen": 0.08,
    "specimen_tokens": 0.09,
    "section_specimen": 0.07,
    "provenance": 0.09,
    "derivation": 0.07,
    "derivation_inputs": 0.08,
    "field": 0.09,
    "field_slips": 0.08,
    "field_slips_optional": 0.07,
    "field_form": 0.08,
    "record": 0.07,
    # S2b-1's part, each at its least share over 48 runs at `ci` (seeds 5001 to 5048, 2026-10-17, PR #37's
    # review, L4), rounded down, below its nominal chance: 7/8 of a fifth, and the token regions an eighth of
    # their share of the part's eight token faults beside it (interval_tokens and composition_tokens 0.21,
    # component 0.24). Measured means 0.17 to 0.24, least shares 0.128 to 0.196; from the measured clusters,
    # the part's regions fall below their draw floors with a probability below 1e-15 a run.
    "interval": 0.12,
    "interval_tokens": 0.16,
    "composition": 0.13,
    "composition_tokens": 0.14,
    "component": 0.19,
}
# A part's drawn field's form, by its chance: the shared parts draw a constant as often as an interval and a
# composition together, and the third takes its region's form. Over 48 runs of each part at `ci` (seeds 5001
# to 5048, 2026-10-17, PR #37's review, L4), the first two parts' means 0.50, 0.24 to 0.25 and 0.25, their
# least shares 0.446, 0.199 and 0.205, and the third's means 0.38 and 0.62, least shares 0.334 and 0.554; each
# declared at the lesser part's least share, rounded down, below its nominal chance (0.5, 0.25, 0.25; 0.38,
# 0.62). From the measured clusters, each falls below its draw floor with a probability below 1e-17 a run.
FORM_CHANCES = (
    {"form_constant": 0.44, "form_interval": 0.19, "form_composition": 0.2},
    {"form_constant": 0.44, "form_interval": 0.19, "form_composition": 0.2},
    {"form_interval": 0.33, "form_composition": 0.55},
)
# Least shares, about a third of those measured at `ci` and `deep` with HP3 whole (S2a-2's fix round); in each
# part they fail a `ci` run with a probability below 1e-9 (measured 2026-10-15).
HP3_FEATURES = {"two_faults": 0.045, "unknown_token": 0.055, "two_codes": 0.036, "passes": 0.003}


def part_chances(part: int) -> dict[str, float]:
    return {**{f"region_{region}": HP3_CHANCES[region] for region in HP3_PARTS[part]}, **FORM_CHANCES[part]}


@pytest.mark.chances(**part_chances(0))
@pytest.mark.features(**HP3_FEATURES)
@given(faulty_records(regions=HP3_PARTS[0]))
def test_one_fault_gives_its_refusal_and_no_other_part_1(example: Example) -> None:
    fault_features(example)
    check_one_fault(example)


@pytest.mark.chances(**part_chances(1))
@pytest.mark.features(**HP3_FEATURES)
@given(faulty_records(regions=HP3_PARTS[1]))
def test_one_fault_gives_its_refusal_and_no_other_part_2(example: Example) -> None:
    fault_features(example)
    check_one_fault(example)


@pytest.mark.chances(**part_chances(2))
@pytest.mark.features(**HP3_FEATURES)
@given(faulty_records(regions=HP3_PARTS[2]))
def test_one_fault_gives_its_refusal_and_no_other_part_3(example: Example) -> None:
    """The forms' own members: an interval's, a composition's and a component's faults, S2b-1's."""
    fault_features(example)
    check_one_fault(example)


def check_passes(example: Example) -> None:
    assert outcome(example.record, example.field) == Outcome(PAST_STEP_8, frozenset())


@given(valid_records())
def test_a_field_without_a_fault_passes_step_8(example: Example) -> None:
    """The base of every draw passes step 8: without it, HP3's refusals could come from the base."""
    check_passes(example)


# The label's rule.

# A Label cell: the label, on a constant, and perhaps on a table whose axis is not a condition.
LABEL_CELL = re.compile(
    r"^\| `([a-z_]+\.[a-z_]+)` \|.* \| `([a-z0-9_.]+)` on a constant"
    r"(?:, or on a table whose axis is not `([a-z_]+)`)? \|$",
    re.M,
)


def label_rows(text: str) -> dict[str, str | None]:
    """Each field the Label column of `record_format.md` section 4.1 gives a label, and the condition a
    table's axis must not be for the label to go on it, or None where it goes on a constant alone."""
    return {found[1]: found[3] for found in LABEL_CELL.finditer(text)}


LABEL_AXES = label_rows((SPECIFICATION / "record_format.md").read_text(encoding="utf-8"))
NUMERIC = tuple(sorted(name for name, spec in VOCABULARY.conditions.items() if spec.shape == "numeric"))


class Labelled(NamedTuple):
    field: str
    value: JsonObject
    form: str
    axis: str | None  # a table's axis


@st.composite
def labelled_fields(draw: st.DrawFn, size: Size = SIZE) -> Labelled:
    """A field the row gives a label, holding it, as a constant, a table on its row's axis or another numeric
    condition, or an interval."""
    name, value = draw(fields(size, tuple(sorted(LABEL_AXES))))
    form = draw(st.sampled_from(["constant", "table", "table", "interval"]))
    axis = draw(st.sampled_from([LABEL_AXES[name] or NUMERIC[0], *NUMERIC])) if form == "table" else None
    value = {**value, "form": form, "label": VOCABULARY.fields[name].label}
    if axis is not None:
        value["table"] = {"axis": axis}
    return Labelled(name, value, form, axis)


def check_label(labelled: Labelled) -> None:
    rule = LABEL_AXES[labelled.field]
    on_a_table = labelled.form == "table" and rule is not None and labelled.axis != rule
    allowed = labelled.form == "constant" or on_a_table
    found = value_shapes.field_problems(labelled.value, VOCABULARY.fields[labelled.field], labelled.form)
    assert {reason.code for reason in found} == (set() if allowed else {"form_invalid"}), labelled


@pytest.mark.features(
    on_a_constant=0.15, on_its_tables_axis=0.039, on_another_axis=0.05, on_an_interval=0.029
)
@given(labelled_fields())
def test_a_label_goes_where_its_row_says(labelled: Labelled) -> None:
    on_its_axis = labelled.axis is not None and labelled.axis == LABEL_AXES[labelled.field]
    feature("on_a_constant", labelled.form == "constant")
    feature("on_its_tables_axis", on_its_axis)
    feature("on_another_axis", labelled.axis is not None and not on_its_axis)
    feature("on_an_interval", labelled.form == "interval")
    check_label(labelled)


def test_the_label_column_is_read_and_a_cell_of_another_form_is_not() -> None:
    assert LABEL_AXES == {
        "fluid.dynamic_viscosity": "shear_rate",
        "magnetic.volume_susceptibility": "magnetic_flux_density",
    }
    cell = "| `fluid.x` | `1` | constant | none | `materica.fluid.x.v1` on an interval |"
    assert label_rows(cell) == {}


# HP5: ignorance.

# Where a member is added, by the kind of place: an object of the record's structure, the field, an object
# inside it, or one inside a member step 8 does not check.
UNCHECKED = frozenset({"extraction", "assistance", "review", "fit", "evidence", "document", "locator"})


Place = tuple[str | int, ...]


class Unknowns(NamedTuple):
    example: Example
    additions: tuple[tuple[Place, str, JsonValue], ...]  # place, name, value


def places(value: JsonValue, here: Place = ()) -> list[Place]:
    """The objects in `value` a member may be added to: every one but a `conditions` map and a status
    object, a list's items among them (a component, a derivation's input)."""
    if isinstance(value, list):
        return [place for index, item in enumerate(value) for place in places(item, (*here, index))]
    if not isinstance(value, dict):
        return []
    found: list[Place] = [] if "status" in value or here[-1:] == ("conditions",) else [here]
    for name, member in value.items():
        found += places(member, (*here, name))
    return found


def at(value: JsonValue, place: Place) -> JsonValue:
    for step in place:
        if isinstance(step, int):
            assert isinstance(value, list)
            value = value[step]
        else:
            assert isinstance(value, dict)
            value = value[step]
    return value


def place_kind(place: Place) -> str:
    if UNCHECKED & set(place):
        return "unchecked"
    if len(place) <= 4:
        return "structure"
    return "field" if len(place) == 5 else "inside_the_field"


def in_an_own_member(place: Place) -> bool:
    """Inside an interval's or a composition's own member, a component included."""
    return place[5:6] in (("interval",), ("composition",))


@st.composite
def with_unknowns(draw: st.DrawFn, size: Size = SIZE) -> Unknowns:
    """A valid record, or in one draw in three one with a fault, and one to four members added, each named
    `x_` and letters or, in one draw in three, a member at its place with two characters added."""
    faulty = draw(st.integers(0, 2)) == 0
    example = draw(faulty_records(size, faults=1) if faulty else valid_records(size))
    where = places(example.record)
    additions: list[tuple[Place, str, JsonValue]] = []
    for _ in range(draw(st.integers(1, 4))):
        place = draw(st.sampled_from(where))
        found = at(example.record, place)
        present = sorted(found) if isinstance(found, dict) else []
        if present and draw(st.integers(0, 2)) == 0:
            name = draw(st.sampled_from(present)) + "xx"
        else:
            name = "x_" + draw(st.text("abcdefghij", min_size=1, max_size=6))
        additions.append((place, name, draw(records.trees(size).values)))
    return Unknowns(example, tuple(additions))


def check_ignored(unknowns: Unknowns) -> None:
    example = unknowns.example
    record = copy.deepcopy(example.record)
    for place, name, value in unknowns.additions:
        held = at(record, place)
        assert isinstance(held, dict)
        held[name] = copy.deepcopy(value)
    assert outcome(record, example.field) == outcome(example.record, example.field)


# `faulty_base` is declared by its chance: its share at `ci` over 64 runs (2026-10-15), rounded down to two
# places. From the measured clusters, its least share failed a `dev` run with a probability of about 1.9e-3
# (at most 4.5e-3); it is not judged at `dev` now, and at `ci` falls below its draw floor with a probability
# below 1e-15. S2b-1 added places in lists and own members, and over 48 runs at `ci` (2026-10-17, PR #37's
# review, M3) `field` fell to 0.099 of the additions on average (0.066 the least), where its least share,
# 0.045, failed a run with a probability of 2.1e-5 (renewal: 1.6e-5), and `in_an_own_member` showed 0.084
# (0.054 the least), where 0.025 failed one with 2.7e-7. Each declared at about a third of its mean share,
# 0.03 and 0.02, they fail a `ci` run with 1.4e-8 and 1.1e-8 (renewal 9e-9 and 8e-9). Neither can be declared
# by its chance: at 0.06 and 0.05, their floors are below `audits.LEAST_DRAWS`.
@pytest.mark.chances(faulty_base=0.33)
@pytest.mark.features(
    structure=0.25,
    field=0.03,
    inside_the_field=0.11,
    unchecked=0.065,
    two_slips=0.23,
    in_an_own_member=0.02,
)
@given(with_unknowns())
def test_members_the_reader_does_not_know_change_nothing(unknowns: Unknowns) -> None:
    for place, name, _ in unknowns.additions:
        feature(place_kind(place))
        feature("in_an_own_member", in_an_own_member(place))
        feature("two_slips", name.endswith("xx"))
    feature("faulty_base", bool(unknowns.example.faults))
    check_ignored(unknowns)
