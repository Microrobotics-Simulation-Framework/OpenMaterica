# SPDX-License-Identifier: Apache-2.0
"""Tables that step 8 accepts (`record_format.md` section 6, table items 1, 2 and 4), each with operating
values at every place table item 3 tells apart, for the properties of `core/evaluate.py`.

A table is drawn by choices made first, each kept beside it for the feature audit: its scheme; the magnitude
of its numbers (ordinary, any double, doubles a few units apart, subnormal); whether it has edges; whether
signed zeros sit among its knots and values (linear only: a log-log table's numbers are positive); and the
kind of its `source_range`. Its operating values are its knots and edges, the readable range's ends and
`source_range`'s, the double either side of each, zero of each sign, a value inside each interval with room,
one beyond each end of the readable range, and the largest doubles.

The table evaluation cases are read here too, as tables and entries, for the oracle's control and the unit
test of `core/evaluate.py`; and so are log-log values halfway between two doubles, with their exact values
(`ties`).
"""

import functools
import itertools
import math
import random
import sys
from fractions import Fraction
from typing import Literal, NamedTuple, TypeAlias

from hypothesis import strategies as st

from materica.core.evaluate import Scheme
from materica.core.jsonio import JsonValue
from tests.conformance import runner
from tests.property.strategies import SIZE, Size

LARGEST = sys.float_info.max
SMALLEST_NORMAL = sys.float_info.min

SCHEMES: tuple[Scheme, ...] = ("linear", "loglog")
Magnitude: TypeAlias = Literal["ordinary", "any_double", "adjacent_doubles", "subnormal"]
MAGNITUDES: tuple[Magnitude, ...] = ("ordinary", "any_double", "adjacent_doubles", "subnormal")
RangeKind: TypeAlias = Literal["no_source_range", "narrower", "wider", "across_an_end", "one_point"]
RANGE_KINDS: tuple[RangeKind, ...] = ("no_source_range", "narrower", "wider", "across_an_end", "one_point")
Order: TypeAlias = Literal["non_decreasing", "non_increasing"]
ORDERS: tuple[Order, ...] = ("non_decreasing", "non_increasing")


class Table(NamedTuple):
    x: tuple[float, ...]
    y: tuple[float, ...]
    scheme: Scheme
    edges: tuple[float, ...]
    source_range: tuple[float, float] | None


class Choices(NamedTuple):
    """What a table was drawn by."""

    magnitude: Magnitude
    with_edges: bool
    signed_zeros: bool
    range_kind: RangeKind
    order: Order | None


class Reading(NamedTuple):
    table: Table
    choices: Choices
    at: tuple[float, ...]  # the operating values, in ascending order, -0 before 0


def key(number: float) -> tuple[float, float]:
    """Orders doubles by value, `-0` before `0`, and tells the two apart."""
    return number, math.copysign(1.0, number)


def beside(number: float) -> list[float]:
    """The double either side of `number`, where finite."""
    return [
        near
        for near in (math.nextafter(number, -math.inf), math.nextafter(number, math.inf))
        if math.isfinite(near)
    ]


# Strategies built once, as `tests/property/README.md` asks.
BOOLEANS = st.booleans()
SIGNED_ZEROS = st.sampled_from((0.0, -0.0))
STEPS = st.integers(1, 3)


@functools.cache
def numbers(magnitude: Magnitude, positive: bool) -> st.SearchStrategy[float]:
    """Numbers of a magnitude: positive for a log-log table (table item 2), of either sign, zero included,
    otherwise."""
    if magnitude == "ordinary":
        return st.floats(1e-3 if positive else -1e3, 1e3, allow_subnormal=False)
    if magnitude == "subnormal":
        return st.floats(
            0.0 if positive else -SMALLEST_NORMAL, SMALLEST_NORMAL, exclude_min=positive, exclude_max=True
        )
    if positive:
        return st.floats(min_value=0.0, exclude_min=True, allow_infinity=False)
    return st.floats(allow_nan=False, allow_infinity=False)


@st.composite
def chain(draw: st.DrawFn, count: int, positive: bool, ascending: bool) -> list[float]:
    """`count` doubles from a start, each one to three units in the last place from the one before, rising, or
    else each way at random."""
    start = draw(
        st.floats(min_value=0.0 if positive else -LARGEST / 2, max_value=LARGEST / 2, exclude_min=positive)
    )
    found = [start]
    while len(found) < count:
        up = ascending or draw(BOOLEANS)
        step = found[-1]
        for _ in range(draw(STEPS)):
            step = math.nextafter(step, math.inf if up or (positive and step <= 5e-324) else -math.inf)
        found.append(step)
    return found


