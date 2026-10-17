# SPDX-License-Identifier: Apache-2.0
"""Mutants of the table evaluator (`core/evaluate.py`), each with one fault, and the property of
`test_evaluate_properties.py` that must kill each one, at the assertion it names. As in `test_mutants.py`,
each must die within the examples the `ci` profile gives a property, at the small size and at the original
one, and records the examples its kill took as `examples_to_kill`.

A fault is injected where the evaluator looks a name up when it runs: one of its module-level functions,
replaced. The first eight are the S3 design's (section 6.6). Of the other nine, six are broken evaluators of
the table evaluation suite's README made a reader's, the text's rules since the design among them (no number
beyond an edge, the end value of the readable range); one raises a refusal, where a read returns one (the code
design's rule 1); and two reach the assertions no design mutant does (`interval`, `monotone`).
"""

import math
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Collection, Sequence
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from typing import Any, NamedTuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from materica.core import evaluate
from materica.core.evaluate import Scheme
from tests.property import test_evaluate_properties as properties
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.support import MUTANT_SEARCH
from tests.property.tables import Reading, readings
from tests.property.test_mutants import setting

# Each property that kills a mutant, by name: its examples at a size, and its check.
KILLERS: dict[str, tuple[Callable[[Size], st.SearchStrategy[Reading]], Callable[[Reading], None]]] = {
    "HP17": (readings, properties.check_agreement),
    "HP18": (lambda size: readings(size, signed_zeros=True), properties.check_knots),
    "HP19": (readings, properties.check_bracketing),
    "HP19 monotone": (
        lambda size: readings(size, order="non_decreasing") | readings(size, order="non_increasing"),
        properties.check_monotone,
    ),
}
# Each assertion's label, by property: the start of its message.
LABELS = {
    "HP17": ("raised", "position", "value"),
    "HP18": ("stored",),
    "HP19": ("interval", "between"),
    "HP19 monotone": ("monotone",),
}


class Mutant(NamedTuple):
    name: str
    killer: str  # a key of KILLERS
    inject: Callable[[pytest.MonkeyPatch], None]
    dies_at: tuple[str, ...]  # the labels of the assertions its kill may fail, one of LABELS[killer]


INTERVAL = evaluate.interval
VALUE = evaluate.value
TABLE_VALUE = evaluate.table_value


def _knot_test_off_by_one(x: Sequence[float], at: float) -> tuple[int, int]:
    """The bracket search with `bisect_right`: one past a knot, so the knot is never found."""
    above = bisect_right(x, at)
    if x[above] == at:
        return above, above
    return above - 1, above


