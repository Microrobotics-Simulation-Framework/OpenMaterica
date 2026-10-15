# SPDX-License-Identifier: Apache-2.0
"""What the property tests' audits count, read from Hypothesis's statistics.

The draw-rejection audit: a property that rejects most of its draws (by `assume` or a `.filter`) searches less
widely than its example count says, and runs close to Hypothesis's `filter_too_much` health check, which fires
at 50 rejected draws before 10 valid ones. At the gate below, as in MADDENING's audit, that chance is about
1.8e-12 per run.

The feature audit: a property declares, with the `features` marker, the least share of its examples that must
show each feature the specification distinguishes, and records each example's features with
`support.feature`. A property that draws one of several features alike as its first choice, as a refusal
property draws its fault, declares them with the `drawn` marker instead, and at the `ci` profile each is held
to its draw floor (`draw_floor`).
"""

import math
from collections import Counter
from collections.abc import Callable, Collection, Generator
from contextlib import contextmanager
from typing import NamedTuple, TypedDict

from hypothesis.statistics import collector

MAX_REJECTION = 0.40
FEATURE = "feature: "


# The parts of Hypothesis's statistics the audits read.
class _Call(TypedDict):
    status: str
    events: list[str]


_Phase = TypedDict("_Phase", {"test-cases": list[_Call]})
_Statistics = TypedDict("_Statistics", {"reuse-phase": _Phase, "generate-phase": _Phase}, total=False)


class Counts(NamedTuple):
    draws: Counter[str]  # by status
    features: Counter[str]  # the examples that showed each feature


@contextmanager
def counting() -> Generator[Counts, None, None]:
    """Counts the draws and features of every Hypothesis run inside the block, and passes the statistics on to
    the collector already set (Hypothesis's pytest plugin sets one for every test)."""
    counts = Counts(Counter(), Counter())
    previous: Callable[[_Statistics], None] | None = collector.value

    def observe(statistics: _Statistics) -> None:
        for phase in (statistics.get("reuse-phase"), statistics.get("generate-phase")):
            for call in [] if phase is None else phase["test-cases"]:
                counts.draws[call["status"]] += 1
                if call["status"] in ("valid", "interesting"):
                    counts.features.update(
                        event.removeprefix(FEATURE) for event in call["events"] if event.startswith(FEATURE)
                    )
        if previous is not None:
            previous(statistics)

    with collector.with_value(observe):  # type: ignore[arg-type]  # Hypothesis declares it DynamicVariable(None).
        yield counts


def rejection(draws: Counter[str]) -> float | None:
    """The share of decided draws rejected, or None where no draw was seen."""
    decided = draws["valid"] + draws["interesting"] + draws["invalid"]
    return draws["invalid"] / decided if decided else None


# A share is judged only where the run's examples make at least this many expected at the least share. Each
# least share is about a third of the share measured, so a judged share falls below it by chance with a
# probability of about 1e-9 (Poisson, 60 expected, at most 20 seen). The `ci` and `deep` profiles judge every
# share declared; `dev`, with 200 examples, judges those of 10% or more.
JUDGED_FROM = 20

# The draw floor. A feature drawn as an example's first choice with chance p is not shown in a binomial count
# of the examples, n and p: Hypothesis keeps the first choices of each example it makes afresh through the
# mutations it then makes of it, six at most (`ConjectureRunner.generate_mutations_from`), and, among a run's
# first 50 examples, through the simplest extension of the same prefix, run before it. So one draw shows in
# at most CLUSTER examples, and a run of n examples holds at least n / CLUSTER draws. Measured over the
# refusal properties at `ci` (2026-10-15), a draw shows in 5.7 to 7.0 examples on average, by fault, and a
# fault's count varies five to seven times as much as a binomial count would. The floor counts the run as
# n / CLUSTER draws, each shown in SHOWN examples, below every fault's mean: it is SHOWN times the largest
# count of draws below which the feature then falls with a probability of at most FALSE_FAILURE. A floor
# below LEAST_DRAWS cannot be judged: the feature must be drawn more often, among fewer.
CLUSTER = 8
SHOWN = 5
FALSE_FAILURE = 1e-6
LEAST_DRAWS = 10
# The profiles that judge a drawn feature by its draw floor. `deep` holds each to a third of its share, as a
# declared feature, and `dev`, whose 200 examples leave no drawn feature's floor judged, judges none.
DRAW_FLOORS = frozenset({"ci"})


def binomial_floor(draws: int, chance: float) -> int:
    """The largest count that the successes of `draws` draws, each with probability `chance`, fall below
    with a probability of at most FALSE_FAILURE."""
    if chance >= 1:
        return draws
    below = 0.0
    for count in range(draws + 1):
        below += math.exp(
            math.lgamma(draws + 1)
            - math.lgamma(count + 1)
            - math.lgamma(draws - count + 1)
            + count * math.log(chance)
            + (draws - count) * math.log1p(-chance)
        )
        if below > FALSE_FAILURE:
            return count
    return draws


def draw_floor(examples: int, chance: float) -> int:
    """The draw floor of a feature drawn with probability `chance`, in a run of `examples` examples."""
    return SHOWN * binomial_floor(examples // CLUSTER, chance)


def feature_shortfalls(
    counts: Counts, declared: dict[str, float], drawn: Collection[str] = (), *, by_draws: bool = False
) -> list[str]:
    """Each judged feature below its least share or its floor, and each feature recorded but not declared.
    `drawn` names the features of which each example shows one, drawn alike; `by_draws` holds them to their
    draw floor, and otherwise to a third of their share as declared features."""
    examples = counts.draws["valid"] + counts.draws["interesting"]
    problems = [
        f"feature {name!r} recorded but not declared"
        for name in sorted(counts.features.keys() - declared.keys() - set(drawn))
    ]
    least_shares = dict(declared)
    if drawn and by_draws:
        floor = draw_floor(examples, 1 / len(drawn))
        if floor < LEAST_DRAWS:
            problems.append(
                f"features {sorted(drawn)}: each, drawn among {len(drawn)}, has a floor of {floor} in"
                f" {examples} examples, below {LEAST_DRAWS}: draw them among fewer"
            )
        problems.extend(
            f"feature {name!r} in {counts.features[name]} of {examples} examples, below its floor of {floor}"
            for name in sorted(drawn)
            if counts.features[name] < floor
        )
    elif drawn:
        least_shares.update({name: 1 / len(drawn) / 3 for name in drawn})
    for name, least in sorted(least_shares.items()):
        share = counts.features[name] / examples if examples else 0.0
        if least * examples >= JUDGED_FROM and share < least:
            problems.append(f"feature {name!r} in {share:.1%} of {examples} examples, below {least:.0%}")
    return problems
