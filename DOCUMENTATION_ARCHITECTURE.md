# Vesalius Documentation Architecture Plan

**Status: a plan.** Written 2026-10-11, before any code exists, and revised the same day with the
architecture draft. Appendix B says what is in place. The architecture of the library itself is in
[`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md) (the **architecture draft**).

## Executive Summary

**Vesalius** is an open material schema with an OpenUSD binding, and a small Python toolkit. It describes
what tissues, phantoms and devices are made of (fluid, mechanical, acoustic, optical, thermal, dielectric,
radiological and magnetic properties), with the provenance and uncertainty of every value, binds those
descriptions to anatomical and device geometry, and lets any simulator read them. Its code is licensed
Apache-2.0; its material library would carry a data licence of its own.

Where it sits:

```
Layer 1  MADDENING      differentiable multiphysics framework       LGPL-3.0-or-later
Layer 1  Vesalius       material schema, library and toolkit        Apache-2.0      <- THIS PROJECT
Layer 2  MIME           microrobotics physics engine                LGPL-3.0-or-later   (uses both)
Layer 3  MICROROBOTICA  research simulator and registry             AGPL-3.0
Layer 4  [Commercial product]                                       regulated, CE-marked

Elsewhere: products built on NVIDIA Isaac for Healthcare may read Vesalius materials directly.
```

Vesalius sits beside MADDENING, not on top of it: it has no code dependency on MADDENING or MIME, and it
must stay readable by simulators that use neither (design principle 1 of the architecture draft).

Vesalius has three components with their own versions (architecture draft section 3.1):

| Component | What it is | Licence |
|---|---|---|
| Core | the specification, the record and USD schemas, the reader and writer, the verification machinery | Apache-2.0 |
| Family packages | model-family definitions: equations, golden test vectors, reference implementations | Apache-2.0 |
| Library | curated material records, in a repository of its own, released as static archives with a DOI; no hosted service | a data licence |

**Why it is likely to become SOUP.** The values Vesalius ships and resolves feed simulations. When a
regulated product is built on MIME, Vesalius is SOUP of SOUP, beside MADDENING. When a product built on
Isaac for Healthcare reads Vesalius materials, Vesalius is SOUP directly. In both cases a wrong value (a
transcription error, a wrong unit, a parameter set read in the wrong convention, a material resolved to
the wrong region) reaches the device's computation silently. That is the failure this documentation
architecture is built around.

**What is different from MADDENING and MIME.** Four things.

1. **Vesalius ships data as well as code.** Its library of materials is part of what a manufacturer would
   assess. The question for the data is not "does the solver converge" but "is this the value the cited
   source gives, in the stated units, under the stated conditions".
2. **There is no physics solver.** The code computes little: unit conversion, mixing rules, interpolation,
   composition into spectra, resolution of which material owns a point, check points and sampling. Its
   documentation replaces the algorithm guide with a normative specification, a short method guide and
   model-family definitions (sections 4 and 5).
3. **The read side must work without Vesalius code.** A C++ simulator reading a record or a stage is a
   consumer too. So the specification, not the Python package, is the primary artefact, and its
   conformance suite is the primary verification evidence (section 6).
4. **Records carry their own verification.** A model parameter set carries check points that any consumer
   evaluates before using it, so a reader that never ran the conformance suite still fails loudly on a
   convention mismatch. A convention witness from the source does the same for extraction: the parameters
   must reproduce a response the source reports (architecture draft section 4.6).

**Model-assisted curation.** Language models may help draft library records, through deterministic MCP
tools driven by the user's own agent and key. That tooling sits outside the SOUP package and never on the
read side; every assisted value carries its quote and document hash, and nothing enters a release without
a human review record (architecture draft section 8; constraints 20 to 22).

**Calibration.** Like MADDENING's, this plan is calibrated to the most demanding plausible downstream use,
IEC 62304 Class C (MADDENING `DOCUMENTATION_ARCHITECTURE.md`, Executive Summary). The library is small, so
the evidence is small; the rigour per item is not lower.

**Relationship to MADDENING's and MIME's plans.** This plan adopts their conventions wherever they apply:
the regulatory boundary language, the anomaly schema and severity definitions, the CHANGELOG format, the
commit prefixes, the SOUP package template, configuration management and the QMS model. Where Vesalius
adopts something unchanged, this document says so and points to the MADDENING section. Where Vesalius
differs, the difference and its reason are written here. The definitions a reader needs to assess
Vesalius (severity, the anomaly schema, what Vesalius warrants about its data) are repeated here, so the
document can be read on its own.

This plan is informed by IEC 62304:2006+AMD1:2015, ISO 14971:2019, ASME V&V 40-2018, EU MDR
(EU 2017/745), MDCG 2019-11, MDCG 2019-16 and EN ISO 13485:2016, as MADDENING's is.

---

## Table of Contents

1. [Inheritance from MADDENING and MIME](#1-inheritance-from-maddening-and-mime)
2. [Documentation Structure](#2-documentation-structure)
3. [Regulatory Boundary Language](#3-regulatory-boundary-language)
4. [The Specification](#4-the-specification)
5. [The Method Guide, Model Families and the Material Library](#5-the-method-guide-model-families-and-the-material-library)
6. [Verification](#6-verification)
7. [Versioning and Stability](#7-versioning-and-stability)
8. [Anomaly Management](#8-anomaly-management)
9. [Compliance as a Feature: Working with MADDENING and MIME Metadata](#9-compliance-as-a-feature-working-with-maddening-and-mime-metadata)
10. [SOUP Package](#10-soup-package)
11. [IEC 62304 Lifecycle Mapping](#11-iec-62304-lifecycle-mapping)
12. [Configuration Management](#12-configuration-management)
13. [EU MDR, MDCG 2019-11 and QMS](#13-eu-mdr-mdcg-2019-11-and-qms)
14. [Downstream Integration](#14-downstream-integration)
15. [Project Constraints](#15-project-constraints)

Appendices: [A: Implementation Priority](#appendix-a-implementation-priority),
[B: Bootstrap Checklist](#appendix-b-bootstrap-checklist).

---

## 1. Inheritance from MADDENING and MIME

Vesalius adopts conventions, not code. Section numbers refer to MADDENING's `DOCUMENTATION_ARCHITECTURE.md`.

| MADDENING section | Vesalius treatment | Difference |
|---|---|---|
| 1. Documentation structure | Adapted (section 2) | smaller; a specification, family definitions and a data guide in place of the algorithm guide |
| 2. Regulatory boundary language | Adapted (section 3) | Apache-2.0, so no LGPL replaceability statement; a data statement added |
| 3. Algorithm documentation standards | Replaced (sections 4, 5) | a normative specification for the read side; a method guide for write-side computations; a definition per model family |
| 4. V&V documentation hooks | Adapted (section 6) | conformance, golden vectors, check points, transcription and fit-reproduction evidence in place of analytical benchmarks |
| 5. Versioning and API stability | Extended (section 7) | four version lines: package, schema, family, material |
| 6. UQ documentation | Adapted (section 9) | material statistics and uncertainty structures become UQ inputs downstream |
| 7. Contributor documentation | Extended (`CONTRIBUTING.md`) | data entry, data attestation, takedown, family admission, schema changes, sign-off |
| 8. README | Adopted | |
| 9.1 NodeMeta | Not applicable | no nodes; material provenance, family definitions and method metadata take its place |
| 9.2 Provenance | New role (section 9) | Vesalius supplies input provenance to MADDENING's run provenance |
| 9.3 Verification registration | Adopted pattern | `VES-VER-` identifiers, registered without a MADDENING import |
| 9.5 Stability machinery | Adopted concept | the same four levels, on schema fields and API surfaces; family versions are frozen |
| 9.7 Anomaly management | Adopted (section 8) | same schema, fields, enums, lifecycle and gate; data and family anomalies defined |
| 9.8 ISO 14971 hooks | Adapted (section 8.4) | quantitative conditions, structured proxy declarations and qualitative applicability hints on materials |
| 9.9 Usability | Adapted (section 3.5) | the main use errors are applying a value outside its conditions and reading parameters in the wrong convention |
| 10. SOUP package | Adapted (section 10) | per component: core, families, library; SOUP of SOUP is numpy, a JSON Schema validator and OpenUSD |
| 11. IEC 62304 mapping | Adapted (section 11) | |
| 12, 13. EU MDR, MDCG 2019-11 | Referenced (section 13) | |
| 14. Configuration management | Extended (section 12) | a content hash per material; frozen family versions; a DOI per library release |
| 15. QMS compatibility | Inherited (section 13) | |
| 16. Downstream inheritance | Reversed (section 14) | Vesalius is upstream of MIME and beside MADDENING |

**No runtime dependency on MADDENING.** MADDENING's compliance namespace is importable without JAX, but
installing MADDENING installs JAX, and its licence is LGPL. A Vesalius runtime dependency on it would
contradict Vesalius's purpose (a neutral, permissive layer that C++ and PyTorch stacks can adopt) and
would invert the stack. Vesalius therefore keeps its own small compliance module whose records have the
same shape as MADDENING's, and MIME, which depends on both, translates between them (section 9).

**A development-time dependency on MADDENING's validator.** Vesalius's CI validates its anomaly registry
with MADDENING's validator (`python -m maddening.compliance check-anomalies`), in a CI job of its own, so
the three registries are held to one implementation of one schema. This is a development dependency only:
nothing in the Vesalius package imports MADDENING, and nothing installed by `pip install vesalius` depends
on it.

---

## 2. Documentation Structure

This repository holds the core and, at first, the family packages:

```
Vesalius/
├── README.md                          # what it is, status, disclaimer, documentation table
├── DOCUMENTATION_ARCHITECTURE.md      # this document
├── CONTRIBUTING.md                    # constraints, sign-off, ID prefixes, data and family rules, schema changes
├── SECURITY.md                        # vulnerability reporting; trusted-input boundary
├── CHANGELOG.md                       # Keep a Changelog + Schema, Families, Data, Verification, Security, Known Anomalies
├── CITATION.cff                       # from the first release
├── LICENSE                            # Apache-2.0
├── design/
│   └── ARCHITECTURE_DRAFT.md          # architecture concept
├── .github/
│   ├── ISSUE_TEMPLATE/anomaly.yml
│   └── pull_request_template.md       # sign-off and data attestation
│
├── docs/
│   ├── index.md
│   ├── specification/                 # NORMATIVE; versioned with the schema (section 4)
│   │   ├── record_format.md           # plain records: structure, value forms, sections, fields, units
│   │   ├── provenance.md              # provenance fields, conditions vocabulary, proxies, tiers
│   │   ├── uncertainty.md             # statistics; the four uncertainty structures; sampling rules
│   │   ├── model_families.md          # what a family definition must fix; identifiers; check points
│   │   ├── fits_and_reference_data.md # fit records, reference data, the fit-reproduction rule
│   │   ├── geometry.md                # layered paths, region binding, label volumes, field overrides
│   │   ├── usd_binding.md             # USD schemas, binding purpose, layered-path form, layers
│   │   ├── read_side_contract.md      # what any reader must do, including when to refuse
│   │   ├── mixing_rules.md            # one declared rule per field
│   │   └── changes.md                 # schema version history
│   ├── method_guide/                  # write-side computations (section 5.1)
│   │   ├── _template.md
│   │   └── ...                        # one per method: unit conversion, composition, derivations, sampler
│   ├── user_guide/
│   │   ├── installation.md
│   │   ├── quickstart.md
│   │   └── reading_without_vesalius.md   # the read side with a JSON parser or USD alone
│   ├── developer_guide/
│   │   ├── documentation_standards.md
│   │   ├── testing_standards.md
│   │   ├── schema_change_policy.md
│   │   └── release_process.md
│   ├── validation/
│   │   ├── known_anomalies.yaml       # VES-ANO-* registry (section 8)
│   │   ├── verification.md            # what is verified, and how (section 6)
│   │   ├── soup_package.md            # from the first release (section 10)
│   │   └── sbom/                      # from the first release (section 12)
│   ├── regulatory/
│   │   ├── intended_use.md
│   │   ├── downstream_integration.md
│   │   └── iec62304_mapping.md
│   └── bibliography.bib               # every source the specification, methods or families cite
│
├── src/vesalius/                      # core, including `python -m vesalius check`; layout in the architecture draft, section 7.1
├── mcp/                               # vesalius-mcp, the MCP server: a separate distribution (architecture draft section 8)
├── families/                          # family packages, one directory per namespace and family (section 5.2)
│   └── vesalius/mechanical/<family>/
│       ├── definition.md              # NORMATIVE for that family version
│       ├── vectors/                   # golden test vectors, frozen per version
│       └── reference.py               # reference implementation (numpy)
├── tests/
│   ├── conformance/                   # VES-VER-* read-side cases (language-neutral data + Python runner)
│   ├── families/                      # vectors against reference implementations
│   └── methods/                       # method verification
└── scripts/                           # CI checks (section 6.5)
```

The library lives in a repository of its own (name to be chosen), with its own data licence. Its releases
are static archives, published on GitHub and archived on Zenodo with a DOI; there is no hosted service
(architecture draft section 6.7):

```
<library repository>/
├── README.md, LICENSE (data licence), CHANGELOG.md, CITATION.cff
├── sources.yaml                       # the source registry (architecture draft section 6.1)
├── bibliography.bib
├── materials/                         # one plain record per material (the source of truth)
├── reference_data/                    # shipped reference curves and spectra, with their licences
├── gold_set/                          # extraction gold set: DOIs, document hashes, verified extractions (section 6.2)
├── generated/                         # GENERATED by the build from the records, never edited
│   ├── usd/                           # self-contained USD layers
│   ├── cards/                         # one material card per record (architecture draft section 6.6)
│   └── index.json                     # every record's identifier, version, hash, sections, tier, licence
├── docs/
│   ├── data_entry_standard.md
│   ├── review_process.md
│   └── takedown.md
└── scripts/                           # policy checks; record checks come from `vesalius check` (section 6.5)
```

Rules for both trees:

- **A folder is created when its first real document arrives.** Empty folders are not committed. The trees
  above are the target, not the current state.
- **Generated files are never hand-edited.** The plain records are the single source of truth (architecture
  draft open question 1); CI regenerates the USD layers, cards and index and fails if they differ, as
  MADDENING does for its stability report.
- **Tooling** follows MADDENING and MIME: Markdown with MyST, Sphinx once a site is worth building,
  Pandoc-style `[@Key]` citations against the repository's `bibliography.bib`.

---

## 3. Regulatory Boundary Language

### 3.1 Platform positioning statement (`docs/regulatory/intended_use.md`)

> Vesalius is an open material schema and a software toolkit for describing the physical properties of
> tissues, phantoms and devices for simulation. It is research software distributed under the Apache
> License 2.0.
>
> **Vesalius is not a medical device** as defined by EU MDR (EU 2017/745) Article 2(1). It has no medical
> purpose. It does not diagnose, monitor, predict, treat or alleviate disease, and it makes no clinical
> interpretation of anything it stores. Under MDCG 2019-11 it is general-purpose software, comparable to a
> units library or a materials database.
>
> When incorporated into a regulated medical device, Vesalius is classified as SOUP under IEC 62304. The
> device manufacturer bears full responsibility for assessing its suitability for their context of use.

### 3.2 Data statement

This is the statement MADDENING does not need and Vesalius does:

> The values in the Vesalius material library are **declarations taken from cited sources**, or fits to
> cited data. Vesalius warrants that each value is what its source gives (or what its recorded fit
> produces), converted correctly to SI, with the conditions, statistics and proxy status the record
> states; and that each model parameter set reproduces its check points under the family definition it
> names. Vesalius does **not** warrant that a value describes any particular patient, tissue sample,
> phantom batch or device, nor that a source is itself correct or current. Whether a library value is
> applicable to a given use is the user's and the manufacturer's judgement.
>
> Many values come from stand-ins (another species, another site, a cadaver, a phantom). Each record says
> so, per field. A reference-only record publishes no values; its values are whatever the user fills in
> from their own copy of the source.
>
> Some values are drafted with the help of a language model. Each such value says so, with the quote and
> the document it was read from, and every value, assisted or not, is checked against its source by a
> named reviewer before release.
>
> Biocompatibility fields are information about what has been reported for a material. They are never a
> biocompatibility assessment or a safety claim. A manufacturer performs their own ISO 10993 evaluation.

### 3.3 Cybersecurity boundary statement (MDCG 2019-16)

> Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation
> beyond validating records against the record schema. A USD stage can pull in other files through its
> composition (sublayers, references, payloads) and through the host's asset resolver, so reading a stage
> may read any file that stage names. Every USD layer Vesalius ships is self-contained (no composition arcs,
> no asset paths), so reading a library layer reads that file alone. Vesalius itself makes no network requests and runs no code from the
> files it reads: records and family vectors are data, and family reference implementations are code
> shipped in the package, never loaded from a record. Loading third-party records and stages, and the
> security of the asset resolver, are the responsibility of the integrating application.

### 3.4 Licence note

Apache-2.0 is permissive: no copyleft obligation follows a product that incorporates Vesalius's code, and
the licence includes an express patent grant. It is compatible with use from MIME and MADDENING
(LGPL-3.0-or-later) and with contributions to Isaac for Healthcare. The library's data is under its own
data licence, stated on each record (architecture draft section 6.4). This is a description, not legal
advice.

### 3.5 Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Family definitions and reference implementations agree | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | golden vectors (section 6.4) |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, fit reproduction, data checks |
| A consumer's own implementation of a family | downstream user | IEC 62304 Clause 5.6 (their own) | the record's check points; the family's golden vectors |
| Choosing a material, judging its applicability and its proxies | downstream user | ASME V&V 40 (model inputs) | the user's input justification |
| Measuring the language model an agent uses for extraction, before relying on it | the curator using it | none: curation tooling is outside the SOUP package | gold-set score; review of every value |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

The use errors Vesalius can make less likely are applying a value outside its conditions (a different
temperature, frequency, wavelength, species or tissue state), using a proxy without knowing it, and reading
a parameter set in another convention. Vesalius makes conditions and proxies machine-readable so an
integrator can check them (section 8.4), and makes a convention mismatch fail at the check points.

---

## 4. The Specification

The specification in `docs/specification/` is the primary artefact. It defines the record format, the USD
binding and everything a reader must do, in prose and tables, independently of the Python package. It is
**normative**: where the Python reader and the specification disagree, the reader is wrong.

| Document | Defines |
|---|---|
| `record_format.md` | the plain record: identity, schema version, content hash, sections; every field with its SI unit, value form, default, allowed tokens and stability level; the five value forms |
| `provenance.md` | provenance fields; the extraction methods; the conditions vocabulary and its ontology identifiers; proxy declarations; the three tiers; the source registry's fields and redistribution statuses; evidence, assistance and search records |
| `uncertainty.md` | the statistics block; the four uncertainty structures; admissibility; the sampling rules, including refusal |
| `model_families.md` | the identifier form; what a family definition must fix (architecture draft section 4.5); check points in records and the tolerance rule; convention witnesses; refusal on an unknown family or version or a failed check point |
| `fits_and_reference_data.md` | the fit record; reference data and its link to a fit; the fit-reproduction rule and "not checked" |
| `geometry.md` | layered paths; region binding; label volumes; field overrides; precedence; nested regions and background |
| `usd_binding.md` | the API schemas; attribute names; the binding purpose; the USD forms of layered paths and of parameter sets, statistics and check points; taking provenance from the layer that supplies the value |
| `read_side_contract.md` | the read procedure (architecture draft section 7.5), in order, and every case in which a reader must refuse |
| `mixing_rules.md` | the rule each field declares, with its equation |
| `changes.md` | each schema version, what changed, and the conformance cases that came with it |

Rules:

- **Every normative statement has a conformance case** (section 6.1). A statement without one is marked
  "not yet covered".
- **A change to the specification is a schema change** (section 7.2), whatever the Python code does.
- **The Python reader is one implementation** of the specification, verified like any other.
- **Plain and USD forms say the same thing.** Every field has both forms in the specification, and the
  conformance suite checks that they agree.
- **A family's definition is normative for that family version** and lives with the family (section 5.2),
  not in the specification. The specification says what every definition must contain.

---

## 5. The Method Guide, Model Families and the Material Library

### 5.1 Method guide

The write side computes a few things: unit conversions, composition into spectra, derived values (the
Grüneisen parameter from thermal expansion, sound speed and heat capacity), the mixing rules, check-point
baking and the reference sampler. Each has a method guide document, adapted from MADDENING's algorithm
guide template (MADDENING section 3):

```markdown
---
bibliography: ../bibliography.bib
---

# [Method name]

**Method ID**: `VES-MTH-[XXX]`
**Stability**: [experimental | provisional | stable | deprecated]
**Version**: [semantic version of this method]

## Summary
## Equations
## Implementation Mapping
| Term | Implementation | Notes |
## Assumptions
## Validity
| Quantity | Range | Basis |
## Known Limitations
## References
## Verification Evidence
## Changelog
```

The Implementation Mapping is mandatory and checked in CI, as in MADDENING (`scripts/check_impl_mapping.py`).

**Extraction procedures are method entries too.** Each prompt for model-assisted extraction (architecture
draft section 8) is a versioned `VES-MTH-` entry. Its Verification Evidence is its gold-set score, per field
and per model tested (section 6.2).

### 5.2 Model-family definitions

Each family version has a `definition.md`, normative for that version, with these sections:

```markdown
# [Family identifier, e.g. vesalius.mechanical.ogden_incompressible.v1]

**Status**: [admitted | deprecated]
**Named consumer**: [who needed it, and for what]

## Kinematics and outputs        # input measure, output measure, loading modes covered
## Equations                      # normative
## Parameters                     # name, unit, meaning, order
## Admissibility                  # constraints on a parameter set
## Golden test vectors            # files in vectors/, precision, what each case exercises
## Reference implementation       # Implementation Mapping, as in 5.1
## Known conventions elsewhere    # how named solvers and papers write the same model, and how they differ
## References
```

A definition never changes once released. A correction is a new version, and the old one is deprecated
with a pointer to it. "Known conventions elsewhere" is informative: it is what an exporter's conversion and
the convention checker (architecture draft section 10) are built from.

### 5.3 The material library

Each library material has an identifier `vesalius/VES-MAT-[XXXX]` (architecture draft section 4.1) and one
plain record in the library repository. Its USD layer and its **material card** (architecture draft section
6.6) are generated from that record. The card's prose sections are fields of the record: motivation, uses
and limitations, and maintenance are written by the curator; the rest is assembled from the other fields.

**Data entry standard** (`docs/data_entry_standard.md` in the library repository). Every value carries:

| Field | Required | Notes |
|---|---|---|
| value | yes, unless the tier is reference-only | one of the five forms (architecture draft section 4.4) |
| unit | implied | always the SI unit the specification fixes for the field |
| kind | yes | declared, measured, fitted or derived |
| source | yes | a key in `sources.yaml`, with a locator: table, figure, page or equation |
| extraction | yes | table, text, digitised figure (tool and digitising error), supplementary dataset (licence), own measurement, derivation (method ID) or fit (fit record) |
| conditions | where the source states them | from the conditions vocabulary; anatomical site and species as ontology identifiers |
| statistics | yes for scalars, unless the source gives a single exact value | number of specimens and donors, mean, standard deviation, minimum, maximum, distribution, basis; at least a range with its basis |
| uncertainty structure | yes for parameter sets | `ensemble`, `multivariate_normal`, `independent` (with a justification) or `none` |
| check points | yes for parameter sets | computed by the family's reference implementation; never typed in |
| fit record | yes for fitted values | reference data (identifier, or DOI and hash), procedure, coverage, residual |
| convention witness | yes for parameter sets taken from a source | a response the source reports, with its locator, that the parameters must reproduce (architecture draft section 4.6); without one, not admitted |
| proxy | yes | none, or: a stand-in for what, and why; per section or field |
| tier | yes | shipped, reference-only or private |
| evidence | yes when a model assisted; recommended otherwise | the verbatim quote, its locator and the SHA-256 of the document copy; for a digitised figure, the locator and the hash. Quotes are not published for reference-only values |
| assistance | yes when a model assisted | tool, model and provider as reported, prompt version (`VES-MTH-` entry and version), date |
| search record | yes for statistics pooled across sources | queries, databases, date, inclusion criteria |
| reviewer, date and ORCID | yes | who checked the value against the source, and which checklist items: value, unit, conditions, statistic, primary or cited, family and witness |

**What review means.** A second person (or the same person on a later day, recorded as such) reads the
source at the locator and confirms the value, the unit conversion, the conditions and the proxy status.
The record of that check is part of the evidence (section 6.3). Agreement with another database is not a
review. For a model-assisted value, the reviewer reads the rendered page at the locator, not only the
quote, and confirms the quote is visible there; hidden text in a document can pass a text-layer check.

**Source registry.** `sources.yaml` holds one entry per source: citation key, DOI or URL, the licence of
the publication and of any dataset, a redistribution status (permitted; values only; not permitted;
unknown) with its reason, who judged it and when, and the source's role. A value from a source whose
status is not permitted or unknown is reference-only.

**Plausibility and consistency checks** run in CI on the whole library: physical bounds per field (density
and sound speed positive and within broad bounds for condensed matter); consistency between related fields
(impedance against density times sound speed; a derived Grüneisen parameter against one given directly);
admissibility of every parameter set and every ensemble member; completeness of provenance. A check failure
blocks the merge.

**What the library is not.** It is not a database of everything published. A material is added when a
consumer needs it, with the sources that consumer relies on.

---

## 6. Verification

Vesalius has no physics to converge, so its verification is of five other kinds. Each verification item has
an identifier `VES-VER-[XXX]`.

### 6.1 Conformance suite (the read side)

Small cases, each with expected answers: the material bound to a prim or a path interval; a property at a
point; a property at a wavelength or frequency; the owner of a point inside nested regions; the provenance
of an overridden value, including USD's dictionary-merge trap; equality of a record's plain and USD forms;
refusal on an unknown family or version; refusal on a failed check point; refusal to sample an undeclared
uncertainty structure. The cases and expected answers are data files, so a C++ or other reader can run them
without Python. The Python reader runs them in CI.

### 6.2 Method verification

Each method guide entry has tests against exact or analytical results: unit conversions exactly; mixing
rules against closed-form layered media (series and parallel conduction, effective sound speed of a
layered stack); composition against worked examples in its sources; the reference sampler's moments and
its rejection count against known cases. Extraction procedures are scored against the gold set by a
deterministic scorer, per field and per model tested; the gold set lists papers by DOI and document hash,
with PDFs only where their licence allows (architecture draft section 8.6).

### 6.3 Data verification

- the transcription review record for every value (section 5.3);
- the plausibility, consistency and admissibility checks (section 5.3);
- **check points recomputed**: every stored check point is recomputed with the family's reference
  implementation and must match;
- **fit reproduction**: every fitted parameter set is evaluated against its reference data and must achieve
  its stated residual. Where the reference data are not shipped, the result is "not checked", reported as
  such, never as a pass;
- **convention witnesses**: every parameter set taken from a source reproduces its witness under its
  family version. Where the witness cannot be shipped, the curator's check at review is recorded and the
  public check reports "not checked";
- **evidence**: every model-assisted value has a quote, a locator and a document hash. The quote is checked
  against the document when the draft is made, and again by the reviewer against their own copy, whose hash
  must match;
- a round trip: write a record, read it back, generate its USD form, read that back, compare every value,
  provenance field and check point.

### 6.4 Model-family verification and admission

- Each family's reference implementation reproduces its golden vectors at the stated precision, including
  the admissibility cases.
- Golden vectors are frozen per family version. CI fails if a released version's vectors change.
- Each conversion an exporter offers to a solver's convention has its own vectors showing the converted
  parameters reproduce the family's outputs.
- **Admission.** A family enters with a definition (section 5.2), golden vectors, a reference
  implementation, and a named consumer. A family with no consumer for two releases is deprecated. The same
  rules bind third-party namespaces that want to be listed.

### 6.5 CI checks

**Record checks are a command in the core**, `python -m vesalius check <directory>`, so that the curated
library and any other publisher run exactly the same checks (architecture draft section 6.7):

| Check | Verifies |
|---|---|
| schema | records validate against the record schema; identifiers are namespaced |
| provenance | the fields of section 5.3 are complete |
| plausibility | physical bounds; consistency between related fields; admissibility of every parameter set and ensemble member; units |
| check points | stored check points equal the reference implementation's |
| fit reproduction | every fit reaches its stated residual; "not checked" is counted and reported |
| generated | USD layers, cards and the index equal what the records produce |
| self-contained | shipped USD layers have no composition arcs and no asset paths |
| witness | parameter sets reproduce their convention witness; "not checked" is counted and reported |
| evidence | model-assisted values carry a quote, a locator, a document hash and an assistance record; with the document present, the quote exists at the locator and contains the value's numbers |
| release (`--release`) | fails on any value without a review record, and on any draft |

In this repository:

| Script | Checks |
|---|---|
| `scripts/check_anomalies.py` | the registry against the schema of section 8, prefix `VES-ANO-`, by delegating to MADDENING's validator (section 8.1) |
| `scripts/check_citations.py` | every `[@Key]` in the specification, methods and families exists in `bibliography.bib` |
| `scripts/check_impl_mapping.py` | every function named in a method guide or family definition exists |
| `scripts/check_families.py` | reference implementations reproduce their vectors; released vectors are unchanged; every family has a named consumer |
| `scripts/check_signoff.py` | every commit in a pull request carries a sign-off (section 15) |

In the library repository, CI runs `vesalius check` on every pull request and adds the curated library's
policy checks:

| Script | Checks |
|---|---|
| `scripts/check_sources.py` | every source key exists; no shipped value comes from a source whose redistribution status is not permitted or unknown; every record states its licence |
| `scripts/check_signoff.py` | sign-off and data attestation on every pull request |

### 6.6 What this verification does not provide

It does not show that any library value describes a patient, a tissue sample or a phantom batch, nor that
a proxy is adequate for a use. That is validation of an input for a context of use, which belongs to the
user and the manufacturer. Every verification document states this in a "Scope and Limitations" section,
as MADDENING's do.

---

## 7. Versioning and Stability

### 7.1 Four version lines

| Version | Tracks | Where it appears |
|---|---|---|
| Package version (SemVer) | the Python package | `pyproject.toml`, CHANGELOG, SOUP package |
| Schema version (SemVer) | the specification, the record schema and the USD schema | `docs/specification/changes.md`; recorded on every material |
| Family version | one model family's definition and vectors; frozen once released | the family identifier (`...v1`); recorded on every parameter set |
| Material version | one library material's values | the record; its card; its content hash (section 12); the library release that carries it |

Schema: **major** for a removed or renamed field, a changed unit or a changed meaning; **minor** for a new
optional field, section, token or value form; **patch** for wording only. A material: **major** when a
value changes beyond its previous statistics, a condition or proxy status changes, or a parameter set moves
to another family version; **minor** for a new value or section; **patch** for provenance wording. A
family: any change is a new version.

### 7.2 Changes to the schema

A schema change needs, in one pull request: the specification text, the conformance cases, the record
schema and USD schema files, the reader change, a `changes.md` entry, and a CHANGELOG entry under
**Schema**. Removal follows the stability levels below.

### 7.3 Stability levels

The same four as MADDENING (section 5): experimental, provisional, stable, deprecated. They apply to schema
fields and sections as well as Python API surfaces. A field starts experimental and becomes stable when it
has conformance cases, at least one library material uses it, and it has not changed for one minor schema
version. Families have no stability levels: a released family version is frozen, and is either admitted or
deprecated.

### 7.4 CHANGELOG and commit prefixes

`CHANGELOG.md` follows Keep a Changelog with MADDENING's extra sections **Verification**, **Security** and
**Known Anomalies**, plus Vesalius's own: **Schema**, **Families** and **Data**. The library repository
keeps its own CHANGELOG with **Data** and **Known Anomalies**.

Commit prefixes are MADDENING's (`feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `verify`, `break`,
`deprecate`, `security`) plus `schema:` for a schema change, `family:` for a family definition or vectors,
and `data:` for a library change.

