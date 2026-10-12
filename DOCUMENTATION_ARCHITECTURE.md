# Vesalius Documentation Architecture Plan

**Status: a plan.** Written 2026-10-11, before any code exists, and revised the same day with the
architecture draft, and again on 2026-10-12 with the decisions taken after the prototypes. Appendix B says
what is in place. The architecture of the library itself is in
[`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md) (the **architecture draft**).

## Executive Summary

**Vesalius** is an open material schema with an OpenUSD binding, and a small Python toolkit. It describes
substances in and around the human body: tissues and body fluids, the media and phantoms that stand in for
them, agents introduced into them, and the materials of devices that enter or touch them. For each it holds
fluid, mechanical, acoustic, optical, thermal, dielectric, radiological and magnetic properties, with the
provenance and uncertainty of every value; it binds those descriptions to anatomical and device geometry, and
lets any simulator read them. It does not describe systems: an apparatus or its calibration, the quantities
of one object, a drive, a procedure, or a simulator's tuning (section 3.1). Its code is licensed Apache-2.0;
its curated material library is released under CC0-1.0.

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
| Families | model-family definitions: equations, golden test vectors, reference implementations; shipped as one distribution, `vesalius-families`, separate from the core, with a content hash per family version | Apache-2.0 |
| Library | curated material records, in a repository of its own, released as static archives with a DOI; no hosted service | CC0-1.0 |

**Why it is likely to become SOUP.** The values Vesalius ships and resolves feed simulations. When a
regulated product is built on MIME, Vesalius is SOUP of SOUP, beside MADDENING. When a product built on
Isaac for Healthcare reads Vesalius materials, Vesalius is SOUP directly. In both cases a wrong value (a
transcription error, a wrong unit, a parameter set read in the wrong convention, a material resolved to
the wrong region) reaches the device's computation silently. That is the failure this documentation
architecture is built around.

**What is different from MADDENING and MIME.** Five things.

1. **Vesalius ships data as well as code.** Its library of materials is part of what a manufacturer would
   assess. The question for the data is not "does the solver converge" but "is this the value the cited
   source gives, in the stated units, under the stated conditions".
2. **There is no physics solver.** The code computes little: unit conversion, mixing rules, interpolation,
   composition into spectra, resolution of which material owns a point, check points and sampling. Its
   documentation replaces the algorithm guide with a normative specification, a short method guide and
   model-family definitions (sections 4 and 5).
3. **The read side must work without Vesalius code.** A C++ simulator reading a record or a stage is a
   consumer too. So the specification, not the Python package, is the primary artefact, and its
   conformance suite is the primary verification evidence (section 6). Vesalius code never runs inside a
   consumer's computation: a consumer writes its own reader, mixing rules and model evaluators in its own
   language or framework, and verifies them against conformance data, golden vectors and check points
   (constraint 26).
4. **Records carry their own verification.** A model parameter set carries check points that any consumer
   evaluates before using it, so a reader that never ran the conformance suite still fails loudly on a
   convention mismatch. A convention witness from the source does the same for extraction: the parameters must
   reproduce a response the source reports that was not used to obtain them (architecture draft section 4.6).
5. **Records hold facts; consumers declare choices.** A record says what was measured and how it is known.
   It never says where or in which regime a model applies, which stand-in is acceptable or how to mix
   materials. The consumer declares those and the build records them, so the most common misuse, reading
   "the data exists" as "the model applies", becomes a refusal or a recorded choice instead of a silent
   default (architecture draft section 3.5).

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
5. [The Method Guide, Model Families and the Material
   Library](#5-the-method-guide-model-families-and-the-material-library)
6. [Verification](#6-verification)
7. [Versioning and Stability](#7-versioning-and-stability)
8. [Anomaly Management](#8-anomaly-management)
9. [Compliance as a Feature: Working with MADDENING and MIME
   Metadata](#9-compliance-as-a-feature-working-with-maddening-and-mime-metadata)
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
| 9.8 ISO 14971 hooks | Adapted (section 8.4) | quantitative conditions, structured specimen facts and qualitative known gaps on materials |
| 9.9 Usability | Adapted (section 3.5) | the main use errors are applying a value outside its conditions, using a stand-in unknowingly, and reading parameters in the wrong convention |
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

This repository holds the core and, at first, the families, released as their own distribution:

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
│   │   ├── provenance.md              # provenance fields, conditions vocabulary, specimen facts, tiers
│   │   ├── uncertainty.md             # statistics and what they represent; five structures; sampling
│   │   ├── model_families.md          # what a family definition must fix; kind; check points; witnesses
│   │   ├── fits_and_reference_data.md # fit records, reference data, the fit-reproduction rule
│   │   ├── geometry.md                # layered paths, regions, label volumes, field overrides, domains
│   │   ├── usd_binding.md             # USD schemas, binding purpose, layered-path form, layers
│   │   ├── read_side_contract.md      # what any reader must do, including when to refuse
│   │   ├── mixing_rules.md            # identities; named rules picked by the consumer
│   │   ├── declarations.md            # domains, targets, picks, tolerances, waivers; met/not met/unknown
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
├── families/                          # vesalius-families, its own distribution: one directory per family (section 5.2)
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

The library lives in a repository of its own (name to be chosen), under CC0-1.0. Its releases
are static archives, published on GitHub and archived on Zenodo with a DOI; there is no hosted service
(architecture draft section 6.7):

```
<library repository>/
├── README.md, LICENSE (CC0-1.0), CHANGELOG.md, CITATION.cff
├── sources.yaml                       # the source registry (architecture draft section 6.1)
├── publishers.yaml                    # other namespaces: repository URLs, release hashes (section 6.7 there)
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
  draft section 3.4); CI regenerates the USD layers, cards and index and fails if they differ, as
  MADDENING does for its stability report.
- **Tooling** follows MADDENING and MIME: Markdown with MyST, Sphinx once a site is worth building,
  Pandoc-style `[@Key]` citations against the repository's `bibliography.bib`.

