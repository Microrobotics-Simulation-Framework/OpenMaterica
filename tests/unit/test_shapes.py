# SPDX-License-Identifier: Apache-2.0
"""The typed shapes type a number as the reader gives it: every JSON number, a whole one included, is a float
(`record_format.md` section 1 item 6). A member the schemas declare `integer` must therefore admit the float
the reader gives there, or a consumer whose code type-checks against the shape fails when it runs."""

import json
import types
from collections.abc import Iterator
from typing import Literal, NotRequired, Required, TypedDict, Union, get_args, get_origin, get_type_hints

import pytest
from typing_extensions import ReadOnly

from materica import shapes
from materica.core import jsonio
from materica.core.jsonio import JsonValue
from tests.spec_sync.schemas import SCHEMA

# The schemas the shapes are generated from (`scripts/gen_shapes.py`).
SOURCES = ("record.writer.json", "case.json", "read_request.json", "read_result.json")
WRAPPERS = (NotRequired, Required, ReadOnly)


def whole(subschema: JsonValue, definitions: dict[str, JsonValue]) -> bool:
    """Whether `subschema` takes a JSON integer: itself, a local definition it refers to, or one of its
    choices."""
    if not isinstance(subschema, dict):
        return False
    target = subschema.get("$ref")
    if isinstance(target, str) and target.startswith("#/$defs/"):
        return whole(definitions[target.removeprefix("#/$defs/")], definitions)
    choices = subschema.get("anyOf", [])
    return subschema.get("type") == "integer" or (
        isinstance(choices, list) and any(whole(choice, definitions) for choice in choices)
    )


def integer_members() -> Iterator[tuple[str, str]]:
    """Each definition of the schemas, as the shape generated from it, and each member it declares whole."""
    for name in SOURCES:
        definitions = json.loads((SCHEMA / name).read_text(encoding="utf-8")).get("$defs", {})
        for definition, schema in definitions.items():
            for member, subschema in schema.get("properties", {}).items():
                if whole(subschema, definitions):
                    yield "".join(part.capitalize() for part in definition.split("_")), member


def admits(annotation: object, value: object) -> bool:
    """Whether a value of the scalar `value` is one the type `annotation` allows."""
    origin = get_origin(annotation)
    if origin in WRAPPERS:
        return admits(get_args(annotation)[0], value)
    if origin in (Union, types.UnionType):
        return any(admits(arm, value) for arm in get_args(annotation))
    if origin is Literal:
        return value in get_args(annotation)
    if annotation is float:
        return isinstance(value, float | int) and not isinstance(value, bool)
    return any(annotation is scalar and type(value) is scalar for scalar in (int, str, bool))


def check_admits_the_readers_number(shape: type, member: str) -> None:
    number = jsonio.parse(b"12")
    assert isinstance(number, float)
    annotation = get_type_hints(shape, include_extras=True)[member]
    assert admits(annotation, number), f"{shape.__name__}.{member}: {annotation} refuses {number!r}"


INTEGER_MEMBERS = sorted(set(integer_members()))


def test_the_schemas_declare_the_whole_members_the_review_found() -> None:
    """A walk that found none would check nothing."""
    assert {
        ("Standard", "year"),
        ("Column", "index"),
        ("Species", "ncbi_taxon"),
        ("StatisticsBlock", "n_specimens"),
        ("StatisticsBlock", "n_donors"),
        ("StatisticsBlock", "n_sources"),
        ("Locator", "page"),
        ("InputSpecimen", "input"),
    } <= set(INTEGER_MEMBERS)


@pytest.mark.parametrize(
    ("shape", "member"), INTEGER_MEMBERS, ids=[".".join(pair) for pair in INTEGER_MEMBERS]
)
def test_a_whole_member_admits_the_float_the_reader_gives(shape: str, member: str) -> None:
    check_admits_the_readers_number(getattr(shapes, shape), member)


class Counted(TypedDict):
    n_specimens: int | shapes.StatusObject


def test_the_check_refuses_a_member_typed_int() -> None:
    """As `shapes.StatisticsBlock.n_specimens` was: a consumer's `range(count)` type-checked, then raised."""
    with pytest.raises(AssertionError, match=r"refuses 12\.0"):
        check_admits_the_readers_number(Counted, "n_specimens")
