# Vesalius: an architecture concept

**Status: a concept draft for iteration.** Written 2026-10-11 in the shared planning directory (first as
`plans/MIME_MATERIAL_MODEL_DRAFT.md`), moved here the same day, and revised the same day after a design
review (section 14). Referenced from `plans/MIME_030_STRUCTURE_DRAFT.md` (the **structure draft**) but not
part of MIME's design yet: the maintainer wants to iterate on it first.

**Decided (maintainer, 2026-10-11):**

- Materials for multiphysics simulation become a standalone package, **Vesalius**, not part of MIME. The
  name was free on PyPI when checked on 2026-10-11. FLESH was considered and dropped.
- Code licence: **Apache-2.0**.
- **OpenUSD is the primary binding**, and the expected long-term one for scenes. Vesalius must still never
  require it: plain records are a complete form of their own (section 5).
- Commits carry a sign-off from the first code commit (`CONTRIBUTING.md`).
- Photoacoustic imaging in MIME: good to have in 0.3.0 but not necessary; expected by MIME 0.5.0 to 0.6.0
  (Appendix A).

Everything else here is a proposal.

Origin: a sketch by the maintainer of a photoacoustic chain (optics, a thermoelastic step, acoustics, the
FVM), offered as a vague idea to extract the core from. Its core is that one description of a tissue,
phantom or device has to feed many physics, and many simulators.

How to read it: a statement with a file path was read in the tree or checked by running something;
"recalled" marks something from memory that was not checked; "would" marks a proposal. Paths are relative
to the workspace that holds the sibling repositories: `MIME:` marks a MIME path, `MADD:` a MADDENING path,
`plans/` the shared planning directory (not versioned), and `i4h:` an Isaac for Healthcare repository.

## 1. What Vesalius is

An open description of what bodies, tissues, phantoms and devices are made of, for simulation: one
**material record** per substance, with a section per physics, every value in SI with its provenance and
its uncertainty. Records are plain files that any language can read. OpenUSD is the primary way to bind
them to scene geometry, but a consumer without USD (a one-dimensional layered model, a finite-element code,
a MATLAB script) uses the same records.

Design principles:

1. **The read side needs no Vesalius code.** A C++ renderer, a JAX solver and a PyTorch policy trainer read
   the same records with nothing but a JSON parser, or with USD.
2. **No solver dependency.** Vesalius knows nothing of MIME, MADDENING, JAX, Warp or Isaac.
3. **Provenance and uncertainty on every value**, stated, never implied.
4. **Fail closed.** An unknown model family or version, an undeclared uncertainty structure, or a check
   point that disagrees makes a reader refuse, never guess.
5. **Data carries its own verification.** A record holds the check points that let any consumer confirm it
   reads the values as intended (section 4.6).
6. **Mechanism in the core, content outside it.** The core defines how families, records and checks are
   declared and verified. Model families and the material library are separately versioned content
   (section 3.1), as MIME's physics is content on MADDENING's mechanism.
7. **Small.** A section, a family or a library material enters only when a consumer needs it (section 7.6).

What Vesalius is not:

- not a solver, a mesher, a segmenter or a renderer;
- not a database service, and not a host for large datasets;
- not a constitutive-model library for production use: reference implementations exist to define and
  verify, not to run in loops;
- not a judge of whether a value applies to a patient;
- not a store of patient data;
- not a source of safety or biocompatibility claims (MICROROBOTICA's rule carries over: biocompatibility
  fields are information, never a safety claim);
- not MIME. MIME is one consumer.

## 2. Why it is needed

No layer in MIME, MADDENING or Isaac for Healthcare carries multiphysics material properties alongside
geometry today.

| Where | What it holds about materials | Source |
|---|---|---|
| MIME `Medium`, `Body` | property dicts, checked for presence only; robot materials as names (`("SU-8", "NdFeB")`) | scope doc H1; structure draft 8.1 |
| MIME `MimeAssetSchema` | biocompatibility and other metadata per asset; "On disk: USD (Phase 4)" | `MIME:src/mime/schema/asset.py:1-12` |
| MIME scene files | no material attributes | `MIME:experiments/*/scene/*.usda` |
| MADDENING USD schema | the graph only: simulation graph, node, edge, coupling group, external input | `MADD:src/maddening/usd/schema/` |
| USD's physics material | density, static and dynamic friction, restitution | `UsdPhysics.MaterialAPI`, checked with USD 0.26.5 |
| Isaac for Healthcare, ultrasound | six tissues hard-coded in C++ (water, blood, fat, liver, muscle, bone): impedance, attenuation, sound speed, four speckle parameters | `i4h:i4h-sensor-simulation/ultrasound-simulator/csrc/core/material.cpp`, read 2026-10-11 |
| Isaac for Healthcare, X-ray | a linear map from CT number to attenuation, by default -1000 to 3000 HU onto 0 to 0.02 per mm | its X-ray simulator README, read 2026-10-09 |
| Isaac for Healthcare, patient twin | meshes, labels and centrelines; no material or property files in its tree | path search, 2026-10-11 |

Each tool elsewhere describes media its own way (recalled): k-Wave as medium arrays, Monte Carlo light
codes as layer or media tables, finite-element codes as material cards in their own conventions. Nothing
carries one tissue across them. Projects that calibrate tissue models from literature typically keep one
code module per source paper and a separate list of sources, with nothing tying one tissue's mechanical,
acoustic, dielectric and optical parameters to one record.

## 3. Architecture

### 3.1 Mechanism and content

```
vesalius core          mechanism                                   Apache-2.0          SOUP-relevant
  specification; record JSON Schema; USD schema; record model and I/O; verification machinery
  (check points, conformance, uncertainty structures); a reference sampler

family packages        content: model-family definitions            Apache-2.0
  one namespaced, separately versioned definition per family: equations, golden test vectors,
  reference implementation, admissibility

library repository     content: curated materials                   a data licence (section 6.4)
  its own releases, review process and DOI
```

