# SPDX-License-Identifier: Apache-2.0
"""A test-only reference evaluator of a table, written from the specification's text (the S3 design's S3Q15).

`read_side_contract.md` section 7 has a consumer that evaluates a table in its own code check its evaluator
against the table evaluation suite (TE). OpenMaterica's own code claims no TE, so the conformance runner runs
the TE cases against this evaluator, under each precision and side it claims, and reports them as verified
against it, never as passed. It imports only the standard library. It was written from the text, not fitted
to the case files: each rule cites the sentence it applies, as `file:line` and a short quote, which
`test_table_evaluator.py` finds at that line.

It evaluates in one of three precisions:
- `binary64`: the text's formulas in doubles, in the text's order;
- `binary32`: each number of the case rounded to binary32 first, then each operation's result rounded to
  binary32, as an evaluator running in binary32 computes;
- `exact`: its numbers are `Fraction`s, but a knot's `-0`, which no `Fraction` holds, is returned as the
  double `-0.0`. A linear table's are exact. A log-log table's are exact where the value is rational, as
  every double and every point halfway between two doubles is (`_exact_loglog`); elsewhere the value is
  irrational, and comes from the text's formulas in `decimal`, worked at more digits until two precisions in
  a row round to the same double (Ziv's strategy, `_ziv`). The pieces after S3-te use it as an oracle.

Two limits are stated, not removed (S3Q29, maintainer, 2026-10-19):
- `exact` mode rests on Schanuel's conjecture (unproven, never contradicted): it takes a log-log value whose
  two exponents are both irrational to be irrational, so that Ziv's strategy ends (`_exact_loglog`);
- in `binary32` it raises on a log-log table with an `x` or a `y` that rounds to zero there, which it cannot
  take the logarithm of: a `ValueError` or a `ZeroDivisionError`, never a `Refusal`. No TE file holds such a
  table; a build's refusal of one for a `binary32` model is a later piece's.
"""

import math
import struct
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import partial
from itertools import pairwise
from typing import Generic, Literal, Protocol, Self, TypeVar

Precision = Literal["exact", "binary64", "binary32"]
Side = Literal["left", "right"]
Scheme = Literal["linear", "loglog"]

# The digits `exact` mode's logarithms and exponentials start at (S3Q15), and the most Ziv's strategy doubles
# them to before it gives up (`_ziv`).
EXACT_DIGITS = 60
EXACT_DIGITS_CAP = 60 * 2**5


@dataclass(frozen=True)
class Table:
    """A table as `record_format.md` section 6 gives it, without its axis and unit, which an evaluation does
    not use. One that breaks the structure a reader checks is refused here (`structural_fault`)."""

    x: tuple[float, ...]
    y: tuple[float, ...]
    scheme: Scheme
    edges: tuple[float, ...] = ()
    source_range: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        fault = structural_fault(self)
        if fault is not None:
            raise ValueError(f"not a table record_format.md section 6 allows: {fault}")


@dataclass(frozen=True)
class Evaluation:
    """What an evaluator returns at one axis value: the refusal, reported as an output of its own, or
    `in_range` with the value and the derivative. A number it does not return is `None`."""

    refused: bool
    in_range: bool | None = None
    value: Fraction | float | None = None
    derivative: Fraction | float | None = None


# read_side_contract.md:564-565 "an evaluator refuses, as the reader does, and the refusal comes before
# `in_range`"; read_side_contract.md:567-569 "It reports the refusal as an output of its own" ... "It returns
# no number there"
REFUSED = Evaluation(refused=True)


def evaluate(table: Table, at: float, precision: Precision = "binary64", side: Side = "right") -> Evaluation:
    """`table` evaluated at the axis value `at` in `precision`, by an evaluator that declares `side`: the side
    whose derivative it returns at an interior knot."""
    match precision:
        case "binary64":
            return _evaluate(table, at, side, _BINARY64)
        case "binary32":
            return _evaluate(table, at, side, _BINARY32)
        case "exact":
            return _evaluate(table, at, side, _EXACT)