---

## 8. Anomaly Management

### 8.1 Adopted unchanged

Vesalius adopts MADDENING's anomaly management (MADDENING section 9.7) unchanged: the registry at
`docs/validation/known_anomalies.yaml`; the record fields `anomaly_id`, `title`, `description`, `severity`,
`safety_relevance`, `safety_relevance_rationale`, `affected_components`, `affected_versions`,
`workaround`, `resolution_status`, `resolution_version`, `github_issue`, and the optional `verification`
and `residual_risk`; the enums; the PEP 440 convention for `affected_versions`; the three-phase lifecycle
(issue, then a manual registry entry, then CI checks); the three-tier release gate; and the rule that
entries are never deleted. The registry's version field is `vesalius_version`. Library anomalies are
recorded in the same registry, naming the library release in their description and the material in
`affected_components`.

The schema is kept identical on purpose, so that a manufacturer can collect MADDENING, MIME and Vesalius
entries into one risk file, and so that one validator can check all three. The one difference is the
version field, which MADDENING's Appendix F says each project names after itself: `vesalius_version`.

Vesalius's CI checks the registry with MADDENING's validator:
`python -m maddening.compliance check-anomalies docs/validation/known_anomalies.yaml --prefix VES-ANO-`
(section 1).

**This depends on a MADDENING change.** Checked 2026-10-11 against MADDENING `f2aa830e`: the validator
accepts no top-level version field except `maddening_version`
(`MADD:src/maddening/compliance/_validate.py`, `_KNOWN_TOPLEVEL_FIELDS`), so it refuses `vesalius_version`,
and MIME's registry fails it for the same reason. That contradicts MADDENING's own Appendix F, which has
downstream registries carry their own version field and pass the validator. Accepting a project version
field has been requested of MADDENING and is to be prioritised there; until it lands, the CI job is
expected to fail on this one field.