- The core changes rarely. Families and materials grow only when a consumer needs them.
- Anyone can publish families in their own namespace under the same evidence rules (section 4.5).
- A manufacturer assesses the core plus only the families and materials it uses, each with its own version
  and content hash (`DOCUMENTATION_ARCHITECTURE.md` section 10).
- Whether families start as subpackages of this repository or as separate distributions, and whether
  reference implementations sit in the core or with their families, are open questions 4 and 5.

### 3.2 Layers inside the core

```
 L6  Adapters             MIME adapter (in MIME); exporters, importers, Isaac adapters (vesalius.integrations)
       ^
 L5  Sampling (optional)  volume fractions on a consumer's grid; layered paths derived from 3-D geometry
       ^
 L4  I/O                  plain records (required); USD (optional extra)
       ^
 L3  Authoring            composition to spectra, derived values, fit bookkeeping, check-point baking
       ^
 L2  Core (numpy)         records, values, provenance, statistics, uncertainty structures, units,
                          mixing rules, validation
       ^
 L1  Data                 conformance cases, family golden vectors, spectra tables              (no code)
 L0  Schema               record JSON Schema; schema.usda, generatedSchema.usda, plugInfo.json  (no code)
```

Rules:

- A layer imports only layers below it. L0 and L1 need nothing at all.
- Nothing imports a simulator. Adapters for a simulator import it lazily and live where their owners
  choose: MIME's adapter in MIME; exporters, importers and Isaac adapters in `vesalius.integrations` until
  someone upstream wants them.
- USD is an optional extra (section 7.2).

### 3.3 Two kinds of user

| | Writes materials | Reads materials |
|---|---|---|
| Who | library curators; a lab characterising a phantom; a fit writing results back | every simulator |
| Needs | L2, L3, L4 (Python) | L0, plus a JSON parser or USD, in any language; optionally L2 and L5 in Python |
| Does | composes, converts units, derives, fits, bakes values, statistics and check points with provenance | reads SI numbers and parameter sets, interpolates tables, evaluates power laws, applies declared mixing rules, verifies check points |

Everything that needs computing happens on the write side. A reader evaluates a model family only with its
own implementation, which it verifies against the record's check points. This is what keeps C++ consumers
first class (section 7.5).

### 3.4 One source of truth

Library materials are authored in one form and the other is generated from it, never edited. The lean is
plain records as the source, with USD layers generated (open question 1). A round-trip check in CI keeps
the two forms equal. Scene-level overrides, such as a fit for one scene, may be authored as USD layers or
as plain overlay records; both name the base record by identifier, version and content hash.

## 4. The data model

### 4.1 Material, section, value

- A **material** has an identity (identifier, name, version), the record-schema version it was written
  against, a content hash (section 5.5), and any subset of sections.
- A **section** is one physics. A consumer checks only the sections it needs.
- A **value** takes one of five forms (section 4.4), in fixed SI units, with provenance (section 4.7),
  statistics or an uncertainty structure (section 4.9), and the conditions it holds at (section 4.8).

### 4.2 Sections

| Section | Example contents (SI) | Typical consumers |
|---|---|---|
| Fluid | density, viscosity, rheology model | fluid solvers |
| Mechanical | parameter sets by model family: linear elastic, hyperelastic, viscoelastic, rate-dependent forms | soft tissue, compliant walls, rods, needle and tool insertion, contact |
| Acoustic | sound speed, density, attenuation as a power law in frequency, nonlinearity B/A | ultrasound, acoustic actuation, photoacoustics |
| Optical | absorption and scattering spectra, scattering anisotropy, refractive index | photoacoustics, fluorescence, photothermal, optical coherence tomography |
| Thermal | conductivity, heat capacity, perfusion, thermal expansion, Grüneisen parameter | bioheat, photoacoustics |
| Dielectric | conductivity and permittivity, as tables over frequency or as Debye or Cole-Cole parameter sets | capacitive and impedance sensing, MRI RF heating, electromagnetic tracking, ablation |
| Radiological | attenuation against photon energy, or elemental composition | X-ray, CT |
| Magnetic | susceptibility, remanence, saturation | robots, implants, coils |
| Biocompatibility | status, standard, notes | asset cards, registries |

Mechanics is organised by model family, not by Young's modulus and Poisson's ratio: linear elasticity is one
family among several, and most soft tissue needs another.

### 4.3 Laws, tables and composition

- **Store laws, not values at one operating point.** Optical properties depend on wavelength, acoustic
  attenuation on frequency, most properties on temperature.
- **Composition is a write-side input.** Tissue optics is usually derived from volume fractions of water,
  blood (with its oxygenation), lipid and melanin, times tabulated spectra (recalled: Jacques 2013). A
  material may record its composition, but the absorption spectrum a reader sees is the baked table.
  Composition is also what transport changes in a simulation (Appendix A.2), so a consumer that varies it
  uses the L3 functions, not the file.
- **Derived values say so.** The Grüneisen parameter can be measured or derived from thermal expansion,
  sound speed and heat capacity. Either is fine if labelled.

### 4.4 Five value forms

| Form | Read side | Example |
|---|---|---|
| Constant | read the number | density |
| Sampled table | linear interpolation over the declared axis | absorption against wavelength |
| Power law `a * x^b` | evaluate | attenuation against frequency |
| Model parameter set | evaluate the named family with your own implementation, after verifying the record's check points | a hyperelastic fit; a Cole-Cole fit |
| Reference data | read; used to check fits, never as a property | a digitised stress-stretch curve; a measured spectrum |

