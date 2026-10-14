# Hash cases

The cases of the hash suite (HS). `CASES.md` lists every case file with what it tests and its expected
answer; the conformance tree's `README.md` explains how to read a case. There are two kinds:
- **`content_hash` operations** (HS-001 to HS-003). Each hashes one input and gives `sha256:` and 64 hex
  digits, or `malformed` for an input that breaks the JSON rules. The hash is of the input's hashable view
  (`docs/specification/record_format.md` section 9): the top-level `content_hash` and `card` removed, and
  every `review` and `copy` inside a `provenance` object removed; then RFC 8785 canonical JSON and SHA-256.
  - HS-001: what is removed and what is kept.
  - HS-002: whole records hashing to their stated hash.
  - HS-003: canonical form (numbers, strings, member order, depth, Unicode), and inputs that are refused.
- **Reads by a reader that claims HS** (HS-010, HS-011; `claims: {"hash": true}`). A reader with HS recomputes
  a record's hash at step 4 of the read, and refuses one whose recomputed hash differs from its stated one,
  with `hash_mismatch` and one `pin_mismatch`. These reads end by step 5. The interface record serves as the
  stop, as in the plain-read suite: `unknown_type` at step 5 shows that the hash step passed. The half of
  HS-011 that holds for a reader without HS is plain-read case PR-327 (`PR-327.pin.json`), since a runner
  never runs this suite for a reader that does not claim it.

Every expected hash was computed by Python `rfc8785` 0.1.4 and Node `canonicalize` 2.0.0, which agree on all
of them, and recomputed by a third implementation written for the check.

## The inputs

| Family | What it holds |
|---|---|
| `view_*` | JSON values built to exercise removal, not records. Some hold shapes no record would, on purpose: a `provenance` that is an array, a string or a number; numeric `review` and `copy` members; the string `"removed"` where a hash would be. Never "fix" them |
| `number_*` | one number each, written in a form whose canonical form differs (`1.0`, `1e2`, `0.0000001`, `-0`, `1e21` written out as an integer, 9007199254740993, the largest double, numbers that underflow), with controls |
| `strings_canonical.json`, `utf16_order_*`, `nfc_*`, `true_beside_one.json` | string escaping, member order by UTF-16 code units (the same names written raw and as escapes), decomposed and composed `é` kept apart (never normalised), `true` beside `1` |
| `depth_64.json`, `depth_64_scalar.json` | nesting exactly 64 deep, which is read: the second ends in a number, which adds no depth |
| `malformed_*` | inputs the JSON rules refuse: a byte-order mark, a repeated member name (also inside a member the view removes), `NaN`, a number that overflows, an unpaired surrogate escape, overlong UTF-8, a trailing comma, nesting 65 deep |
| `water_fixture.json`, `water_density_fixture.json`, `water_overlay_fixture.json` | whole records, hashing to their stated hashes. This `water_fixture.json` is this suite's own and differs from the plain-read one; see the conformance tree's `README.md` |
| `water_fixture_*` | the water record with one thing changed: edited after pinning (value, licence, name, a member added, the type) with the old hash still stated; with an envelope the reader schema refuses, or another schema version, so that the read stops before the hash step; with `null` and unknown members; with a field's `provenance` an array (nothing removed); with `review` and `copy` at depth, and that record's hashable view written out (the same hash) |
| `interface_fixture.json` | the step-5 stop for the HS-010 control |

## What the cases cannot show

- **Accepting an encoded surrogate (`ED A0 80`) or `Infinity`.** No hash case holds these. Plain-read case
  PR-002, which every reader claims, refuses both.
- **Comparing the recomputed hash with the pin instead of with the stated hash.** Step 1 has already found the
  stated hash equal to the pin, so the two comparisons always agree, and no case can tell them apart.
- **That the type is inside the hash, from `HS-010.type_edited` alone.** A reader that left `record_type` out
  of the hash also gives `hash_mismatch` there. That arm tests the step order (the hash step before the type
  step). `HS-010.control_hash_verifies` and the HS-002 records test the type's place in the hash.
- `HS-010.value_edited` and `HS-011.edited_after_pinning` are the same read, under the two rows that each name
  it.