### 8.2 Severity, applied to data and families

The definitions are MADDENING's (section 9.7, "Severity"), repeated here so this document stands alone. A
**wrong result** is a value the library returns, stores or resolves that differs from what Vesalius
documents for it. For data, "what Vesalius documents" is: the cited source, at the stated locator,
converted to the specification's SI unit, under the stated conditions, resolved as the specification
says. For a family, it is the family's definition. A result is **silent** when no exception and no warning
accompanied it. **A silent wrong result is never minor.**

| Severity | Definition, with examples |
|---|---|
| `critical` | A silent wrong result that a default configuration reaches, that a user cannot detect from anything Vesalius returns, and that no workaround avoids short of not using the feature. Examples: the reader resolves the wrong material for nested regions in every stage; a reference implementation disagrees with its definition and the check points baked from it carry the error into every record. |
| `major` | Any other silent wrong result. Examples: a library value that differs from its source; a wrong unit conversion; conditions or proxy status recorded wrongly; provenance attributed to the wrong layer; a sampler that ignores a declared structure; a model-assisted value its quote does not support. A loud failure whose only workaround is not to use the feature. |
| `minor` | A loud failure with a workaround. A wrong statement in documentation where stored values are still right. A defect in performance. A cosmetic defect. |
| `enhancement` | Not a defect: a request for behaviour Vesalius never claimed. |

