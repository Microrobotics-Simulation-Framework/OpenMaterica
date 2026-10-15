# Schemas

The JSON Schemas (layer L0, AD 7.1), in the dialect of JSON Schema 2020-12, one directory per schema version.
Each version has a closed writer schema and an open reader schema for records (`record_format.md` section 1
item 2), schemas for the read request and result, a schema for conformance case files, and the vocabulary.
Every file's `$id` is its path under `https://w3id.org/materica/schema/`; an `$id` is an identifier and need
not resolve.

## Where each fact is edited

- **Structure** is edited in the writer schemas, by hand. The specification's member tables (the envelope, the
  read request and result, a value field, the provenance object, the statistics block, the conditions and the
  specimen facts, and the members that may hold a status object) are checked against them, not generated from
  them, so the specification keeps its prose (`tests/spec_sync/test_schemas.py`, `test_value_fields.py`).
- **Tokens** are edited in the specification's tables and token lists. The vocabulary is generated from them
  (`0.1/vocabulary/`), and a schema takes a token list from it by `$ref`: a reason's code in `read_result.json`,
  and every token list of a value field in `record.writer.json` but the status-object tokens, which are
  written there by hand and checked against `provenance.md` section 1. The writer schema is closed in its
  structure but for the places its description names: a section's field names, which the vocabulary
  registers, and the placeholders whose members the specification does not yet name.
- **The reader schema** is generated from the writer schema by `scripts/gen_reader_schema.py`, which opens it
  where a reader is open: unknown members and tokens pass, a pattern stays only on `id`, `version` and
  `content_hash`, and the shapes of value fields, forms and a section's `specimen` are never applied. Its
  `$defs` hold those shapes as step 8 of a read checks them, opened alike, for a reader that checks one field
  with them: a member the writer schema marks `x-materica-write-only`, one a read does not check (its
  `extraction`, a `review`), accepts anything there and is required nowhere, and a rule that tests one or
  requires only such members (a recipe where the value is withheld) is left out. Cross-member rules (a range in
  order, no component twice), a member one slip from a named one, and a token or status token where its row
  does not allow it are step 8's but no JSON Schema's.
- **The typed shapes** (`materica/shapes.py`, `shapes.pyi`) are generated from the writer schema,
  `case.json` and the request and result it refers to, by `scripts/gen_shapes.py`.

CI regenerates every derived file and fails where one differs (CONTRIBUTING, "Changing the schema"). Every
pattern starts with `^` and ends with `(?![\s\S])`: a validator's `$` also matches before a final newline.

## Released versions

Until a schema version is released its files may change; once it is released they never change, and a change
is a new minor version in a new directory (maintainer, 2026-10-14). At the release, `scripts/freeze_schema.py`
lists the version, with every file under its directory and the SHA-256 of its bytes, in
`tests/spec_sync/released_schemas.json`. From then on `tests/spec_sync/test_released_schemas.py` fails where
one of those files is added, removed or changed, or an `$id` is no longer its path. The list lies outside this
tree, so the wheel and the published site hold the schemas alone.

## Who reads them

The Python reader checks envelopes with `core/envelope.py`, which tests hold to agreement with the reader schema;
it never runs a JSON Schema validator. The schemas are for readers in other languages, for record checks, and
for the tests, which validate with jsonschema, a development dependency.
