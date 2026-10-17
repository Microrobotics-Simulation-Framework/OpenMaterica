# SPDX-License-Identifier: Apache-2.0
"""The reference evaluator on small tables worked by hand from `read_side_contract.md` section 7, each check
beside a control the evaluator must answer otherwise; its refusal of a broken table; its citations, found in
the text; and its imports, the standard library's only.

The tables, and their numbers by the text's formulas (my arithmetic):
- `LINEAR`, x [0, 1, 3], y [0, 2, 3]: slope 2 on [0, 1] and 0.5 on [1, 3]; at 0.5, 1; at 2.5, 2.75.
- `LOGLOG`, x [1, 4, 16], y [1, 2, 8]: y = x^(1/2) on [1, 4] and x / 2 on [4, 16]; at 2, sqrt(2), with the
  derivative sqrt(2) / 4; at the knot 4, 0.25 from the left and 0.5 from the right. Read as linear: 4 / 3 at
  2.
- `EDGED`, x [0, 1, 1, 2], y [0, 1, 5, 6], an edge at 1: slope 1 on each side, 1 below the edge and 5 above.

Every number those tables and points hold is exact in binary32, so each precision gives the linear answers
exactly.
"""

import io
import itertools
import math
import re
import sys
import tokenize
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from tests.reference import table_evaluator
from tests.reference.table_evaluator import (
    Evaluation,
    Precision,
    Side,
    Table,
    evaluate,
    structural_fault,
    to_binary32,
)
from tests.unit.test_source_files import outside_the_standard_library

LINEAR = Table(x=(0.0, 1.0, 3.0), y=(0.0, 2.0, 3.0), scheme="linear")
LOGLOG = Table(x=(1.0, 4.0, 16.0), y=(1.0, 2.0, 8.0), scheme="loglog")
EDGED = Table(x=(0.0, 1.0, 1.0, 2.0), y=(0.0, 1.0, 5.0, 6.0), scheme="linear", edges=(1.0,))

PRECISIONS: tuple[Precision, ...] = ("exact", "binary64", "binary32")
SIDES: tuple[Side, ...] = ("left", "right")
# The relative error allowed a log-log number: four binary32 roundings, one binary64 rounding, or exact mode's
# 60 digits rounded once.
LOGLOG_TOLERANCE = {"binary32": 4 * 2.0**-24, "binary64": 2.0**-52, "exact": 2.0**-53}

REPOSITORY = Path(__file__).resolve().parents[2]
SPECIFICATION = REPOSITORY / "docs" / "specification"
SOURCE = Path(table_evaluator.__file__)


def close(number: Fraction | float | None, expected: float, precision: Precision) -> bool:
    return number is not None and abs(float(number) - expected) <= LOGLOG_TOLERANCE[precision] * abs(expected)


def refused(found: Evaluation) -> bool:
    """Whether `found` is a refusal as read_side_contract.md section 7 item 7 has it: reported, with no value
    and no derivative. `in_range` beside it is not compared: the refusal comes first."""
    return found.refused is True and found.value is None and found.derivative is None


@pytest.mark.parametrize("precision", PRECISIONS)
def test_each_scheme_follows_its_formula(precision: Precision) -> None:
    linear = evaluate(LINEAR, 0.5, precision)
    assert (linear.in_range, linear.value, linear.derivative) == (True, 1.0, 2.0)
    loglog = evaluate(LOGLOG, 2.0, precision)
    assert loglog.in_range
    assert close(loglog.value, math.sqrt(2.0), precision)
    assert close(loglog.derivative, math.sqrt(2.0) / 4, precision)
    # Control: the same knots read as linear give the linear formula's value, which differs.
    assert close(evaluate(replace(LOGLOG, scheme="linear"), 2.0, precision).value, 4 / 3, precision)


