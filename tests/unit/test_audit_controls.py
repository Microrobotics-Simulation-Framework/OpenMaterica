# SPDX-License-Identifier: Apache-2.0
"""The controls of the feature audits of the json and records shards' properties that declare features by
their chances (`@pytest.mark.chances`), of the conditions shard's, steps 9 and 10's and the result's, which
declare them by their chances or draw them alike (`@pytest.mark.drawn`), and of the relations shard's audit
of the monotonicity relations' worlds, by their chances: run at the `ci` profile's examples with a generator
that stops producing one of them, each property fails its audit, on that feature alone; a parametrised
property, on one of its parameters, by the marks that parameter carries. Outside `tests/property/`, whose
audits would fail these runs too."""

import sys
from collections.abc import Callable
from typing import NamedTuple

import pytest
from hypothesis import HealthCheck, reject, settings

from tests.conftest import EXAMPLES
from tests.property import audits
from tests.property import test_canonical_properties as canonical_properties
from tests.property import test_condition_properties as condition_properties
from tests.property import test_hashing_properties as hashing_properties
from tests.property import test_jsonio_properties as jsonio_properties
from tests.property import test_monotonicity_properties as monotonicity_properties
from tests.property import test_read_properties as read_properties
from tests.property import test_result_properties as result_properties
from tests.property import test_value_field_properties as value_field_properties
from tests.property import test_version_properties as version_properties


class Control(NamedTuple):
    test: Callable[..., None]  # the property, as pytest runs it
    never: str  # the feature its generator stops producing
    # The checks of the property's law it skips: the audit counts the features, which the checks do not
    # change, and skipping them saves most of the run.
    skipped: tuple[str, ...]
    parameters: tuple[tuple[str, object], ...] = ()  # of a parametrised property, the one it runs with


CONTROLS = [
    Control(jsonio_properties.test_written_values_read_back, "three_deep", ("check_reads_back",)),
    Control(canonical_properties.test_output_matches_rfc8785, "negative_zero", ("check_matches_rfc8785",)),
    Control(
        hashing_properties.test_editing_any_leaf_the_hash_covers_changes_it,
        "edited_inside_a_provenance_object",
        ("check_edit",),
    ),
    Control(
        hashing_properties.test_the_hash_ignores_what_it_leaves_out,
        "card_below_the_top",
        ("check_invariance",),
    ),
    Control(version_properties.test_versions_order_as_their_integers, "decided_by_major", ("check_order",)),
    # The read's outcome is a feature, so the first law's check runs; the others' laws read again, skipped.
    Control(read_properties.test_a_read_never_raises_and_gives_each_reason_once, "malformed", ()),
    Control(
        read_properties.test_the_order_and_identical_copies_of_the_sources_change_nothing,
        "malformed",
        ("check_order_and_copies",),
    ),
    Control(
        read_properties.test_a_record_of_another_identity_changes_nothing,
        "malformed",
        ("check_other_identity",),
    ),
    Control(
        read_properties.test_an_unreadable_source_turns_only_absent_or_pin_mismatch_into_malformed,
        "malformed",
        ("check_unreadable",),
    ),
    Control(
        read_properties.test_a_request_member_the_shape_does_not_name_changes_nothing,
        "malformed",
        ("check_unnamed",),
    ),
    Control(
        value_field_properties.test_members_the_reader_does_not_know_change_nothing,
        "faulty_base",
        ("check_ignored",),
    ),
    Control(
        value_field_properties.test_one_fault_gives_its_refusal_and_no_other_part_1,
        "region_derivation",
        ("check_one_fault",),
    ),
    Control(
        value_field_properties.test_one_fault_gives_its_refusal_and_no_other_part_2,
        "region_derivation_inputs",
        ("check_one_fault",),
    ),
    Control(
        condition_properties.test_each_row_of_the_table_and_the_conditions_it_checks,
        "required_with_its_token",
        ("check_against_the_oracle",),
    ),
    Control(
        condition_properties.test_the_registered_unit_passes_step_9_however_escapes_write_it,
        "input_fact",
        ("check_registered",),
    ),
    Control(
        condition_properties.test_one_fault_of_step_10_gives_its_reason_beside_the_others,
        "two_faults",
        ("check_one_fault",),
    ),
    Control(
        condition_properties.test_members_the_reader_does_not_know_change_nothing_steps_9_and_10_read,
        "implied_value",
        ("check_ignored",),
    ),
    Control(
        condition_properties.test_any_other_unit_gives_unit_mismatch_with_its_condition,
        "status_object",
        ("check_refused",),
        (("place", "plus_minus"),),
    ),
    Control(
        result_properties.test_a_read_gives_a_result_whose_reasons_are_the_tables,
        "alternatives_broken",
        ("check_totality",),
    ),
    Control(
        result_properties.test_what_a_read_returns_is_as_stored_and_shares_nothing,
        "negative_zero",
        ("check_returned_as_stored",),
    ),
    *(
        Control(monotonicity_properties.test_the_worlds_hold_the_shapes_the_restrictions_are_for, shape, ())
        for shape in monotonicity_properties.WORLD_SHAPES
    ),
]


