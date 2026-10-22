# SPDX-License-Identifier: Apache-2.0
"""Can-fail controls of HP13's last assertion (`test_table_form_properties.check_one_fault`), that a fault is
its rule's alone (`table_form_strategies.JUDGED`): a hand-made builder of one fault that gives `form_invalid`,
which breaks a member its rule does not judge as well, `x`, `y` or the edges, so that its read gives
`form_invalid` as the fault's does and HP13's other assertions pass it. On every example of its fault, at both
sizes, it fails HP13 at that assertion, and the same builder without its extra break passes. They hold every
example they draw, not the first that fails, so they are not mutant searches and record no kill; like those,
they draw derandomised and keep nothing in the example database. The mutant searches
(`test_table_form_mutants.py`) show HP13 failing on faults of the reader."""

from collections.abc import Callable
from typing import NamedTuple

import pytest
from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from tests.property import table_form_strategies as strategies
from tests.property.strategies import ORIGINAL, SMALL
from tests.property.table_form_strategies import CATALOGUE, Faulty, Read, Reasons
from tests.property.test_table_form_properties import check_one_fault
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
]


def on_every_example(examples: st.SearchStrategy[Faulty], check: Callable[[Faulty], None]) -> None:
    @RUN
    @given(examples)
    def run(faulty: Faulty) -> None:
        check(faulty)

    run()


def beyond_its_rule(faulty: Faulty) -> None:
    with pytest.raises(AssertionError, match=f"^beyond its rule: the fault {faulty.fault}, "):
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