**Not an anomaly:**

- a value that faithfully transcribes a source that later proves wrong or is superseded. That is a data
  update, recorded under **Data** in the library CHANGELOG with a new material version. If the source is
  withdrawn for error, the update is made promptly and noted in the release notes;
- a licensing problem with a shipped value. It is handled by the takedown procedure (`CONTRIBUTING.md`),
  which moves the value to reference-only; the values themselves are not wrong.

A refusal (an unknown family, a failed check point, an undeclared uncertainty structure) is the
specification working, not a defect, unless the refusal is itself wrong.

### 8.3 Identifiers and components

| Category | Prefix | Example |
|---|---|---|
| Anomalies | `VES-ANO-` | `VES-ANO-001` |
| Verification items | `VES-VER-` | `VES-VER-001` |
| Library materials | `VES-MAT-` | `VES-MAT-0001` |
| Methods | `VES-MTH-` | `VES-MTH-001` |

Material identifiers are namespaced, `<namespace>/<local id>`; in the curated library the local identifier
is the `VES-MAT-` catalogue number (`vesalius/VES-MAT-0001`). This registry covers Vesalius's own
components, so `data:VES-MAT-0003` is unambiguous; another publisher tracks anomalies in its own records.
Model families are named by their own identifiers (`vesalius.mechanical.ogden_incompressible.v1`) and need
no prefix.