def readable_range(table: Table) -> tuple[float, float]:
    """The table's readable range, as doubles."""
    return _readable_range(table.x, table.source_range)


def structural_fault(table: Table) -> str | None:
    """How `table` breaks `record_format.md` section 6 table items 1, 2 and 4, which a reader refuses
    (`form_invalid`), or `None`. An evaluator is given no such table, and this one refuses to evaluate one."""
    x, edges = table.x, table.edges
    # record_format.md:390-391 "`x` holds at least two distinct values and is non-decreasing, and `y` holds
    # one number for each entry of `x`"; record_format.md:394 "Numbers are compared by value, so `-0` equals
    # `0`."
    if len(set(x)) < 2:
        return "x holds fewer than two distinct values"
    if any(above < below for below, above in pairwise(x)):
        return "x decreases"
    if len(table.y) != len(x):
        return "y does not hold one number for each entry of x"
    # record_format.md:392-394 "with no number twice; each edge lies strictly between `x[0]` and `x[-1]` and
    # appears in `x` exactly twice, consecutively" ... "and no other x value repeats"
    if len(set(edges)) != len(edges):
        return "an edge is listed twice"
    if not all(x[0] < edge < x[-1] for edge in edges):
        return "an edge does not lie strictly between x[0] and x[-1]"
    if any(x.count(edge) != 2 for edge in edges):
        return "an edge is not in x exactly twice"
    if any(x.count(value) > 1 for value in x if value not in edges):
        return "an x value that is no edge repeats"
    # record_format.md:395 "A `loglog` table holds only positive `x` and `y`."
    if table.scheme == "loglog" and not all(number > 0 for number in (*x, *table.y)):
        return "a log-log table holds a number that is not positive"
    # record_format.md:414-416 "the first not greater than the second, sharing with `[x[0], x[-1]]` at least
    # one value that is no edge"
    if table.source_range is not None:
        low, high = table.source_range
        if high < low:
            return "source_range is out of order"
        shared_low, shared_high = max(x[0], low), min(x[-1], high)
        if shared_high < shared_low or (shared_low == shared_high and shared_low in edges):
            return "source_range shares no value that is no edge with [x[0], x[-1]]"
    return None


def to_binary32(value: float) -> float:
    """`value` rounded to the nearest binary32, ties to even; infinite beyond binary32's largest number."""
    try:
        rounded: float = struct.unpack("<f", struct.pack("<f", value))[0]
    except OverflowError:  # `struct` refuses a double that rounds to an infinity
        return math.copysign(math.inf, value)
    return rounded


class _Real(Protocol):
    """The arithmetic the text's formulas use, in one precision."""

    def __add__(self, other: Self, /) -> Self: ...
    def __sub__(self, other: Self, /) -> Self: ...
    def __mul__(self, other: Self, /) -> Self: ...
    def __truediv__(self, other: Self, /) -> Self: ...
    def __lt__(self, other: Self, /) -> bool: ...
    def __le__(self, other: Self, /) -> bool: ...
    def __float__(self) -> float: ...


N = TypeVar("N", bound=_Real)


@dataclass(frozen=True)
class _Arithmetic(Generic[N]):
    """One precision: how a number of the case enters it, and its natural logarithm and exponential. Where
    `loglog` and `loglog_slope` are set (`exact` mode), they compute the log-log value and derivative in place
    of the text's formulas in their order (`_loglog`, `_loglog_slope`), with the same arguments."""

    number: Callable[[float], N]
    ln: Callable[[N], N]
    exp: Callable[[N], N]
    loglog: "Callable[[N, N, N, N, N, _Arithmetic[N]], N] | None" = None
    loglog_slope: "Callable[[N, N, N, N, N, N, _Arithmetic[N]], N] | None" = None


