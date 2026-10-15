# SPDX-License-Identifier: Apache-2.0
"""The property tests' audits can fail. This lives outside `tests/property/`, whose audits would fail this
test's filtering property too."""

import math
from collections import Counter
from fractions import Fraction
from math import comb

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from tests.property import audits
from tests.property.support import feature

FIXED = settings(
    max_examples=50, database=None, derandomize=True, suppress_health_check=[HealthCheck.filter_too_much]
)


def test_a_property_that_rejects_most_draws_is_over_the_gate() -> None:
    @FIXED
    @given(st.integers(0, 99))
    def filtering(number: int) -> None:
        assume(number < 10)

    with audits.counting() as counts:
        filtering()
    share = audits.rejection(counts.draws)
    assert share is not None
    assert share > audits.MAX_REJECTION


def test_a_property_that_rejects_nothing_is_at_zero() -> None:
    @FIXED
    @given(st.integers(0, 99))
    def accepting(number: int) -> None:
        assert 0 <= number <= 99

    with audits.counting() as counts:
        accepting()
    assert audits.rejection(counts.draws) == 0.0


def test_no_draws_seen_is_not_a_rate() -> None:
    with audits.counting() as counts:
        pass
    assert audits.rejection(counts.draws) is None


def counts(examples: int, **features: int) -> audits.Counts:
    return audits.Counts(Counter(valid=examples), Counter(features))


def test_the_feature_audit_fails_a_share_below_its_least() -> None:
    assert audits.feature_shortfalls(counts(2000, deep=100), {"deep": 0.05}) == []
    assert audits.feature_shortfalls(counts(2000, deep=99), {"deep": 0.05})
    assert audits.feature_shortfalls(counts(2000), {"deep": 0.01})


def test_the_feature_audit_fails_a_feature_not_declared() -> None:
    assert audits.feature_shortfalls(counts(2000, deep=2000, typo=1), {"deep": 0.05})


def test_a_share_is_judged_only_with_enough_examples() -> None:
    assert audits.feature_shortfalls(counts(200), {"rare": 0.05}) == []
    assert audits.feature_shortfalls(counts(200), {"common": 0.10})


def exact_floor(draws: int, chance: Fraction) -> int:
    """The largest count that `draws` draws at `chance` fall below with a probability of at most 1e-6."""
    below = Fraction(0)
    for count in range(draws + 1):
        below += comb(draws, count) * chance**count * (1 - chance) ** (draws - count)
        if below > Fraction(1, 10**6):
            return count
    return draws


def test_the_binomial_floor_is_the_largest_count_below_which_the_draws_fall_rarely_enough() -> None:
    assert audits.FALSE_FAILURE == 1e-6
    for draws, chance in [(250, 1 / 9), (250, 1 / 14), (100, 1 / 4), (500, 1 / 27), (40, 0.5)]:
        assert audits.binomial_floor(draws, chance) == exact_floor(draws, Fraction(chance)), (draws, chance)


def test_the_draw_floor_counts_a_run_as_one_draw_in_eight_examples_each_shown_in_five() -> None:
    for drawn in range(9, 16):
        assert audits.draw_floor(2000, 1 / drawn) == 5 * exact_floor(250, Fraction(1, drawn)), drawn


def test_a_drawn_feature_is_held_to_its_draw_floor_by_draws() -> None:
    floor = audits.draw_floor(2000, 1 / 12)
    assert floor >= audits.LEAST_DRAWS
    drawn = [f"fault_{index}" for index in range(12)]
    at_floor = counts(2000, **dict.fromkeys(drawn, floor))
    assert audits.feature_shortfalls(at_floor, {}, drawn, by_draws=True) == []
    short = counts(2000, **{**dict.fromkeys(drawn, floor), "fault_3": floor - 1})
    assert audits.feature_shortfalls(short, {}, drawn, by_draws=True) == [
        f"feature 'fault_3' in {floor - 1} of 2000 examples, below its floor of {floor}"
    ]


