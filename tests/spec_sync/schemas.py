# SPDX-License-Identifier: Apache-2.0
"""JSON Schema validators for the package's schemas: the verdict jsonschema-rs gives (`tests/verdicts.py`),
and, for a value it refuses, the messages python-jsonschema gives. Both are development dependencies only.

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
from tests.verdicts import DOCUMENTS, Json, verdict

PACKAGE = Path(materica.__file__).parent
SCHEMA = PACKAGE / "schema" / "0.1"
BASE = "https://w3id.org/materica/schema/0.1/"

REGISTRY: Registry[Schema] = Registry[Schema]().with_resources(
    (uri, DRAFT202012.create_resource(document)) for uri, document in DOCUMENTS.items()
)
TAKEN_BY_PYTHON = "jsonschema-rs refuses it, python-jsonschema takes it"


def registry(files: Iterable[Json] = ()) -> Registry[Schema]:
    """python-jsonschema's registry of the package's files, each of `files` in place of the file of its
    `$id`."""
    return REGISTRY.with_resources((str(file["$id"]), DRAFT202012.create_resource(file)) for file in files)


def why_refused(schema: Json, files: Iterable[Json] = ()) -> Callable[[JsonValue], list[str]]:
    """python-jsonschema's messages for a value jsonschema-rs refuses against `schema`, with `files` as in
    `registry`; where python-jsonschema finds nothing, the two disagree, and the one message says so."""
    checker = Draft202012Validator(schema, registry=registry(files))

    def messages(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = checker.iter_errors(value)  # pyright: ignore[reportUnknownMemberType]
        return [error.message for error in found] or [TAKEN_BY_PYTHON]

    return messages


def validator(reference: str, files: Iterable[Json] = ()) -> Callable[[JsonValue], list[str]]:
    """The errors a value has against the schema at `reference`, relative to schema 0.1's
    (`case.json#/$defs/reason`), with `files` as in `registry`: none where jsonschema-rs takes it, and
    python-jsonschema's messages where it does not."""
    files = tuple(files)
    schema: Json = {"$ref": urljoin(BASE, reference)}
    accepts, messages = verdict(schema, files), why_refused(schema, files)

    def errors(value: JsonValue) -> list[str]:
        return [] if accepts(value) else messages(value)

    return errors


def takes(reference: str, files: Iterable[Json] = ()) -> Callable[[JsonValue], bool]:
    """Whether jsonschema-rs takes a value against the schema at `reference`, as `validator` reads it, with
    no messages: for a loop in which refusals are common."""
    return verdict(urljoin(BASE, reference), files)
