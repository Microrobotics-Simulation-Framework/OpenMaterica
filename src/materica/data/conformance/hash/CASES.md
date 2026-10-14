# Hash cases: what each case file tests

One row per file in `cases/`, grouped by case id; each heading quotes the case's row in the
specification, which holds where the two differ. **Ends at** is `operation` for a `content_hash`
operation, or the step of `docs/specification/read_side_contract.md` section 3 at which a read ends.
**Expected** is read from the case file; hashes are shortened here, never in the case files. See
`README.md` beside this file for how to read a case.


## HS-001

`record_format.md`: the hash excludes exactly the listed members, at any depth

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `escaped_names` | names are matched after their escapes are decoded (`c\u0061rd`, `rev\u0069ew`, `pr\u006fvenance`) | operation | met; `sha256:33ebe517…` |
| `names_exact` | only the exact names are removed: `Card`, `content-hash`, `Review`, `COPY`, `reviews`, `review `, and `review` inside `Provenance`, are kept | operation | met; `sha256:a10dbe23…` |
| `nested_names_kept` | `content_hash` and `card` below the top level are kept | operation | met; `sha256:3aa89daf…` |
| `outside_kept` | `review` and `copy` outside any provenance object are kept, siblings of `provenance` included | operation | met; `sha256:d463dc0d…` |
| `provenance_anywhere` | a member named `provenance` anywhere (top level, in an array item, inside an unknown member) opens removal | operation | met; `sha256:1ea5b6ab…` |
| `provenance_arrays` | `review` and `copy` removed through arrays, arrays of arrays and objects in arrays; a string `"review"` as an array item is a value and kept | operation | met; `sha256:5a250db2…` |
| `provenance_depth` | `review` and `copy` removed through nested objects (`evidence.copy`, `per_parameter.*.review`, deeper) | operation | met; `sha256:3d93ab72…` |
| `provenance_inside_non_object` | a `provenance` object inside an array that is a `provenance`'s value has `review` and `copy` removed | operation | met; `sha256:85db855e…` |
| `provenance_members` | `review` and `copy` directly inside a provenance object are removed | operation | met; `sha256:1453feca…` |
| `provenance_nested_in_provenance` | a `provenance` array inside a `provenance` object: the objects in it are still inside the outer provenance object, so their `review` and `copy` are removed | operation | met; `sha256:8a7e1bd5…` |
| `provenance_not_object` | a `provenance` that is an array, string, number, `true` or `null` has nothing removed | operation | met; `sha256:9c1f135b…` |
| `top_level_absent` | control: the same object without them gives the same hash | operation | met; `sha256:e1f0e207…` |
| `top_level_any_value` | they are removed by name whatever their value (a number, an object): same hash again | operation | met; `sha256:e1f0e207…` |
| `top_level_array` | a top-level array is hashed; `content_hash` and `card` inside it are kept (top-level members are removed only from an object), and a `provenance` object in it still has `review` removed | operation | met; `sha256:1a6b81a1…` |
| `top_level_removed` | top-level `content_hash` and `card` are removed (same hash as `top_level_absent`) | operation | met; `sha256:e1f0e207…` |
| `top_level_scalar` | a top-level number is hashed: `1.0` gives the hash of `1` | operation | met; `sha256:6b86b273…` |

## HS-002

`record_format.md`: the content hash verifies (RFC 8785, SHA-256, lowercase hexadecimal)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `material` | a material record (constant field, with `card`) hashes to its stated `content_hash` | operation | met; `sha256:b5c462ab…` |
| `material_table` | a material record with a table field hashes to its stated `content_hash` | operation | met; `sha256:665355a1…` |
| `overlay` | an overlay record hashes to its stated `content_hash`; the nested `base.content_hash` is hashed | operation | met; `sha256:9d2599e3…` |
| `string_escapes` | RFC 8785 strings: escapes decoded and re-escaped canonically (`\u0000`, `\u001f`, `\b`...), `\/` and non-ASCII written raw, U+007F, U+2028 and the noncharacter U+FFFF raw | operation | met; `sha256:3b690cd7…` |

