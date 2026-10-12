# Changelog

All notable changes to Vesalius will be documented in this file.

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
  layers; record checks as a core command (`python -m vesalius check`). Constraints 18 and 19.
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
  has a record type, `material` and `interface` being Vesalius's, so other namespaces can use the machinery
  for data that is not a material; the curated library under CC0-1.0; reference implementations live with
  their families, shipped as `vesalius-families`; consumers write their own readers, mixing rules and
  evaluators, verified against conformance data; quotes for every value extracted from text or a table in
  the curated library; curation tools before the first library release; a `bulk` section for density and
  elemental composition; the layered path's USD form as a typed prim, needed by MIME 0.3.0; an anisotropic
  linear elastic family for bone; conditions separated from specimen facts, with a starting vocabulary;
  new conformance cases (derivatives at table knots and ends, in-range reports, mixing at the cell, record
  types, the stage's units, physics bindings). Constraints 26 and 27; constraints 17 and 21 revised.

### Schema
### Families
### Data
### Verification
### Security
### Known Anomalies
- Registry created, with no entries.