def test_features_drawn_among_too_many_for_a_floor_of_ten_fail_however_often_drawn() -> None:
    drawn = [f"fault_{index}" for index in range(27)]
    assert audits.draw_floor(2000, 1 / 27) < audits.LEAST_DRAWS
    problems = audits.feature_shortfalls(counts(2000, **dict.fromkeys(drawn, 74)), {}, drawn, by_draws=True)
    assert len(problems) == 1
    assert "draw them among fewer" in problems[0]


def test_a_drawn_feature_is_held_to_a_third_of_its_share_otherwise() -> None:
    drawn = [f"fault_{index}" for index in range(14)]
    least = 20_000 / 14 / 3
    passing = counts(20_000, **dict.fromkeys(drawn, math.ceil(least)))
    assert audits.feature_shortfalls(passing, {}, drawn) == []
    short = counts(20_000, **{**dict.fromkeys(drawn, math.ceil(least)), "fault_0": math.floor(least)})
    assert len(audits.feature_shortfalls(short, {}, drawn)) == 1


def test_a_drawn_feature_counts_as_declared() -> None:
    drawn = ["fault_0", "fault_1"]
    assert audits.feature_shortfalls(counts(200, fault_0=100, fault_1=100), {}, drawn) == []
    assert audits.feature_shortfalls(counts(200, fault_0=100, fault_1=100, typo=1), {}, drawn) == [
        "feature 'typo' recorded but not declared"
    ]


DRAWN = [f"fault_{index}" for index in range(4)]
# A first choice, then draws that Hypothesis's mutations copy among themselves.
BODY = st.tuples(st.lists(st.integers(0, 9), max_size=8), st.lists(st.text(max_size=3), max_size=5))


@pytest.mark.parametrize("never", [None, "fault_2"])
def test_the_draw_floor_fails_a_feature_never_drawn_and_only_that(never: str | None) -> None:
    """The control: at 800 examples, a floor each of four drawn alike must clear; drawn by Hypothesis as a
    refusal property draws its fault, so that its examples come in clusters."""

    @settings(max_examples=800, database=None, derandomize=True)
    @given(data=st.data())
    def drawing(data: st.DataObject) -> None:
        feature(data.draw(st.sampled_from([name for name in DRAWN if name != never])))
        data.draw(BODY)

    with audits.counting() as counted:
        drawing()
    floor = audits.draw_floor(800, 1 / len(DRAWN))
    assert floor >= audits.LEAST_DRAWS
    problems = audits.feature_shortfalls(counted, {}, DRAWN, by_draws=True)
    assert problems == (
        [] if never is None else [f"feature {never!r} in 0 of 800 examples, below its floor of {floor}"]
    )


def test_a_feature_declared_by_its_chance_is_held_to_its_draw_floor_by_draws() -> None:
    chances = {"rare": 0.1, "common": 0.6}
    floors = {name: audits.draw_floor(2000, chance) for name, chance in chances.items()}
    assert floors == {name: 5 * exact_floor(250, Fraction(chance)) for name, chance in chances.items()}
    assert min(floors.values()) >= audits.LEAST_DRAWS
    at_floor = counts(2000, **floors)
    assert audits.feature_shortfalls(at_floor, {}, by_draws=True, chances=chances) == []
    short = counts(2000, **{**floors, "common": floors["common"] - 1})
    assert audits.feature_shortfalls(short, {}, by_draws=True, chances=chances) == [
        f"feature 'common' in {floors['common'] - 1} of 2000 examples, below its floor of {floors['common']}"
    ]


def test_a_feature_whose_chance_gives_a_floor_below_ten_fails_however_often_shown() -> None:
    assert audits.draw_floor(2000, 0.03) < audits.LEAST_DRAWS
    problems = audits.feature_shortfalls(counts(2000, rare=600), {}, by_draws=True, chances={"rare": 0.03})
    assert len(problems) == 1
    assert "draw it more often, its family in parts" in problems[0]