@st.composite
def knots(draw: st.DrawFn, magnitude: Magnitude, positive: bool, count: int) -> list[float]:
    """`count` distinct doubles of a magnitude, in ascending order. A value drawn twice is replaced by the
    double beside the others, so that no draw is thrown away."""
    if magnitude == "adjacent_doubles":
        return draw(chain(count, positive, ascending=True))
    found = sorted(set(draw(st.lists(numbers(magnitude, positive), min_size=count, max_size=count))))
    while len(found) < count:
        lower, upper = math.nextafter(found[0], -math.inf), math.nextafter(found[-1], math.inf)
        if math.isfinite(lower) and (lower > 0 or not positive):
            found.insert(0, lower)
        elif math.isfinite(upper):
            found.append(upper)
        else:
            room = next(i for i, (a, b) in enumerate(itertools.pairwise(found)) if math.nextafter(a, b) < b)
            found.insert(room + 1, math.nextafter(found[room], math.inf))
    return found


@st.composite
def values(draw: st.DrawFn, magnitude: Magnitude, positive: bool, count: int) -> list[float]:
    """`count` values of a magnitude, any order."""
    if magnitude == "adjacent_doubles":
        return draw(chain(count, positive, ascending=False))
    return draw(st.lists(numbers(magnitude, positive), min_size=count, max_size=count))


def inside(draw: st.DrawFn, distinct: list[float]) -> list[float]:
    """The distinct knots, and a double strictly inside each interval between two with room, in order."""
    found = [distinct[0]]
    for low, high in itertools.pairwise(distinct):
        if math.nextafter(low, math.inf) < high:
            found.append(draw(st.floats(low, high, exclude_min=True, exclude_max=True)))
        found.append(high)
    return found


def below(number: float) -> st.SearchStrategy[float]:
    """A double strictly below `number`, the one beside it among the drawn ones; `number` is not the least."""
    return st.one_of(
        st.just(math.nextafter(number, -math.inf)),
        st.floats(max_value=number, exclude_max=True, allow_nan=False, allow_infinity=False),
    )


def above(number: float) -> st.SearchStrategy[float]:
    """A double strictly above `number`; `number` is not the largest."""
    return st.one_of(
        st.just(math.nextafter(number, math.inf)),
        st.floats(min_value=number, exclude_min=True, allow_nan=False, allow_infinity=False),
    )


@st.composite
def source_range(
    draw: st.DrawFn, kind: RangeKind, distinct: list[float], edges: list[float]
) -> tuple[float, float] | None:
    """A `source_range` of a kind, sharing with `[x[0], x[-1]]` a value that is no edge (table item 4)."""
    first, last = distinct[0], distinct[-1]
    candidates = inside(draw, distinct)
    if kind == "no_source_range":
        return None
    if kind == "narrower":
        final = len(candidates) - 1
        low, high = draw(
            st.sampled_from(
                [
                    (low, high)
                    for low in range(final)
                    for high in range(low + 1, final + 1)
                    if (low, high) != (0, final) and shares_a_value(candidates[low], candidates[high], edges)
                ]
            )
        )
        return candidates[low], candidates[high]
    if kind == "wider":
        return (
            draw(st.one_of(st.just(first), below(first))) if first > -LARGEST else first,
            draw(st.one_of(st.just(last), above(last))) if last < LARGEST else last,
        )
    if kind == "across_an_end":
        sides = [side for side, open_ in (("lower", first > -LARGEST), ("upper", last < LARGEST)) if open_]
        if not sides:
            return first, candidates[-2]
        if draw(st.sampled_from(sides)) == "lower":
            return draw(below(first)), draw(st.sampled_from(candidates[:-1]))
        return draw(st.sampled_from(candidates[1:])), draw(above(last))
    point = draw(st.sampled_from([value for value in candidates if all(value != edge for edge in edges)]))
    return point, point


def shares_a_value(low: float, high: float, edges: list[float]) -> bool:
    """Whether `[low, high]`, `low < high`, holds a double that is no edge."""
    return math.nextafter(low, math.inf) < high or any(
        all(end != edge for edge in edges) for end in (low, high)
    )


def signed_zero(draw: st.DrawFn) -> float:
    return draw(SIGNED_ZEROS)


