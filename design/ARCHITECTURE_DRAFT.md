# Vesalius: an architecture concept

**Status: a concept draft for iteration.** Written 2026-10-11 in the shared planning directory (first as
`plans/MIME_MATERIAL_MODEL_DRAFT.md`), moved here the same day, and revised the same day after a design review
(section 15). Referenced from `plans/MIME_030_STRUCTURE_DRAFT.md` (the **structure draft**) and used there by
direction, not decision: MIME 0.3.0 aims between the realistic and ambitious sets of section 12.

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
   reads the values as intended, and the convention witness that confirms the values match their source
   (section 4.6).
6. **Mechanism in the core, content outside it.** The core defines how families, records and checks are
   declared and verified. Model families and the material library are separately versioned content
   (section 3.1), as MIME's physics is content on MADDENING's mechanism.
7. **Small.** A section, a family or a library material enters only when a consumer needs it (section 7.6).
8. **Models propose; code and people decide.** Language models may help draft records (section 8). They never
   run on the read side or in the checks, and never decide a tier, a unit, a check point or a fit.

What Vesalius is not:

- not a solver, a mesher, a segmenter or a renderer;
- not a database service, and not a host for large datasets;
- not a constitutive-model library for production use: reference implementations exist to define and
  verify, not to run in loops;
- not a judge of whether a value applies to a patient;
- not a store of patient data;
- not a source of safety or biocompatibility claims (MICROROBOTICA's rule carries over: biocompatibility
  fields are information, never a safety claim);
- not a language-model application: it calls no model and holds no keys (section 8);
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
  its own review process; static releases with a DOI, no hosted service (section 6.7)
```

- The core changes rarely. Families and materials grow only when a consumer needs them.
- Anyone can publish families and materials in their own namespace, in their own repository, under the
  same rules and the same checks (sections 4.1, 4.5 and 6.7). Only the curated library carries this
  project's review.
- A manufacturer assesses the core plus only the families and materials it uses, each with its own version
  and content hash (`DOCUMENTATION_ARCHITECTURE.md` section 10).
- Whether families start as subpackages of this repository or as separate distributions, and whether
  reference implementations sit in the core or with their families, are open questions 4 and 5.

### 3.2 Layers inside the core

```
 L6  Adapters and tools   MIME adapter (in MIME); exporters, importers, Isaac adapters (vesalius.integrations);
                          the record checks as a command (`python -m vesalius check`); the MCP server (section 8)
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

- A **material** has an identity (a namespaced identifier, a human-readable name, a version), the
  record-schema version it was written against, a content hash (section 5.6), and any subset of sections.
- **Identifiers are namespaced**: `<namespace>/<local id>`. A namespace belongs to one publisher and is
  shared by its materials and its families (section 4.5). `vesalius` is reserved for this project; in it,
  local identifiers are the catalogue numbers `VES-MAT-XXXX` (for example `vesalius/VES-MAT-0001`). Other
  publishers choose their own. Namespaces from the start let anyone publish records without a central
  authority (section 6.7); adding them later would be a breaking schema change. Their form is open
  question 15.
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

### 4.6 Check points and convention witnesses

When a model parameter set is written, the reference implementation of its family version computes the
response at a handful of states (stated deformations, rates, frequencies, loading modes), and the record
stores those input-output pairs with a tolerance. Before using the parameters, a consumer evaluates its own
implementation at the same states and compares. A mismatch is a refusal.

- A convention mismatch then fails loudly even for a consumer that never ran the conformance suite.
- Check points travel with the record into overlays, USD layers and private copies.
- They are required for model parameter sets and optional for the other forms, where they add little.

**Check points cannot catch an extraction error.** They are baked from the stored parameters, so a parameter
set assigned to the wrong family, or transcribed in another convention, is self-consistent and passes.
Check points verify that a consumer reads the record as intended. They say nothing about whether the record
matches its source.

That is the job of the **convention witness**: a response the source itself reports (a stress at a stated
stretch, a modulus, points on a published curve, a permittivity at a stated frequency), stored with its
locator, which the parameter set must reproduce under its assigned family version within a stated
tolerance.

- Every model parameter set taken from a source needs one, whoever or whatever extracted it. A curator's
  own fit to a digitised curve is witnessed by construction: the curve is the witness, and fit
  reproduction (section 4.10) checks it.
- A parameter set whose source reports neither a curve nor a response value is not admitted to the curated
  library. In a community namespace it carries the flag "convention unverified", and a consumer may refuse
  it.
- Witness data are reference data (section 4.4) and follow the same tiers. Where a witness cannot be
  shipped, the curator's check at review is recorded and the public check reports "not checked", as for
  fit reproduction.
- `vesalius check` runs the witness checks.

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
| evidence | for a value drafted from a document: the verbatim quote, its locator, and the SHA-256 of the document copy it was read from; for a digitised figure, the locator and the document hash. Required when a model assisted. Quotes are not published for reference-only values, because a quote contains the value |
| assistance | when a model helped draft the value: tool, model and provider as reported, prompt version, date (section 8.5). The value's kind does not change |
| search record | for a statistic pooled across sources: the queries, databases, date and inclusion criteria that found the sources |
| witness | for a parameter set: its convention witness (section 4.6) |

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
uncertainty quantification belongs to the consumer (for MIME, to MADDENING: section 9.4).

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
same material in the renderer's own namespace (section 11.1).

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
- **Shipped layers are self-contained.** Every USD layer generated for a release has no composition arcs
  (sublayers, references, payloads) and no asset paths; an aggregate layer, if one is shipped, is
  flattened. A scene that uses the library adds its own arcs. Reading a library layer therefore reads that
  one file and nothing else, whoever published it. `vesalius check` enforces this.

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

