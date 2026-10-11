# Vesalius Documentation Architecture Plan

**Status: a plan.** Written 2026-10-11, before any code exists. Appendix B says what is in place. The
architecture of the library itself is in [`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md).

## Executive Summary

**Vesalius** is an OpenUSD material schema and a small Python toolkit. It describes what tissues, phantoms
and devices are made of (acoustic, optical, thermal, fluid, mechanical, radiological and magnetic
properties), binds those descriptions to anatomical and device geometry, and lets any simulator read them.
It is licensed Apache-2.0.

Where it sits:

```
Layer 1  MADDENING    differentiable multiphysics framework       LGPL-3.0-or-later
Layer 1  Vesalius     material schema, library and toolkit        Apache-2.0      <- THIS PROJECT
Layer 2  MIME         microrobotics physics engine                LGPL-3.0-or-later   (uses both)
Layer 3  MICROBOTICA  research simulator and registry             AGPL-3.0
Layer 4  [Commercial product]                                     regulated, CE-marked

Elsewhere: products built on NVIDIA Isaac for Healthcare may read Vesalius materials directly.
```

Vesalius sits beside MADDENING, not on top of it: it has no code dependency on MADDENING or MIME, and it
must stay readable by simulators that use neither (design goal 1 of the architecture draft).

**Why it is likely to become SOUP.** The values Vesalius ships and resolves feed simulations. When a
regulated product is built on MIME, Vesalius is SOUP of SOUP, beside MADDENING. When a product built on
Isaac for Healthcare reads Vesalius materials, Vesalius is SOUP directly. In both cases a wrong value
(a transcription error, a wrong unit, a material resolved to the wrong region) reaches the device's
computation silently. That is the failure this documentation architecture is built around.

**What is different from MADDENING and MIME.** Three things.

1. **Vesalius ships data as well as code.** Its library of materials is part of what a manufacturer would
   assess. The question for the data is not "does the solver converge" but "is this the value the cited
   source gives, in the stated units, under the stated conditions".
2. **There is no physics solver.** The code computes little: unit conversion, mixing rules, interpolation,
   composition into spectra, resolution of which material owns a point. Its documentation replaces the
   algorithm guide with a normative specification and a short method guide (sections 4 and 5).
3. **The read side must work without Vesalius code.** A C++ simulator reading a stage is a consumer too.
   So the specification, not the Python package, is the primary artefact, and its conformance suite is
   the primary verification evidence (section 6).

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
5. [The Method Guide and the Material Library](#5-the-method-guide-and-the-material-library)
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
| 1. Documentation structure | Adapted (section 2) | smaller; a specification and a data guide in place of the algorithm guide |
| 2. Regulatory boundary language | Adapted (section 3) | Apache-2.0, so no LGPL replaceability statement; a data statement added |
| 3. Algorithm documentation standards | Replaced (sections 4, 5) | a normative specification for the read side; a method guide for the write-side computations |
| 4. V&V documentation hooks | Adapted (section 6) | conformance, transcription and plausibility evidence in place of analytical benchmarks |
| 5. Versioning and API stability | Extended (section 7) | three version lines: package, schema, library data |
| 6. UQ documentation | Adapted (section 9) | material ranges become UQ inputs downstream |
| 7. Contributor documentation | Extended (`CONTRIBUTING.md`) | data entry, schema changes, sign-off |
| 8. README | Adopted | |
| 9.1 NodeMeta | Not applicable | no nodes; material provenance and method metadata take its place |
| 9.2 Provenance | New role (section 9) | Vesalius supplies input provenance to MADDENING's run provenance |
| 9.3 Verification registration | Adopted pattern | `VES-VER-` identifiers, registered without a MADDENING import |
| 9.5 Stability machinery | Adopted concept | the same four levels, on schema fields and API surfaces |
| 9.7 Anomaly management | Adopted (section 8) | same schema, fields, enums, lifecycle and gate; data anomalies defined |
| 9.8 ISO 14971 hooks | Adapted (section 8.4) | quantitative conditions and qualitative applicability hints on materials |
| 9.9 Usability | Adapted (section 3.5) | the main use error is applying a value outside its conditions |
| 10. SOUP package | Adapted (section 10) | covers code and data; SOUP of SOUP is numpy and OpenUSD |
| 11. IEC 62304 mapping | Adapted (section 11) | |
| 12, 13. EU MDR, MDCG 2019-11 | Referenced (section 13) | |
| 14. Configuration management | Extended (section 12) | a content hash per material |
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

```
Vesalius/
├── README.md                          # what it is, status, disclaimer, documentation table
├── DOCUMENTATION_ARCHITECTURE.md      # this document
├── CONTRIBUTING.md                    # constraints, sign-off, ID prefixes, data entry, schema changes
├── SECURITY.md                        # vulnerability reporting; trusted-input boundary
├── CHANGELOG.md                       # Keep a Changelog + Schema, Data, Verification, Security, Known Anomalies
├── CITATION.cff                       # from the first release
├── LICENSE                            # Apache-2.0
├── design/
│   └── ARCHITECTURE_DRAFT.md          # architecture concept (layers, data model, USD form, interfaces)
│
├── docs/
│   ├── index.md
│   ├── specification/                 # NORMATIVE; versioned with the schema (section 4)
│   │   ├── schema.md                  # sections, fields, units, defaults
│   │   ├── read_side_contract.md      # what any reader must do (binding, precedence, provenance)
│   │   ├── mixing_rules.md            # one declared rule per field
│   │   └── changes.md                 # schema version history
│   ├── method_guide/                  # write-side computations (section 5.1)
│   │   ├── _template.md
│   │   └── ...                        # one per method: unit conversion, composition, derivations
│   ├── data_guide/                    # the material library (section 5.2)
│   │   ├── data_entry_standard.md
│   │   ├── review_process.md
│   │   └── materials/                 # one data sheet per material, GENERATED from the library
│   ├── user_guide/
│   │   ├── installation.md
│   │   ├── quickstart.md
│   │   └── reading_from_cpp.md        # the read side with USD alone
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
│   └── bibliography.bib               # every source the library or the method guide cites
│
├── src/vesalius/                      # layout in design/ARCHITECTURE_DRAFT.md section 6.1
├── tests/
│   ├── conformance/                   # VES-VER-* read-side cases (language-neutral data + Python runner)
│   ├── methods/                       # method verification
│   └── library/                       # data plausibility and consistency checks
└── scripts/                           # CI checks (section 6.4)
```

Rules for the tree:

- **A folder is created when its first real document arrives.** Empty folders are not committed. The tree
  above is the target, not the current state.
- **Data sheets are generated, never hand-edited.** The library file is the single source of truth; CI
  regenerates the sheets and fails if they differ (as MADDENING does for its stability report).
- **Tooling** follows MADDENING and MIME: Markdown with MyST, Sphinx once a site is worth building,
  Pandoc-style `[@Key]` citations against `docs/bibliography.bib`.

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

> The values in the Vesalius material library are **declarations taken from cited sources**. Vesalius
> warrants that each value is what its source gives, converted correctly to SI, with the conditions and
> range the source reports. Vesalius does **not** warrant that a value describes any particular patient,
> tissue sample, phantom batch or device, nor that a source is itself correct or current. Whether a
> library value is applicable to a given use is the user's and the manufacturer's judgement.
>
> Biocompatibility fields are information about what has been reported for a material. They are never a
> biocompatibility assessment or a safety claim. A manufacturer performs their own ISO 10993 evaluation.

### 3.3 Cybersecurity boundary statement (MDCG 2019-16)

> Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation.
> A USD stage can pull in other files through its composition (sublayers, references, payloads) and
> through the host's asset resolver, so reading a stage may read any file that stage names. Vesalius
> itself makes no network requests and runs no code from the files it reads. Loading third-party stages,
> and the security of the asset resolver, are the responsibility of the integrating application.

### 3.4 Licence note

Apache-2.0 is permissive: no copyleft obligation follows a product that incorporates Vesalius, and the
licence includes an express patent grant. It is compatible with use from MIME and MADDENING
(LGPL-3.0-or-later) and with contributions to Isaac for Healthcare. This is a description, not legal
advice.

### 3.5 Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, data checks |
| Choosing a material and judging its applicability | downstream user | ASME V&V 40 (model inputs) | the user's input justification |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

The use error Vesalius can make less likely is applying a value outside its conditions (a different
temperature, frequency, wavelength, species or tissue state). Vesalius makes the conditions
machine-readable so an integrator can check them (section 8.4).

---

## 4. The Specification

The specification in `docs/specification/` is the primary artefact. It defines the schema and everything a
reader must do, in prose and tables, independently of the Python package. It is **normative**: where the
Python reader and the specification disagree, the reader is wrong.

| Document | Defines |
|---|---|
| `schema.md` | every applied schema, field, SI unit, default, allowed tokens, and its stability level |
| `read_side_contract.md` | binding purpose; precedence of field overrides, label volumes and region bindings; nested regions and background; reading tables and power laws; taking provenance from the layer that supplies the value |
| `mixing_rules.md` | the rule each field declares, with its equation |
| `changes.md` | each schema version, what changed, and the conformance cases that came with it |

Rules:

- **Every normative statement has a conformance case** (section 6.1). A statement without one is marked
  "not yet covered".
- **A change to the specification is a schema change** (section 7.2), whatever the Python code does.
- **The Python reader is one implementation** of the specification, verified like any other.

---

## 5. The Method Guide and the Material Library

### 5.1 Method guide

The write side computes a few things: unit conversions, composition into spectra, derived values (the
Grüneisen parameter from thermal expansion, sound speed and heat capacity), and the mixing rules. Each has a
method guide document, adapted from MADDENING's algorithm guide template (MADDENING section 3):

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

### 5.2 The material library

Each library material has an identifier `VES-MAT-[XXXX]` and lives in its own USD layer. Its data sheet in
`docs/data_guide/materials/` is generated from that layer.

**Data entry standard** (`docs/data_guide/data_entry_standard.md`). Every value carries:

| Field | Required | Notes |
|---|---|---|
| value | yes | a number, a sampled table, or a power law (architecture draft 4.3) |
| unit | implied | always the SI unit the specification fixes for the field |
| kind | yes | declared, measured, fitted or derived |
| source | yes | a `[@Key]` in `docs/bibliography.bib`, with a locator: table, figure, page or equation |
| conditions | where the source states them | temperature, frequency, wavelength, species, tissue state (in vivo, ex vivo, phantom recipe) |
| range | yes, unless the source gives a single exact value | with its basis: spread across sources, reported standard deviation, or reported range |
| reviewer and date | yes | who checked the transcription against the source |

**What review means.** A second person (or the same person on a later day, recorded as such) reads the
source at the locator and confirms the value, the unit conversion and the conditions. The record of that
check is part of the evidence (section 6.3). Agreement with another database is not a review.

**Plausibility and consistency checks** run in CI on the whole library: physical bounds per field (density
and sound speed positive and within broad bounds for condensed matter); consistency between related fields
(impedance against density times sound speed; a derived Grüneisen parameter against one given directly);
completeness of provenance. A check failure blocks the merge.

**What the library is not.** It is not a database of everything published. A material is added when a
consumer needs it, with the sources that consumer relies on.

---

## 6. Verification

Vesalius has no physics to converge, so its verification is of four other kinds. Each verification item has
an identifier `VES-VER-[XXX]`.

### 6.1 Conformance suite (the read side)

Small stages, each with expected answers to queries: the material bound to a prim; a property at a point;
a property at a wavelength or frequency; the owner of a point inside nested regions; the provenance of an
overridden value. The stages and expected answers are data files, so a C++ or other reader can run them
without Python. The Python reader runs them in CI.

### 6.2 Method verification

Each method guide entry has tests against exact or analytical results: unit conversions exactly; mixing
rules against closed-form layered media (series and parallel conduction, effective sound speed of a
layered stack); composition against worked examples in its sources.

### 6.3 Data verification

- the transcription review record for every value (section 5.2);
- the plausibility and consistency checks (section 5.2);
- a round trip: write a material, read it back, compare every value and provenance field.

### 6.4 CI checks

| Script | Checks |
|---|---|
| `scripts/check_anomalies.py` | the registry against the schema of section 8, prefix `VES-ANO-`, by delegating to MADDENING's validator (section 8.1) |
| `scripts/check_citations.py` | every `[@Key]` in the library and the guides exists in `bibliography.bib` |
| `scripts/check_impl_mapping.py` | every function named in a method guide exists |
| `scripts/check_library.py` | provenance completeness, plausibility, consistency, units |
| `scripts/check_datasheets.py` | generated data sheets equal the library |
| `scripts/check_signoff.py` | every commit in a pull request carries a sign-off (section 15) |

### 6.5 What this verification does not provide

It does not show that any library value describes a patient, a tissue sample or a phantom batch. That is
validation of an input for a context of use, which belongs to the user and the manufacturer. Every
verification document states this in a "Scope and Limitations" section, as MADDENING's do.

---

## 7. Versioning and Stability

### 7.1 Three version lines

| Version | Tracks | Where it appears |
|---|---|---|
| Package version (SemVer) | the Python package | `pyproject.toml`, CHANGELOG, SOUP package |
| Schema version (SemVer) | the specification and the USD schema | `docs/specification/changes.md`; recorded on every material |
| Material version | one library material's values | the material's layer; its data sheet; its content hash (section 12) |

Schema: **major** for a removed or renamed field, a changed unit or a changed meaning; **minor** for a new
optional field, section or token; **patch** for wording only. A material: **major** when a value changes
beyond its previous range or a condition changes; **minor** for a new value or section; **patch** for
provenance wording.

### 7.2 Changes to the schema

A schema change needs, in one pull request: the specification text, the conformance cases, the USD schema
files, the reader change, a `changes.md` entry, and a CHANGELOG entry under **Schema**. Removal follows
the stability levels below.

### 7.3 Stability levels

The same four as MADDENING (section 5): experimental, provisional, stable, deprecated. They apply to schema
fields and sections as well as Python API surfaces. A field starts experimental and becomes stable when it
has conformance cases, at least one library material uses it, and it has not changed for one minor schema
version.

### 7.4 CHANGELOG and commit prefixes

`CHANGELOG.md` follows Keep a Changelog with MADDENING's extra sections **Verification**, **Security** and
**Known Anomalies**, plus two of Vesalius's own: **Schema** and **Data**.

Commit prefixes are MADDENING's (`feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `verify`, `break`,
`deprecate`, `security`) plus `schema:` for a schema change and `data:` for a library change.

