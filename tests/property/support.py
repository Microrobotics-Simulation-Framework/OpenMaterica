# SPDX-License-Identifier: Apache-2.0
"""Strict equality of JSON values, the features an example records, and the search that kills a mutant."""

import struct
from collections.abc import Callable
from typing import TypeVar

from hypothesis import Phase, event, given, settings
from hypothesis import strategies as st

from materica.core.jsonio import JsonValue
from tests.conftest import EXAMPLES
from tests.property.audits import FEATURE

Example = TypeVar("Example")

# A mutant must die within the examples the `ci` profile gives a property. The search is derandomised, so it
# finds the same example on every run; it keeps nothing in the example database, and does not shrink what it
# finds, which only a person reading a failure needs.
MUTANT_SEARCH = settings(
    max_examples=EXAMPLES["ci"],
    derandomize=True,
    database=None,
    deadline=None,
    phases=[Phase.generate],
    report_multiple_bugs=False,
)


def same(expected: JsonValue, actual: JsonValue) -> bool:
    """Equal as values read by item 6: of the same JSON types (a bool is not a number, nor an int a float),
    and numbers equal bit for bit, so that -0 is not 0."""
    if isinstance(expected, float):
        return type(actual) is float and struct.pack(">d", expected) == struct.pack(">d", actual)
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same(e, a) for e, a in zip(expected, actual, strict=True))
        )
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(same(expected[name], actual[name]) for name in expected)
        )
    return type(actual) is type(expected) and actual == expected


def feature(name: str, shown: bool = True) -> None:
    """Records, for the feature audit, that this example shows the feature `name`."""
    if shown:
        event(FEATURE + name)


def examples_to_kill(
    examples: st.SearchStrategy[Example],
    check: Callable[[Example], None],
    error: type[Exception] = AssertionError,
) -> int:
    """The examples Hypothesis tries, searching `examples`, until `check` raises `error`; an AssertionError
    where it never does."""
    tried = 0
    killed_at = 0

    @MUTANT_SEARCH
    @given(examples)
    def search(example: Example) -> None:
        nonlocal tried, killed_at
        tried += 1
        try:
            check(example)
        except error:
            killed_at = killed_at or tried
            raise

    try:
        search()
    except error:
        return killed_at
    raise AssertionError(f"the mutant survived {tried} examples")
