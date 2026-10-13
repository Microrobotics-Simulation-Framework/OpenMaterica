# Plain-read cases

The cases of the plain-read suite: what a read of one field of one record gives, from the request's own check
(step 0) to the type check (step 5) of `docs/specification/read_side_contract.md` section 3, and the
`list_records` operation. `CASES.md` lists every case file with what it tests, where the read ends and the
expected answer. The conformance tree's `README.md` explains how to read a case.

## How the arms end early

None of these cases reads a value: that comes after step 5. So each arm is built to stop at a known step, and
three devices recur in it:
- **The interface record.** A read that passes steps 1 to 4 on `interface_fixture.json`, or on
  `water_fixture_as_interface.json`, stops at step 5 with `unknown_type`: schema 0.1.0 reserves `interface`,
  and no 0.1.0 reader reads it. So `unknown_type`, and nothing before it, shows that the earlier steps passed.
- **The unsupplied version.** A request whose target is `conformance/water_fixture` 2.0.0, with only version
  1.0.0 supplied, passes step 0 and stops at step 1 with `absent`. So `absent`, and nothing at step 0, shows
  that the request was accepted: the escaped `K`, a well-formed `accept` list, a `unit` beside it.
- **Listings.** `list_records` lists the sources that are candidates and pass steps 2, 3 and 5 on their own.
  It shows what a reader accepts without a read: a record nested 64 deep, a noncharacter, an overlay with a
  complete scope.

## The fixtures

All are illustrative, in the namespace `conformance`. See the conformance tree's `README.md`.

| Input | What it is |
|---|---|
| `water_fixture.json` | the base record: `conformance/water_fixture` 1.0.0, a material with `fluid.dynamic_viscosity` constant at 0.000692 Pa·s, temperature 310.15 K stated, shear rate unstated. Most arms are this record with one thing changed |
| `water_fixture_v2.json` | version 2.0.0 of it |
| `glycerol_fixture.json` | a second material (`bulk.density`), for listings and for sources beside the target |
| `interface_fixture.json`, `water_fixture_as_interface.json` | records of type `interface`, which a 0.1.0 reader cannot read: the step-5 stop above |
| `water_overlay_fixture.json` | an overlay on the water record, whose base pins it |
| `unknown_type_fixture.json`, `namespaced_type_fixture.json` | records of a type no 0.1.0 reader knows, and of a namespaced type |
| `scene_manifest_fixture.json`, `engine_crosswalk_fixture.json` | documents, not records: set aside at step 1 and never resolved |

The inputs come in families, named by what they break:

| Family | What it holds |
|---|---|
| `water_fault_*` | the water record broken as JSON: a byte-order mark, UTF-16 and UTF-32 text, overlong, truncated and encoded-surrogate UTF-8, a comment, a raw control character, a trailing comma, trailing content, truncated text, `NaN`, `Infinity`, `-Infinity`, unpaired surrogate escapes, a repeated member (also after unescaping), numbers that overflow, nesting 65 and 100000 deep |
| `water_schema_*` | `schema_version` absent, `null`, a number, an array, off the pattern (leading zeros, `0.1`, a trailing newline or space, Arabic-Indic digits, a pre-release, 100-digit parts), other versions (0.0.1, 0.1.7, 0.10.0, 1.0.0, 1.1.0, 2.0.0), and 0.2.0 with envelope faults (refused at step 2, before step 3 sees them) |
| `water_missing_*`, `water_*_wrong_type`, `water_null_*` | an envelope member missing or of the wrong JSON type, and `null` in each envelope member and each place of the body's structure |
| `water_content_hash_*`, `water_id_*`, `water_local_id_*`, `water_version_*`, `water_licence_*` | those envelope members off their patterns or shapes |
| other `water_*` | body structure (`sections` missing, `sections`, `fields` or `extensions` an array, a section a number or without `fields`), `document_type` without or beside `record_type`, `record_type` capitalised, `null` in an unknown member, an escaped U+0000, noncharacters, nesting exactly 64 |
| `water_fixture_*` | copies of the water record: edited after pinning (stale or recomputed hash), with another card, reformatted, as CBOR, TOML or YAML, under schema 0.2.0, and the 2.0.0 record with an uppercase hash |
| `interface_*` | the interface record, copied, edited, and with envelope faults |
| `overlay_*` | the overlay body's members missing, of the wrong type or `null`: `base`, `scope` with its `model`, `replaces`, `purpose`. Twelve are `fit` overlays, so that their scope may name a model |
| `unknown_type_*`, `namespaced_type_*` | the unknown-type records, also with envelope faults (refused at step 3 before the type is checked) |
| `source_*`, `empty_file.json`, `record_binary_bytes.json` | sources that are not records: a number, a string, an array, an object with only an `id`, an empty file, bytes that are not text |
| `request_*` | requests that are not valid JSON, used through `inputs.request` (PR-330) |

## What the cases cannot show

- **A tolerance on a token condition, on its own** (PR-330). Such a tolerance always also lacks an operating
  condition, which gives the same reason with the same condition. So a reader that ignored the rule would
  pass. The rule is kept because it states why such an entry is refused. The arms with it are right but cannot
  fail on that rule alone.
- **PR-006's set-aside arms.** A document set aside at step 1 and a source that is simply not the target give
  the same answer. PR-328 holds the arms where setting aside changes the answer.
- **Anything after step 5:** values, units in records, conditions, forms and labels on a read that is met.
  Those cases come with the code that reads them.
