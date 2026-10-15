# SPDX-License-Identifier: Apache-2.0
"""The controls of the feature audits of the json and records shards' properties that declare features by
their chances (`@pytest.mark.chances`): run at the `ci` profile's examples with a generator that stops
producing one of them, each property fails its audit, on that feature alone. Outside `tests/property/`, whose
audits would fail these runs too."""

import sys
from collections.abc import Callable
from typing import NamedTuple

import pytest
from hypothesis import HealthCheck, reject, settings

from tests.conftest import EXAMPLES
from tests.property import audits
from tests.property import test_canonical_properties as canonical_properties
from tests.property import test_hashing_properties as hashing_properties
from tests.property import test_jsonio_properties as jsonio_properties
from tests.property import test_read_properties as read_properties
from tests.property import test_value_field_properties as value_field_properties
from tests.property import test_version_properties as version_properties


class Control(NamedTuple):
    test: Callable[..., None]  # the property, as pytest runs it
    never: str  # the feature its generator stops producing
    # The checks of the property's law it skips: the audit counts the features, which the checks do not
    # change, and skipping them saves most of the run.
    skipped: tuple[str, ...]


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
]


def skipped(*_: object) -> None:
    pass


def marker_kwargs(test: Callable[..., None], name: str) -> dict[str, float]:
    marks: list[pytest.Mark] = getattr(test, "pytestmark", [])
    return {key: value for mark in marks if mark.name == name for key, value in mark.kwargs.items()}


@pytest.mark.parametrize(
    "control", CONTROLS, ids=[f"{control.test.__name__}-{control.never}" for control in CONTROLS]
)
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
    chances = marker_kwargs(control.test, "chances")
    assert control.never in chances
    with audits.counting() as counts:
        control.test()
    problems = audits.feature_shortfalls(
        counts,
        marker_kwargs(control.test, "features"),
        by_draws=True,
        chances=chances,
        chance_floors=True,
    )
    floor = audits.draw_floor(EXAMPLES["ci"], chances[control.never])
    assert floor >= audits.LEAST_DRAWS
    assert problems == [
        f"feature {control.never!r} in 0 of {EXAMPLES['ci']} examples, below its floor of {floor}"
    ]
