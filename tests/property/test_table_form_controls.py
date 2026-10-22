# SPDX-License-Identifier: Apache-2.0
"""Can-fail controls of HP13's last assertion (`test_table_form_properties.check_one_fault`), that a fault is
its rule's alone (`table_form_strategies.JUDGED`): a hand-made builder of one fault that gives `form_invalid`,
which breaks a member its rule does not judge as well, `x`, `y`, the edges or the scheme, so that its read
gives `form_invalid` as the fault's does and HP13's other assertions pass it. On every example of its fault,
at both sizes, it fails HP13 at that assertion, and the same builder without its extra break passes. For
every fault, a second control breaks each member its rule does not judge, one at a time, on the faulty read,
and holds that the fault's undo leaves it broken: an undo made broader than its rule, which would mend that
break, fails there, whichever fault it is. They hold every example they draw, not the first that fails, so
they are not mutant searches and record no kill; like those, they draw derandomised and keep nothing in the
example database. The mutant searches (`test_table_form_mutants.py`) show HP13 failing on faults of the
reader."""

import copy
from collections.abc import Callable
from typing import NamedTuple

import pytest
from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from tests.property import table_form_strategies as strategies
from tests.property.strategies import ORIGINAL, SMALL, Size
from tests.property.table_form_strategies import (
    CATALOGUE,
    JUDGED,
    KNOTS,
    PAST_STEP_9,
    Faulty,
    Outcome,
    Read,
    Reasons,
    Undo,
    outcome,
    put_back,
    table_of,
    undone,
)
from tests.property.test_table_form_properties import UNDONE_REFUSED, check_one_fault
from tests.property.value_fields import Json, listing

EXAMPLES = 100
RUN = settings(max_examples=EXAMPLES, derandomize=True, database=None, deadline=None, phases=[Phase.generate])


class WronglyBuilt(NamedTuple):
    name: str
    part: str
    fault: str
    breaks: Callable[[Json], None]  # the faulty table broken further, drawing nothing


def _first_two_knots_swapped(table: Json) -> None:
    x = listing(table["x"])
    x[0], x[1] = x[1], x[0]


def _y_shortened(table: Json) -> None:
    listing(table["y"]).pop()


def _first_knot_listed_as_an_edge(table: Json) -> None:
    listing(table["edges"]).append(listing(table["x"])[0])


def _scheme_not_a_string(table: Json) -> None:
    table["scheme"] = None


WRONGLY_BUILT = [
    WronglyBuilt(
        "x_broken_beside_token_not_a_string", "tokens", "token_not_a_string", _first_two_knots_swapped
    ),
    WronglyBuilt(
        "y_broken_beside_source_range_reversed",
        "source_range_and_points",
        "source_range_reversed",
        _y_shortened,
    ),
    WronglyBuilt("edges_broken_beside_y_longer", "knots", "y_longer", _first_knot_listed_as_an_edge),
    # The faults whose undo is the narrowest that mends them: it must leave the member broken beside them.
    WronglyBuilt("y_shortened_beside_edge_at_an_end", "edges", "edge_at_an_end", _y_shortened),
    WronglyBuilt("y_shortened_beside_repeated_x_no_edge", "knots", "repeated_x_no_edge", _y_shortened),
    WronglyBuilt(
        "scheme_broken_beside_log_log_not_positive", "edges", "log_log_not_positive", _scheme_not_a_string
    ),
]


def on_every_example(examples: st.SearchStrategy[Faulty], check: Callable[[Faulty], None]) -> None:
    @RUN
    @given(examples)
    def run(faulty: Faulty) -> None:
        check(faulty)

    run()


def beyond_its_rule(faulty: Faulty) -> None:
    with pytest.raises(AssertionError, match=f"^{UNDONE_REFUSED}: the fault {faulty.fault}, "):
        check_one_fault(faulty)


