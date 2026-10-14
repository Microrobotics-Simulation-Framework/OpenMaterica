# SPDX-License-Identifier: Apache-2.0
"""(5) Versions (`record_format.md` section 8): their order is the integers' order, for components hundreds of
digits long, and a text is a version exactly when its three parts are ASCII digits with no leading zero. The
mutants they kill are in `test_mutants.py`."""

import operator
from collections.abc import Callable

import pytest
from hypothesis import example, given

from materica.core.identifiers import Version, parse_version
from tests.property import records
from tests.property.records import VersionPair
from tests.property.support import feature

Parse = Callable[[str], Version | None]
COMPARISONS = (operator.lt, operator.le, operator.eq, operator.ne, operator.gt, operator.ge)


def integers(text: str) -> tuple[int, ...]:
    return tuple(int(component) for component in text.split("."))


def check_order(parse: Parse, pair: VersionPair) -> None:
    first, second = parse(pair.first), parse(pair.second)
    assert first is not None
    assert second is not None
    for compare in COMPARISONS:
        assert compare(first, second) == compare(integers(pair.first), integers(pair.second)), (
            compare.__name__
        )


@pytest.mark.features(
    equal=0.05, decided_by_major=0.10, decided_by_minor=0.05, decided_by_patch=0.05, long=0.30
)
@example(VersionPair("9" * 400 + ".0.0", "1" + "0" * 400 + ".0.0"))
@example(VersionPair("0.10.0", "0.9.0"))
@given(records.version_pairs())
def test_versions_order_as_their_integers(pair: VersionPair) -> None:
    first, second = integers(pair.first), integers(pair.second)
    deciding = next((index for index in range(3) if first[index] != second[index]), None)
    feature("equal", deciding is None)
    feature("decided_by_major", deciding == 0)
    feature("decided_by_minor", deciding == 1)
    feature("decided_by_patch", deciding == 2)
    feature("long", max(len(component) for component in (pair.first + "." + pair.second).split(".")) > 100)
    check_order(parse_version, pair)


def is_version(text: str) -> bool:
    """Section 8's pattern, written without a regular expression."""
    parts = text.split(".")
    return len(parts) == 3 and all(
        part.isascii() and part.isdigit() and (part == "0" or not part.startswith("0")) for part in parts
    )


def check_parse(parse: Parse, text: str) -> None:
    try:
        version = parse(text)
    except ValueError as error:
        # It gives None for a text that is not a version, and never raises.
        raise AssertionError(f"{text!r}: {error}") from error
    assert (version is not None) == is_version(text)
    if version is not None:
        assert (version.major, version.minor, version.patch) == tuple(text.split("."))


@pytest.mark.features(accepted=0.09, refused=0.21, long=0.04)
@example("0.1.0\n")
@example("\u0660.1.0")
@given(records.near_versions())
def test_a_text_is_a_version_exactly_when_it_matches(text: str) -> None:
    feature("accepted", is_version(text))
    feature("refused", not is_version(text))
    feature("long", is_version(text) and len(text) > 100)
    check_parse(parse_version, text)
