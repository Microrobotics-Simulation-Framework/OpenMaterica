# SPDX-License-Identifier: Apache-2.0
"""`tests/property/strategies.py` builds `json_values`'s strategy once for each set of arguments, under a key
(`_strict_key`) that tells apart what `==` does not: 0.0 and -0.0, `True`, 1 and 1.0, two strategies that
compare equal, and a `Size` from a tuple of the same items. A key by `==` (`functools.cache`'s) would hand a
strategy built for one to a caller who asked for the other, and no property test would notice: no caller
passes two such arguments, so the draws of the suite are the same under either key. These cases say what the
key does, and a control runs each under a key by `==`, which must merge every pair.
"""

from collections.abc import Callable
from typing import Any, cast

import pytest
from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from tests.property import strategies
from tests.property.strategies import Size

strict_key: Callable[[object], object] = strategies._strict_key  # pyright: ignore[reportPrivateUsage]


class Equal(SearchStrategy[int]):
    """A strategy that compares equal to every other `Equal` and hashes alike, whatever it draws."""

    def __init__(self, value: int) -> None:
        super().__init__()
        self.value = value

    def do_draw(self, data: Any) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Equal)

    def __hash__(self) -> int:
        return 0


ONE, ANOTHER = Equal(1), Equal(2)

# Each pair is equal under `==` and hashes alike, so a key by `==` is the same for both.
PAIRS = {
    "zero_and_negative_zero": (0.0, -0.0),
    "zero_and_negative_zero_in_a_tuple": ((0.0, 1), (-0.0, 1)),
    "true_and_one": (True, 1),
    "one_and_one_float": (1, 1.0),
    "true_and_one_float": (True, 1.0),
    "false_and_zero": (False, 0),
    "equal_strategies_not_identical": (ONE, ANOTHER),
    "equal_strategies_in_the_arguments": ((ONE, 1.0), (ANOTHER, 1.0)),
    "size_by_an_item_true_and_one": (Size(10, True, 5), Size(10, 1, 5)),
    "size_by_an_item_one_and_one_float": (Size(10, 1, 5), Size(10, cast(int, 1.0), 5)),
    "size_and_the_tuple_of_its_items": (Size(10, 3, 5), (10, 3, 5)),
}

# Each pair is the same argument twice, which must give one key, or the cache never answers.
SAME = {
    "a_float": (1.5, 1.5),
    "negative_zero": (-0.0, -0.0),
    "a_size": (Size(10, 3, 5), Size(10, 3, 5)),
    "one_strategy": (ONE, ONE),
    "a_tuple_of_both": ((ONE, Size(10, 3, 5), -0.0), (ONE, Size(10, 3, 5), -0.0)),
}


def naive_key(value: object) -> object:
    """What `functools.cache` keys an argument by."""
    return value


def tells_apart(key: Callable[[object], object], first: object, second: object) -> bool:
    return key(first) != key(second)


@pytest.mark.parametrize("name", PAIRS)
def test_the_key_tells_apart_what_equality_does_not(name: str) -> None:
    first, second = PAIRS[name]
    assert first == second, "the pair must be equal for the case to mean anything"
    assert hash(first) == hash(second)
    assert tells_apart(strict_key, first, second)


@pytest.mark.parametrize("name", PAIRS)
def test_control_a_key_by_equality_merges_every_pair(name: str) -> None:
    """The control: the assertion above, made of the same function under `==`'s key, fails for each pair, so
    each pair is a case that the strict key's test can fail."""
    first, second = PAIRS[name]
    assert not tells_apart(naive_key, first, second)


@pytest.mark.parametrize("name", SAME)
def test_the_key_is_one_key_for_the_same_argument(name: str) -> None:
    first, second = SAME[name]
    assert strict_key(first) == strict_key(second)
    assert hash(strict_key(first)) == hash(strict_key(second))


def test_json_values_builds_one_strategy_for_the_same_arguments() -> None:
    assert strategies.json_values(size=Size(10, 3, 5)) is strategies.json_values(size=Size(10, 3, 5))
    assert strategies.json_values(numbers=ONE) is strategies.json_values(numbers=ONE)


def test_json_values_builds_a_strategy_of_its_own_for_each_pair() -> None:
    assert strategies.json_values(numbers=ONE) is not strategies.json_values(numbers=ANOTHER)
    assert strategies.json_values(size=Size(10, True, 5)) is not strategies.json_values(size=Size(10, 1, 5))
    assert strategies.json_values(numbers=st.just(0.0)) is not strategies.json_values(numbers=st.just(-0.0))


def test_control_json_values_under_a_key_by_equality_hands_one_strategy_for_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control for the test above, through the module's own code path: with the key replaced by `==`'s,
    two arguments that differ share a strategy, so the test above would fail."""
    monkeypatch.setattr(strategies, "_strict_key", naive_key)
    monkeypatch.setattr(strategies, "_JSON_VALUES", {})
    assert strategies.json_values(numbers=ONE) is strategies.json_values(numbers=ANOTHER)
    assert strategies.json_values(size=Size(10, True, 5)) is strategies.json_values(size=Size(10, 1, 5))
