# Specification sync

Checks that what is written in two places says the same in both. The specification is normative, so where a
check here fails, the specification holds and the other copy is wrong.

| Test | Holds together |
|---|---|
| `test_schemas.py` | the specification's member tables (the envelope, the read request and result) and the schemas' members; the token lists written in the schemas by hand (sections, record types, `want`s, suites, overlay purposes, status-object tokens, read statuses) and the specification's tables or text, with a control that changes the text; and every schema file's `$id` against its path, with a control |
| `test_envelope.py` | `core/envelope.py` and the generated reader schema, which accept and refuse the same conformance inputs |
| `test_cases_md.py` | each suite's `CASES.md` and its case files: one row per file, the expected column as the file states it, and each heading the specification's row for its case |
| `test_case_steps.py` | `case_steps.json` and the case files: every case file mapped to the implementation step whose code first runs it, and every case file of a step done passing |

The vocabulary and the generated schemas and shapes are checked by their generators' `--check`, which CI runs
(`scripts/README.md`). `schemas.py` gives jsonschema validators for the package's schemas, each reference
resolved to a file in this tree, never over a network.
