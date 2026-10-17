# SPDX-License-Identifier: Apache-2.0
"""Every test here passes the draw-rejection audit, and every property its feature audit (`audits.py`)."""

from collections.abc import Generator

import pytest
from hypothesis import is_hypothesis_test

from tests.conftest import PROFILE
from tests.property import audits


def replay(item: pytest.Item) -> str:
    return audits.replay(getattr(item, "obj", None), getattr(item, "originalname", item.name), PROFILE)


# Innermost of the wrappers, so that the audits' collector is the one Hypothesis calls; it passes the
# statistics on to the plugin's.
@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, None, None]:
    with audits.counting() as counts:
        yield
    share = audits.rejection(counts.draws)
    if share is None:
        if is_hypothesis_test(getattr(item, "obj", None)):
            pytest.fail("the audits saw no draws: has Hypothesis changed its statistics?")
        return
    if share > audits.MAX_REJECTION:
        pytest.fail(
            f"rejected {share:.0%} of its draws, over the audit's {audits.MAX_REJECTION:.0%}" + replay(item)
        )
    declared = item.get_closest_marker("features")
    drawn = item.get_closest_marker("drawn")
    chances = item.get_closest_marker("chances")
    problems = audits.feature_shortfalls(
        counts,
        {} if declared is None else dict(declared.kwargs),
        () if drawn is None else drawn.args,
        by_draws=PROFILE in audits.DRAW_FLOORS,
        chances={} if chances is None else dict(chances.kwargs),
        chance_floors=PROFILE in audits.CHANCE_FLOORS,
    )
    if problems:
        pytest.fail("feature audit: " + "; ".join(problems) + replay(item))
