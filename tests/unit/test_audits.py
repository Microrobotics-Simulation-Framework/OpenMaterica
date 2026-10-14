# SPDX-License-Identifier: Apache-2.0
"""The property tests' audits can fail. This lives outside `tests/property/`, whose audits would fail this
test's filtering property too."""

from collections import Counter

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from tests.property import audits

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