@pytest.mark.parametrize("precision", PRECISIONS)
def test_at_an_interior_knot_the_derivative_is_the_declared_sides(precision: Precision) -> None:
    assert evaluate(LINEAR, 1.0, precision, "left").derivative == 2.0
    assert evaluate(LINEAR, 1.0, precision, "right").derivative == 0.5
    assert close(evaluate(LOGLOG, 4.0, precision, "left").derivative, 0.25, precision)
    assert close(evaluate(LOGLOG, 4.0, precision, "right").derivative, 0.5, precision)
    # The value at a knot is its own `y`, from either side.
    assert {evaluate(LOGLOG, 4.0, precision, side).value for side in SIDES} == {2.0}
    # Control: between knots the declared side changes nothing.
    assert {evaluate(LINEAR, 2.0, precision, side).derivative for side in SIDES} == {0.5}


@pytest.mark.parametrize("precision", PRECISIONS)
@pytest.mark.parametrize("side", SIDES)
def test_the_range_holds_its_ends_and_outside_it_gives_the_end_value(
    precision: Precision, side: Side
) -> None:
    for end, value, inside in ((0.0, 0.0, 2.0), (3.0, 3.0, 0.5)):
        found = evaluate(LINEAR, end, precision, side)
        # At an end of `x`, the derivative from inside, whatever the side.
        assert (found.in_range, found.value, found.derivative) == (True, value, inside)
    for outside, end_value in ((-1e-30, 0.0), (3.0 + 2.0**-21, 3.0), (-1e6, 0.0), (1e6, 3.0)):
        found = evaluate(LINEAR, outside, precision, side)
        assert (found.refused, found.in_range, found.value, found.derivative) == (
            False,
            False,
            end_value,
            0.0,
        )


@pytest.mark.parametrize("precision", PRECISIONS)
@pytest.mark.parametrize("side", SIDES)
def test_a_narrower_source_range_narrows_the_range_and_a_wider_one_widens_nothing(
    precision: Precision, side: Side
) -> None:
    narrowed = replace(LINEAR, source_range=(0.5, 2.5))
    below, low, high = (evaluate(narrowed, at, precision, side) for at in (0.25, 0.5, 2.5))
    assert (below.in_range, below.value, below.derivative) == (False, 1.0, 0.0)
    assert (low.in_range, low.value, low.derivative) == (True, 1.0, 2.0)
    assert (high.in_range, high.value, high.derivative) == (True, 2.75, 0.5)
    # Control: without `source_range`, 0.25 is inside.
    assert evaluate(LINEAR, 0.25, precision, side).in_range
    wide = replace(LINEAR, source_range=(-1.0, 4.0))
    assert [evaluate(wide, at, precision, side).in_range for at in (-0.5, 0.0, 3.0, 3.5)] == [
        False,
        True,
        True,
        False,
    ]


@pytest.mark.parametrize("precision", PRECISIONS)
@pytest.mark.parametrize("side", SIDES)
def test_at_a_range_end_on_an_interior_knot_the_derivative_is_from_inside(
    precision: Precision, side: Side
) -> None:
    assert evaluate(replace(LINEAR, source_range=(1.0, 3.0)), 1.0, precision, side).derivative == 0.5
    assert evaluate(replace(LINEAR, source_range=(0.0, 1.0)), 1.0, precision, side).derivative == 2.0
    # Control: with the knot inside the range, the declared side.
    assert evaluate(LINEAR, 1.0, precision, side).derivative == (2.0 if side == "left" else 0.5)


@pytest.mark.parametrize("precision", PRECISIONS)
def test_a_one_point_range_has_a_value_and_no_derivative(precision: Precision) -> None:
    one_point = replace(LINEAR, source_range=(3.0, 5.0))
    at = evaluate(one_point, 3.0, precision)
    assert (at.in_range, at.value, at.derivative) == (True, 3.0, None)
    below = evaluate(one_point, 2.0, precision)
    assert (below.in_range, below.value, below.derivative) == (False, 3.0, 0.0)
    # Control: a range of two points has a derivative at the same end.
    assert evaluate(replace(LINEAR, source_range=(2.0, 3.0)), 3.0, precision).derivative == 0.5


