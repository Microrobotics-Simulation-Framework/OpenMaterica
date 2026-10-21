# SPDX-License-Identifier: Apache-2.0
"""The property tests' audits can fail. This lives outside `tests/property/`, whose audits would fail this
test's filtering property too."""

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Iterator
from fractions import Fraction
from math import comb
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from tests.conftest import EXAMPLES
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
    LEAST_DRAWS, and judges no other, a floor of 5 included; `ci` fails the other. A chance's floor is not
    held to a third of the chance."""
    dev = audits.RULES["dev"]
    chances = {"often": 0.6, "seldom": 0.45}
    assert audits.draw_floor(200, 0.6) >= audits.LEAST_DRAWS > audits.draw_floor(200, 0.45) > 0
    floor = audits.draw_floor(200, 0.6)
    assert audits.feature_shortfalls(counts(200, often=floor), {}, chances=chances, **dev) == []
    assert audits.feature_shortfalls(counts(200, often=floor - 1), {}, chances=chances, **dev) == [
        f"feature 'often' in {floor - 1} of 200 examples, below its floor of {floor}"
    ]
    strict = audits.feature_shortfalls(counts(200, often=floor), {}, chances=chances, **audits.RULES["ci"])
    assert "draw it more often" in strict[0]
    nearly_always = audits.draw_floor(200, 0.9)
    assert nearly_always - 1 > 0.9 / 3 * 200
    assert audits.feature_shortfalls(
        counts(200, shown=nearly_always - 1), {}, chances={"shown": 0.9}, **dev
    ) == [f"feature 'shown' in {nearly_always - 1} of 200 examples, below its floor of {nearly_always}"]


def test_at_dev_features_drawn_among_two_are_held_to_their_draw_floor_and_among_three_are_not_judged() -> (
    None
):
    dev = audits.RULES["dev"]
    floor = audits.draw_floor(200, 1 / 2)
    assert floor >= audits.LEAST_DRAWS > audits.draw_floor(200, 1 / 3)
    assert (
        audits.feature_shortfalls(counts(200, one=floor, other=200 - floor), {}, ["one", "other"], **dev)
        == []
    )
    assert audits.feature_shortfalls(
        counts(200, one=floor - 1, other=201 - floor), {}, ["one", "other"], **dev
    ) == [f"feature 'one' in {floor - 1} of 200 examples, below its floor of {floor}"]
    assert audits.feature_shortfalls(counts(200, b=100, c=100), {}, ["a", "b", "c"], **dev) == []


def test_at_dev_a_declared_feature_is_held_to_the_floor_of_three_times_its_least_share_never_above_it() -> (
    None
):
    dev = audits.RULES["dev"]
    floor = audits.draw_floor(200, 3 * 0.2)
    assert audits.LEAST_DRAWS <= floor < 0.2 * 200
    assert audits.feature_shortfalls(counts(200, held=floor), {"held": 0.2}, **dev) == []
    assert audits.feature_shortfalls(counts(200, held=floor - 1), {"held": 0.2}, **dev) == [
        f"feature 'held' in {floor - 1} of 200 examples, below its floor of {floor}"
    ]
    # A floor above the least share's count holds the feature to its least share.
    assert audits.draw_floor(200, 3 * 0.33) > 0.33 * 200
    assert audits.feature_shortfalls(counts(200, held=66), {"held": 0.33}, **dev) == []
    assert audits.feature_shortfalls(counts(200, held=65), {"held": 0.33}, **dev) == [
        "feature 'held' in 32.5% of 200 examples, below 33%"
    ]
    # A floor below LEAST_DRAWS is not judged.
    assert audits.draw_floor(200, 3 * 0.11) < audits.LEAST_DRAWS
    assert audits.feature_shortfalls(counts(200), {"held": 0.11}, **dev) == []


def test_at_dev_a_feature_recorded_but_not_declared_fails_whichever_way_the_others_are_declared() -> None:
    """A mistyped feature name is reported at `dev` as at `ci`, whether the others are declared by a least
    share, drawn alike or declared by a chance, and before any shortfall."""
    dev = audits.RULES["dev"]
    typo = "feature 'typo' recorded but not declared"
    declarations: list[tuple[dict[str, float], list[str], dict[str, float]]] = [
        ({"held": 0.2}, [], {}),
        ({}, ["one", "other"], {}),
        ({}, [], {"often": 0.6}),
    ]
    for declared, drawn, chances in declarations:
        names = [*declared, *drawn, *chances]
        # The control: with every feature declared and shown as often as its floor, the run passes.
        assert (
            audits.feature_shortfalls(
                counts(200, **dict.fromkeys(names, 100)), declared, drawn, chances=chances, **dev
            )
            == []
        )
        mistyped = counts(200, **dict.fromkeys(names, 100), typo=1)
        assert audits.feature_shortfalls(mistyped, declared, drawn, chances=chances, **dev) == [typo]
        short = counts(200, **dict.fromkeys(names, 0), typo=1)
        problems = audits.feature_shortfalls(short, declared, drawn, chances=chances, **dev)
        assert problems[0] == typo
        assert len(problems) > 1, "the shortfalls follow the typo"


def test_a_feature_declared_by_its_chance_counts_as_declared() -> None:
    assert audits.feature_shortfalls(counts(200, shown=100), {}, chances={"shown": 0.5}) == []
    assert audits.feature_shortfalls(counts(200, shown=100, typo=1), {}, chances={"shown": 0.5}) == [
        "feature 'typo' recorded but not declared"
    ]


CHANCES = {"often": 0.5, "seldom": 0.2}


def drawn_by_chance(never: str | None) -> audits.Counts:
    """A run of 2,000 examples, each showing each of CHANCES at its chance, `never` aside, as a later choice
    of an example whose first Hypothesis's mutations keep, so that the examples come in clusters."""

    @settings(max_examples=2000, database=None, derandomize=True)
    @given(data=st.data())
    def drawing(data: st.DataObject) -> None:
        data.draw(st.integers(0, 9))
        for name, chance in CHANCES.items():
            feature(name, name != never and data.draw(st.integers(0, 99)) < 100 * chance)
        data.draw(BODY)

    with audits.counting() as counted:
        drawing()
    return counted