class _Binary32(float):
    """A binary32 number. Each operation is computed in binary64 and its result rounded to binary32; for `+`,
    `-`, `*` and `/` on binary32 operands that is binary32's own correctly rounded result, since binary64 has
    more than twice binary32's 24 bits and two more (a known bound on double rounding, recalled)."""

    def __new__(cls, value: float) -> "_Binary32":
        return super().__new__(cls, to_binary32(value))

    def __add__(self, other: float, /) -> "_Binary32":
        return _binary32_result(float(self) + float(other))

    def __sub__(self, other: float, /) -> "_Binary32":
        return _binary32_result(float(self) - float(other))

    def __mul__(self, other: float, /) -> "_Binary32":
        return _binary32_result(float(self) * float(other))

    def __truediv__(self, other: float, /) -> "_Binary32":
        return _binary32_result(float(self) / float(other))


def _binary32_result(value: float) -> _Binary32:
    """An operation's result in binary32. Every result is rounded here, so that a test can round it
    otherwise."""
    return _Binary32(value)


def _binary32_ln(value: _Binary32) -> _Binary32:
    return _binary32_result(math.log(value))


def _binary32_exp(value: _Binary32) -> _Binary32:
    return _binary32_result(math.exp(value))


def _exact_ln(value: Fraction, digits: int) -> Fraction:
    with localcontext(prec=digits):
        return Fraction((Decimal(value.numerator) / Decimal(value.denominator)).ln())


def _exact_exp(value: Fraction, digits: int) -> Fraction:
    with localcontext(prec=digits):
        return Fraction((Decimal(value.numerator) / Decimal(value.denominator)).exp())


class _NegativeZero(Fraction):
    """`-0` in `exact` mode, which a plain `Fraction` cannot hold: it equals 0 in every comparison, and
    arithmetic on it gives plain `Fraction`s, as every result of the formulas is. So only a number returned as
    stored keeps it: a knot's `y` (`_value`), which `_returned` gives as the double `-0.0`."""


def _exact_number(value: float) -> Fraction:
    # README.md:147 "so `-0` in one is negative zero"
    return _NegativeZero(0) if value == 0 and math.copysign(1.0, value) < 0 else Fraction(value)


def _exact_arithmetic(digits: int) -> "_Arithmetic[Fraction]":
    """`exact` mode's numbers, with logarithms and exponentials to `digits` significant digits."""
    return _Arithmetic(
        number=_exact_number, ln=partial(_exact_ln, digits=digits), exp=partial(_exact_exp, digits=digits)
    )


_BINARY64 = _Arithmetic[float](number=float, ln=math.log, exp=math.exp)
# README.md:221 "a `binary32` evaluator first rounds each number of the case to the nearest `binary32`"
_BINARY32 = _Arithmetic[_Binary32](number=_Binary32, ln=_binary32_ln, exp=_binary32_exp)


@dataclass(frozen=True)
class _Knots(Generic[N]):
    """A table's numbers in one precision, with that precision's arithmetic."""

    x: tuple[N, ...]
    y: tuple[N, ...]
    scheme: Scheme
    edges: tuple[N, ...]
    source_range: tuple[N, N] | None
    arithmetic: _Arithmetic[N]


def _knots(table: Table, arithmetic: _Arithmetic[N]) -> _Knots[N]:
    number = arithmetic.number
    source_range = table.source_range
    return _Knots(
        x=tuple(map(number, table.x)),
        y=tuple(map(number, table.y)),
        scheme=table.scheme,
        edges=tuple(map(number, table.edges)),
        source_range=None if source_range is None else (number(source_range[0]), number(source_range[1])),
        arithmetic=arithmetic,
    )


