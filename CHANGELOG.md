# Changelog

All notable changes to OpenMaterica will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Additional sections per release: **Schema**, **Families**, **Data**, **Verification**, **Security** and
**Known Anomalies**. The schema, each model family and each library material carry their own versions; see
`DOCUMENTATION_ARCHITECTURE.md` section 7. Once the material library has its own repository, its changes are
recorded in that repository's CHANGELOG.

## [Unreleased]

### Added
- Architecture concept (`design/ARCHITECTURE_DRAFT.md`).
- Documentation architecture plan (`DOCUMENTATION_ARCHITECTURE.md`), contribution rules (`CONTRIBUTING.md`),
  security policy (`SECURITY.md`), intended use statement (`docs/regulatory/intended_use.md`), an empty
  anomaly registry (`docs/validation/known_anomalies.yaml`) and its issue template.
- Design revision: plain records as a complete form with OpenUSD as the primary binding; five value forms;
  versioned model families with golden test vectors, reference implementations and check points in
  records; declared uncertainty structures; per-field proxies; a source registry, three record tiers and a
  separate data licence; the core, family packages and library as separate components; the dielectric
  section; layered paths. Constraints 13 to 17 and the pull-request template with the data attestation.
- Distribution design: namespaced material identifiers; material cards in place of data sheets; static,
  archived releases with federation through an index and no hosted service; self-contained shipped USD
  layers; record checks as a core command (`python -m materica check`). Constraints 18 and 19.
- Model-assisted curation design: an MCP tooling layer (bring-your-own-key, deterministic tools, quotes,
  human review, fail-closed release, a gold set); convention witnesses for parameter sets; evidence,
  assistance and search-record provenance fields. Constraints 20 to 22; constraint 14 extended.
- Phasing for MIME 0.3.0: three feature sets, each feature tied to what it serves; MIME spikes before MIME
  work starts.
- Revision against two new principles (records hold facts, consumers declare choices; carry what the
  evidence supports): consumer declarations with three-valued checks; domains; specimen facts in place of
  proxy flags; named mixing rules picked by the consumer; no schema fallbacks; tables with schemes, ranges
  and edges; spreads that say what they represent, `not_reported` and interval-only values; independent
  witnesses; fits written back only as scoped overlays; a family `kind` for evolution families;
  failure properties under mechanics; biocompatibility as test evidence; an advisory index; rewritten
  spike controls. Constraints 23 to 25; constraints 6, 9, 13 and 14 revised.
- Simplification pass: sections specified when a consumer needs them (fluid, mechanical with failure,
  acoustic, radiological, magnetic, biocompatibility first; optical, thermal and dielectric later), with
  three rules that make adding one a minor schema change; a publishers file and a template repository
  from the first library release, with MIME as the first other publisher; prototypes before the package;
  the advisory index and Hugging Face items as notes for later.
- Evolution families in the core from the start: state and history (viscoelastic and rate-dependent
  models), with optional events defined independently of any solver.