---

## 3. Regulatory Boundary Language

### 3.1 Platform positioning statement (`docs/regulatory/intended_use.md`)

> Vesalius is an open material schema and a software toolkit for describing the physical properties of
> substances in and around the human body for simulation. It is research software distributed under the
> Apache License 2.0.
>
> **Vesalius is not a medical device** as defined by EU MDR (EU 2017/745) Article 2(1). It has no medical
> purpose. It does not diagnose, monitor, predict, treat or alleviate disease, and it makes no clinical
> interpretation of anything it stores. Under MDCG 2019-11 it is general-purpose software, comparable to a
> units library or a materials database.
>
> When incorporated into a regulated medical device, Vesalius is classified as SOUP under IEC 62304. The
> device manufacturer bears full responsibility for assessing its suitability for their context of use.

The scope statement sits beside it in `intended_use.md`:

> Vesalius describes substances in and around the human body: tissues and body fluids, the media and
> phantoms that stand in for them, agents introduced into them, and the materials of devices that enter or
> touch them. It does not describe systems: an apparatus or its calibration, the quantities of one object
> (its moment, inertia or mean density), a drive, a procedure, or a simulator's tuning.
>
> - **The transfer test.** A value belongs in Vesalius if it would hold for another object made of the same
>   substance under the same conditions. If it changes with an object's shape, size or assembly, the
>   consumer computes or records it.
> - **Pairs.** A property of two substances in contact (friction, slip, a solute's diffusivity) is in, as an
>   interface record, when the source states the surface conditions and the test method, which become
>   required conditions. A number measured with one tool or device is reference data for checking a model.
> - **Geometry is scene data.** Vesalius defines how geometry binds to materials, and ships only small test
>   phantoms and label mappings from reference anatomies, never anatomy.
> - **Behaviour.** Behaviour computed from geometry and materials (an implant's heating in MRI, a puncture
>   force) is the consumer's output; measured behaviour is reference data in the consumer's namespace.
> - **Entry.** Content enters when a named consumer needs it, and the curated library starts with the
>   body. Other publishers may use the same machinery in their own namespaces, including for data Vesalius
>   does not curate: a record of a type of their own (an apparatus's calibration, say) is checked like any
>   other record but is never a material and is never curated (constraint 27).

### 3.2 Data statement

This is the statement MADDENING does not need and Vesalius does:

> The values in the Vesalius material library are **taken from cited sources**, or are fits to cited data,
> labelled by origin. Vesalius warrants that each value is what its source gives (or what its recorded fit
> produces), converted correctly to SI, with the specimen, conditions and statistics the record states; and
> that each model parameter set reproduces its check points under the family definition it names, and its
> independent convention witness where the record has one. Vesalius does **not** warrant that a value
> describes any particular patient, tissue sample, phantom batch or device, nor that a source is itself
> correct or current. Whether a library value is applicable to a given use is the user's and the
> manufacturer's judgement.
>
> Many values were measured on specimens that differ from a user's target (another species, another site,
> a cadaver, a phantom). Each record states its specimen, per field; whether it stands in adequately for a
> target is the user's declaration, never the library's. A reference-only record publishes no values; its
> values are whatever the user fills in from their own copy of the source, and the curator has not
> reviewed them.
>
> Every value in the curated library that was extracted from text or a table carries the verbatim quote it
> was read from, with the identity and version of the document. Some values are drafted with the help of a
> language model; each such value says so. Every value, assisted or not, is checked against its source by a
> named reviewer before release.
>
> Biocompatibility fields record test evidence reported for a material. They are never a biocompatibility
> assessment or a safety claim, and never a device's status. A manufacturer performs their own ISO 10993
> evaluation.

### 3.3 Cybersecurity boundary statement (MDCG 2019-16)

> Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation beyond
> validating records against the record schema. A USD stage can pull in other files through its composition
> (sublayers, references, payloads) and through the host's asset resolver, so reading a stage may read any
> file that stage names. Every USD layer Vesalius ships is self-contained (no composition arcs, no asset
> paths), so reading a library layer reads that file alone. Vesalius itself makes no network requests and
> runs no code from the files it reads: records and family vectors are data, and family reference
> implementations are code shipped in the `vesalius-families` distribution, never loaded from a record.
> Loading third-party records and stages, and the security of the asset resolver, are the responsibility of
> the integrating application.

### 3.4 Licence note

Apache-2.0 is permissive: no copyleft obligation follows a product that incorporates Vesalius's code, and
the licence includes an express patent grant. It is compatible with use from MIME and MADDENING
(LGPL-3.0-or-later) and with contributions to Isaac for Healthcare. The curated library's data is released
under CC0-1.0, stated on each record (architecture draft section 6.4), so that anyone may recombine it with
other data without attribution conditions; credit travels instead in each value's source, its curator's
ORCID and each release's DOI. Two things CC0 does not change: a value whose source restricts redistribution
stays reference-only, and a short quote kept as evidence is the source's text, not relicensed. Other
publishers choose their own licences. This is a description, not legal advice.

### 3.5 Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Family definitions and reference implementations agree | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | golden vectors (section 6.4) |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, fit reproduction, data checks |
| A consumer's own reader, mixing rules and family evaluators | downstream user | IEC 62304 Clause 5.6 (their own) | the conformance cases; the record's check points; the family's golden vectors |
| Choosing a material; declaring its domain, target, mixing rule and picks; accepting differences between specimen and target | downstream user | ASME V&V 40 (model inputs) | the user's input justification and the material input sheet |
| Watching, during a run, a condition that the run or an optimiser moves | downstream user | ASME V&V 40 | the evaluator's in-range output, recorded with the results |
| Measuring the language model an agent uses for extraction, before relying on it | the curator using it | none: curation tooling is outside the SOUP package | gold-set score; review of every value |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

The use errors Vesalius can make less likely are applying a value outside its conditions (a different
temperature, frequency, wavelength, species or tissue state), using a stand-in without knowing it, mixing
across the edge of a domain, and reading a parameter set in another convention. Vesalius makes conditions
and specimen facts machine-readable and the consumer's declarations explicit, so a build can check them
(architecture draft section 3.5). A consumer's convention mismatch fails at the check points; an
extraction in the wrong convention fails at the independent witness. A condition that moves during a run
(a temperature an optimiser adjusts) cannot be checked at build: an evaluator reports whether its condition is
in range, and the consumer watches that condition, not a parameter derived from it, because an evaluator
that clamps at a table's end keeps the derived parameter inside its range while the condition leaves it.

---

## 4. The Specification

The specification in `docs/specification/` is the primary artefact. It defines the record format, the USD
binding and everything a reader must do, in prose and tables, independently of the Python package. It is
**normative**: where the Python reader and the specification disagree, the reader is wrong.

| Document | Defines |
|---|---|
| `record_format.md` | the envelope every record shares (identifier, version, record type, schema version, content hash, provenance and the value machinery) and its body; the record types `material` and `interface`, and the rule that a reader skips a type it does not know; for a material, its sections, including `bulk` (density and elemental composition, which no other section duplicates); the `extensions` block for another namespace's sections; every field with its SI unit, value form, range, interpolation scheme and edges, allowed tokens and stability level; the five value forms, with a table's tabulated range kept apart from the range its source says it holds over, and power laws with the basis of their exponent and their decibel or neper convention; no fallback values |
| `provenance.md` | provenance fields, including origin (with "evaluated from a reference formulation"); the extraction methods; document identity and version beside the hash of the copy read; locators per document version; explicit statuses ("not checked", "none") in place of empty fields; fields filled at import kept apart from those filled at curation; per-parameter provenance in a parameter set; the conditions vocabulary, categorical conditions included, the basis of each condition, and unstated conditions; specimen facts, with the division between the two (conditions describe the test, specimen facts the thing tested) and the starting vocabulary (NCBI Taxonomy, UBERON and a short list of tissue states); the three tiers, derived from the source registry, and user fill-ins; the source registry's fields and redistribution statuses; evidence, assistance and search records |
| `uncertainty.md` | the statistics block; what each spread represents; `dispersion: not_reported`; relative and expanded uncertainty with a coverage factor; the basis "specification limits"; interval-only values, one-sided ones included; the five uncertainty structures; admissibility; the sampling rules, including refusal |
| `model_families.md` | the identifier form; the `kind` field, stated per loading control, with every rate marked as an input or a test condition; input and output measures with conversion vectors; the domain of each term; the evolution form (state variables, input histories, events); events that say only where a family's range of states ends, never which model takes over; what a family definition must fix (architecture draft section 4.5); check points in records, their coverage and the tolerance rule; independent convention witnesses and their tolerance; refusal on an unknown family or version or a failed check point |
| `fits_and_reference_data.md` | the fit record, including "exactly determined"; coverage as a set of loading modes and ranges, with histories; the reference-data payload (points with their own origin and status; curves with a digitised flag and the digitiser's axis calibration); the fit-reproduction rule and "not checked" |
| `geometry.md` | layered paths; region binding and the region marker; label volumes; field overrides, their provenance and their frame (world, or the region's reference configuration); precedence declared by the scene; nested regions; background; domains, named relative to the prim that declares them |
| `usd_binding.md` | the API schemas; attribute names; the physics binding purpose, authored on the region prim, and the bindings a reader refuses; the USD form of a layered path (a typed prim of our own); each field's full plain form as one generated JSON string beside its typed scalar; library materials under a scope of their own, never `/Materials/<name>`; the stage's authored `metersPerUnit`; taking provenance from the layer that supplies the value |
| `read_side_contract.md` | the read procedure (architecture draft section 7.5), in order, and every case in which a reader must refuse; what an evaluator reports (whether its condition is in range, and which side's derivative it gives at a table's knots and ends) |
| `mixing_rules.md` | the identities; the named rules, each with its equation, its assumptions and a numpy reference; fields with no general rule. Consumers write the rules in their own code (constraint 26) |
| `declarations.md` | what a consumer declares (domains, targets, family versions, mixing rules, picks, tolerances with their reason and consequence, waivers, a specimen fact that implies a condition, chains of families across events); the three results of a check (met, not met, unknown), an unknown carrying its value; how declarations are recorded (architecture draft section 3.5) |
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

**Curation tools come before the library.** Draft templates (with "not applicable" driven by the value's type,
and a structured "unstated"), quote attach-and-verify, registry drafting from a DOI and licence pages, a
digitiser with a stated axis calibration and an overlay, formulation evaluators (a reference formulation such
as water's) and check-point bakers are a prerequisite of the first library release. Each is a method entry
built first as a library function with a command line; the MCP server only exposes them (architecture draft
section 8). A prototype estimated (it did not measure) full provenance at two to seven times the time
first assumed per value; tooling, not fewer fields, is the answer chosen.

### 5.2 Model-family definitions

Each family version has a `definition.md`, normative for that version, with these sections:

```markdown
# [Family identifier, e.g. vesalius.mechanical.ogden_incompressible.v1]

**Status**: [admitted | deprecated]
**Named consumer**: [who needed it, and for what]

## Kind and state                # static or evolution, per loading control; each rate an input
                                 # or a test condition; state variables, initial state, events
## Kinematics and outputs        # input and output measures, with conversion vectors; loading modes covered
## Equations                      # normative; the domain of each term
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

- **Reference implementations live with their families**, not in the core. They run on the write side, to
  bake check points; consumers evaluate parameter sets with their own code (constraint 26). The families
  ship as one distribution, `vesalius-families`, separate from the core, and each family version has its
  own content hash, so a manufacturer assesses only the families it uses.
- **An event never names its successor.** A family's event says only that its range of states ends, and
  under which condition. Which model takes over is the consumer's choice: the consumer declares the chain,
  the build records it in the material input sheet, and the run records each hand-over and its time.
- **Golden vectors cover both sides of every switch** in the equations, and consistency vectors cover any
  constant that continuity fixes.

### 5.3 The material library

Each library material has an identifier `vesalius/VES-MAT-[XXXX]` (architecture draft section 4.1) and one
plain record in the library repository. Its USD layer and its **material card** (architecture draft section
6.6) are generated from that record. The card's prose sections are fields of the record: motivation, what was
measured and what was not, and maintenance are written by the curator; the rest is assembled from the other
fields.

**Data entry standard** (`docs/data_entry_standard.md` in the library repository). Every value carries:

| Field | Required | Notes |
|---|---|---|
| value | yes, unless the tier is reference-only | one of the five forms (architecture draft section 4.4), with the range it was measured or fitted over; a table with its interpolation scheme and edges, the range its source says it holds over where that differs from the tabulated range, and evidence per point; a power law with the basis of its exponent (fitted, assumed or theoretical) and its decibel or neper convention; a constitutive constant with its trivial family |
| unit | implied | always the SI unit the specification fixes for the field |
| origin | yes | measured by the source, measured by the contributor, fitted, derived, evaluated from a reference formulation (with derivation evidence instead of a quote), or stated without an origin |
| source | yes | a key in `sources.yaml`, with a locator for the version of the document read: table (with the column header quoted and its index), figure, page or equation |
| extraction | yes | table, text, digitised figure (tool, axis calibration and digitising error), supplementary dataset (licence), own measurement, derivation (method ID) or fit (fit record); for text, which text extraction of the document matched the quote |
| conditions | yes | the conditions of the test, as the source states them, from the conditions vocabulary: temperature, frequency, rate, loading mode, test method, measurement geometry, propagation direction (for speeds in anisotropic tissue), categorical ones included; each with its basis (stated, or inferred from a figure); a condition the source does not state is recorded as unstated; specimen shape for magnetic values; test method and specimen geometry for failure values |
| statistics | yes for scalars | number of specimens and donors, mean, standard deviation, minimum, maximum, distribution, basis, and what the spread represents (population, estimate, measurement, across sources); relative or expanded uncertainty with its coverage factor where the source gives one; the basis "specification limits" for a datasheet's minimum and maximum; `dispersion: not_reported` where the source gives none; an interval-only value with its basis, one-sided where only one bound is known |
| uncertainty structure | yes for parameter sets | `ensemble`, `multivariate_normal`, `independent` (with a justification), `interval` or `none`, and what it represents |
| check points | yes for shipped parameter sets | computed by the family's reference implementation, never typed in; spanning the fit's coverage and the family's branch points. None for a reference-only set, since they would publish its parameters; its fill-in is checked against the witness (section 6.3) |
| fit record | yes for fitted values | reference data (identifier, or DOI and hash), procedure, coverage, residual |
| convention witness | yes for parameter sets taken from a source | a response the source reports, with its locator, that the parameters must reproduce, independent of how they were obtained (for a fit, a held-out datum), and which fit it is independent of; its tolerance taken from the fit's residual and the precision of the stated state, never from the spread between specimens; whether it tests the family alone or through a model of the test (architecture draft section 4.6); without one, "no independent witness" and not admitted |
| specimen | yes | the facts of the thing tested, per section or field: species and anatomical site as ontology identifiers (NCBI Taxonomy, UBERON), tissue state from a short list (in vivo, ex vivo fresh, frozen and thawed, fixed, phantom), preparation, preservation, donor age and shape; a fact the source does not state is recorded as a structured "unstated"; for a phantom or substitute, what its maker says it mimics |
| tier | yes | shipped, reference-only or private, derived from the source's redistribution status in the registry, not written per value. A record a model drafted stays reference-only until a person sets the status |
| evidence | yes for every value extracted from text or a table, in the curated library; optional in other namespaces | the verbatim quote, including any conditions and exponents it states, its locator, the identifier and version of the document, and the SHA-256 of the copy read. A hash identifies a copy, not a document: re-verifying means the quote occurs in your own copy. Copies stamped with personal data (a downloader's name or address) never ship. For a digitised figure, the locator and the hash. Quotes are not published for reference-only values |
| statuses | yes | an explicit status ("not checked", "none") wherever a check or a field has no result, never an empty field; fields filled at import kept apart from fields filled at curation; per-parameter provenance where a parameter set's parameters come from different places |
| assistance | yes when a model assisted | tool, model and provider as reported, prompt version (`VES-MTH-` entry and version), date |
| search record | yes for statistics pooled across sources | queries, databases, date, inclusion criteria |
| reviewer, date and ORCID | yes | who checked the value against the source, whether they are independent of whoever or whatever extracted it, and which checklist items: value, unit, conditions, specimen, statistic, primary or cited, family and witness |

**What review means.** A second person (or the same person on a later day, recorded as such) reads the
source at the locator and confirms the value, the unit conversion, the conditions and the specimen facts.
The record of that check is part of the evidence (section 6.3). Agreement with another database is not a
review. For a model-assisted value, the reviewer reads the rendered page at the locator, not only the
quote, and confirms the quote is visible there; hidden text in a document can pass a text-layer check. The
review checklist also asks for what drafting agents flagged most usefully in the prototypes: contradictions
inside a source, swapped values, implausible spreads and mislabelled specimen states. Before review, a pass
told to refute the draft (a person, or an agent with a person reading its findings) is part of the pipeline.

**A citation found in code is a lead, not provenance.** A number in someone's code with a reference beside it
is traced to the source and checked there; the reference alone is never the value's source.

**Source registry.** `sources.yaml` holds one entry per source: citation key, DOI or URL, the licence of
the publication and of any dataset, a redistribution status (permitted; values only; not permitted;
unknown) with its reason, who judged it and when, and the source's role; and, for each copy a curator
holds, its retrieval route, its version identity and the licence it came under. A value from a source whose
status is not permitted or unknown is reference-only.

**Plausibility and consistency checks** run in CI on the whole library: physical bounds per field (density and
sound speed positive and within broad bounds for condensed matter); consistency between related fields within
one record (impedance against density times sound speed; a derived Grüneisen parameter against one given
directly); admissibility of every parameter set and every ensemble member; completeness of provenance. A
failure blocks the merge. Disagreement between sources is reported and kept, not blocked: which source a
simulation uses is the consumer's pick (architecture draft section 3.5).

**What the library is not.** It is not a database of everything published. A material is added when a
consumer needs it, with the sources that consumer relies on.

---

## 6. Verification

Vesalius has no physics to converge, so its verification is of five other kinds. Each verification item has
an identifier `VES-VER-[XXX]`.

### 6.1 Conformance suite (the read side)

Small cases, each with expected answers: the material bound to a prim or a path interval; a property at a
point; a property at a wavelength or frequency; the owner of a point inside nested regions; the provenance of
an overridden value, including USD's dictionary-merge trap; equality of a record's plain and USD forms;
refusal on an unknown family or version; refusal on a failed check point; refusal to sample an undeclared
uncertainty structure; a record of a newer minor schema version, with a section the reader has never seen,
read for the sections the reader knows; refusal of an attribute that was not authored; refusal to interpolate
across an edge or outside a range; unknown, not met, for an unstated condition; refusal of a nominal for an
interval or an ensemble; refusal to mix a field with no general rule; a requirement checked over a domain's
regions only. Added after the prototypes:

- at every knot and end of a table, the value and the derivative from each side; an evaluator's test states
  which side's derivative it returns (implementations differ, and a gradient check near a knot needs to know);
- an evaluator reports whether its condition is in range, beside the value, instead of only clamping;
- mixing rules tested at the cell, on stated fractions and values, not through a projector or a solver;
- the throwaway reader's four defects, each as a case: an unknown or waived result still carries its value;
  a malformed record gives "not met", never a crash; a power law's own axis is not checked again as a
  condition; a tolerance carries its reason;
- the analytic volume fractions of the canonical example phantoms (a sphere, a cylinder, a layered slab) on
  stated grids, which also serve as the example phantoms;
- a record of a type the reader does not know, skipped; a namespaced record type, its envelope checked;
- each field's JSON string in USD equal to its typed scalar;
- refusal of a stage with no authored `metersPerUnit`; refusal of a physics material reached through an
  all-purpose binding or a binding with no purpose; a binding that applies within its region and never
  across into a nested one.

The cases and expected answers are data files, so a C++ or other reader can run them without Python. The
Python reader runs them in CI.

### 6.2 Method verification

Each method guide entry has tests against exact or analytical results: unit conversions exactly; each named
mixing rule against its limits (series and parallel conduction; Wood's rule and the ray limit for a layered
stack); composition against worked examples in its sources; the reference sampler's moments and its rejection
count against known cases. Extraction procedures are scored against the gold set by a deterministic scorer,
per field and per model tested; the gold set lists papers by DOI and document hash, with PDFs only where their
licence allows (architecture draft section 8.6).

### 6.3 Data verification

- the transcription review record for every value (section 5.3);
- the plausibility, consistency and admissibility checks (section 5.3);
- **check points recomputed**: every stored check point is recomputed with the family's reference
  implementation and must match. This shows that the implementation has not drifted; it is not evidence
  about any value;
- **fit reproduction**: every fitted parameter set is evaluated against its reference data and must achieve
  its stated residual. Where the reference data are not shipped, the result is "not checked", reported as
  such, never as a pass;
- **convention witnesses**: every parameter set taken from a source reproduces its witness under its
  family version, within a tolerance taken from the fit's residual and the stated state's precision, and the
  witness is independent of how the parameters were obtained. A record without an independent witness is
  counted and reported, never shown as a pass. Where the witness cannot be shipped, the curator's check at
  review is recorded and the public check reports "not checked";
- **reference-only parameter sets** ship no check points, which would publish the parameters. A user who
  fills in the parameters and the witness datum from their own copy runs the witness locally with `vesalius
  check`; a mistyped parameter fails against the source itself, and the curator's own result at review is
  recorded beside it;
- **evidence**: every value extracted from text or a table carries a quote, a locator, the document's
  identity and version, and the hash of the copy read. The quote is checked against the document when the
  draft is made, and again by the reviewer, who checks that it occurs in their own copy;
- a round trip: write a record, read it back, generate its USD form, read that back, compare every value,
  provenance field and check point.

### 6.4 Model-family verification and admission

- An evolution family's reference implementation states its integrator and its event location, and
  reproduces the family's analytic cases; its vectors carry tolerances, not only a precision.
- Each family's reference implementation reproduces its golden vectors at the stated precision, including
  the admissibility cases.
- Golden vectors are frozen per family version. CI fails if a released version's vectors change.
- Each conversion an exporter offers to a solver's convention has its own vectors showing the converted
  parameters reproduce the family's outputs; so does each conversion between a family's input and output
  measures.
- Golden vectors sit on both sides of every switch in the equations; consistency vectors check every
  constant that continuity fixes.
- A check point's tolerance is set by what it must tell apart and by the precision consumers declare; no
  check point sits where every arm of the family gives zero; an evolution family's tolerances allow for
  discretisation.
- **Admission.** A family enters with a definition (section 5.2), golden vectors, a reference
  implementation, and a named consumer. A family with no consumer for two releases is deprecated. The same
  rules bind third-party namespaces that want to be listed.

### 6.5 CI checks

**Record checks are a command in the core**, `python -m vesalius check <directory>`, so that the curated
library and any other publisher run exactly the same checks (architecture draft section 6.7):

| Check | Verifies |
|---|---|
| schema | records validate against the record schema; identifiers are namespaced; every record states its record type, and a namespaced type's envelope validates |
| provenance | the fields of section 5.3 are complete, with explicit statuses where a field has no result |
| plausibility | physical bounds; consistency between related fields; admissibility of every parameter set and ensemble member; units |
| check points | stored check points equal the reference implementation's |
| fit reproduction | every fit reaches its stated residual; "not checked" is counted and reported |
| generated | USD layers, cards and the index equal what the records produce; each field's JSON string equals its typed scalar |
| self-contained | shipped USD layers have no composition arcs and no asset paths |
| witness | parameter sets reproduce an independent convention witness; "no independent witness" and "not checked" are counted and reported |
| fallbacks | physical attributes in the USD schema have no fallback values |
| tables | every table declares its interpolation scheme, its range and its edges; every form states its range |
| evidence | every value extracted from text or a table carries a quote, a locator, the document's identity and version, and a copy hash; model-assisted values also an assistance record; with the document present, the quote exists at the locator and contains the value's numbers |
| release (`--release`) | fails on any value without a review record, and on any draft |

In this repository:

| Script | Checks |
|---|---|
| `scripts/check_anomalies.py` | the registry against the schema of section 8, prefix `VES-ANO-`, by delegating to MADDENING's validator (section 8.1) |
| `scripts/check_citations.py` | every `[@Key]` in the specification, methods and families exists in `bibliography.bib` |
| `scripts/check_impl_mapping.py` | every function named in a method guide or family definition exists |
| `scripts/check_families.py` | reference implementations reproduce their vectors; released vectors are unchanged; every family version's content hash matches; every family has a named consumer |
| `scripts/check_signoff.py` | every commit in a pull request carries a sign-off (section 15) |

In the library repository, CI runs `vesalius check` on every pull request and adds the curated library's
policy checks:

| Script | Checks |
|---|---|
| `scripts/check_publishers.py` | every namespace in `publishers.yaml` is unique, and every registered release passes `vesalius check` |
| `scripts/check_sources.py` | every source key exists; every value's tier is the one its source's redistribution status gives; no shipped value comes from a source whose status is not permitted or unknown; no record a model drafted is shipped before a person set its status; every record states its licence |
| `scripts/check_signoff.py` | sign-off and data attestation on every pull request |

### 6.6 What this verification does not provide

It does not show that any library value describes a patient, a tissue sample or a phantom batch, nor that a
specimen stands in adequately for a target. That is validation of an input for a context of use, which belongs
to the user and the manufacturer. Every verification document states this in a "Scope and Limitations"
section, as MADDENING's do.

---

## 7. Versioning and Stability

### 7.1 Four version lines

| Version | Tracks | Where it appears |
|---|---|---|
| Package version (SemVer) | each Python distribution: the core, `vesalius-families` and `vesalius-mcp` | `pyproject.toml`, CHANGELOG, SOUP package |
| Schema version (SemVer) | the specification, the record schema and the USD schema | `docs/specification/changes.md`; recorded on every record |
| Family version | one model family's definition, vectors and reference implementation; frozen once released, with its own content hash | the family identifier (`...v1`); recorded on every parameter set |
| Material version | one library material's values | the record; its card; its content hash (section 12); the library release that carries it |

Schema: **major** for a removed or renamed field, a changed unit or a changed meaning; **minor** for a new
optional field, section, token or value form; **patch** for wording only. A material: **major** when a value
changes by more than the uncertainty its record states for that value (a population's spread is not that
measure), a condition or specimen fact changes, or a parameter set moves to another family version; **minor**
for a new value or section; **patch** for provenance wording. A family: any change is a new version.

### 7.2 Changes to the schema

A schema change needs, in one pull request: the specification text, the conformance cases, the record
schema and USD schema files, the reader change, a `changes.md` entry, and a CHANGELOG entry under
**Schema**. Removal follows the stability levels below.

Any section or field can be added later as a minor change, because three rules hold (architecture draft
section 5.6): sections are optional and a reader ignores those it does not use; an added field never changes
the meaning of an existing one, and a change that would is major; conditions a reader does not know are
reported as present and unchecked, never dropped. A reader reads a record of a newer minor version and
refuses one of a newer major version. A new record type is additive in the same way: a reader skips a type
it does not know. This works only because every record states its type from the first schema version
(constraint 27).

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
| `major` | Any other silent wrong result. Examples: a library value that differs from its source; a wrong unit conversion; conditions or specimen facts recorded wrongly; provenance attributed to the wrong layer; a sampler that ignores a declared structure; a model-assisted value its quote does not support. A loud failure whose only workaround is not to use the feature. |
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
same split on materials, and adds specimen facts, which are structured rather than free text:

| On a material | Nature | Example |
|---|---|---|
| conditions and statistics | quantitative | measured at 37 °C, 1 to 10 MHz; n = 12 specimens from 4 donors, mean 1575 m/s, standard deviation 18 m/s |
| a fit's coverage | quantitative | uniaxial tension, stretch 1.0 to 1.3, strain rate 0.01 per second |
| specimen facts, per section or field | structured | acoustic section: porcine, ex vivo, 2 hours post-mortem |
| known gaps | qualitative | "no data above 10 MHz; no diseased tissue" |

A given limitation appears in exactly one of these. All are technical statements about the data, never
statements that it applies to a use, and not clinical risk assessments; that boundary is MADDENING's (section
9.8) and is adopted unchanged.

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
| **Input provenance for a run** (clear) | `collect_material_inputs(...)`: every property value a set of prims or path intervals resolves to, with material identifier and version, content hash, origin, source, statistics and what they represent, conditions, specimen facts, tier and review status (including user fill-ins), family version, fit-reproduction and witness status, whether a model assisted, and the layer or overlay it came from; the consumer's declarations (domains, targets, picks, tolerances, waivers) and the three-valued results; and the derivation chain from each record to each node parameter (overlays, unit conversion, mixing, defaults), with the derivation log saying which node parameter each value fed. Stored on the stage beside the simulation graph it describes, and exported as JSON and as a Markdown "material input sheet" | MADDENING's `SimulationProvenance.custom` (`MADD:src/maddening/core/compliance/provenance.py`); a credibility assessment's model-input evidence; MADDENING's context-of-use template | MIME writes the record into the run's provenance |
| **Uncertainty inputs** (partial) | statistics for scalars and uncertainty structures for parameter sets, each saying what it represents | MADDENING's `UncertainParameter` (a nominal, bounds and a distribution that defaults to uniform; no standard deviation), which describes one parameter at a time | MIME maps the spread its question needs where `UncertainParameter` can carry it; a mean and standard deviation, interval-only values and joint structures need MADDENING changes (architecture draft section 9.4). Until then MIME samples joint structures with Vesalius's reference sampler and labels the results |
| **Operating-point checks** (clear) | conditions, material values and fit coverage; evaluators that report whether their condition is in range | MIME's checks against computed operating points (Reynolds number, Mach number), and run-time watches on any condition a run or an optimiser moves, placed on the condition, not on a parameter derived from it. Fit coverage is not mapped onto MADDENING's `ValidatedRegime`, which records regimes in which a node was verified | MIME |
| **One anomaly schema** (clear) | `VES-ANO-` entries in MADDENING's format | one combined risk file; MIME entries can cite `VES-ANO-` entries as they cite `MADD-ANO-` ones | none needed |
| **Biocompatibility** (partial) | a material's reported test evidence | MIME's `BiocompatibilityMeta`, declared on the device's `Body` and citing that evidence; never derived from the materials | MIME |
| **References** (clear) | source registry keys | MADDENING's `Reference(key, description)` | MIME |

### 9.2 Where it does not fit

- **A Vesalius dependency on `maddening.compliance`**: ruled out in section 1.
- **Vesalius nodes or benchmarks**: Vesalius simulates nothing.
- **Clinical applicability**: Vesalius can record conditions, specimen facts and known gaps; deciding that a
  value applies to a patient stays with the user and the manufacturer (section 3.2).

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
| Each family version, in `vesalius-families` | Apache-2.0 | when a product evaluates parameter sets of that family (its own evaluator is the product's code; the family's definition, vectors and check points are what it verifies against) |
| Each library release | CC0-1.0 | when a product uses its materials; otherwise only the product's own records |

Contents, with the Vesalius-specific additions:

1. **Software identification**: name, version, release date, Apache-2.0, repository, PyPI hashes, Python
   versions; **plus** the schema version and the hash of the schema archive; the family versions included
   and the content hash of each; the library release, its DOI, its licence (CC0-1.0) and the hash of its
   archive.
2. **Functional description**: the reader, the writer, the methods, the families, the reference sampler, the
   library; **capabilities not provided**: no clinical interpretation; no assurance that a value applies to a
   use, a patient's included; no validation of files from third parties; no production-grade or differentiable
   evaluation of model families, and no code that runs inside a consumer's computation (constraint 26); no
   description of systems (section 3.1).
3. **Known anomalies**: summary counts, split into code, schema, family and data anomalies (by
   `affected_components`).
4. **Verification evidence**: the conformance suite, method, family and data verification, with pass counts
   per release, the number of fits reported "not checked", and the number of parameter sets with no
   independent witness; the scope statement of section 6.6.
5. **Lifecycle activities**: section 11.
6. **Configuration management**: section 12.
7. **Anomaly management policy**: section 8.
8. **Dependencies (SOUP of SOUP)**: numpy; a JSON Schema validator; OpenUSD, either `usd-core` from PyPI or
   the host application's own build (Isaac Sim ships its own), only with the `[usd]` extra. OpenUSD's
   licence is a modified Apache 2.0 (recalled; check the exact text before the first release).

**Material library contents table**: every material with identifier, version, content hash, sections present,
tier, licence, specimen facts per section, family versions used, number of reviewed values, number of
model-assisted values, and fit-reproduction and witness status (independent witness, or none).

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

- **a content hash per record**: SHA-256 of a canonical serialisation of its values, provenance,
  statistics, uncertainty structures and check points, using an existing canonical JSON scheme that fixes
  how numbers are written (recalled: RFC 8785), so that two writers of the same record produce the same
  hash. A simulation that records the hashes of the materials it used can show it used exactly those values,
  even if a later library version changes them;
- **frozen family versions**, each with a hash of its definition, vectors and reference implementation;
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
manufacturer's design controls must cover the choice of material and the declarations made for it (domain,
target, picks, waivers). The material input sheet of section 9 is meant to make that record easy to produce. A
manufacturer's own measurements fit the same format as a private overlay, with the same provenance and checks.

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
their content hashes, how MIME's own JAX implementations of the value forms, mixing rules and families are
verified (the conformance cases, golden vectors and check points), and the update policy (review the
CHANGELOG's Schema, Families, Data and Known Anomalies sections; rerun MIME's tests; update the pin).

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
6. **No value without provenance.** Every library value has an origin, a source with a locator, an
   extraction method, its conditions, statistics or an uncertainty structure (or `not_reported`), specimen
   facts, a tier and a recorded review.
7. **The specification is normative.** Every normative statement gets a conformance case.
8. **Generated files are never hand-edited.** USD layers, material cards and the index come from the plain
   records; CI checks equality.
9. **Claim hygiene.** Library values are taken from cited sources, or fits to cited data, labelled by origin.
   Biocompatibility is never a safety claim. Nothing in the repository presents a value as validated for a
   patient.
10. **Anomaly entries are never deleted**, only resolved.
11. **No network access and no code execution from data**, at import or when reading files.
12. **The anomaly registry stays in MADDENING's schema** and is checked with MADDENING's validator, a
    development-time dependency only (sections 1 and 8.1).
13. **Fail closed.** A reader refuses an unknown family or version, a failed check point, a request to
    sample an undeclared uncertainty structure, an attribute that was not authored, and interpolation across
    an edge or outside a range. It never guesses.
14. **Check points and a convention witness on every model parameter set.** Check points are computed by the
    family's reference implementation, never typed in; a reference-only set ships none, because they would
    publish its parameters, and its fill-in is checked against the witness instead. The witness is a response
    the source itself reports, independent of how the parameters were obtained, which they must reproduce; a
    parameter set without one is not admitted to the curated library.
15. **Family versions are frozen.** A family is admitted with a definition, golden vectors, a reference
    implementation and a named consumer; any change is a new version.
16. **Nothing non-redistributable is shipped.** A value from a source whose redistribution status is not
    permitted or unknown is reference-only. Every pull request that adds data carries a data attestation.
17. **The curated library's data is CC0-1.0, separate from the code licence**, and every record states the
    licence it is distributed under. A quote kept as evidence is the source's text and is not relicensed.
18. **Shipped USD layers are self-contained**: no composition arcs and no asset paths. `vesalius check`
    enforces it.
19. **Static releases.** Everything needed to use a release is in its archived artefacts. No Vesalius
    feature requires a hosted service, and nothing is fetched from the network unless the user asks.
20. **No model on the read side.** No language model runs in a reader, in `vesalius check`, in a release
    build, or in any consumer's build. Vesalius calls no model and holds no keys; the user's agent brings
    both (architecture draft section 8.1).
21. **Quotes and human review.** Every value in the curated library that was extracted from text or a table
    carries its verbatim quote, locator, document identity and copy hash, whoever or whatever extracted it;
    a value a model helped draft also carries an assistance record. No value of any kind enters a release
    without a human review record; the release build fails closed.
22. **A model never decides.** A model never sets a tier or a redistribution status, converts a unit,
    writes a check point or a witness, or produces a fit result. The MCP tools are scoped so that it
    cannot.
23. **Records hold facts; consumers declare choices** (architecture draft principle 9, section 3.5). No
    record, card, check or default says where, in what state or in which regime a model applies, which
    stand-in is acceptable, which mixing rule to use beyond the identities, or which of competing values
    wins. Declarations, picks and waivers are recorded with the run.
24. **Nothing stands in for a value without saying so** (principle 10). No fallback values on physical
    attributes; no nominal, distribution or extrapolation the source does not give; an unstated condition is
    unknown, never met; every spread says what it represents.
25. **A check is reported for what it can show.** A witness is independent of how the parameters were
    obtained, or the record says "no independent witness". Check points are not presented as evidence about
    a value. An attestation by an interested party says that it is one.
26. **The core never runs inside a consumer's computation.** Readers, mixing rules and model evaluators are
    written by consumers and verified against conformance data, golden vectors and check points. The core's
    numpy references define behaviour and bake check points on the write side; nothing of Vesalius's runs in
    a consumer's step, loop or gradient.
27. **Every record has a record type.** A reader skips types it does not know. Vesalius curates only
    `material` and `interface` records; other namespaces may define types of their own, which share the
    envelope and its checks but are never curated.

---

## Appendix A: Implementation Priority

Scaled down from MADDENING's Appendix B to what a small library needs.

**Phase 0, now (design):** this document; `CONTRIBUTING.md`; `SECURITY.md`; `CHANGELOG.md`; the empty
anomaly registry and its issue template; the pull-request template; `docs/regulatory/intended_use.md`; a
README disclaimer.

**Phase 1, with the first code:** the specification for each release's contents as it is built (architecture
draft section 12.2): first the record format with namespaced identifiers, record types, values, provenance
and required properties (Vesalius 0.1), then uncertainty, model families, geometry (layered paths and their
USD form included) and the USD binding (0.2); the conformance suite; the first family definition
(architecture draft section 12.1, R5) with golden vectors and a reference implementation, in
`vesalius-families`; `python -m vesalius check`; `scripts/check_anomalies.py`, `check_families.py` and
the sign-off check; GitHub labels as MADDENING's (`anomaly:critical`, `anomaly:major`, `anomaly:minor`,
`safety-relevant`, `soup-assessment`, `known-anomaly`).

**Phase 2, with the first library material:** the curation tools of section 5.1 (templates, quote attach-
and-verify, registry drafting, the digitiser, formulation evaluators and check-point bakers), as library
functions with a command line, before the first value is curated; the library repository under CC0-1.0; the
source registry; the data entry standard, review process and takedown procedure; `bibliography.bib`; the
library checks of section 6.5; generated USD layers, cards and index; the legal review of the architecture
draft, section 6.5. The publishers file and a template repository for other publishers come with the first
library release; other hosting items (a data wheel, a viewer) follow their triggers in the architecture
draft, section 6.7. Once the seed library exists: the MCP server, the extraction procedures as method
entries, and the gold set (architecture draft section 8).

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
- [ ] the first family definitions under `families/`, with golden vectors and reference implementations,
  released as the separate distribution `vesalius-families`
- [ ] `python -m vesalius check`, including the namespaced-identifier, self-contained-layer, fallback, table,
  witness, evidence and `--release` checks
- [ ] `scripts/check_anomalies.py`, delegating to MADDENING's validator, run in CI on every push
- [ ] MADDENING's validator accepts a project version field (`vesalius_version`); requested of MADDENING
- [ ] `scripts/check_families.py` and `scripts/check_signoff.py`, run in CI on every pull request
- [ ] GitHub labels as in Appendix A

**Phase 2**

- [ ] the curation tools of section 5.1, before the first value is curated
- [ ] the library repository, under CC0-1.0 (decided 2026-10-12)
- [ ] `sources.yaml` with redistribution statuses
- [ ] `publishers.yaml` and a template repository for other publishers, with MIME's namespace as the first
  entry
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
