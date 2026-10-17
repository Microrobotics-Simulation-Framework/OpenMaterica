# SPDX-License-Identifier: Apache-2.0
"""The table evaluator (`core/evaluate.py`) against every table evaluation case, as the S3 design's section
5.4 item 4 asks: each entry's number and `in_range` at 1e-12 relative, and each refusal. OpenMaterica claims
no table evaluation (`read_side_contract.md` section 7): this ties the reader's numbers to the cases. A case's
derivative is not compared, since the reader computes none.

Each thing compared has a control in which a broken evaluator fails it, and the edges of the text are examples
below.
"""

import math
import random
from collections.abc import Callable, Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, Context
from fractions import Fraction

import pytest

from materica.core import evaluate
from tests.conformance.runner import CONFORMANCE
from tests.property.tables import CaseEntry, Tie, case_entries, ties
from tests.property.test_evaluate_mutants import clamped_to_x

TOLERANCE = 1e-12
ENTRIES = case_entries()
LOGLOG = evaluate.loglog


def disagreements(entries: Sequence[CaseEntry] = ENTRIES) -> list[str]:
    """Where `core/evaluate.py` and a case entry differ: a refusal, `in_range`, or the number beyond 1e-12
    relative, absolute where the case's number is zero."""
    found: list[str] = []
    for entry in entries:
        x, y, scheme, edges, source_range = entry.table
        number = evaluate.table_value(x, y, scheme, edges, source_range, entry.at)
        where = f"{entry.case} at {entry.at!r}"
        if entry.expected.get("refused") is True:
            if number is not None:
                found.append(f"{where}: {number!r}, not refused")
            continue
        if number is None:
            found.append(f"{where}: refused")
            continue
        if evaluate.in_readable_range(x, source_range, entry.at) is not entry.expected["in_range"]:
            found.append(f"{where}: in_range is not {entry.expected['in_range']}")
        expected = entry.expected["value"]
        assert isinstance(expected, float), where
        if abs(number - expected) > TOLERANCE * (abs(expected) or 1.0):
            found.append(f"{where}: {number!r}, not {expected!r}")
    return found


def test_the_evaluator_gives_every_number_in_range_and_refusal_of_the_table_evaluation_cases() -> None:
    assert disagreements() == []


def test_every_table_evaluation_case_file_is_compared() -> None:
    """So that a case file the reader of the cases skipped could not pass unseen."""
    on_disk = {path.name for path in (CONFORMANCE / "table_evaluation" / "cases").glob("*.json")}
    assert on_disk
    assert {entry.case for entry in ENTRIES} == on_disk
    assert any(entry.expected.get("refused") is True for entry in ENTRIES)
    assert any(entry.expected.get("in_range") is False for entry in ENTRIES)


def _source_range_ignored(x: Sequence[float], source_range: Sequence[float] | None) -> tuple[float, float]:
    return x[0], x[-1]


def _linear_in_log_space(x0: float, x1: float, y0: float, y1: float, at: float) -> float:
    return LOGLOG(x0, x1, y0, y1, at)


# What each broken evaluator replaces, its fault, the replacement, and what the comparison must report.
CONTROLS: list[tuple[str, str, Callable[..., object], str]] = [
    ("readable_range", "source_range_ignored", _source_range_ignored, "in_range is not False"),
    ("on_edge", "edges_ignored", lambda *_: False, "not refused"),
    ("beyond_an_edge", "extrapolated_beyond_an_edge", lambda *_: False, "not refused"),
    ("loglog", "loglog_as_linear", evaluate.linear, "TE-004.loglog_values.json"),
    ("linear", "linear_in_log_space", _linear_in_log_space, "TE-004.linear_values.json"),
    ("table_value", "clamped_to_x", clamped_to_x, "TE-002.source_range_narrow.json at 285.0: 1000.0"),
]


@pytest.mark.parametrize(("name", "fault", "broken", "reported"), CONTROLS, ids=[c[1] for c in CONTROLS])
def test_a_broken_evaluator_disagrees_with_the_cases(
    name: str, fault: str, broken: Callable[..., object], reported: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evaluate, name, broken)
    found = disagreements()
    assert any(reported in problem for problem in found), (fault, found[:5])


# The edges of the text, by example.