def test_a_feature_declared_by_its_chance_is_held_to_a_third_of_it_otherwise() -> None:
    least = 20_000 * 0.3 / 3
    passing = counts(20_000, common=math.ceil(least))
    assert audits.feature_shortfalls(passing, {}, chances={"common": 0.3}) == []
    short = counts(20_000, common=math.floor(least) - 1)
    assert len(audits.feature_shortfalls(short, {}, chances={"common": 0.3})) == 1
    assert audits.feature_shortfalls(counts(200, common=0), {}, chances={"rare": 0.2, "common": 0.3}) == [
        "feature 'common' in 0.0% of 200 examples, below 10%"
    ]


def test_at_dev_a_feature_declared_by_its_chance_is_held_to_its_draw_floor_where_it_can_be_judged() -> None:
    """`dev` (200 examples) holds a feature declared by its chance to its draw floor where that is at least
    LEAST_DRAWS, and judges no other; `ci` fails the other."""
    chances = {"often": 0.6, "seldom": 0.2}
    assert audits.draw_floor(200, 0.6) >= audits.LEAST_DRAWS > audits.draw_floor(200, 0.2)
    floor = audits.draw_floor(200, 0.6)
    assert audits.feature_shortfalls(counts(200, often=floor), {}, chances=chances, chance_floors=True) == []
    assert audits.feature_shortfalls(
        counts(200, often=floor - 1), {}, chances=chances, chance_floors=True
    ) == [f"feature 'often' in {floor - 1} of 200 examples, below its floor of {floor}"]
    strict = audits.feature_shortfalls(counts(200, often=floor), {}, by_draws=True, chances=chances)
    assert len(strict) == 1
    assert "draw it more often" in strict[0]
    assert audits.CHANCE_FLOORS == audits.DRAW_FLOORS | {"dev"}


def test_a_feature_declared_by_its_chance_counts_as_declared() -> None:
    assert audits.feature_shortfalls(counts(200, shown=100), {}, chances={"shown": 0.5}) == []
    assert audits.feature_shortfalls(counts(200, shown=100, typo=1), {}, chances={"shown": 0.5}) == [
        "feature 'typo' recorded but not declared"
    ]


CHANCES = {"often": 0.5, "seldom": 0.2}


@pytest.mark.parametrize("never", [None, "seldom"])
def test_the_draw_floor_fails_a_feature_declared_by_its_chance_never_drawn_and_only_that(
    never: str | None,
) -> None:
    """The control: at 2,000 examples, a floor each of two features declared by their chances must clear,
    each drawn as a later choice of an example whose first Hypothesis's mutations keep, so that the examples
    come in clusters."""

    @settings(max_examples=2000, database=None, derandomize=True)
    @given(data=st.data())
    def drawing(data: st.DataObject) -> None:
        data.draw(st.integers(0, 9))
        for name, chance in CHANCES.items():
            feature(name, name != never and data.draw(st.integers(0, 99)) < 100 * chance)
        data.draw(BODY)

    with audits.counting() as counted:
        drawing()
    floors = {name: audits.draw_floor(2000, chance) for name, chance in CHANCES.items()}
    assert min(floors.values()) >= audits.LEAST_DRAWS
    problems = audits.feature_shortfalls(counted, {}, by_draws=True, chances=CHANCES)
    assert problems == (
        []
        if never is None
        else [f"feature {never!r} in 0 of 2000 examples, below its floor of {floors[never]}"]
    )


def test_a_first_choice_shows_in_at_most_cluster_examples() -> None:
    """The draw floor's premise, checked against the Hypothesis installed: an example's first choice is kept
    through at most CLUSTER examples, and is so through that many."""
    shown: Counter[bytes] = Counter()

    @settings(max_examples=1000, database=None, derandomize=True)
    @given(data=st.data())
    def drawing(data: st.DataObject) -> None:
        shown[data.draw(st.binary(min_size=8, max_size=8))] += 1
        data.draw(BODY)

    drawing()
    assert max(shown.values()) == audits.CLUSTER
