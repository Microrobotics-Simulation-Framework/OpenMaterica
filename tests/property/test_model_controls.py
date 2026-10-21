# SPDX-License-Identifier: Apache-2.0
"""Can-fail controls of HP12's check (`test_model_properties.check_agreement`), on reads written out here: it
fails on a divergence its list does not hold, on a listed one that does not hold as listed, and on an open
point the model no longer refuses or that the implementation no longer reads as listed. HP12 lists no open
point since the maintainer's ruling of 2026-10-19, so its controls take the last one, open point 1's record
half, as the implementation read it before that ruling, with the listing it had. The mutant searches
(`test_model_mutants.py`) show it failing on faults of either side."""

import json
from pathlib import Path
from typing import Any

import pytest

from materica.core import value_shapes
from materica.core.hashing import content_hash
from materica.core.jsonio import JsonValue
from materica.core.read import read
from materica.core.reasons import Reason
from materica.shapes import Suite
from tests.property import test_model_properties as properties
from tests.property.condition_strategies import at
from tests.property.model_strategies import Example
from tests.reference.mutants import MUTANTS as MODEL_FAULTS
from tests.unit.test_read import INPUTS, REQUEST, water

JsonObject = dict[str, JsonValue]
CLAIMS: frozenset[Suite] = frozenset({"plain_read", "hash"})
CASES = INPUTS.parent / "cases"


def pinned_example(record: JsonObject, request: JsonObject, *planted: str) -> Example:
    record = {**record, "content_hash": content_hash(record)}
    target = request["target"]
    assert isinstance(target, dict)
    target["record"] = {name: record[name] for name in ("id", "version", "content_hash")}
    return Example("control", (json.dumps(record).encode(),), json.dumps(request).encode(), CLAIMS, planted)


def water_read() -> tuple[JsonObject, JsonObject]:
    request: JsonObject = json.loads(json.dumps(REQUEST))
    return water(), request


def temperature_of(record: JsonObject) -> JsonObject:
    return at(record, "body", "sections", "fluid", "fields", "dynamic_viscosity", "conditions", "temperature")


def overlay_as_the_target() -> Example:
    """PR-007's case of an overlay as the target, which S4 builds."""
    case: dict[str, Any] = json.loads((CASES / "PR-007.target_is_overlay.json").read_text(encoding="utf-8"))
    sources = tuple(Path(INPUTS / name).read_bytes() for name in case["inputs"]["records"])
    return Example("control", sources, json.dumps(case["request"]).encode(), CLAIMS)


def trainable_across_the_edge() -> Example:
    """PR-339's case file, a read under a `trainable` acceptance, which S7a-4 builds."""
    case: dict[str, Any] = json.loads(
        (CASES / "PR-339.across_edge_no_value.json").read_text(encoding="utf-8")
    )
    sources = tuple(Path(INPUTS / name).read_bytes() for name in case["inputs"]["records"])
    return Example("control", sources, json.dumps(case["request"]).encode(), CLAIMS)


def token_on_a_numeric_condition() -> Example:
    record, request = water_read()
    temperature_of(record)["token"] = "tube"
    return pinned_example(record, request, "members_of_the_other_kind")


def read_as_before_its_ruling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Open point 1's record half listed as it was until the maintainer's ruling of 2026-10-19, and read by
    the implementation as it was: a numeric condition's `token` ignored by step 8."""
    conditions = value_shapes.conditions

    def ignoring(value: JsonValue, where: str, found: list[Reason]) -> None:
        temperature = value.get("temperature") if isinstance(value, dict) else None
        if isinstance(value, dict) and isinstance(temperature, dict):
            value = {
                **value,
                "temperature": {name: held for name, held in temperature.items() if name != "token"},
            }
        conditions(value, where, found)

    monkeypatch.setattr(value_shapes, "conditions", ignoring)
    monkeypatch.setitem(
        properties.OPEN_POINTS,
        "members_of_the_other_kind",
        properties.OpenPoint("form_invalid", "members_of_the_other_kind_ignored"),
    )


def test_a_read_both_decide_alike_passes() -> None:
    record, request = water_read()
    assert properties.check_agreement(pinned_example(record, request)) == "agrees"


def test_a_listed_divergence_passes_and_fails_once_unlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    example = overlay_as_the_target()
    assert properties.check_agreement(example) == "not_built"
    monkeypatch.delitem(properties.NOT_BUILT, "an overlay as the target")
    with pytest.raises(AssertionError, match="a step not built that no divergence lists"):
        properties.check_agreement(example)


def test_a_listed_divergence_fails_where_the_draw_does_not_hold_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The implementation's words alone never list a divergence: a water read that raised as for an overlay
    target fails."""

    def raises_as_for_an_overlay(*arguments: object, **members: object) -> None:
        raise NotImplementedError("a read whose target is an overlay is not built yet")

    monkeypatch.setattr(properties, "read", raises_as_for_an_overlay)
    record, request = water_read()
    with pytest.raises(AssertionError, match="an overlay as the target, not as listed"):
        properties.check_agreement(pinned_example(record, request))


def test_a_kind_not_read_passes_as_listed_and_fails_once_unlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    example = trainable_across_the_edge()
    assert properties.check_agreement(example) == "not_read"
    monkeypatch.delitem(properties.NOT_READ, "a trainable acceptance")
    with pytest.raises(AssertionError, match="the implementation gives"):
        properties.check_agreement(example)


def test_a_kind_not_read_fails_where_the_implementation_does_not_refuse_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model's words alone never list a divergence: an implementation that reads the request as without
    its `trainable` acceptance, so that it gives `outside_range` and not `request_incomplete`, fails."""

    def as_without_it(request: Any, store: Any, **members: Any) -> Any:
        parsed = json.loads(request)
        del parsed["acceptances"]
        return read(json.dumps(parsed).encode(), store, **members)

    monkeypatch.setattr(properties, "read", as_without_it)
    with pytest.raises(AssertionError, match="the implementation gives"):
        properties.check_agreement(trainable_across_the_edge())


def test_open_point_1s_record_half_reads_alike_since_its_ruling() -> None:
    """Both refuse a numeric condition holding `token` (`provenance.md` section 6.1 item 1), so the draw that
    plants it agrees, and HP12 lists no divergence of it."""
    assert "members_of_the_other_kind" not in properties.OPEN_POINTS
    assert properties.check_agreement(token_on_a_numeric_condition()) == "agrees"


def test_an_open_point_passes_as_listed_and_fails_unlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    read_as_before_its_ruling(monkeypatch)
    example = token_on_a_numeric_condition()
    assert properties.check_agreement(example) == "open_point"
    monkeypatch.delitem(properties.OPEN_POINTS, "members_of_the_other_kind")
    with pytest.raises(AssertionError, match="the implementation gives"):
        properties.check_agreement(example)


def test_an_open_point_fails_where_the_model_no_longer_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    read_as_before_its_ruling(monkeypatch)
    with (
        MODEL_FAULTS["members_of_the_other_kind_ignored"].applied(),
        pytest.raises(AssertionError, match="the model does not refuse it"),
    ):
        properties.check_agreement(token_on_a_numeric_condition())


def test_an_open_point_fails_where_the_listed_reading_is_not_the_implementations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_as_before_its_ruling(monkeypatch)
    monkeypatch.setitem(
        properties.OPEN_POINTS,
        "members_of_the_other_kind",
        properties.OpenPoint("form_invalid", "declaration_names_not_named_in_a_request"),
    )
    with pytest.raises(AssertionError, match="members_of_the_other_kind: the implementation gives"):
        properties.check_agreement(token_on_a_numeric_condition())