---

## 8. Anomaly Management

### 8.1 Adopted unchanged

Vesalius adopts MADDENING's anomaly management (MADDENING section 9.7) unchanged: the registry at
`docs/validation/known_anomalies.yaml`; the record fields `anomaly_id`, `title`, `description`, `severity`,
`safety_relevance`, `safety_relevance_rationale`, `affected_components`, `affected_versions`,
`workaround`, `resolution_status`, `resolution_version`, `github_issue`, and the optional `verification`
and `residual_risk`; the enums; the PEP 440 convention for `affected_versions`; the three-phase lifecycle
(issue, then a manual registry entry, then CI checks); the three-tier release gate; and the rule that
entries are never deleted. The registry's version field is `vesalius_version`.

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

### 8.2 Severity, applied to data

The definitions are MADDENING's (section 9.7, "Severity"), repeated here so this document stands alone. A
**wrong result** is a value the library returns, stores or resolves that differs from what Vesalius
documents for it. For data, "what Vesalius documents" is: the cited source, at the stated locator,
converted to the specification's SI unit, under the stated conditions, resolved as the specification
says. A result is **silent** when no exception and no warning accompanied it. **A silent wrong result is
never minor.**

| Severity | Definition, with data examples |
|---|---|
| `critical` | A silent wrong result that a default configuration reaches, that a user cannot detect from anything Vesalius returns, and that no workaround avoids short of not using the feature. Example: the reader resolves the wrong material for nested regions in every stage. |
| `major` | Any other silent wrong result. Examples: a library value that differs from its source; a wrong unit conversion; conditions recorded wrongly; provenance attributed to the wrong layer. A loud failure whose only workaround is not to use the feature. |
| `minor` | A loud failure with a workaround. A wrong statement in documentation where stored values are still right. A defect in performance. A cosmetic defect. |
| `enhancement` | Not a defect: a request for behaviour Vesalius never claimed. |

