# Vesalius: an architecture concept

**Status: a concept draft for iteration.** Written 2026-10-11 in the shared planning directory (first as
`plans/MIME_MATERIAL_MODEL_DRAFT.md`) and moved here the same day. Referenced from
`plans/MIME_030_STRUCTURE_DRAFT.md` (the **structure draft**) but not part of MIME's design yet: the
maintainer wants to iterate on it first.

**Decided (maintainer, 2026-10-11):**

- Materials for multiphysics simulation become a standalone package, **Vesalius**, not part of MIME. The
  name was free on PyPI when checked on 2026-10-11. FLESH was considered and dropped.
- Licence: **Apache-2.0**.
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
**material** record per substance, with a section per physics (fluid, mechanical, acoustic, optical,
thermal, radiological, magnetic, biocompatibility), every value in SI with its provenance. Materials are
bound to scene geometry in USD. Any simulator, in any language, can read them.

Design goals:

1. **The read side needs no Vesalius code.** A C++ renderer, a JAX solver and a PyTorch policy trainer
   read the same files with nothing but USD.
2. **No solver dependency.** Vesalius knows nothing of MIME, MADDENING, JAX, Warp or Isaac.
3. **Provenance on every value.** Declared, measured, fitted or derived, with a source and a range.
4. **Small.** Only sections that have a consumer.

What Vesalius is not:

- not a solver, a mesher, a segmenter or a renderer;
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
codes as media tables, finite-element codes as material lists. Nothing carries one tissue across them.

## 3. Architecture

### 3.1 Layers

```
 L6  Adapters             MIME adapter (in MIME)          Isaac for Healthcare adapters (vesalius.integrations)
       ^                        ^                                    ^
 L5  Sampling (optional)  evaluate properties on a consumer's grid or points: volume fractions, mixing rules
       ^
 L4  USD I/O (optional)   read, write, bind, resolve a prim's material, label volumes, field overrides
       ^
 L3  Authoring            composition to spectra, derived values, importers from published tables, "bake"
       ^
 L2  Core (numpy)         Material, Section, Value with provenance, units, mixing rules, validation
       ^
 L1  Data                 material library layers, spectra tables, conformance stages     (no code)
 L0  Schema               schema.usda, generatedSchema.usda, plugInfo.json                (no code)
```

Rules:

- A layer imports only layers below it. L0 and L1 need nothing at all.
- Nothing imports a simulator. Adapters for a simulator import it lazily and live where their owners
  choose: MIME's adapter in MIME; Isaac adapters in `vesalius.integrations` until upstream wants them.
- USD is an optional extra (section 6.2).

### 3.2 Two kinds of user

| | Writes materials | Reads materials |
|---|---|---|
| Who | library maintainers; a lab characterising a phantom; a fit writing results back | every simulator |
| Needs | L2, L3, L4 (Python) | L0 and USD, in any language; optionally L2 and L5 in Python |
| Does | composes, converts units, derives, bakes evaluated values with provenance | reads SI numbers, interpolates tables, applies declared mixing rules |

Everything that needs computing happens on the write side. This is what keeps C++ consumers first class
(section 6.4).

## 4. The data model

### 4.1 Material, section, value

- A **material** has an identity (identifier, name, version), the schema version it was written against,
  and any subset of sections.
- A **section** is one physics. A consumer checks only the sections it needs.
- A **value** is a number, a sampled table, or a simple law, in fixed SI units, with provenance and the
  conditions it holds at (temperature; wavelength or frequency where relevant).

### 4.2 Sections

| Section | Example contents (SI) | Typical consumers |
|---|---|---|
| Fluid | density, viscosity, rheology model | fluid solvers |
| Mechanical | Young's modulus, Poisson's ratio, viscoelastic parameters | soft tissue, compliant walls, rods, contact |
| Acoustic | sound speed, density, attenuation as a power law in frequency, nonlinearity B/A | ultrasound, acoustic actuation, photoacoustics |
| Optical | absorption and scattering spectra, scattering anisotropy, refractive index | photoacoustics, fluorescence, photothermal |
| Thermal | conductivity, heat capacity, perfusion, thermal expansion, Grüneisen parameter | bioheat, photoacoustics |
| Radiological | attenuation against photon energy, or elemental composition | X-ray, CT |
| Magnetic | susceptibility, remanence, saturation | robots, implants, coils |
| Biocompatibility | status, standard, notes | asset cards, registries |

