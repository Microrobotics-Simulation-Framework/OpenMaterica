# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target 3: Atheris drives the Hypothesis properties of records and the read, in-process, through
`fuzz_one_input`: the envelope checks against the reader schema, versions, the read's laws, step 8's, steps 9
and 10's but those drawn in parameters, which `fuzz_one_input` cannot take, and the S2 design's HP1, HP2, HP4,
HP6, HP10, HP11 and HP12 (the S2 design's target 2, which takes each HP once registered).

    python -m tests.fuzz.record_properties [CORPUS] [libFuzzer options]

As in `properties.py`, the first byte picks the property and the rest is the choices it draws; the
properties' strategies build records, stores and requests, so the fuzzer works on their structure, not on
bytes. A failure is saved to the example database and raised; `pytest tests/property`, under the same
profile, then replays it first and shrinks it.
"""

import importlib
import sys
from collections.abc import Callable

import atheris

# Imported first, and inside this block, so that Atheris instruments the core for its coverage.
with atheris.instrument_imports(include=["materica"]):
    importlib.import_module("materica")

from hypothesis.core import HypothesisHandle

# The Hypothesis profiles, from MATERICA_HYPOTHESIS_PROFILE as under pytest: the properties' sizes come from
# the profile, and a failure replays only under the profile it was found with.
importlib.import_module("tests.conftest")

from tests.fuzz import seeded_fault  # noqa: E402
from tests.property import test_condition_properties as condition_properties  # noqa: E402
from tests.property import test_envelope_properties as envelope_properties  # noqa: E402
from tests.property import test_invariance_properties as invariance_properties  # noqa: E402
from tests.property import test_model_properties as model_properties  # noqa: E402
from tests.property import test_read_properties as read_properties  # noqa: E402
from tests.property import test_result_properties as result_properties  # noqa: E402
from tests.property import test_value_field_properties as value_field_properties  # noqa: E402
from tests.property import test_version_properties as version_properties  # noqa: E402

PROPERTIES: list[Callable[..., None]] = [
    envelope_properties.test_the_envelope_checks_agree_with_the_reader_schema,
    version_properties.test_versions_order_as_their_integers,
    version_properties.test_a_text_is_a_version_exactly_when_it_matches,
    read_properties.test_a_read_never_raises_and_gives_each_reason_once,
    read_properties.test_the_order_and_identical_copies_of_the_sources_change_nothing,
    read_properties.test_a_record_of_another_identity_changes_nothing,
    read_properties.test_an_unreadable_source_turns_only_absent_or_pin_mismatch_into_malformed,
    read_properties.test_a_request_member_the_shape_does_not_name_changes_nothing,
    read_properties.test_every_listed_record_resolves_under_its_own_hash,
    value_field_properties.test_one_fault_gives_its_refusal_and_no_other_part_1,
    value_field_properties.test_one_fault_gives_its_refusal_and_no_other_part_2,
    value_field_properties.test_one_fault_gives_its_refusal_and_no_other_part_3,
    value_field_properties.test_a_field_without_a_fault_passes_step_8,
    value_field_properties.test_members_the_reader_does_not_know_change_nothing,
    condition_properties.test_a_stated_plus_minus_turns_met_into_unknown_and_nothing_else,
    condition_properties.test_each_row_of_the_table_and_the_conditions_it_checks,
    condition_properties.test_implied_conditions_fill_never_override_and_end_the_read_where_they_disagree,
    condition_properties.test_an_implied_condition_rests_on_the_section_facts_overridden_by_the_fields,
    condition_properties.test_a_base_read_passes_steps_8_to_10,
    condition_properties.test_the_registered_unit_passes_step_9_however_escapes_write_it,
    condition_properties.test_one_fault_of_step_9_gives_its_refusal_and_no_other,
    condition_properties.test_one_fault_of_step_10_gives_its_reason_beside_the_others,
    condition_properties.test_members_the_reader_does_not_know_change_nothing_steps_9_and_10_read,
    result_properties.test_a_read_gives_a_result_whose_reasons_are_the_tables,
    result_properties.test_the_status_is_the_worst_reason_and_the_members_are_those_item_6_gives,
    result_properties.test_what_a_read_returns_is_as_stored_and_shares_nothing,
    result_properties.test_without_the_hash_suite_the_label_marks_exactly_a_read_that_reached_step_4,
    invariance_properties.test_a_fault_in_another_field_or_section_never_changes_the_read,
    invariance_properties.test_a_fault_in_the_read_fields_section_specimen_refuses_it,
    invariance_properties.test_the_byte_form_of_the_sources_and_the_request_never_changes_the_read,
    model_properties.test_the_read_agrees_with_the_model_on_values_and_alternatives,
    model_properties.test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10,
    model_properties.test_the_read_agrees_with_the_model_on_two_faults_of_one_step,
    model_properties.test_the_read_agrees_with_the_model_on_requests_and_reads_that_end_early,
    model_properties.test_the_read_agrees_with_the_model_where_no_case_pins_a_rule,
]


def handle(test: Callable[..., None]) -> HypothesisHandle:
    found: HypothesisHandle = test.hypothesis  # type: ignore[attr-defined]  # @given adds it; its types do not say.
    return found


HANDLES = [handle(test) for test in PROPERTIES]


def test_one_input(data: bytes) -> None:
    if data:
        HANDLES[data[0] % len(HANDLES)].fuzz_one_input(data[1:])


def main(arguments: list[str]) -> None:
    seeded_fault.seed_if_asked()
    atheris.Setup(arguments, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)