**Not an anomaly:** a value that faithfully transcribes a source that later proves wrong or is superseded.
That is a data update, recorded under **Data** in the CHANGELOG with a new material version. If the source
is withdrawn for error, the update is made promptly and noted in the release notes.

### 8.3 Identifiers and components

| Category | Prefix | Example |
|---|---|---|
| Anomalies | `VES-ANO-` | `VES-ANO-001` |
| Verification items | `VES-VER-` | `VES-VER-001` |
| Library materials | `VES-MAT-` | `VES-MAT-0001` |
| Methods | `VES-MTH-` | `VES-MTH-001` |

`affected_components` names what is affected without new fields (which would break schema compatibility):
`schema:VesaliusAcousticAPI`, `reader:resolve`, `method:VES-MTH-002`, `data:VES-MAT-0003`.

### 8.4 ISO 14971 inputs

MADDENING separates quantitative regimes from qualitative hazard hints (its section 9.1). Vesalius keeps the
same split on materials:

| On a material | Nature | Example |
|---|---|---|
| conditions and ranges | quantitative | measured at 37 °C, 1 to 10 MHz; range 1540 to 1610 m/s |
| applicability hints | qualitative | "adult human liver, ex vivo; not for fatty or fibrotic liver" |

A given limitation appears in exactly one of the two. Both are technical statements about the data, not
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
| **Input provenance for a run** (clear) | `collect_material_inputs(stage)`: every property value a set of prims resolves to, with material identifier and version, content hash, kind, source, range, conditions, and the layer it came from. Exported as JSON and as a Markdown "material input sheet" | MADDENING's `SimulationProvenance.custom` (`MADD:src/maddening/core/compliance/provenance.py`); a credibility assessment's model-input evidence; MADDENING's context-of-use template | MIME writes the record into the run's provenance |
| **Uncertainty inputs** (clear) | ranges with their basis | MADDENING's `UncertainParameter` (nominal, lower, upper, units, description) for UQ | MIME builds `UncertainParameter` from a range |
| **Operating-point checks** (clear) | conditions and material values | MADDENING's `ValidatedRegime` checks against computed operating points (Reynolds number, Mach number) | MIME |
| **One anomaly schema** (clear) | `VES-ANO-` entries in MADDENING's format | one combined risk file; MIME entries can cite `VES-ANO-` entries as they cite `MADD-ANO-` ones | none needed |
| **Biocompatibility** (partial) | a material's biocompatibility section | MIME's `BiocompatibilityMeta` (materials, tested flags, hazard hints) derived from a body's materials instead of typed in | MIME |
| **References** (clear) | `[@Key]` sources | MADDENING's `Reference(key, description)` | MIME |