`affected_components` names what is affected without new fields (which would break schema compatibility):
`schema:VesaliusAcousticAPI`, `reader:resolve`, `method:VES-MTH-002`,
`model:vesalius.mechanical.ogden_incompressible.v1`, `data:VES-MAT-0003`.

### 8.4 ISO 14971 inputs

MADDENING separates quantitative regimes from qualitative hazard hints (its section 9.1). Vesalius keeps the
same split on materials, and adds proxy declarations, which are structured rather than free text:

| On a material | Nature | Example |
|---|---|---|
| conditions and statistics | quantitative | measured at 37 °C, 1 to 10 MHz; n = 12 specimens from 4 donors, mean 1575 m/s, standard deviation 18 m/s |
| a fit's coverage | quantitative | uniaxial tension, stretch 1.0 to 1.3, strain rate 0.01 per second |
| proxy declarations, per section or field | structured | acoustic section: porcine tissue standing in for human tissue, because no human data at the stated frequency |
| applicability hints | qualitative | "adult human liver, ex vivo; not for fatty or fibrotic liver" |

A given limitation appears in exactly one of these. All are technical statements about the data, not
clinical risk assessments; that boundary is MADDENING's (section 9.8) and is adopted unchanged.

---

## 9. Compliance as a Feature: Working with MADDENING and MIME Metadata

