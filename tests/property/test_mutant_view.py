# SPDX-License-Identifier: Apache-2.0
"""The code of `test_mutants.py` that is not a fault, held against the core. The hashable view it writes again
for its hash mutants is, without a fault, the core's `hashable_view`, so each of those mutants differs from
the core by its fault alone; and the searches it plans (an edit below a non-object provenance, a pair through
an empty word) draw only examples the core passes, so that a mutant they kill dies of its fault and not of an
example the property would refuse of the core itself. In a module apart from the mutant searches, so that it
runs on every Python (`--property-controls` in `tests/conftest.py`)."""

from hypothesis import given, settings

from materica.core.hashing import content_hash, hashable_view
from materica.core.jsonio import JsonValue
from tests.conftest import EXAMPLES
from tests.property import test_hashing_properties as hashing_properties
from tests.property import test_slip_properties as slip_properties
from tests.property.strategies import SIZE
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


@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(edits_below_a_non_object_provenance(SIZE))
def test_an_edit_below_a_non_object_provenance_changes_the_core_hash(edit: hashing_properties.Edit) -> None:
    hashing_properties.check_edit(content_hash, edit)


@settings(max_examples=min(EXAMPLES[settings.get_current_profile_name()], EXAMPLES["ci"]))
@given(pairs_through_an_empty_word())
def test_a_pair_through_an_empty_word_is_the_cores_to_the_generator(pair: slip_properties.Pair) -> None:
    slip_properties.check_one_slip(pair)