### 9.2 Where it does not fit

- **A Vesalius dependency on `maddening.compliance`**: ruled out in section 1.
- **Vesalius nodes or benchmarks**: Vesalius simulates nothing.
- **Clinical applicability**: Vesalius can record conditions and hints; deciding that a value applies to a
  patient stays with the user and the manufacturer (section 3.2).

### 9.3 What this would add to Vesalius

A small `vesalius.compliance` module, pure Python, with no dependency beyond the core:

- the anomaly record and registry check in MADDENING's shape (section 8);
- `collect_material_inputs` and the material input sheet;
- content hashes for materials (section 12).

This is a proposal. It is cheap because the provenance is already in the data model; the module only
gathers it. Its value is that a simulation's inputs become as traceable as its code, automatically.

---

## 10. SOUP Package

`docs/validation/soup_package.md`, from the first release, follows MADDENING's template (section 10) with
these Vesalius-specific contents:

1. **Software identification**: name, version, release date, Apache-2.0, repository, PyPI hashes, Python
   versions; **plus** the schema version and the hash of the schema archive.
2. **Functional description**: the reader, the writer, the methods, the library; **capabilities not
   provided**: no clinical interpretation; no assurance that a value applies to a patient; no validation of
   files from third parties.
3. **Known anomalies**: summary counts, split into code, schema and data anomalies (by
   `affected_components`).
