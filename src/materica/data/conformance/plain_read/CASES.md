# Plain-read cases: what each case file tests

One row per file in `cases/`, grouped by case id; each heading quotes the case's row in the
specification, which holds where the two differ. **Ends at** is the step of
`docs/specification/read_side_contract.md` section 3 at which the read ends (0 is the request's own
check); `listing` is a `list_records` operation. **Expected** is read from the case file: status,
reasons (with their condition), and the listing, value, labels or claims where the case states them.
See `README.md` beside this file for how to read a case.


## PR-001

`record_format.md`: a record in another serialisation is not read as a record

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `cbor` | the target's record supplied only as CBOR (same content, same stated hash) | 1 | not_met; `malformed` |
| `listing_yaml_not_listed` | a YAML serialisation beside a JSON record is not listed | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `toml` | the target's record supplied only as TOML (same content, same stated hash) | 1 | not_met; `malformed` |
| `yaml` | the target's record supplied only as YAML (same content, same stated hash) | 1 | not_met; `malformed` |

## PR-002

`record_format.md`: each of these, in the record a read's target names, gives `malformed`, never a crash: invalid JSON; a trailing comma; UTF-16 and UTF-32 text; an overlong form (`C0 80`); an encoded surrogate (`ED A0 80`); a byte-order mark before valid JSON; a member name repeated after unescaping (`{"a":1,"\u0061":2}`); `NaN`; `Infinity`; an unpaired surrogate escape; `1.7976931348623159e308`; nesting 65 deep, and 100000 deep without a crash; an envelope member missing or of the wrong JSON type; a `content_hash` that is not `sha256:` and 64 lowercase hexadecimal digits; a record `version` off the pattern (`"1.0"`, the target naming that same string); a known section whose `fields` is an array; and, when a read applies it (`read_side_contract.md` section 3, step 6), an overlay whose `base` has no `content_hash`. A record with nesting 64 deep, an escaped U+0000 or a noncharacter is read

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `body_not_object` | target's record with `body` an array | 3 | not_met; `malformed` |
| `bom` | target's record: EF BB BF before the record | 1 | not_met; `malformed` |
| `card_not_string` | target's record with `card` a number | 3 | not_met; `malformed` |
| `comment` | target's record: a // comment after the opening brace | 1 | not_met; `malformed` |
| `content_hash_63_digits` | target's record whose stated content_hash has 63 digits; the target pins the well-formed hash | 1 | not_met; `malformed` |
| `content_hash_no_prefix` | target's record whose stated content_hash has no `sha256:` prefix; the target pins the well-formed hash | 1 | not_met; `malformed` |
| `content_hash_not_string` | target's record with `content_hash` a number | 1 | not_met; `malformed` |
| `content_hash_trailing_newline` | target's record whose stated content_hash has a trailing newline; the target pins the well-formed hash | 1 | not_met; `malformed` |
| `content_hash_uppercase` | target's record whose stated content_hash has uppercase hexadecimal digits; the target pins the well-formed hash | 1 | not_met; `malformed` |
| `content_hash_uppercase_pinned_as_stated` | target's record with an uppercase content_hash, pinned by that same string: found at step 1, refused by the reader schema | 3 | not_met; `malformed` |
| `duplicate_member` | target's record: name repeated, same value | 1 | not_met; `malformed` |
| `duplicate_member_escaped` | target's record: name repeated as "n\u0061me", same value | 1 | not_met; `malformed` |
| `encoded_surrogate` | target's record: ED A0 80 inside the card string | 1 | not_met; `malformed` |
| `extensions_not_object` | target's record with `extensions` an array | 3 | not_met; `malformed` |
| `fields_array` | target's record with the known section fluid's `fields` an array | 3 | not_met; `malformed` |
| `id_namespace_uppercase` | target's record with `id` "Conformance/water_fixture", the target naming the same | 3 | not_met; `malformed` |
| `id_not_string` | target's record with `id` a number | 1 | not_met; `malformed` |
| `id_without_namespace` | target's record with `id` "water_fixture", the target naming the same | 3 | not_met; `malformed` |
| `infinity` | target's record: the viscosity value Infinity | 1 | not_met; `malformed` |
| `invalid_json` | target's record: the final closing brace removed | 1 | not_met; `malformed` |
| `known_section_fields_missing` | target's record with the known section fluid without `fields` | 3 | not_met; `malformed` |
| `known_section_not_object` | target's record with the known section fluid a number | 3 | not_met; `malformed` |
| `licence_evidence_missing` | target's record whose licence lacks `evidence` | 3 | not_met; `malformed` |
| `licence_evidence_not_string` | target's record whose licence `evidence` is `false` | 3 | not_met; `malformed` |
| `licence_not_object` | target's record with `licence` a string | 3 | not_met; `malformed` |
| `licence_values_missing` | target's record whose licence lacks `values` | 3 | not_met; `malformed` |
| `local_id_empty` | target's record with `id` "conformance/" (an empty local id), the target naming the same | 3 | not_met; `malformed` |
| `local_id_trailing_newline` | target's record with `id` "conformance/water_fixture\n" (a trailing newline), the target naming the same | 3 | not_met; `malformed` |
| `local_id_with_space` | target's record with `id` "conformance/water fixture" (a space in the local id), the target naming the same | 3 | not_met; `malformed` |
| `missing_body` | target's record without `body` | 3 | not_met; `malformed` |
| `missing_content_hash` | target's record without `content_hash` (the target pins water's hash) | 1 | not_met; `malformed` |
| `missing_id` | target's record without `id` | 1 | not_met; `malformed` |
| `missing_licence` | target's record without `licence` | 3 | not_met; `malformed` |
| `missing_name` | target's record without `name` | 3 | not_met; `malformed` |
| `missing_record_type` | target's record without `record_type` | 3 | not_met; `malformed` |
| `missing_version` | target's record without `version` | 1 | not_met; `malformed` |
| `name_not_string` | target's record with `name` an array | 3 | not_met; `malformed` |
| `nan` | target's record: the viscosity value NaN | 1 | not_met; `malformed` |
| `negative_infinity` | target's record: the viscosity value -Infinity | 1 | not_met; `malformed` |
| `nesting_100000` | target's record nested 100000 deep: malformed, without a crash | 1 | not_met; `malformed` |
| `nesting_65` | target's record nested 65 deep (in an unknown top-level member) | 1 | not_met; `malformed` |
| `number_overflow` | target's record: the viscosity value 1.7976931348623159e308 | 1 | not_met; `malformed` |
| `number_overflow_exponent` | target's record: the viscosity value 1e400 | 1 | not_met; `malformed` |
| `overlay_base_content_hash_missing` | target's record is the overlay with `base` without `content_hash`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_content_hash_not_string` | target's record is the overlay with `base.content_hash` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_id_missing` | target's record is the overlay with `base` without `id`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_id_not_string` | target's record is the overlay with `base.id` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_missing` | target's record is the overlay with no `base`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_not_object` | target's record is the overlay with `base` a string: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_version_missing` | target's record is the overlay with `base` without `version`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_version_not_string` | target's record is the overlay with `base.version` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_purpose_missing` | target's record is the overlay with no `purpose`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_purpose_not_string` | target's record is the overlay with `purpose` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_replaces_missing` | target's record is the overlay with no `replaces`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_replaces_not_object` | target's record is the overlay with `replaces` an array: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_consumer_missing` | target's record is the overlay with `scope` without `consumer`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_consumer_not_string` | target's record is the overlay with `scope.consumer` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_missing` | target's record is the overlay with no `scope`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_configuration_hash_not_string` | target's record is the overlay with purpose `fit` and `scope.model_configuration_hash` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_empty` | target's record is the overlay with purpose `fit` and `scope.model` an empty object (both missing: one `malformed`): its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_name_missing` | target's record is the overlay with purpose `fit` and `scope.model` without `name`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_name_not_string` | target's record is the overlay with purpose `fit` and `scope.model.name` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_not_object` | target's record is the overlay with purpose `fit` and `scope.model` a string: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_version_missing` | target's record is the overlay with purpose `fit` and `scope.model` without `version`: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_version_not_string` | target's record is the overlay with purpose `fit` and `scope.model.version` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_not_object` | target's record is the overlay with `scope` a string: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_run_not_string` | target's record is the overlay with purpose `fit` and `scope.run` a number: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlong` | target's record: C0 80 inside the card string | 1 | not_met; `malformed` |
| `read_escaped_nul` | a record whose name holds an escaped U+0000 is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `read_nesting_64` | a record nested exactly 64 deep is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `read_noncharacter` | a record whose name holds U+FFFE, raw, is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `read_noncharacter_escaped` | a record whose name holds the escape \ufdd0 is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `record_type_not_string` | target's record with `record_type` a number | 3 | not_met; `malformed` |
| `sections_missing` | target's record with a material body without `sections` | 3 | not_met; `malformed` |
| `sections_not_object` | target's record with `sections` an array | 3 | not_met; `malformed` |
| `trailing_comma` | target's record: a trailing comma inside licence | 1 | not_met; `malformed` |
| `trailing_content` | target's record: a second JSON value after the record | 1 | not_met; `malformed` |
| `truncated_utf8` | target's record: E2 82 (a truncated three-byte sequence) inside the card string | 1 | not_met; `malformed` |
| `unescaped_control_character` | target's record: a raw TAB inside the card string | 1 | not_met; `malformed` |
| `unpaired_low_surrogate_escape` | target's record: \udc00 alone inside the card string | 1 | not_met; `malformed` |
| `unpaired_surrogate_escape` | target's record: \ud800 alone inside the card string | 1 | not_met; `malformed` |
| `utf16be` | target's record: UTF-16BE, no BOM | 1 | not_met; `malformed` |
| `utf16le` | target's record: UTF-16LE, no BOM | 1 | not_met; `malformed` |
| `utf16le_bom` | target's record: UTF-16LE with its BOM | 1 | not_met; `malformed` |
| `utf32be` | target's record: UTF-32BE, no BOM | 1 | not_met; `malformed` |
| `utf32le` | target's record: UTF-32LE, no BOM | 1 | not_met; `malformed` |
| `version_leading_zero` | target's record with `version` "01.0.0", the target naming the same | 3 | not_met; `malformed` |
| `version_not_string` | target's record with `version` a number | 1 | not_met; `malformed` |
| `version_off_pattern` | target's record with `version` "1.0", the target naming "1.0" | 3 | not_met; `malformed` |

