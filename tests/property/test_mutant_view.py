# SPDX-License-Identifier: Apache-2.0
"""The code of `test_mutants.py` that is not a fault, held against the core. The hashable view it writes again
for its hash mutants is, without a fault, the core's `hashable_view`, so each of those mutants differs from
the core by its fault alone; and the searches it plans (an edit below a non-object provenance, a pair through
an empty word) draw only examples the core passes, so that a mutant they kill dies of its fault and not of an
example the property would refuse of the core itself. In a module apart from the mutant searches, so that it
runs on every Python (`--property-controls` in `tests/conftest.py`). The controls of the hash's search run at
both sizes, as the mutant search does, and one shows that the control fails a search it is there to refuse."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from materica.core.hashing import content_hash, hashable_view
from materica.core.jsonio import JsonValue
from tests.conftest import EXAMPLES
from tests.property import test_hashing_properties as hashing_properties
from tests.property import test_slip_properties as slip_properties
from tests.property.strategies import ORIGINAL, SCALARS, SIZE, SMALL, Size
from tests.property.support import examples_to_kill
from tests.property.test_mutants import (
    edits_below_a_non_object_provenance,
    mutant_view,
    pairs_through_an_empty_word,
)


# This checks the mutants' own code, not the core's, so `deep` adds nothing to it: it searches as `ci` does at
# most, which saves `deep` some five minutes.
@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(hashing_properties.records(SIZE))
def test_the_view_without_a_fault_is_the_view(record: JsonValue) -> None:
    assert mutant_view(record) == hashable_view(record)


def trees_holding_a_provenance_object_that_removes() -> st.SearchStrategy[JsonValue]:
    """A tree below `review` or `copy` with a provenance object holding `review` or `copy`, whose leaf the
    hash removes with it: alone (no leaf of the tree is kept) or beside a kept one. A search that edits a leaf
    of the tree without choosing a kept one draws a removed leaf at once, so these are the draws that tell it
    from the planned one; `trees` draws them one example in several thousand."""
    names = st.sampled_from(hashing_properties.REMOVED_IN_PROVENANCE)

    def removed_alone(name: str, value: JsonValue) -> JsonValue:
        return {"provenance": {name: value}}

    def removed_beside_a_kept_leaf(name: str, value: JsonValue, kept: JsonValue) -> JsonValue:
        return {"kept": kept, "provenance": {name: value}}

    return st.one_of(
        st.builds(removed_alone, names, SCALARS),
        st.builds(removed_beside_a_kept_leaf, names, SCALARS, SCALARS),
    )


def check_the_core_on(edits: st.SearchStrategy[hashing_properties.Edit]) -> None:
    @settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
    @given(edits)
    def check(edit: hashing_properties.Edit) -> None:
        hashing_properties.check_edit(content_hash, edit)

    check()


SIZES = [pytest.param(SMALL, id="small"), pytest.param(ORIGINAL, id="original")]


@pytest.mark.parametrize("size", SIZES)
def test_an_edit_below_a_non_object_provenance_changes_the_core_hash(size: Size) -> None:
    check_the_core_on(edits_below_a_non_object_provenance(size))


@pytest.mark.parametrize("size", SIZES)
def test_an_edit_below_a_provenance_object_inside_it_changes_the_core_hash(size: Size) -> None:
    """The planned draws that reach a removed leaf (see `trees_holding_a_provenance_object_that_removes`): the
    core passes them, so the planned search does not edit a leaf the hash removes."""
    check_the_core_on(
        edits_below_a_non_object_provenance(size, inside=trees_holding_a_provenance_object_that_removes())
    )


@pytest.mark.parametrize("size", SIZES)
def test_the_control_refuses_a_search_that_edits_a_removed_leaf(size: Size) -> None:
    """The control above can fail: the search without the kept-leaf filter (`only_kept=False`), drawn as the
    control draws, edits a leaf the hash removes, and the core fails it at the first example (the first
    draw of `one_of` is the tree with no kept leaf), and three random examples in four (so 200 draws miss it
    with a probability below 1e-100)."""
    edits = edits_below_a_non_object_provenance(
        size, inside=trees_holding_a_provenance_object_that_removes(), only_kept=False
    )
    with pytest.raises(AssertionError, match="left the hash unchanged"):
        check_the_core_on(edits)


@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(pairs_through_an_empty_word())
def test_a_pair_through_an_empty_word_is_the_cores_to_the_generator(pair: slip_properties.Pair) -> None:
    slip_properties.check_one_slip(pair)


def test_a_strategy_that_raises_is_not_a_kill() -> None:
    """`examples_to_kill` returned 0, a kill before any example, when the strategy itself asserted (the
    planned hash search asserts that its record is an object): that is a defect of the search, not a kill."""

    @st.composite
    def asserting(draw: st.DrawFn) -> int:
        assert draw(st.integers()) is None, "the strategy refuses"
        return 0

    with pytest.raises(AssertionError, match="the strategy raised AssertionError itself"):
        examples_to_kill(asserting(), lambda example: None)

    def check(example: int) -> None:
        assert example < 5

    assert examples_to_kill(st.integers(), check) > 0  # a check that raises is still a kill