## HS-003

`record_format.md`: hash vectors: numbers whose canonical form differs (`1.0`, `1e2`, `0.0000001`, `-0`, an integer written as `1000000000000000000000`, 9007199254740993); `true` beside `1`; `null` in a member the reader does not know; member order by UTF-16 code units; members the reader does not know are hashed; `review` and `copy` removed at any depth inside a provenance object and kept outside one

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `depth_64` | control: nesting exactly 64 deep is read and hashed | operation | met; `sha256:0b041828…` |
| `depth_64_scalar` | 64 nested arrays, the top-level one at depth 1, the innermost (depth 64) holding the number `0`: a scalar adds no depth, so the file is read and hashed, not refused as 65 deep | operation | met; `sha256:f0244ae1…` |
| `integer_1e20` | boundary control: `100000000000000000000` stays `100000000000000000000` | operation | met; `sha256:8e85c124…` |
| `integer_1e21` | `1000000000000000000000` serialises as `1e+21` | operation | met; `sha256:9e24d139…` |
| `integer_9007199254740993` | `9007199254740993` is hashed as `9007199254740992` | operation | met; `sha256:e7b4b245…` |
| `largest_double` | `1.7976931348623158e308` serialises as `1.7976931348623157e+308` | operation | met; `sha256:f32207f7…` |
| `malformed_bom` | a byte-order mark before valid JSON: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_depth_65` | nesting 65 deep (an object holding 64 nested arrays): `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_duplicate_name` | a member name repeated after unescaping (`{"a":1,"\u0061":2}`): `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_duplicate_removed_member` | a repeated name inside a member the hash view removes (`provenance.review` twice): still malformed: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_nan` | the token `NaN`: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_overflow` | `1.7976931348623159e308`, which rounds to an infinity: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_overlong_utf8` | an overlong UTF-8 form (`C0 80`) in a string: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_trailing_comma` | a trailing comma: `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `malformed_unpaired_surrogate` | an unpaired surrogate escape (`\ud800`): `not_met`, `malformed`, no value | operation | not_met; `malformed` |
| `negative_zero` | `-0` serialises as `0` | operation | met; `sha256:ec4f95ab…` |
| `nfc_decomposed` | `e` followed by U+0301 (raw, escaped, and in a member name) is hashed as those two code points, never normalised to U+00E9 | operation | met; `sha256:87c4703f…` |
| `nfc_side_by_side` | U+00E9 and `e` U+0301 as two member names: distinct names, not a repeated one, both hashed, the decomposed one first (UTF-16 order) | operation | met; `sha256:1bfd06ee…` |
| `null_in_unknown_member` | `null` in members the reader does not know (top level, inside a value field) is hashed as `null` | operation | met; `sha256:fd23b86b…` |
| `number_0_0000001` | `0.0000001` serialises as `1e-7` | operation | met; `sha256:3a28f15d…` |
| `number_1` | control: `1` gives the same hash as `1.0` | operation | met; `sha256:afbf9d0f…` |
| `number_1_0` | `1.0` serialises as `1` | operation | met; `sha256:afbf9d0f…` |
| `number_1e2` | `1e2` serialises as `100` | operation | met; `sha256:f5e21757…` |
| `provenance_not_object` | a value field whose `provenance` is an array of one object holding `review` and `evidence.copy`, and an unknown member whose `provenance` is a string: nothing removed | operation | met; `sha256:a5ea82e7…` |
| `review_copy_at_depth` | `review` and `copy` removed at depth inside a provenance object, through nested objects and arrays; `review` and `copy` outside it (top level, section, field) kept | operation | met; `sha256:0ace292d…` |
| `review_copy_view` | control: `review_copy_at_depth`'s hashable view written out gives the same hash | operation | met; `sha256:0ace292d…` |
| `true_beside_one` | `true` beside `1` (and `false` beside `0`) stay distinct | operation | met; `sha256:33715643…` |
| `underflow` | `3e-324` serialises as `5e-324`; `1e-400` and `-1e-400` as `0` | operation | met; `sha256:9bd107cb…` |
| `unknown_members_hashed` | members the reader does not know are hashed: top level, body, `extensions`, an unknown section, inside a section, field, statistics and provenance | operation | met; `sha256:07d2cb22…` |
| `utf16_order_escaped` | the same names written as escapes (a surrogate pair): same hash | operation | met; `sha256:f001054e…` |
| `utf16_order_raw` | members ordered by UTF-16 code units: U+1F600 before U+E000 (names written raw) | operation | met; `sha256:f001054e…` |

