# Schemas

The JSON Schemas (layer L0, AD 7.1), in the dialect of JSON Schema 2020-12, one directory per schema version.
Each version has a closed writer schema and an open reader schema for records (`record_format.md` section 1
item 2), schemas for the read request and result, a schema for conformance case files, a schema for page-text
documents (`page_text.md`), and the vocabulary. Every file's `$id` is its path under
`https://w3id.org/materica/schema/`; an `$id` is an identifier and need not resolve.

## Where each fact is edited

- **Structure** is edited in the writer schemas, by hand. The specification's member tables (the envelope, the
  read request and result, a value field, the provenance object, the statistics block, the conditions and the
  specimen facts, the members that may hold a status object, and the page-text document) are checked against
  them, not generated from them, so the specification keeps its prose (`tests/spec_sync/test_schemas.py`,
  `test_value_fields.py`).
- **Tokens** are edited in the specification's tables and token lists. The vocabulary is generated from them
  (`0.1/vocabulary/`), and a schema takes a token list from it by `$ref`: a reason's code in `read_result.json`,
  and every token list of a value field in `record.writer.json` but the status-object tokens, which are
  written there by hand and checked against `provenance.md` section 1. The writer schema is closed in its
  structure but for the places its description names, the placeholders whose members the specification does
  not yet name among them. A section's field names, an overlay's replaced fields, each field's forms, unit and
  label, and a numeric condition's unit are bound to their rows by the vocabulary's bindings, which the writer
  applies by `allOf` (maintainer, 2026-10-15).
- **The reader schema** is generated from the writer schema by `scripts/gen_reader_schema.py`, which opens it
  where a reader is open: unknown members and tokens pass, a pattern stays only on `id`, `version` and
  `content_hash`, and the shapes of value fields, forms and a section's `specimen` are never applied. Its
  `$defs` hold those shapes as step 8 of a read checks them, opened alike, for a reader that checks one field
  with them: a member the writer schema marks `x-materica-write-only`, one a read does not check (its
  `extraction`, a `review`), accepts anything there and is required nowhere, and a rule that tests one or
  requires only such members (a recipe where the value is withheld) is left out. A member marked
  `{"unless": {<member>: <token>}}` is one a read checks only where that member holds that token (a
  `derivation` for origin `derived`): the reader `$defs` apply its shape there alone, and elsewhere treat it
  as write-only. Cross-member rules (a range in order, no component twice), a member one slip from a named
  one, and a token or status token where its row does not allow it are step 8's but no JSON Schema's.
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

The published site shows which side of the release a version is on. The index page of a version that the list
does not hold opens with a note, "Draft until 0.1.0": its files may change until the release, and the release
freezes them. The page of a listed version has none (`scripts/schema_index.py`, tested in
`tests/unit/test_schema_index.py`), so freezing a version at its release removes the note when Pages next
deploys. Until 0.1.0 is released, then, the 0.1 files at `https://w3id.org/materica/schema/0.1/` can be seen to
change. The manifest is committed in the release's pull request, before the tag, so the note leaves the site when
that pull request merges and Pages deploys, which is just before the tag: from that merge CI holds the files, and
the note's "until 0.1.0 is released" is read as until then. That is intended.

**The next line** (maintainer, 2026-10-18). After 0.1.0 is released, the development of the next minor version
lives in a directory of its own, `0.2-dev/`, with `$id`s under `https://w3id.org/materica/schema/0.2-dev/`, and
its index page carries the same note. At the 0.2.0 release the directory is renamed `0.2/` (moved, not copied:
the site's staging refuses a tree that holds both `0.2-dev/` and `0.2/`), its `$id`s are rewritten to match, and
`scripts/freeze_schema.py 0.2` freezes it, which it would refuse to do under the name `0.2-dev` or with the old
`$id`s. The rename is more than the `$id`s: the files the generators write into the directory (the reader
schema, the vocabulary) move with it, and the paths wired to `0.1` (`scripts/gen_vocabulary.py`,
`scripts/gen_reader_schema.py`, `scripts/gen_shapes.py`, `tests/spec_sync/schemas.py`) are pointed at the new
line, since each generator's `--check` reads only the tree it names. Renaming and freezing is the documented
path; the alternative, to redirect the address by a pull request to `perma-id/w3id.org`, is decided at the 0.2.0
release. No `0.2-dev/` exists until the first change that belongs to 0.2 is made.

## Who reads them

The Python reader checks envelopes with `core/envelope.py`, which tests hold to agreement with the reader schema;
it never runs a JSON Schema validator. The schemas are for readers in other languages, for record checks, and
for the tests, which validate with jsonschema-rs and hold python-jsonschema to its verdicts, both development
dependencies.