def _evaluate(table: Table, at: float, side: Side, arithmetic: _Arithmetic[N]) -> Evaluation:
    knots = _knots(table, arithmetic)
    point = arithmetic.number(at)
    # record_format.md:404-405 "An operating value is compared with these ends and with the edges by value and
    # exactly"; read_side_contract.md:564 "At a declared edge, wherever it lies, inside the readable range or
    # outside it, an evaluator refuses"
    if point in knots.edges:
        return REFUSED
    low, high = _readable_range(knots.x, knots.source_range)
    if low <= point <= high:
        value = _value(knots, point)
        derivative = _derivative(knots, point, value, side, low, high)
        return Evaluation(
            refused=False, in_range=True, value=_returned(value), derivative=_returned(derivative)
        )
    end = low if point < low else high
    # read_side_contract.md:565-567 "It refuses in the same way where a declared edge lies between its
    # condition and the readable range's nearest end, or on that end, since no extrapolation crosses an edge"
    if any(point < edge <= end or end <= edge < point for edge in knots.edges):
        return REFUSED
    # read_side_contract.md:540 "An evaluator returns, beside the value, `in_range`";
    # read_side_contract.md:545-547 "Outside a table's readable range, an evaluator's value is the value at
    # the range's nearest end, taken from inside the range" ... "and its derivative is zero". `end` is no edge
    # here, so its value is one-sided.
    value = _value(knots, end)
    zero = arithmetic.number(0.0)
    return Evaluation(refused=False, in_range=False, value=_returned(value), derivative=_returned(zero))


def _readable_range(x: tuple[N, ...], source_range: tuple[N, N] | None) -> tuple[N, N]:
    # record_format.md:403-404 "from `x[0]`, or `source_range[0]` where that is greater, to `x[-1]`, or
    # `source_range[1]` where that is smaller, inclusive"
    if source_range is None:
        return x[0], x[-1]
    low, high = source_range
    return (low if low > x[0] else x[0]), (high if high < x[-1] else x[-1])


def _value(knots: _Knots[N], point: N) -> N:
    """The value at `point`, a point of the table that is no edge."""
    if point in knots.x:
        # A knot that is no edge is in `x` once (record_format.md:393-394 "no other x value repeats"), and the
        # formulas of both intervals beside it give its `y` there. The `y` is returned as stored, as the TE
        # suite's README has it ("At a knot the value is that knot's `y`"), so a `-0` stays negative zero,
        # in `exact` mode too (`_NegativeZero`).
        return knots.y[knots.x.index(point)]
    # record_format.md:410-411 "the interval used is the one whose two knots bracket the read"
    return _interpolate(knots, _interval(knots.x, point, "right"), point)


def _derivative(knots: _Knots[N], point: N, value: N, side: Side, low: N, high: N) -> N | None:
    # read_side_contract.md:559-560 "Where the readable range is one point, it has no inside: the evaluator
    # returns no derivative there"
    if low == high:
        return None
    # read_side_contract.md:556-558 "At an end of a table's readable range, an interior knot of `x` included,
    # the derivative is the one from inside the range, whatever side the evaluator declares: item 3's side
    # applies only at an interior knot strictly inside the readable range."
    if point == low:
        side = "right"
    elif point == high:
        side = "left"
    # read_side_contract.md:553-554 "At an interior knot the derivative depends on the side. An evaluator
    # states which side it returns there"
    return _slope(knots, _interval(knots.x, point, side), point, value)


def _interval(x: tuple[N, ...], point: N, side: Side) -> int:
    """The index `i` of the interval `[x[i], x[i + 1]]` on `side` of `point`: below it, `x[i] < point <= x[i +
    1]`, or above it, `x[i] <= point < x[i + 1]`. Between two knots both are the interval that brackets it."""
    # record_format.md:411-412 "strictly where an edge is concerned, so a read just below an edge uses the
    # knot below it"; read_side_contract.md:558-559 "the value and derivative below it come from the interval
    # below, and above it from the interval above"
    return (bisect_left(x, point) if side == "left" else bisect_right(x, point)) - 1


def _interpolate(knots: _Knots[N], i: int, point: N) -> N:
    x0, x1, y0, y1 = knots.x[i], knots.x[i + 1], knots.y[i], knots.y[i + 1]
    if knots.scheme == "linear":
        # read_side_contract.md:551 "Linear interpolation within `[x0, x1]` is `y0 + (x - x0) * (y1 - y0) /
        # (x1 - x0)`"
        return y0 + (point - x0) * (y1 - y0) / (x1 - x0)
    loglog = knots.arithmetic.loglog or _loglog
    return loglog(x0, x1, y0, y1, point, knots.arithmetic)


