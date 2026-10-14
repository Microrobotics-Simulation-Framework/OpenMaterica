# Scripts

Development and CI tools; nothing in the package imports them. All but `gen_shapes.py` use Python's standard
library only, so the sign-off check runs before any dependency is installed.

| Script | What it does | When CI runs it |
|---|---|---|
| `check_signoff.py <base> <head>` | checks that every commit in `base..head` carries a DCO `Signed-off-by` from its author (CONTRIBUTING constraint 1); the design commits made before the first code commit are exempt, by ancestry of one pinned commit | on every pull request, in the first job, whatever the change touches |
| `check_wheel.py <wheel>` | checks that the built wheel holds `py.typed`, every file under `data/` and `schema/` byte for byte and no other there, the licence as an SPDX expression with its file (PEP 639), no run-time dependency, and nothing outside the package | in the static job, after `uv build`, when a change touches code |
| `gen_vocabulary.py [--check]` | generates `src/materica/schema/0.1/vocabulary/*.json`, each with its `$id`, from the specification's tables: reasons, fields, conditions, specimen facts and acceptance kinds; a list of tokens is read in full, and a cell it cannot read stops it | with `--check`, in the generated-files job, when a change touches code |
| `gen_reader_schema.py [--check]` | generates `schema/0.1/record.reader.json` from the writer schema, opened where `record_format.md` section 1 item 2 says a reader is open | as above |
| `gen_shapes.py [--check]` | generates `src/materica/shapes.py` and `shapes.pyi`, the JSON shapes as TypedDicts, from the writer schema, `case.json` and the read request and result, with datamodel-code-generator and ruff (pinned in the dev group), working in a temporary copy of the schemas; runs on Python 3.11 to 3.14, since the generator does not run on 3.15 | as above |
| `schema_index.py <directory>` | writes an `index.html` into a published schema tree and each directory under it, linking what each holds, with every JSON file's `$id` and its schema's title and description; refuses a tree that already holds an `index.html` | in the Pages workflow, on its staged copy of `src/materica/schema/`, at every deployment |

A generator writes its files; with `--check` it writes nothing and fails where a file on disk differs from what
its source gives, so a hand edit to a generated file, or a source edited without regenerating, fails CI
(CONTRIBUTING, "Changing the schema"). Each script has tests in `tests/unit/` that show it failing on what it
must refuse.
