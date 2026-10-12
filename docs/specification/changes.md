# Schema changes

Each schema version, what changed, and the conformance cases that came with it
(`DOCUMENTATION_ARCHITECTURE.md` section 7.2). Before 1.0.0 a reader reads only its own minor version
(`README.md`), so a minor version may change any shape; each change is listed here.

## 0.1.0 (draft, 2026-10-12)

The first version. It specifies records (the envelope, record types `material` and `overlay` with `interface`
reserved, the bulk, fluid, magnetic and biocompatibility sections, the eight form tokens, units, identifiers,
versions and the content hash), provenance, uncertainty, model families, fits and reference data, scene
documents, the USD binding, mixing rules, declarations and the read-side contract. Its cases are those listed
at the end of each document. Scene documents, layered paths, label mappings, the USD binding, the stage check
and the engine adapter are in 0.1.0; families, fits and reference data, and mixing are specified but their
profiles are optional until the minor version that brings their first consumer (`README.md`). In USD a region
binds its material with the purpose `vesalius`; the `physics` purpose is left to engines, whose materials an
engine adapter writes from a declared engine model, stamped with the reads they came from, and which the stage
check re-derives per shape (`usd_binding.md` sections 5, 9 and 10). Acoustic attenuation is registered in
`/m`.
