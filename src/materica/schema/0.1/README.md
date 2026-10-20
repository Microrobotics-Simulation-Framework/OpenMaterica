# Schema 0.1

| File | What it is | Edited |
|---|---|---|
| `record.writer.json` | a record as a writer writes it: closed in its structure, but for the places its description names. The envelope, the body's structure and the value fields of the four forms 0.1.0's fields use without tables (constant, interval, composition, evidence), with conditions, specimen facts, the statistics block and the provenance object; the table, power-law, parameter-set and reference-data forms, the fit record and the provenance members whose own members the specification does not yet name are placeholders. Each section's field names, an overlay's replaced fields, each field's forms, unit and label, and a numeric condition's unit are bound to their rows by the vocabulary's bindings, applied by `allOf`. A member marked `x-materica-write-only` is one a read does not check | by hand |
| `record.reader.json` | a record as a reader checks it at step 3 of a read: open, never applying a value field's shape; its `$defs` hold a value field's and a section specimen's shapes as step 8 checks them | generated, by `scripts/gen_reader_schema.py` |
| `read_request.json` | a read request (`read_side_contract.md` section 1) | by hand |
| `read_result.json` | a read result (`read_side_contract.md` section 2); its `result_` definitions are the writer's a result returns, closed alike, without the patterns of members a read checks only as strings | by hand |
| `case.json` | a conformance case file, holding a read request or an operation, and the result it expects | by hand |
| `page_text.json` | a page-text document (`page_text.md` section 1): the text of one copy as one text extraction gave it, the pages of a PDF or the text and elements of an XML file. The rules it does not state (a range in order and within its text, a jump at a line feed, no line ending in `White_Space`) are the record checks' (RC-220) | by hand |
| `vocabulary/` | the tokens of the specification's tables, and the bindings of their rows (`vocabulary/README.md`) | generated, by `scripts/gen_vocabulary.py` |

Every file's `$id` is its path under `https://w3id.org/materica/schema/0.1/`
(`tests/spec_sync/test_schemas.py`), and the files refer to each other by `$ref`s relative to their `$id`s:
`case.json` to `read_request.json` and `read_result.json`, these and `page_text.json` to `record.writer.json`,
`read_result.json` to `vocabulary/reasons.json` for the reason codes, and `record.writer.json` to the
vocabulary for every other token list and for the bindings of the rows.