@pytest.mark.parametrize("precision", PRECISIONS)
@pytest.mark.parametrize("side", SIDES)
def test_at_an_edge_it_refuses_and_beside_it_reads_each_side(precision: Precision, side: Side) -> None:
    assert refused(evaluate(EDGED, 1.0, precision, side))
    at_zero = Table(x=(-1.0, 0.0, 0.0, 1.0), y=(0.0, 1.0, 5.0, 6.0), scheme="linear", edges=(0.0,))
    assert refused(evaluate(at_zero, -0.0, precision, side))
    # Control: a point beside the edge reads, from its own side.
    below = evaluate(EDGED, 1.0 - 2.0**-20, precision, side)
    above = evaluate(EDGED, 1.0 + 2.0**-20, precision, side)
    assert (below.refused, below.value, below.derivative) == (False, 1.0 - 2.0**-20, 1.0)
    assert (above.refused, above.value, above.derivative) == (False, 5.0 + 2.0**-20, 1.0)


@pytest.mark.parametrize("precision", PRECISIONS)
def test_an_edge_outside_the_range_refuses_at_it_and_across_it(precision: Precision) -> None:
    beyond = replace(EDGED, source_range=(1.5, 2.0))
    assert refused(evaluate(beyond, 1.0, precision))
    assert refused(evaluate(beyond, 0.5, precision))
    between = evaluate(beyond, 1.25, precision)
    assert (between.in_range, between.value, between.derivative) == (False, 5.5, 0.0)
    on_the_end = replace(EDGED, source_range=(1.0, 2.0))
    assert refused(evaluate(on_the_end, 0.5, precision))
    assert evaluate(on_the_end, 1.5, precision).value == 5.5
    # Control: with no edge between it and the range, a point outside is no refusal.
    assert evaluate(replace(LINEAR, source_range=(1.5, 3.0)), 0.5, precision).refused is False


# x [0, 1, 2], y [0, -0, 3]: `-0` at the interior knot, `0` at the first.
SIGNED_ZEROS = Table(x=(0.0, 1.0, 2.0), y=(0.0, -0.0, 3.0), scheme="linear")


def sign(number: Fraction | float | None) -> float:
    return math.copysign(1.0, as_double(number))


@pytest.mark.parametrize("precision", PRECISIONS)
@pytest.mark.parametrize("side", SIDES)
def test_a_knot_s_minus_zero_is_returned_as_negative_zero(precision: Precision, side: Side) -> None:
    at_the_knot = evaluate(SIGNED_ZEROS, 1.0, precision, side)
    assert at_the_knot.value == 0
    assert sign(at_the_knot.value) == -1.0
    # Outside a readable range that ends on that knot, the end value is the knot's.
    outside = evaluate(replace(SIGNED_ZEROS, source_range=(0.0, 1.0)), 1.5, precision, side)
    assert (outside.in_range, outside.value) == (False, 0)
    assert sign(outside.value) == -1.0
    # Controls: a knot's `0` stays positive, and between the knots, where no knot is read, the formula's 0 is
    # positive in every precision (`0 + 0.5 * (-0 - 0) / 1` in doubles).
    assert sign(evaluate(SIGNED_ZEROS, 0.0, precision, side).value) == 1.0
    between = evaluate(SIGNED_ZEROS, 0.5, precision, side).value
    assert between == 0
    assert sign(between) == 1.0


def test_binary32_rounds_the_case_s_numbers_first() -> None:
    beside_the_knot = math.nextafter(1.0, 2.0)
    # In binary32 the point is the knot 1, so the declared side decides.
    assert evaluate(LINEAR, beside_the_knot, "binary32", "left").derivative == 2.0
    # Control: in binary64 it lies above the knot, in the interval [1, 3].
    assert evaluate(LINEAR, beside_the_knot, "binary64", "left").derivative == 0.5