MADDENING's and MIME's compliance architecture documents **code**: what each node computes, how it was
verified, where it is known to fail. Nothing in it documents the **inputs**: where the physical parameter
values a simulation used came from, how uncertain they are, and whether they apply. ASME V&V 40 treats model
inputs as a credibility factor of their own (recalled; check the clause before citing). Vesalius carries
exactly that information, so it can fill the gap. This section says where that fits and where it does not.

### 9.1 Where it fits

| Fit | What Vesalius provides | What uses it | Who translates |
|---|---|---|---|
| **Input provenance for a run** (clear) | `collect_material_inputs(...)`: every property value a set of prims or path intervals resolves to, with material identifier and version, content hash, kind, source, statistics, conditions, proxy status, tier, family version, check-point result, fit-reproduction and witness status, whether a model assisted, and the layer or overlay it came from. Exported as JSON and as a Markdown "material input sheet" | MADDENING's `SimulationProvenance.custom` (`MADD:src/maddening/core/compliance/provenance.py`); a credibility assessment's model-input evidence; MADDENING's context-of-use template | MIME writes the record into the run's provenance |
| **Uncertainty inputs** (partial) | statistics for scalars; uncertainty structures for parameter sets | MADDENING's `UncertainParameter` (nominal, lower, upper, units, description) for UQ, which describes one parameter at a time | MIME builds `UncertainParameter` from scalar statistics and `independent` structures. Joint structures have been requested of MADDENING; until then MIME samples them with Vesalius's reference sampler |
| **Operating-point checks** (clear) | conditions, material values and fit coverage | MADDENING's `ValidatedRegime` checks against computed operating points (Reynolds number, Mach number) | MIME |
| **One anomaly schema** (clear) | `VES-ANO-` entries in MADDENING's format | one combined risk file; MIME entries can cite `VES-ANO-` entries as they cite `MADD-ANO-` ones | none needed |
| **Biocompatibility** (partial) | a material's biocompatibility section | MIME's `BiocompatibilityMeta` (materials, tested flags, hazard hints) derived from a body's materials instead of typed in | MIME |
| **References** (clear) | source registry keys | MADDENING's `Reference(key, description)` | MIME |

### 9.2 Where it does not fit

- **A Vesalius dependency on `maddening.compliance`**: ruled out in section 1.
- **Vesalius nodes or benchmarks**: Vesalius simulates nothing.
- **Clinical applicability**: Vesalius can record conditions, proxies and hints; deciding that a value
  applies to a patient stays with the user and the manufacturer (section 3.2).

### 9.3 What this would add to Vesalius

A small `vesalius.compliance` module, pure Python, with no dependency beyond the core:

- the anomaly record and registry check in MADDENING's shape (section 8);
- `collect_material_inputs` and the material input sheet;
- content hashes for materials (section 12).

This is a proposal. It is cheap because the provenance is already in the data model; the module only
gathers it. Its value is that a simulation's inputs become as traceable as its code, automatically.

---

## 10. SOUP Package

`docs/validation/soup_package.md`, from the first release, follows MADDENING's template (section 10). A
manufacturer assesses only the components it uses, so the package is organised per component:

| Component | Licence | Assessed when |
|---|---|---|
| Core | Apache-2.0 | always |
| Each family version | Apache-2.0 | when a product evaluates parameter sets of that family |
| Each library release | its data licence | when a product uses its materials; otherwise only the product's own records |

