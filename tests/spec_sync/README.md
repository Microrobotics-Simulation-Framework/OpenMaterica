# Specification sync

Checks that what is written in two places says the same in both. The specification is normative, so where a
check here fails, the specification holds and the other copy is wrong; for a released schema, the manifest
holds.

| Test | Holds together |
|---|---|
| `test_schemas.py` | the specification's member tables (the envelope, the read request and result) and the schemas' members; the token lists written in the schemas by hand (sections, record types, `want`s, suites, overlay purposes, status-object tokens, read statuses) and the specification's tables or text, with a control that changes the text; and every schema file's `$id` against its path, with a control |
| `test_released_schemas.py` | each released schema version's directory and its entry in `released_schemas.json`, which `scripts/freeze_schema.py` writes at release: no file added, removed or changed, every `$id` still its path, and no version listed without its directory. Its controls run on a copy of the tree with 0.1 frozen: a file changed, added or removed, the directory gone, and an `$id` frozen wrong |
| `test_envelope.py` | `core/envelope.py` and the generated reader schema, which accept and refuse the same conformance inputs |
| `test_cases_md.py` | each suite's `CASES.md` and its case files: one row per file, the expected column as the file states it, and each heading the specification's row for its case |
| `test_case_steps.py` | `case_steps.json` and the case files: every case file mapped to the implementation step whose code first runs it (S2 by its pieces, `S2a-1` to `S2b-2`, or a list of pieces whose order is not fixed), and every case file of a step done passing; the runner reports the others as not yet runnable |
| `test_references.py` | each reference in the specification, the architecture draft and the documentation plan, in the forms its docstring lists, and the section, item or title it names; each case tag and a row of a Cases table, and each row and a tag; and the items of each numbered list, no two with one number. References that are right but that the forms read wrongly are allowed by name, each with its reason |

The vocabulary and the generated schemas and shapes are checked by their generators' `--check`, which CI runs
(`scripts/README.md`). `schemas.py` gives jsonschema validators for the package's schemas, each reference
resolved to a file in this tree, never over a network.
