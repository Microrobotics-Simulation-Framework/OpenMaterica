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
  witnesses; fits written back only as scoped overlays; a reserved family `kind` for evolution families;
  failure properties under mechanics; biocompatibility as test evidence; an advisory index; rewritten
  spike controls. Constraints 23 to 25; constraints 6, 9, 13 and 14 revised.

### Schema
### Families
### Data
### Verification
### Security
### Known Anomalies
- Registry created, with no entries.
