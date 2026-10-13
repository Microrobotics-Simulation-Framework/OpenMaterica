# Schema changes

Each schema version, what changed, and the conformance cases that came with it
(`DOCUMENTATION_ARCHITECTURE.md` section 7.2). Before 1.0.0 a reader reads only its own minor version
(`README.md`), so a minor version may change any shape; each change is listed here.

## 0.1.0 (draft, 2026-10-12)

The first version. It specifies records (the envelope, record types `material` and `overlay` with `interface`
reserved, the bulk, fluid, magnetic and biocompatibility sections, the eight form tokens, units, identifiers,
versions and the content hash), provenance, uncertainty, model families, fits and reference data, scene
documents, the USD binding, mixing rules, declarations and the read-side contract. Its cases are those listed
at the end of each document. Scene documents, layered paths, label crosswalks, the USD binding, the stage
check and the engine adapter are in 0.1.0; families, fits and reference data, and mixing are specified but
their suites are optional until the minor version that brings their first consumer (`README.md`). In USD a
region binds its material with the purpose `vesalius`; the `physics` purpose is left to engines, whose
materials an engine adapter writes from a declared engine model by an engine crosswalk, stamped with the reads
they came from, and which the stage check re-derives per shape (`usd_binding.md` sections 5, 9 and 10).
Vesalius ships one engine crosswalk, for `UsdPhysics`; a consumer writes the crosswalk for any other engine it
runs, drafted by a scaffold. Acoustic attenuation is registered in `/m`.

Settled before the first code (maintainer, 2026-10-13): a reader refuses as malformed exactly what RFC 8259's
grammar refuses and a listed set of further faults, follows I-JSON except that noncharacters are legal, and
reads every number as the nearest double, ties to even (`record_format.md` section 1 item 6; PR-002, PR-047);
`null` is read by where it is, and ignored inside a member the reader does not know (PR-049); records' and
other documents' schema versions match one pattern, and a missing or ill-formed `schema_version` is malformed
(section 8; PR-048), as is a scene document's `scene_schema_version` (SC-002), while an engine crosswalk with
an ill-formed or other `crosswalk_schema_version` is invalid (RC-140); the reader schema, in JSON Schema
2020-12, checks the envelope with the patterns of `id`, `version` and `content_hash`, and the body's structure
as far as the reader's version knows it, never a value field, form or section `specimen`, whose shape errors
refuse only the fields they affect, nor an unknown section or anything inside `extensions` (section 1 items 2
and 3; PR-008, PR-034, PR-045); an object with `document_type` and no `record_type` is not a record (PR-006);
a material reference resolves among the records supplied by hash, giving `malformed` where the record may be a
source that did not parse, one without a string `id` and `version`, or a candidate with an ill-formed
`content_hash`, or where two copies differ in their bytes (`read_side_contract.md` section 3, step 1; PR-328,
PR-329); the request has an exact shape and is checked on its own first, with structural, `want`,
condition-name, range and tolerance checks, and the two checks that need the form at step 11 (PR-330); a
`want` of a suite the reader does not claim gives `want_mismatch` at step 0 (PR-332); a reason appears once
per code and condition, with `condition` on a listed set of codes, and each step makes all its checks
(PR-331); with HS, a recomputed hash that differs gives `hash_mismatch` and one `pin_mismatch` (HS-010,
HS-011), and `hash_not_checked` labels only results that reach step 4; an overlay is resolved after the
target, and its base pin compared at step 6; the hash vectors widened (HS-003); case files gain claims,
variants (one file per arm, a case passing when a variant ran and none failed), exact comparison, a request
file for requests that break item 6, the `content_hash` operation and the `list_records` operation (always
`met`, listing only the good records), a `cases/` and `inputs/` layout, `labels` compared without
`hash_not_checked` unless a hash claim is stated, and reasons compared as a multiset of code and condition
(`README.md`, "Case files"); a request's unit is compared with the registered unit code point for code point,
after JSON escapes are decoded, on any operating condition or tolerance of a registered numeric condition
whose unit is a string, whatever else is wrong with the entry, and a request member the shape does not name at
that place is ignored (PR-320, PR-330); a reference with no candidate holding its hash gives `malformed`, not
`pin_mismatch`, when a supplied source is unreadable (PR-329); strings are hashed with no Unicode
normalisation (`record_format.md` section 9 item 2; HS-003); and the namespace `conformance` is reserved for
conformance fixtures, whose contents are illustrative: a record check flags one given from outside a
conformance tree, and a check of a whole library leaves conformance trees out (`record_format.md` section 7;
RC-121).
