# SPDX-License-Identifier: Apache-2.0
"""What the property tests' audits count, read from Hypothesis's statistics.

The draw-rejection audit: a property that rejects most of its draws (by `assume` or a `.filter`) searches less
widely than its example count says, and runs close to Hypothesis's `filter_too_much` health check, which fires
at 50 rejected draws before 10 valid ones. At the gate below, as in MADDENING's audit, that chance is about
1.8e-12 per run.

The feature audit: a property declares, with the `features` marker, the least share of its examples that must
show each feature the specification distinguishes, and records each example's features with
`support.feature`. A property that draws one of several features alike as its first choice, as a refusal
property draws its fault, declares them with the `drawn` marker instead; one that declares the chance that a
draw shows each feature, measured, as the writer schema's acceptance properties do, and the json and records
shards' properties where a least share failed a run too often, declares them with the `chances` marker. At
the `ci` profile, each drawn feature and each feature declared by its chance is held to its draw floor
(`draw_floor`).
"""

import math
from collections import Counter
from collections.abc import Callable, Collection, Generator, Mapping
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


# Where Hypothesis 6.169 keeps the seed it drew a test's last run under, where it drew one at random
# (`core.get_random_for_wrapped_test`); None where the run was derandomised or seeded by `@seed` or
# `--hypothesis-seed`. Private state: `tests/unit/test_audit_replay.py` fails if it is gone.
GENERATED_SEED = "_hypothesis_internal_use_generated_seed"


def replay(test: object, name: str, profile: str) -> str:
    """How to draw again a run whose audit failed, where Hypothesis drew it at random. An audit fails after
    Hypothesis's run has passed, so Hypothesis prints no seed and stores no example: without this, the run is
    lost. Hypothesis also draws constants from the modules outside `tests/` that are loaded, so a run that
    collects less, as of the test's file alone, draws other examples under the same seed."""
    seed = getattr(test, GENERATED_SEED, None)
    if seed is None:
        return ""
    return (
        f" (Hypothesis drew this run at random under the seed {seed}: to draw it again, run the same pytest "
        f"command at MATERICA_HYPOTHESIS_PROFILE={profile} with -k {name} --hypothesis-seed={seed}, or with "
        f"@seed({seed}) on the test; a run that collects less, as of this file alone, draws other examples)"
    )


# A share is judged only where the run's examples make at least this many expected at the least share. Each
# least share is about a third of the share measured. Were the examples independent, a share at this gate
# would fall below it by chance with a probability of about 1e-9 (Poisson, 60 expected, at most 20 seen). They
# are not: Hypothesis shows one draw in up to CLUSTER examples (below). With the clusters measured on the
# writer schema's acceptance properties (2026-10-15: 6.2 examples on average at `ci`, 4.7 at `dev`, a count
# varying up to 8 times as much as a binomial count), a feature shown by whole clusters at the gate falls
# below its least share with a probability of about 1e-2 at either profile. Those properties' least shares
# failed a run with a probability of about 1.5e-6 at `ci` and 1e-3 at `dev`, computed from the measured
# clusters, so they declare their features by their chances instead (`chances`). So do the json and
# records shards' properties, measured on each (2026-10-15: 1.5 to 6.7 examples a cluster, by property and
# profile), for each feature whose least share failed a run with a probability above 1e-6 at `ci` or 1e-3 at
# `dev`. The two shards' least shares failed a run with a probability of about 7e-3 at `ci` and 2e-2 at `dev`,
# and one of them failed 16 of 2,000 `dev` runs (`test_versions_order_as_their_integers`, feature `long`).
# Two models give these figures, each taking the measured clusters as independent: the earlier analyses' sums
# the fewest clusters a run held, a bound that overstates a common feature's spread (it gave `long` 13%); the
# other draws clusters until a run's examples are made, and predicts the failures seen (`long` 0.95%, against
# 0.8%). A feature was chosen by the bound; the figures are the other's, the bound's "at most" where cited.
# The least shares kept fail a run of the two shards with a probability of about 2e-6 at `ci` and 5e-4 at
# `dev`, most of it `test_the_envelope_checks_agree_with_the_reader_schema`'s `card_accepted` (4e-4). The
# `ci` and `deep` profiles judge every share declared; `dev`, with 200 examples, judges those of 10% or more.
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


# Each profile's rule (RULES). `ci` judges a drawn feature, and one declared by its chance, by its draw floor,
# a floor below LEAST_DRAWS failing. `deep` holds each to a third of its share or chance, as a declared
# feature. `dev`, whose 200 examples leave no drawn feature's floor judged, judges none, and holds a feature
# declared by its chance to its draw floor where that is at least LEAST_DRAWS, judging no other.
# For the acceptance properties' chances, from the measured clusters: a run of both falls short with a
# probability of about 3e-10 at `ci` and 7e-7 at `dev`, and at most 2e-22 at `deep` (three runs measured). For
# the json and records shards': about 2e-8 a run of the two at `ci`, nearly all HP3's regions, and 1e-15 at
# `dev`, where one is judged; at `deep`, three runs of each property held each at 2.6 times its least share
# or more.
class Rule(TypedDict):
    """How a profile judges the features: the arguments it gives `feature_shortfalls`."""

    by_draws: bool
    chance_floors: bool


RULES: dict[str, Rule] = {
    "dev": {"by_draws": False, "chance_floors": True},
    "ci": {"by_draws": True, "chance_floors": True},
    "deep": {"by_draws": False, "chance_floors": False},
}


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
    counts: Counts,
    declared: dict[str, float],
    drawn: Collection[str] = (),
    *,
    by_draws: bool = False,
    chances: Mapping[str, float] | None = None,
    chance_floors: bool = False,
) -> list[str]:
    """Each judged feature below its least share or its floor, and each feature recorded but not declared.
    `drawn` names the features of which each example shows one, drawn alike; `chances` gives other features
    each the chance that one draw shows it. `by_draws` holds both to their draw floors, a floor below
    LEAST_DRAWS failing; `chance_floors` holds those of `chances` to theirs where it is at least LEAST_DRAWS,
    judging no other; and otherwise each is held to a third of its chance, one over their number for the
    drawn, as a declared feature."""
    examples = counts.draws["valid"] + counts.draws["interesting"]
    chances = {} if chances is None else dict(chances)
    problems = [
        f"feature {name!r} recorded but not declared"
        for name in sorted(counts.features.keys() - declared.keys() - set(drawn) - chances.keys())
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
    if by_draws or chance_floors:
        floors = {name: draw_floor(examples, chance) for name, chance in chances.items()}
        unjudged = sorted(name for name, floor in floors.items() if floor < LEAST_DRAWS)
        if unjudged and by_draws:
            problems.append(
                f"features {unjudged}: each, at its chance, has a floor below {LEAST_DRAWS} in {examples}"
                " examples: draw it more often, its family in parts"
            )
        problems.extend(
            f"feature {name!r} in {counts.features[name]} of {examples} examples, below its floor of {floor}"
            for name, floor in sorted(floors.items())
            if (by_draws or name not in unjudged) and counts.features[name] < floor
        )
    else:
        least_shares.update({name: chance / 3 for name, chance in chances.items()})
    for name, least in sorted(least_shares.items()):
        share = counts.features[name] / examples if examples else 0.0
        if least * examples >= JUDGED_FROM and share < least:
            problems.append(f"feature {name!r} in {share:.1%} of {examples} examples, below {least:.0%}")
    return problems