def test_a_log_log_interval_between_adjacent_doubles_never_divides_by_zero() -> None:
    """S3Q16: in doubles, `ln x1 - ln x0` is 0 for `x0 = 1e300` and the next double. Exactly, the reader
    gives each knot's `y` and never raises."""
    x0 = 1e300
    x1 = math.nextafter(x0, math.inf)
    x2 = math.nextafter(x1, math.inf)
    assert math.log(x1) - math.log(x0) == 0.0  # the control: doubles divide by zero here
    x, y = [x0, x2], [1.0, 4.0]
    assert evaluate.table_value(x, y, "loglog", [], None, x1) == 2.0
    assert evaluate.table_value(x, y, "loglog", [], None, x0) == 1.0
    assert evaluate.table_value(x, y, "loglog", [], None, x2) == 4.0


def test_a_linear_interval_whose_values_span_every_double_is_exact() -> None:
    """In doubles `y1 - y0` overflows; exactly, the midpoint between the largest doubles of each sign is 0."""
    largest = 1.7976931348623157e308
    assert largest - -largest == math.inf  # the control
    assert evaluate.table_value([0.0, 2.0], [-largest, largest], "linear", [], None, 1.0) == 0.0


def test_negative_zero_at_a_knot_is_returned_as_stored() -> None:
    """S3Q16: "At a knot that is no edge, the stored `y` is returned as stored, `-0` included", whichever
    zero the operating value is (table item 3: "compared by value")."""
    x, y = [-1.0, 0.0, 1.0], [1.0, -0.0, 1.0]
    for at in (0.0, -0.0):
        number = evaluate.table_value(x, y, "linear", [], None, at)
        assert number == 0.0
        assert number is not None
        assert math.copysign(1.0, number) == -1.0


def test_negative_zero_at_an_edge_at_zero_is_refused() -> None:
    """Table item 3: "`-0` lies at an end or an edge at `0`" (PR-018's arm)."""
    x, y, edges = [-1.0, 0.0, -0.0, 1.0], [1.0, 2.0, 3.0, 4.0], [0.0]
    for at in (0.0, -0.0):
        assert evaluate.on_edge(edges, at)
        assert evaluate.table_value(x, y, "linear", edges, None, at) is None
    # Either side, the interval on that side (table item 3, "strictly where an edge is concerned").
    assert evaluate.table_value(x, y, "linear", edges, None, -0.5) == 1.5
    assert evaluate.table_value(x, y, "linear", edges, None, 0.5) == 3.5


def test_an_edge_outside_the_readable_range_is_at_an_edge_and_outside() -> None:
    """S3Q8 rule 4, T11 of the cases: at 273, `at_edge` and `outside_range` both stand, and no number."""
    x, y, edges, source_range = (
        [263.0, 273.0, 273.0, 283.0],
        [918.0, 916.0, 1000.0, 999.5],
        [273.0],
        [275.0, 283.0],
    )
    assert evaluate.on_edge(edges, 273.0)
    assert not evaluate.in_readable_range(x, source_range, 273.0)
    assert evaluate.table_value(x, y, "linear", edges, source_range, 273.0) is None
    # Below it, beyond the edge from the range: no number; between it and the range, the end's.
    assert evaluate.beyond_an_edge(x, edges, source_range, 272.0)
    assert evaluate.table_value(x, y, "linear", edges, source_range, 272.0) is None
    assert evaluate.table_value(x, y, "linear", edges, source_range, 274.0) == 999.9


# Log-log values halfway between two doubles, and the rest.


def test_a_log_log_value_halfway_between_two_doubles_is_rounded_to_even() -> None:
    """The value is the exact one rounded once, ties to even (the S3b-1 review's M1), at the ties of
    `tables.ties`: among them `y = 1 / x` among the least subnormals, where the text's 1e-12 against a
    correctly rounded case would demand it. Each value, computed in fractions alone, is checked to be
    halfway, the control that one unit off was possible."""
    wrong: list[tuple[Tie, float | None]] = []
    for tie in ties():
        nearest = float(tie.value)
        other = math.nextafter(nearest, math.inf if tie.value > Fraction(nearest) else -math.inf)
        assert 2 * tie.value == Fraction(nearest) + Fraction(other), tie
        number = evaluate.table_value(tie.x, tie.y, "loglog", (), None, tie.at)
        if number != nearest:
            wrong.append((tie, number))
    assert wrong == []


