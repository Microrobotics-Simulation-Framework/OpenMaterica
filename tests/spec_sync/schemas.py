# SPDX-License-Identifier: Apache-2.0
"""JSON Schema validators for the package's schemas, with jsonschema, a development dependency only.

Every JSON file under `schema/`, the vocabulary included, is registered under its `$id`, so that a reference
resolves to the file in this tree and never over a network.
"""

from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import urljoin

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012, Schema

import materica
from materica.core.jsonio import JsonValue
from tests.verdicts import DOCUMENTS, Json

PACKAGE = Path(materica.__file__).parent
SCHEMA = PACKAGE / "schema" / "0.1"
BASE = "https://w3id.org/materica/schema/0.1/"

REGISTRY: Registry[Schema] = Registry[Schema]().with_resources(
    (uri, DRAFT202012.create_resource(document)) for uri, document in DOCUMENTS.items()
)


def registry(files: Iterable[Json] = ()) -> Registry[Schema]:
    """The registry with each of `files` in place of the package's file of its `$id`."""
    return REGISTRY.with_resources((str(file["$id"]), DRAFT202012.create_resource(file)) for file in files)


def validator(reference: str, registry: Registry[Schema] = REGISTRY) -> Callable[[JsonValue], list[str]]:
    """The errors a value has against the schema at `reference`, relative to schema 0.1's
    (`case.json#/$defs/reason`), its references resolved in `registry`: none where it is valid."""
    checker = Draft202012Validator({"$ref": urljoin(BASE, reference)}, registry=registry)

    def errors(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = checker.iter_errors(value)  # pyright: ignore[reportUnknownMemberType]
        return [error.message for error in found]

    return errors
