# SPDX-License-Identifier: Apache-2.0
"""What the property tests' audits count, read from Hypothesis's statistics.

The draw-rejection audit: a property that rejects most of its draws (by `assume` or a `.filter`) searches less
widely than its example count says, and runs close to Hypothesis's `filter_too_much` health check, which fires
at 50 rejected draws before 10 valid ones. At the gate below, as in MADDENING's audit, that chance is about
1.8e-12 per run.

The feature audit: a property declares, with the `features` marker, the least share of its examples that must
show each feature the specification distinguishes, and records each example's features with
`support.feature`.
"""

from collections import Counter
from collections.abc import Callable, Generator
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


def feature_shortfalls(counts: Counts, declared: dict[str, float]) -> list[str]:
    """Each judged feature below its least share, and each feature recorded but not declared."""
    examples = counts.draws["valid"] + counts.draws["interesting"]
    problems = [
        f"feature {name!r} recorded but not declared" for name in sorted(counts.features.keys() - declared)
    ]
    for name, least in sorted(declared.items()):
        share = counts.features[name] / examples if examples else 0.0
        if least * examples >= JUDGED_FROM and share < least:
            problems.append(f"feature {name!r} in {share:.1%} of {examples} examples, below {least:.0%}")
    return problems