def test_each_precision_rounds_each_operation_its_own_way() -> None:
    third = Table(x=(0.0, 3.0), y=(0.0, 1.0), scheme="linear")
    assert evaluate(third, 1.0, "exact").value == Fraction(1, 3)
    assert evaluate(third, 1.0, "binary64").value == 1 / 3
    assert evaluate(third, 1.0, "binary32").value == to_binary32(1 / 3) != 1 / 3


def rounded_ln(value: float) -> float:
    return to_binary32(math.log(value))


def rounded_exp(value: float) -> float:
    return to_binary32(math.exp(value))


Function = Callable[[float], float]


def binary32_loglog(
    x0: float, x1: float, y0: float, y1: float, at: float, ln: Function, exp: Function
) -> float:
    """The log-log value at `at` by the text's formula, worked step by step in its order, each `+`, `-`, `*`
    and `/` rounded to binary32, with the logarithm `ln` and the exponential `exp`."""
    rounded = to_binary32
    slope = rounded(rounded(rounded(ln(at) - ln(x0)) * rounded(ln(y1) - ln(y0))) / rounded(ln(x1) - ln(x0)))
    return exp(rounded(ln(y0) + slope))


def test_binary32_rounds_each_logarithm_and_exponential() -> None:
    # A point where each rounding shows, in a table whose numbers are exact in binary32.
    x0, x1, y0, y1, at = 2.0, 10.0, 3.0, 11.0, 3.0
    found = evaluate(Table(x=(x0, x1), y=(y0, y1), scheme="loglog"), at, "binary32")
    value = binary32_loglog(x0, x1, y0, y1, at, rounded_ln, rounded_exp)
    ln = rounded_ln
    derivative = to_binary32(
        to_binary32(to_binary32(value / at) * to_binary32(ln(y1) - ln(y0))) / to_binary32(ln(x1) - ln(x0))
    )
    assert (found.value, found.derivative) == (value, derivative)
    # Controls: with the logarithms unrounded, or the exponential, the value differs.
    assert binary32_loglog(x0, x1, y0, y1, at, math.log, rounded_exp) != value
    assert binary32_loglog(x0, x1, y0, y1, at, rounded_ln, math.exp) != value


# y = x^2 and y = x^3 as log-log tables, and the points where their value, or their derivative, lies halfway
# between two doubles: at n / 2^36, n odd and n^2 above 2^53, x^2 is n^2 / 2^72 with 54 bits; at n / 2^26, n
# odd just above 2^26, 3 x^2 is 3 n^2 / 2^52 with 54 bits.
SQUARE = Table(x=(2.0**-10, 2.0**-9), y=(2.0**-20, 2.0**-18), scheme="loglog")
CUBE = Table(x=(1.0, 2.0), y=(1.0, 8.0), scheme="loglog")
SQUARE_TIES = range((math.isqrt(2**53) + 1) | 1, (math.isqrt(2**53) + 1) + 400, 2)
CUBE_TIES = range(2**26 + 1, 2**26 + 401, 2)


def halfway_between_two_doubles(number: Fraction) -> bool:
    """Whether `number`, in the normal range, has 54 significant bits, the last one set."""
    numerator, denominator = number.numerator, number.denominator
    return denominator & (denominator - 1) == 0 and numerator % 2 == 1 and numerator.bit_length() == 54


def test_exact_mode_is_exact_where_the_value_or_derivative_is_halfway_between_two_doubles() -> None:
    for n in SQUARE_TIES:
        value = Fraction(n * n, 2**72)
        assert halfway_between_two_doubles(value)
        found = evaluate(SQUARE, n / 2**36, "exact")
        assert (found.value, found.derivative) == (value, Fraction(2 * n, 2**36))
    for n in CUBE_TIES:
        derivative = Fraction(3 * n * n, 2**52)
        assert halfway_between_two_doubles(derivative)
        found = evaluate(CUBE, n / 2**26, "exact")
        assert (found.value, found.derivative) == (Fraction(n**3, 2**78), derivative)
    # Where the point is a rational power of the knots' ratio, not the values: 2 on [1, 4] is 4^(1/2).
    assert evaluate(Table(x=(1.0, 4.0), y=(3.0, 27.0), scheme="loglog"), 2.0, "exact").value == 9