Contents, with the Vesalius-specific additions:

1. **Software identification**: name, version, release date, Apache-2.0, repository, PyPI hashes, Python
   versions; **plus** the schema version and the hash of the schema archive; the family versions included
   and the hash of their vectors; the library release, its DOI, its data licence and the hash of its
   archive.
2. **Functional description**: the reader, the writer, the methods, the families, the reference sampler,
   the library; **capabilities not provided**: no clinical interpretation; no assurance that a value or a
   proxy applies to a patient; no validation of files from third parties; no production-grade or
   differentiable evaluation of model families.
3. **Known anomalies**: summary counts, split into code, schema, family and data anomalies (by
   `affected_components`).
4. **Verification evidence**: the conformance suite, method, family and data verification, with pass counts
   per release, and the number of fits reported "not checked"; the scope statement of section 6.6.
5. **Lifecycle activities**: section 11.
6. **Configuration management**: section 12.
7. **Anomaly management policy**: section 8.
8. **Dependencies (SOUP of SOUP)**: numpy; a JSON Schema validator; OpenUSD, either `usd-core` from PyPI or
   the host application's own build (Isaac Sim ships its own), only with the `[usd]` extra. OpenUSD's
   licence is a modified Apache 2.0 (recalled; check the exact text before the first release).

**Material library contents table**: every material with identifier, version, content hash, sections
present, tier, licence, proxy flags per section, family versions used, number of reviewed values, number
of model-assisted values, and fit-reproduction and witness status.

**Not in the package:** the MCP server and the extraction procedures are curation tooling (architecture
draft section 8.5). Every value they help draft is reviewed against its source before release. The package
states how many library values were model-assisted, which procedure versions drafted them, and those
procedures' gold-set scores.

---

## 11. IEC 62304 Lifecycle Mapping

Vesalius is not subject to IEC 62304. This mapping is voluntary, as MADDENING's is (section 11).

| Phase | Clause | What Vesalius provides |
|---|---|---|
| Development planning | 5.1 | the architecture draft, this document, `CONTRIBUTING.md`, Git and CI |
| Requirements | 5.2 | `docs/specification/` (normative); family definitions |
| Architectural design | 5.3 | the architecture draft's components and layers; no shared mutable state; the read side needs no Vesalius code |
| Detailed design | 5.4 | the specification, the method guide and family definitions, with Implementation Mappings |
| Unit implementation | 5.5 | source code, NumPy-style docstrings |
| Unit verification | 5.6 | conformance, method, family and data verification (section 6) |
| Integration testing | 5.7 | round trips between plain and USD forms; reading records and stages produced by downstream pipelines |
| System testing | 5.8 | the conformance suite run against more than one reader, when a second exists |
| Release | 5.9 | CHANGELOG, tags, PyPI, registry, SOUP package, SBOM; for the library, a DOI |

---

## 12. Configuration Management

Adopted from MADDENING section 14: Git with full history; tagged releases; PyPI hashes; `CITATION.cff` from
the first release; a CycloneDX SBOM per release, generated from a clean install, as MADDENING does.

Vesalius adds:

- **a content hash per material**: SHA-256 of a canonical serialisation of its values, provenance,
  statistics, uncertainty structures and check points. A simulation that records the hashes of the
  materials it used can show it used exactly those values, even if a later library version changes them;
- **frozen family versions**, each with a hash of its definition and vectors;
- **the schema archive** (the L0 files, conformance cases and golden vectors) released with its own hash,
  so a project in another language can vendor exactly the version it was built against;
- **static release archives**: each library release is one archive (records, generated layers, cards,
  index, shipped reference data), published on GitHub and archived on Zenodo with a DOI and a hash, so a
  simulation can cite the exact data it used and nothing in a release depends on a hosted service;
- **signed release tags** (recommended, as in MADDENING).

---

## 13. EU MDR, MDCG 2019-11 and QMS

Referenced, not repeated: MADDENING sections 12 (EU MDR Annex I and II), 13 (MDCG 2019-11) and 15 (QMS
compatibility) apply to Vesalius unchanged in principle. Vesalius is general-purpose software with no
medical purpose; a commercial manufacturer assesses it as SOUP within their ISO 13485 QMS; Vesalius
operates under no QMS and says so.

One addition for a manufacturer's design inputs: library values are inputs to their simulation, so the
manufacturer's design controls must cover the choice of material, its proxies and its applicability. The
material input sheet of section 9 is meant to make that record easy to produce. A manufacturer's own
measurements fit the same format as a private overlay, with the same provenance and checks.

---

## 14. Downstream Integration

`docs/regulatory/downstream_integration.md` would document two chains:

```
Chain 1                                        Chain 2
[Commercial product]                           [Commercial product on Isaac for Healthcare]
  └── MICROROBOTICA                              ├── Isaac for Healthcare components
       └── MIME                                  └── Vesalius   (SOUP)
            ├── MADDENING  (SOUP of SOUP)
            └── Vesalius   (SOUP of SOUP)
```