def skipped(*_: object) -> None:
    pass


def marks_of(control: Control) -> list[pytest.Mark]:
    """The property's marks, and those of the parameter set it runs with, as pytest gives them to its item."""
    marks: list[pytest.Mark] = getattr(control.test, "pytestmark", [])
    found = [mark for mark in marks if mark.name != "parametrize"]
    for mark in marks:
        if mark.name == "parametrize":
            names = [name.strip() for name in str(mark.args[0]).split(",")]
            for parameter_set in mark.args[1]:
                if tuple(zip(names, parameter_set.values, strict=True)) == control.parameters:
                    found += [decorator.mark for decorator in parameter_set.marks]
    return found


def marker_kwargs(control: Control, name: str) -> dict[str, float]:
    return {
        key: value for mark in marks_of(control) if mark.name == name for key, value in mark.kwargs.items()
    }


def marker_args(control: Control, name: str) -> tuple[str, ...]:
    return tuple(arg for mark in marks_of(control) if mark.name == name for arg in mark.args)


def control_id(control: Control) -> str:
    parameters = "".join(f"[{value}]" for _, value in control.parameters)
    return f"{control.test.__name__}{parameters}-{control.never}"


@pytest.mark.parametrize("control", CONTROLS, ids=[control_id(control) for control in CONTROLS])
def test_a_generator_that_stops_producing_a_feature_fails_the_audit_at_ci(
    control: Control, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = sys.modules[control.test.__module__]
    record: Callable[..., None] = module.feature

    def feature(name: str, shown: bool = True) -> None:
        if shown and name == control.never:
            reject()
        record(name, shown)

    # The property's own strategy, its example rejected wherever it would show the feature: a generator that
    # stops producing it, drawing the rest as before.
    monkeypatch.setattr(module, "feature", feature)
    for check in control.skipped:
        monkeypatch.setattr(module, check, skipped)
    # The `ci` profile's examples, derandomised so that the run is the same each time. Hypothesis keeps a
    # test's settings on it from when `@given` wraps it; this sets them for this test alone.
    monkeypatch.setattr(
        control.test,
        "_hypothesis_internal_use_settings",
        settings(
            vars(control.test)["_hypothesis_internal_use_settings"],
            max_examples=EXAMPLES["ci"],
            derandomize=True,
            database=None,
            suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow],
        ),
    )
    chances = marker_kwargs(control, "chances")
    drawn = marker_args(control, "drawn")
    assert control.never in chances or control.never in drawn
    with audits.counting() as counts:
        control.test(**dict(control.parameters))
    problems = audits.feature_shortfalls(
        counts,
        marker_kwargs(control, "features"),
        drawn,
        chances=chances,
        **audits.RULES["ci"],
    )
    chance = chances[control.never] if control.never in chances else 1 / len(drawn)
    floor = audits.draw_floor(EXAMPLES["ci"], chance)
    assert floor >= audits.LEAST_DRAWS
    assert problems == [
        f"feature {control.never!r} in 0 of {EXAMPLES['ci']} examples, below its floor of {floor}"
    ]
