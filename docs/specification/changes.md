# Schema changes

Each schema version, what changed, and the conformance cases that came with it
(`DOCUMENTATION_ARCHITECTURE.md` section 7.2). Before 1.0.0 a reader reads only its own minor version
(`README.md`), so a minor version may change any shape; each change is listed here.

## 0.1.0 (draft, 2026-10-12)

The first version. It specifies records (the envelope, record types `material` and `overlay` with `interface`
reserved, the bulk, fluid, magnetic and biocompatibility sections, the eight form tokens, units, identifiers,
versions and the content hash), provenance, uncertainty, model families, fits and reference data, scene
documents, the USD binding, mixing rules, declarations and the read-side contract. Its cases are those listed
at the end of each document. Scene documents and the USD binding are built in 0.1.0, last; families, fits
and reference data, and mixing are specified but their profiles are optional until the minor version that
brings their first consumer (`README.md`).
