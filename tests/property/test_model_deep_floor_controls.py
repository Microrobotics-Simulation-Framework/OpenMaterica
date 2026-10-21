# SPDX-License-Identifier: Apache-2.0
"""The audit controls of the floors HP12's two parts hold at `deep` alone (`@pytest.mark.deep_chances`; the
README's "The regions held to a floor"), and the check that every such floor has one.

A floor held at `deep` alone is judged only where the `deep` profile runs, CI's scheduled and dispatched runs
of the Hypothesis job, so its control runs there too, in this shard, and nowhere else: each is marked
`deep_controls`, which `tests/conftest.py` deselects at every other profile, and runs a property for
`deep`'s 20,000 examples, far longer than a pull request's controls should take
(`tests/unit/test_ci_workflows.py` holds both). A control runs another property and judges that run's audit
itself, so this directory's audits leave it alone (`conftest.py`). The run and the marks are read as the
other audit controls read them (`tests/unit/test_audit_controls.py`).
"""

import importlib
from pathlib import Path

import pytest

from tests.conftest import EXAMPLES
from tests.property import audits
from tests.property import test_model_properties as model_properties
from tests.unit.test_audit_controls import Control, control_id, marker_args, marker_kwargs, run_without

# The regions too thin for a floor at `ci`, each held to its draw floor at `deep` alone, on the property whose
# own draws its planned search stands in for. Run at `deep`'s examples and judged by `deep`'s rule, the
# property fails its audit on the feature its generator stops producing, alone: every other feature passes,
# the other region of its part, drawn as the property draws it, among them.
DEEP_CONTROLS = [
    Control(
        model_properties.test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10,
        "plus_minus_unit_refused",
        ("check_outcome",),
    ),
    Control(
        model_properties.test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10,
        "token_condition_unit_refused",
        ("check_outcome",),
    ),
    Control(
        model_properties.test_the_read_agrees_with_the_model_on_values_and_alternatives,
        "components_not_normalised",
        ("check_outcome",),
    ),
    Control(
        model_properties.test_the_read_agrees_with_the_model_on_values_and_alternatives,
        "request_faults_of_two_alternatives",
        ("check_outcome",),
    ),
]


@pytest.mark.deep_controls
@pytest.mark.parametrize("control", DEEP_CONTROLS, ids=[control_id(control) for control in DEEP_CONTROLS])
def test_a_generator_that_stops_producing_a_region_held_at_deep_fails_the_audit_at_deep(
    control: Control, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep_chances = marker_kwargs(control, "deep_chances")
    assert control.never in deep_chances
    counts = run_without(control, monkeypatch, EXAMPLES["deep"])
    problems = audits.feature_shortfalls(
        counts,
        marker_kwargs(control, "features"),
        marker_args(control, "drawn"),
        chances=marker_kwargs(control, "chances"),
        deep_chances=deep_chances,
        **audits.RULES["deep"],
    )
    floor = audits.draw_floor(EXAMPLES["deep"], deep_chances[control.never])
    assert floor >= audits.LEAST_DRAWS
    assert problems == [
        f"feature {control.never!r} in 0 of {EXAMPLES['deep']} examples, below its floor of {floor}"
    ]


def declared_at_deep() -> set[tuple[str, str]]:
    """Each feature a property of this directory declares by `deep_chances`, with the property's name."""
    found: set[tuple[str, str]] = set()
    for path in sorted(Path(__file__).parent.glob("test_*_properties.py")):
        module = importlib.import_module(f"tests.property.{path.stem}")
        for name, test in sorted(vars(module).items()):
            marks: list[pytest.Mark] = getattr(test, "pytestmark", [])
            found.update(
                (name, feature) for mark in marks if mark.name == "deep_chances" for feature in mark.kwargs
            )
    return found


def uncontrolled(controls: list[Control]) -> list[str]:
    """Each feature held at `deep` alone with no control here, and each control of a feature not so held."""
    controlled = {(control.test.__name__, control.never) for control in controls}
    declared = declared_at_deep()
    return [f"{name}: {feature} has no control" for name, feature in sorted(declared - controlled)] + [
        f"{name}: {feature} is not held at `deep` alone" for name, feature in sorted(controlled - declared)
    ]


def test_each_floor_held_at_deep_alone_has_its_control() -> None:
    assert declared_at_deep()
    assert uncontrolled(DEEP_CONTROLS) == []


def test_the_check_finds_a_floor_held_at_deep_without_a_control() -> None:
    assert uncontrolled(DEEP_CONTROLS[1:]) == [
        "test_the_read_agrees_with_the_model_on_faults_of_steps_8_to_10: plus_minus_unit_refused has no "
        "control"
    ]
    stray = Control(
        model_properties.test_the_read_agrees_with_the_model_on_values_and_alternatives, "standing", ()
    )
    assert uncontrolled([*DEEP_CONTROLS, stray]) == [
        "test_the_read_agrees_with_the_model_on_values_and_alternatives: standing is not held at `deep` alone"
    ]
