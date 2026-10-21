# SPDX-License-Identifier: Apache-2.0
"""A table at an operating value of its axis, as a read computes it: its readable range, its edges, the knots
that bracket the value, and the number (`record_format.md` section 6, table items 1 to 4;
`read_side_contract.md` section 5, "The form's range").

Step 11 of a read uses these: `read.range_report` for its reasons and report (an edge, the readable range, an
edge between the operating value and the range's nearest end), and `read.form_range` for the table's number,
at the operating value or, under an extrapolation that covers the read, at the readable range's nearest end.
The table is one step 8 has accepted (table items 1, 2 and 4): `x` non-decreasing, with two distinct values or
more; `y` as long; each edge strictly between `x[0]` and `x[-1]` and in `x` exactly twice, side by side, and
no other value of `x` repeated; a log-log table's numbers positive; a `source_range` two numbers in order
sharing with `[x[0], x[-1]]` a value that is no edge. Its numbers and the operating value are finite doubles
(`record_format.md` section 1 item 6). Outside that contract the functions here may raise or return any
number.

Numbers are compared by value and exactly, as Python compares doubles, so `-0` lies at an end, a knot or an
edge at `0` (table item 3). A value is the exact value of the text's formula rounded once to the nearest
double, ties to even, so it never raises and is the same double on every platform: a linear one computed in
`fractions`; a log-log one computed in `fractions` where it is rational, and elsewhere bounded in `decimal`
until both bounds round to the same double (`loglog`, which states the one assumption this rests on); at a
knot that is no edge, that knot's `y` as stored, `-0` included (the S3 design, S3Q16). No derivative is
computed: a read returns none, and a consumer's evaluator is its own (`read_side_contract.md` section 7).
"""

from bisect import bisect_left
from collections.abc import Collection, Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, Context, Decimal
from fractions import Fraction
from itertools import combinations
from math import gcd
from typing import Literal, TypeAlias

Scheme: TypeAlias = Literal["linear", "loglog"]