def test_an_irrational_log_log_value_is_rounded_correctly() -> None:
    """Through x [1, 4], y [1, 2] the value is the square root, irrational at a double that is no square, and
    IEEE 754 rounds `sqrt` correctly; `e = 1 / 2` is rational there, so the exact path decides and the bounds
    settle. Among the points, ratios whose numerator alone is a square (9 / 8, ...)."""
    rng = random.Random(3)
    points = [rng.uniform(1.0, 4.0) for _ in range(300)]
    points += [math.nextafter(2.25, math.inf), math.nextafter(2.25, -math.inf), math.nextafter(1.0, math.inf)]
    points += [9 / 8, 25 / 8, 49 / 32, 81 / 32, 121 / 32]
    for at in points:
        assert evaluate.loglog(1.0, 4.0, 1.0, 2.0, at) == math.sqrt(at), at
    assert evaluate.loglog(1.0, 4.0, 1.0, 2.0, 2.25) == 1.5


def test_the_bounds_hold_the_exact_value() -> None:
    """`loglog_bounds` bounds the value strictly, where it is known exactly: at every tie, rising and falling,
    at the first two precisions and at each from 3 digits to 12, where a unit is large; and at random doubles
    on `y = x^2` and `y = 1 / x`, at the first four, and at one of each at all six. A bound one unit astray,
    which could change a rounding only within 1e-48 of a halfway point, shows here."""
    rng = random.Random(4)
    coarse = tuple(_contexts(digits) for digits in range(3, 13))
    known: list[
        tuple[tuple[float, float], tuple[float, float], float, Fraction, Sequence[tuple[Context, Context]]]
    ]
    known = [(tie.x, tie.y, tie.at, tie.value, evaluate.LOGLOG_CONTEXTS[:2] + coarse) for tie in ties()]
    for count in range(10):
        at = rng.uniform(1.0, 2.0)
        contexts = evaluate.LOGLOG_CONTEXTS if count == 0 else evaluate.LOGLOG_CONTEXTS[:4]
        known.append(((1.0, 2.0), (1.0, 4.0), at, Fraction(at) ** 2, contexts))
        known.append(((1.0, 2.0), (1.0, 0.5), at, 1 / Fraction(at), contexts))
    for x, y, at, exact, precisions in known:
        for down, up in precisions:
            low, high = (Fraction(bound) for bound in evaluate.loglog_bounds(down, up, *x, *y, at))
            assert low < exact < high, (x, y, at, down.prec)
            assert high - low < exact * Fraction(10) ** (20 - down.prec), (x, y, at, down.prec)


def _contexts(digits: int) -> tuple[Context, Context]:
    return Context(prec=digits, rounding=ROUND_FLOOR), Context(prec=digits, rounding=ROUND_CEILING)


def test_bounds_that_do_not_settle_are_refined(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the precisions cut to 3 digits and its doublings, where bounds seldom settle at first, every
    square root still comes out correctly rounded: the code refines. Its control: kept at the first
    precision, many do not."""
    rng = random.Random(5)
    points = [rng.uniform(1.0, 4.0) for _ in range(200)]
    coarse = tuple(_contexts(3 * 2**step) for step in range(6))
    monkeypatch.setattr(evaluate, "LOGLOG_CONTEXTS", coarse)
    assert [evaluate.loglog(1.0, 4.0, 1.0, 2.0, at) for at in points] == [math.sqrt(at) for at in points]
    monkeypatch.setattr(evaluate, "LOGLOG_CONTEXTS", coarse[:1])
    wrong = [at for at in points if evaluate.loglog(1.0, 4.0, 1.0, 2.0, at) != math.sqrt(at)]
    assert len(wrong) >= 100, len(wrong)


def _never_exact(*_: object) -> None:
    return None


def test_without_the_exact_decision_a_tie_is_rounded_either_way_and_nothing_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control that the exact decision is what rounds ties to even: bounds alone straddle a halfway point
    at every precision, so the code returns the double nearest their middle. With the precisions cut to two,
    some ties round the wrong way, and none raises."""
    monkeypatch.setattr(evaluate, "exact_loglog", _never_exact)
    monkeypatch.setattr(evaluate, "LOGLOG_CONTEXTS", evaluate.LOGLOG_CONTEXTS[:2])
    found = ties()
    wrong = [tie for tie in found if evaluate.loglog(*tie.x, *tie.y, tie.at) != float(tie.value)]
    assert len(wrong) >= len(found) // 10, len(wrong)


def test_past_the_last_precision_the_code_returns_rather_than_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """At every precision, up to `LOGLOG_DIGITS[-1]`, a tie's bounds straddle it; the code still returns one
    of the two doubles beside it."""
    monkeypatch.setattr(evaluate, "exact_loglog", _never_exact)
    tie = ties()[0]
    nearest = float(tie.value)
    other = math.nextafter(nearest, math.inf if tie.value > Fraction(nearest) else -math.inf)
    assert evaluate.loglog(*tie.x, *tie.y, tie.at) in {nearest, other}
