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
import math
import re
import tokenize
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from tests.reference import table_evaluator
from tests.reference.table_evaluator import (
    REFUSED,
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
    assert evaluate(EDGED, 1.0, precision, side) == REFUSED
    at_zero = Table(x=(-1.0, 0.0, 0.0, 1.0), y=(0.0, 1.0, 5.0, 6.0), scheme="linear", edges=(0.0,))
    assert evaluate(at_zero, -0.0, precision, side) == REFUSED
    # Control: a point beside the edge reads, from its own side.
    below = evaluate(EDGED, 1.0 - 2.0**-20, precision, side)
    above = evaluate(EDGED, 1.0 + 2.0**-20, precision, side)
    assert (below.refused, below.value, below.derivative) == (False, 1.0 - 2.0**-20, 1.0)
    assert (above.refused, above.value, above.derivative) == (False, 5.0 + 2.0**-20, 1.0)


@pytest.mark.parametrize("precision", PRECISIONS)
def test_an_edge_outside_the_range_refuses_at_it_and_across_it(precision: Precision) -> None:
    beyond = replace(EDGED, source_range=(1.5, 2.0))
    assert evaluate(beyond, 1.0, precision) == REFUSED
    assert evaluate(beyond, 0.5, precision) == REFUSED
    between = evaluate(beyond, 1.25, precision)
    assert (between.in_range, between.value, between.derivative) == (False, 5.5, 0.0)
    on_the_end = replace(EDGED, source_range=(1.0, 2.0))
    assert evaluate(on_the_end, 0.5, precision) == REFUSED
    assert evaluate(on_the_end, 1.5, precision).value == 5.5
    # Control: with no edge between it and the range, a point outside is no refusal.
    assert evaluate(replace(LINEAR, source_range=(1.5, 3.0)), 0.5, precision).refused is False


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


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(lambda: replace(LINEAR, x=(1.0, 1.0), y=(0.0, 2.0)), id="one_distinct_x"),
        pytest.param(lambda: replace(LINEAR, x=(0.0, 3.0, 1.0)), id="x_decreasing"),
        pytest.param(lambda: replace(LINEAR, y=(0.0, 2.0)), id="y_short"),
        pytest.param(lambda: replace(EDGED, edges=(1.0, 1.0)), id="edge_twice"),
        pytest.param(lambda: replace(EDGED, x=(0.0, 0.0, 1.0, 2.0), edges=(0.0,)), id="edge_at_an_end"),
        pytest.param(lambda: replace(LINEAR, edges=(1.0,)), id="edge_not_repeated"),
        pytest.param(lambda: replace(LINEAR, x=(0.0, 1.0, 1.0)), id="repeat_that_is_no_edge"),
        pytest.param(lambda: replace(LINEAR, scheme="loglog"), id="loglog_holding_zero"),
        pytest.param(lambda: replace(LINEAR, source_range=(2.0, 1.0)), id="source_range_reversed"),
        pytest.param(lambda: replace(LINEAR, source_range=(4.0, 5.0)), id="source_range_disjoint"),
        pytest.param(lambda: replace(EDGED, source_range=(1.0, 1.0)), id="source_range_only_an_edge"),
    ],
)
def test_a_table_the_record_format_refuses_is_refused(broken: Callable[[], Table]) -> None:
    with pytest.raises(ValueError, match="section 6 allows"):
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
