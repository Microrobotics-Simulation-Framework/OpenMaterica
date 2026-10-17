# SPDX-License-Identifier: Apache-2.0
"""(15) The table evaluator (`core/evaluate.py`), the S3 design's HP17 to HP19, against an oracle written from
the text alone (`record_format.md` section 6, table items 1 to 4; `read_side_contract.md` sections 5 and 7):

- HP17, agreement: over drawn tables (both schemes; edges; `source_range` absent, narrower, within one
  interval, wider, across an end, of one point; every magnitude; subnormals, the least of them following
  `y = c / x` so that reads fall halfway between two doubles; `-0`) and operating values at every place
  table item 3 tells apart, the evaluator never raises; "at an edge", "in the readable range" and "no
  number" fall exactly where the oracle puts them; and the number is the oracle's, the exact value rounded
  once, bit for bit.
- HP18, knot exactness: a read at a knot that is no edge, or outside the readable range at an end that is
  one, gives the stored `y`, bit for bit, `-0` included.
- HP19, bracketing and monotonicity: the knots that bracket a read are the interval table item 3 names, and
  the value lies between their two `y`; over knots whose `y` are monotone, with no edge, reads are monotone in
  the operating value.

The oracle compares numbers as fractions, finds a read's interval by scanning every pair of knots, and
computes a linear value exactly in another arrangement, `(y0 (x1 - x) + y1 (x - x0)) / (x1 - x0)`. A log-log
value it computes in decimal at 100 digits as `y0 * (y1 / y0) ** (ln(x / x0) / ln(x1 / x0))`, rounded at once
where that is provably the value's rounding, and decides exactly whether the value is a point halfway between
two doubles where it lies near one (`loglog`). It shares no code with the evaluator. It shares the standard
library: `fractions` and the rounding of a fraction to a double, ties to even; `decimal`'s arithmetic,
logarithm and exponential (the evaluator bounds the value with them, rounding each step down and up, where
the oracle bounds its error by analysis) and the rounding of a decimal to a double. Where the evaluator
decides that a value is rational over a basis found by gcds and integer roots, the oracle factors into primes.
Its own controls: it gives every number and refusal of the table evaluation cases, and the exact value at
constructed ties.

The mutants it kills are in `test_evaluate_mutants.py`, each at the assertion it names: every assertion's
message begins with its label.
"""

import itertools
import math
import sys
from collections import Counter
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from functools import cache, lru_cache
from typing import NamedTuple

import pytest
from hypothesis import example, given

from materica.core import evaluate
from tests.property.support import feature, same
from tests.property.tables import (
    SMALLEST_NORMAL,
    Choices,
    RangeKind,
    Reading,
    Table,
    beside,
    case_entries,
    readings,
    ties,
)

# The digits of the oracle's log-log number, and how near a point halfway between two doubles the number must
# lie, relatively, for the oracle to decide exactly whether the value is that point (`loglog`).
ORACLE_DIGITS = 100
NEAR = Fraction(1, 10**70)
_ORACLE = Context(prec=ORACLE_DIGITS)


def accepted(table: Table) -> bool:
    """Whether step 8 accepts the table's numbers, by table items 1, 2 and 4: a draw the evaluator's contract
    covers."""
    x = [Fraction(number) for number in table.x]
    edges = [Fraction(edge) for edge in table.edges]
    repeated = sorted({value for value in x if x.count(value) > 1})
    structure = (
        len(set(x)) >= 2
        and all(a <= b for a, b in itertools.pairwise(x))
        and len(table.y) == len(table.x)
        and len(set(edges)) == len(edges)
        and all(x[0] < edge < x[-1] and x.count(edge) == 2 for edge in edges)
        and all(x[x.index(edge) + 1] == edge for edge in edges)
        and repeated == sorted(edges)
    )
    positive = table.scheme == "linear" or all(number > 0 for number in (*table.x, *table.y))
    if table.source_range is None:
        return structure and positive
    low, high = (Fraction(end) for end in table.source_range)
    shared_low, shared_high = max(low, x[0]), min(high, x[-1])
    shares = shared_low < shared_high or (shared_low == shared_high and shared_low not in edges)
    return structure and positive and low <= high and shares