def _loglog(x0: N, x1: N, y0: N, y1: N, point: N, arithmetic: _Arithmetic[N]) -> N:
    ln, exp = arithmetic.ln, arithmetic.exp
    # read_side_contract.md:551-552 "Log-log interpolation is `exp(ln y0 + (ln x - ln x0) * (ln y1 - ln y0) /
    # (ln x1 - ln x0))`, in natural logarithms"
    return exp(ln(y0) + (ln(point) - ln(x0)) * (ln(y1) - ln(y0)) / (ln(x1) - ln(x0)))


def _slope(knots: _Knots[N], i: int, point: N, value: N) -> N:
    """The derivative within the interval `[x[i], x[i + 1]]` at `point`, where the value is `value`."""
    slope = _linear_slope if knots.scheme == "linear" else knots.arithmetic.loglog_slope or _loglog_slope
    return slope(knots.x[i], knots.x[i + 1], knots.y[i], knots.y[i + 1], point, value, knots.arithmetic)


def _linear_slope(x0: N, x1: N, y0: N, y1: N, point: N, value: N, arithmetic: _Arithmetic[N]) -> N:
    # read_side_contract.md:537-538 "A derivative is the value's derivative with respect to the axis": for
    # item 2's linear formula, its interval's slope (calculus, not quoted).
    return (y1 - y0) / (x1 - x0)


def _loglog_slope(x0: N, x1: N, y0: N, y1: N, point: N, value: N, arithmetic: _Arithmetic[N]) -> N:
    # read_side_contract.md:561 "For a log-log table, the derivative within an interval is `(y / x) * (ln y1 -
    # ln y0) / (ln x1 - ln x0)`"
    ln = arithmetic.ln
    return (value / point) * (ln(y1) - ln(y0)) / (ln(x1) - ln(x0))


def _returned(number: _Real | None) -> Fraction | float | None:
    """A number as the evaluator returns it: a `Fraction` in `exact` mode, but a knot's `-0` as the double
    `-0.0`; a plain float otherwise."""
    if isinstance(number, _NegativeZero):
        return -0.0
    if number is None or isinstance(number, Fraction):
        return number
    return float(number)


# `exact` mode's log-log formulas. With a = point / x0, b = x1 / x0 and c = y1 / y0, item 2's value is
# y0 * a ** e with e = ln c / ln b, and also y0 * c ** t with t = ln a / ln b, and item 5's derivative is
# (value / point) * e (algebra, not quoted). Where e or t is rational, the value is computed exactly wherever
# it is rational, and the derivative too where e is. A rational value with e and t both irrational, that is
# with neither c nor a a rational power of b, would make ln(value / y0) * ln b equal ln a * ln c, which
# Schanuel's conjecture (unproven, never contradicted) rules out. Elsewhere the value is irrational, so no
# double and no point halfway between two, and the text's formulas are worked in `decimal` by Ziv's
# strategy. At a halfway point that strategy alone could only land on either side, or give up.


def _exact_loglog(
    x0: Fraction, x1: Fraction, y0: Fraction, y1: Fraction, point: Fraction, arithmetic: _Arithmetic[Fraction]
) -> Fraction:
    a, b, c = point / x0, x1 / x0, y1 / y0
    for base, exponent in ((a, _log_ratio(c, b)), (c, _log_ratio(a, b))):
        power = None if exponent is None else _rational_power(base, exponent)
        if power is not None:
            return y0 * power
    return _ziv(partial(_loglog, x0, x1, y0, y1, point), arithmetic)


def _exact_loglog_slope(
    x0: Fraction,
    x1: Fraction,
    y0: Fraction,
    y1: Fraction,
    point: Fraction,
    value: Fraction,
    arithmetic: _Arithmetic[Fraction],
) -> Fraction:
    exponent = _log_ratio(y1 / y0, x1 / x0)
    if exponent is not None:
        return value / point * exponent
    return _ziv(partial(_loglog_slope, x0, x1, y0, y1, point, value), arithmetic)