def test_without_its_exact_forms_exact_mode_rounds_some_of_those_points_wrongly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Control: worked to any number of digits, the formula lands on either side of such a point, so that
    # Ziv's strategy either gives up or settles on a side, the wrong one about half the time.
    def irrational(r: Fraction, s: Fraction) -> None:
        return None

    monkeypatch.setattr(table_evaluator, "_log_ratio", irrational)
    monkeypatch.setattr(table_evaluator, "EXACT_DIGITS_CAP", 480)  # giving up sooner, to save time

    def rounded(n: int) -> float | None:
        try:
            return as_double(evaluate(SQUARE, n / 2**36, "exact").value)
        except ArithmeticError:
            return None

    assert [n for n in SQUARE_TIES[:40] if rounded(n) != n * n / 2**72]


def test_exact_mode_rounds_an_irrational_value_correctly() -> None:
    # y = x^(1/2) on [1, 4]: at a double that is no square the value is irrational, and the platform's square
    # root is correctly rounded (IEEE 754).
    root = Table(x=(1.0, 4.0), y=(1.0, 2.0), scheme="loglog")
    for at in (1 + k / 997 for k in range(1, 2991, 13)):
        assert as_double(evaluate(root, at, "exact").value) == math.sqrt(at)


def as_double(number: Fraction | float | None) -> float:
    assert number is not None
    return float(number)


def test_ziv_s_strategy_gives_up_rather_than_guess() -> None:
    halfway = Fraction(2**53 + 1, 2**53)  # between 1 and the next double
    calls = itertools.count()

    def straddling(arithmetic: object) -> Fraction:
        return halfway + Fraction((-1) ** next(calls), 10**80)

    with pytest.raises(ArithmeticError):
        table_evaluator._ziv(straddling, table_evaluator._EXACT)  # pyright: ignore[reportPrivateUsage]

    # Control: answers that settle on one side are taken.
    def settling(arithmetic: object) -> Fraction:
        return halfway + Fraction(1, 10 ** (20 + next(calls)))

    settled = table_evaluator._ziv(settling, table_evaluator._EXACT)  # pyright: ignore[reportPrivateUsage]
    assert float(settled) == 1 + 2.0**-52


# x [5e-324, 1], y [1, 3], log-log: the derivative at 5e-324 is 2^1074 ln 3 / ln 2^1074, about 3e320, and at
# 1e-323 about half that, both beyond the largest double; at 0.5 it is about 0.0088.
STEEP = Table(x=(5e-324, 1.0), y=(1.0, 3.0), scheme="loglog")
LARGEST = Fraction(sys.float_info.max)


def steep_derivative(at: float) -> Fraction:
    """`STEEP`'s derivative at `at` by read_side_contract.md section 7 items 2 and 5, in `decimal` at 100
    digits, the text's order, without the evaluator."""
    with localcontext(prec=100):
        x0, x1, y0, y1, x = (Decimal(number) for number in (*STEEP.x, *STEEP.y, at))
        exponent = (y1.ln() - y0.ln()) / (x1.ln() - x0.ln())
        return Fraction((y0.ln() + (x.ln() - x0.ln()) * exponent).exp() / x * exponent)


def test_exact_mode_returns_a_derivative_beyond_the_largest_double() -> None:
    for at in (5e-324, 1e-323):
        derivative = evaluate(STEEP, at, "exact").derivative
        assert isinstance(derivative, Fraction)
        assert derivative > LARGEST
        assert abs(derivative / steep_derivative(at) - 1) < Fraction(1, 10**50)
        # Rounded once it is an infinity, which the text's formulas in doubles give too.
        assert evaluate(STEEP, at, "binary64").derivative == math.inf
    # Control: where the derivative is below the largest double, exact mode gives it, rounding to its double.
    below = evaluate(STEEP, 0.5, "exact").derivative
    assert below is not None
    assert below < LARGEST
    assert float(below) == float(steep_derivative(0.5)) == pytest.approx(0.0088, rel=0.01)


