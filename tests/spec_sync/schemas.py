# SPDX-License-Identifier: Apache-2.0
"""JSON Schema validators for the package's schemas, from jsonschema-rs (`tests/verdicts.py`) and
python-jsonschema, both development dependencies only:
- `validator` and `agreed`, for a test that takes few verdicts: both libraries judge every value, and a
  Disagreement fails the test where they differ; `validator` gives python-jsonschema's messages;
- `takes`, for a loop: jsonschema-rs alone, its verdicts held to python-jsonschema's by
  `tests/property/test_validators_agree.py`, which lists every place that calls it;
- `why_refused`: python-jsonschema's messages for a value jsonschema-rs refuses; where it finds none, the two
  disagree, and the test fails at once.

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


class Disagreement(Exception):
    """jsonschema-rs and python-jsonschema give a value different verdicts. Not an AssertionError, so that a
    search that takes an assertion as a mutant's death (`kill` in `tests/property/test_writer_mutants.py`)
    never takes a disagreement for one."""


def registry(files: Iterable[Json] = ()) -> Registry[Schema]:
    """python-jsonschema's registry of the package's files, each of `files` in place of the file of its
    `$id`."""
    return REGISTRY.with_resources((str(file["$id"]), DRAFT202012.create_resource(file)) for file in files)


def why_refused(schema: Json, files: Iterable[Json] = ()) -> Callable[[JsonValue], list[str]]:
    """python-jsonschema's messages for a value jsonschema-rs refuses against `schema`, with `files` as in
    `registry`; where python-jsonschema finds none, the two disagree, and it raises Disagreement."""
    checker = Draft202012Validator(schema, registry=registry(files))

    def messages(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = checker.iter_errors(value)  # pyright: ignore[reportUnknownMemberType]
        said = [error.message for error in found]
        if not said:
            said_of = f"{value!r:.300} against {schema}"
            raise Disagreement(f"jsonschema-rs refuses, python-jsonschema takes {said_of}")
        return said

    return messages


def both(schema: str | Json, files: Iterable[Json] = ()) -> Callable[[JsonValue], list[str]]:
    """python-jsonschema's messages for a value against `schema`, a schema object or a reference relative to
    schema 0.1's (`case.json#/$defs/reason`), with `files` as in `registry`: a Disagreement where
    jsonschema-rs's verdict differs."""
    files = tuple(files)
    root: Json = {"$ref": urljoin(BASE, schema)} if isinstance(schema, str) else schema
    rust, checker = verdict(root, files), Draft202012Validator(root, registry=registry(files))

    def messages(value: JsonValue) -> list[str]:
        # types-jsonschema types its second overload's instance as unknown.
        found = checker.iter_errors(value)  # pyright: ignore[reportUnknownMemberType]
        said = [error.message for error in found]
        if rust(value) == bool(said):
            verdicts = "takes, python-jsonschema refuses" if said else "refuses, python-jsonschema takes"
            raise Disagreement(f"jsonschema-rs {verdicts} {value!r:.300} against {schema}")
        return said

    return messages


def validator(reference: str, files: Iterable[Json] = ()) -> Callable[[JsonValue], list[str]]:
    """The errors a value has against the schema at `reference`, as in `both`: python-jsonschema's messages,
    none where both libraries take it, and a Disagreement where they differ."""
    return both(reference, files)


def agreed(schema: str | Json, files: Iterable[Json] = ()) -> Callable[[JsonValue], bool]:
    """Whether a value is valid against `schema`, as in `both`: a Disagreement where the libraries differ."""
    messages = both(schema, files)
    return lambda value: messages(value) == []


def takes(reference: str, files: Iterable[Json] = ()) -> Callable[[JsonValue], bool]:
    """Whether jsonschema-rs takes a value against the schema at `reference`, as `validator` reads it, with
    no messages: for a loop in which refusals are common."""
    return verdict(urljoin(BASE, reference), files)
