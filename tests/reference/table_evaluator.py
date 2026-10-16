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
- `exact`: linear tables in `fractions`, log-log ones with `decimal` at 60 digits; its numbers are
  `Fraction`s. The pieces after S3-te use it as an oracle.
"""

import math
import struct
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import pairwise
from typing import Generic, Literal, Protocol, Self, TypeVar

Precision = Literal["exact", "binary64", "binary32"]
Side = Literal["left", "right"]
Scheme = Literal["linear", "loglog"]

# The digits of `exact` mode's logarithms and exponentials (S3Q15).
EXACT_DIGITS = 60


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


# read_side_contract.md:483-484 "an evaluator refuses, as the reader does, and the refusal comes before
# `in_range`"; read_side_contract.md:486-488 "It reports the refusal as an output of its own" ... "It returns
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
    # record_format.md:333-334 "`x` holds at least two distinct values and is non-decreasing, and `y` holds
    # one number for each entry of `x`"; record_format.md:337 "Numbers are compared by value, so `-0` equals
    # `0`."
    if len(set(x)) < 2:
        return "x holds fewer than two distinct values"
    if any(above < below for below, above in pairwise(x)):
        return "x decreases"
    if len(table.y) != len(x):
        return "y does not hold one number for each entry of x"
    # record_format.md:335-337 "with no number twice; each edge lies strictly between `x[0]` and `x[-1]` and
    # appears in `x` exactly twice, consecutively" ... "and no other x value repeats"
    if len(set(edges)) != len(edges):
        return "an edge is listed twice"
    if not all(x[0] < edge < x[-1] for edge in edges):
        return "an edge does not lie strictly between x[0] and x[-1]"
    if any(x.count(edge) != 2 for edge in edges):
        return "an edge is not in x exactly twice"
    if any(x.count(value) > 1 for value in x if value not in edges):
        return "an x value that is no edge repeats"
    # record_format.md:338 "A `loglog` table holds only positive `x` and `y`."
    if table.scheme == "loglog" and not all(number > 0 for number in (*x, *table.y)):
        return "a log-log table holds a number that is not positive"
    # record_format.md:357-359 "the first not greater than the second, sharing with `[x[0], x[-1]]` at least
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
    """One precision: how a number of the case enters it, and its natural logarithm and exponential."""

    number: Callable[[float], N]
    ln: Callable[[N], N]
    exp: Callable[[N], N]


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


def _exact_ln(value: Fraction) -> Fraction:
    with localcontext(prec=EXACT_DIGITS):
        return Fraction((Decimal(value.numerator) / Decimal(value.denominator)).ln())


def _exact_exp(value: Fraction) -> Fraction:
    with localcontext(prec=EXACT_DIGITS):
        return Fraction((Decimal(value.numerator) / Decimal(value.denominator)).exp())


_BINARY64 = _Arithmetic[float](number=float, ln=math.log, exp=math.exp)
# README.md:212 "a `binary32` evaluator first rounds each number of the case to the nearest `binary32`"
_BINARY32 = _Arithmetic[_Binary32](number=_Binary32, ln=_binary32_ln, exp=_binary32_exp)
_EXACT = _Arithmetic[Fraction](number=Fraction, ln=_exact_ln, exp=_exact_exp)


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
    # record_format.md:347-348 "An operating value is compared with these ends and with the edges by value and
    # exactly"; read_side_contract.md:483 "At a declared edge, wherever it lies, inside the readable range or
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
    # read_side_contract.md:484-486 "It refuses in the same way where a declared edge lies between its
    # condition and the readable range's nearest end, or on that end, since no extrapolation crosses an edge"
    if any(point < edge <= end or end <= edge < point for edge in knots.edges):
        return REFUSED
    # read_side_contract.md:460 "An evaluator returns, beside the value, `in_range`";
    # read_side_contract.md:465-467 "Outside a table's readable range, an evaluator's value is the value at
    # the range's nearest end, taken from inside the range" ... "and its derivative is zero". `end` is no edge
    # here, so its value is one-sided.
    value = _value(knots, end)
    zero = arithmetic.number(0.0)
    return Evaluation(refused=False, in_range=False, value=_returned(value), derivative=_returned(zero))


def _readable_range(x: tuple[N, ...], source_range: tuple[N, N] | None) -> tuple[N, N]:
    # record_format.md:346-347 "from `x[0]`, or `source_range[0]` where that is greater, to `x[-1]`, or
    # `source_range[1]` where that is smaller, inclusive"
    if source_range is None:
        return x[0], x[-1]
    low, high = source_range
    return (low if low > x[0] else x[0]), (high if high < x[-1] else x[-1])


def _value(knots: _Knots[N], point: N) -> N:
    """The value at `point`, a point of the table that is no edge."""
    if point in knots.x:
        # A knot that is no edge is in `x` once (record_format.md:336-337 "no other x value repeats"), and the
        # formulas of both intervals beside it give its `y` there.
        return knots.y[knots.x.index(point)]
    # record_format.md:353-354 "the interval used is the one whose two knots bracket the read"
    return _interpolate(knots, _interval(knots.x, point, "right"), point)


def _derivative(knots: _Knots[N], point: N, value: N, side: Side, low: N, high: N) -> N | None:
    # read_side_contract.md:478-479 "Where the readable range is one point, it has no inside: the evaluator
    # returns no derivative there"
    if low == high:
        return None
    # read_side_contract.md:475-477 "At an end of a table's readable range, an interior knot of `x` included,
    # the derivative is the one from inside the range, whatever side the evaluator declares: item 3's side
    # applies only at an interior knot strictly inside the readable range."
    if point == low:
        side = "right"
    elif point == high:
        side = "left"
    # read_side_contract.md:472-473 "At an interior knot the derivative depends on the side. An evaluator
    # states which side it returns there"
    return _slope(knots, _interval(knots.x, point, side), point, value)


def _interval(x: tuple[N, ...], point: N, side: Side) -> int:
    """The index `i` of the interval `[x[i], x[i + 1]]` on `side` of `point`: below it, `x[i] < point <= x[i +
    1]`, or above it, `x[i] <= point < x[i + 1]`. Between two knots both are the interval that brackets it."""
    # record_format.md:354-355 "strictly where an edge is concerned, so a read just below an edge uses the
    # knot below it"; read_side_contract.md:477-478 "the value and derivative below it come from the interval
    # below, and above it from the interval above"
    return (bisect_left(x, point) if side == "left" else bisect_right(x, point)) - 1


def _interpolate(knots: _Knots[N], i: int, point: N) -> N:
    x0, x1, y0, y1 = knots.x[i], knots.x[i + 1], knots.y[i], knots.y[i + 1]
    ln, exp = knots.arithmetic.ln, knots.arithmetic.exp
    if knots.scheme == "linear":
        # read_side_contract.md:470 "Linear interpolation within `[x0, x1]` is `y0 + (x - x0) * (y1 - y0) /
        # (x1 - x0)`"
        return y0 + (point - x0) * (y1 - y0) / (x1 - x0)
    # read_side_contract.md:470-471 "Log-log interpolation is `exp(ln y0 + (ln x - ln x0) * (ln y1 - ln y0) /
    # (ln x1 - ln x0))`, in natural logarithms"
    return exp(ln(y0) + (ln(point) - ln(x0)) * (ln(y1) - ln(y0)) / (ln(x1) - ln(x0)))


def _slope(knots: _Knots[N], i: int, point: N, value: N) -> N:
    """The derivative within the interval `[x[i], x[i + 1]]` at `point`, where the value is `value`."""
    slope = _linear_slope if knots.scheme == "linear" else _loglog_slope
    return slope(knots.x[i], knots.x[i + 1], knots.y[i], knots.y[i + 1], point, value, knots.arithmetic)


def _linear_slope(x0: N, x1: N, y0: N, y1: N, point: N, value: N, arithmetic: _Arithmetic[N]) -> N:
    # read_side_contract.md:457-458 "A derivative is the value's derivative with respect to the axis": for
    # item 2's linear formula, its interval's slope (calculus, not quoted).
    return (y1 - y0) / (x1 - x0)


def _loglog_slope(x0: N, x1: N, y0: N, y1: N, point: N, value: N, arithmetic: _Arithmetic[N]) -> N:
    # read_side_contract.md:480 "For a log-log table, the derivative within an interval is `(y / x) * (ln y1 -
    # ln y0) / (ln x1 - ln x0)`"
    ln = arithmetic.ln
    return (value / point) * (ln(y1) - ln(y0)) / (ln(x1) - ln(x0))


def _returned(number: _Real | None) -> Fraction | float | None:
    """A number as the evaluator returns it: a `Fraction` in `exact` mode, a plain float otherwise."""
    if number is None or isinstance(number, Fraction):
        return number
    return float(number)
