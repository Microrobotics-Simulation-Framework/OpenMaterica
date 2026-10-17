# SPDX-License-Identifier: Apache-2.0
"""(14) Information monotonicity (the maintainer's "more checks of the same kind", 2026-10-14): the relations
of the fail-closed spike's check 1 that S2's forms reach, each a change of a world and what it may do to the
read (`monotonicity_strategies.py`), restricted exactly as the spike's limits say. Information lost never
helps (N), information added never hurts (P), and some changes must degrade (S); S5 is an exact oracle, which
no relation can be for a comparison made in floating point.

- N1r: removing a condition never turns `unknown` or `not_met` into `met`, for one the row requires, another
  requires with its token, or the request names, and no implied condition fills (`read_side_contract.md`
  section 5; `declarations.md` section 4.1).
- N2: removing a provenance member never does; N3r: a member made a status object never does, but `unstated`
  where an implied condition fills it; N4: adding a plus or minus never does; N5r: narrowing a tolerance
  never does, a field without alternatives (the worlds hold none); N6: removing an operating condition never
  does, from a request that passed step 0 (every world's does).
- N8: adding an implied condition never turns `not_met` into `met`.
- P1: widening a tolerance never turns `met` into `not_met`; P2: removing a plus or minus never makes `met`
  worse; P3: adding a token to an accept list never turns `met` into `not_met`; P4: adding an operating value
  with no tolerance never changes the status (no table reads one here).
- S1: a positive `sd` or unstated plus or minus on a condition section 5 finds met makes its entry
  `unknown`; S2: a stated condition made a status object, but `unstated` where an implied condition fills
  it, makes its entry `unknown` or the read `not_met`; S5: each stated entry without a plus or minus is the
  one section 5's row gives on the exact values, the temperature at one of its boundaries in half the draws.

Relations over tables, picks and alternatives set aside (N7r, P5 to P7, S3, S4) are S3's and S4's. The
unrestricted twins N1 and N3 do not hold, by design: the mutant searches show each failing on the
implementation, on N1r's and N3r's own draws, by the ways that hold their counterexamples, so that draws
that lost those shapes are seen (`test_monotonicity_mutants.py`); and an audit of the worlds every relation
draws sees worlds that lost them.
"""

import json
from collections.abc import Callable, Mapping
from typing import NamedTuple

import pytest
from hypothesis import given

from materica.core.read import read
from materica.core.record import RecordStore
from materica.core.status import ReadStatus
from tests.property import monotonicity_strategies as strategies
from tests.property.monotonicity_strategies import Drawn, JsonObject, World
from tests.property.strategies import SIZE
from tests.property.support import feature


class Verdict(NamedTuple):
    status: ReadStatus
    entries: Mapping[str, str] | None  # each condition entry's status, where step 10 ran to its end


def verdict(world: World) -> Verdict | None:
    """The implementation's read of `world`, or None where a step not built yet decides it."""
    store = RecordStore()
    store.add("record", json.dumps(world.record).encode())
    try:
        result = read(world.request, store, claims=world.claims)
    except NotImplementedError:
        return None
    except Exception as error:
        raise AssertionError(f"the read raised {error!r}") from error
    entries = None if result.conditions is None else {entry.name: entry.status for entry in result.conditions}
    return Verdict(result.status, entries)


def always(facts: JsonObject) -> bool:
    return True


class Relation(NamedTuple):
    change: str  # a key of `monotonicity_strategies.CHANGES`
    kind: str
    applies: Callable[[JsonObject], bool] = always


def checked_and_not_implied(facts: JsonObject) -> bool:
    return bool(facts["checked"]) and not facts["implied"]


def not_unstated_under_an_implied_condition(facts: JsonObject) -> bool:
    return not (facts["implied"] and facts["token"] == "unstated")


RELATIONS: dict[str, Relation] = {
    "N1r": Relation("remove_condition", "never_met", checked_and_not_implied),
    "N2": Relation("remove_provenance_member", "never_met"),
    "N3r": Relation("status_object", "never_met", not_unstated_under_an_implied_condition),
    "N4": Relation("add_plus_minus", "never_met"),
    "N5r": Relation("narrow_tolerance", "never_met"),
    "N6": Relation("remove_operating", "never_met"),
    "N8": Relation("add_implied", "never_not_met_to_met"),
    "P1": Relation("widen_tolerance", "never_not_met"),
    "P2": Relation("remove_plus_minus", "never_worse"),
    "P3": Relation("add_accept_token", "never_not_met"),
    "P4": Relation("add_operating", "unchanged"),
    "S1": Relation("add_uncertain_plus_minus", "degrades_entry"),
    "S2": Relation("stated_to_status", "degrades_entry"),
    "S5": Relation("at_a_boundary", "oracle"),
}