class Position(NamedTuple):
    at_edge: bool
    in_range: bool
    refused: bool  # no number: at an edge, or beyond one
    source: float | None  # where the number is taken: the operating value, or the readable range's end


def ends(table: Table) -> tuple[float, float]:
    """The readable range: "from `x[0]`, or `source_range[0]` where that is greater, to `x[-1]`, or
    `source_range[1]` where that is smaller, inclusive" (table item 3)."""
    low, high = table.x[0], table.x[-1]
    if table.source_range is not None:
        if Fraction(table.source_range[0]) > Fraction(low):
            low = table.source_range[0]
        if Fraction(table.source_range[1]) < Fraction(high):
            high = table.source_range[1]
    return low, high


def position(table: Table, at: float) -> Position:
    """Table item 3: "A read exactly at an edge is refused ..., wherever the edge lies"; inside the readable
    range, the value at `at`; outside it, "the value at the range's nearest end, taken from inside the range"
    (`read_side_contract.md` section 5), but where "an edge lies between the operating value and the readable
    range's nearest end, or on that end", none."""
    point = Fraction(at)
    low, high = ends(table)
    edges = [Fraction(edge) for edge in table.edges]
    in_range = Fraction(low) <= point <= Fraction(high)
    if point in edges:
        return Position(True, in_range, True, None)
    if in_range:
        return Position(False, True, False, at)
    if point < Fraction(low):
        end, beyond = low, any(point < edge <= Fraction(low) for edge in edges)
    else:
        end, beyond = high, any(Fraction(high) <= edge < point for edge in edges)
    return Position(False, False, beyond, None if beyond else end)


def bracket(table: Table, at: float) -> tuple[int, int]:
    """The knots of `x` that bracket `at`, a double of `[x[0], x[-1]]` on no edge, by a scan of every pair:
    `(i, i)` at the knot `x[i]`, else `(i, i + 1)` with `x[i] < at < x[i + 1]`."""
    point = Fraction(at)
    for index, knot in enumerate(table.x):
        if Fraction(knot) == point:
            return index, index
    for index in range(len(table.x) - 1):
        if Fraction(table.x[index]) < point < Fraction(table.x[index + 1]):
            return index, index + 1
    raise AssertionError(f"drawn: no knots bracket {at!r} in {table}")