@pytest.mark.parametrize(
    ("number", "rounded"),
    [
        # At a magnitude of 2^1024 - 2^970 and above, a number rounds to an infinity (record_format.md section
        # 1 item 6, as `_double` cites it).
        pytest.param(Fraction(2**1024 - 2**970), math.inf, id="halfway_to_infinity"),
        pytest.param(Fraction(-(2**1024) + 2**970), -math.inf, id="negative_halfway_to_infinity"),
        pytest.param(Fraction(10**400), math.inf, id="far_beyond"),
        pytest.param(Fraction(-(10**400)), -math.inf, id="negative_far_beyond"),
        # Controls: just below the halfway point, the largest double; and an ordinary number.
        pytest.param(Fraction(2**1024 - 2**970 - 1), sys.float_info.max, id="below_halfway"),
        pytest.param(Fraction(-(2**1024) + 2**970 + 1), -sys.float_info.max, id="negative_below_halfway"),
        pytest.param(Fraction(1, 3), 1 / 3, id="a_third"),
    ],
)
def test_exact_mode_rounds_a_number_beyond_the_largest_double_to_an_infinity(
    number: Fraction, rounded: float
) -> None:
    assert table_evaluator._double(number) == rounded  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("value", "rounded"),
    [
        pytest.param(1.0, 1.0, id="exact"),
        pytest.param(1 / 3, 0.3333333432674408, id="nearest"),
        pytest.param(1 + 2.0**-24, 1.0, id="tie_to_even_down"),
        pytest.param(1 + 3 * 2.0**-24, 1 + 2.0**-22, id="tie_to_even_up"),
        pytest.param(-0.0, -0.0, id="minus_zero"),
        pytest.param(2.0**-149, 2.0**-149, id="smallest_subnormal"),
        pytest.param(3.4028234663852886e38, 3.4028234663852886e38, id="largest"),
        pytest.param(1e39, math.inf, id="overflow"),
        pytest.param(-1e39, -math.inf, id="negative_overflow"),
    ],
)
def test_to_binary32_rounds_to_nearest_even(value: float, rounded: float) -> None:
    found = to_binary32(value)
    assert found == rounded
    assert math.copysign(1.0, found) == math.copysign(1.0, rounded)


NO_EDGE_SHARED = "source_range shares no value that is no edge with [x[0], x[-1]]"


@pytest.mark.parametrize(
    ("broken", "fault"),
    [
        pytest.param(
            lambda: replace(LINEAR, x=(1.0,), y=(0.0,)), "x holds fewer than two distinct values", id="one_x"
        ),
        pytest.param(
            lambda: replace(LINEAR, x=(1.0, 1.0), y=(0.0, 2.0)),
            "x holds fewer than two distinct values",
            id="one_distinct_x",
        ),
        pytest.param(lambda: replace(LINEAR, x=(0.0, 3.0, 1.0)), "x decreases", id="x_decreasing"),
        pytest.param(
            lambda: replace(LINEAR, y=(0.0, 2.0)),
            "y does not hold one number for each entry of x",
            id="y_short",
        ),
        pytest.param(lambda: replace(EDGED, edges=(1.0, 1.0)), "an edge is listed twice", id="edge_twice"),
        pytest.param(
            lambda: replace(EDGED, x=(0.0, 0.0, 1.0, 2.0), edges=(0.0,)),
            "an edge does not lie strictly between x[0] and x[-1]",
            id="edge_at_an_end",
        ),
        pytest.param(
            lambda: replace(LINEAR, edges=(1.0,)), "an edge is not in x exactly twice", id="edge_not_repeated"
        ),
        pytest.param(
            lambda: replace(LINEAR, x=(0.0, 1.0, 1.0)),
            "an x value that is no edge repeats",
            id="repeat_that_is_no_edge",
        ),
        pytest.param(
            lambda: replace(LINEAR, scheme="loglog"),
            "a log-log table holds a number that is not positive",
            id="loglog_holding_zero",
        ),
        pytest.param(
            lambda: replace(LINEAR, source_range=(2.0, 1.0)),
            "source_range is out of order",
            id="source_range_reversed",
        ),
        pytest.param(
            lambda: replace(LINEAR, source_range=(4.0, 5.0)), NO_EDGE_SHARED, id="source_range_disjoint"
        ),
        pytest.param(
            lambda: replace(EDGED, source_range=(1.0, 1.0)), NO_EDGE_SHARED, id="source_range_only_an_edge"
        ),
    ],
)
def test_a_table_the_record_format_refuses_is_refused_for_its_own_fault(
    broken: Callable[[], Table], fault: str
) -> None:
    # Each fault by its own check: a table that breaks two rules is refused by the first, so the reason is
    # compared, not only the refusal.
    with pytest.raises(ValueError, match=f"section 6 allows: {re.escape(fault)}$"):
        broken()


