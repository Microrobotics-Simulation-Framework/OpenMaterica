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
resolves to the file in this tree and never over a network. Beside them, `read_result.json`'s twins of the
writer's definitions, which `test_schemas.py` and the name-overlap walk read alike.
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


# The writer's definitions a result returns holding a member a read checks only as a string, and the patterns
# that member's writer definition gives it (S2a-4's review, L1): an anatomical site's UBERON identifier, a
# record check's (RC-039), and a derivation input's pinned record (`provenance.md` section 5, "`id`,
# `version`, `content_hash` and `field` each a string"). In read_result.json each is a `result_` twin, closed
# as the writer's, without them, so that a correct result of a record the writer refuses validates.
RESULT_TWINS = (
    "specimen",
    "anatomical_site",
    "derivation",
    "derivation_input",
    "pinned_record",
    "input_specimen",
)
UNCHECKED_AT_READ = (
    "vocabulary/specimen_facts.json#/$defs/anatomical_site_uberon",
    "#/$defs/record_id",
    "#/$defs/version",
    "#/$defs/content_hash",
)


def as_returned(node: JsonValue) -> JsonValue:
    """A part of a writer definition as read_result.json gives it: a reference to a pattern a read does not
    check any string, to a definition of RESULT_TWINS its twin, to another of the writer's the writer's, and
    to the vocabulary unchanged (both files sit beside it)."""
    if isinstance(node, list):
        return [as_returned(item) for item in node]
    if not isinstance(node, dict):
        return node
    reference = node.get("$ref")
    if not isinstance(reference, str):
        return {key: as_returned(value) for key, value in node.items()}
    assert set(node) == {"$ref"}, node
    name = reference.removeprefix("#/$defs/")
    if reference in UNCHECKED_AT_READ:
        return {"type": "string"}
    if name == reference:
        return node
    return {"$ref": f"#/$defs/result_{name}" if name in RESULT_TWINS else f"record.writer.json{reference}"}