- Decisions after the prototypes (2026-10-12): the scope is substances in and around the human body, never
  systems, with five rules (a transfer test, pairs, geometry as scene data, behaviour, entry); every record
  has a record type, `material` and `interface` being OpenMaterica's, so other namespaces can use the
  machinery for data that is not a material; the curated library under CC0-1.0; reference implementations live
  with their families, shipped as `openmaterica-families`; consumers write their own readers, mixing rules and
  evaluators, verified against conformance data; quotes for every value extracted from text or a table in
  the curated library; curation tools before the first library release; a `bulk` section for density and
  elemental composition; the layered path's USD form as a typed prim, needed by MIME 0.3.0; an anisotropic
  linear elastic family for bone; conditions separated from specimen facts, with a starting vocabulary;
  new conformance cases (derivatives at table knots and ends, in-range reports, mixing at the cell, record
  types, the stage's units, physics bindings). Constraints 26 and 27; constraints 14, 17 and 21 revised.
- Fixes after an independent review of that revision (2026-10-12): the transfer test replaced by a line
  between test specimens (in, with their shape and size as conditions) and made objects as built (out); the
  typed value beside each field's JSON string in USD deleted, and no `UsdPhysics.MaterialAPI` on shipped
  layers; an `overlay` record type, overlays as prims of their own applied only when declared, scoped by a
  hash of the consumer's model configuration; unknown record types skipped when listing and refused when
  referenced, with namespaced types specified only after a consumer prototypes one; a plain scene manifest;
  the layered path's USD form with an index per interval, since USD drops repeated relationship targets;
  `interval` and `composition` value forms; attenuation stored as an amplitude coefficient, with shear
  attenuation for solids; declared extrapolation as a consumer declaration; an unknown token refuses its
  field and an unknown condition gives "unknown"; run-time watches on every declared condition; a
  `marginals` uncertainty structure; quotes required by the curated library's policy and checked where
  present, with a hash fallback if the legal review rules quotes may not ship, and evidence excluded from
  the CC0 grant; the content hash over the whole record minus an exclusion list, with test vectors;
  "a consumer's computation" defined as its step, compiled program and gradient path, the core running at
  build, and the write-side tooling split into `openmaterica-authoring`; the first library release defined as
  the first archived release with a DOI; conformance suites; disease and treatment state as specimen
  facts; records in JSON only. The stiffness tensor for bone moved to stretch. Constraints 4, 5, 13, 14, 21,
  24, 26 and 27 revised.
- After an ecosystem survey of NVIDIA's schemas and the wider ecosystem, and its review: the USD binding,
  layered paths, label crosswalks and scene documents move into OpenMaterica 0.1, with no cut line; a region
  binds its material with the purpose `materica`, and `physics` is left to engines; an engine is declared as a
  model, written by an engine adapter from pinned engine crosswalks and checked per shape by `materica check
  --stage`; readers detect schemas by name, traverse instances, and refuse unloaded payloads, point-instancer
  prototypes and time samples; acoustic attenuation is registered as `/m`; label crosswalks read by name.
- OpenMaterica ships one engine crosswalk, for OpenUSD's `UsdPhysics`; a consumer writes and pins the
  crosswalk for any other engine it runs, drafted by a scaffold from the engine's schema file and compared
  with the schema file it pins by hash. The stamp on an engine material carries the APIs applied, each
  attribute's type and dimension and the unit convention, so the stage check re-derives values without the
  crosswalk and checks the stamp against its units.
- Names settled (maintainer, 2026-10-13): conformance suites, engine crosswalks and label crosswalks replace
  conformance profiles, engine maps and label mappings; identifiers renamed to match
  (`engine_crosswalk_invalid`, `family_suite_absent`, `--crosswalk`, `"suite"` in case files).
- Decisions before the first code (maintainer, 2026-10-13): the core depends on Python's standard library
  only, with `[check]`, `[usd]` and `[sample]` extras; engine results in `openmaterica[usd]`; scene documents
  built before declarations; the writer JSON Schemas the single source of structure, with typed shapes
  generated from them; the package typed (`py.typed`); a Python 3.11 floor under a standing rule; record
  checks that need a registry, a copy or the history moved to the library's tooling; SPDX headers on source
  files.

### Changed
- Renamed before the first release (maintainer, 2026-10-14): the project is OpenMaterica, formerly developed
  under the working name Vesalius. The distribution is `openmaterica` and the package `materica`. The record
  namespace, family identifiers, USD binding purpose, attribute namespace and command are `materica`, and the
  USD schema classes take the prefix `Materica`. Library records are `materica/MAT-NNNN` and
  `materica/INT-NNNN`, and the registry prefixes are `OMAT-ANO-`, `OMAT-VER-` and `OMAT-MTH-`.

### Schema
- Schema 0.1.0 (draft), settled before the first code: what a reader refuses as malformed JSON, numbers read
  as doubles, `null` read by where it is, one schema-version pattern, the reader schema's scope, how a
  material reference resolves among the records supplied, the request checked first, reason multiplicity,
  case-file claims, variants, exact comparison and operations, and the namespace `conformance` reserved for
  conformance fixtures (`docs/specification/changes.md`).

### Families
### Data
### Verification
### Security
### Known Anomalies
- Registry created, with no entries.