def test_a_source_range_of_one_point_that_is_no_edge_is_a_table() -> None:
    assert structural_fault(replace(LINEAR, source_range=(3.0, 5.0))) is None
    assert structural_fault(replace(EDGED, source_range=(1.5, 1.5))) is None
    assert structural_fault(replace(EDGED, source_range=(-1.0, 0.0))) is None
    assert structural_fault(LINEAR) is None
    assert structural_fault(EDGED) is None


# A citation, as the reference model's convention writes it: `file:line` or `file:start-end`, and one or more
# quotes, joined by "and", "or", a comma, a semicolon or "...".
CITATION = re.compile(
    r'(?P<file>[A-Za-z_]+\.md):(?P<start>\d+)(?:-(?P<end>\d+))?\s+(?P<quotes>"[^"]+"'
    r'(?:\s*(?:and|or|,|;|\.\.\.)\s*"[^"]+")*)'
)
QUOTE = re.compile(r'"([^"]+)"')


def comments(source: str) -> list[str]:
    """Each run of consecutive comment lines in `source`, joined, white space collapsed."""
    runs: list[list[str]] = []
    last = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            if not runs or token.start[0] != last + 1:
                runs.append([])
            runs[-1].append(token.string.lstrip("#").strip())
            last = token.start[0]
    return [" ".join(" ".join(run).split()) for run in runs]


def citation_problems(texts: list[str]) -> list[str]:
    """Each quote not found at the lines it cites, or on the line after them."""
    problems: list[str] = []
    for text in texts:
        for citation in CITATION.finditer(text):
            path = SPECIFICATION / citation["file"]
            if not path.is_file():
                problems.append(f"{citation[0]}: no such file in the specification")
                continue
            start = int(citation["start"])
            end = int(citation["end"] or start)
            lines = path.read_text(encoding="utf-8").splitlines()
            window = " ".join(" ".join(lines[start - 1 : end + 1]).split())
            problems.extend(
                f"{citation['file']}:{start}: {quote!r} is not there"
                for quote in QUOTE.findall(citation["quotes"])
                if quote not in window
            )
    return problems


def test_each_citation_is_found_at_its_lines() -> None:
    texts = comments(SOURCE.read_text(encoding="utf-8"))
    assert sum(len(CITATION.findall(text)) for text in texts) >= 20
    assert citation_problems(texts) == []


@pytest.mark.parametrize(
    "drifted",
    [
        pytest.param('read_side_contract.md:1 "Linear interpolation within"', id="wrong_line"),
        pytest.param('read_side_contract.md:470 "Linear interpolation outside"', id="wrong_quote"),
        pytest.param('read_contract.md:467 "Linear interpolation within"', id="wrong_file"),
    ],
)
def test_the_citation_check_can_fail(drifted: str) -> None:
    assert citation_problems([drifted])
    assert citation_problems(['read_side_contract.md:470 "Linear interpolation within"']) == []


def test_it_imports_only_the_standard_library() -> None:
    assert outside_the_standard_library(SOURCE.read_text(encoding="utf-8"), "tests.reference") == []