## PR-004

`record_format.md`: every record type carries the envelope

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `interface_missing_licence` | target's record of type 'interface' without `licence` (refused before step 5's type check) | 3 | not_met; `malformed` |
| `interface_missing_name` | target's record of type 'interface' without `name` (refused before step 5's type check) | 3 | not_met; `malformed` |
| `material_and_overlay_listed` | a material and an overlay are both listed | listing | met; lists `conformance/water_fixture` 1.0.0, `conformance/water_overlay_fixture` 1.0.0 |
| `material_listed` | a material record with the full envelope is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `namespaced_type_missing_name` | target's record of type 'conformance:sample_batch' without `name` (refused before step 5's type check) | 3 | not_met; `malformed` |
| `overlay_licence_evidence_not_string` | target's overlay record whose licence `evidence` is a number | 3 | not_met; `malformed` |
| `overlay_listed` | an overlay record with the full envelope is listed | listing | met; lists `conformance/water_overlay_fixture` 1.0.0 |
| `overlay_missing_body` | target's record of type 'overlay' without `body` | 3 | not_met; `malformed` |
| `overlay_missing_licence` | target's record of type 'overlay' without `licence` | 3 | not_met; `malformed` |
| `overlay_missing_name` | target's record of type 'overlay' without `name` | 3 | not_met; `malformed` |
| `overlay_missing_name_not_listed` | an overlay without `name` fails step 3 and is not listed; the good material beside it is | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `overlay_missing_record_type` | target's record of type 'overlay' without `record_type` | 3 | not_met; `malformed` |
| `overlay_missing_schema_version` | target's record of type 'overlay' without `schema_version` | 2 | not_met; `malformed` |
| `overlay_scope_model_complete_listed` | control: a `fit` overlay whose `scope.model` has a string `name` and `version` (and a member no document defines), with a string `model_configuration_hash`, passes step 3 and is listed | listing | met; lists `conformance/water_overlay_fixture` 1.0.0 |
| `unknown_type_missing_body` | target's record of type 'sample_batch' without `body` (refused before step 5's type check) | 3 | not_met; `malformed` |

## PR-006

