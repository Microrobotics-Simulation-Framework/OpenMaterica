# Schema 0.1

| File | What it is | Edited |
|---|---|---|
| `record.writer.json` | a record as a writer writes it: closed. So far the envelope and the body's structure; value fields, forms and specimen facts are placeholders until their shapes are written | by hand |
| `record.reader.json` | a record as a reader checks it at step 3 of a read: open, never applying a value field's shape | generated, by `scripts/gen_reader_schema.py` |
| `read_request.json` | a read request (`read_side_contract.md` section 1) | by hand |
| `read_result.json` | a read result (`read_side_contract.md` section 2) | by hand |
| `case.json` | a conformance case file, holding a read request or an operation, and the result it expects | by hand |
| `vocabulary/` | the tokens of the specification's tables (`vocabulary/README.md`) | generated, by `scripts/gen_vocabulary.py` |

Every file's `$id` is its path under `https://w3id.org/materica/schema/0.1/` (`tests/spec_sync/test_schemas.py`),
and the files refer to each other by `$ref`s relative to their `$id`s: `case.json` to `read_request.json` and
`read_result.json`, these to `record.writer.json`, and `read_result.json` to `vocabulary/reasons.json` for the
reason codes.