The first three are the only forms a reader computes from directly. Anything richer than a table or a power
law is either evaluated on the write side and baked into one of them, or is a model parameter set, whose
meaning the family definition fixes.

### 4.5 Model families

A model family is identified by a namespaced, versioned identifier, for example
`vesalius.mechanical.ogden_incompressible.v1` or `<org>.dielectric.cole_cole_4term.v1`, never by a common
name alone. The same name hides different formulas in different solvers and papers (as I recall, Ogden's
strain energy appears with different factors on its coefficients and with different volumetric terms), so
a name alone lets one parameter set give different stresses in two solvers with no error anywhere.

A family definition (a document and its data files) fixes:

| Item | Contents |
|---|---|
| Kinematics and outputs | the deformation or input measure (stretch, Green-Lagrange strain, frequency), the output measure (Cauchy or first Piola-Kirchhoff stress, complex permittivity), the loading modes covered |
| Equations | the energy or response function, normatively; the treatment of incompressibility |
| Parameters | names, units, meaning, order |
| Admissibility | constraints a parameter set must satisfy, for example stability conditions |
| Golden test vectors | inputs and expected outputs at a stated precision, as data files; edge cases; admissibility cases |
| Reference implementation | plain numpy, written for clarity: the executable form of the definition |
| References | `[@Key]` citations |

Rules:

- Changing anything in a definition creates a new version. Golden vectors are frozen per version.
- A reader that meets a family identifier or version it does not know refuses the value.
- Records hold parameters only in the family's own convention. Conversion to a particular solver's
  convention happens in an adapter or exporter (L6), and each conversion has its own vectors showing that
  the solver's form reproduces the family's outputs.
- A family is admitted with a definition, golden vectors, a reference implementation and a named consumer
  (`DOCUMENTATION_ARCHITECTURE.md` section 6.4). A family with no consumer for two releases is deprecated.

### 4.6 Check points in records

When a model parameter set is written, the reference implementation of its family version computes the
response at a handful of states (stated deformations, rates, frequencies, loading modes), and the record
stores those input-output pairs with a tolerance. Before using the parameters, a consumer evaluates its own
implementation at the same states and compares. A mismatch is a refusal.

- A convention mismatch then fails loudly even for a consumer that never ran the conformance suite.
- Check points travel with the record into overlays, USD layers and private copies.
- They are required for model parameter sets and optional for the other forms, where they add little.

### 4.7 Provenance

Each value carries:

| Field | Contents |
|---|---|
| kind | declared, measured, fitted or derived |
| source | a key in the source registry (section 6.1) with a locator: table, figure, page or equation |
| extraction | the method: a table; the text; digitised from a figure (with the tool and an estimate of digitising error); a supplementary dataset (with its licence); an own measurement; a derivation (with a method identifier); a fit (with its fit record, section 4.10) |
| conditions | section 4.8 |
| statistics or uncertainty structure | section 4.9 |
| proxy | section 4.11 |
| review | who checked the value against the source, and when; the curator's ORCID |
| tier | shipped, reference-only or private (section 6.2) |

A value from a table is a declaration until something fits it (`MIME:CLAUDE.md`).

### 4.8 Conditions

A controlled vocabulary with an extension mechanism: temperature, frequency, wavelength, strain rate,
loading mode, specimen orientation, donor age, preservation and post-mortem interval, species, anatomical
site, tissue state (in vivo, ex vivo, phantom recipe). Anatomical site and species would use existing
ontology identifiers (recalled: UBERON and the NCBI Taxonomy), so records link to other biomedical data.

### 4.9 Statistics and uncertainty structures

Literature tissue properties often vary by a factor of two or more between sources (recalled), so a value
without its spread is not honest.

- **Scalar values** carry a statistics block, not just a range: number of specimens and donors, mean,
  standard deviation, minimum, maximum, the distribution if the source states one, and the basis
  (reported standard deviation, reported range, spread across sources, digitising error). Where a source
  gives only a range, the range is recorded with that basis.
- **Parameter sets** declare an uncertainty structure. There is no default.

| Structure | Contents | Note |
|---|---|---|
| `ensemble` | one fitted parameter vector per specimen or donor | preferred: keeps the dependence between parameters without assuming a distribution |
| `multivariate_normal` | mean and covariance in a declared space (identity or log, per parameter) | the form a fit's covariance arrives in |
| `independent` | one marginal per parameter | only with a stated justification for independence |
| `none` | nominal values only | must not be sampled |

Fitted parameters are strongly correlated as a rule, so sampling each from its own range produces
combinations that describe no real material, and some that the family's admissibility constraints forbid.
Sampling therefore happens in the declared space, maps back, and rejects draws that violate admissibility,
reporting how many it rejected. A consumer that cannot honour the declared structure refuses to sample and
uses the nominal values. The core ships a reference sampler for tests and simple consumers; production
uncertainty quantification belongs to the consumer (for MIME, to MADDENING: section 8.4).

### 4.10 Fits and reference data

A fitted parameter set records what it was fitted to: the reference data (by identifier, or by DOI and
content hash where the data are not shipped), the fit procedure, the loading modes and ranges covered, and
the residual. Its validity envelope is that coverage.

Fitted parameters are not intrinsic material properties. They belong to a material, a model, a test
protocol and a fitting procedure together, and several parameter sets can fit one curve equally well. So
sources are compared on curves, not on parameters.

The fit-reproduction check (`DOCUMENTATION_ARCHITECTURE.md` section 6.3) evaluates the parameter set
against its reference data and requires the stated residual. Where the reference data are not shipped, it
reports "not checked", never a pass.

### 4.11 Proxies

Much tissue data comes from a stand-in: another species, another anatomical site, a cadaver for living
tissue, a phantom for tissue. A value records that it is a proxy, for what, and why. Proxy status is per
section or per field, not per material, because a stand-in can be acceptable for one physics and not for
another (a porcine sample may be a fair acoustic proxy and a poor mechanical one).