### 4.3 Laws, tables and composition

- **Store laws, not values at one operating point.** Optical properties depend on wavelength, acoustic
  attenuation on frequency, most properties on temperature.
- **Read-side forms are limited to three:** a constant; a sampled table with linear interpolation; a power
  law `a * x^b`. Anything richer is evaluated on the write side and baked into one of these.
- **Composition is a write-side input.** Tissue optics is usually derived from volume fractions of water,
  blood (with its oxygenation), lipid and melanin, times tabulated spectra (recalled: Jacques 2013). A
  material may record its composition, but the absorption spectrum a reader sees is the baked table.
  Composition is also what transport changes in a simulation (Appendix A.2), so a consumer that varies it
  uses the L3 functions, not the file.
- **Derived values say so.** The Grüneisen parameter can be measured or derived from thermal expansion,
  sound speed and heat capacity. Either is fine if labelled.

### 4.4 Provenance

Each value carries its kind (declared, measured, fitted, derived), its source, a range or uncertainty where
known, and its conditions. Literature tissue properties often vary by a factor of two or more between
sources (recalled), so a range is the honest default. A value from a table is a declaration until something
fits it (`MIME:CLAUDE.md`).

### 4.5 Mixing rules

A cell that is part tissue and part vessel needs one value per property, and the right average depends on
the property: absorption and density average by volume; compressibility and heat conduction across a layer
do not. Each field declares its rule in the schema (section 5.1), so any consumer can apply it. The rules
themselves live in L2, written against the Python array API standard, so numpy, JAX and PyTorch callers
share one implementation (recalled: jax.numpy follows that standard).

### 4.6 Interfaces between materials

Some properties belong to a pair, not to one material: friction and lubrication between a catheter and a
vessel wall, thermal contact resistance, a slip condition. These would sit on an **interface** record that
names two materials. USD's own physics material puts friction on single materials and leaves the
combination to the engine (recalled), which loses the pair. Open question 6.

### 4.7 Appearance is not physics

Isaac for Healthcare's ultrasound table mixes physical properties (impedance, attenuation, sound speed) with
renderer settings (speckle parameters). Vesalius holds the physical ones. A renderer's settings sit on the
same material prim in the renderer's own namespace (section 8.1).

## 5. The USD representation

Checked on 2026-10-11 with USD 0.26.5 and a one-schema prototype in a scratch directory; nothing in a
repository.

### 5.1 Schemas

- One **single-apply API schema per section**: `VesaliusFluidAPI`, `VesaliusMechanicalAPI`,
  `VesaliusAcousticAPI`, `VesaliusOpticalAPI`, `VesaliusThermalAPI`, `VesaliusRadiologicalAPI`,
  `VesaliusMagneticAPI`, `VesaliusBiocompatibilityAPI`. Attributes are namespaced
  `vesalius:<section>:<field>`.
- A **mixing rule per field** as a token attribute beside it, for example
  `vesalius:acoustic:soundSpeed:mixing = "harmonic"`, with its default in the schema.
- **Resource-only**: `schema.usda` as the source, `generatedSchema.usda` and `plugInfo.json` as the
  registered form, no compiled library. MADDENING already ships its graph schema this way
  (`MADD:src/maddening/usd/__init__.py:29`).

Checked in the prototype:

- the plug-in registers at run time; `ApplyAPI("VesaliusAcousticAPI")` and `HasAPI` work by name;
- schema defaults are visible on a material before anything is authored (sound speed read 1540, the
  schema's default);
- the plug-in entry must carry `schemaIdentifier`. An `alias` equal to the type's name is refused.

Generated C++ classes are not needed; USD can generate them from the same `schema.usda` if a consumer wants
typed access (recalled).

### 5.2 Materials and binding

- A material is a `UsdShade.Material` prim with the section APIs it needs, plus `UsdPhysics.MaterialAPI` for
  density, so physics engines that read only that still see something.
- Geometry binds it with `UsdShade.MaterialBindingAPI` and a purpose. Checked: binding with purpose
  `"physics"` writes `material:binding:physics`, and `ComputeBoundMaterial("physics")` resolves it; a
  purpose of our own resolves only to its own binding or the all-purpose one.

| Binding purpose | For | Against |
|---|---|---|
| Reuse `physics` (lean) | one binding per mesh; engines that read physics materials see the same prim | other tools meet our schemas on that prim |
| A purpose of our own | no interference | a second binding to keep consistent; physics engines miss it |

### 5.3 Where properties vary inside a body

Three representations, in order of precedence where they overlap:

1. **Field overrides**: a `UsdVol` field per property (checked: `UsdVol` has `OpenVDBAsset` and
   `Field3DAsset`), for continuous maps such as CT-derived attenuation or sound speed.
2. **Label volumes**: an integer volume with a table from label to material, which is how a segmented scan
   arrives from a patient twin.
3. **Region binding**: a material bound to a closed mesh.

Two rules a reader needs:

- **Nested regions** (a vessel inside an organ inside the abdomen): an explicit integer priority on the
  binding, defaulting to depth in the hierarchy, decides which material owns a point.
- **Background**: a stage-level default material for points no region claims (water, air, agar).

Geometry units follow the stage's `metersPerUnit`; property values are SI whatever the stage says.

### 5.4 Layers: declared, then fitted

USD composition gives a declared-then-fitted history for free. A library layer holds declared values; a
scene references it; a fit writes a stronger layer with fitted values and its own provenance. The declared
values stay intact underneath. Checked: a fitted 1555 m/s in a stronger layer composed over a declared
1570 m/s, and the root layer still held 1570.

**A trap the prototype found.** USD merges dictionary metadata key by key across layers. When the fitted
layer wrote its provenance without a range, the composed provenance read "fitted" with the declared value's
range. So:

- readers take provenance from the layer that supplies the value, not from the composed dictionary.
  Checked: the first spec in `GetPropertyStack()` with a default value gave the fitted provenance alone;
- writers write every provenance key.

The conformance suite (6.3) should contain this case.

### 5.5 Versioning

- The schema has its own semantic version, independent of the package's. Additive changes are minor;
  removals and renames are major, with a deprecation period.
- Every material records the schema version it was written against.
- The library's materials are versioned individually, with their sources.

## 6. The package

### 6.1 Layout (proposal)

```
vesalius/
  schema/        schema.usda, generatedSchema.usda, plugInfo.json          (L0)
  data/          library/*.usda, spectra/*.csv, conformance/             (L1)
  core/          material.py, values.py, units.py, mixing.py, validate.py  (L2, numpy)
  authoring/     compose.py, derive.py, bake.py, importers/               (L3)
  usd/           io.py, resolve.py, volumes.py                            (L4, needs pxr)
  sample/        fractions.py, evaluate.py                                (L5)
  integrations/  i4h/                                                     (L6, lazy imports)
```

### 6.2 Dependencies and distribution

- Core: numpy only. Extras: `[usd]` for `usd-core`, `[sample]` for whatever L5 needs.
- `pxr` is imported from whatever USD is installed. Isaac Sim ships its own USD build, and `usd-core` 26.8
  publishes wheels for macOS, Linux x86_64 and Windows only (checked 2026-10-11), while Isaac for
  Healthcare also supports Linux on aarch64. So `usd-core` must never be a hard requirement.
- Release artifacts: the wheel on PyPI, and the schema directory (L0) and data (L1) as a separate archive
  for C++ projects to vendor.

### 6.3 Conformance

A set of small stages, each with expected answers to queries: the material bound to a prim, a property at
a point, a property at a wavelength, the owner of a point inside nested regions, the provenance of an
overridden value. Any implementation in any language checks itself against them. That is what makes a
second reader trustworthy without a second implementation of everything.

### 6.4 The C++ read side

What a C++ consumer does, with no Vesalius code:

1. Put the schema directory on USD's plug-in path.
2. Resolve a prim's material with the `physics` purpose (or the chosen one).
3. Read attributes in SI; interpolate tables; evaluate power laws.
4. Apply each field's declared mixing rule on its own grid.
5. Honour the precedence of 5.3, and take provenance as in 5.4.

Everything else (composition, unit conversion, derivation) was done when the file was written.

### 6.5 Governance

- Apache-2.0 (decided).
- Contributions with a sign-off (Developer Certificate of Origin), as Isaac for Healthcare requires of its
  own (`i4h-workflows` `CONTRIBUTING.md`, read 2026-10-10), so code can move between the projects. Decided
  2026-10-11 as a project constraint from the first code commit: `CONTRIBUTING.md` and
  `DOCUMENTATION_ARCHITECTURE.md` section 15.
- One maintainer at the start. The schema is the part that must stay stable; keep it small until a second
  consumer exists.

## 7. Interface with MIME

### 7.1 Where it attaches

MIME depends on Vesalius (core and USD extra). The adapter lives in MIME, beside the things of structure
draft 4.1. Vesalius knows nothing of nodes, graphs or JAX.

```
USD stage: geometry + material bindings + Vesalius materials      (Vesalius L0, L1, L4)
    -> MIME things: Body, Medium, Apparatus                       plain views of prims
    -> each effect or observation model declares required properties (section, field, unit, conditions)
    -> Experiment.build(): Vesalius L5 gives volume fractions on each node's discretisation;
       MIME combines them with material values in JAX, applying the declared mixing rules
    -> gm.params (differentiable) or static data (scope doc class P3)
```

### 7.2 What changes in MIME

| Structure draft | Change |
|---|---|
| 4.1 Things | bodies and media hold Vesalius materials; apparatus may too (a detector, a coil housing) |
| 4.2, 4.3 Models | required properties become typed, with units and conditions; replaces presence-only checks (scope doc H1) |
| 5.1 Build order | a step after the things: resolve materials, check required properties, compute validity |
| 5.5 Saved form (scope doc D2) | the stage holds things and materials; the experiment file holds models, controller and run settings |
| 8 Metadata | biocompatibility and provenance move to the material; open question 8.8 is answered by one record; `MimeAssetSchema` refers to materials by identifier |
| 3.8, 3.10 New nodes | Vesalius is a prerequisite for every new family: acoustics, X-ray, transport, photoacoustics |
| 7.4 N3 | shared parameters become more pressing (7.3) |

### 7.3 Differentiability

The split that keeps gradients:

- **Which material is where** is geometry. Vesalius L5 computes volume fractions per region on a node's
  grid once (static data). For a moving body, MIME recomputes its fractions per frame from a soft distance
  function in JAX, as for the X-ray rung (structure draft 3.9).
- **What the material's values are** become MIME parameters. A node's property field is the mixing rule
  applied to fractions and values, in JAX, through Vesalius's array-API mixing functions.

So gradients reach material values (fitting an absorption map, a sound-speed map, a viscosity) and, for
moving bodies, poses. One material value usually feeds several nodes; until MADDENING can tie a parameter
across nodes (structure draft N3), MIME keeps one value per material and copies it out.

### 7.4 Round trip

A MIME fit writes its results back as a stronger USD layer of fitted values with provenance (5.4). The
library's declared values stay underneath, and the fit's layer records what was fitted, from which data,
by which run.

### 7.5 Validity

MIME computes operating points from material values and the run: Reynolds number, acoustic Mach number,
the diffusion approximation's condition for light. That is structure draft 8.5's "one validity
declaration, checked against a computed operating point".

### 7.6 Beside MADDENING and MICROROBOTICA

- MADDENING's USD live stage and graph schema describe the simulation; Vesalius describes the scene's
  materials. They would be separate layers composed into one stage.
- MICROROBOTICA would read materials for display and keep its rule that biocompatibility is never shown as
  a safety claim.

## 8. Interface with Isaac for Healthcare

None of this exists or has been proposed to them. Each row is a possible adapter, in the order I would try
them.

| Their component | Today | Vesalius touchpoint | Adapter |
|---|---|---|---|
| Ultrasound simulator | six materials hard-coded in C++ | fill its material table from a stage's materials | Python, in their Python layer or in `vesalius.integrations.i4h`; no C++ change |
| Patient twin | CT to labels to meshes and USD, no properties | a step that binds a Vesalius material to each label | a mapping file from their label names to library materials, plus a binding function |
| X-ray simulator | linear map from CT number to attenuation | per-material attenuation at an effective energy, from a label volume | builds an attenuation volume; whether their API accepts one directly was not checked |
| Physics (Newton, the XPBD catheter, soft tissue) | engine materials | mechanical section to engine parameters; interfaces (4.6) for catheter-wall friction | per engine; position-based solvers use compliance, which depends on the discretisation, so the adapter converts |
| Workflows and scenes | USD scenes | scenes reference material library layers | none: plain USD composition |

### 8.1 The ultrasound adapter in more detail

- Their `Material(impedance, attenuation, speed_of_sound, mu0, mu1, sigma, specularity)` computes density as
  impedance times 1e6 over sound speed (`material.cpp:36-38`), so impedance is in MRayl. The attenuation
  values (water 0.0022, liver 0.7, bone 5.0) look like dB per cm per MHz; inferred from the values, not
  from their documentation.
- From Vesalius's acoustic section: impedance as density times sound speed, sound speed directly,
  attenuation converted from SI to their units.
- Their four speckle parameters are renderer settings. They would sit on the same material prim in their
  own namespace (for example `i4h:ultrasound:mu0`), outside Vesalius's schema.

### 8.2 Why this could interest them

- One patient twin would feed their ultrasound, X-ray and physics simulators, and other people's solvers.
- It is framework-neutral, Apache-2.0, and competes with nothing of theirs.
- The first adapter needs no change to their C++.

I would rank this above the physics bridges of structure draft 7.7 as a first contribution.

### 8.3 Caveats

- NVIDIA may already have something partial. As I recall, SimReady assets carry non-visual materials for
  RTX sensors, and PhysX has deformable-body material schemas. Check both before proposing anything, and
  map onto them where they overlap.
- A standard succeeds by adoption. Round-tripping their patient twin's output matters more than a complete
  schema.

## 9. Phasing (proposal, not committed)

| Vesalius | Contents | MIME |
|---|---|---|
| 0.1 | schema and core for fluid, acoustic, radiological, magnetic, biocompatibility; USD I/O; region binding; conformance stages; a small library (water, blood, soft tissue, silicone, agar, SU-8, NdFeB) with sources | 0.3.0 uses it for things if timing allows; otherwise the Python core only |
| 0.2 | optical and thermal sections; composition and spectra; label volumes; field overrides | photoacoustics, cheap rungs (Appendix A) |
| 0.3 | sampling helpers (L5); mechanical section; interfaces | resolved rungs; contact |
| alongside 0.1 or 0.2 | the ultrasound adapter and the label mapping for the patient twin | |

## 10. Open questions

1. Reuse the `physics` binding purpose, or define one (5.2)?
2. Where the mixing rules are documented normatively: the schema's `doc` strings, a separate
   specification, or both?
3. Which spectra and which tissue library to start from, and whether their terms allow redistribution
   (IT'IS database: recalled, terms not checked).
4. How much sampling (L5) belongs in Vesalius. Inside-tests against meshes are a geometry problem with
   libraries of their own; label volumes and fields are easy.
5. Deforming tissue: properties that move with a deforming mesh.
6. Interfaces (4.6): a prim type of their own, or a relationship on one of the two materials?
7. Temperature coupling: properties that change with a simulated temperature field.
8. Who maintains it beyond the first version.

## 11. Not examined

- Nothing was built in a repository. The USD checks of section 5 ran in a scratch directory against
  USD 0.26.5, with one prototype schema.
- Isaac for Healthcare was read at its main branches on 2026-10-09 to 2026-10-11 by documentation and file
  search; their asset catalogue, SimReady specifications and Newton material model were not read.
- The papers, databases and NVIDIA schemas named here are recalled.
- The photoacoustic figures in Appendix A are my arithmetic on assumed values.

## Appendix A. Photoacoustics in MIME: the first consumer of the optical sections

**Direction (maintainer, 2026-10-11):** good to have in MIME 0.3.0 but not necessary; expected by 0.5.0 to
0.6.0. A medium-term vision.

Why it matters for MIME:

- It images microrobots in tissue. As I recall, PA tomography has guided microrobots in the intestine (Wu et
  al., Science Robotics 2019), and optoacoustics has tracked magnetic microrobots in mouse brain
  vasculature (Wrede et al., Science Advances 2022, Razansky's group). Recalled, not checked.
- It chains three physics (light, heat, sound) through one material, so it tests Vesalius.
- Quantitative PA, recovering an absorption map from images, is a recognised inverse problem. With 7.3 it
  becomes an ordinary fit of material values.

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
  position. They change the absorption map, one way, from transport through composition (4.3) into optics.
  Doppler is the only direct flow-to-sound effect.
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
(7.5).

### A.4 Prerequisites, in order

1. Vesalius 0.2's optical and thermal sections, with composition.
2. Scalar transport in MIME.
3. The time-domain acoustic kernel.
4. Observation models that run per frame.
5. A sensor model and a reconstruction.
