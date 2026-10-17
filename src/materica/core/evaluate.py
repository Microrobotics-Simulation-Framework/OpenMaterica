# SPDX-License-Identifier: Apache-2.0
"""A table at an operating value of its axis, as a read computes it: its readable range, its edges, the knots
that bracket the value, and the number (`record_format.md` section 6, table items 1 to 4;
`read_side_contract.md` section 5, "The form's range").

Step 11 of a read is to use these; nothing calls them yet. The table is one step 8 has accepted (table items
1, 2 and 4): `x` non-decreasing, with two distinct values or more; `y` as long; each edge strictly between
`x[0]` and `x[-1]` and in `x` exactly twice, side by side, and no other value of `x` repeated; a log-log
table's numbers positive; a `source_range` two numbers in order sharing with `[x[0], x[-1]]` a value that is
no edge. Its numbers and the operating value are finite doubles (`record_format.md` section 1 item 6).
Outside that contract the functions here may raise or return any number.

Numbers are compared by value and exactly, as Python compares doubles, so `-0` lies at an end, a knot or an
edge at `0` (table item 3). A value is computed exactly and rounded once, so it never raises and is the same
double on every platform: a linear one with `fractions`, a log-log one in `decimal` at 50 significant digits;
at a knot that is no edge it is that knot's `y` as stored, `-0` included (the S3 design, S3Q16). No
derivative is computed: a read returns none, and a consumer's evaluator is its own (`read_side_contract.md`
section 7).
"""

from bisect import bisect_left
from collections.abc import Collection, Sequence
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from typing import Literal, TypeAlias

Scheme: TypeAlias = Literal["linear", "loglog"]

# A log-log value's significant digits before its one rounding to a double (S3Q16).
LOGLOG_DIGITS = 50
_LOGLOG = Context(prec=LOGLOG_DIGITS)


def readable_range(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    """The ends of the readable range, both included: "from `x[0]`, or `source_range[0]` where that is
    greater, to `x[-1]`, or `source_range[1]` where that is smaller" (table item 3). So `source_range` "never
    extends the readable range, and narrows it where it is narrower" (table item 4)."""
    if source_range is None:
        return x[0], x[-1]
    return max(x[0], source_range[0]), min(x[-1], source_range[1])


def in_readable_range(x: Sequence[float], source_range: Sequence[float] | None, at: float) -> bool:
    """Whether `at` lies in the readable range, an end included. An edge is not judged here: "A read exactly
    at an edge is refused (the value is two-sided), wherever the edge lies" (table item 3), as `on_edge`
    tells."""
    low, high = readable_range(x, source_range)
    return low <= at <= high


def on_edge(edges: Collection[float], at: float) -> bool:
    """Whether `at` lies exactly at a declared edge, inside the readable range or outside it (table item
    3)."""
    return any(edge == at for edge in edges)


def beyond_an_edge(
    x: Sequence[float], edges: Collection[float], source_range: Sequence[float] | None, at: float
) -> bool:
    """Whether `at` lies outside the readable range with a declared edge between it and the range's nearest
    end, or on that end: "Beyond an edge that lies outside the readable range or on its end, on the far side
    from the range, no extrapolation applies either, so the table gives no value there" (table item 3),
    "since the end value would come from the far side of the edge" (`read_side_contract.md` section 5)."""
    low, high = readable_range(x, source_range)
    if at < low:
        return any(at < edge <= low for edge in edges)
    if at > high:
        return any(high <= edge < at for edge in edges)
    return False


def interval(x: Sequence[float], at: float) -> tuple[int, int]:
    """The knots that bracket `at`, which lies in `[x[0], x[-1]]` and on no edge: `(i, i)` where `at` is the
    knot `x[i]`, and otherwise `(i, i + 1)` with `x[i] < at < x[i + 1]`, "strictly where an edge is
    concerned, so a read just below an edge uses the knot below it" (table item 3)."""
    above = bisect_left(x, at)
    if x[above] == at:
        return above, above
    return above - 1, above


def value(x: Sequence[float], y: Sequence[float], scheme: Scheme, at: float) -> float:
    """The table's value at `at`, which lies in `[x[0], x[-1]]` and on no edge: at a knot, its `y` as stored;
    otherwise interpolated by `scheme` between the two knots that bracket `at`, "a knot outside
    `source_range` ... used where it brackets a read inside the readable range" (table item 3)."""
    below, above = interval(x, at)
    if below == above:
        return y[below]
    interpolate = linear if scheme == "linear" else loglog
    return interpolate(x[below], x[above], y[below], y[above], at)


def linear(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    """The linear formula, "`y0 + (x - x0) * (y1 - y0) / (x1 - x0)`" (`read_side_contract.md` section 7
    item 2), in fractions, exactly, rounded once to the nearest double."""
    x0_, x1_, y0_ = Fraction(x0), Fraction(x1), Fraction(y0)
    return float(y0_ + (Fraction(at) - x0_) * (Fraction(y1) - y0_) / (x1_ - x0_))


def loglog(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    """The log-log formula, "`exp(ln y0 + (ln x - ln x0) * (ln y1 - ln y0) / (ln x1 - ln x0))`, in natural
    logarithms" (`read_side_contract.md` section 7 item 2), in decimal at `LOGLOG_DIGITS` significant digits,
    rounded once to the nearest double. A double converts to a decimal exactly, and the logarithms of two
    distinct positive doubles differ within those digits, so nothing divides by zero; the result lies between
    `y0` and `y1`, so nothing overflows."""
    with localcontext(_LOGLOG):
        ln_x0, ln_y0 = Decimal(x0).ln(), Decimal(y0).ln()
        slope = (Decimal(y1).ln() - ln_y0) / (Decimal(x1).ln() - ln_x0)
        return float((ln_y0 + (Decimal(at).ln() - ln_x0) * slope).exp())


def table_value(
    x: Sequence[float],
    y: Sequence[float],
    scheme: Scheme,
    edges: Collection[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    """The number a read of the table gives at `at`, or None where it gives none.

    - Inside the readable range, the table's value at `at` (`value`).
    - Outside it, "the value at the range's nearest end, taken from inside the range"
      (`read_side_contract.md` section 5, "The form's range"): the number a declared extrapolation starts
      from, and the one an evaluator may return beside `in_range` false (section 7 item 1). That end is no
      edge, or `at` would lie beyond one, so its value is one-sided.
    - None at a declared edge, wherever it lies, where "the refusal at the edge decides: the table gives no
      value", and beyond one, where "the table gives no value there" (table item 3).
    """
    if on_edge(edges, at) or beyond_an_edge(x, edges, source_range, at):
        return None
    low, high = readable_range(x, source_range)
    if at < low:
        return value(x, y, scheme, low)
    if at > high:
        return value(x, y, scheme, high)
    return value(x, y, scheme, at)