## 6. The library: sources, tiers, licences and distribution

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
- One legal review before the first library release, scoped to four questions: individual values taken
  from papers; curves digitised from figures; fits derived from others' data; short verbatim quotes kept as
  evidence in shipped records (section 8.3).
- Own open measurements, published under an open licence, are the cleanest data and a contribution to the
  field in their own right.

### 6.6 Material cards

Each record has a **card**, its landing page, generated from the record and never edited, as the Hugging
Face Hub's model and dataset cards are the landing pages of their repositories. A card has two parts:

- **A metadata header** (YAML): identifier, version, content hash, licence, tier, sections present, family
  versions used, proxy flags per section, check-point and fit-reproduction status, curators' ORCIDs. It is
  what an index, a viewer or a search reads.
- **Prose sections**, adapted from "Datasheets for Datasets" (recalled: Gebru et al.): motivation (why the
  material was curated, and for which consumer); composition (sections, value forms, conditions);
  collection (sources and extraction methods); processing (conversions, derivations, fits); uses and
  limitations (applicability hints, proxies, the conditions outside which nothing was measured);
  distribution (tier and licence); maintenance (who curates it, and how to report a problem).

The prose is stored in the record as fields, so the record stays the single source of truth and the card
only assembles it. Cards replace the data sheets of earlier drafts.

### 6.7 Distribution and hosting

**Proposal: git repositories and static releases, no hosted service.** Three reasons:

- **The library is small.** Records, digitised curves and spectra are kilobytes each. Large data
  (CT-derived volumes, measured property maps) are scene data, outside Vesalius's scope (section 1).
- **Static releases are what can be assessed.** A tagged release with a DOI and content hashes is under
  configuration management and can be assessed as SOUP. A live database that changes under its users
  cannot, and a hosted service would add uptime, access control and a cybersecurity boundary of its own.
- **The closest model needs no hosting to copy.** The Hugging Face Hub is git repositories plus an index,
  metadata cards and viewers, plus hosting for everyone. Vesalius can build the first three statically.

The repository is the database:

```
records in git ── pull request + review ──> vesalius check ──> build ──────────────> release
(source of truth)  (curation)                 (ingestion)       cards, USD layers,    GitHub release, archived on
                                                                index.json, plots     Zenodo with a DOI; a static
                                                                                      site on GitHub Pages
```