@pytest.mark.parametrize("never", [None, "seldom"])
def test_the_draw_floor_fails_a_feature_declared_by_its_chance_never_drawn_and_only_that(
    never: str | None,
) -> None:
    """The control: at 2,000 examples, a floor each of two features declared by their chances must clear,
    drawn in clusters (`drawn_by_chance`)."""
    floors = {name: audits.draw_floor(2000, chance) for name, chance in CHANCES.items()}
    assert min(floors.values()) >= audits.LEAST_DRAWS
    problems = audits.feature_shortfalls(drawn_by_chance(never), {}, by_draws=True, chances=CHANCES)
    assert problems == (
        []
        if never is None
        else [f"feature {never!r} in 0 of 2000 examples, below its floor of {floors[never]}"]
    )


# A feature declared by `deep_chances`, which a region too thin for a floor at `ci` is: held to its draw floor
# at `deep` alone.


def test_a_feature_declared_by_its_chance_at_deep_is_held_to_its_draw_floor_there_alone() -> None:
    chance = 0.02
    floor = audits.draw_floor(EXAMPLES["deep"], chance)
    assert floor == 5 * exact_floor(EXAMPLES["deep"] // audits.CLUSTER, Fraction(chance))
    assert floor >= audits.LEAST_DRAWS > audits.draw_floor(EXAMPLES["ci"], chance)
    deep = audits.RULES["deep"]
    at_floor = counts(EXAMPLES["deep"], seldom=floor)
    assert audits.feature_shortfalls(at_floor, {}, deep_chances={"seldom": chance}, **deep) == []
    short = counts(EXAMPLES["deep"], seldom=floor - 1)
    assert audits.feature_shortfalls(short, {}, deep_chances={"seldom": chance}, **deep) == [
        f"feature 'seldom' in {floor - 1} of {EXAMPLES['deep']} examples, below its floor of {floor}"
    ]
    for profile in ("dev", "ci"):
        never = counts(EXAMPLES[profile])
        assert (
            audits.feature_shortfalls(never, {}, deep_chances={"seldom": chance}, **audits.RULES[profile])
            == []
        )


def test_at_deep_a_feature_whose_chance_gives_a_floor_below_ten_fails_however_often_shown() -> None:
    assert audits.draw_floor(EXAMPLES["deep"], 0.005) < audits.LEAST_DRAWS
    shown = counts(EXAMPLES["deep"], rare=EXAMPLES["deep"])
    problems = audits.feature_shortfalls(shown, {}, deep_chances={"rare": 0.005}, **audits.RULES["deep"])
    assert len(problems) == 1
    assert "draw it more often, its family in parts" in problems[0]


@pytest.mark.parametrize("profile", sorted(EXAMPLES))
def test_a_feature_declared_by_its_chance_at_deep_counts_as_declared_at_every_profile(profile: str) -> None:
    examples = EXAMPLES[profile]
    shown = {"shown": audits.draw_floor(examples, 0.5)}
    rule = audits.RULES[profile]
    assert audits.feature_shortfalls(counts(examples, **shown), {}, deep_chances={"shown": 0.5}, **rule) == []
    assert audits.feature_shortfalls(
        counts(examples, **shown, typo=1), {}, deep_chances={"shown": 0.5}, **rule
    ) == ["feature 'typo' recorded but not declared"]


@pytest.mark.parametrize("never", [None, "seldom"])
def test_deep_alone_fails_a_feature_declared_by_its_chance_at_deep_never_drawn_and_only_that(
    never: str | None,
) -> None:
    """The control: the run of the control above, its features declared by `deep_chances`. `deep`'s rule
    judges a run by its own examples, so at 2,000 it holds each to the floor `ci` holds a chance to; `ci`'s
    and `dev`'s judge neither."""
    counted = drawn_by_chance(never)
    floors = {name: audits.draw_floor(2000, chance) for name, chance in CHANCES.items()}
    assert min(floors.values()) >= audits.LEAST_DRAWS
    for profile, rule in audits.RULES.items():
        problems = audits.feature_shortfalls(counted, {}, deep_chances=CHANCES, **rule)
        assert problems == (
            [f"feature {never!r} in 0 of 2000 examples, below its floor of {floors[never]}"]
            if never is not None and profile == "deep"
            else []
        ), profile


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


# Every declaration the pins and the false-failure check judge: a least share or a chance in steps of 0.001,
# or one to 60 features drawn alike.
DECLARATIONS = [
    *(("features", index / 1000) for index in range(1, 1001)),
    *(("drawn", drawn) for drawn in range(1, 61)),
    *(("chances", index / 1000) for index in range(1, 1001)),
]

# A run is its number of examples (the draws Hypothesis reports `valid` or `interesting`), how many of them
# were `interesting`, and how many further draws were `invalid`.
Run = tuple[int, int, int]


def runs(*sizes: int) -> tuple[Run, ...]:
    """Each size as a run of valid draws alone, then with interesting draws, with invalid draws, and with
    both: the examples a run counts are the valid and the interesting, not the invalid. A size need not be a
    multiple of CLUSTER, as a run that replays a saved failure is not."""
    return tuple(
        (size, interesting, invalid) for size in sizes for interesting in (0, 3) for invalid in (0, 9)
    )


def counted(run: Run, **features: int) -> audits.Counts:
    examples, interesting, invalid = run
    return audits.Counts(
        Counter(valid=examples - interesting, interesting=interesting, invalid=invalid), Counter(features)
    )


def judging(
    rule: audits.Rule, run: Run, kind: str, value: float, module: ModuleType = audits
) -> tuple[int | None, list[str]]:
    """The fewest examples a feature declared so must show to pass `rule`'s audit in `run`, with the
    problems one fewer gives; or None, with the problems the most give, where no count passes."""
    examples = run[0]
    names = [f"f{index}" for index in range(int(value))] if kind == "drawn" else ["f"]

    def problems(shown: int) -> list[str]:
        found: list[str] = module.feature_shortfalls(
            counted(run, **dict.fromkeys(names, shown)),
            {"f": value} if kind == "features" else {},
            names if kind == "drawn" else (),
            chances={"f": value} if kind == "chances" else {},
            deep_chances={"f": value} if kind == "deep_chances" else {},
            **rule,
        )
        return found

    if problems(examples):
        return None, problems(examples)
    fewest, passing = 0, examples
    while fewest < passing:
        middle = (fewest + passing) // 2
        if problems(middle):
            fewest = middle + 1
        else:
            passing = middle
    return fewest, problems(fewest - 1) if fewest else []


Judgement = tuple[Run, str, float, int | None, list[str]]


def judgements(
    rule: audits.Rule, pinned: tuple[Run, ...], module: ModuleType = audits
) -> Iterator[Judgement]:
    """What `rule` judges of every declaration, in each of the runs."""
    for run in pinned:
        for kind, value in DECLARATIONS:
            yield (run, kind, value, *judging(rule, run, kind, value, module))


def digest(rule: audits.Rule, pinned: tuple[Run, ...], module: ModuleType = audits) -> str:
    return hashlib.sha256(json.dumps(list(judgements(rule, pinned, module))).encode()).hexdigest()


def differ(rule: audits.Rule, pinned: str, module: ModuleType = audits) -> bool:
    """Whether `rule`, in `module`, judges some declaration otherwise than the pinned profile's rule in
    `audits`, in the pinned runs: so that its digest is another. It stops at the first difference."""
    pinned_runs = PINNED[pinned][0]
    return any(
        ours != theirs
        for ours, theirs in zip(
            judgements(rule, pinned_runs, module), judgements(audits.RULES[pinned], pinned_runs), strict=True
        )
    )


# What `ci` and `deep` judge, pinned on 2026-10-18 from the rule as it stood before `dev` was held to
# FALSE_FAILURE: a change of `dev`'s rule leaves them as they are. The runs are each profile's examples and a
# run that ends sooner, and sizes that are not multiples of CLUSTER (`runs`). The digests are of
# `origin/main`'s own `feature_shortfalls` (`by_draws` and `chance_floors` for `ci`, neither for `deep`).
PINNED = {
    "ci": (
        runs(2_000, 200, 1_999, 2_001, 2_003, 199, 203),
        "2fe5c02b9c8cd7d01cc529f22faf0b11a62ee4efb70260d73d5ba5ce66127440",
    ),
    "deep": (
        runs(20_000, 2_000, 19_999, 20_001, 1_999, 2_001),
        "d052820c1fe8e43ecfa219d79d8a80c5b954d54ed900d9de27c9ce2042c0111c",
    ),
}


@pytest.mark.parametrize("profile", sorted(PINNED))
def test_what_ci_and_deep_judge_is_pinned(profile: str) -> None:
    pinned_runs, pinned = PINNED[profile]
    assert digest(audits.RULES[profile], pinned_runs) == pinned


@pytest.mark.parametrize("profile", sorted(PINNED))
def test_the_pin_sees_another_rule(profile: str) -> None:
    """The control: each other profile's rule judges a pinned profile's runs otherwise."""
    for other in sorted(audits.RULES.keys() - {profile}):
        assert differ(audits.RULES[other], profile), other


def test_the_pin_sees_a_floor_moved(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control: `ci`'s rule with floors at another false failure judges its runs otherwise."""
    rule = audits.RULES["ci"]
    floors = list(judgements(rule, PINNED["ci"][0]))
    monkeypatch.setattr(audits, "FALSE_FAILURE", 1e-3)
    assert any(ours != theirs for ours, theirs in zip(judgements(rule, PINNED["ci"][0]), floors, strict=True))


def audits_with(old: str, new: str) -> ModuleType:
    """The audits module with one line of its source changed: a constructed change to what a run counts."""
    source = Path(audits.__file__).read_text()
    assert source.count(old) == 1, old
    module = ModuleType("audits_changed")
    exec(compile(source.replace(old, new), "audits_changed", "exec"), module.__dict__)
    return module


EXAMPLES_LINE = 'examples = counts.draws["valid"] + counts.draws["interesting"]'
FLOOR_LINE = "return SHOWN * binomial_floor(examples // CLUSTER, chance)"
# What a run counts, changed one way at a time, with the profiles whose judgement it changes: `deep` judges
# no draw floor of the declarations pinned, so a change to the floor's count is no change of its.
CHANGES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "interesting_draws_not_examples": (EXAMPLES_LINE, 'examples = counts.draws["valid"]', ("ci", "deep")),
    "invalid_draws_are_examples": (
        EXAMPLES_LINE,
        EXAMPLES_LINE + ' + counts.draws["invalid"]',
        ("ci", "deep"),
    ),
    "draws_rounded_up": (
        FLOOR_LINE,
        "return SHOWN * binomial_floor(-(-examples // CLUSTER), chance)",
        ("ci",),
    ),
    "no_floor_for_a_part_cluster": (
        FLOOR_LINE,
        "return SHOWN * binomial_floor(examples // CLUSTER, chance) if examples % CLUSTER == 0 else 0",
        ("ci",),
    ),
}


def test_a_changed_module_judges_as_the_module_when_nothing_is_changed() -> None:
    """The control: the loader that makes the constructed changes changes nothing by itself."""
    same = audits_with(EXAMPLES_LINE, EXAMPLES_LINE)
    for profile, (pinned_runs, pinned) in PINNED.items():
        assert digest(audits.RULES[profile], pinned_runs, same) == pinned


@pytest.mark.parametrize(
    ("change", "profile"),
    [(change, profile) for change, (*_, profiles) in CHANGES.items() for profile in profiles],
)
def test_the_pin_sees_a_change_to_what_a_run_counts(change: str, profile: str) -> None:
    """A run's examples are its valid and interesting draws, and its draws are its examples in eights, rounded
    down: the pin sees each of these four changes, in the runs that are not multiples of eight and have
    interesting and invalid draws."""
    old, new, _ = CHANGES[change]
    assert differ(audits.RULES[profile], profile, audits_with(old, new))


def test_every_profile_has_a_rule() -> None:
    assert audits.RULES.keys() == EXAMPLES.keys()


THREE_FIELDS = ["another_field", "unknown_field", "another_section_specimen"]
THREE_PLUS_MINUS = ["drawn", "just_outside", "met"]
# The three audits that CI's `dev` jobs failed by chance on 2026-10-18, each a correct property's feature
# drawn among three, which `dev` held to a third of its share where 20 were expected (11%, 22.2 of 200
# examples): the counts of each run, replayed under its job's command and seed (pull requests #35 and #37, at
# d226c16, 9344311 and f36810d).
CHANCE_FAILURES: list[tuple[audits.Counts, dict[str, float], list[str], str]] = [
    (
        counts(200, another_field=71, unknown_field=21, another_section_specimen=108),
        {},
        THREE_FIELDS,
        "feature 'unknown_field' in 10.5% of 200 examples, below 11%",
    ),
    (
        counts(200, another_field=22, unknown_field=119, another_section_specimen=59),
        {},
        THREE_FIELDS,
        "feature 'another_field' in 11.0% of 200 examples, below 11%",
    ),
    (
        counts(200, drawn=19, just_outside=110, met=71, held=72),
        {"held": 0.12},
        THREE_PLUS_MINUS,
        "feature 'drawn' in 9.5% of 200 examples, below 11%",
    ),
]


@pytest.mark.parametrize(("counted", "declared", "drawn", "reported"), CHANCE_FAILURES)
def test_the_chance_failures_ci_met_at_dev_pass(
    counted: audits.Counts, declared: dict[str, float], drawn: list[str], reported: str
) -> None:
    assert audits.feature_shortfalls(counted, declared, drawn, **audits.RULES["dev"]) == []
    # The control: judged by least shares where 20 are expected, as `dev` judged declared and drawn features
    # until 2026-10-18 and `deep` judges them, each fails as CI reported it.
    assert audits.feature_shortfalls(counted, declared, drawn, **audits.RULES["deep"]) == [reported]


def model_false_failure(examples: int, chance: float, fewest: int) -> float:
    """By the draw floor's model, the probability that a feature drawn with probability `chance` shows in
    fewer than `fewest` examples of a run of `examples`: SHOWN times the successes of examples // CLUSTER
    draws, each at `chance`. Each term is taken in logarithms, which `deep`'s 2,500 draws need."""
    draws = examples // audits.CLUSTER
    needed = -(-fewest // audits.SHOWN)  # the examples shown are fewer than `fewest` with fewer successes
    if chance >= 1:
        return 1.0 if needed > draws else 0.0
    return math.fsum(
        math.exp(
            math.lgamma(draws + 1)
            - math.lgamma(count + 1)
            - math.lgamma(draws - count + 1)
            + count * math.log(chance)
            + (draws - count) * math.log1p(-chance)
        )
        for count in range(min(needed, draws + 1))
    )


# The chance that one draw shows a feature declared so: a least share is a third of the share measured.
CHANCE: dict[str, Callable[[float], float]] = {
    "features": lambda least: 3 * least,
    "drawn": lambda drawn: 1 / drawn,
    "chances": lambda chance: chance,
    "deep_chances": lambda chance: chance,
}
# The judgements made by a least share, as before 2026-10-18 and pinned as they are (above): the draw floor's
# model does not bound them. It gives a feature shown by whole clusters at JUDGED_FROM about 5e-2, and a least
# share of 10% at `ci` about 1e-6; the figures for those whose clusters were measured are in `audits.py`.
BY_LEAST_SHARES = {("ci", "features"), ("deep", "features"), ("deep", "drawn"), ("deep", "chances")}


# Every chance `deep_chances` can declare, in steps of 0.001: a declaration the pins do not hold.
DEEP_CHANCES = [("deep_chances", index / 1000) for index in range(1, 1001)]


def worst_false_failure(
    rule: audits.Rule, examples: int, kinds: set[str], declarations: list[tuple[str, float]] = DECLARATIONS
) -> tuple[float, tuple[str, float]]:
    """Of every declaration of these kinds that `rule` judges in a run of `examples`, the one most likely to
    fail a correct run, by the draw floor's model, with that probability. A declaration no count passes is the
    declaration's fault, not chance: `ci` refuses it on every run."""
    worst: tuple[float, tuple[str, float]] = (0.0, ("", 0.0))
    for kind, value in declarations:
        fewest, _ = judging(rule, (examples, 0, 0), kind, value)
        if kind in kinds and fewest:
            worst = max(worst, (model_false_failure(examples, CHANCE[kind](value), fewest), (kind, value)))
    return worst


@pytest.mark.parametrize("profile", ["dev", "ci"])
def test_no_feature_judged_by_a_floor_fails_a_correct_run_more_often_than_one_in_a_million(
    profile: str,
) -> None:
    kinds = {kind for kind in CHANCE if (profile, kind) not in BY_LEAST_SHARES}
    probability, declaration = worst_false_failure(audits.RULES[profile], EXAMPLES[profile], kinds)
    assert probability <= 1e-6, declaration


def test_dev_judges_every_feature_by_a_floor() -> None:
    assert {profile for profile, _ in BY_LEAST_SHARES} == {"ci", "deep"}


def test_the_check_sees_the_least_shares_dev_judged_by() -> None:
    """The control: `dev`'s runs judged by least shares where 20 are expected, as `dev` judged declared and
    drawn features until 2026-10-18, fail a correct run more often: features drawn among three about one run
    in twenty by the model."""
    probability, _ = worst_false_failure(audits.RULES["deep"], EXAMPLES["dev"], {"features", "drawn"})
    assert probability > 1e-6
    fewest, _ = judging(audits.RULES["deep"], (EXAMPLES["dev"], 0, 0), "drawn", 3)
    assert fewest is not None
    assert model_false_failure(EXAMPLES["dev"], 1 / 3, fewest) > 1e-2


def test_the_check_sees_floors_at_another_false_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audits, "FALSE_FAILURE", 1e-3)
    probability, _ = worst_false_failure(audits.RULES["dev"], EXAMPLES["dev"], set(CHANCE))
    assert probability > 1e-6


def test_a_feature_declared_by_its_chance_at_deep_is_judged_at_deep_alone() -> None:
    """At `deep` no count passes a chance whose floor is below LEAST_DRAWS, and each other has a floor; at
    `ci` and `dev` a feature never shown passes every chance."""
    for profile, rule in audits.RULES.items():
        fewest = {
            value: judging(rule, (EXAMPLES[profile], 0, 0), kind, value)[0] for kind, value in DEEP_CHANCES
        }
        if profile == "deep":
            assert all(count is None or count >= audits.LEAST_DRAWS for count in fewest.values())
            assert {value for value, count in fewest.items() if count is None} == {
                value
                for _, value in DEEP_CHANCES
                if audits.draw_floor(EXAMPLES["deep"], value) < audits.LEAST_DRAWS
            }
        else:
            assert set(fewest.values()) == {0}, profile


def test_no_feature_declared_by_its_chance_at_deep_fails_a_correct_run_more_often_than_one_in_a_million() -> (
    None
):
    probability, declaration = worst_false_failure(
        audits.RULES["deep"], EXAMPLES["deep"], {"deep_chances"}, DEEP_CHANCES
    )
    assert 0 < probability <= 1e-6, declaration


def test_the_check_sees_deep_floors_at_another_false_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audits, "FALSE_FAILURE", 1e-3)
    probability, _ = worst_false_failure(
        audits.RULES["deep"], EXAMPLES["deep"], {"deep_chances"}, DEEP_CHANCES
    )
    assert probability > 1e-6