### 4.12 Mixing rules

A cell that is part tissue and part vessel needs one value per property, and the right average depends on
the property: absorption and density average by volume; compressibility and heat conduction across a layer
do not. Each field declares its rule in the schema (section 5.3), so any consumer can apply it. The rules
themselves live in L2, written against the Python array API standard, so numpy, JAX and PyTorch callers
share one implementation (recalled: jax.numpy follows that standard). They are simple elementwise
averages; this is the one place the core's code runs inside a consumer's computation.

### 4.13 Interfaces between materials

Some properties belong to a pair, not to one material: friction and lubrication between a catheter or needle
and tissue, thermal contact resistance, a slip condition. These would sit on an **interface** record that
names two materials. USD's own physics material puts friction on single materials and leaves the
combination to the engine (recalled), which loses the pair. Open question 11.

### 4.14 Appearance is not physics

Isaac for Healthcare's ultrasound table mixes physical properties (impedance, attenuation, sound speed) with
renderer settings (speckle parameters). Vesalius holds the physical ones. A renderer's settings sit on the
same material in the renderer's own namespace (section 10.1).

## 5. Geometry, records and the USD binding

### 5.1 The geometry ladder

Four representations bind the same material records, so moving a project from one to another changes the
geometry and not the materials.

| Representation | Geometry | Typical use |
|---|---|---|
| Layered path | an ordered list of (material, thickness) along a path from an entry point; lateral homogeneity assumed and declared | needle or catheter insertion; a transducer through tissue layers; layered optical models |
| Region binding | a material bound to a closed mesh | organs, vessels, devices |
| Label volume | an integer volume with a table from label to material | a segmented scan from a patient twin |
| Field override | a volume field per property | CT-derived attenuation; measured sound-speed maps |

- **Precedence** among the three 3-D representations, where they overlap: field override, then label
  volume, then region binding.
- **Nested regions** (a vessel inside an organ inside the abdomen): an explicit integer priority on the
  binding, defaulting to depth in the hierarchy, decides which material owns a point.
- **Background**: a stage-level default material for points no region claims (water, air, agar).
- A **layered path** is a geometry of its own, read by one-dimensional consumers. A sampling helper (L5)
  would derive a layered path from 3-D geometry along a trajectory, which is also how a project checks a
  hand-authored path against anatomy once it has the anatomy.
- Thicknesses and other geometry are scene data, not material data. They may carry their own provenance (an
  anatomical atlas, an image), recorded in the scene.

### 5.2 Plain records

A record is a JSON or YAML document valid against the record JSON Schema. A layered path without USD is a
small document listing its intervals and the material identifiers, versions and content hashes they bind.
The conformance suite covers the plain form completely; a consumer never needs USD to use Vesalius.

### 5.3 USD schemas

Checked on 2026-10-11 with USD 0.26.5 and a one-schema prototype in a scratch directory; nothing in a
repository.

- One **single-apply API schema per section**: `VesaliusFluidAPI`, `VesaliusMechanicalAPI`,
  `VesaliusAcousticAPI`, `VesaliusOpticalAPI`, `VesaliusThermalAPI`, `VesaliusDielectricAPI`,
  `VesaliusRadiologicalAPI`, `VesaliusMagneticAPI`, `VesaliusBiocompatibilityAPI`. Attributes are
  namespaced `vesalius:<section>:<field>`.
- A **mixing rule per field** as a token attribute beside it, for example
  `vesalius:acoustic:soundSpeed:mixing = "harmonic"`, with its default in the schema.
- **Resource-only**: `schema.usda` as the source, `generatedSchema.usda` and `plugInfo.json` as the
  registered form, no compiled library. MADDENING already ships its graph schema this way
  (`MADD:src/maddening/usd/__init__.py:29`).
- Model parameter sets, statistics, uncertainty structures and check points have no USD encoding yet:
  structured attributes, dictionary metadata on the field, or a reference to the plain record (open
  question 7).

Checked in the prototype:

- the plug-in registers at run time; `ApplyAPI("VesaliusAcousticAPI")` and `HasAPI` work by name;
- schema defaults are visible on a material before anything is authored (sound speed read 1540, the
  schema's default);
- the plug-in entry must carry `schemaIdentifier`. An `alias` equal to the type's name is refused.

Generated C++ classes are not needed; USD can generate them from the same `schema.usda` if a consumer wants
typed access (recalled).

### 5.4 Materials and binding in USD

- A material is a `UsdShade.Material` prim with the section APIs it needs, plus `UsdPhysics.MaterialAPI` for
  density, so physics engines that read only that still see something.
- Geometry binds it with `UsdShade.MaterialBindingAPI` and a purpose. Checked: binding with purpose
  `"physics"` writes `material:binding:physics`, and `ComputeBoundMaterial("physics")` resolves it; a
  purpose of our own resolves only to its own binding or the all-purpose one.

| Binding purpose | For | Against |
|---|---|---|
| Reuse `physics` (lean) | one binding per mesh; engines that read physics materials see the same prim | other tools meet our schemas on that prim |
| A purpose of our own | no interference | a second binding to keep consistent; physics engines miss it |

- **Field overrides and label volumes** use `UsdVol` (checked: `UsdVol` has `OpenVDBAsset` and
  `Field3DAsset`).
- **Layered paths** need a USD form, so a project can move from one dimension to a full scene without
  changing representation. Two candidates: a typed prim of our own (a path plus ordered interval arrays and
  a relationship per interval), or a `BasisCurves` prim with one `GeomSubset` per interval bound to its
  material. Open question 3.
- Geometry units follow the stage's `metersPerUnit`; property values are SI whatever the stage says.

### 5.5 Declared, then fitted

USD composition gives a declared-then-fitted history for free. A library layer holds declared values; a
scene references it; a fit writes a stronger layer with fitted values and its own provenance. The declared
values stay intact underneath. Checked: a fitted 1555 m/s in a stronger layer composed over a declared
1570 m/s, and the root layer still held 1570. Plain records do the same with overlay records.

**A trap the prototype found.** USD merges dictionary metadata key by key across layers. When the fitted
layer wrote its provenance without a range, the composed provenance read "fitted" with the declared value's
range. So:

- readers take provenance from the layer that supplies the value, not from the composed dictionary.
  Checked: the first spec in `GetPropertyStack()` with a default value gave the fitted provenance alone;
- writers write every provenance key;
- a plain overlay replaces a value's provenance whole, never key by key.

The conformance suite (section 7.4) contains this case.

### 5.6 Versions and hashes

- The record schema and the USD schema share one semantic version, independent of the package's. Additive
  changes are minor; removals, renames and changes of meaning are major, with a deprecation period.
- Every material records the schema version it was written against.
- Each family version is frozen (section 4.5).
- Each material has its own version and a **content hash**: SHA-256 of a canonical serialisation of its
  values, provenance, statistics and check points. A simulation that records the hashes of the materials it
  used can show it used exactly those values.

## 6. The library: sources, tiers and licences

Not legal advice. As far as I could find (2026-10-11), the EU text-and-data-mining exceptions (Directive
2019/790, Articles 3 and 4) cover copying and extraction for mining, but whether extracted results may be
shared is unsettled (Margoni and Kretschmer, GRUR International 2022). Facts are generally not protected by
copyright, but the EU's sui generis database right protects substantial extraction from databases. The
design below makes the legal question a decision per record, and makes the conservative answer cost
nothing.

### 6.1 Source registry

One entry per source: citation key and BibTeX, DOI or URL, the licence of the publication, the licence of
any dataset, a **redistribution status** (permitted; values only; not permitted; unknown) with its reason,
who judged it and when, and the source's role. Values point at registry keys.

### 6.2 Three tiers

| Tier | What is published | Typical sources |
|---|---|---|
| Shipped | values and provenance | open-licence papers and datasets; own measurements; own fits and check points; individual factual values judged safe |
| Reference-only | provenance, locator and an extraction recipe; the values are filled in locally from the user's own copy of the source | sources whose redistribution status is not permitted or unknown |
| Private | nothing; an organisation's own overlay in the same format | proprietary or unpublished measurements |

The tools treat the three tiers identically, so the public library can be conservative without making
Vesalius weaker. Fits the curator makes from published curves are the curator's own work and can often be
shipped where the curves themselves stay reference-only. So can the check points the reference
implementation computes.

### 6.3 Extraction

- Primary literature, never bulk copies of a secondary database.
- The extraction method is recorded per value (section 4.7), because the risk, legal and numerical, differs
  by method.

### 6.4 Licences

Code is Apache-2.0. The library's data would be under a data licence (CC-BY-4.0, CDLA-Permissive-2.0, or
CC0 for the widest reuse; open question 8), and each record states the licence it is distributed under.

### 6.5 Process

- A data attestation in the pull-request template, beside the sign-off.
- A takedown procedure for a rights holder who objects.
- One legal review before the first library release, scoped to three questions: individual values taken
  from papers; curves digitised from figures; fits derived from others' data.
- Own open measurements, published under an open licence, are the cleanest data and a contribution to the
  field in their own right.

## 7. The core package

### 7.1 Layout (proposal)

```
vesalius/
  schema/          record.schema.json; schema.usda, generatedSchema.usda, plugInfo.json      (L0)
  data/            conformance/, vectors/, spectra/                                          (L1)
  core/            record.py, values.py, provenance.py, statistics.py, uncertainty.py,
                   units.py, mixing.py, validate.py, checkpoints.py                          (L2, numpy)
  authoring/       compose.py, derive.py, fit_record.py, bake.py                             (L3)
  io/              plain.py (required); usd/ (needs pxr)                                     (L4)
  sample/          fractions.py, layered_path.py, reference_sampler.py                       (L5)
  integrations/    exporters/, importers/, i4h/                                              (L6, lazy imports)
```

Family packages and the library repository have their own layouts (`DOCUMENTATION_ARCHITECTURE.md`
section 2).

### 7.2 Dependencies and distribution

- Core: numpy and a JSON Schema validator. Extras: `[usd]` for `usd-core`, `[sample]` for whatever L5
  needs.
- `pxr` is imported from whatever USD is installed. Isaac Sim ships its own USD build, and `usd-core` 26.8
  publishes wheels for macOS, Linux x86_64 and Windows only (checked 2026-10-11), while Isaac for
  Healthcare also supports Linux on aarch64. So `usd-core` must never be a hard requirement.
- Release artifacts: the wheel on PyPI, and the schemas (L0), conformance data and golden vectors (L1) as a
  separate archive for projects in other languages to vendor.

### 7.3 Uncertainty and sampling

The reference sampler honours the four structures of section 4.9, rejects inadmissible draws and reports
the rejection count. It is there to define the behaviour and to test consumers against; it is not a UQ
engine.

### 7.4 Conformance

Small cases, each with expected answers: the material bound to a prim or a path interval; a property at a
point; a property at a wavelength or frequency; the owner of a point inside nested regions; the provenance
of an overridden value (including the dictionary-merge trap); equality of the plain and USD forms;
refusal on an unknown family version; refusal on a failed check point; refusal to sample an undeclared
structure. Any implementation, in any language, checks itself against them. That is what makes a second
reader trustworthy without a second implementation of everything.

### 7.5 The read side in another language

What a consumer does, with no Vesalius code:

1. Read a record with a JSON parser; or put the schema directory on USD's plug-in path and resolve a prim's
   material with the `physics` purpose (or the chosen one).