def check_relation(name: str, drawn: Drawn) -> str:
    """Whether `drawn` holds relation `name`: "n/a" where its change does not apply, "no_verdict" where a
    step not built decides either read, "vacuous" where the base is not where the relation speaks, "held"
    where it holds; an AssertionError where it does not."""
    relation = RELATIONS[name]
    if drawn.changed is None or not relation.applies(drawn.changed.facts):
        return "n/a"
    if relation.kind == "oracle":
        return exactness(drawn.changed.world, verdict(drawn.changed.world))
    before = verdict(drawn.base)
    after = verdict(drawn.changed.world)
    if before is None or after is None:
        return "no_verdict"
    said = f"{name}: {drawn.changed.facts}; before {before}, after {after}"
    if relation.kind == "never_met":
        if before.status == "met":
            return "vacuous"
        assert after.status != "met", f"became met. {said}"
    elif relation.kind == "never_not_met_to_met":
        if before.status != "not_met":
            return "vacuous"
        assert after.status != "met", f"not_met became met. {said}"
    elif relation.kind == "never_not_met":
        if before.status != "met":
            return "vacuous"
        assert after.status != "not_met", f"met became not_met. {said}"
    elif relation.kind == "never_worse":
        if before.status != "met":
            return "vacuous"
        assert after.status == "met", f"met became worse. {said}"
    elif relation.kind == "unchanged":
        assert after.status == before.status, f"the status changed. {said}"
    else:
        condition = str(drawn.changed.facts["condition"])
        if after.entries is None or condition not in after.entries:
            return "vacuous"
        assert after.entries[condition] == "unknown" or after.status == "not_met", f"not degraded. {said}"
    return "held"


def exactness(world: World, before: Verdict | None) -> str:
    """S5: each stated numeric entry without a plus or minus, against a tolerance, is the one section 5's row
    gives on the exact values of the doubles (`monotonicity_strategies.exactly_met`)."""
    if before is None:
        return "no_verdict"
    if before.entries is None:
        return "vacuous"
    checked = 0
    for name, status in before.entries.items():
        exact = strategies.exactly_met(world, name)
        if exact is not None:
            assert (status == "met") == exact, (
                f"S5: {name} is {status}, exactly {'met' if exact else 'not met'}"
            )
            checked += 1
    return "held" if checked else "vacuous"


def checked(name: str, drawn: Drawn) -> None:
    feature("held", check_relation(name, drawn) == "held")
    if RELATIONS[name].change in strategies.WAYS:
        feature(drawn.way)


# Each relation is a property of its own, run in parallel. The least share of its examples on which it held,
# applied with a verdict on both sides where the base is where the relation speaks: about a third of the share
# measured at both sizes (2026-10-17). N1r's two ways for N1, where it does not apply, took its share from
# about 0.9 to 0.63 (seed 1, 2,000 examples at both sizes), and its least share is a third of that: over 24
# runs at each profile (2026-10-18) the share was 0.60 at `dev` and 0.62 at `ci`, and at 0.3, which `dev`
# holds to 60 of 200 examples, a correct run fell short with a probability of about 5e-5 at its measured
# clusters and 1e-3 at `audits.CLUSTER`, above `audits.FALSE_FAILURE`; at 0.2 (20 of 200), below 1e-7.
HELD = {
    "N1r": 0.2,
    "N2": 0.25,
    "N3r": 0.3,
    "N4": 0.24,
    "N5r": 0.11,
    "N6": 0.25,
    "N8": 0.2,
    "P1": 0.12,
    "P2": 0.12,
    "P3": 0.19,
    "P4": 0.33,
    "S1": 0.11,
    "S2": 0.32,
    "S5": 0.23,
}


# The shapes N1r's and N3r's restrictions are for, in the worlds each relation's drawn way starts from: an
# implied condition that fills a condition of the field, and a numeric condition the read leaves unchecked.
# The twins find theirs by ways of their own (`monotonicity_strategies.UNRESTRICTED_WAYS`); this audit sees
# worlds that lost the shapes, which every relation's drawn way would then miss (S2a-4's review B, M3). And a
# world the read meets, where the converse relations speak, which the cooperative half of the worlds is for:
# without it, one world in forty (the review's S11). Their shares in eight `ci` runs (2026-10-17): 0.203 to
# 0.248, mean 0.221; 0.064 to 0.117, mean 0.090; and in seven, 0.148 to 0.176, mean 0.166. Each chance is
# declared at or below its mean.
WORLD_SHAPES = {"implied_fills": 0.2, "unchecked_numeric": 0.08, "met": 0.15}


