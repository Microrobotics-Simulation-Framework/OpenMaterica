# SPDX-License-Identifier: Apache-2.0
"""JSON Schema validators for the package's schemas, with jsonschema, a development dependency only.

Every JSON file under `schema/`, the vocabulary included, is registered under its `$id`, so that a reference
resolves to the file in this tree and never over a network.
"""

import json
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012, Schema

import materica
from materica.core.jsonio import JsonValue

PACKAGE = Path(materica.__file__).parent
SCHEMA = PACKAGE / "schema" / "0.1"
BASE = "https://w3id.org/materica/schema/0.1/"


def _registry() -> Registry[Schema]:
    resources: list[tuple[str, Resource[Schema]]] = []
    for path in sorted((PACKAGE / "schema").rglob("*.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        resources.append((contents["$id"], DRAFT202012.create_resource(contents)))
    registry: Registry[Schema] = Registry()
    return registry.with_resources(resources)


REGISTRY = _registry()


def validator(reference: str) -> Callable[[JsonValue], list[str]]:
    """The errors a value has against the schema at `reference`, relative to schema 0.1's
    (`case.json#/$defs/reason`): none where it is valid."""
    checker = Draft202012Validator({"$ref": urljoin(BASE, reference)}, registry=REGISTRY)

    def errors(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = checker.iter_errors(value)  # pyright: ignore[reportUnknownMemberType]
        return [error.message for error in found]

    return errors