2. Read SI values; interpolate tables; evaluate power laws.
3. For a parameter set: confirm the family identifier and version are known; evaluate your own
   implementation at the record's check points; refuse on a mismatch.
4. Apply each field's declared mixing rule on your own grid; honour the precedence of section 5.1; take
   provenance as in section 5.5.
5. Sample only as the declared uncertainty structure allows.

Everything else (composition, unit conversion, derivation, fitting) was done when the record was written.

### 7.6 Scope rules

- **Admission.** A section, family or library material enters when a named consumer needs it, with its
  evidence (`DOCUMENTATION_ARCHITECTURE.md` section 6.4 for families, `CONTRIBUTING.md` for materials).
- **Non-goals.** No solver, no mesher, no query service, no hosting of large datasets, no judgement of
  applicability, no fast or differentiable model evaluation. Consumers write their own evaluators (MIME's
  would be JAX) and verify them against the golden vectors and check points.

### 7.7 Governance

- Apache-2.0 for code (decided); a data licence for the library (section 6.4).
- Contributions with a sign-off (Developer Certificate of Origin), as Isaac for Healthcare requires of its
  own (`i4h-workflows` `CONTRIBUTING.md`, read 2026-10-10), so code can move between the projects. Decided
  2026-10-11 as a project constraint from the first code commit: `CONTRIBUTING.md` and
  `DOCUMENTATION_ARCHITECTURE.md` section 15.
- One maintainer at the start. The schema is the part that must stay stable; keep it small until a second
  consumer exists.

## 8. Interface with MIME

### 8.1 Where it attaches

MIME depends on the Vesalius core (with the USD extra) and the families it uses. The adapter lives in MIME,
beside the things of structure draft 4.1. Vesalius knows nothing of nodes, graphs or JAX.

```
USD stage (or plain records): geometry + bindings + Vesalius materials     (Vesalius L0, L1, L4)
    -> MIME things: Body, Medium, Apparatus                       plain views of prims and records
    -> each effect or observation model declares required properties (section, field or family, unit, conditions)
    -> Experiment.build(): Vesalius L5 gives volume fractions on each node's discretisation;
       MIME's JAX evaluators of model families, verified against each record's check points;
       mixing rules applied in JAX
    -> gm.params (differentiable) or static data (scope doc class P3)
```

### 8.2 What changes in MIME

| Structure draft | Change |
|---|---|
| 4.1 Things | bodies and media hold Vesalius materials; apparatus may too (a detector, a coil housing) |
| 4.2, 4.3 Models | required properties become typed: section, field or family, unit, conditions; replaces presence-only checks (scope doc H1) |
| 5.1 Build order | a step after the things: resolve materials, verify check points, check required properties and conditions, compute validity |
| 5.5 Saved form (scope doc D2) | the stage holds things and materials; the experiment file holds models, controller and run settings |
| 8 Metadata | biocompatibility and provenance move to the material; open question 8.8 is answered by one record; `MimeAssetSchema` refers to materials by identifier |
| 3.8, 3.10 New nodes | Vesalius is a prerequisite for every new family: acoustics, X-ray, transport, photoacoustics |
| 7.4 N3 | shared parameters become more pressing (8.3) |

### 8.3 Differentiability

The split that keeps gradients:

- **Which material is where** is geometry. Vesalius L5 computes volume fractions per region on a node's
  grid once (static data). For a moving body, MIME recomputes its fractions per frame from a soft distance
  function in JAX, as for the X-ray rung (structure draft 3.9).
- **What the material's values are** become MIME parameters. A node's property field is the mixing rule
  applied to fractions and values, in JAX, through Vesalius's array-API mixing functions. Model-family
  parameters go through MIME's own JAX implementation of the family.

So gradients reach material values (fitting an absorption map, a sound-speed map, a viscosity, a
hyperelastic parameter set) and, for moving bodies, poses. One material value usually feeds several nodes;
until MADDENING can tie a parameter across nodes (structure draft N3), MIME keeps one value per material and
copies it out.

### 8.4 Uncertainty

MIME maps a record's statistics and uncertainty structure into MADDENING's UQ types. Today MADDENING's
`UncertainParameter` describes one parameter at a time (`MADD:src/maddening/core/compliance/uq.py`), so
only scalar statistics and `independent` structures map directly. Joint distributions (a covariance in a
declared space, an ensemble, admissibility constraints) have been requested of MADDENING for a later
release. Until then MIME samples `ensemble` and `multivariate_normal` structures with Vesalius's reference
sampler, or uses nominal values.

### 8.5 Round trip

A MIME fit writes its results back as a stronger layer (or overlay record) of fitted values with provenance
(section 5.5), check points from the family's reference implementation, and a covariance where the fit
produces one. The library's declared values stay underneath, and the fit's layer records what was fitted,
from which data, by which run.

### 8.6 Validity

MIME computes operating points from material values and the run: Reynolds number, acoustic Mach number, the
diffusion approximation's condition for light. That is structure draft 8.5's "one validity declaration,
checked against a computed operating point". A fitted parameter set adds its own envelope (section 4.10):
the loading modes and ranges it was fitted over.

### 8.7 Beside MADDENING and MICROROBOTICA

- MADDENING's USD live stage and graph schema describe the simulation; Vesalius describes the scene's
  materials. They would be separate layers composed into one stage.
- MICROROBOTICA would read materials for display and keep its rule that biocompatibility is never shown as
  a safety claim.

## 9. Adoption

The design should be worth having with no outside adopters: provenance, check points and the material input
sheet (`DOCUMENTATION_ARCHITECTURE.md` section 9) pay for themselves inside the projects that use it first.
Wider adoption is the upside, pursued as follows.