# The significant digits at which a log-log value is bounded, in turn, until both bounds round to the same
# double: S3Q16's 50 first, then twice as many each time, up to a cap.
LOGLOG_DIGITS = (50, 100, 200, 400, 800, 1600)
# Each as two contexts: one rounding every step down, for the lower bound, and one rounding it up.
LOGLOG_CONTEXTS = tuple(
    (Context(prec=digits, rounding=ROUND_FLOOR), Context(prec=digits, rounding=ROUND_CEILING))
    for digits in LOGLOG_DIGITS
)
_ZERO, _ONE = Decimal(0), Decimal(1)


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
    logarithms" (`read_side_contract.md` section 7 item 2), its exact value rounded once to the nearest
    double, ties to even.

    With `a = x / x0`, `b = x1 / x0` and `c = y1 / y0`, the value is `y0 a^e` with `e = ln c / ln b`, and
    also `y0^(1 - t) y1^t` with `t = ln a / ln b`. Where `e` is rational, whether the value is rational is
    decided exactly, and a rational value is computed in fractions (`exact_loglog`). No other value is
    halfway between two doubles:
    - where `e` is rational, it is irrational;
    - where `e` is irrational and `t = r / s` rational, a rational value is a double: its `s`-th power is
      `y0^(s - r) y1^r`, so its exponent of each prime lies between `y0`'s and `y1`'s; its odd part is then at
      most the larger of theirs, below 2^53, its exponent of 2 at least -1074, and it lies between `y0` and
      `y1`;
    - where `e` and `t` are both irrational, the value is irrational: rational, `a`, `b`, `a^e` and `b^e`
      would all be rational with `1, e` and `ln a, ln b` each linearly independent over the rationals, against
      the four exponentials conjecture (which Schanuel's implies; neither is proven).

    So any other value is bounded in decimal at each of `LOGLOG_DIGITS` in turn (`loglog_bounds`) until both
    bounds round to the same double, which is then the value's rounding, since rounding to the nearest double
    never decreases; a value no halfway point holds settles in the end. Past the last, the code returns the
    double nearest the middle of the bounds, which may be one unit off: that would take a value within about
    1e-1580 of a halfway point, relatively, and not on it, or a rational one against the conjecture. No such
    value is known.
    """
    exact = exact_loglog(x0, x1, y0, y1, at)
    if exact is not None:
        return float(exact)
    low, high = loglog_bounds(*LOGLOG_CONTEXTS[0], x0, x1, y0, y1, at)
    for down, up in LOGLOG_CONTEXTS[1:]:
        if float(low) == float(high):
            break
        low, high = loglog_bounds(down, up, x0, x1, y0, y1, at)
    return float((Fraction(low) + Fraction(high)) / 2)


def loglog_bounds(
    down: Context, up: Context, x0: float, x1: float, y0: float, y1: float, at: float
) -> tuple[Decimal, Decimal]:
    """A lower and an upper bound on the log-log value, at the contexts' precision. A double converts to a
    decimal exactly; `decimal`'s logarithm and exponential are correctly rounded, so each true value lies
    strictly within a unit of the rounded one; every other step rounds down (`down`) for the lower bound and
    up (`up`) for the upper. The share `(ln x - ln x0) / (ln x1 - ln x0)` lies in (0, 1), since
    `x0 < x < x1`, so its bounds are kept there: nothing divides by zero, however close the logarithms."""

    def ln(number: float) -> tuple[Decimal, Decimal]:
        rounded = down.ln(Decimal(number))
        return down.next_minus(rounded), up.next_plus(rounded)

    ln_x0, ln_x1, ln_y0, ln_y1, ln_at = ln(x0), ln(x1), ln(y0), ln(y1), ln(at)
    rise = down.subtract(ln_at[0], ln_x0[1]), up.subtract(ln_at[1], ln_x0[0])
    run = down.subtract(ln_x1[0], ln_x0[1]), up.subtract(ln_x1[1], ln_x0[0])
    gain = down.subtract(ln_y1[0], ln_y0[1]), up.subtract(ln_y1[1], ln_y0[0])
    share = (
        down.divide(rise[0], run[1]) if rise[0] > 0 else _ZERO,
        min(up.divide(rise[1], run[0]), _ONE) if run[0] > 0 else _ONE,
    )
    # The share times the gain: least at the gain's lower bound and greatest at its upper, the share being
    # positive.
    step = (
        down.multiply(share[1] if gain[0] < 0 else share[0], gain[0]),
        up.multiply(share[1] if gain[1] > 0 else share[0], gain[1]),
    )
    low = down.next_minus(down.exp(down.add(ln_y0[0], step[0])))
    high = up.next_plus(up.exp(up.add(ln_y0[1], step[1])))
    return low, high


def exact_loglog(x0: float, x1: float, y0: float, y1: float, at: float) -> Fraction | None:
    """The log-log value `y0 a^e` (`loglog`), exactly, where `e` and the value are both rational; else None.

    Write `b` and `c` as products of powers of integers above 1 that are pairwise coprime (`coprime_base`).
    Their logarithms are linearly independent over the rationals (a relation among them would make two equal
    products with no factor in common), so `e` is rational exactly where `c`'s exponents are a rational
    multiple of `b`'s. Then, with `e = r / s` in lowest terms, `a^e` is rational exactly where `a` is the
    `s`-th power of a rational: were `a^(r / s)` rational, so would be `a^(1 / s)`, a product of integer
    powers of it and of `a`."""
    b, c = Fraction(x1) / Fraction(x0), Fraction(y1) / Fraction(y0)
    base = coprime_base([b.numerator, b.denominator, c.numerator, c.denominator])
    e = multiple(exponents(c, base), exponents(b, base))
    if e is None:
        return None
    root = rational_root(Fraction(at) / Fraction(x0), e.denominator)
    return None if root is None else Fraction(y0) * root**e.numerator


def coprime_base(numbers: Sequence[int]) -> list[int]:
    """2 and odd integers above 1, pairwise coprime, such that each of `numbers` (positive) is a product of
    their powers: the odd parts, with each two that share a factor `g` replaced by their quotients by `g` and
    `g` itself, until no two do. Each replacement leaves every number a product of the base and shrinks the
    base's product, so it ends."""
    base = {number >> twos(number) for number in numbers} - {1}
    while shared := next(((p, q) for p, q in combinations(sorted(base), 2) if gcd(p, q) > 1), None):
        p, q = shared
        factor = gcd(p, q)
        base = (base - {p, q}) | ({p // factor, q // factor, factor} - {1})
    return [2, *sorted(base)]


def twos(number: int) -> int:
    """The exponent of 2 in `number`, a positive integer."""
    return (number & -number).bit_length() - 1


def exponents(ratio: Fraction, base: Sequence[int]) -> list[int]:
    """The exponent of each of `base` (a `coprime_base`) in `ratio`, a product of their powers."""

    def exponent(number: int, factor: int) -> int:
        if factor == 2:
            return twos(number)
        count = 0
        while number % factor == 0:
            number //= factor
            count += 1
        return count

    return [exponent(ratio.numerator, factor) - exponent(ratio.denominator, factor) for factor in base]


def multiple(numbers: Sequence[int], of: Sequence[int]) -> Fraction | None:
    """The rational `r` with `numbers` equal to `r` times `of`, term by term, where there is one; `of` is not
    all zero."""
    first = next(index for index, number in enumerate(of) if number)
    ratio = Fraction(numbers[first], of[first])
    return ratio if all(n == ratio * o for n, o in zip(numbers, of, strict=True)) else None


def rational_root(ratio: Fraction, degree: int) -> Fraction | None:
    """The rational whose `degree`-th power is `ratio` (positive), where there is one: in lowest terms, both
    its numerator and its denominator are `degree`-th powers."""
    top, bottom = integer_root(ratio.numerator, degree), integer_root(ratio.denominator, degree)
    return None if top is None or bottom is None else Fraction(top, bottom)


def integer_root(number: int, degree: int) -> int | None:
    """The integer whose `degree`-th power is `number` (positive), where there is one: Newton's method in
    integers, from a power of 2 above the root, falls to the root's floor and stops there."""
    root = 1 << -(-number.bit_length() // degree)
    while (lower := ((degree - 1) * root + number // root ** (degree - 1)) // degree) < root:
        root = lower
    return root if root**degree == number else None


def table_value(
    x: Sequence[float],
    y: Sequence[float],
    scheme: Scheme,
    edges: Collection[float],
    source_range: Sequence[float] | None,
    at: float,
) -> float | None:
    """The table's number at `at`: its value inside the readable range, the value at the range's nearest end
    outside it, and None at or beyond an edge.

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