@lru_cache(maxsize=4096)
def loglog(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    """The log-log value (`read_side_contract.md` section 7 item 2), rounded once to the nearest double, ties
    to even.

    The number is `y0 * c ** (ln a / ln b)`, with `a = x / x0`, `b = x1 / x0` and `c = y1 / y0`, in decimal at
    100 digits, each step correctly rounded. A ratio of two distinct doubles lies at least 2^-53 from 1, so
    each logarithm is at least 1.1e-16 in size where it is not 0, and within 4.5e-84 of its value, relatively;
    the exponent within 1.4e-83, relatively, and, being at most 1455 in size, within 2.1e-80 absolutely; so
    the number lies within 2.1e-80 of the value, relatively (the bound's arithmetic is the oracle's own,
    checked by hand, not by a program). So where the number lies farther than `NEAR` from every halfway point,
    the value lies on the same side of each, and the number rounds as the value does.

    Nearer a halfway point `m`, whether the value is `m` is decided exactly (`is_the_value`). If it is, `m`
    rounds to the even double beside it. If not, the number's rounding is the value's unless the value lies
    within 2.1e-80 of `m` and is not `m`."""
    with localcontext(_ORACLE):
        share = (Decimal(at) / Decimal(x0)).ln() / (Decimal(x1) / Decimal(x0)).ln()
        number = Decimal(y0) * ((Decimal(y1) / Decimal(y0)).ln() * share).exp()
    nearest, approximate = float(number), Fraction(number)
    halfway = min(halfway_points(nearest), key=lambda point: abs(point - approximate))
    if abs(halfway - approximate) <= NEAR * approximate and is_the_value(x0, x1, y0, y1, at, halfway):
        return float(halfway)
    return nearest


def halfway_points(number: float) -> list[Fraction]:
    """The points halfway between `number`, a positive double, and the doubles either side of it."""
    return [
        (Fraction(number) + Fraction(near)) / 2
        for near in (math.nextafter(number, 0.0), math.nextafter(number, math.inf))
        if math.isfinite(near)
    ]


def is_the_value(x0: float, x1: float, y0: float, y1: float, at: float, point: Fraction) -> bool:
    """Whether `point` is the log-log value `y0 a^(ln c / ln b)` (`loglog`), exactly: where
    `ln(point / y0) ln b = ln a ln c`. Each logarithm of a positive rational is a sum of logarithms of primes
    with integer coefficients, its prime factors' exponents (`logarithm`), so each side is a product of two
    such sums (`product`), and the two sides are equal where their coefficients agree. Where they disagree,
    the point is not the value, provided the logarithms of primes are algebraically independent, as Schanuel's
    conjecture has it (unproven)."""
    exact = [Fraction(number) for number in (x0, x1, y0, y1, at)]
    left = product(logarithm(point / exact[2]), logarithm(exact[1] / exact[0]))
    right = product(logarithm(exact[4] / exact[0]), logarithm(exact[3] / exact[2]))
    return left == right


def logarithm(number: Fraction) -> Counter[int]:
    """The natural logarithm of a positive rational as the coefficients of the primes' logarithms."""
    found = prime_factors(number.numerator)
    found.subtract(prime_factors(number.denominator))
    return found


def product(first: Counter[int], second: Counter[int]) -> Counter[tuple[int, int]]:
    """The product of two such sums, as the coefficients of `ln p ln q`, `p <= q`."""
    found: Counter[tuple[int, int]] = Counter()
    for p, i in first.items():
        for q, j in second.items():
            found[min(p, q), max(p, q)] += i * j
    return found


# Miller and Rabin's test with these witnesses tells every number below 3.3e24 prime or composite.
_WITNESSES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def prime_factors(number: int) -> Counter[int]:
    """The prime factors of a positive integer, each with its exponent: here a power of 2 times an odd number
    below 2^55, the numerator or denominator of a double or of a point halfway between two. The witnesses
    divide out first, then Pollard's rho splits what is left until each part passes Miller and Rabin's
    test."""
    found = Counter[int]()
    for prime in _WITNESSES:
        while number % prime == 0:
            number //= prime
            found[prime] += 1
    parts = [number] if number > 1 else []
    while parts:
        part = parts.pop()
        if is_prime(part):
            found[part] += 1
        else:
            factor = a_factor(part)
            parts += [factor, part // factor]
    return found


@cache
def is_prime(number: int) -> bool:
    """Miller and Rabin's test of an odd number with no factor among the witnesses."""
    odd, halvings = number - 1, 0
    while odd % 2 == 0:
        odd, halvings = odd // 2, halvings + 1
    for witness in _WITNESSES:
        power = pow(witness, odd, number)
        if power in (1, number - 1):
            continue
        for _ in range(halvings - 1):
            power = power * power % number
            if power == number - 1:
                break
        else:
            return False
    return True


def a_factor(number: int) -> int:
    """A factor of a composite odd number other than 1 and itself: Pollard's rho, with Floyd's cycle finding,
    the polynomial's constant raised until a step finds one."""
    for constant in itertools.count(1):
        slow = fast = 2
        found = 1
        while found == 1:
            slow = (slow * slow + constant) % number
            fast = (fast * fast + constant) % number
            fast = (fast * fast + constant) % number
            found = math.gcd(slow - fast, number)
        if found != number:
            return found
    raise AssertionError("unreachable")


def exact(table: Table, at: float) -> float:
    """The table's value at `at`, a double of `[x[0], x[-1]]` on no edge: at a knot, its `y` as stored (the
    S3 design, S3Q16); else the formula of its scheme (`read_side_contract.md` section 7 item 2), rounded
    once."""
    below, above = bracket(table, at)
    if below == above:
        return table.y[below]
    x0, x1, y0, y1 = table.x[below], table.x[above], table.y[below], table.y[above]
    if table.scheme == "loglog":
        return loglog(x0, x1, y0, y1, at)
    point = Fraction(at)
    return float(
        (Fraction(y0) * (Fraction(x1) - point) + Fraction(y1) * (point - Fraction(x0)))
        / (Fraction(x1) - Fraction(x0))
    )


def raised(at: float, table: Table, error: Exception) -> AssertionError:
    return AssertionError(f"raised: {error!r} at {at!r} on {table}")


def check_agreement(reading: Reading) -> None:
    """Where each operating value lies first, then what is read there, so that a fault of where is caught as
    one, not by the number it leads to."""
    table = reading.table
    x, y, scheme, edges, source_range = table
    positions = [position(table, at) for at in reading.at]
    for at, expected in zip(reading.at, positions, strict=True):
        try:
            found = (evaluate.on_edge(edges, at), evaluate.in_readable_range(x, source_range, at))
        except Exception as error:
            raise raised(at, table, error) from error
        assert found == expected[:2], f"position: {found}, not {expected}, at {at!r} on {table}"
    for at, expected in zip(reading.at, positions, strict=True):
        try:
            number = evaluate.table_value(x, y, scheme, edges, source_range, at)
        except Exception as error:
            raise raised(at, table, error) from error
        assert (number is None) == expected.refused, (
            f"position: {number!r}, not {expected}, at {at!r} on {table}"
        )
        if number is not None and expected.source is not None:
            oracle = exact(table, expected.source)
            assert same(oracle, number), f"value: {number!r}, not {oracle!r}, at {at!r} on {table}"


def on_a_knot(table: Table, at: float) -> bool:
    return any(Fraction(knot) == Fraction(at) for knot in table.x)


def without_a_knot(table: Table) -> bool:
    """Whether the readable range is more than one point and holds no knot (the S3 design's S3Q8 rule 1)."""
    low, high = (Fraction(end) for end in ends(table))
    return low < high and not any(low <= Fraction(knot) <= high for knot in table.x)


_U = 5e-324


def subnormal_tie(table: Table, at: float) -> Reading:
    """A read HP17 drew at the `ci` profile (the first three) or that is the least of its kind (the rest),
    where the log-log value lies halfway between two subnormals; the S3b-1 review's R1. Bit for bit, it fails
    an evaluator or an oracle that rounds such a value the wrong way."""
    kind: RangeKind = "no_source_range" if table.source_range is None else "wider"
    return Reading(table, Choices("subnormal", False, False, kind, None), (at,))


# Every feature by its chance: the least share it showed in eight runs of 2,000 examples (seeds 1 to 4, at
# the small size and the original one; 2026-10-17, measured again after the S3b-1 review's strategy changes),
# rounded down. A choice's chance is near the share it is drawn with, but Hypothesis draws the first of a
# choice more often.
@pytest.mark.chances(
    linear=0.47,
    loglog=0.45,
    ordinary=0.18,
    any_double=0.15,
    adjacent_doubles=0.16,
    subnormal=0.17,
    least_subnormals=0.13,
    with_edges=0.4,
    signed_zeros=0.21,
    no_source_range=0.16,
    narrower=0.12,
    within_an_interval=0.16,
    wider=0.14,
    across_an_end=0.09,
    one_point=0.14,
    at_an_edge_inside=0.21,
    at_an_edge_outside=0.21,
    beyond_an_edge=0.24,
    end_between_knots=0.33,
    end_on_a_knot=0.7,
    subnormal_y=0.4,
    negative_zero_y=0.17,
    range_without_a_knot=0.14,
)
@example(
    subnormal_tie(
        Table((_U, 2e-323, 3e-323), (_U, 1e-323, 1.5e-323), "loglog", (), (0.0, 9.716508993683519e307)),
        2.5e-323,
    )
)
@example(
    subnormal_tie(
        Table(
            (_U, 3.0052337292636e-309, 2.0698175165701283e-308, 2.069817516570129e-308),
            (3.0052337292636e-309, _U, 2.0698175165701283e-308, 3.0052337292636e-309),
            "loglog",
            (),
            None,
        ),
        1e-323,
    )
)
@example(
    subnormal_tie(
        Table(
            (_U, 9.8819390526424e-310, 5.00570041176814e-309, 8.541824180569135e-309),
            (9.8819390526424e-310, _U, 8.541824180569135e-309, 5.00570041176814e-309),
            "loglog",
            (),
            None,
        ),
        1e-323,
    )
)
@example(
    subnormal_tie(Table((_U, 4.24436392890612e-309), (4.24436392890612e-309, _U), "loglog", (), None), 1e-323)
)
@example(subnormal_tie(Table((_U, 5 * _U), (5 * _U, _U), "loglog", (), None), 2 * _U))
@example(subnormal_tie(Table((_U, 7 * _U), (7 * _U, _U), "loglog", (), None), 2 * _U))
@given(readings())
def test_hp17_the_evaluator_agrees_with_the_oracle(reading: Reading) -> None:
    table, choices = reading.table, reading.choices
    assert accepted(table), f"drawn: {table}"
    for choice in (table.scheme, choices.magnitude, choices.range_kind):
        feature(choice)
    feature("with_edges", choices.with_edges)
    feature("signed_zeros", choices.signed_zeros)
    positions = [position(table, at) for at in reading.at]
    feature("at_an_edge_inside", any(found.at_edge and found.in_range for found in positions))
    feature("at_an_edge_outside", any(found.at_edge and not found.in_range for found in positions))
    feature("beyond_an_edge", any(found.refused and not found.at_edge for found in positions))
    ends_read = [found.source for found in positions if not found.in_range and found.source is not None]
    feature("end_between_knots", any(not on_a_knot(table, end) for end in ends_read))
    feature("end_on_a_knot", any(on_a_knot(table, end) for end in ends_read))
    feature("subnormal_y", any(0 < abs(number) < SMALLEST_NORMAL for number in table.y))
    feature("negative_zero_y", any(same(-0.0, number) for number in table.y))
    feature("range_without_a_knot", without_a_knot(table))
    check_agreement(reading)


def check_knots(reading: Reading) -> None:
    table = reading.table
    x, y, scheme, edges, source_range = table
    for index, knot in enumerate(x):
        if any(knot == edge for edge in edges):
            continue
        for at in (0.0, -0.0) if knot == 0 else (knot,):
            number = evaluate.value(x, y, scheme, at)
            assert same(y[index], number), f"stored: {number!r}, not {y[index]!r}, at {at!r} on {table}"
    for at in reading.at:
        source = position(table, at).source
        if source is not None and on_a_knot(table, source):
            stored = y[bracket(table, source)[0]]
            read = evaluate.table_value(x, y, scheme, edges, source_range, at)
            assert read is not None, f"stored: no number at {at!r} on {table}"
            assert same(stored, read), f"stored: {read!r}, not {stored!r}, at {at!r} on {table}"


@pytest.mark.chances(
    linear=0.47,
    loglog=0.45,
    negative_zero_at_a_knot=0.26,
    zero_knot=0.35,
    knot_beside_an_edge=0.41,
    end_on_a_knot=0.7,
)
@given(readings(signed_zeros=True))
def test_hp18_a_read_at_a_knot_gives_its_y_as_stored(reading: Reading) -> None:
    table = reading.table
    assert accepted(table), f"drawn: {table}"
    feature(table.scheme)
    plain = [index for index, knot in enumerate(table.x) if all(knot != edge for edge in table.edges)]
    feature("negative_zero_at_a_knot", any(same(-0.0, table.y[index]) for index in plain))
    feature("zero_knot", any(table.x[index] == 0 for index in plain))
    feature(
        "knot_beside_an_edge",
        any(knot in table.edges for index in plain for knot in table.x[max(index - 1, 0) : index + 2]),
    )
    positions = [position(table, at) for at in reading.at]
    feature(
        "end_on_a_knot",
        any(
            not found.in_range and found.source is not None and on_a_knot(table, found.source)
            for found in positions
        ),
    )
    check_knots(reading)


def check_bracketing(reading: Reading) -> None:
    table = reading.table
    x, y, scheme, edges, _ = table
    for at in reading.at:
        if not x[0] <= at <= x[-1] or any(at == edge for edge in edges):
            continue
        below, above = bracket(table, at)
        found = evaluate.interval(x, at)
        assert found == (below, above), f"interval: {found}, not {(below, above)}, at {at!r} on {table}"
        number = evaluate.value(x, y, scheme, at)
        low, high = sorted((y[below], y[above]))
        assert low <= number <= high, f"between: {number!r} outside [{low!r}, {high!r}] at {at!r} on {table}"


@pytest.mark.chances(
    linear=0.47,
    loglog=0.45,
    with_edges=0.4,
    rising=0.78,
    falling=0.8,
    flat=0.27,
    beside_an_edge=0.4,
)
@given(readings())
def test_hp19_a_read_lies_between_the_y_of_the_knots_that_bracket_it(reading: Reading) -> None:
    table = reading.table
    assert accepted(table), f"drawn: {table}"
    feature(table.scheme)
    feature("with_edges", reading.choices.with_edges)
    pairs = [(table.y[i], table.y[i + 1]) for i in range(len(table.x) - 1) if table.x[i] != table.x[i + 1]]
    feature("rising", any(low < high for low, high in pairs))
    feature("falling", any(low > high for low, high in pairs))
    feature("flat", any(low == high for low, high in pairs))
    feature("beside_an_edge", any(at in beside(edge) for edge in table.edges for at in reading.at))
    check_bracketing(reading)


def check_monotone(reading: Reading) -> None:
    table = reading.table
    rising = reading.choices.order == "non_decreasing"
    numbers = [evaluate.table_value(*table, at) for at in reading.at]
    for (at, number), (next_at, next_number) in itertools.pairwise(zip(reading.at, numbers, strict=True)):
        assert number is not None, f"monotone: no number at {at!r} on {table}"
        assert next_number is not None, f"monotone: no number at {next_at!r} on {table}"
        ordered = number <= next_number if rising else number >= next_number
        assert ordered, f"monotone: {number!r} at {at!r}, then {next_number!r} at {next_at!r}, on {table}"


@pytest.mark.chances(
    non_decreasing=0.47,
    non_increasing=0.43,
    linear=0.47,
    loglog=0.43,
    flat_run=0.34,
    narrower=0.14,
)
@given(readings(order="non_decreasing") | readings(order="non_increasing"))
def test_hp19_reads_over_monotone_knots_are_monotone(reading: Reading) -> None:
    table, choices = reading.table, reading.choices
    assert accepted(table), f"drawn: {table}"
    assert choices.order is not None
    feature(table.scheme)
    feature(choices.order)
    feature("flat_run", any(a == b for a, b in itertools.pairwise(table.y)))
    feature("narrower", choices.range_kind == "narrower")
    check_monotone(reading)


def test_the_oracle_gives_every_number_and_refusal_of_the_table_evaluation_cases() -> None:
    """The oracle's own control: the cases, written from the text by another pass, agree with it."""
    entries = case_entries()
    for entry in entries:
        assert accepted(entry.table), entry.case
        found = position(entry.table, entry.at)
        if entry.expected.get("refused") is True:
            assert found.refused, (entry.case, entry.at)
            continue
        assert not found.refused, (entry.case, entry.at)
        assert found.in_range == entry.expected["in_range"], (entry.case, entry.at)
        assert found.source is not None
        number = entry.expected["value"]
        assert isinstance(number, float), (entry.case, entry.at)
        assert same(number, exact(entry.table, found.source)), (entry.case, entry.at)
    assert len(entries) >= 100


def test_the_oracle_gives_the_exact_value_where_it_is_halfway_between_two_doubles() -> None:
    """Its control at constructed ties, each value computed in fractions alone and checked to be halfway."""
    found = ties()
    for tie in found:
        nearest = float(tie.value)
        other = math.nextafter(nearest, math.inf if tie.value > Fraction(nearest) else -math.inf)
        assert 2 * tie.value == Fraction(nearest) + Fraction(other), tie
        assert same(nearest, loglog(*tie.x, *tie.y, tie.at)), tie
    assert len(found) >= 400


def never(*_: object) -> bool:
    return False


def test_without_its_exact_decision_the_oracle_misses_ties(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control that the exact decision is what gives the ties: at 100 digits alone, the number falls on
    either side of a halfway point."""
    loglog.cache_clear()
    monkeypatch.setattr(sys.modules[__name__], "is_the_value", never)
    try:
        missed = [tie for tie in ties() if not same(float(tie.value), loglog(*tie.x, *tie.y, tie.at))]
    finally:
        loglog.cache_clear()
    assert len(missed) >= 50, len(missed)


def test_the_exact_decision_tells_the_value_from_the_halfway_point_beside_it() -> None:
    """`is_the_value` both ways: true at each tie's halfway point, false at the next halfway point up, a
    rational that is not the value."""
    for tie in ties():
        nearest = float(tie.value)
        assert is_the_value(*tie.x, *tie.y, tie.at, tie.value), tie
        beyond = max(halfway_points(nearest)) if tie.value < Fraction(nearest) else None
        other = beyond if beyond is not None else max(halfway_points(math.nextafter(nearest, math.inf)))
        assert other != tie.value
        assert not is_the_value(*tie.x, *tie.y, tie.at, other), tie


REFUSED = {
    "one knot": Table((1.0,), (1.0,), "linear", (), None),
    "one distinct x": Table((1.0, 1.0), (1.0, 2.0), "linear", (), None),
    "x decreasing": Table((1.0, 3.0, 2.0), (1.0, 2.0, 3.0), "linear", (), None),
    "y one short": Table((1.0, 2.0, 3.0), (1.0, 2.0), "linear", (), None),
    "an edge listed twice, by value": Table(
        (-1.0, 0.0, 0.0, 1.0), (1.0, 2.0, 3.0, 4.0), "linear", (0.0, -0.0), None
    ),
    "an edge at x[0]": Table((1.0, 1.0, 2.0), (1.0, 2.0, 3.0), "linear", (1.0,), None),
    "an edge in x once": Table((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), "linear", (2.0,), None),
    "an edge in x three times": Table(
        (1.0, 2.0, 2.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0, 5.0), "linear", (2.0,), None
    ),
    "a repeated x that is no edge": Table((-1.0, -0.0, 0.0, 1.0), (1.0, 2.0, 3.0, 4.0), "linear", (), None),
    "a log-log x of 0": Table((0.0, 1.0), (1.0, 2.0), "loglog", (), None),
    "a log-log y below 0": Table((1.0, 2.0), (1.0, -2.0), "loglog", (), None),
    "source_range out of order": Table((1.0, 3.0), (1.0, 2.0), "linear", (), (2.5, 1.5)),
    "source_range disjoint": Table((1.0, 3.0), (1.0, 2.0), "linear", (), (4.0, 5.0)),
    "source_range meeting x only at an edge": Table(
        (1.0, 2.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0), "linear", (2.0,), (2.0, 2.0)
    ),
}


@pytest.mark.parametrize("table", REFUSED.values(), ids=REFUSED.keys())
def test_the_generator_self_check_refuses_each_table_step_8_refuses(table: Table) -> None:
    """`accepted`'s control (the S3b-1 review's L1): one table for each rule of table items 1, 2 and 4 that
    step 8 refuses. Each rule dropped from `accepted` lets one of them through, but three that others imply:
    distinct edges (the repeated values are a set), repeated values side by side (`x` is in order) and
    `source_range` in order (no value is shared otherwise)."""
    assert not accepted(table)


def test_the_generator_self_check_accepts_a_table_step_8_accepts() -> None:
    """Beside its control: an edge, and a `source_range` narrower at one end and meeting `x[-1]`."""
    assert accepted(Table((1.0, 2.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0), "linear", (2.0,), (1.5, 3.0)))