`record_format.md`: an unknown record type is skipped when listing; so is an object with `document_type` and no `record_type`

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `all_sources` | material, overlay, interface, unknown, namespaced, scene manifest and crosswalk together: the material and overlay records are listed | listing | met; lists `conformance/water_fixture` 1.0.0, `conformance/glycerol_fixture` 1.0.0, `conformance/water_overlay_fixture` 1.0.0 |
| `array_source_not_listed` | an array holding the water record is no candidate and is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `document_type_without_record_type_skipped` | an object with document_type, no record_type, and an otherwise complete water envelope is not listed; cannot fail: such an object fails step 2 or 3, or is no candidate, even if not set aside (PR-328 holds the arms that can) (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `engine_crosswalk_skipped` | an engine crosswalk, with a string id and version, is not listed; cannot fail: such an object fails step 2 or 3, or is no candidate, even if not set aside (PR-328 holds the arms that can) (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `id_only_object_not_listed` | an object with only an `id` is no candidate and is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `interface_skipped` | an `interface` record is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `namespaced_type_skipped` | a record of a namespaced type is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `number_source_not_listed` | a number is no candidate and is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `record_with_document_type_member_listed` | an object with both record_type and document_type is a record: listed | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `scene_manifest_skipped` | a scene manifest is not listed; cannot fail: such an object fails step 2 or 3, or is no candidate, even if not set aside (PR-328 holds the arms that can) (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |
| `unknown_type_skipped` | a record of an unknown type is not listed (beside glycerol, which is) | listing | met; lists `conformance/glycerol_fixture` 1.0.0 |

## PR-007

`record_format.md`: a referenced record of an unknown type is refused (`unknown_type`)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `interface` | target's record has record_type `interface`: unknown_type | 5 | not_met; `unknown_type` |
| `interface_other_version` | an interface record of schema 0.2.0: other_version at step 2, before the type check | 2 | not_met; `other_version` |
| `interface_pin_mismatch` | an interface record whose stated hash differs from the pin: pin_mismatch at step 1, before the type check | 1 | not_met; `pin_mismatch` |
| `namespaced_type` | target's record has record_type "conformance:sample_batch": unknown_type | 5 | not_met; `unknown_type` |
| `record_type_capitalised` | target's record has record_type "Material" (not `material`): unknown_type | 5 | not_met; `unknown_type` |
| `unknown_type` | target's record has record_type "sample_batch": unknown_type | 5 | not_met; `unknown_type` |

## PR-026

`record_format.md`: before 1.0.0, a record of another minor version is refused (`other_version`)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `minor_0_0_1` | target's record of schema "0.0.1" | 2 | not_met; `other_version` |
| `minor_0_10_0` | target's record of schema "0.10.0" (minor 10, not 1) | 2 | not_met; `other_version` |
| `minor_0_2_0` | target's record of schema "0.2.0" | 2 | not_met; `other_version` |
| `minor_0_2_0_not_listed` | a record of schema 0.2.0 is not listed | listing | met; lists nothing |

## PR-027

`record_format.md`: a record of another major version is refused (`other_version`)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `major_1_0_0` | target's record of schema "1.0.0" | 2 | not_met; `other_version` |
| `major_1_1_0` | target's record of schema "1.1.0" | 2 | not_met; `other_version` |
| `major_2_0_0` | target's record of schema "2.0.0" | 2 | not_met; `other_version` |

## PR-048

`record_format.md`: a record whose `schema_version` is absent, not a string, or does not match the pattern (`"0.1"`, `"0.1.0-rc1"`, `"00.1.0"`, `"0.1.0 "`, `"0.1.0\n"`, Arabic-Indic digits) is malformed; a major or minor component of a hundred digits gives `other_version`, not a crash; `0.1.7` is read by a 0.1 reader

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `absent` | target's record with no `schema_version`: malformed | 2 | not_met; `malformed` |
| `arabic_indic_digits` | target's record with "٠.١.٠" (U+0660, U+0661, U+0660): malformed | 2 | not_met; `malformed` |
| `leading_zero_major` | target's record with "00.1.0": malformed | 2 | not_met; `malformed` |
| `leading_zero_minor` | target's record with "0.01.0": malformed | 2 | not_met; `malformed` |
| `major_100_digits` | target's record whose major component has 100 digits (a multiple of 2^64): other_version, no crash | 2 | not_met; `other_version` |
| `minor_100_digits` | target's record whose minor component has 100 digits (1 modulo 2^64): other_version, no crash | 2 | not_met; `other_version` |
| `not_string_array` | target's record with `schema_version` ["0.1.0"]: malformed | 2 | not_met; `malformed` |
| `not_string_null` | target's record with `schema_version` null: malformed | 2 | not_met; `malformed` |
| `not_string_number` | target's record with `schema_version` the number 0.1: malformed | 2 | not_met; `malformed` |
| `other_version_before_envelope` | target's record of schema 0.2.0 that also lacks `name`: other_version at step 2, not malformed | 2 | not_met; `other_version` |
| `patch_0_1_7_listed` | a record of schema 0.1.7 is listed by a 0.1 reader | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `patch_100_digits_listed` | a record of schema 0.1.<100-digit patch> is listed (any patch is read) | listing | met; lists `conformance/water_fixture` 1.0.0 |
| `pre_release` | target's record with "0.1.0-rc1": malformed | 2 | not_met; `malformed` |
| `trailing_newline` | target's record with "0.1.0\n": malformed | 2 | not_met; `malformed` |
| `trailing_space` | target's record with "0.1.0 ": malformed | 2 | not_met; `malformed` |
| `two_components` | target's record with "0.1": malformed | 2 | not_met; `malformed` |

## PR-049

`record_format.md`: `null` in the envelope (`"card": null`) makes the record malformed; inside a value field (`"unit": null`) it refuses that field (`form_invalid`); inside a member the reader does not know, at the top level or inside a value field, it is ignored; in a member step 8 does not check (`"extraction": null`), it does not refuse the field

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `body_null` | target's record with "body": null in the envelope or body structure | 3 | not_met; `malformed` |
| `card_null` | target's record with "card": null in the envelope or body structure | 3 | not_met; `malformed` |
| `extensions_null` | target's record with "extensions": null in the envelope or body structure | 3 | not_met; `malformed` |
| `fields_null` | target's record with fluid "fields": null in the envelope or body structure | 3 | not_met; `malformed` |
| `known_section_null` | target's record with the known section "fluid": null in the envelope or body structure | 3 | not_met; `malformed` |
| `licence_evidence_null` | target's record with licence "evidence": null | 3 | not_met; `malformed` |
| `licence_null` | target's record with "licence": null in the envelope or body structure | 3 | not_met; `malformed` |
| `licence_values_null` | target's record with licence "values": null in the envelope or body structure | 3 | not_met; `malformed` |
| `name_null` | target's record with "name": null in the envelope or body structure | 3 | not_met; `malformed` |
| `overlay_base_content_hash_null` | target's record is the overlay with `base.content_hash`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_id_null` | target's record is the overlay with `base.id`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_null` | target's record is the overlay with `base`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_base_version_null` | target's record is the overlay with `base.version`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_purpose_null` | target's record is the overlay with `purpose`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_replaces_null` | target's record is the overlay with `replaces`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_consumer_null` | target's record is the overlay with `scope.consumer`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_configuration_hash_null` | target's record is the overlay with purpose `fit` and `scope.model_configuration_hash`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_model_null` | target's record is the overlay with purpose `fit` and `scope.model`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_null` | target's record is the overlay with `scope`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `overlay_scope_run_null` | target's record is the overlay with purpose `fit` and `scope.run`: null: its body structure is refused (step 3) | 3 | not_met; `malformed` |
| `record_type_null` | target's record with "record_type": null in the envelope or body structure | 3 | not_met; `malformed` |
| `sections_null` | target's record with "sections": null in the envelope or body structure | 3 | not_met; `malformed` |
| `unknown_top_level_member_null_listed` | a record holding null in a top-level member the reader does not know passes step 3 and is listed | listing | met; lists `conformance/water_fixture` 1.0.0 |

## PR-300

`read_side_contract.md`: no read raises; every read returns a result

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `no_records` | no records supplied at all: a result (absent), no error | 1 | not_met; `absent` |
| `record_binary_bytes` | the only source is binary bytes: a result (malformed), no error | 1 | not_met; `malformed` |
| `record_empty_file` | the only source is an empty file: a result (malformed), no error | 1 | not_met; `malformed` |
| `request_empty_file` | the request file is empty: a result (request_incomplete), no error | 0 | not_met; `request_incomplete` |
| `request_nesting_100000` | a request nested 100000 deep: a result (request_incomplete), no error | 0 | not_met; `request_incomplete` |

## PR-301

`read_side_contract.md`: every reason is reported; the status is the worst; each step makes all its checks

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `hash_and_pin_mismatch_hs` | a reader with HS: an interface record edited after pinning gives both `hash_mismatch` and one `pin_mismatch` at step 4 (so never reaches the type check) | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `hash_and_pin_mismatch_no_hs` | the same read for a reader without HS: the stated hash equals the pin, nothing is recomputed, the read reaches step 5 (`unknown_type`) labelled `hash_not_checked` | 5 | not_met; `unknown_type`; labels `hash_not_checked`; claims `hash: false` |
| `incomplete_and_unit_mismatch` | field off the pattern and temperature in Cel: both reported | 0 | not_met; `request_incomplete`, `request_unit_mismatch (temperature)` |
| `step0_ends_read` | a request fault ends the read at step 0: the unparseable record is never reported | 0 | not_met; `request_incomplete` |
| `step1_ends_read` | a record that is of schema 0.2.0 and has a bad licence, pinned by another hash: only pin_mismatch | 1 | not_met; `pin_mismatch` |
| `step2_ends_read` | the same record pinned by its own hash: only other_version (step 2), not malformed | 2 | not_met; `other_version` |
| `three_codes_step0` | want coverage without the suite, a negative tolerance, shear_rate in 1/min: all three reported | 0 | not_met; `want_mismatch`, `request_incomplete (temperature)`, `request_unit_mismatch (shear_rate)`; claims `fits_and_reference_data: false` |
| `three_codes_step0_with_fd` | as `three_codes_step0`, the suite claimed: no want_mismatch, the other two reported | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (shear_rate)`; claims `fits_and_reference_data: true` |
| `want_suite_and_incomplete` | want fit without the suite, and field off the pattern: both reported | 0 | not_met; `want_mismatch`, `request_incomplete`; claims `fits_and_reference_data: false` |
| `want_suite_and_incomplete_with_fd` | as `want_suite_and_incomplete`, the suite claimed: want fit passes, the field still fails | 0 | not_met; `request_incomplete`; claims `fits_and_reference_data: true` |

## PR-308

`read_side_contract.md`: no `want`, a tolerance with no operating condition (both at step 0), or no operating value for an axis (at step 11): `request_incomplete`, which at step 11 ends the read even where it arises in one alternative

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `no_want` | requirement without `want` | 0 | not_met; `request_incomplete` |
| `tolerance_with_other_operating_condition` | a temperature tolerance, operating conditions giving only shear_rate | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_without_operating_conditions` | a temperature tolerance and no operating_conditions member | 0 | not_met; `request_incomplete (temperature)` |

## PR-310

`read_side_contract.md`: every reason code a read gives is one of the table's; a read applies no acceptance the request does not carry, and a `waiver` in a request gives `request_incomplete`

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `absent` | the code `absent` is spelled as the reason table gives it | 1 | not_met; `absent` |
| `hash_mismatch` | a reader with HS: a record edited after pinning, its stated hash still the pin: `hash_mismatch` and one `pin_mismatch`, spelled as the table gives them | 4 | not_met; `hash_mismatch`, `pin_mismatch`; claims `hash: true` |
| `malformed` | the code `malformed` is spelled as the reason table gives it | 1 | not_met; `malformed` |
| `other_version` | the code `other_version` is spelled as the reason table gives it | 2 | not_met; `other_version` |
| `pin_mismatch` | the code `pin_mismatch` is spelled as the reason table gives it | 1 | not_met; `pin_mismatch` |
| `request_incomplete` | the code `request_incomplete` is spelled as the reason table gives it | 0 | not_met; `request_incomplete` |
| `request_unit_mismatch` | the code `request_unit_mismatch` is spelled as the reason table gives it | 0 | not_met; `request_unit_mismatch (temperature)` |
| `unknown_type` | the code `unknown_type` is spelled as the reason table gives it | 5 | not_met; `unknown_type` |
| `want_mismatch` | the code `want_mismatch` is spelled as the reason table gives it | 0 | not_met; `want_mismatch`; claims `fits_and_reference_data: false` |

## PR-320

`read_side_contract.md`: an operating condition or tolerance of a numeric condition with a string unit other than the registered one is refused (`request_unit_mismatch`, with that `condition`), whatever else is wrong with the entry; units are compared code point for code point (`Cel`, `k`, `K` with U+212A); an operating condition's or tolerance's unit that is not a string gives only `request_incomplete`; a unit on a token or unregistered condition is compared with nothing, and the entry gives `request_incomplete` only where its own shape is wrong or its condition is not registered; a value an implied condition supplies in another unit is refused alike

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `accept_entry_with_unit_accepted` | control: density_kind requirement {"accept": ["apparent"], "unit": "K"}: the `unit` member, which the accept shape does not name, is ignored and, on a token condition, compared with nothing, so step 0 gives no reason; the reference has no candidate (water 2.0.0 not supplied): `absent` | 1 | not_met; `absent` |
| `operating_range_lo_above_hi_wrong_unit` | operating shear_rate range [30000, 3000], unit 1/min: both `request_incomplete` and `request_unit_mismatch` for shear_rate | 0 | not_met; `request_incomplete (shear_rate)`, `request_unit_mismatch (shear_rate)` |
| `operating_range_per_minute` | operating shear_rate range in 1/min (registered 1/s) | 0 | not_met; `request_unit_mismatch (shear_rate)` |
| `operating_range_three_numbers_wrong_unit` | operating shear_rate range of three numbers, unit 1/min: both `request_incomplete` and `request_unit_mismatch` for shear_rate | 0 | not_met; `request_incomplete (shear_rate)`, `request_unit_mismatch (shear_rate)` |
| `operating_token_condition_with_unit` | an operating condition {"value": 1, "unit": "K"} for the token condition density_kind, otherwise well shaped: `request_incomplete` only (the unit is compared with nothing) | 0 | not_met; `request_incomplete (density_kind)` |
| `operating_unit_array` | operating temperature whose `unit` is the array ["K"]: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `operating_unit_escaped_k_accepted` | control: the operating temperature's unit written as the escape \u004B, which is "K": no unit reason; the reference has no candidate (water 2.0.0 not supplied): `absent` | 1 | not_met; `absent` |
| `operating_unit_kelvin_sign` | operating temperature in U+212A KELVIN SIGN, written raw (bytes E2 84 AA): `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (temperature)` |
| `operating_unit_kelvin_sign_escaped` | operating temperature in U+212A KELVIN SIGN, written as the escape \u212A: `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (temperature)` |
| `operating_unit_lowercase_k` | operating temperature in "k" (registered "K"): `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (temperature)` |
| `operating_unit_null` | operating temperature whose `unit` is null: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `operating_unit_number` | operating temperature whose `unit` is the number 1.0: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `operating_unit_per_s` | operating shear_rate in "/s" (registered "1/s"): `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (shear_rate)` |
| `operating_unit_s_minus_1` | operating shear_rate in "s-1" (registered "1/s"): `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (shear_rate)` |
| `operating_unit_trailing_space` | operating temperature in "K " (a trailing space): `request_unit_mismatch`, units compared code point for code point | 0 | not_met; `request_unit_mismatch (temperature)` |
| `operating_unregistered_condition_with_unit` | an operating condition {"value": 100000, "unit": "Pa"} for the unregistered condition pressure: `request_incomplete` only (the unit is compared with nothing) | 0 | not_met; `request_incomplete (pressure)` |
| `operating_value_and_range_wrong_unit` | operating temperature with both value and range, unit Cel: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `operating_value_cel` | operating temperature in Cel (registered K) | 0 | not_met; `request_unit_mismatch (temperature)` |
| `operating_value_missing_wrong_unit` | operating temperature with neither value nor range, unit Cel: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `operating_value_not_number_wrong_unit` | operating temperature value the string "37.0", unit Cel: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `operating_without_tolerance_cel` | operating temperature in Cel, no requirement conditions | 0 | not_met; `request_unit_mismatch (temperature)` |
| `specimen_size_mm` | operating specimen_size in mm (registered m) | 0 | not_met; `request_unit_mismatch (specimen_size)` |
| `tolerance_and_accept_wrong_unit` | temperature requirement with both a tolerance in Cel and an accept list: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `tolerance_below_zero_wrong_unit` | temperature tolerance -1.0, unit Cel: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `tolerance_cel` | temperature tolerance in Cel (registered K) | 0 | not_met; `request_unit_mismatch (temperature)` |
| `tolerance_for_token_condition_with_unit` | a tolerance {"value": 0, "unit": "1"} for the token condition density_kind: `request_incomplete` only (the unit is compared with nothing) | 0 | not_met; `request_incomplete (density_kind)` |
| `tolerance_unit_array` | temperature tolerance whose `unit` is the array ["K"]: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_unit_escaped_k_accepted` | control: the temperature tolerance's unit written as the escape \u004B, which is "K": no unit reason; the reference has no candidate (water 2.0.0 not supplied): `absent` | 1 | not_met; `absent` |
| `tolerance_unit_kelvin_sign` | temperature tolerance in U+212A KELVIN SIGN, written raw: `request_unit_mismatch` | 0 | not_met; `request_unit_mismatch (temperature)` |
| `tolerance_unit_null` | temperature tolerance whose `unit` is null: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_unit_number` | temperature tolerance whose `unit` is the number 1.0: `request_incomplete` only, no `request_unit_mismatch` | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_unregistered_condition_with_unit` | a tolerance {"value": 1000, "unit": "Pa"} for the unregistered condition pressure: `request_incomplete` only (the unit is compared with nothing) | 0 | not_met; `request_incomplete (pressure)` |
| `tolerance_value_not_number_wrong_unit` | temperature tolerance value the string "1.0", unit Cel: both `request_incomplete` and `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `tolerance_without_operating_condition_wrong_unit` | a shear_rate tolerance of 60 in 1/min and no shear_rate operating condition: both `request_incomplete` and `request_unit_mismatch` for shear_rate | 0 | not_met; `request_incomplete (shear_rate)`, `request_unit_mismatch (shear_rate)` |

## PR-327

`read_side_contract.md`: a reader without HS labels `hash_not_checked` the results that reach step 4, and still refuses, at step 1 and without that label, a stated hash that differs from a pin

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `label_hs` | a reader with HS: the same read, hash verified, no hash_not_checked | 5 | not_met; `unknown_type`; labels none; claims `hash: true` |
| `label_no_hs` | a reader without HS: a read refused at step 5 (unknown_type) reached step 4, so hash_not_checked | 5 | not_met; `unknown_type`; labels `hash_not_checked`; claims `hash: false` |
| `pin` | stated hash differs from the pin: pin_mismatch at step 1, no labels | 1 | not_met; `pin_mismatch`; labels none |
| `pin_no_hs` | as `pin`, for a reader without HS: the result ends at step 1, so no hash_not_checked | 1 | not_met; `pin_mismatch`; labels none; claims `hash: false` |

## PR-328

`read_side_contract.md`: a reference with no candidate gives `malformed` when a supplied source did not parse, or parsed to a value that is neither a set-aside document nor an object with a string `id` and `version` (an array, an object with only an `id`); otherwise `absent`; a scene manifest or an engine crosswalk among the sources is set aside and never resolved

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `array_source_malformed` | no candidate, and a source parsed to an array (holding the water record) | 1 | not_met; `malformed` |
| `engine_crosswalk_named_absent` | the target names the engine crosswalk by its id, version and RFC 8785 SHA-256: set aside, absent | 1 | not_met; `absent` |
| `id_only_object_malformed` | no candidate, and a source parsed to an object with only an id | 1 | not_met; `malformed` |
| `ill_formed_hash_other_version_absent` | the only source is water 1.0.0 with an uppercase content_hash; the target names water 2.0.0: no candidate of the reference's id and version, and no source unreadable, so `absent` | 1 | not_met; `absent` |
| `no_candidate_absent` | no supplied record has the reference's id and version; every source parsed | 1 | not_met; `absent` |
| `number_source_malformed` | no candidate, and a source parsed to a number | 1 | not_met; `malformed` |
| `other_version_of_id_absent` | water 1.0.0 supplied, water 2.0.0 referenced | 1 | not_met; `absent` |
| `other_version_supplied_absent` | water 2.0.0 supplied, water 1.0.0 referenced | 1 | not_met; `absent` |
| `scene_manifest_absent` | no candidate; the scene manifest is set aside, so absent, not malformed | 1 | not_met; `absent` |
| `set_aside_and_unparsed_malformed` | no candidate; a scene manifest set aside and a source that did not parse | 1 | not_met; `malformed` |
| `string_source_malformed` | no candidate, and a source parsed to a string | 1 | not_met; `malformed` |
| `unparsed_source_malformed` | no candidate, and a supplied source did not parse | 1 | not_met; `malformed` |
| `unrelated_malformed_candidate_absent` | the only source is a candidate for another id (and would fail step 3): absent | 1 | not_met; `absent` |
| `version_not_string_source_malformed` | no candidate, and a source parsed to an object whose version is a number | 1 | not_met; `malformed` |

## PR-329

`read_side_contract.md`: candidates of one `id` and `version`: the one with the reference's hash is read, and identical copies are read once; none with the hash gives `pin_mismatch`, whether there is one candidate or several, unless one has an absent, `null` or ill-formed `content_hash`, or a supplied source is unreadable, which gives `malformed`; two with the hash whose bytes differ give `malformed`

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `hash_selects_other_version_copy` | two candidates of water 1.0.0; the pin selects the schema 0.2.0 one, refused at step 2 | 2 | not_met; `other_version` |
| `hash_selects_unknown_type_copy` | two candidates of water 1.0.0; the pin selects the interface one, refused at step 5 | 5 | not_met; `unknown_type` |
| `identical_copies_read_once` | two byte-identical copies with the pinned hash are read once: unknown_type, not malformed | 5 | not_met; `unknown_type` |
| `match_beside_ill_formed_copy` | one candidate has the pin, another an ill-formed hash: the match is read (unknown_type at step 5) | 5 | not_met; `unknown_type` |
| `match_beside_ill_formed_hash_other_version` | the one candidate with the pinned hash (an interface record carrying water's id and version 1.0.0) beside water 2.0.0 with an uppercase content_hash: the read goes on, and ends at step 5 (`unknown_type`) | 5 | not_met; `unknown_type` |
| `match_beside_unparsed_source` | the one candidate with the pinned hash (an interface record carrying water's id and version) beside a source that did not parse: the read goes on, and ends at step 5 (`unknown_type`) | 5 | not_met; `unknown_type` |
| `none_with_hash_absent_content_hash` | no candidate has the pin and one has no content_hash | 1 | not_met; `malformed` |
| `none_with_hash_beside_array_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that parsed to an array (holding the water record, with the pinned hash): `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_beside_id_only_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that parsed to an object with only an `id` (water's): `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_beside_ill_formed_hash_other_version` | one candidate of water 1.0.0 with a well-formed stated hash that differs from the pin, beside water 2.0.0 with an uppercase content_hash, which is no candidate of the reference's version: `pin_mismatch` | 1 | not_met; `pin_mismatch` |
| `none_with_hash_beside_malformed_other_candidate` | one candidate with a well-formed stated hash that differs from the pin, beside a candidate for another id that would fail step 3 (an overlay without `name`): a candidate, not unreadable: `pin_mismatch` | 1 | not_met; `pin_mismatch` |
| `none_with_hash_beside_number_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that parsed to a number: `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_beside_scene_manifest` | one candidate with a well-formed stated hash that differs from the pin, beside a scene manifest, which is set aside, not unreadable (it has no `id` or `version`, so a reader that did not set it aside would count it unreadable and give `malformed`): `pin_mismatch` | 1 | not_met; `pin_mismatch` |
| `none_with_hash_beside_string_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that parsed to a string: `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_beside_unparsed_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that did not parse (water's bytes after a byte-order mark): `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_beside_version_not_string_source` | one candidate with a well-formed stated hash that differs from the pin, beside a source that parsed to an object whose `id` is water's and whose `version` is a number: `malformed` | 1 | not_met; `malformed` |
| `none_with_hash_ill_formed_content_hash` | no candidate has the pin and one has an uppercase content_hash | 1 | not_met; `malformed` |
| `none_with_hash_null_content_hash` | no candidate has the pin and one has content_hash null | 1 | not_met; `malformed` |
| `none_with_hash_one_candidate` | one candidate, its well-formed stated hash differs from the pin | 1 | not_met; `pin_mismatch` |
| `none_with_hash_several_candidates` | two candidates, neither stated hash equals the pin | 1 | not_met; `pin_mismatch` |
| `two_with_hash_card_differs` | two candidates state the pinned hash (both correctly) but differ in their card | 1 | not_met; `malformed` |
| `two_with_hash_whitespace_differs` | two candidates state the pinned hash (both correctly) but their bytes differ (formatting) | 1 | not_met; `malformed` |

## PR-330

`read_side_contract.md`: `request_incomplete` for: a request that is not valid JSON, or not an object; a member missing or of the wrong JSON type; a target with neither or both of record and region; a reference without its hash; a field off the pattern (`fluid`, `a.b.c`, `Fluid.x`); a `want` not in section 6; a requirement holding `label`, `represents` or `population_level`; a condition that is not registered; a `range` of three numbers; a tolerance for a token condition (with that `condition`); a tolerance below zero; an operating range with `lo` above `hi`; a field that is not registered (`fluid.surface_tension`, `acoustic.sound_speed`, `fluid.specimen`); an operating condition for a token condition; an acceptance of a kind a read does not take, or one that breaks its shape, whatever field it names; an acceptance naming a field that is not registered; an implied condition whose `fact` takes no tokens or whose `token` is not that fact's, or whose `implies` names a condition that is not registered or gives one a status object, `plus_minus`, `set_or_measured` or a token outside its row; two nominals naming one field; `operating_conditions` that is not an object beside a tolerance, with a second reason carrying the tolerance's `condition`; a tolerance of `-0` is accepted; a member the shape does not name at that place, at any depth, is ignored (a `unit` beside an `accept` list), unless it is one slip from a member named there, refused ones included (`acceptance` beside `target`, for `acceptances`)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `accept_for_numeric_condition` | step 0 refuses: an accept list for the numeric condition temperature | 0 | not_met; `request_incomplete (temperature)` |
| `accept_list_accepted` | control: a well-formed accept list for the token condition density_kind ({"accept": ["apparent"]}) passes step 0; the reference has no candidate (water 2.0.0 not supplied): `absent` | 1 | not_met; `absent` |
| `accept_list_non_string` | step 0 refuses: density_kind accept list holding a number | 0 | not_met; `request_incomplete (density_kind)` |
| `accept_not_list` | step 0 refuses: density_kind accept a string, not a list | 0 | not_met; `request_incomplete (density_kind)` |
| `condition_not_registered` | step 0 refuses: a requirement naming the unregistered condition pressure (an accept list, no unit) | 0 | not_met; `request_incomplete (pressure)` |
| `field_empty_part` | step 0 refuses: field "fluid." | 0 | not_met; `request_incomplete` |
| `field_missing` | step 0 refuses: target without field | 0 | not_met; `request_incomplete` |
| `field_no_dot` | step 0 refuses: field "fluid" | 0 | not_met; `request_incomplete` |
| `field_not_string` | step 0 refuses: field a number | 0 | not_met; `request_incomplete` |
| `field_three_parts` | step 0 refuses: field "a.b.c" | 0 | not_met; `request_incomplete` |
| `field_trailing_newline` | step 0 refuses: field "fluid.dynamic_viscosity\n" | 0 | not_met; `request_incomplete` |
| `field_uppercase` | step 0 refuses: field "Fluid.x" | 0 | not_met; `request_incomplete` |
| `not_json_bom` | the request is not valid JSON: a byte-order mark | 0 | not_met; `request_incomplete` |
| `not_json_duplicate_member` | the request is not valid JSON: a top-level member name repeated | 0 | not_met; `request_incomplete` |
| `not_json_nan` | the request is not valid JSON: NaN in a top-level member no document defines | 0 | not_met; `request_incomplete` |
| `not_json_nesting_65` | the request is not valid JSON: nested 65 deep in a top-level member no document defines | 0 | not_met; `request_incomplete` |
| `not_json_trailing_comma` | the request is not valid JSON: a trailing comma inside target | 0 | not_met; `request_incomplete` |
| `not_object_array` | step 0 refuses: the request is an array | 0 | not_met; `request_incomplete` |
| `not_object_string` | step 0 refuses: the request is a string | 0 | not_met; `request_incomplete` |
| `operating_conditions_not_object` | step 0 refuses: operating_conditions an array (and no requirement conditions, so no tolerance lacks its operating condition) | 0 | not_met; `request_incomplete` |
| `operating_conditions_not_object_beside_tolerance` | step 0 refuses: operating_conditions an array, beside a temperature tolerance: the member's own `request_incomplete`, and one with the condition temperature, which has no operating entry | 0 | not_met; `request_incomplete`, `request_incomplete (temperature)` |
| `operating_entry_not_object` | step 0 refuses: operating temperature the number 310.15 | 0 | not_met; `request_incomplete (temperature)` |
| `operating_unit_missing` | step 0 refuses: operating temperature without `unit` | 0 | not_met; `request_incomplete (temperature)` |
| `operating_value_and_range` | step 0 refuses: operating temperature with both value and range (unit K) | 0 | not_met; `request_incomplete (temperature)` |
| `operating_value_missing` | step 0 refuses: operating temperature with a unit and neither value nor range | 0 | not_met; `request_incomplete (temperature)` |
| `operating_value_not_number` | step 0 refuses: operating temperature value the string "310.15" (unit K) | 0 | not_met; `request_incomplete (temperature)` |
| `range_lo_above_hi` | step 0 refuses: operating shear_rate range [500, 50] | 0 | not_met; `request_incomplete (shear_rate)` |
| `range_not_numbers` | step 0 refuses: operating shear_rate range of two strings | 0 | not_met; `request_incomplete (shear_rate)` |
| `range_one_number` | step 0 refuses: operating shear_rate range of one number | 0 | not_met; `request_incomplete (shear_rate)` |
| `range_three_numbers` | step 0 refuses: operating shear_rate range of three numbers | 0 | not_met; `request_incomplete (shear_rate)` |
| `record_content_hash_not_string` | step 0 refuses: reference content_hash an array | 0 | not_met; `request_incomplete` |
| `record_id_missing` | step 0 refuses: reference without id | 0 | not_met; `request_incomplete` |
| `record_id_not_string` | step 0 refuses: reference id a number | 0 | not_met; `request_incomplete` |
| `record_not_object` | step 0 refuses: target.record a string | 0 | not_met; `request_incomplete` |
| `record_version_missing` | step 0 refuses: reference without version | 0 | not_met; `request_incomplete` |
| `record_version_not_string` | step 0 refuses: reference version a number | 0 | not_met; `request_incomplete` |
| `record_without_content_hash` | step 0 refuses: reference without its hash | 0 | not_met; `request_incomplete` |
| `requirement_condition_empty` | step 0 refuses: temperature requirement an empty object (neither tolerance nor accept) | 0 | not_met; `request_incomplete (temperature)` |
| `requirement_condition_not_object` | step 0 refuses: temperature requirement the string "x" | 0 | not_met; `request_incomplete (temperature)` |
| `requirement_conditions_not_object` | step 0 refuses: requirement.conditions an array | 0 | not_met; `request_incomplete` |
| `requirement_missing` | step 0 refuses: no requirement | 0 | not_met; `request_incomplete` |
| `requirement_not_object` | step 0 refuses: requirement a string | 0 | not_met; `request_incomplete` |
| `target_missing` | step 0 refuses: no target | 0 | not_met; `request_incomplete` |
| `target_neither_record_nor_region` | step 0 refuses: target with neither record nor region | 0 | not_met; `request_incomplete` |
| `target_not_object` | step 0 refuses: target a string | 0 | not_met; `request_incomplete` |
| `tolerance_and_accept` | step 0 refuses: temperature requirement with both a tolerance and an accept list | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_below_zero` | step 0 refuses: temperature tolerance -1.0 K | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_beside_accept_for_token_condition` | density_kind requirement {"accept": ["apparent"], "tolerance": {"value": 0, "unit": "1"}}: a tolerance for a token condition beside a well-formed accept list gives `request_incomplete` (the unit is compared with nothing) | 0 | not_met; `request_incomplete (density_kind)` |
| `tolerance_for_token_condition_without_unit` | step 0 refuses: a tolerance, with no unit, for the token condition density_kind | 0 | not_met; `request_incomplete (density_kind)` |
| `tolerance_negative_zero_accepted` | a temperature tolerance of -0 passes step 0; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `tolerance_not_object` | step 0 refuses: temperature tolerance the number 1.0 | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_unit_missing` | step 0 refuses: temperature tolerance without `unit` | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_value_missing` | step 0 refuses: temperature tolerance without value (unit K) | 0 | not_met; `request_incomplete (temperature)` |
| `tolerance_value_not_number` | step 0 refuses: temperature tolerance value the string "1.0" (unit K) | 0 | not_met; `request_incomplete (temperature)` |
| `unknown_member_in_operating_condition` | a member inside an operating condition entry no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `unknown_member_in_reference` | a member inside the record reference no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `unknown_member_in_requirement` | a member inside requirement no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `unknown_member_in_target` | a member inside target no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `unknown_member_in_tolerance` | a member inside a tolerance no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `unknown_member_top_level` | a top-level member no document defines is ignored; the read ends at step 5 on the interface record (unknown_type) | 5 | not_met; `unknown_type` |
| `want_not_string` | step 0 refuses: want a number | 0 | not_met; `request_incomplete` |
| `want_unknown_token` | step 0 refuses: want "values" | 0 | not_met; `request_incomplete` |
| `want_wrong_case` | step 0 refuses: want "Value" | 0 | not_met; `request_incomplete` |

## PR-331

`read_side_contract.md`: a reason appears once per code and condition, however many times its check fails; `condition` is present exactly on the codes section 2 lists

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `incomplete_and_unit_mismatch_once_each` | temperature's operating value the string "37.0" and its tolerance -1.0, both in Cel: one `request_incomplete` and one `request_unit_mismatch` for temperature | 0 | not_met; `request_incomplete (temperature)`, `request_unit_mismatch (temperature)` |
| `malformed_once_step1` | no candidate, and two supplied sources did not parse: one malformed | 1 | not_met; `malformed` |
| `malformed_once_step1_pin` | no candidate holds the pin; one has an ill-formed (uppercase) content_hash and another source did not parse: one `malformed` | 1 | not_met; `malformed` |
| `malformed_once_step3` | a record with two envelope faults (and an unknown type): one malformed, no unknown_type | 3 | not_met; `malformed` |
| `request_incomplete_once_per_condition` | temperature's operating value a string and its tolerance below zero: one reason for temperature | 0 | not_met; `request_incomplete (temperature)` |
| `request_incomplete_once_without_condition` | field, want and reference hash all at fault: one request_incomplete | 0 | not_met; `request_incomplete` |
| `request_incomplete_two_conditions` | faults in temperature and in shear_rate: one reason per condition | 0 | not_met; `request_incomplete (temperature)`, `request_incomplete (shear_rate)` |
| `request_incomplete_with_and_without_condition` | a field off the pattern and a negative temperature tolerance: two reasons, one without condition | 0 | not_met; `request_incomplete`, `request_incomplete (temperature)` |
| `request_unit_mismatch_once` | temperature operating value and tolerance both in Cel: one reason | 0 | not_met; `request_unit_mismatch (temperature)` |
| `request_unit_mismatch_two_conditions` | temperature in Cel and shear_rate in 1/min: one reason each | 0 | not_met; `request_unit_mismatch (temperature)`, `request_unit_mismatch (shear_rate)` |
| `unregistered_condition_once` | pressure unregistered and its accept list holding a number: one reason for pressure | 0 | not_met; `request_incomplete (pressure)` |

## PR-332

`read_side_contract.md`: a `want` of a suite the reader does not claim (`fit`, `coverage`, `reference_data` without the fits and reference data suite) gives `want_mismatch` at step 0

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `bounds_absent` | want 'bounds' (plain read) is not refused at step 0, though the field is a constant; the reference has no candidate: absent | 1 | not_met; `absent` |
| `components_absent` | want 'components' (plain read) is not refused at step 0, though the field is a constant; the reference has no candidate: absent | 1 | not_met; `absent` |
| `coverage_with_fd_absent` | want 'coverage' with the suite claimed passes step 0; the reference has no candidate (water 2.0.0 not supplied): absent | 1 | not_met; `absent`; claims `fits_and_reference_data: true` |
| `coverage_without_fd` | want 'coverage', fits and reference data suite not claimed | 0 | not_met; `want_mismatch`; claims `fits_and_reference_data: false` |
| `evidence_absent` | want 'evidence' (plain read) is not refused at step 0, though the field is a constant; the reference has no candidate: absent | 1 | not_met; `absent` |
| `fit_with_fd_absent` | want 'fit' with the suite claimed passes step 0; the reference has no candidate (water 2.0.0 not supplied): absent | 1 | not_met; `absent`; claims `fits_and_reference_data: true` |
| `fit_without_fd` | want 'fit', fits and reference data suite not claimed | 0 | not_met; `want_mismatch`; claims `fits_and_reference_data: false` |
| `reference_data_with_fd_absent` | want 'reference_data' with the suite claimed passes step 0; the reference has no candidate (water 2.0.0 not supplied): absent | 1 | not_met; `absent`; claims `fits_and_reference_data: true` |
| `reference_data_without_fd` | want 'reference_data', fits and reference data suite not claimed | 0 | not_met; `want_mismatch`; claims `fits_and_reference_data: false` |