def _ziv(compute: Callable[[_Arithmetic[Fraction]], Fraction], arithmetic: _Arithmetic[Fraction]) -> Fraction:
    """`compute` in `arithmetic`, at `EXACT_DIGITS` digits, then again at twice the digits, and so on, until
    two in a row round to the same double; past `EXACT_DIGITS_CAP`, an `ArithmeticError`, never a guess."""
    found, digits = compute(arithmetic), EXACT_DIGITS
    while digits < EXACT_DIGITS_CAP:
        digits *= 2
        refined = compute(_exact_arithmetic(digits))
        if _double(refined) == _double(found):
            return refined
        found = refined
    raise ArithmeticError(f"no two successive precisions up to {digits} digits round to the same double")


def _double(number: Fraction) -> float:
    """`number` rounded to the nearest double, ties to even: an infinity of its sign where that is beyond the
    largest double, where `float` raises."""
    try:
        return float(number)
    except OverflowError:
        # record_format.md:64 "a number that rounds to an infinity: under IEEE 754 rounding to nearest, ties
        # to even". `math.copysign` would take `number` as a float, and raise again.
        return math.inf if number > 0 else -math.inf


def _log_ratio(r: Fraction, s: Fraction) -> Fraction | None:
    """`ln r / ln s`, `r` and `s` positive and `s` not 1, where it is rational, else None. The logarithms of
    pairwise coprime integers above 1 are independent over the rationals (by unique factorization), so the
    ratio is rational exactly where `r`'s and `s`'s exponents over such integers are proportional."""
    base = _coprime_base((r.numerator, r.denominator, s.numerator, s.denominator))
    of_r, of_s = _exponents(r, base), _exponents(s, base)
    ratio = next(Fraction(in_r, in_s) for in_r, in_s in zip(of_r, of_s, strict=True) if in_s)
    return ratio if all(in_r == ratio * in_s for in_r, in_s in zip(of_r, of_s, strict=True)) else None


def _coprime_base(numbers: Iterable[int]) -> list[int]:
    """Pairwise coprime integers above 1 of which each of `numbers`, all positive, is a product of powers:
    each shared divisor split off in turn, with no factoring into primes."""
    base: list[int] = []
    pending = [number for number in numbers if number > 1]
    while pending:
        number = pending.pop()
        shared = next((element for element in base if math.gcd(number, element) > 1), None)
        if shared is None:
            base.append(number)
        elif shared != number:
            base.remove(shared)
            divisor = math.gcd(number, shared)
            pending += [part for part in (divisor, number // divisor, shared // divisor) if part > 1]
    return base


def _exponents(r: Fraction, base: list[int]) -> list[int]:
    """The exponent of each element of `base` in `r`, a product of their powers."""
    return [_multiplicity(r.numerator, element) - _multiplicity(r.denominator, element) for element in base]


def _multiplicity(number: int, element: int) -> int:
    count = 0
    while number % element == 0:
        number //= element
        count += 1
    return count


def _rational_power(r: Fraction, exponent: Fraction) -> Fraction | None:
    """`r ** exponent`, `r` positive, where it is rational, else None: with `exponent` `p / q` in lowest
    terms, exactly where `r`'s numerator and denominator are `q`-th powers of integers."""
    numerator = _integer_root(r.numerator, exponent.denominator)
    denominator = _integer_root(r.denominator, exponent.denominator)
    if numerator is None or denominator is None:
        return None
    return Fraction(numerator, denominator) ** exponent.numerator


def _integer_root(number: int, degree: int) -> int | None:
    """The `degree`-th root of `number`, positive, where it is an integer, else None: Newton's method on
    integers, from above."""
    root = 1 << -(-number.bit_length() // degree)
    while True:
        better = ((degree - 1) * root + number // root ** (degree - 1)) // degree
        if better >= root:
            return root if root**degree == number else None
        root = better


_EXACT = replace(_exact_arithmetic(EXACT_DIGITS), loglog=_exact_loglog, loglog_slope=_exact_loglog_slope)