- **Tools before a format.** What people adopt is what saves them work this week:
  - exporters to the formats they already use: finite-element material cards in each solver's own
    convention (through a conversion with its own vectors, section 4.5), k-Wave medium arrays, Monte Carlo
    layer and media tables, Isaac for Healthcare's ultrasound material table;
  - importers from what they already have: spreadsheets, code holding one parameter set per paper,
    existing source lists;
  - a convention checker: given parameters and a claimed convention, report which family version
    reproduces a reference curve.
- **Cheap partial use.** A consumer can read one section, use plain records without USD, and ignore the
  rest.
- **Existing ecosystems.** OpenUSD for scenes and the Python scientific stack, not a new container format.
- **Credit for curation.** The library is a citable dataset with a DOI per release; each curated value
  records its curator's ORCID.
- **Criteria.** For example, by Vesalius 0.3: two consumers outside the founding projects, a stated number
  of curated materials, and one outside contributor. If they are not met, Vesalius narrows to an internal
  tool, which is still worth having.

An earlier materials-data exchange format, MatML, went from NIST to an OASIS technical committee in
2003-2004. How widely it was adopted was not established here.

## 10. Interface with Isaac for Healthcare

None of this exists or has been proposed to them. Each row is a possible adapter, in the order I would try
them.

| Their component | Today | Vesalius touchpoint | Adapter |
|---|---|---|---|
| Ultrasound simulator | six materials hard-coded in C++ | fill its material table from a stage's materials | Python, in their Python layer or in `vesalius.integrations.i4h`; no C++ change |
| Patient twin | CT to labels to meshes and USD, no properties | a step that binds a library material to each label | a mapping file from their label names to library materials, plus a binding function |
| X-ray simulator | linear map from CT number to attenuation | per-material attenuation at an effective energy, from a label volume | builds an attenuation volume; whether their API accepts one directly was not checked |
| Physics (Newton, the XPBD catheter, soft tissue) | engine materials | mechanical families to engine parameters; interfaces (4.13) for catheter-wall friction | per engine; position-based solvers use compliance, which depends on the discretisation, so the adapter converts |
| Workflows and scenes | USD scenes | scenes reference library layers | none: plain USD composition |

### 10.1 The ultrasound adapter in more detail

- Their `Material(impedance, attenuation, speed_of_sound, mu0, mu1, sigma, specularity)` computes density as
  impedance times 1e6 over sound speed (`material.cpp:36-38`), so impedance is in MRayl. The attenuation
  values (water 0.0022, liver 0.7, bone 5.0) look like dB per cm per MHz; inferred from the values, not
  from their documentation.
- From Vesalius's acoustic section: impedance as density times sound speed, sound speed directly,
  attenuation converted from SI to their units.
- Their four speckle parameters are renderer settings. They would sit on the same material prim in their
  own namespace (for example `i4h:ultrasound:mu0`), outside Vesalius's schema.

### 10.2 Why this could interest them

- One patient twin would feed their ultrasound, X-ray and physics simulators, and other people's solvers.
- It is framework-neutral, Apache-2.0, and competes with nothing of theirs.
- The first adapter needs no change to their C++.

I would rank this above the physics bridges of structure draft 7.7 as a first contribution.

### 10.3 Caveats

- NVIDIA may already have something partial. As I recall, SimReady assets carry non-visual materials for
  RTX sensors, and PhysX has deformable-body material schemas. Check both before proposing anything, and
  map onto them where they overlap.
- A standard succeeds by adoption. Round-tripping their patient twin's output matters more than a complete
  schema.

## 11. Phasing (proposal, not committed)

| Vesalius | Contents | Consumers |
|---|---|---|
| 0.1 | core mechanism; plain records and their JSON Schema; USD schemas and I/O; source registry; check points; uncertainty structures and the reference sampler; layered paths and region binding, plain and USD; sections fluid, acoustic, dielectric, radiological, magnetic, biocompatibility, and mechanics with linear elasticity and one hyperelastic family; conformance; a seed library (water, blood, soft tissue, silicone, agar, SU-8, NdFeB) with sources | MIME 0.3.0 for things if timing allows, otherwise the Python core only; an importer from an existing per-paper calibration code base as the design's acceptance test |
| 0.2 | optical and thermal sections; composition and spectra; label volumes; field overrides; more families as consumers need them; the first exporters | photoacoustics in MIME, cheap rungs (Appendix A) |
| 0.3 | sampling helpers (L5), including layered paths derived from 3-D geometry; interfaces; the convention checker | resolved photoacoustic rungs; contact |
| alongside 0.1 or 0.2 | the ultrasound adapter and the label mapping for the patient twin | Isaac for Healthcare, if they want it |

## 12. Open questions

1. Source of truth for library materials: plain records with generated USD (lean), or USD with generated
   plain records.
2. Binding purpose: reuse `physics` (lean) or define one (section 5.4).
3. The USD form of a layered path: a typed prim of our own, or `BasisCurves` with `GeomSubset`s.
4. Family registry scope: which families Vesalius defines and maintains itself, how third-party namespaces
   are listed, who may publish under `vesalius.`, and whether families ship as subpackages or as separate
   distributions.
5. Whether reference implementations sit in the core or with their families. In the core, they are SOUP
   for every user; with their families, the core only runs vectors.
6. Where the mixing rules and family equations are documented normatively: the specification only, or also
   the schema's `doc` strings.
7. The USD encoding of parameter sets, statistics, uncertainty structures and check points.
8. The data licence: CC-BY-4.0, CDLA-Permissive-2.0 or CC0.
9. Which spectra, tissue sources and ontologies to start from, and their terms (IT'IS database: recalled,
   terms not checked).
10. How much sampling (L5) belongs in Vesalius. Inside-tests against meshes are a geometry problem with
    libraries of their own; label volumes, fields and layered paths are easy.