@pytest.mark.chances(**WORLD_SHAPES)
@given(strategies.worlds(SIZE))
def test_the_worlds_hold_the_shapes_the_restrictions_are_for(world: World) -> None:
    feature("implied_fills", strategies.implied_applies(world, "temperature"))
    feature("unchecked_numeric", strategies.unchecked_numeric(world))
    read = verdict(world)
    feature("met", read is not None and read.status == "met")


@pytest.mark.drawn(*strategies.REMOVAL_WAYS)
@pytest.mark.features(held=HELD["N1r"])
@given(strategies.drawn(SIZE, RELATIONS["N1r"].change))
def test_removing_a_checked_condition_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N1r", drawn)


@pytest.mark.features(held=HELD["N2"])
@given(strategies.drawn(SIZE, RELATIONS["N2"].change))
def test_removing_a_provenance_member_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N2", drawn)


@pytest.mark.drawn(*strategies.STATUS_WAYS)
@pytest.mark.features(held=HELD["N3r"])
@given(strategies.drawn(SIZE, RELATIONS["N3r"].change))
def test_a_status_object_in_a_members_place_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N3r", drawn)


@pytest.mark.drawn(*strategies.OUTSIDE_WAYS)
@pytest.mark.features(held=HELD["N4"])
@given(strategies.drawn(SIZE, RELATIONS["N4"].change))
def test_adding_a_plus_or_minus_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N4", drawn)


@pytest.mark.drawn(*strategies.NARROW_WAYS)
@pytest.mark.features(held=HELD["N5r"])
@given(strategies.drawn(SIZE, RELATIONS["N5r"].change))
def test_narrowing_a_tolerance_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N5r", drawn)


@pytest.mark.features(held=HELD["N6"])
@given(strategies.drawn(SIZE, RELATIONS["N6"].change))
def test_removing_an_operating_condition_never_turns_a_read_met(drawn: Drawn) -> None:
    checked("N6", drawn)


@pytest.mark.drawn(*strategies.IMPLIED_WAYS)
@pytest.mark.features(held=HELD["N8"])
@given(strategies.drawn(SIZE, RELATIONS["N8"].change))
def test_adding_an_implied_condition_never_turns_not_met_into_met(drawn: Drawn) -> None:
    checked("N8", drawn)


@pytest.mark.drawn(*strategies.WIDEN_WAYS)
@pytest.mark.features(held=HELD["P1"])
@given(strategies.drawn(SIZE, RELATIONS["P1"].change))
def test_widening_a_tolerance_never_turns_met_into_not_met(drawn: Drawn) -> None:
    checked("P1", drawn)


@pytest.mark.drawn(*strategies.PLUS_MINUS_REMOVAL_WAYS)
@pytest.mark.features(held=HELD["P2"])
@given(strategies.drawn(SIZE, RELATIONS["P2"].change))
def test_removing_a_plus_or_minus_never_makes_met_worse(drawn: Drawn) -> None:
    checked("P2", drawn)


@pytest.mark.drawn(*strategies.ACCEPT_WAYS)
@pytest.mark.features(held=HELD["P3"])
@given(strategies.drawn(SIZE, RELATIONS["P3"].change))
def test_adding_an_accepted_token_never_turns_met_into_not_met(drawn: Drawn) -> None:
    checked("P3", drawn)


@pytest.mark.features(held=HELD["P4"])
@given(strategies.drawn(SIZE, RELATIONS["P4"].change))
def test_an_operating_value_without_a_tolerance_changes_nothing(drawn: Drawn) -> None:
    checked("P4", drawn)


@pytest.mark.features(held=HELD["S1"])
@given(strategies.drawn(SIZE, RELATIONS["S1"].change))
def test_a_positive_sd_or_unstated_plus_or_minus_makes_a_met_entry_unknown(drawn: Drawn) -> None:
    checked("S1", drawn)


@pytest.mark.features(held=HELD["S2"])
@given(strategies.drawn(SIZE, RELATIONS["S2"].change))
def test_a_stated_condition_made_a_status_object_makes_its_entry_unknown(drawn: Drawn) -> None:
    checked("S2", drawn)


@pytest.mark.drawn(*strategies.BOUNDARY_WAYS)
@pytest.mark.features(held=HELD["S5"])
@given(strategies.drawn(SIZE, RELATIONS["S5"].change))
def test_each_stated_entry_is_section_5s_row_on_the_exact_values(drawn: Drawn) -> None:
    checked("S5", drawn)