## HS-010

`read_side_contract.md`: a record whose recomputed hash differs from its own is refused (`hash_mismatch`), with one `pin_mismatch`, since its stated hash equals the pin

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `control_hash_verifies` | control: a record whose recomputed hash equals its stated hash and the pin passes step 4 and is refused at step 5 (`unknown_type`: `interface` in 0.1.0), with no `hash_mismatch` | 5 | not_met; `unknown_type`; labels none; claims `hash: true` |
| `envelope_refused` | stated hash equals the pin, `licence` then written as a string: still a candidate at step 1, refused at step 3 (`malformed`) before the hash is recomputed, so no `hash_mismatch` or `pin_mismatch` | 3 | not_met; `malformed`; labels none; claims `hash: true` |
| `licence_edited` | stated hash equals the pin, record then edited (its `licence.values` changed): `hash_mismatch` and one `pin_mismatch`, no value, no labels | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `member_added` | stated hash equals the pin, record then edited (a top-level member the reader does not know added): `hash_mismatch` and one `pin_mismatch`, no value, no labels | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `name_edited` | stated hash equals the pin, record then edited (its `name` (informative only) changed): `hash_mismatch` and one `pin_mismatch`, no value, no labels | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `other_version` | stated hash equals the pin, `schema_version` then changed to `0.2.0`: refused at step 2 (`other_version`) before the hash is recomputed, so no `hash_mismatch` or `pin_mismatch` | 2 | not_met; `other_version`; labels none; claims `hash: true` |
| `type_edited` | stated hash equals the pin, `record_type` then changed to `interface`, a type no 0.1.0 reader reads: the type is inside the hash, and step 4 comes before step 5, so `hash_mismatch` and one `pin_mismatch`, not `unknown_type` | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `value_edited` | stated hash equals the pin, record then edited (its viscosity value changed): `hash_mismatch` and one `pin_mismatch`, no value, no labels | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |

## HS-011

`read_side_contract.md`: a reader with HS refuses a record whose stated hash differs from a pin (`pin_mismatch`), and one edited after pinning whose stated hash still equals the pin (`hash_mismatch` and one `pin_mismatch`); a reader without HS refuses the first as well (PR-327's pin arm)

| Variant | Arm | Ends at | Expected |
|---|---|---|---|
| `edited_after_pinning` | a record edited after pinning whose stated hash still equals the pin: `hash_mismatch` and one `pin_mismatch` | 4 | not_met; `hash_mismatch`, `pin_mismatch`; labels none; claims `hash: true` |
| `stated_differs` | the record's stated (and correct) hash differs from the pin: `pin_mismatch` only, read ends at step 1, so no `hash_not_checked` label | 1 | not_met; `pin_mismatch`; labels none; claims `hash: true` |
| `stated_differs_recomputed_equals` | the pin equals the record's recomputed hash but not its stated one: step 1 compares the stated hash, so `pin_mismatch` only, and no `hash_mismatch` (step 4 is never reached) | 1 | not_met; `pin_mismatch`; labels none; claims `hash: true` |