def _log10_for_x(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    with localcontext(Context(prec=evaluate.LOGLOG_DIGITS)):
        slope = (Decimal(y1).ln() - Decimal(y0).ln()) / (Decimal(x1).log10() - Decimal(x0).log10())
        return float((Decimal(y0).ln() + (Decimal(at).ln() - Decimal(x0).ln()) * slope).exp())


def _in_doubles(x: Sequence[float], y: Sequence[float], scheme: Scheme, at: float) -> float:
    """`read_side_contract.md` section 7 item 2's formulas in doubles, as written, a knot read through the
    interval below it."""
    above = max(bisect_left(x, at), 1)
    x0, x1, y0, y1 = x[above - 1], x[above], y[above - 1], y[above]
    if scheme == "linear":
        return y0 + (at - x0) * (y1 - y0) / (x1 - x0)
    ln = math.log
    return math.exp(ln(y0) + (ln(at) - ln(x0)) * (ln(y1) - ln(y0)) / (ln(x1) - ln(x0)))


def _x_alone(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    return x[0], x[-1]


def _never(*_: object) -> bool:
    return False


def _widened(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    if source_range is None:
        return x[0], x[-1]
    return min(x[0], source_range[0]), max(x[-1], source_range[1])


def _range_before_the_edge(
    x: Sequence[float],
    y: Sequence[float],
    scheme: Scheme,
    edges: Collection[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    """The readable range judged before the edge, so that an edge outside it reads as outside."""
    low, high = evaluate.readable_range(x, source_range)
    if low <= at <= high:
        return None if evaluate.on_edge(edges, at) else evaluate.value(x, y, scheme, at)
    if evaluate.beyond_an_edge(x, edges, source_range, at):
        return None
    return evaluate.value(x, y, scheme, low if at < low else high)


def _clamped_to_x(
    x: Sequence[float],
    y: Sequence[float],
    scheme: Scheme,
    edges: Collection[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    """Outside the readable range, the value at `x[0]` or `x[-1]`, as NumPy's `interp` clamps."""
    number = TABLE_VALUE(x, y, scheme, edges, source_range, at)
    if number is None or evaluate.in_readable_range(x, source_range, at):
        return number
    return y[0] if at < evaluate.readable_range(x, source_range)[0] else y[-1]


def _refusal_raised(
    x: Sequence[float],
    y: Sequence[float],
    scheme: Scheme,
    edges: Collection[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    number = TABLE_VALUE(x, y, scheme, edges, source_range, at)
    if number is None:
        raise ValueError("at or beyond an edge")
    return number


def _ends_excluded(x: Sequence[float], source_range: Sequence[float] | None, at: float) -> bool:
    low, high = evaluate.readable_range(x, source_range)
    return low < at < high


def _below_an_edge_from_above(x: Sequence[float], at: float) -> tuple[int, int]:
    """Just below an edge, the interval above it."""
    below, above = INTERVAL(x, at)
    if below != above and above + 1 < len(x) and x[above] == x[above + 1]:
        return above + 1, above + 2
    return below, above


def _interval_above(x: Sequence[float], at: float) -> tuple[int, int]:
    """Between two knots, the interval above them."""
    below, above = INTERVAL(x, at)
    return (below, above) if below == above else (below + 1, above + 1)


def _knot_through_a_fraction(x: Sequence[float], y: Sequence[float], scheme: Scheme, at: float) -> float:
    below, above = evaluate.interval(x, at)
    if below == above:
        return float(Fraction(y[below]))
    return VALUE(x, y, scheme, at)


def _t_from_the_upper_knot(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    """`t` computed as `(x - x1) / (x1 - x0)`, the S3 design's HP19 mutant."""
    t = (Fraction(at) - Fraction(x1)) / (Fraction(x1) - Fraction(x0))
    return float(Fraction(y0) + t * (Fraction(y1) - Fraction(y0)))


def _read_backwards(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    """`t` computed as `(x1 - x) / (x1 - x0)`: inside its interval's `y`, run the wrong way."""
    t = (Fraction(x1) - Fraction(at)) / (Fraction(x1) - Fraction(x0))
    return float(Fraction(y0) + t * (Fraction(y1) - Fraction(y0)))


MUTANTS = [
    # The S3 design's.
    Mutant(
        "bracket_search_off_by_one_at_a_knot",
        "HP17",
        setting(evaluate, "interval", _knot_test_off_by_one),
        ("raised", "value"),
    ),
    Mutant("loglog_interpolated_linearly", "HP17", setting(evaluate, "loglog", evaluate.linear), ("value",)),
    Mutant("log10_for_x_beside_ln_for_y", "HP17", setting(evaluate, "loglog", _log10_for_x), ("value",)),
    Mutant("formulas_in_doubles", "HP17", setting(evaluate, "value", _in_doubles), ("raised", "value")),
    Mutant(
        "source_range_ignored",
        "HP17",
        setting(evaluate, "readable_range", _x_alone),
        ("position",),
    ),
    Mutant("source_range_widening", "HP17", setting(evaluate, "readable_range", _widened), ("position",)),
    Mutant(
        "knot_through_a_fraction", "HP18", setting(evaluate, "value", _knot_through_a_fraction), ("stored",)
    ),
    Mutant(
        "t_from_the_upper_knot", "HP19", setting(evaluate, "linear", _t_from_the_upper_knot), ("between",)
    ),
    # The text's since.
    Mutant(
        "extrapolated_beyond_an_edge",
        "HP17",
        setting(evaluate, "beyond_an_edge", _never),
        ("position",),
    ),
    Mutant(
        "range_judged_before_the_edge",
        "HP17",
        setting(evaluate, "table_value", _range_before_the_edge),
        ("position",),
    ),
    Mutant("edges_ignored", "HP17", setting(evaluate, "on_edge", _never), ("position",)),
    Mutant("end_value_at_the_ends_of_x", "HP17", setting(evaluate, "table_value", _clamped_to_x), ("value",)),
    Mutant("refusal_raised", "HP17", setting(evaluate, "table_value", _refusal_raised), ("raised",)),
    Mutant("ends_excluded", "HP17", setting(evaluate, "in_readable_range", _ends_excluded), ("position",)),
    Mutant(
        "below_an_edge_from_the_interval_above",
        "HP17",
        setting(evaluate, "interval", _below_an_edge_from_above),
        ("value",),
    ),
    Mutant(
        "between_knots_the_interval_above",
        "HP19",
        setting(evaluate, "interval", _interval_above),
        ("interval",),
    ),
    Mutant(
        "interval_read_backwards",
        "HP19 monotone",
        setting(evaluate, "linear", _read_backwards),
        ("monotone",),
    ),
]


def kill(examples: st.SearchStrategy[Reading], check: Callable[[Reading], None]) -> tuple[int, str]:
    """The examples searched until `check` first fails, and its message; an AssertionError where it never
    does. Hypothesis runs the failing example once more to report it, which is not counted."""
    tried = 0
    first: list[tuple[int, str]] = []

    @MUTANT_SEARCH
    @given(examples)
    def search(example: Any) -> None:
        nonlocal tried
        tried += 1
        try:
            check(example)
        except AssertionError as error:
            first.append((tried, str(error)))
            raise

    try:
        search()
    except AssertionError:
        return first[0]
    raise AssertionError(f"the mutant survived {tried} examples")


@pytest.mark.parametrize("size", [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")])
@pytest.mark.parametrize("mutant", MUTANTS, ids=[mutant.name for mutant in MUTANTS])
def test_the_evaluator_mutant_is_killed_at_its_assertion(
    mutant: Mutant,
    size: Size,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    assert set(mutant.dies_at) <= set(LABELS[mutant.killer]), mutant.name
    mutant.inject(monkeypatch)
    examples, check = KILLERS[mutant.killer]
    tried, message = kill(examples(size), check)
    record_property("examples_to_kill", tried)
    assert message.split(":", 1)[0] in mutant.dies_at, message
