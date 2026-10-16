# SPDX-License-Identifier: Apache-2.0
"""Every verdict the tests take from the package's JSON Schemas, given by jsonschema-rs, a development
dependency only.

python-jsonschema stays in two roles: a second, independent implementation, which
`tests/property/test_validators_agree.py` holds to the same verdicts, and the source of the messages a failing
test prints (`tests/spec_sync/schemas.py`). Both read the documents here.

Every JSON file under `schema/`, the vocabulary included, is registered under its `$id`, so that a reference
resolves to the file in this tree and never over a network. A `format` is an annotation, as python-jsonschema
reads it without a format checker.
"""

import json
from collections.abc import Callable, Iterable
from pathlib import Path

import jsonschema_rs

import materica
from materica.core.jsonio import JsonValue

Json = dict[str, JsonValue]

DOCUMENTS: dict[str, Json] = {
    str(document["$id"]): document
    for document in (
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((Path(materica.__file__).parent / "schema").rglob("*.json"))
    )
}
REGISTRY = jsonschema_rs.Registry([(uri, document) for uri, document in DOCUMENTS.items()])


def verdict(schema: str | Json, files: Iterable[Json] = ()) -> Callable[[JsonValue], bool]:
    """Whether a value is valid against `schema`, a schema object or the absolute reference of one, with each
    of `files` (a schema file, a mutant of it) in place of the package's file of its `$id`."""
    replaced = {str(file["$id"]): file for file in files}
    registry = (
        jsonschema_rs.Registry([(uri, document) for uri, document in (DOCUMENTS | replaced).items()])
        if replaced
        else REGISTRY
    )
    root: Json = {"$ref": schema} if isinstance(schema, str) else schema
    checker = jsonschema_rs.Draft202012Validator(
        root, registry=registry, validate_formats=False, offline=True
    )
    return checker.is_valid