11. Interfaces (4.13): a record or prim type of their own, or a relationship on one of the two materials?
12. Deforming tissue: properties that move with a deforming mesh.
13. Temperature coupling: properties that change with a simulated temperature field.
14. Who maintains Vesalius beyond the first version.

## 13. Not examined

- Nothing was built in a repository. The USD checks of section 5 ran in a scratch directory against
  USD 0.26.5, with one prototype schema. Plain records, family definitions, check points and the sampler
  are unprototyped.
- No legal review has been done. Section 6 rests on a short search and is not legal advice.
- Isaac for Healthcare was read at its main branches on 2026-10-09 to 2026-10-11 by documentation and file
  search; their asset catalogue, SimReady specifications and Newton material model were not read.
- The adoption history of earlier materials-data formats was not researched.
- The papers, databases, ontologies and NVIDIA schemas named here are recalled.
- The photoacoustic figures in Appendix A are my arithmetic on assumed values.

## 14. Revision of 2026-10-11

A design review, using an existing per-paper tissue calibration code base as a case study, changed the
draft as follows.

| Before | After | Why |
|---|---|---|
| USD was the only on-disk form | plain records are complete on their own; USD is the primary binding, generated from them | one-dimensional and non-USD consumers must not need USD; scenes still move to USD |
| three read-side forms | five value forms, adding model parameter sets and reference data | constitutive models are not reducible to tables |
| mechanics as Young's modulus and Poisson's ratio | mechanics by model family | soft tissue is rarely linear elastic |
| a range per value | statistics per scalar; declared uncertainty structures per parameter set | fitted parameters are correlated; independent sampling makes materials that do not exist |
| region binding first | a geometry ladder starting at the layered path | many projects start one-dimensional |
| no dielectric section | dielectric section | sensing, RF heating and tracking all need tissue permittivity and conductivity |
| one package | core, family packages, library repository | mechanism is SOUP and should change rarely; content grows |
| sources as citations | a source registry with redistribution status; three tiers; a separate data licence | legal exposure is per record |
| none | check points per record; fail-closed readers; fit-reproduction check | silent convention mismatches are the main technical risk |
| none | proxies per field; a conditions vocabulary with ontology identifiers | most tissue data comes from stand-ins |
| none | adoption strategy with criteria | a standard succeeds by adoption |

## Appendix A. Photoacoustics in MIME: the first consumer of the optical sections

**Direction (maintainer, 2026-10-11):** good to have in MIME 0.3.0 but not necessary; expected by 0.5.0 to
0.6.0. A medium-term vision.

Why it matters for MIME:

- It images microrobots in tissue. As I recall, PA tomography has guided microrobots in the intestine (Wu et
  al., Science Robotics 2019), and optoacoustics has tracked magnetic microrobots in mouse brain
  vasculature (Wrede et al., Science Advances 2022, Razansky's group). Recalled, not checked.
- It chains three physics (light, heat, sound) through one material, so it tests Vesalius.
- Quantitative PA, recovering an absorption map from images, is a recognised inverse problem. With section
  8.3 it becomes an ordinary fit of material values.

### A.1 What a PA frame is

1. A laser pulse of a few nanoseconds illuminates tissue. Light crosses a centimetre of tissue in about
   50 ps, so the fluence can be computed as steady.
2. Absorbed energy is absorption times fluence. Under stress confinement it becomes an initial pressure:
   the Grüneisen parameter times the absorbed energy.
3. That pressure propagates as a broadband wave, recorded for some tens of microseconds (about 20 us across
   3 cm).
4. An image is reconstructed from the recorded signals.

### A.2 Where it sits in MIME's structure

- **A PA frame is an observation model** (structure draft 4.3). The flow moves at about two millionths of
  the speed of sound, and the pulse's pressure does not move the fluid, so nothing in the frame writes
  back. No coupling group with the FVM is needed.
- **It fires once per laser pulse.** A broadband acoustic simulation needs steps of about 10 ns, against
  0.5 ms for the fluid, a ratio of about 50,000. The resolved rung runs once per frame on the state at that
  instant (structure draft 5.4, candidate N1).
- **The fluid reaches PA through what it carries**: contrast agent, blood oxygenation, the robot's
  position. They change the absorption map, one way, from transport through composition (section 4.3) into
  optics. Doppler is the only direct flow-to-sound effect.
- **The thermoelastic step is a transform with static weights** (structure draft 3.4), not a node.
- **Absorbed power is shared** with bioheat, so photothermal therapy reuses it.
- **Optical diffusion is a steady diffusion-reaction equation**, the same family as scalar transport, so one
  grid solver could serve both. That argues for building transport first.

### A.3 A fidelity ladder (proposal)

| Piece | Cheap, every frame | Resolved | Oracle |
|---|---|---|---|
| Light | Beer-Lambert along the beam plus a diffusion approximation | the same, heterogeneous, on the experiment's grid | Monte Carlo light transport (recalled: MCX) |
| Robot signal | fluence computed once; the robot as a small absorber, a point source of pressure | the robot's absorption added to the map, light recomputed | the resolved rung |
| Sound | analytic spherical waves in a uniform medium | a time-domain pseudo-spectral solver, MIME's own (structure draft 3.5) | k-Wave or j-Wave |
| Sensor | ideal point receivers | element size, bandwidth, noise | a measured impulse response |
| Image | delay-and-sum | model-based inversion | the same inversion on simulated data |

The diffusion approximation fails within about one transport mean free path of the source and of
boundaries, and where absorption is not small against reduced scattering: a computed validity check
(section 8.6).

### A.4 Prerequisites, in order

1. Vesalius 0.2's optical and thermal sections, with composition.
2. Scalar transport in MIME.
3. The time-domain acoustic kernel.
4. Observation models that run per frame.
5. A sensor model and a reconstruction.