@st.composite
def tables(
    draw: st.DrawFn,
    size: Size = SIZE,
    *,
    with_edges: bool | None = None,
    signed_zeros: bool | None = None,
    order: Order | None = None,
) -> tuple[Table, Choices]:
    """A table step 8 accepts, and its choices. `with_edges` and `signed_zeros` fix those; `order` draws
    values in that order along `x`, with no edges."""
    scheme = draw(st.sampled_from(SCHEMES))
    positive = scheme == "loglog"
    magnitude = draw(st.sampled_from(MAGNITUDES))
    edged = order is None and (draw(BOOLEANS) if with_edges is None else with_edges)
    zeros = not positive and (draw(BOOLEANS) if signed_zeros is None else signed_zeros)
    kind = draw(st.sampled_from(RANGE_KINDS))
    least = 3 if edged or kind == "narrower" else 2
    distinct = draw(knots(magnitude, positive, draw(st.integers(least, max(least, size.leaves // 2)))))
    if zeros and all(knot != 0 for knot in distinct):
        distinct = sorted([*distinct, 0.0])
    if zeros:
        distinct = [signed_zero(draw) if knot == 0 else knot for knot in distinct]
    edge_at: set[int] = draw(st.sets(st.integers(1, len(distinct) - 2), min_size=1)) if edged else set()
    # One value for each knot, and a second, above it, for each edge.
    below_or_at = draw(values(magnitude, positive, len(distinct)))
    above_edge = iter(draw(values(magnitude, positive, len(edge_at))))
    x: list[float] = []
    y: list[float] = []
    for index, knot in enumerate(distinct):
        x.append(knot)
        y.append(below_or_at[index])
        if index in edge_at:
            x.append(signed_zero(draw) if knot == 0 else knot)
            y.append(next(above_edge))
    if zeros:
        for index in draw(st.sets(st.integers(0, len(y) - 1), min_size=1)):
            y[index] = signed_zero(draw)
    if order is not None:
        y.sort(reverse=order == "non_increasing")
    edges = [signed_zero(draw) if distinct[index] == 0 else distinct[index] for index in sorted(edge_at)]
    edges = draw(st.permutations(edges))
    table = Table(tuple(x), tuple(y), scheme, tuple(edges), draw(source_range(kind, distinct, edges)))
    return table, Choices(magnitude, edged, zeros, kind, order)


def readable_ends(table: Table) -> tuple[float, float]:
    """The readable range's ends, by table item 3's sentence, for drawing operating values."""
    low, high = table.x[0], table.x[-1]
    if table.source_range is not None:
        low, high = max(low, table.source_range[0]), min(high, table.source_range[1])
    return low, high


@st.composite
def readings(
    draw: st.DrawFn,
    size: Size = SIZE,
    *,
    with_edges: bool | None = None,
    signed_zeros: bool | None = None,
    order: Order | None = None,
) -> Reading:
    """A table of `tables`, with its operating values."""
    table, choices = draw(tables(size, with_edges=with_edges, signed_zeros=signed_zeros, order=order))
    low, high = readable_ends(table)
    places = [*table.x, *table.edges, low, high, *(table.source_range or ())]
    found = [*places, *(near for place in places for near in beside(place)), 0.0, -0.0, LARGEST, -LARGEST]
    found += inside(draw, sorted(set(table.x)))
    if low > -LARGEST:
        found.append(draw(below(low)))
    if high < LARGEST:
        found.append(draw(above(high)))
    by_key = {key(number): number for number in found}
    return Reading(table, choices, tuple(by_key[place] for place in sorted(by_key)))


class CaseEntry(NamedTuple):
    case: str  # the case file's name
    table: Table
    at: float
    expected: dict[str, JsonValue]  # its entry of `expected.evaluations`


def _numbers(value: JsonValue) -> tuple[float, ...]:
    assert isinstance(value, list), value
    assert all(isinstance(number, float) for number in value), value
    return tuple(number for number in value if isinstance(number, float))


def case_entries() -> list[CaseEntry]:
    """Every entry of every table evaluation case, with its table and its operating value."""
    found: list[CaseEntry] = []
    for case_file in runner.discover():
        if case_file.suite != "table_evaluation":
            continue
        request = case_file.request
        assert isinstance(request, dict), case_file.path.name
        table = request["table"]
        evaluations = case_file.expected["evaluations"]
        assert isinstance(table, dict), case_file.path.name
        assert isinstance(evaluations, list), case_file.path.name
        scheme = table["scheme"]
        assert scheme in SCHEMES, case_file.path.name
        source_range = _numbers(table["source_range"]) if "source_range" in table else None
        read = Table(
            _numbers(table["x"]),
            _numbers(table["y"]),
            "linear" if scheme == "linear" else "loglog",
            _numbers(table["edges"]),
            None if source_range is None else (source_range[0], source_range[1]),
        )
        for at, expected in zip(_numbers(request["at"]), evaluations, strict=True):
            assert isinstance(expected, dict), case_file.path.name
            found.append(CaseEntry(case_file.path.name, read, at, expected))
    return found


class Tie(NamedTuple):
    family: str
    x: tuple[float, float]
    y: tuple[float, float]
    at: float
    value: Fraction  # the exact value, halfway between two doubles


def ties() -> list[Tie]:
    """Log-log tables through two knots of `y = y0 (x / x0)^k`, a power law the log-log formula follows
    exactly, read where the exact value `y0 (at / x0)^k`, computed in fractions alone, lies halfway between
    two doubles: `y = x^2` and `y = x^3` in the normal range and among subnormals; `y = 1 / x` among the
    least subnormals, where one unit is a large share of the value; `y = x^2` over [1, 3], whose ratios 3 and
    9 share a factor; and `y = 3 x^(3/2)`, whose exponent is no integer and whose square roots lie in the
    lower half of an octave, where a root search started from the bit count alone begins below them. A fixed
    seed draws the operating values."""
    u = 5e-324
    rng = random.Random(1)
    found: list[Tie] = []

    def add(family: str, x: tuple[float, float], y0: float, k: Fraction, at: float) -> None:
        y1 = float(Fraction(y0) * power(Fraction(x[1]) / Fraction(x[0]), k))
        found.append(Tie(family, x, (y0, y1), at, Fraction(y0) * power(Fraction(at) / Fraction(x[0]), k)))

    # at = a / 2^26, a odd and at least 2^26.5, so that at^2 needs 54 bits.
    for a in (rng.randrange(94906267, 2**27, 2) for _ in range(100)):
        add("y = x^2", (1.0, 2.0), 1.0, Fraction(2), a / 2**26)
    # at = n / 2^23, n odd and at least 208065 (2^17.67), so that at^3 needs 54 bits.
    for n in (rng.randrange(208065, 2**18, 2) for _ in range(100)):
        add("y = x^3", (2.0**-6, 2.0**-5), 2.0**-18, Fraction(3), n / 2**23)
    # at = 1 + j / 2^m, j odd: y0 (at)^k is (2^m + j)^k / 2 units of the least subnormal.
    for m in range(1, 26):
        for j in sorted({rng.randrange(1, 2**m, 2) for _ in range(4)}):
            add("y = x^2 among subnormals", (1.0, 2.0), 2.0 ** (2 * m - 1) * u, Fraction(2), 1 + j / 2**m)
    for m in range(1, 17):
        for j in sorted({rng.randrange(1, 2**m, 2) for _ in range(6)}):
            add("y = x^3 among subnormals", (1.0, 2.0), 2.0 ** (3 * m - 1) * u, Fraction(3), 1 + j / 2**m)
    for k in range(3, 200, 2):
        add("y = 1 / x among subnormals", (u, k * u), k * u, Fraction(-1), 2 * u)
    for a in (rng.randrange(94906267, 2**27, 2) for _ in range(100)):
        add("y = x^2 over [1, 3]", (1.0, 3.0), 1.0, Fraction(2), a / 2**26)
    # at = p^2 / 2^34, p odd with 2^53 <= 3 p^3 < 2^54, so that 3 at^(3/2) = 3 p^3 / 2^51 needs 54 bits; p
    # lies below 2^17.5, in the lower half of its octave.
    for p in (rng.randrange(144265, 181761, 2) for _ in range(100)):
        add("y = 3 x^(3/2)", (1.0, 4.0), 3.0, Fraction(3, 2), p * p / 2**34)
    return found


def power(base: Fraction, exponent: Fraction) -> Fraction:
    """`base` to a rational power with denominator 1 or 2, where the result is rational."""
    roots = [math.isqrt(part) if exponent.denominator == 2 else part for part in base.as_integer_ratio()]
    root = Fraction(*roots)
    assert root**exponent.denominator == base, (base, exponent)
    return root**exponent.numerator