4. **Verification evidence**: the conformance suite, method verification and data verification, with
   pass counts per release; the scope statement of section 6.5.
5. **Lifecycle activities**: section 11.
6. **Configuration management**: section 12.
7. **Anomaly management policy**: section 8.
8. **Dependencies (SOUP of SOUP)**: numpy; OpenUSD, either `usd-core` from PyPI or the host application's
   own build (Isaac Sim ships its own). OpenUSD's licence is a modified Apache 2.0 (recalled; check the
   exact text before the first release).

**Material library contents table**: every material with identifier, version, content hash, sections
present, and number of reviewed values.

---

## 11. IEC 62304 Lifecycle Mapping

Vesalius is not subject to IEC 62304. This mapping is voluntary, as MADDENING's is (section 11).

| Phase | Clause | What Vesalius provides |
|---|---|---|
| Development planning | 5.1 | `design/ARCHITECTURE_DRAFT.md`, this document, `CONTRIBUTING.md`, Git and CI |
| Requirements | 5.2 | `docs/specification/` (normative) |
| Architectural design | 5.3 | `design/ARCHITECTURE_DRAFT.md` layers; no shared mutable state; the read side needs no Vesalius code |
| Detailed design | 5.4 | the specification and the method guide, with Implementation Mappings |
| Unit implementation | 5.5 | source code, NumPy-style docstrings |
| Unit verification | 5.6 | conformance, method and data verification (section 6) |
| Integration testing | 5.7 | round trips; reading stages produced by downstream pipelines |
| System testing | 5.8 | the conformance suite run against more than one reader, when a second exists |
| Release | 5.9 | CHANGELOG, tags, PyPI, registry, SOUP package, SBOM |