- **A release is one archive**: the records, the generated USD layers and cards, a generated `index.json`
  (every record's identifier, version, content hash, sections, tier and licence), and the shipped reference
  data. It is published as a GitHub release and archived on Zenodo with a DOI. A consumer pins a release by
  DOI or hash and needs nothing online afterwards.
- **Federation without hosting.** Any publisher keeps records in their own repository, under their own
  namespace (section 4.1), and runs the same `vesalius check`. Nothing needs this project's permission.
  Once a second publisher exists, an **index repository** would list namespaces, repository URLs and the
  content hashes of releases, with CI that runs the checks on each registration pull request. It hosts no
  data. Julia's package registry works this way (recalled). The index labels the curated namespace apart
  from community ones.
- **Data too big for git** goes on Zenodo. A record points to it by DOI and SHA-256, and a tool fetches it
  only on explicit request, never when a record is read (`DOCUMENTATION_ARCHITECTURE.md` section 15,
  constraint 11), as Homebrew and Spack pin downloads by checksum.

Later, each when its trigger arrives:

| Item | Trigger |
|---|---|
| the index repository | a second publisher |
| a data wheel of the library on PyPI | the first Python consumer outside MIME |
| a viewer on the static site (fits plotted over their reference data); a SQLite build queryable in the browser (recalled: Datasette Lite, sql.js) | a library big enough to browse |
| an issue form that a bot turns into a draft record pull request | contributors who do not use git |
| a mirror of each release on the Hugging Face Hub, for discoverability only | adoption work (section 10) |

Not planned unless the scope changes: a hosted database, a query API, accounts, an upload portal. Their
triggers would be large imaging data, or many writers who cannot work through pull requests; both are
outside Vesalius's scope.

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
  tools/           check.py: python -m vesalius check                                        (L6)
```

The MCP server is a separate distribution, `vesalius-mcp` (section 8), so nothing in the core depends on it.

Family packages and the library repository have their own layouts (`DOCUMENTATION_ARCHITECTURE.md`
section 2).

### 7.2 Dependencies and distribution

- Core: numpy and a JSON Schema validator. Extras: `[usd]` for `usd-core`, `[sample]` for whatever L5
  needs.
- `pxr` is imported from whatever USD is installed. Isaac Sim ships its own USD build, and `usd-core` 26.8
  publishes wheels for macOS, Linux x86_64 and Windows only (checked 2026-10-11), while Isaac for
  Healthcare also supports Linux on aarch64. So `usd-core` must never be a hard requirement.
- Release artifacts: the wheel on PyPI, and the schemas (L0), conformance data and golden vectors (L1) as a
  separate archive for projects in other languages to vendor. Library releases are separate (section 6.7).

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

## 8. Layer 6: MCP tooling and curation

Extracting tissue parameters from unstructured literature is the bottleneck of curation, and language
models are good at the drafting part of it. This section puts them to work without letting them become an
authority. The rule: **a model proposes; deterministic code and a named person decide.** Determinism is
restored at the merge: once a reviewed record is released with its hash, nothing depends on how it was
drafted or on running any model again.

### 8.1 The BYOK boundary

- **Vesalius calls no model and holds no keys.** It exposes deterministic tools over the Model Context
  Protocol (MCP). The researcher's own agent (any MCP client: a coding agent, an IDE assistant, a custom
  command-line tool) brings the model and the key. Bring-your-own-key holds by construction, not by
  configuration.
- **The MCP server** (`vesalius-mcp`, an optional separate distribution in L6) depends on the core and an
  MCP server library only, with no model SDK. It makes no network requests and reads only files the user
  points it at, such as their own copies of papers. Fetching papers is the agent's business, on the user's
  request (`DOCUMENTATION_ARCHITECTURE.md` section 15, constraint 19).
- **MCP sampling** would let the server request completions from the client's model, keeping
  bring-your-own-key while letting Vesalius sequence the steps. Client support was uneven when last
  recalled; the design assumes an agent-driven loop and keeps sampling as an option (open question 16).
- **Nothing a model touches is on the read side.** No model runs in a reader, in `vesalius check`, in a
  release build, or in any consumer's build. MIME's build binds materials by identifier and content hash
  and never calls a model.

### 8.2 The deterministic toolset

MCP's three primitives map onto Vesalius as follows (recalled from the MCP specification; check before
building):

| Primitive | Exposes |
|---|---|
| Resources (read-only) | records, cards, `index.json`, family definitions, the source registry |
| Tools (deterministic) | query the index; get a record (values bundled with conditions, proxy flags, tier and hash); compare sources on curves; gap analysis against a consumer's required properties; create a draft; attach and verify a quote; parse a unit string; run the convention checker; digitise with a stated axis calibration; run a fit; bake check points; run `vesalius check` |
| Prompts | the extraction procedures and review checklists (section 8.3), versioned, so any MCP client gets them; the same text ships as agent skills |

- **Capability scoping.** Draft tools write only to a drafts area of the user's working tree. No tool can
  merge, push or open a pull request on its own, set a tier to shipped, set or change a redistribution
  status, write a check point other than by baking it, or edit a released record. A person opens and
  merges the pull request. An agent that follows instructions injected through a paper can at worst write a
  bad draft, which the rest of the pipeline exists to stop.
- **Private overlays** are excluded from tool output unless the user enables them explicitly, since tool
  output goes to whatever model provider the user's agent uses.

### 8.3 The curation pipeline

```
model proposes ──> grounded in quotes ──> deterministic checks ──> human review ──> pull request ──> release
(a draft record)   (verbatim quote,        (quote exists at the      (checklist;        (sign-off,       (fails closed on
                    locator, document       locator; numbers in the   rendered page      attestation)     any value without
                    hash)                   quote; unit parses;       beside the draft)                   a review record)
                                            plausibility; witness)
```

| Stage | Model's role | What decides |
|---|---|---|
| Finding sources | search and triage candidate papers; draft a search record | the curator; the search record is kept (section 4.7) |
| Source registry | draft the citation and licence facts | a person sets the redistribution status; it stays "unknown" until then |
| Locating values | propose a locator in the user's own copy | the quote check: the quote exists at that page of the document with the recorded hash |
| Extracting values | value, unit as written, conditions, specimen and donor counts, the dispersion statistic and which one it is (standard deviation or standard error), species, site, preservation; each with a verbatim quote | the number-in-quote check; review |
| Primary or cited | classify whether the paper measured the value or cites it | review; cited values are traced to their primary source |
| Units | none: the unit string is recorded as written | the core's unit converter; an unparseable unit goes to a person |
| Model family | propose the family version the paper's equation corresponds to | the convention checker against the convention witness (section 4.6) |
| Figures | propose an axis calibration | a deterministic digitiser, an overlay plot a person inspects, a recorded digitising error |
| Fits | draft bounds and initial guesses | deterministic fit code; the fit record |
| Check points | none | the family's reference implementation |
| Card prose | draft motivation, limitations and maintenance | a person edits; a lint rejects claims such as "validated" or "suitable for patients" |
| Importing a code base that holds one parameter set per source | translate the code into records | a differential test: the original code and the reference implementation agree on the same inputs |

Equations are never extracted: a parameter set's meaning comes from its family definition. Values in
reference-only records are drafted the same way, but their quotes are not published (section 4.7).

### 8.4 The query layer

A model turns a question into a structured query, and a deterministic tool answers it. "Acoustic
attenuation in human or porcine liver at 37 °C, 1 to 5 MHz" becomes ontology identifiers and condition
ranges, matched against `index.json`. Ontology hierarchies supply the "semantic" part without embeddings,
which would add another model-dependent, unreproducible step; a local embedding index built from a release
stays an option.

- Tools return values only bundled with their conditions, proxy flags, tier and content hash, so an answer
  cannot lose them unless the agent discards them.
- An optional checker confirms that every number in an answer appears in a tool result.
- The query layer is advisory. A simulation binds a material by identifier and content hash, never by a
  natural-language query.
- It makes no applicability judgements. The prompts say so, and the claim lint applies to anything it
  saves.

### 8.5 Traceability and the SOUP boundary

- **Provenance records the assistance** (section 4.7): tool, model and provider as reported, prompt
  version, date. The value's kind does not change: a value read from a table is declared whether a person
  or a model drafted it. A manufacturer can ask which inputs were model-assisted and get an exact answer.
- **The evidence does not depend on the model.** The quote, its locator and the SHA-256 of the document
  copy let anyone re-verify a value without any model, after the model is withdrawn. Model outputs are not
  reproducible and need not be.
- **Accountability is human.** The review record names who checked what against a checklist: value, unit,
  conditions, statistic, primary or cited, family and witness.
- **The release fails closed.** `vesalius check --release` refuses any value without a review record.
  Drafts may exist in a working tree; they cannot enter a release.
- **The MCP server is curation tooling, outside the SOUP package**, like the CI scripts. Every value it
  helps draft is independently verified before release, which is the usual argument for light validation
  of a tool used in a quality system (recalled: ISO 13485:2016 clause 4.1.6). Vesalius operates under no
  QMS, but a manufacturer reasoning about it will look for exactly this argument. The SOUP package states
  how many library values were model-assisted and which procedure versions drafted them
  (`DOCUMENTATION_ARCHITECTURE.md` section 10).

### 8.6 Measuring it

The failure modes in section 8.7 come from general experience with language models, not from measurements
on this literature. Three mechanisms measure them:

- **A gold set**: papers with hand-verified extractions, and a deterministic scorer that compares any
  agent's drafts against them, per field. With bring-your-own-key every user's model differs; the gold set
  lets each user measure their own model and agent before trusting it, and the per-field error rates show
  reviewers where to look. Papers are listed by DOI and document hash; PDFs are included only where their
  licence allows.
- **Independent dual extraction for parameter sets**: a second extraction made without seeing the first,
  by a person, or by a second model with a person adjudicating every disagreement, as systematic reviews do
  (recalled). Two models agreeing count as one extraction, not two, because they can share a failure such
  as a broken PDF text layer.
- **Measured review**: occasional seeded errors in review batches measure the reviewers' catch rate. An
  unmeasured review is not a control.

### 8.7 Risks and mitigations

| Risk | Mitigation |
|---|---|
| Fabricated values, quotes or locators | a quote for every number; the quote and number-in-quote checks; review |
| Plausible but wrong: conditions swapped, standard error read as standard deviation, specimen and donor counts confused, table rows misaligned, a cited value presented as measured | quotes for each of these fields; a review checklist that targets them. Plausibility bounds catch orders of magnitude only |
| A wrong model convention (silent, `major`) | the convention witness and the convention checker; no witness means not admitted |
| Garbled equations; misread figures | equations come from family definitions; figures go through a deterministic digitiser with an overlay |
| Automation bias: reviewers accept fluent drafts | the rendered page beside the draft; dual extraction for parameter sets; seeded errors (section 8.6) |
| Prompt injection from papers, including hidden text that a text-layer quote check accepts | capability-scoped tools; the reviewer confirms the quote is visible on the rendered page |
| Selection bias in what a search finds, skewing pooled statistics | a search record for every pooled statistic: queries, databases, date, inclusion criteria, in the spirit of PRISMA |
| Model drift; non-reproducible outputs | nothing depends on re-running; the evidence is the quote, the locator and the document hash |
| Review overload: fast drafting erodes "small" | admission rules unchanged; review capacity is the intended bottleneck |
| Legal: sending copyrighted papers to a model provider; mass extraction | the user's own copies, key and provider terms; primary literature only; tiers never set by a model; quotes in shipped records within the legal review (section 6.5) |
| Leaking private overlays to a provider | excluded from tool output by default |
| Query answers with numbers not from tools, or without their conditions and proxy flags | bundled tool outputs; the number checker; binding only by identifier and hash |

## 9. Interface with MIME

### 9.1 Where it attaches

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

### 9.2 What changes in MIME

| Structure draft | Change |
|---|---|
| 4.1 Things | bodies and media hold Vesalius materials; apparatus may too (a detector, a coil housing) |
| 4.2, 4.3 Models | required properties become typed: section, field or family, unit, conditions; replaces presence-only checks (scope doc H1) |
| 5.1 Build order | a step after the things: resolve materials, verify check points, check required properties and conditions, compute validity |
| 5.5 Saved form (scope doc D2) | the stage holds things and materials; the experiment file holds models, controller and run settings |
| 8 Metadata | biocompatibility and provenance move to the material; open question 8.8 is answered by one record; `MimeAssetSchema` refers to materials by identifier |
| 3.8, 3.10 New nodes | Vesalius is a prerequisite for every new family: acoustics, X-ray, transport, photoacoustics |
| 7.4 N3 | shared parameters become more pressing (9.3) |

### 9.3 Differentiability

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

### 9.4 Uncertainty

MIME maps a record's statistics and uncertainty structure into MADDENING's UQ types. Today MADDENING's
`UncertainParameter` describes one parameter at a time (`MADD:src/maddening/core/compliance/uq.py`), so
only scalar statistics and `independent` structures map directly. Joint distributions (a covariance in a
declared space, an ensemble, admissibility constraints) have been requested of MADDENING for a later
release. Until then MIME samples `ensemble` and `multivariate_normal` structures with Vesalius's reference
sampler, or uses nominal values.

### 9.5 Round trip

A MIME fit writes its results back as a stronger layer (or overlay record) of fitted values with provenance
(section 5.5), check points from the family's reference implementation, and a covariance where the fit
produces one. The library's declared values stay underneath, and the fit's layer records what was fitted,
from which data, by which run.

### 9.6 Validity

MIME computes operating points from material values and the run: Reynolds number, acoustic Mach number, the
diffusion approximation's condition for light. That is structure draft 8.5's "one validity declaration,
checked against a computed operating point". A fitted parameter set adds its own envelope (section 4.10):
the loading modes and ranges it was fitted over.

### 9.7 Beside MADDENING and MICROROBOTICA

- MADDENING's USD live stage and graph schema describe the simulation; Vesalius describes the scene's
  materials. They would be separate layers composed into one stage.
- MICROROBOTICA would read materials for display and keep its rule that biocompatibility is never shown as
  a safety claim.

## 10. Adoption

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
- **Somewhere to look.** The static site (section 6.7) shows each material's card, and later its fits
  plotted over their reference data. Comparing sources on curves is what a curator, and a sceptical reader,
  wants to see.
- **Publishing without permission.** A lab publishes its phantom recipes or its own measurements under its
  own namespace and runs the same checks (section 6.7). The curated library stays small; the long tail
  lives outside it.
- **Existing ecosystems.** OpenUSD for scenes and the Python scientific stack, not a new container format.
- **Credit for curation.** The library is a citable dataset with a DOI per release; each curated value
  records its curator's ORCID.
- **Criteria.** For example, within a year of the library's first release: two consumers outside the founding projects, a stated number
  of curated materials, and one outside contributor or publisher. Measured from Zenodo, PyPI and GitHub
  release downloads and, once it exists, the index. If they are not met, Vesalius narrows to an internal
  tool, which is still worth having.

An earlier materials-data exchange format, MatML, went from NIST to an OASIS technical committee in
2003-2004. How widely it was adopted was not established here.

## 11. Interface with Isaac for Healthcare

None of this exists or has been proposed to them. Each row is a possible adapter, in the order I would try
them.

| Their component | Today | Vesalius touchpoint | Adapter |
|---|---|---|---|
| Ultrasound simulator | six materials hard-coded in C++ | fill its material table from a stage's materials | Python, in their Python layer or in `vesalius.integrations.i4h`; no C++ change |
| Patient twin | CT to labels to meshes and USD, no properties | a step that binds a library material to each label | a mapping file from their label names to library materials, plus a binding function |
| X-ray simulator | linear map from CT number to attenuation | per-material attenuation at an effective energy, from a label volume | builds an attenuation volume; whether their API accepts one directly was not checked |
| Physics (Newton, the XPBD catheter, soft tissue) | engine materials | mechanical families to engine parameters; interfaces (4.13) for catheter-wall friction | per engine; position-based solvers use compliance, which depends on the discretisation, so the adapter converts |
| Workflows and scenes | USD scenes | scenes reference library layers | none: plain USD composition |

### 11.1 The ultrasound adapter in more detail

- Their `Material(impedance, attenuation, speed_of_sound, mu0, mu1, sigma, specularity)` computes density as
  impedance times 1e6 over sound speed (`material.cpp:36-38`), so impedance is in MRayl. The attenuation
  values (water 0.0022, liver 0.7, bone 5.0) look like dB per cm per MHz; inferred from the values, not
  from their documentation.
- From Vesalius's acoustic section: impedance as density times sound speed, sound speed directly,
  attenuation converted from SI to their units.
- Their four speckle parameters are renderer settings. They would sit on the same material prim in their
  own namespace (for example `i4h:ultrasound:mu0`), outside Vesalius's schema.

### 11.2 Why this could interest them

- One patient twin would feed their ultrasound, X-ray and physics simulators, and other people's solvers.
- It is framework-neutral, Apache-2.0, and competes with nothing of theirs.
- The first adapter needs no change to their C++.

I would rank this above the physics bridges of structure draft 7.7 as a first contribution.

### 11.3 Caveats

- NVIDIA may already have something partial. As I recall, SimReady assets carry non-visual materials for
  RTX sensors, and PhysX has deformable-body material schemas. Check both before proposing anything, and
  map onto them where they overlap.
- A standard succeeds by adoption. Round-tripping their patient twin's output matters more than a complete
  schema.

## 12. Phasing for MIME 0.3.0 (proposal)

MIME is the first consumer, so its 0.3.0 release sets the order. **Direction (maintainer, 2026-10-11):** aim
between the realistic and ambitious sets below. Anything that touches MIME is first proven by a spike
(section 12.3), while MIME waits for MADDENING 0.4.0's release, so that MIME 0.3.0 work starts from results
rather than proposals. The cut in section 12.2 is my proposal.

Each feature names what it serves, as document, section number and *heading*:

- **AD**: this architecture draft;
- **DA**: `DOCUMENTATION_ARCHITECTURE.md`;
- **SD**: the structure draft, `plans/MIME_030_STRUCTURE_DRAFT.md`;
- **RS**: the scope doc, `plans/MIME_040_REFACTOR_SCOPE.md`.

### 12.1 Three sets

Each set includes the one before it. A MIME row is done first as the spike named in brackets.

**Minimal: MIME's things hold materials, and no result changes.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| M1 | Plain records and their JSON Schema; namespaced identifiers; a schema version; content hashes | Vesalius | AD 4.1 *Material, section, value*; AD 5.2 *Plain records*; AD 5.6 *Versions and hashes* |
| M2 | Sections for what MIME's experiments use today: fluid (density, viscosity), magnetic (remanence, saturation, susceptibility), biocompatibility | Vesalius | AD 4.2 *Sections*; SD 8.4 *Where each piece would go* (the `BiocompatibilityMeta` row) |
| M3 | Three value forms: constant, table, power law. No model families yet | Vesalius | AD 4.4 *Five value forms* |
| M4 | Provenance per value (kind, source, extraction, review); conditions, starting with temperature; scalar statistics; proxies | Vesalius | AD 4.7 *Provenance*; AD 4.8 *Conditions*; AD 4.9 *Statistics and uncertainty structures*; AD 4.11 *Proxies*; SD 8.3 *Principle: metadata sits on what it describes* |
| M5 | A deterministic reader for plain records: a value in SI, with its provenance, at stated conditions. A refusal comes back as a structured result, never as a guess | Vesalius | AD 3.2 *Layers inside the core* (L2, L4); DA 15 *Project Constraints* (no. 13, fail closed) |
| M6 | Required properties as a type (section, field, unit, conditions), and a check of a material against them | Vesalius | AD 9.1 *Where it attaches*; SD 5.1 *Build order* (step 1); RS H1 *What the layer does today* (presence-only checks) |
| M7 | Conformance cases as data files | Vesalius | AD 7.4 *Conformance*; DA 6.1 *Conformance suite (the read side)* |
| M8 | `vesalius check`: schema, provenance, plausibility | Vesalius | DA 6.5 *CI checks* |
| M9 | A seed library holding the values MIME's experiments use today, transcribed as declared values with their sources (water as a table over temperature, SU-8, NdFeB grades, the tube materials); its source registry; the data licence decided | library | AD 6.1 *Source registry*; AD 6.2 *Three tiers*; AD 6.4 *Licences*; AD 13 *Open questions* (no. 8) |
| M10 | Tagged releases of the package and the library, which MIME pins exactly | Vesalius | AD 6.7 *Distribution and hosting*; DA 7.1 *Four version lines* |
| M11 | The seam: `Body` and `Medium` hold a material reference (identifier and hash) or an inline value labelled "declared in the experiment"; an adapter resolves either into what the nodes take today | MIME (S1) | SD 4.1 *Things*; AD 9.2 *What changes in MIME* |
| M12 | Migration control: experiments built from records reproduce today's outputs exactly; corrections follow as separate changes | MIME (S1) | SD 8.2 *What is wrong with it* (point 4); RS *TODO: what it takes* (item 56, "results reproduce") |

**Realistic: MIME 0.3.0's new nodes and its saved form use it.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| R1 | USD schemas, read and write, for the sections in use; region binding; self-contained shipped layers | Vesalius | AD 5.1 *The geometry ladder*; AD 5.3 *USD schemas*; AD 5.4 *Materials and binding in USD*; DA 15 *Project Constraints* (no. 18) |
| R2 | Acoustic section (density, sound speed, attenuation as a power law in frequency, B/A), for both body and medium | Vesalius | SD 3.5 *Acoustics with MIME's own kernels (decided)*; SD 3.8 *Nodes planned for 0.3.0* (row 6) |
| R3 | Radiological section: mass attenuation against photon energy, elemental composition, an effective value over a tube spectrum; seed materials water, soft tissue, bone, NdFeB and iodine, from a public-domain table (recalled: NIST's; terms to check) | Vesalius, library | SD 3.8 *Nodes planned for 0.3.0* (rows 7, 8); SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks* |
| R4 | Mixing rules in the array API | Vesalius | AD 4.12 *Mixing rules*; AD 9.3 *Differentiability* |
| R5 | The first model family, `vesalius.magnetic.langevin.v1`, with golden vectors, a reference implementation, check points and a convention witness. Its named consumer is MIME's superparamagnetic response node | Vesalius | AD 4.5 *Model families*; AD 4.6 *Check points and convention witnesses*; AD 7.6 *Scope rules*; SD 3.8 *Nodes planned for 0.3.0* (the eMNS pair) |
| R6 | Uncertainty structures and the reference sampler; scalar statistics mapped onto MADDENING's `UncertainParameter` | Vesalius, MIME (S5) | AD 4.9 *Statistics and uncertainty structures*; AD 7.3 *Uncertainty and sampling*; AD 9.4 *Uncertainty* |
| R7 | `vesalius.compliance`: `collect_material_inputs` and the material input sheet, written into each MIME run's provenance | Vesalius, MIME (S5) | DA 9.1 *Where it fits*; DA 9.3 *What this would add to Vesalius* |
| R8 | Material cards; the legal review; the library's first archived release, with a DOI | library | AD 6.5 *Process*; AD 6.6 *Material cards*; AD 6.7 *Distribution and hosting* |
| R9 | A decided record shape for properties of a pair: a species' diffusivity in a medium, and interfaces. Design only | Vesalius | AD 4.13 *Interfaces between materials*; AD 13 *Open questions* (no. 11); SD 3.8 *Nodes planned for 0.3.0* (row 9); SD 9 *Open decisions* (no. 10) |
| R10 | Typed required properties on MIME's effect and observation models, checked at build against conditions and a computed operating point | MIME (S2) | SD 8.5 *One validity declaration, checked against a computed operating point*; AD 9.6 *Validity*; RS H1 *What the layer does today* |
| R11 | MIME's JAX evaluators of value forms, mixing rules and the Langevin family, tested against Vesalius's conformance cases and golden vectors in MIME's default test lane | MIME (S3) | AD 9.3 *Differentiability*; AD 7.6 *Scope rules* (consumers write their own evaluators); DA 6.1 *Conformance suite (the read side)* |
| R12 | Inputs derived, not typed: a magnet's dipole moment from remanence and volume; a density difference from two materials; a composite body's density from fractions; biocompatibility from the body's materials | MIME (S6) | SD 8.2 *What is wrong with it* (point 1); SD 8.4 *Where each piece would go*; DA 9.1 *Where it fits* (biocompatibility row) |
| R13 | The saved form on a USD stage: MIME's things and Vesalius's layers composed with MADDENING's graph | MIME (S4) | RS *TODO: what it takes* (decision D2); RS H5 *The `Experiment`: what stays, what moves, where the other sides attach (a proposal)*; SD 5.5 *The saved form*; AD 9.7 *Beside MADDENING and MICROROBOTICA* |

**Ambitious: images from materials, fits written back, and the pair properties.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| A1 | Label volumes and field overrides | Vesalius | AD 5.1 *The geometry ladder*; SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks* (the voxel-grid source of attenuation) |
| A2 | Sampling helpers (L5): volume fractions on a node's grid. MIME's soft-distance fractions for moving bodies are checked against them | Vesalius, MIME (S7) | AD 3.2 *Layers inside the core* (L5); AD 9.3 *Differentiability*; AD 13 *Open questions* (no. 10) |
| A3 | Joint uncertainty structures used in MIME's UQ through the reference sampler, before MADDENING supports them | MIME (S5) | AD 9.4 *Uncertainty*; AD 4.9 *Statistics and uncertainty structures* |
| A4 | Fit write-back: a MIME fit stored as an overlay with check points and a covariance; the declared values stay underneath | Vesalius, MIME (S8) | AD 4.10 *Fits and reference data*; AD 5.5 *Declared, then fitted*; AD 9.5 *Round trip* |
| A5 | X-ray from materials: the analytic and ray-marched rungs take attenuation from records, with gradients to pose and to attenuation values | MIME (S7) | SD 3.8 *Nodes planned for 0.3.0* (rows 7, 8); SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks* |
| A6 | Interface records for friction | Vesalius | AD 4.13 *Interfaces between materials*; SD 3.8 *Nodes planned for 0.3.0* (existing nodes: surface contact, the contact-friction stub) |
| A7 | Transport records: a species' diffusivity in a medium; contrast agents | Vesalius | SD 3.8 *Nodes planned for 0.3.0* (row 9); AD A.4 *Prerequisites, in order* (item 2) |
| A8 | Optical and thermal sections with composition, for photoacoustics' cheap rungs | Vesalius | AD A.3 *A fidelity ladder (proposal)*; AD A.4 *Prerequisites, in order* (item 1) |
| A9 | The MCP server, the extraction prompts and the gold set | `vesalius-mcp` | AD 8 *Layer 6: MCP tooling and curation* |

Not in any set, for want of a MIME consumer (section 7.6): the dielectric section, mechanics
families, and a non-Newtonian blood family. The mechanics families have a consumer of their own (section
12.2).

### 12.2 The target and the release order

**Proposed cut:** all of minimal and realistic, and A1 to A5 from ambitious. Each of A1 to A5 serves a node
MIME 0.3.0 plans (the X-ray rungs) or MIME's rule that a declared value stays a declaration until something
fits it (section 5.5). A6 to A9 are stretch: none of them blocks a 0.3.0 node.

**Floor:** the minimal set. Because the seam (M11) also accepts inline values, MIME 0.3.0 never waits for
Vesalius; an experiment whose materials are not ready keeps declaring its values inline.

| Vesalius | Set | Contents | Proven in MIME by | Consumers |
|---|---|---|---|---|
| 0.1 | minimal | M1 to M10 | S1 | the MIME spikes |
| 0.2 | realistic | R1 to R9 | S2 to S6 | MIME 0.3.0: the release it is expected to pin |
| 0.3 | target | A1, A2 and A4 (the Vesalius side) | S7, S8 | MIME 0.3.0 if ready when its work starts; otherwise a later MIME minor release |
| 0.4 | stretch | A6 to A9; the first exporters; the convention checker | none needed | photoacoustics in MIME (Appendix A); curators; contact |
| beside 0.2 or 0.3 | independent of MIME | mechanics with linear elasticity and one hyperelastic family; layered paths; an importer from an existing per-paper calibration code base, as the design's acceptance test | none needed | that code base |
| with a consumer | | the dielectric section; further families | | |
| beside 0.2 or 0.3 | | the ultrasound adapter and the label mapping for the patient twin | | Isaac for Healthcare, if they want it |

A spike runs against the release that carries its features, before the next set starts, and a failed spike
changes the next release's contents. Nothing here is sized. Hosting items (the index repository, a data
wheel, a viewer) follow their triggers in section 6.7, not this table.

### 12.3 MIME spikes

The spikes live in `plans/spikes/`, as the Warp spike before them did. They import MIME without changing it
and run on MADDENING `release/0.4.0`. Each records its result in a README; the experiments each uses are
named in SD 4.1 *Things*. Each has a control: a run that must come out differently if the spike's claim is
false.

| Spike | Does | Passes when | Control | Features |
|---|---|---|---|---|
| S1 Seam and migration | resolves materials into today's node parameters for two experiments that run on MADDENING 0.4.0 | outputs are bitwise equal to today's, at the same precision settings | change one record value (water density 997 to 993.3 kg/m³) and see the predicted change. An unchanged output would mean the record never reached a node | M11, M12 |
| S2 Requirements and validity | typed requirements for the drag, magnetic and gravity effects, and for the planned radiation-force node (acoustic sections of body and medium) | the build refuses a missing field, a wrong unit and a temperature outside a table's range, each with a structured reason; a valid experiment builds the same graph as S1 | a material with every field present but at the wrong temperature: a presence-only check passes it, the typed check must not | M6, R10 |
| S3 Differentiable evaluation | runs MIME's JAX evaluators against the conformance cases and the Langevin golden vectors and check points, in float32 and float64; takes a drag gradient with respect to a viscosity record | agreement within the tolerances the cases state; the gradient matches finite differences | a deliberately wrong convention (a chord slope read as the initial tangent, section 4.6) must fail the check points and refuse to build | R4, R5, R11 |
| S4 Saved form on USD | writes a stage with things, Vesalius layers and MADDENING's graph; reloads and builds | `gm.to_dict()` and every material hash are equal after the round trip | a library layer with a composition arc is refused | R1, R13 |
| S5 Provenance and UQ | writes the material input sheet into `SimulationProvenance.custom`; builds `UncertainParameter`s from statistics; samples a joint structure with the reference sampler | every value a node received appears in the sheet with its hash | compare the sheet with the built graph's parameters: a sheet that disagrees with what ran is the failure SD 8.4 removes | R6, R7, A3 |
| S6 Derived inputs | derives a dipole moment, a density difference, a composite density and biocompatibility; feeds the asset gate | each derived value reproduces today's typed value, or the difference is explained | each typed value is compared with its derivation before it is replaced; SD 4.1 names one that may not match | R12 |
| S7 X-ray from materials | the analytic and ray-marched rungs with attenuation from records, a label volume and soft-distance fractions | the ray-marched image of a sphere matches the analytic chord to a stated tolerance; gradients to pose and to an attenuation value match finite differences | the analytic radiograph is the oracle (SD 3.9) | A1, A2, A5 |
| S8 Fit write-back | fits a viscosity, or a Langevin field scale, to a synthetic trajectory; writes an overlay; reloads | the known value is recovered within the fit's stated uncertainty; the overlay's check points pass; the declared value is still underneath | the synthetic truth is known | A4 |

### 12.4 What MIME needs to rely on it

| Requirement | Ties to |
|---|---|
| Exact pins: package, schema, library release and record hashes. No version ranges until the schema is stable | AD 5.6 *Versions and hashes*; DA 7.1 *Four version lines* |
| A reader whose behaviour is defined by conformance data, not only by its code | AD 7.4 *Conformance*; DA 6.1 *Conformance suite (the read side)* |
| Fail closed, with structured results that MIME can report | DA 15 *Project Constraints* (no. 13) |
| No network access and no code execution at build or import; the library comes from the pinned release | DA 15 *Project Constraints* (nos. 11, 19); AD 6.7 *Distribution and hosting* |
| No language model anywhere on MIME's build path | DA 15 *Project Constraints* (no. 20); AD 8.1 *The BYOK boundary* |
| SI in the records. MIME converts to each node's units in its adapter, with tests: some of its nodes run in dimensionless units | DA 15 *Project Constraints* (no. 5) |
| The migration first reproduces today's results exactly (S1); each correction then follows with its measured effect | SD 8.2 *What is wrong with it* (point 4) |
| The comparisons of R11 run in MIME's default test lane. Tests marked `slow` or `gpu` do not run in its CI | DA 6.1 *Conformance suite (the read side)*; AD 7.6 *Scope rules* |

From MADDENING, nothing blocks. Shared parameters across nodes (SD 7.4 *New candidates from this draft*, N3)
would replace MIME's copying of one material value into several nodes (section 9.3). Joint uncertainty has
been requested for a later release (section 9.4). The anomaly validator's version field affects only
Vesalius's own CI (DA 8.1 *Adopted unchanged*).

## 13. Open questions

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
15. The form of namespaces: short names, unique by first-come registration in the index (lean), or
    reverse-DNS names that need no registry.
16. The MCP server's packaging (a separate distribution, lean, or an extra of the core), and whether to use
    MCP sampling once clients support it.
17. Whether quotes should be required for every value extracted from text or tables, not only for
    model-assisted ones. It would help every review, at a cost to manual curation.

## 14. Not examined

- Nothing was built in a repository. The USD checks of section 5 ran in a scratch directory against
  USD 0.26.5, with one prototype schema. Plain records, family definitions, check points and the sampler
  are unprototyped.
- No legal review has been done. Section 6 rests on a short search and is not legal advice.
- Isaac for Healthcare was read at its main branches on 2026-10-09 to 2026-10-11 by documentation and file
  search; their asset catalogue, SimReady specifications and Newton material model were not read.
- The adoption history of earlier materials-data formats was not researched.
- The hosting and registry examples of section 6.7 (Zenodo, PyPI, Julia's registry, Datasette Lite, the
  Hugging Face Hub) are recalled; none was checked for limits or terms.
- No MCP server was prototyped. MCP's primitives and client support are recalled. The failure modes of
  section 8.7 come from general experience, not from measurements on tissue literature; the gold set
  exists to measure them.
- The papers, databases, ontologies and NVIDIA schemas named here are recalled.
- The photoacoustic figures in Appendix A are my arithmetic on assumed values.
- MIME's material needs in section 12.1 were found by searching its node and experiment files. None of the
  spikes of section 12.3 has run, and the experiments chosen for S1 were not run on MADDENING 0.4.0.

## 15. Revision of 2026-10-11

A design review, using an existing per-paper tissue calibration code base as a case study, changed the
draft as follows. A follow-up the same day on distribution, drawing on the Hugging Face Hub, added four rows
(namespaced identifiers to self-contained layers); a third revision added model-assisted curation (the
witness and MCP rows); a fourth set the phasing by MIME 0.3.0's needs (the last row).

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
| catalogue numbers `VES-MAT-XXXX` | namespaced identifiers `<namespace>/<local id>` | anyone can publish without a central authority; retrofitting would break the schema |
| data sheets | material cards: a metadata header and prose sections | a landing page that tools and people both read |
| hosting unstated | git repositories, static archived releases, federation through an index; no hosted service | small data; static releases can be assessed; no service to run |
| USD composition trusted | shipped layers self-contained, checked | reading a library layer reads one file, whoever published it |
| check points only | check points plus a convention witness per parameter set | check points are baked from the stored parameters, so they cannot catch an extraction error |
| none | model-assisted curation and query through MCP: bring-your-own-key, deterministic tools, quotes, human review, fail-closed release | extraction is the bottleneck; a model must never become an authority |
| phasing by section; MIME "if timing allows"; a mechanics family first | three sets for MIME 0.3.0, each feature tied to what it serves; MIME-facing features proven by spikes first; the Langevin magnetisation family first, mechanics on a track of its own | the first consumer sets the order; a spike is cheaper than a design reversed after release |

## Appendix A. Photoacoustics in MIME: the first consumer of the optical sections

**Direction (maintainer, 2026-10-11):** good to have in MIME 0.3.0 but not necessary; expected by 0.5.0 to
0.6.0. A medium-term vision.

Why it matters for MIME:

- It images microrobots in tissue. As I recall, PA tomography has guided microrobots in the intestine (Wu et
  al., Science Robotics 2019), and optoacoustics has tracked magnetic microrobots in mouse brain
  vasculature (Wrede et al., Science Advances 2022, Razansky's group). Recalled, not checked.
- It chains three physics (light, heat, sound) through one material, so it tests Vesalius.
- Quantitative PA, recovering an absorption map from images, is a recognised inverse problem. With section
  9.3 it becomes an ordinary fit of material values.

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
(section 9.6).

### A.4 Prerequisites, in order

1. Vesalius's optical and thermal sections, with composition (section 12.1, A8).
2. Scalar transport in MIME.
3. The time-domain acoustic kernel.
4. Observation models that run per frame.
5. A sensor model and a reconstruction.
