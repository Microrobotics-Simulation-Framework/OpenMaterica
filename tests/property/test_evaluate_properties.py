# SPDX-License-Identifier: Apache-2.0
"""(15) The table evaluator (`core/evaluate.py`), the S3 design's HP17 to HP19, against an oracle written from
the text alone (`record_format.md` section 6, table items 1 to 4; `read_side_contract.md` sections 5 and 7):

- HP17, agreement: over drawn tables (both schemes; edges; `source_range` absent, narrower, wider, across an
  end, of one point; every magnitude; subnormals; `-0`) and operating values at every place table item 3
  tells apart, the evaluator never raises; "at an edge", "in the readable range" and "no number" fall exactly
  where the oracle puts them; and the number is the oracle's, rounded once: a linear one bit for bit, a
  log-log one within 1e-15.
- HP18, knot exactness: a read at a knot that is no edge, or outside the readable range at an end that is
  one, gives the stored `y`, bit for bit, `-0` included.
- HP19, bracketing and monotonicity: the knots that bracket a read are the interval table item 3 names, and
  the value lies between their two `y`; over knots whose `y` are monotone, with no edge, reads are monotone in
  the operating value.

The oracle compares numbers as fractions, finds a read's interval by scanning every pair of knots, and
computes a linear value exactly in another arrangement, `(y0 (x1 - x) + y1 (x - x0)) / (x1 - x0)`, and a
log-log one in decimal at 80 digits as `y0 * (y1 / y0) ** (ln(x / x0) / ln(x1 / x0))`, where the evaluator
works at 50 in the text's arrangement. It shares with the evaluator only the standard library's rounding of a
fraction to a double. Its own control: it gives every number and refusal of the table evaluation cases.

The mutants it kills are in `test_evaluate_mutants.py`, each at the assertion it names: every assertion's
message begins with its label.
"""

import itertools
from decimal import Context, Decimal, localcontext
from fractions import Fraction
from functools import lru_cache
from typing import NamedTuple

import pytest
from hypothesis import given

from materica.core import evaluate
from tests.property.support import feature, same
from tests.property.tables import SMALLEST_NORMAL, Reading, Table, beside, case_entries, readings

# How far a log-log number may lie from the oracle's: both are rounded once, from 50 digits and from 80, so
# they differ only where a double rounding falls between them (the S3 design's HP17).
LOGLOG_AGREEMENT = 1e-15
_ORACLE = Context(prec=80)


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
def _loglog(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    with localcontext(_ORACLE):
        share = (Decimal(at) / Decimal(x0)).ln() / (Decimal(x1) / Decimal(x0)).ln()
        return float(Decimal(y0) * ((Decimal(y1) / Decimal(y0)).ln() * share).exp())


def exact(table: Table, at: float) -> float:
    """The table's value at `at`, a double of `[x[0], x[-1]]` on no edge: at a knot, its `y` as stored (the
    S3 design, S3Q16); else the formula of its scheme (`read_side_contract.md` section 7 item 2), rounded
    once."""
    below, above = bracket(table, at)
    if below == above:
        return table.y[below]
    x0, x1, y0, y1 = table.x[below], table.x[above], table.y[below], table.y[above]
    if table.scheme == "loglog":
        return _loglog(x0, x1, y0, y1, at)
    point = Fraction(at)
    return float(
        (Fraction(y0) * (Fraction(x1) - point) + Fraction(y1) * (point - Fraction(x0)))
        / (Fraction(x1) - Fraction(x0))
    )


def agrees(scheme: str, number: float, oracle: float) -> bool:
    return same(oracle, number) or (
        scheme == "loglog" and abs(number - oracle) <= LOGLOG_AGREEMENT * abs(oracle)
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
            assert agrees(scheme, number, oracle), f"value: {number!r}, not {oracle!r}, at {at!r} on {table}"


def on_a_knot(table: Table, at: float) -> bool:
    return any(Fraction(knot) == Fraction(at) for knot in table.x)


# Every feature by its chance: the least share it showed in eight runs of 2,000 examples (seeds 1 to 4, at
# the small size and the original one, 2026-10-17), rounded down. A choice's chance is near the share it is
# drawn with, but Hypothesis draws the first of a choice more often.
@pytest.mark.chances(
    linear=0.45,
    loglog=0.45,
    ordinary=0.2,
    any_double=0.2,
    adjacent_doubles=0.19,
    subnormal=0.2,
    with_edges=0.42,
    signed_zeros=0.18,
    no_source_range=0.15,
    narrower=0.15,
    wider=0.17,
    across_an_end=0.16,
    one_point=0.15,
    at_an_edge_inside=0.23,
    at_an_edge_outside=0.18,
    beyond_an_edge=0.2,
    end_between_knots=0.19,
    end_on_a_knot=0.9,
    subnormal_y=0.3,
    negative_zero_y=0.09,
)
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
    linear=0.45,
    loglog=0.44,
    negative_zero_at_a_knot=0.16,
    zero_knot=0.36,
    knot_beside_an_edge=0.46,
    end_on_a_knot=0.9,
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
    linear=0.45, loglog=0.47, with_edges=0.42, rising=0.74, falling=0.76, flat=0.2, beside_an_edge=0.42
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
    non_decreasing=0.47, non_increasing=0.47, linear=0.42, loglog=0.48, flat_run=0.27, narrower=0.15
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
        assert agrees(entry.table.scheme, exact(entry.table, found.source), number), (entry.case, entry.at)
    assert len(entries) >= 100