**What MIME's SOUP package section 8 must list for Vesalius**, following MADDENING's pattern for itself
(MADDENING section 16): the pinned Vesalius version, the schema version, the family versions and library
release it uses, links to Vesalius's version-tagged SOUP package and anomaly registry, the PyPI hash, the
SBOM, a table of Vesalius anomalies relevant to MIME, the library materials MIME's experiments use with
their content hashes, how MIME's own JAX implementations of families are verified (the golden vectors and
check points), and the update policy (review the CHANGELOG's Schema, Families, Data and Known Anomalies
sections; rerun MIME's tests; update the pin).

**For a product on Isaac for Healthcare**: the same items, plus which reader they use (Vesalius's Python
reader, or their own against the specification). An independent reader must pass the conformance suite to
claim conformance to a schema version.

---

## 15. Project Constraints

Binding on every contribution. `CONTRIBUTING.md` holds the operational detail.

1. **Sign-off on every commit** (Developer Certificate of Origin), from the first code commit. The design
   commits that precede the first code are exempt. CI enforces it once code exists.
2. **Apache-2.0** for all code contributions. No runtime dependency under a copyleft licence.
3. **No runtime dependency on a simulator or ML framework**: not MIME, MADDENING, JAX, PyTorch, Warp or
   Isaac. Core: numpy and a JSON Schema validator. USD is an optional extra and is imported from whatever
   build is installed.
4. **The read side stays implementable without Vesalius code**, with a JSON parser or with USD. Anything
   that needs computing is baked when a record is written. A change that would require reader code beyond
   the specification is a major schema change.
5. **SI units in stored values, always.** Conversion happens in importers and adapters. Parameter sets are
   stored only in their family's convention; conversion to a solver's convention happens in adapters and
   exporters, with vectors.
6. **No value without provenance.** Every library value has a kind, a source with a locator, an extraction
   method, statistics or an uncertainty structure (or a reason for none), a proxy declaration, a tier and a
   recorded review.
7. **The specification is normative.** Every normative statement gets a conformance case.
8. **Generated files are never hand-edited.** USD layers, material cards and the index come from the plain
   records; CI checks equality.
9. **Claim hygiene.** Library values are declarations, or fits to cited data. Biocompatibility is never a
   safety claim. Nothing in the repository presents a value as validated for a patient.
10. **Anomaly entries are never deleted**, only resolved.
11. **No network access and no code execution from data**, at import or when reading files.
12. **The anomaly registry stays in MADDENING's schema** and is checked with MADDENING's validator, a
    development-time dependency only (sections 1 and 8.1).
13. **Fail closed.** A reader refuses an unknown family or version, a failed check point, or a request to
    sample an undeclared uncertainty structure. It never guesses.
14. **Check points and a convention witness on every model parameter set.** Check points are computed by
    the family's reference implementation, never typed in. The witness is a response the source itself
    reports, which the parameters must reproduce; a parameter set without one is not admitted to the
    curated library.
15. **Family versions are frozen.** A family is admitted with a definition, golden vectors, a reference
    implementation and a named consumer; any change is a new version.
16. **Nothing non-redistributable is shipped.** A value from a source whose redistribution status is not
    permitted or unknown is reference-only. Every pull request that adds data carries a data attestation.
17. **The library's data licence is separate from the code licence**, and every record states the licence
    it is distributed under.
18. **Shipped USD layers are self-contained**: no composition arcs and no asset paths. `vesalius check`
    enforces it.
19. **Static releases.** Everything needed to use a release is in its archived artefacts. No Vesalius
    feature requires a hosted service, and nothing is fetched from the network unless the user asks.
20. **No model on the read side.** No language model runs in a reader, in `vesalius check`, in a release
    build, or in any consumer's build. Vesalius calls no model and holds no keys; the user's agent brings
    both (architecture draft section 8.1).
21. **Quotes and human review.** Every value a model helped draft carries its verbatim quote, locator and
    document hash, and an assistance record. No value of any kind enters a release without a human review
    record; the release build fails closed.
22. **A model never decides.** A model never sets a tier or a redistribution status, converts a unit,
    writes a check point or a witness, or produces a fit result. The MCP tools are scoped so that it
    cannot.

---

## Appendix A: Implementation Priority

Scaled down from MADDENING's Appendix B to what a small library needs.

**Phase 0, now (design):** this document; `CONTRIBUTING.md`; `SECURITY.md`; `CHANGELOG.md`; the empty
anomaly registry and its issue template; the pull-request template; `docs/regulatory/intended_use.md`; a
README disclaimer.

**Phase 1, with the first code:** the specification for each release's contents as it is built (architecture
draft section 12.2): first the record format with namespaced identifiers, values, provenance and required
properties (Vesalius 0.1), then uncertainty, model families, geometry and the USD binding (0.2); the
conformance suite; the first family definition (architecture draft section 12.1, R5) with golden vectors and a
reference implementation; `python -m vesalius check`; `scripts/check_anomalies.py`, `check_families.py` and
the sign-off check; GitHub labels as MADDENING's (`anomaly:critical`, `anomaly:major`, `anomaly:minor`,
`safety-relevant`, `soup-assessment`, `known-anomaly`).

**Phase 2, with the first library material:** the library repository with its data licence; the source
registry; the data entry standard, review process and takedown procedure; `bibliography.bib`; the library
checks of section 6.5; generated USD layers, cards and index; the legal review of the architecture draft,
section 6.5. Hosting items beyond the release archive (an index repository, a data wheel, a viewer) follow
their triggers in the architecture draft, section 6.7. Once the seed library exists: the MCP server, the
extraction procedures as method entries, and the gold set (architecture draft section 8).

**Phase 3, at the first release:** `CITATION.cff`; the SOUP package; the SBOM; `iec62304_mapping.md`;
`downstream_integration.md`; signed tags; the library's first DOI.

**Phase 4, when MIME adopts it** (planned with Vesalius 0.2, architecture draft section 12.2):
`vesalius.compliance` (section 9); MIME's SOUP package section 8 entry for Vesalius.

---

## Appendix B: Bootstrap Checklist

Status at 2026-10-11.

**Phase 0**

- [x] `design/ARCHITECTURE_DRAFT.md`
- [x] `DOCUMENTATION_ARCHITECTURE.md` (this document)
- [x] `CONTRIBUTING.md` with the constraints of section 15, the ID prefixes, data and family rules and the
  anomaly lifecycle
- [x] `SECURITY.md` with a reporting contact, response times, and the trusted-input boundary of section 3.3
- [x] `CHANGELOG.md` in Keep a Changelog format with Schema, Families, Data, Verification, Security and
  Known Anomalies
- [x] `docs/validation/known_anomalies.yaml` with `schema_version`, `vesalius_version`, `generated_date`
  and an empty `anomalies` list
- [x] `.github/ISSUE_TEMPLATE/anomaly.yml` with MADDENING's mandatory fields
- [x] `.github/pull_request_template.md` with the sign-off and the data attestation
- [x] `docs/regulatory/intended_use.md` with the statements of sections 3.1 to 3.5
- [x] README disclaimer and documentation table

**Phase 1**

- [ ] `docs/specification/` for each release's contents, every normative statement with a conformance case
- [ ] `tests/conformance/` with cases and expected answers as data files, for plain records and USD
- [ ] the first family definitions under `families/`, with golden vectors and reference implementations
- [ ] `python -m vesalius check`, including the namespaced-identifier, self-contained-layer, witness,
  evidence and `--release` checks
- [ ] `scripts/check_anomalies.py`, delegating to MADDENING's validator, run in CI on every push
- [ ] MADDENING's validator accepts a project version field (`vesalius_version`); requested of MADDENING
- [ ] `scripts/check_families.py` and `scripts/check_signoff.py`, run in CI on every pull request
- [ ] GitHub labels as in Appendix A

**Phase 2**

- [ ] the library repository, with its data licence chosen (architecture draft open question 8)
- [ ] `sources.yaml` with redistribution statuses
- [ ] `docs/data_entry_standard.md`, `review_process.md` and `takedown.md`
- [ ] the library checks of section 6.5
- [ ] generated material cards and `index.json`
- [ ] the legal review, before the first library release
- [ ] the first library material with a complete review record
- [ ] the gold set and its deterministic scorer
- [ ] `vesalius-mcp` with capability-scoped tools; extraction procedures as `VES-MTH-` entries with
  gold-set scores

**Phase 3**

- [ ] `CITATION.cff`
- [ ] `docs/validation/soup_package.md`
- [ ] SBOM under `docs/validation/sbom/`
- [ ] `docs/regulatory/iec62304_mapping.md` and `downstream_integration.md`
- [ ] the first library release archive on GitHub and Zenodo, with a DOI

**Phase 4**

- [ ] `vesalius.compliance` with `collect_material_inputs` and content hashes
- [ ] MIME's SOUP package lists Vesalius in its section 8
