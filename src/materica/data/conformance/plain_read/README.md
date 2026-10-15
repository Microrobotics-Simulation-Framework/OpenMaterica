# Plain-read cases

The cases of the plain-read suite: what a read of one field of one record gives, from the request's own check
(step 0) through the type check (step 5) to the value (steps 6 to 13) of
`docs/specification/read_side_contract.md` section 3, and the `list_records` operation. `CASES.md` lists every
case file with what it tests, where the read ends and the expected answer. The conformance tree's `README.md`
explains how to read a case.

## How the arms end early

The cases that end by step 5 read no value. So each of them is built to stop at a known step, and three
devices recur in them:
- **The interface record.** A read that passes steps 1 to 4 on `interface_fixture.json`, or on
  `water_fixture_as_interface.json`, stops at step 5 with `unknown_type`: schema 0.1.0 reserves `interface`,
  and no 0.1.0 reader reads it. So `unknown_type`, and nothing before it, shows that the earlier steps passed.
- **The unsupplied version.** A request whose target is `conformance/water_fixture` 2.0.0, with only version
  1.0.0 supplied, passes step 0 and stops at step 1 with `absent`. So `absent`, and nothing at step 0, shows
  that the request was accepted: the escaped `K`, a well-formed `accept` list, a `unit` beside it.
- **Listings.** `list_records` lists the sources that are candidates and pass steps 2, 3 and 5 on their own.
  It shows what a reader accepts without a read: a record nested 64 deep, a noncharacter, an overlay with a
  complete scope.

## The reads of values

The cases that go past step 5 read a value. Each compares every member a result can hold (`status`, `reasons`,
`value`, `alternative_values`, `unit`, `conditions`, `specimen`, `statistics`, `provenance`, `labels`,
`assumption`), so a member it does not expect must be absent, and compares numbers `exact`. A read refused
before step 12 expects `labels` empty: the field's label is added at step 12, and `hash_not_checked` is
compared only where a case claims `hash`.
- **Two base reads recur.** `water_fixture.json` under the default request (310.15 K, tolerance 1 K) reads
  `unknown`, its shear rate unstated, with the value. `water_shear_stated.json`, the same record with its
  shear rate stated as [10, 1000] 1/s, read with an operating shear rate of 100 1/s and a tolerance of 0,
  reads `met`. Most arms are one of them with one thing changed, so the reason or member that differs shows
  the rule.
- **Boundaries are exact.** Each arm at a tolerance's edge was checked with exact rationals, not decimals or
  floating point. PR-335's arms are those where floating point as written and the exact comparison disagree,
  at least one for each row of section 5, with and without a stated ±, and `decimal_310_15`, where the two
  agree and the decimals written are not the doubles read.
- **Each side fails somewhere.** Every row of section 5, with and without a stated ±, has an arm that fails on
  its lower side and one that fails on its upper side, so a reader that checks one inequality is refused.
- **They wait for their code.** `tests/spec_sync/case_steps.json` names the implementation step that first
  runs each; until it is done the tests report the file as not yet runnable, never as passed.

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
| `water_shear_stated.json` | the water record with its shear rate stated: the base of the reads that are `met` |
| `magnet_fixture.json` | `conformance/magnet_fixture`: `magnetic.remanence` 1.2 T at 293.15 K on a cylinder, by `hysteresigraph`, and `magnetic.volume_susceptibility` 0.0005 with the linear label |
| `grade_density_*` | `conformance/polymer_grade_fixture`: `bulk.density` as an interval, specification limits [1150, 1250] kg/m3 with `lot` not applicable, and the same beside a lot's constant (`grade_density_limits_and_lot.json`) |
| `composition_*` | `conformance/composition_fixture`: `bulk.elemental_composition`, a partial mass-fraction composition, and its faults |
| `evidence_fixture.json`, `evidence_*` | `conformance/evidence_fixture`: `biocompatibility.evidence`, two reports, and its faults |
| `mixture_*` | `conformance/mixture_fixture`: a derived viscosity whose derivation names the water and glycerol records |
| `form_*` | `conformance/form_fixture`: a well-formed form on a field whose row does not allow it |

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
| `water_*`, read to the value | the water record with one change a read of the value checks: units (`water_field_unit_*`, `water_condition_unit_*`), tokens (`water_token_*`, `water_form_*`), statistics (`water_statistics_*`), status objects (`water_status_*`, `water_temperature_*`), reviews (`water_review_*`), a ± (`water_plus_minus_*`), conditions (`water_shear_*`, `water_tube_*`, `water_gap_*`, `water_condition_*`), specimen facts (`water_fact_*`, and for implied conditions `water_in_vivo*`, `water_ex_vivo*`), alternatives (`water_alternatives_*`, `water_two_constant_alternatives.json`), near-typos (`water_near_typo_*`), `null` in a value field's member (`water_plus_minus_null.json` and the like), unknown members (`water_unknown_*`) |
| `glycerol_*`, `magnet_test_method_absent.json` | the density and the remanence with one such change |

## What the cases cannot show

- **A tolerance on a token condition, on its own** (PR-330). Such a tolerance always also lacks an operating
  condition, which gives the same reason with the same condition. So a reader that ignored the rule would
  pass. The rule is kept because it states why such an entry is refused. The arms with it are right but cannot
  fail on that rule alone.
- **PR-006's set-aside arms.** A document set aside at step 1 and a source that is simply not the target give
  the same answer. PR-328 holds the arms where setting aside changes the answer.
- **Answers the text leaves open.** No arm meets them; each waits for the text:
  - an alternative's own reasons beside `no_pick`, which `read_side_contract.md` section 3, step 7 leaves
    unspecified. So every `no_pick` arm uses alternatives whose conditions are all met, none is set aside, and
    no arm shows that an entry's `alternative` counts the stored alternatives rather than the remaining ones;
  - whether an alternative refused at step 8 or 9, which stays because alternatives are set aside for their
    conditions only, turns `no_pick` into `not_met`;
  - whether a member the reader does not know is left out (`read_side_contract.md` section 2 item 5) inside a
    review returned as found, and inside an evidence entry's `provenance`, returned whole: no fixture holds
    one there;
  - whether `provenance.md` section 2 item 6 reads the `review` inside an evidence entry's `provenance`, which
    is returned whole: every evidence fixture's entry review is a status object holding `not_checked`, where
    both readings agree.
- **Acceptances located at a region.** Regions belong to the scene suite. An acceptance located at an
  `interval` is checked and not applied (`PR-316.implied_at_interval`, `PR-338.nominal_at_interval`).
- **Tables, overlays and picks:** later steps, with their cases.
