# Changelog

All notable changes to OpenMaterica will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Additional sections per release: **Schema**, **Families**, **Data**, **Verification**, **Security** and
**Known Anomalies**. The schema, each model family and each library material carry their own versions; see
`DOCUMENTATION_ARCHITECTURE.md` section 7. Once the material library has its own repository, its changes are
recorded in that repository's CHANGELOG.

## [Unreleased]

### Schema
- The value fields of schema 0.1's writer schema, so far open placeholders (S2a-1): a value field of each of
  the eight forms, or alternatives; the constant, interval, composition and evidence forms in full; conditions
  with `plus_minus` and `set_or_measured`, each token condition bound to its own row's tokens; the specimen
  facts with `supply_form` and `lot`, a fact's fixed unit `s` and `mimics`'s stated basis taken from the text;
  the statistics block and its uncertainties, the provenance object and `label`; a status object in exactly
  the members `provenance.md` section 1 item 5 lists, a placeholder beside one taking no other; and the rules
  across objects of `provenance.md` sections 2, 3 and 7 (an extraction's derivation, formulation or fit
  record, a pooled statistic's search, a withheld value's or evidence entry's recipe). The table, power-law,
  parameter-set and reference-data forms' own members, the fit record, and the provenance members whose own
  members the text does not yet name stay placeholders, and a section's field names stay open; the schema's
  description names each such place. Members a read does not check carry `x-materica-write-only`
  (`record.writer.json`).
- The reader schema holds a value field's and a section specimen's shapes in `$defs`, as step 8 checks them,
  applied from nowhere, without the rules a read cannot apply (one testing, or requiring only, a member it
  does not check); the typed shapes gain a TypedDict per form and per shape, every number typed `float` as the
  reader gives it (`materica.shapes`).
- The vocabulary gains every token S2 reads, generated from the specification: the reason table's steps, the
  bases a field's row allows a form, the conditions another condition requires, the element symbols, each
  token condition's tokens and each specimen fact's fixed values as enumerations, and the form, interval,
  composition, statistics, uncertainty, provenance and result-label tokens, four of them in new files
  (`forms.json`, `statistics.json`, `provenance.json`, `labels.json`). The generator reads every code span of
  a cell or stops, and stops on a name listed twice in a table.
- `case.json` takes the `transform_draws` operation of a sampling case, its draws' shape not yet specified.

### Verification
- Checks that the value-field shapes match the specification's member tables, status table and examples, that
  the members marked write-only are those step 8 does not check, that each token condition and fact binds its
  row's list, that each rule across objects refuses a field without its member, and that the writer's
  description names exactly the places it leaves open (`tests/spec_sync/test_value_fields.py`).
- A check that the names valid at one place, the members an `allOf` joins included, stay more than one slip
  apart and that no name has two meanings, over the schemas, the vocabulary and the specification, with an
  allowlist of the overlaps judged intended, each with its reason and a safeguard quote that must stay in its
  document (`tests/spec_sync/test_name_overlaps.py`).
- A check that each reason code is given only at the steps the reason table names, against the text (a step's
  item and the passages it hands its checks to, and step 6 for an overlay what steps 1 to 5 give), and against
  the code of steps 0 to 5 in every module of the core, statically and traced through every read case file
  (`tests/spec_sync/test_reason_steps.py`).
- Hypothesis properties of the writer schema: it takes every value field the specification allows, and refuses
  each of 153 faults the text names, built from the text and the vocabulary, never from the schema; 69 mutants
  of the schema, the S2a-1 review's 31 among them, each killed at the assertion it names
  (`tests/property/test_writer_properties.py`, `test_writer_mutants.py`), in a third CI shard, `writer`.
- A check that each member the schemas declare whole admits the float the reader gives
  (`tests/unit/test_shapes.py`).
- Each new check is shown failing on seeded faults.

## [0.1.0.dev1] - 2026-10-14

A development pre-release, published to rehearse the release workflow and to hold the name on PyPI. It holds
S1: strict JSON, RFC 8785 and the content hash; records, their store and the read up to step 5; and the
schemas and vocabulary of 0.1, whose files may still change before 0.1.0. The entries below are everything
up to this release.

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
- The first code: the package (`pyproject.toml` with uv's build backend, `uv.lock`, `py.typed`, no run-time
  dependency, the licence as an SPDX expression); strict JSON reading (`materica.core.jsonio`), RFC 8785
  serialisation (`materica.core.canonical`) and the content hash (`materica.core.hashing`, exported as
  `materica.content_hash`); CI, with a sign-off check on every commit of a pull request.
- The read up to step 5: identifiers and versions matched in full, versions ordered by their components'
  lengths and digits (`materica.core.identifiers`); the vocabulary of schema 0.1, generated from the
  specification's tables (`schema/0.1/vocabulary/`, `materica.core.vocabulary`); the reader schema's checks by hand
  (`materica.core.envelope`); the record store, and steps 1 to 5 of a read (`materica.core.record`,
  `materica.core.resolve`); the request's own check and the read, which raises `NotImplementedError` where a
  step not built yet would decide it (`materica.core.read`); plain records from files (`materica.io.plain`).
  `materica.read` and `materica.load_records` join `materica.content_hash` as the public API.
- The JSON shapes of records, read requests and results, and case files, as TypedDicts generated from the
  schemas (`materica.shapes`); a read's results are read-only to a type checker (PEP 705, in `shapes.pyi`).
- Generators, which CI runs with `--check` in a job of its own: the vocabulary from the specification's tables,
  the reader schema and the typed shapes from the writer schemas (`scripts/gen_*.py`).

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
- The JSON Schemas of 0.1, each `$id` its path under `https://w3id.org/materica/schema/0.1/`: the writer
  schema's envelope and body structure, edited by hand (`record.writer.json`); the reader schema, generated
  from it (`record.reader.json`); the read request and result (`read_request.json`, `read_result.json`); the
  schema of case files (`case.json`); and the vocabulary, generated from the specification's tables
  (`vocabulary/`). The specification's member tables are checked against them.

### Families
### Data
### Verification
- The conformance-case runner. Of the 416 case files, the 51 `content_hash` cases (HS-001 to HS-003) run and
  pass; the 365 reads and listings are reported as not yet runnable, never as passed. Nine broken
  implementations, one fault each, each fail a real case.
- Property tests of the JSON reader, the RFC 8785 serialisation and the content hash, under a draw-rejection
  audit and a feature audit; 32 mutants of the core, each killed by its property within the `ci` profile's
  examples at both tree sizes; Hypothesis profiles `dev`, `ci` and `deep`, the last at the original sizes.
- Atheris fuzzing, weekly: raw bytes into the JSON reader, checked against a reference reader built from the
  standard library; and the Hypothesis properties driven by Atheris, whose findings the property tests replay
  and shrink. Each run first shows that both find a fault seeded in the reader.
- All 417 case files run and pass, each under every configuration of claims it holds for: with the hash suite
  (409), without it (347), and with the fits and reference data suite (408). PR-330 gains an arm: a tolerance
  beside `operating_conditions` that is not an object (`read_side_contract.md` section 1). Fifteen more broken
  implementations, of the read and the listing, each fail a real case. Every case file reads alike through the
  reader under test and a reference reader that shares no code with it, and is valid against `case.json`.
- Checks that what is written twice agrees: the specification's member tables and the schemas, and the token
  lists the schemas write by hand; the envelope checks and the reader schema on every conformance input; each
  `CASES.md` and its case files; and the map of case files to the steps that run them (`tests/spec_sync/`).
  Each module's imports, relative ones included, against the layers, and the shapes' against the standard
  library.
- Property tests of the envelope checks against the reader schema, of versions, and of the laws of a read up to
  step 5; 35 more mutants, each killed within the `ci` profile's examples at both sizes. CI runs the property
  tests in two shards side by side. A third Atheris target drives these properties, and first shows that it
  finds a fault seeded in the read.

### Security
### Known Anomalies
- Registry created, with no entries.