---

## 12. Configuration Management

Adopted from MADDENING section 14: Git with full history; tagged releases; PyPI hashes; `CITATION.cff` from
the first release; a CycloneDX SBOM per release, generated from a clean install, as MADDENING does.

Vesalius adds:

- **a content hash per material**: SHA-256 of a canonical serialisation of its values and provenance. A
  simulation that records the hashes of the materials it used can show it used exactly those values, even
  if a later library version changes them;
- **the schema archive** (the L0 files) released with its own hash, so a C++ project can vendor exactly
  the version it was built against;
- **signed release tags** (recommended, as in MADDENING).

---

## 13. EU MDR, MDCG 2019-11 and QMS

Referenced, not repeated: MADDENING sections 12 (EU MDR Annex I and II), 13 (MDCG 2019-11) and 15 (QMS
compatibility) apply to Vesalius unchanged in principle. Vesalius is general-purpose software with no
medical purpose; a commercial manufacturer assesses it as SOUP within their ISO 13485 QMS; Vesalius
operates under no QMS and says so.

One addition for a manufacturer's design inputs: library values are inputs to their simulation, so the
manufacturer's design controls must cover the choice of material and its applicability. The material input
sheet of section 9 is meant to make that record easy to produce.

---

## 14. Downstream Integration

`docs/regulatory/downstream_integration.md` would document two chains:

```
Chain 1                                        Chain 2
[Commercial product]                           [Commercial product on Isaac for Healthcare]
  └── MICROBOTICA                                ├── Isaac for Healthcare components
       └── MIME                                  └── Vesalius   (SOUP)
            ├── MADDENING  (SOUP of SOUP)
            └── Vesalius   (SOUP of SOUP)
```

**What MIME's SOUP package section 8 must list for Vesalius**, following MADDENING's pattern for itself
(MADDENING section 16): the pinned Vesalius version, the schema version, links to Vesalius's version-tagged
SOUP package and anomaly registry, the PyPI hash, the SBOM, a table of Vesalius anomalies relevant to MIME,
the library materials MIME's experiments use with their content hashes, and the update policy (review the
CHANGELOG's Schema, Data and Known Anomalies sections; rerun MIME's tests; update the pin).

**For a product on Isaac for Healthcare**: the same items, plus which reader they use (Vesalius's Python
reader, or their own against the specification). An independent reader must pass the conformance suite to
claim conformance to a schema version.

---

## 15. Project Constraints

Binding on every contribution. `CONTRIBUTING.md` holds the operational detail.

1. **Sign-off on every commit** (Developer Certificate of Origin), from the first code commit. The design
   commits that precede the first code are exempt. CI enforces it once code exists.
2. **Apache-2.0** for all contributions. No runtime dependency under a copyleft licence.
3. **No runtime dependency on a simulator or ML framework**: not MIME, MADDENING, JAX, PyTorch, Warp or
   Isaac. Core: numpy only. USD is an optional extra and is imported from whatever build is installed.