@pytest.mark.parametrize("built", WRONGLY_BUILT, ids=[built.name for built in WRONGLY_BUILT])
def test_a_fault_built_to_break_another_member_fails_hp13_at_its_rule_alone(
    built: WronglyBuilt, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its message is the last assertion's, so the fault's, the base's and the neighbour's passed it. Both
    runs draw the same examples, as the break draws nothing."""
    right = CATALOGUE[built.part][built.fault]

    def wrong(draw: st.DrawFn, drawn: Read) -> Reasons | None:
        reasons = right(draw, drawn)
        built.breaks(strategies.table_of(drawn))
        return reasons

    for size in (SMALL, ORIGINAL):
        examples = strategies.faulty_reads(built.part, size, only=(built.fault,))
        on_every_example(examples, check_one_fault)
        with monkeypatch.context() as patched:
            patched.setitem(CATALOGUE[built.part], built.fault, wrong)
            on_every_example(examples, beyond_its_rule)


# What each fault's rule judges, among the table's members: written here, not read from `JUDGED`, so that an
# undo made broader fails against it. The faults that rewrite `x`, `y` and the edges together are judged on
# all three; a near miss has no undo, and no entry.
KNOT_MEMBERS = frozenset({"x", "y", "edges"})
RULE_JUDGES: dict[str, frozenset[str]] = {
    "y_longer": frozenset({"y"}),
    "y_shorter": frozenset({"y"}),
    "x_one_value": KNOT_MEMBERS,
    "x_without_two_distinct_values": KNOT_MEMBERS,
    "x_decreasing": frozenset({"x"}),
    "repeated_x_no_edge": frozenset({"x", "y"}),
    "not_numbers": KNOT_MEMBERS,
    "member_missing": frozenset({"axis", "axis_unit", "x", "y", "scheme", "edges"}),
    "edge_at_an_end": KNOT_MEMBERS,
    "edge_not_in_x": frozenset({"edges"}),
    "edge_not_repeated": frozenset({"edges"}),
    "edge_repeated_thrice": frozenset({"x", "y"}),
    "edge_listed_twice": frozenset({"edges"}),
    "edges_zero_and_minus_zero": frozenset({"edges"}),
    "log_log_not_positive": frozenset({"x", "y"}),
    "scheme_unknown": frozenset({"scheme"}),
    "axis_unknown": frozenset({"axis"}),
    "axis_token_condition": frozenset({"axis"}),
    "token_not_a_string": frozenset({"axis", "scheme"}),
    "axis_condition_held_otherwise": frozenset(),
    "axis_unit_not_a_unit": frozenset({"axis_unit"}),
    "source_range_reversed": frozenset({"source_range"}),
    "source_range_disjoint": frozenset({"source_range"}),
    "source_range_only_at_an_edge": frozenset({"source_range"}),
    "source_range_not_two_numbers": frozenset({"source_range"}),
    "points": frozenset({"points"}),
    "points_null": frozenset({"points"}),
    "x_empty_beside_edges_or_a_source_range": KNOT_MEMBERS,
}


def _x_reversed(table: Json) -> None:
    listing(table["x"]).reverse()


def _a_value_that_is_no_number_before_the_edges(table: Json) -> None:
    """Before them, so that an undo that takes the last edge away leaves it."""
    table["edges"] = ["a", *listing(table["edges"])]


# A break of each member the reader refuses whatever else the table holds, drawing nothing.
BREAKS: dict[str, Callable[[Json], None]] = {
    "x": _x_reversed,
    "y": _y_shortened,
    "edges": _a_value_that_is_no_number_before_the_edges,
    "scheme": _scheme_not_a_string,
    "axis": lambda table: table.update(axis=1.0),
    "axis_unit": lambda table: table.update(axis_unit=1.0),
    "source_range": lambda table: table.update(source_range=[2.0, 1.0]),
    "points": lambda table: table.update(points="x"),
}


def mended_break(faulty: Faulty) -> str | None:
    """The first member its rule does not judge whose break, put on the faulty read, an undo of the fault
    mends: the read undone then passes steps 8 and 9."""
    for member, breaks in BREAKS.items():
        if member in RULE_JUDGES[faulty.fault]:
            continue
        broken = Read(copy.deepcopy(faulty.read.record), faulty.read.field)
        breaks(table_of(broken))
        for undo in JUDGED[faulty.fault]:
            read = undone(faulty._replace(read=broken), undo)
            if outcome(read.record, read.field) == Outcome(PAST_STEP_9):
                return f"{member}: {undo.says}"
    return None


def leaves_alone(faulty: Faulty) -> None:
    mended = mended_break(faulty)
    assert mended is None, f"an undo of {faulty.fault} mends a break of {mended}"


def part_of(fault: str) -> str:
    return next(part for part, faults in CATALOGUE.items() if fault in faults)


def test_every_fault_with_an_undo_has_its_rule_judges_declared() -> None:
    assert set(RULE_JUDGES) == {fault for fault, undos in JUDGED.items() if undos}


@pytest.mark.parametrize("fault", sorted(RULE_JUDGES))
def test_an_undo_leaves_broken_a_member_its_rule_does_not_judge(fault: str) -> None:
    for size in (SMALL, ORIGINAL):
        on_every_example(strategies.faulty_reads(part_of(fault), size, only=(fault,)), leaves_alone)


def broader(undos: tuple[Undo, ...], *members: str) -> tuple[Undo, ...]:
    """Each undo also putting `members` back as the base holds them."""
    extra = put_back(*members)

    def widened(undo: Undo) -> Undo:
        def apply(field: Json, base: Json) -> None:
            undo.apply(field, base)
            extra.apply(field, base)

        return Undo(f"{undo.says}, {extra.says}", apply)

    return tuple(widened(undo) for undo in undos)


def examples_that_mend(fault: str, member: str, size: Size) -> tuple[int, int]:
    """Of the fault's examples, those whose first mended break is of `member`, and all of them."""
    first: list[str | None] = []
    on_every_example(
        strategies.faulty_reads(part_of(fault), size, only=(fault,)),
        lambda faulty: first.append(mended_break(faulty)),
    )
    return sum(found is not None and found.startswith(f"{member}:") for found in first), len(first)


def test_an_undo_made_to_restore_the_knots_fails_that_control_on_every_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`edge_listed_twice`, whose rule judges the edges, undone by putting `x`, `y` and the edges back."""
    monkeypatch.setitem(JUDGED, "edge_listed_twice", (KNOTS,))
    for size in (SMALL, ORIGINAL):
        mended, examples = examples_that_mend("edge_listed_twice", "x", size)
        assert mended == examples > 0, (mended, examples)


@pytest.mark.parametrize("member", [member for member in BREAKS if member != "edges"])
def test_an_undo_made_broader_by_one_member_fails_that_control(
    member: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Putting `x`, `y` or the `source_range` back mends the break only where the base's differs from the
    faulty read's: a base that has no edge leaves the one `an_edge` made, and the table is refused all the
    same."""
    monkeypatch.setitem(JUDGED, "edge_listed_twice", broader(JUDGED["edge_listed_twice"], member))
    for size in (SMALL, ORIGINAL):
        mended, examples = examples_that_mend("edge_listed_twice", member, size)
        assert 0 < mended <= examples, (mended, examples)