4. **The read side stays implementable with USD alone.** Anything that needs computing is baked when a
   material is written. A change that would require reader code beyond the specification is a major schema
   change.
5. **SI units in stored values, always.** Conversion happens in importers and adapters.
6. **No value without provenance.** Every library value has a kind, a source with a locator, a range or a
   reason for none, and a recorded review.
7. **The specification is normative.** Every normative statement gets a conformance case.
8. **Generated documents are never hand-edited.** Data sheets come from the library; CI checks equality.
9. **Claim hygiene.** Library values are declarations. Biocompatibility is never a safety claim. Nothing in
   the repository presents a value as validated for a patient.
10. **Anomaly entries are never deleted**, only resolved.
11. **No network access and no code execution from data**, at import or when reading files.
12. **The anomaly registry stays in MADDENING's schema** and is checked with MADDENING's validator, a
    development-time dependency only (sections 1 and 8.1).

---

## Appendix A: Implementation Priority

Scaled down from MADDENING's Appendix B to what a small library needs.

**Phase 0, now (design):** this document; `CONTRIBUTING.md`; `SECURITY.md`; `CHANGELOG.md`; the empty
anomaly registry and its issue template; `docs/regulatory/intended_use.md`; a README disclaimer.

**Phase 1, with the first code:** the specification for the 0.1 sections (architecture draft section 9);
the conformance suite; `scripts/check_anomalies.py`; the sign-off check; GitHub labels as MADDENING's
(`anomaly:critical`, `anomaly:major`, `anomaly:minor`, `safety-relevant`, `soup-assessment`,
`known-anomaly`).

**Phase 2, with the first library material:** the data entry standard and review process;
`docs/bibliography.bib`; `check_citations.py`, `check_library.py`, `check_datasheets.py`; generated data
sheets.

**Phase 3, at the first release:** `CITATION.cff`; the SOUP package; the SBOM; `iec62304_mapping.md`;
`downstream_integration.md`; signed tags.

**Phase 4, when MIME adopts it:** `vesalius.compliance` (section 9); MIME's SOUP package section 8 entry
for Vesalius.

---

## Appendix B: Bootstrap Checklist

Status at 2026-10-11.

**Phase 0**

- [x] `design/ARCHITECTURE_DRAFT.md`
- [x] `DOCUMENTATION_ARCHITECTURE.md` (this document)
- [x] `CONTRIBUTING.md` with the constraints of section 15, the ID prefixes and the anomaly lifecycle
- [x] `SECURITY.md` with a reporting contact, response times, and the trusted-input boundary of section 3.3
- [x] `CHANGELOG.md` in Keep a Changelog format with Schema, Data, Verification, Security and Known Anomalies
- [x] `docs/validation/known_anomalies.yaml` with `schema_version`, `vesalius_version`, `generated_date`
  and an empty `anomalies` list
- [x] `.github/ISSUE_TEMPLATE/anomaly.yml` with MADDENING's mandatory fields
- [x] `docs/regulatory/intended_use.md` with the statements of sections 3.1 to 3.5
- [x] README disclaimer and documentation table

**Phase 1**

- [ ] `docs/specification/` for the 0.1 sections, every normative statement with a conformance case
- [ ] `tests/conformance/` with stages and expected answers as data files
- [ ] `scripts/check_anomalies.py`, delegating to MADDENING's validator, run in CI on every push
- [ ] MADDENING's validator accepts a project version field (`vesalius_version`); requested of MADDENING
- [ ] `scripts/check_signoff.py`, run in CI on every pull request
- [ ] GitHub labels as in Appendix A

**Phase 2**

- [ ] `docs/data_guide/data_entry_standard.md` and `review_process.md`
- [ ] `docs/bibliography.bib` and `scripts/check_citations.py`
- [ ] `scripts/check_library.py` and `scripts/check_datasheets.py`
- [ ] the first library material with a complete review record

**Phase 3**

- [ ] `CITATION.cff`
- [ ] `docs/validation/soup_package.md`
- [ ] SBOM under `docs/validation/sbom/`
- [ ] `docs/regulatory/iec62304_mapping.md` and `downstream_integration.md`

**Phase 4**

- [ ] `vesalius.compliance` with `collect_material_inputs` and content hashes
- [ ] MIME's SOUP package lists Vesalius in its section 8
