# OpenMaterica: an architecture concept

**Status: a concept draft for iteration.** Written 2026-10-11 in the maintainer's private planning notes,
moved here the same day, and revised the same day after a design
review, on 2026-10-12 after a review against principles 9 and 10, again on 2026-10-12 after five prototypes
and the maintainer's decisions on their findings, on 2026-10-12 and 2026-10-13 after an ecosystem survey, the
maintainer's decisions on it and their reviews, on 2026-10-13 after the decisions taken before the first
code, on 2026-10-14 for the project's name, on 2026-10-16 for the sibling distributions and the MCP server,
and on 2026-10-17 for the maintainer's rulings on that change's open points (section 15). Referenced from
MIME's private 0.3.0 structure draft (the **structure draft**) and used there by direction, not decision: MIME
0.3.0 aims between the realistic and ambitious sets of section 12.

**Decided (maintainer, 2026-10-11):**

- Materials for multiphysics simulation become a standalone package, **OpenMaterica**, not part of MIME. The
  name was settled on 2026-10-14 (section 15), and `openmaterica` was free on PyPI when checked that day.
  FLESH was considered and dropped.
- Code licence: **Apache-2.0**.
- **OpenUSD is the primary binding**, and the expected long-term one for scenes. OpenMaterica must still never
  require it: plain records are a complete form of their own (section 5).
- Commits carry a sign-off from the first code commit (`CONTRIBUTING.md`).
- Photoacoustic imaging in MIME: good to have in 0.3.0 but not necessary; expected by MIME 0.5.0 to 0.6.0
  (Appendix A).

**Decided (maintainer, 2026-10-12, after the prototypes):**

- **Scope: substances, not systems** (section 1). OpenMaterica describes substances in and around the human
  body; it never describes systems.
- **Records have a type.** OpenMaterica defines material, interface and overlay records. Other namespaces may
  define their own types on the same machinery; the first is specified only after MIME prototypes one
  (section 4.1).
- Plain records are the source of truth, and USD is generated from them, one JSON string per field
  (sections 3.4, 5.3).
- The library's data licence is **CC0-1.0** (section 6.4).
- The core never runs inside a consumer's computation (its simulation step, compiled program and gradient
  path): consumers write their own evaluators and mixing rules there, and verify them against conformance
  data. The core does run at a consumer's build (sections 4.12, 7.2, 7.6).
- A consumer may declare an extrapolation, with its basis; the build records it (principle 10, section 3.5).
- Layered paths are specified now, for MIME 0.3.0's acoustics and X-ray; the anisotropic stiffness tensor is
  stretch (section 12).
- The prototypes' findings the maintainer approved are written into the sections that carry them (section 15),
  and the answers to the open questions of the earlier drafts are in section 13.

**Decided (maintainer, 2026-10-12, after the ecosystem survey and its review):**

- OpenMaterica 0.1 carries the plain scene documents, layered paths, label crosswalks and the USD binding (R1,
  R14), with no cut line: none of them slips to 0.2 (section 12.2).
- A region binds its material with a purpose of OpenMaterica's own, `materica`; the `physics` purpose is left
  to engines (section 5.4).
- The engine adapter, its engine crosswalks (then called engine profiles) and the stage check are specified
  and built in 0.1 (section 5.4).

**Decided (maintainer, 2026-10-13):**

- OpenMaterica specifies the engine crosswalk and ships one crosswalk, for OpenUSD's `UsdPhysics`; a crosswalk
  for any other engine is written and pinned by the consumer that runs it, drafted by a scaffold from the
  engine's registered schema (section 5.4). Applied as: the engine's schema file, read without registering it
  and pinned by hash in the crosswalk (review of 2026-10-13).
- The review's four changes beyond that decision are approved: no engine fallback member; dimensions over the
  seven SI base units; no dimension for a token, string, boolean or asset; and one engine model per region
  (section 5.4).
- Names, to avoid clashes: conformance suites (not profiles), engine crosswalks (not engine profiles or maps)
  and label crosswalks (not label mappings); "field" stays (section 13, item 8).

**Decided (maintainer, 2026-10-13), before the first code:**

- The core distribution, `openmaterica`, has no run-time dependency beyond Python's standard library;
  `jsonschema` comes with the `[check]` extra, `usd-core` with `[usd]` and numpy with `[sample]` (section
  7.2).
- Engine results are computed in `openmaterica[usd]`; only the engine adapter and the crosswalk scaffold are
  in `openmaterica-authoring` (section 7.2).
- 0.1 builds the plain scene documents before declarations and build checks (section 12.2).
- The package is typed (`py.typed`), and the JSON shapes of its public API are generated from the writer JSON
  Schemas, which are the single hand-edited source of structure; the specification's tables stay the source of
  tokens (section 7.1).
- Python 3.11 is the floor, under a standing rule: every Python that is not at end of life and that a named
  consumer or engine needs in-process (section 7.2).
- Record checks that need the source registry, a source copy, the previous release or the repository's history
  run in the library's tooling, not in `materica check` (`DOCUMENTATION_ARCHITECTURE.md` section 6.5).

**Decided (maintainer, 2026-10-16):**

- One repository holds every Python distribution: the core, `openmaterica-authoring` and
  `openmaterica-families`, each with its own `pyproject.toml`, version line and changelog, as a uv workspace
  with tag-prefixed releases. The curated library keeps a repository of its own (section 7.2). The layout is
  `DOCUMENTATION_ARCHITECTURE.md` section 2's.
- There is no separate MCP distribution. The core's `[mcp]` extra brings the one MCP server, which discovers
  the tools of whichever siblings are installed. A sibling's tools are plain functions registered by entry
  point, and no sibling imports an MCP library. The server skips a missing or mismatched sibling with a logged
  reason (sections 7.1, 8.1 and 8.2).
- A sibling's MAJOR.MINOR is the core's MAJOR.MINOR it is built for, and its patch number is its own. A core
  minor is a release train, and nothing updates itself (section 7.2).

**Decided (maintainer, 2026-10-17), on the open points of those decisions:**

- The MCP server is part of the core's assessed wheel. The SOUP package lists it as present, imported by no
  reader, check or consumer's build, and never run at a consumer's build (section 8.5).
- The server loads tools from a closed list: the core, `openmaterica-authoring` and `openmaterica-families`.
  The core's own read-side tools register through the same entry-point group. No tool it loads makes a network
  request, and it speaks over stdio only. Only its own module loads sibling code, through the entry-point
  group; every static import of a sibling from `materica` is refused (sections 7.1, 8.1 and 8.2).
- OpenMaterica's own families stay in this repository, in the import package `materica_families`, not a part
  of `materica`. A second publisher publishes its families from its own repository, under its own namespace
  (sections 3.1 and 7.1).
- A sibling stays in lockstep with the core's minor for life: it depends on `openmaterica>=X.Y.F,<X.(Y+1)`
  after 1.0 as before. The core's sibling extras pin the matching minor with a range, never `==`, and `[all]`
  brings both siblings only. The version machinery is built with `openmaterica-authoring`'s first release
  (section 7.2).

Everything else here is a proposal.

Origin: a sketch by the maintainer of a photoacoustic chain (optics, a thermoelastic step, acoustics, the
FVM), offered as a vague idea to extract the core from. Its core is that one description of a tissue,
phantom or device has to feed many physics, and many simulators.

How to read it: a statement with a file path was read in the tree or checked by running something;
"recalled" marks something from memory that was not checked; "would" marks a proposal. Paths are relative
to the workspace that holds the sibling repositories: `MIME:` marks a MIME path, `MADD:` a MADDENING path,
and `i4h:` an Isaac for Healthcare repository. Private planning documents are named, never linked.

## 1. What OpenMaterica is

An open description of what bodies, tissues, phantoms and devices are made of, for simulation: one
**material record** per substance, with a section per physics, every value in SI with its provenance and
its uncertainty. Records are plain files that any language can read. OpenUSD is the primary way to bind
them to scene geometry, but a consumer without USD (a one-dimensional layered model, a finite-element code,
a MATLAB script) uses the same records.

**Scope.** OpenMaterica describes substances in and around the human body: tissues and body fluids, the media
and phantoms that stand in for them, agents introduced into them, and the materials of devices that enter or
touch them. It does not describe systems: an apparatus or its calibration, the quantities of one object (its
moment, inertia or mean density), a drive, a procedure, or a simulator's tuning. Five rules apply it:

- **Specimen or object.** A value of a substance, or of a mixture given by its composition, measured on a test
  specimen whose shape and size are recorded as conditions, is in. A value of a made object as built (a
  device, a product, an assembled robot) is out: its consumer computes or records it. So a magnetic value
  measured on a sphere of a composite is in, with the sphere as a condition, while the capsule built from that
  composite keeps its own total moment, mass and inertia. Shape-dependent values measured on specimens (blood
  viscosity in a tube of stated diameter, a notched failure specimen) are in the same way.
- **Pairs.** A property of two substances in contact (friction, slip) is in, as an interface record (section
  4.13), when the source states the surface conditions and the test method. A number measured with one tool
  or device is reference data for checking a model. A solute's diffusivity in a medium is a pair too, of its
  own kind, with no surface.
- **Geometry is scene data.** OpenMaterica defines how geometry binds to materials, and ships only small test
  phantoms and label crosswalks from reference anatomies, never anatomy itself.
- **Behaviour.** A behaviour computed from geometry and materials (an implant's heating in MRI, a puncture
  force) is the consumer's output. A measured one is reference data in the consumer's namespace.
- **Entry.** Content enters when a named consumer needs it, and the curated library starts with the body and
  the materials of devices that enter or touch it. An apparatus's materials (a coil's copper, a detector's
  scintillator) go in other namespaces as material records. Other publishers may use the same machinery in
  their own namespaces, including for data OpenMaterica does not curate (section 4.1).

An earlier wording of the first rule, a transfer test ("would the value hold for another object of the same
substance?"), was tried over 64 cases: 47 values and records from the prototypes, MIME's constants and Isaac
for Healthcare's tissues, and 17 edge cases raised in review. It gave no clearly wrong answer, but a review
then showed it put a capsule's effective susceptibility in while the statement's own example put it out, so
the line is now drawn between a specimen and a made object.

**Relation to materiomics.** OpenMaterica is adjacent to materiomics, not infrastructure for it. Materiomics,
in both its senses, studies a material system across its hierarchical levels (Cranford and Buehler 2010) or
screens biomaterial libraries against cell response (Cranford et al. 2013), and defines no record of
property values. OpenMaterica records measured properties of specimens, with their test conditions, specimen
facts and provenance, at the scale where a simulation consumes them; it does not represent the structure,
process, hierarchical level or cell response whose relations materiomics studies. Materiomics studies could
publish the property values they measure into it, and multiscale models could take their top-level inputs
from it, once each value states the level and the length scale at which it was measured (section 4.8).

Design principles:

1. **The read side needs no OpenMaterica code.** A C++ renderer, a JAX solver and a PyTorch policy trainer
   read the same records with nothing but a JSON parser, or with USD. Verifying a record's content hash also
   needs a canonical JSON serialiser (RFC 8785) and SHA-256, both standard and available in most languages
   (recalled).
2. **No solver dependency.** OpenMaterica knows nothing of MIME, MADDENING, JAX, Warp or Isaac, and its code
   never runs inside a consumer's computation: its simulation step, compiled program and gradient path. A
   consumer that reads, interpolates, evaluates or mixes there writes its own code and verifies it against
   OpenMaterica's conformance data, golden vectors and check points. OpenMaterica's code may run at a
   consumer's build, outside that computation (section 7.2).
3. **Provenance and uncertainty on every value**, stated, never implied.
4. **Fail closed.** An unknown model family or version, an undeclared uncertainty structure, or a check
   point that disagrees makes a reader refuse, never guess.
5. **Data carries its own checks.** A record holds check points, which let a consumer confirm that it
   evaluates a parameter set as the reference implementation does at the states checked, and a convention
   witness: a response the source reports, independent of how the parameters were obtained, which they must
   reproduce (section 4.6). Each check is reported for what it can show, and for nothing more.
6. **Mechanism in the core, content outside it.** The core defines how families, records and checks are
   declared and verified. Model families and the material library are separately versioned content
   (section 3.1), as MIME's physics is content on MADDENING's mechanism.
7. **Small.** A section, a family or a library material enters only when a consumer needs it (section 7.6).
8. **Models propose; code and people decide.** Language models may help draft records (section 8). They never
   run on the read side or in the checks, and never decide a tier, a unit, a check point or a fit.
9. **Records hold facts; consumers declare choices.** A record says what was measured, on what, under which
   conditions, and how it is known. It never says where, in what state or in which regime a model applies,
   which stand-in is acceptable, how to mix materials, or which of two competing values to use. The consumer
   declares those; the build checks the declarations against the records and records them. That data exists
   never means that a model applies (section 3.5).
10. **Carry what the evidence supports, no more and no less.** No default, nominal value, distribution,
    interpolation across an edge or extrapolation that the source does not give. A consumer may declare one of
    these for its own use, with its basis; the build records the declaration and labels the results. A spread
    says what it represents. Nothing unchecked is reported as passed.

What OpenMaterica is not:

- not a solver, a mesher, a segmenter or a renderer;
- not a database service, and not a host for large datasets;
- not a constitutive-model library for production use: reference implementations exist to define and
  verify, not to run in loops;
- not a judge of whether a value applies to a use, a patient's included (principle 9);
- not a description of systems: apparatus and their calibrations, one object's derived quantities, drives
  and procedures stay with their consumers (scope, above);
- not a source of anatomy: geometry is scene data;
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
openmaterica           mechanism: read and check                   Apache-2.0          SOUP-relevant
  specification; record JSON Schema; USD schema; record model and I/O; verification machinery
  (check points, conformance, uncertainty structures); label fractions; a reference sampler;
  the MCP server, run only with the `[mcp]` extra (section 8)

openmaterica-authoring tools: write and curate                     Apache-2.0          curation tooling
  authoring (composition, derivation, fit records, check-point baking); the curation tools;
  integrations (exporters, importers, the Isaac generator)

family packages        content: model-family definitions            Apache-2.0
  one namespaced, separately versioned definition per family: equations, golden test vectors,
  reference implementation, admissibility; shipped together as `openmaterica-families`, whose import
  package is `materica_families`

library repository     content: curated materials                   CC0-1.0 (section 6.4)
  its own review process; static releases with a DOI, no hosted service (section 6.7)
```

- The core changes rarely. Families and materials grow only when a consumer needs them.
- Anyone can publish families and records in their own namespace, in their own repository, under the
  same rules and the same checks (sections 4.1, 4.5 and 6.7). Only the curated library carries this
  project's review.
- A manufacturer assesses `openmaterica` plus only the families and records it uses, each with its own version
  and content hash (`DOCUMENTATION_ARCHITECTURE.md` section 10). The core's wheel includes the MCP server,
  which no consumer's build runs (section 8.5). `openmaterica-authoring` is curation tooling, and part of a
  consumer's product only when the consumer's build runs it, as a build that runs the engine adapter does
  (section 7.2).
- **Families** live in one directory of the main repository, outside the core package, and ship as one
  separate distribution, `openmaterica-families`, whose import package is `materica_families` (maintainer,
  2026-10-17; section 7.1); each family version has its own content hash, so a manufacturer assesses only the
  families it uses. OpenMaterica's own families stay in this repository, and a second publisher publishes its
  families from its own repository, under its own namespace (maintainer, 2026-10-17; sections 4.1 and 4.5).
  That retired the earlier trigger, a move into repositories of their own when a second publisher of families
  appears (section 15).
- **Reference implementations sit with their families**, not in the core. Consumers evaluate families with
  their own code (principle 2), so a reference implementation runs only on the write side, to define the
  family and bake check points. Golden vectors live only with their families, and check-point baking (in
  `openmaterica-authoring`) imports `openmaterica-families` on the write side only. The core keeps a generic
  runner that compares numbers against golden vectors and check points.

### 3.2 Layers inside the core

```
 L6  Adapters and tools   MIME adapter (in MIME); exporters, importers, Isaac adapters
                          (openmaterica-authoring); the record checks as a command
                          (`python -m materica check`); the MCP server (section 8)
       ^
 L5  Sampling (optional)  volume fractions from label volumes; layered paths derived from 3-D geometry
       ^
 L4  I/O                  plain records (required); USD (optional extra)
       ^
 L3  Authoring            composition to spectra, derived values, fit bookkeeping, check-point baking;
                          the curation tools (section 8.2). Shipped as openmaterica-authoring
       ^ L2  Core (stdlib only)   records, values, provenance, statistics, uncertainty structures, units,
                          reference forms of the mixing rules, validation
       ^
 L1  Data                 conformance cases, spectra tables, analytic test phantoms             (no code)
 L0  Schema               record JSON Schema; schema.usda, generatedSchema.usda, plugInfo.json  (no code)
```

Rules:

- A layer imports only layers below it. L0 and L1 need nothing at all.
- Nothing in `materica` imports a sibling (`materica_authoring`, `materica_families`) statically. The MCP
  server loads the tools of the core and of its listed siblings through an entry-point group, and only its own
  module does so (section 7.1; maintainer, 2026-10-17).
- Nothing imports a simulator. Adapters for a simulator import it lazily and live where their owners
  choose: MIME's adapter in MIME; exporters, importers and Isaac adapters in `openmaterica-authoring` until
  someone upstream wants them.
- `openmaterica` holds L0 to L2, L4, L5, the `check` command and the MCP server, which runs only with the
  `[mcp]` extra (section 8.1); `openmaterica-authoring` holds L3 and L6's integrations. A consumer's product
  depends on the first, and on the second only when its build runs it, as one that runs the engine adapter
  does (section 7.2).
- USD is an optional extra (section 7.2).

### 3.3 Two kinds of user

| | Writes materials | Reads materials |
|---|---|---|
| Who | library curators; a lab characterising a phantom; a fit writing results back | every simulator |
| Needs | L2, L3, L4 (Python) | L0, plus a JSON parser or USD, in any language; optionally L2 and L5 in Python |
| Does | composes, converts units, derives, fits, bakes values, statistics and check points with provenance | reads SI numbers and parameter sets, interpolates tables, evaluates power laws, applies the mixing rules it declared, verifies check points |

Everything that needs computing happens on the write side. A reader evaluates a model family only with its
own implementation, which it verifies against the record's check points. This is what keeps C++ consumers
first class (section 7.5).

### 3.4 One source of truth

Library materials are authored as plain records, and USD layers are generated from them, never edited (decided
2026-10-12). Every prototype wrote plain records first; the first outside consumer needed a C++ table
generated from records, not a stage; and USD's own physics material stores density as float32, so a stage
cannot be the source of every value at full precision. A round-trip check in CI keeps the two forms equal.
Scene-level overrides, such as a fit for one scene or an organisation's own measurement, are overlay records
(section 4.1), which name their base record by identifier, version and content hash. A consumer applies an
overlay only by declaring it, never by an order of layers, and a fit's overlay is scoped to the model that
produced it (section 5.5).

### 3.5 Facts, declarations and the build

Principle 9 in practice. A record, a consumer and the build each make a different kind of statement:

| | States | Examples |
|---|---|---|
| A record | facts about a measurement, and how they are known | the specimen (species, site, state, preparation); the conditions it was measured at; the range covered; statistics and what they represent; competing values where sources disagree |
| A consumer | choices, declared when it attaches a model | the domain (which regions); the target (species, site, state); the family version; the mixing rule; which competing value; tolerances; waivers; any extrapolation or nominal it assumes, with its basis; the overlays it applies; the independence it assumes between fields it samples together |
| The build | the relation between the two | per region and field: met, not met or unknown; how the specimen differs from the target; the picks and waivers, all recorded in the material input sheet (`DOCUMENTATION_ARCHITECTURE.md` section 9.1) |

Four rules:

1. **Never infer applicability from which data exist.** A fluid section on a tissue does not put the tissue
   in a flow domain. A fracture energy does not say which failure model governs. A value measured at 25 °C
   does not apply at 37 °C, and a fit does not apply outside its coverage.
2. **Check where declared, and report the rest.** Requirements are checked over what the consumer declared:
   the regions of a domain, a family version, a range of states. A check has three results: met, not met
   and unknown. Unknown (a condition the source does not state, a field a model reads that nobody declared)
   is refused unless the consumer waives it, and every waiver is recorded. An unknown result still carries
   the value the record holds, so a waiver has something to use. Nothing undeclared passes silently.
3. **An edge of applicability hands over to other physics.** At the edge of a domain a node gets geometry
   (a distance function for a wall) and, where it needs one, an interface record (section 4.13), not an
   average of the materials on either side. At the edge of a model's range of states, the model the consumer
   declared next takes over (evolution families, section 4.5). A family never names its successor: which
   model follows is a choice about applicability. The library never averages, interpolates or extrapolates
   across an edge. A consumer's grid may still smooth one (a soft boundary, an immersed boundary): that is
   the consumer's declared discretisation, tested for convergence.
4. **Competing values coexist, and the consumer picks.** Where sources disagree, or one source supports two
   fits, a record keeps every alternative found as a list, each with its full provenance and none marked as
   the default. A consumer's sensitivity to the choice decides only how hard a curator searches for
   alternatives, never which are kept. The consumer picks, and the run records the pick. Validation may later
   show which was right; recording the pick is the obligation, validating it is not.

Four limits keep this usable:

- **Tolerances.** Most literature values were measured at room temperature, or the source does not say,
  while MIME runs at 37 °C. A requirement states how far a condition may differ, why (a sensitivity, a
  temperature coefficient) and what the difference costs (in one prototype, a 15 K tolerance on water's
  temperature passed a 29 % error in drag), or the consumer waives it. A consumer may also declare once that
  a specimen fact implies a condition ("values measured in vivo are at body temperature"), with a reason;
  the declaration is recorded and replaces a waiver per field.
- **Only a model that reads a field declares anything about it.** A Stokes-drag run declares nothing about
  the fluid's density. A requirement belongs to the model that reads the field, and the operating conditions
  it is checked at (a temperature, a frequency band) are declared once per experiment.
- **What changes during a run** (heating, a Reynolds number that depends on velocity) cannot be refused at
  build. It is watched at run time, and the results are marked (section 9.6). A condition that an optimiser
  moves is such a quantity: a fit that moves a temperature can leave a table's range mid-run. So the build
  emits a run-time watch for every condition and tolerance a consumer declares on a field, not only for a
  table's own axis: a constant measured at 37 °C has no axis, but a run that heats it still leaves its
  tolerance.
- **Extrapolation and nominal values are the consumer's to declare.** Where a source gives no value at the
  consumer's operating point (a band that excludes its frequency, an interval with no nominal), the result is
  "not met". The consumer may declare an extrapolation or a nominal for its own use, with its basis (a stated
  law, a temperature coefficient, a midpoint it chooses); the build records the declaration in the material
  input sheet and labels the results. Isaac for Healthcare's ultrasound table at 3.5 MHz is the first case:
  for most tissues, the open sources fitted attenuation over bands that exclude it (prototype P2). An
  evaluator that clamps outside its range is extrapolating by a constant, so it needs this declaration, or
  its in-range flag stops the run.

This is the positive form of a non-goal the draft has had from the start: OpenMaterica makes no judgement of
applicability (section 7.6). The review of section 15 found the draft making that judgement in at least
eight places; the sections below no longer do. Nor does OpenMaterica grade data. The pedigree matrix of
life-cycle assessment scores a datum's reliability, completeness and correlation to its use and turns the
scores into uncertainty factors (Weidema and Wesnæs 1996); that is the road not taken here. The facts such a
score would rest on are recorded, and judging them is the consumer's.

## 4. The data model

### 4.1 Material, section, value

- **Every record has a type**, in an envelope that every record shares: identity (a namespaced identifier, a
  human-readable name, a version), `record_type`, the record-schema version it was written against, a
  content hash (section 5.6), provenance, and the value machinery of this section (value forms, conditions,
  statistics, families, check points). The body depends on the type.
  - OpenMaterica defines three types: `material` (a substance, with any subset of sections); `interface` (a
    pair, section 4.13; the name is reserved from the first schema, its body is specified in 0.2, R9); and
    `overlay` (a scene-level or private replacement of some of a material's fields, a consumer's fit, or a
    user's fill-in of a reference-only value: it names its base record's identifier, version and hash, its
    scope, and the fields it replaces; sections 5.5 and 6.2). The curated library
    curates, cards and lists materials and interfaces.
  - **A reader skips a type it does not know when it lists records, and refuses one that is referenced**: by
    a binding, an overlay declaration, a pin, a layered-path interval or an interface member. Skipping a
    referenced record would let a region silently fall to the background. A new type is then an additive
    change (section 5.6). The conformance suite has both cases.
  - Another namespace may define its own type on the same machinery, for data that is not a substance: a
    calibration of MIME's electromagnet, for example. Its body's meaning belongs to that namespace; the core
    checks its envelope and value machinery, never its body. The first such type is specified only after
    MIME has prototyped one, the Navion's calibration, on it; that calibration also needs a value form for
    arrays of vectors, which none of section 4.4's forms holds yet.
  - The field is `record_type`, not `kind`, because a family definition already has a kind (static or
    evolution) and one name with two meanings is the trap section 4.5 warns about.
  - The risk is that OpenMaterica drifts into a general data format. The guards are a small envelope and a
    curated scope of substances (section 1).
- A material may carry sections in another namespace in an **`extensions`** block keyed by namespace, using
  the core's value forms and provenance; the namespace owns their meaning. It carries, for example, a
  renderer's settings in plain records, as namespaced attributes do on a USD prim (section 4.14). Extension
  values are their namespace's responsibility and outside the curated library's review, so curated records
  carry none.
- **Scene documents are not records.** A plain scene manifest, a layered path and a label crosswalk describe a
  scene, not a substance (section 5.2). They have schemas of their own, and bind records by identifier,
  version and hash.
- **Identifiers are namespaced**: `<namespace>/<local id>`. A namespace belongs to one publisher and is
  shared by its records and its families (section 4.5). Namespaces are short names of the characters
  `[a-z0-9_]`, registered first come first served in the publishers file (section 6.7); CI refuses a
  collision. A namespace is unique only once registered, so consumers pin records by hash, not by name.
  `materica` and `mime` are reserved. In `materica`, local identifiers are the catalogue numbers
  `MAT-XXXX` for materials and `INT-XXXX` for interfaces (for example `materica/MAT-0001`). Other
  publishers choose their own. Namespaces from the start let anyone publish records without a central
  authority (section 6.7); adding them later would be a breaking schema change.
- A **section** is one physics. A consumer checks only the sections it needs. A section's presence says
  what is known about a material, not where that physics applies (section 3.5).
- A **value** takes one of seven forms (section 4.4), in fixed SI units, with provenance (section 4.7),
  statistics or an uncertainty structure (section 4.9), and the conditions it was measured at (section 4.8).

### 4.2 Sections

| Section | Example contents (SI) | Typical consumers |
|---|---|---|
| Bulk | mass density, with its kind (apparent, for a porous tissue as a whole, or of the solid matrix); elemental composition, and later composition by named component | every section that needs them: fluid, acoustic, radiological, mechanical dynamics |
| Fluid | viscosity, rheology model | fluid solvers |
| Mechanical | parameter sets by model family: linear elastic (isotropic; anisotropic, with a declared symmetry class, as stretch), hyperelastic, viscoelastic, rate-dependent forms; failure properties (below) | soft tissue, bone, compliant walls, rods, needle and tool insertion, contact, tearing |
| Acoustic | sound speed, longitudinal and, for solids, shear, each with its propagation direction where the material is anisotropic; attenuation as an amplitude coefficient, a power law over a stated frequency band, for each wave type; nonlinearity B/A | ultrasound, acoustic actuation, photoacoustics |
| Optical | absorption and scattering spectra, scattering anisotropy, refractive index | photoacoustics, fluorescence, photothermal, optical coherence tomography |
| Thermal | conductivity, heat capacity, perfusion, thermal expansion, Grüneisen parameter | bioheat, photoacoustics |
| Dielectric | conductivity and permittivity, as tables over frequency or as Debye or Cole-Cole parameter sets | capacitive and impedance sensing, MRI RF heating, electromagnetic tracking, ablation |
| Radiological | mass attenuation against photon energy (or derived from the bulk section's composition) | X-ray, CT |
| Magnetic | susceptibility, remanence, saturation, each with the shape of the specimen it was measured on (section 4.8) | robots, implants, coils |
| Biocompatibility | test evidence reported for a material: endpoint, standard and part, contact category and duration tested, material form and processing | asset cards, registries |

Mechanics is organised by model family, not by Young's modulus and Poisson's ratio: linear elasticity is one
family among several, and most soft tissue needs another.

**Which sections are specified first.** Bulk, fluid, mechanical (with failure), acoustic, radiological,
magnetic and biocompatibility have consumers now (section 12). Optical, thermal and dielectric are described
here so that the design accounts for them, and are specified when a consumer needs them; adding a section
later is a minor schema change (section 5.6). Two of the deferrals need a word:

- **Radiological now, optical later.** Both describe how photons interact with matter, in different
  regimes. At X-ray energies attenuation follows from elemental composition (photoelectric absorption and
  Compton scattering), and a projection needs no transport of scattered light. At optical wavelengths
  absorption comes from chromophores and scattering dominates, so light needs a transport model. What they
  share is machinery: tables over photon energy or wavelength, and spectra derived from composition. The
  radiological section builds the spectral machinery generally (an axis in either unit), so that the optical
  section adds fields to it later; composition, by element now and by named component later, lives in the
  bulk section, and both derive from it.
- **Temperature is a condition, not the thermal section.** Water at 25 °C and at 37 °C is the fluid
  section's table over temperature, checked against a declared operating temperature (sections 4.8 and
  3.5). The thermal section (conductivity, heat capacity, perfusion, expansion, the Grüneisen parameter) is
  for consumers that compute heat, and enters with the first of them.

**Failure** is part of mechanics: fracture energy, strength and critical stretch, each with its test method
and specimen geometry as required conditions, because a tear test, a notched specimen, a puncture and a
uniaxial test do not give interchangeable numbers. A puncture or cutting force is not a material property:
it depends on the tool and on friction between tool and tissue, which is an interface (section 4.13). It is
reference data for checking a model, never a stored property. Failure is specified with mechanics: its
properties are static data, and a failure criterion that depends only on the current state is a static
family. Models of how failure develops in time (damage, crack growth) are evolution families (section 4.5).

**Bulk** holds what describes the substance rather than one physics. The X-ray projector needs density in
every region, solids had no section for it, and a density under both fluid and acoustic would be two copies
of one fact (prototype P1c). Elemental composition sits beside it for the same reason: the radiological
section derives from it, and optical composition (by named component) is added later beside it. Two cautions
come with one shared density. For a porous tissue (trabecular bone, lung) the apparent density of the whole
and the density of its solid matrix differ widely, so the kind is a required condition. And a consumer that
pairs a density with a sound speed from another source, to compute an impedance, compares their specimen
facts first (section 4.11), because the two may describe different specimens.

**Anisotropic solids.** Bone is the first case. A measured sound speed is a fact with its propagation
direction (a categorical condition, section 4.8), and these come with the acoustic section. The complete form
is the stiffness tensor: a linear elastic family with a declared symmetry class (isotropic, transversely
isotropic, orthotropic or general), its constants in Voigt form, stated in the material's principal axes.
Speeds in any direction then follow from the tensor and the density; a tensor derived from measured speeds is
a derivation with those speeds as its inputs (section 4.3). The tensor is stretch (section 12.1, A10): its
consumer is MIME's acoustics through bone, and for the skull, porosity and shear waves matter more than
direction (section 12.2, transcranial ultrasound). How a material's axes lie in a scene (along a bone's long
axis, say) is scene data: an orientation on the region (section 5.1), needed whenever a direction-dependent
value is used.

**Solids in acoustics** need both wave speeds. A solid's compressibility depends on both; taken from the
longitudinal speed alone, it is underestimated by about a third at a Poisson's ratio of 0.33 (my
arithmetic), which matters for the radiation force on a solid particle.

**Biocompatibility** belongs to a finished device in its intended use, not to a material (recalled: ISO
10993-1 evaluates the device in its final form). The section holds test evidence reported for a material.
A device's biocompatibility is declared on the device by its maker, citing that evidence; it is never
derived from the device's materials.

### 4.3 Laws, tables and composition

- **Store laws, not values at one operating point.** Optical properties depend on wavelength, acoustic
  attenuation on frequency, most properties on temperature.
- **Composition is a write-side input.** Tissue optics is usually derived from volume fractions of water,
  blood (with its oxygenation), lipid and melanin, times tabulated spectra (recalled: Jacques 2013). A
  material may record its composition, but the absorption spectrum a reader sees is the baked table.
  A baked table states its composition (oxygen saturation, blood fraction) as conditions. Composition is
  also what transport changes in a simulation (Appendix A.2), so a consumer that varies it evaluates
  composition in its own code, with the L3 functions as its reference (section 7.6).
- **Derived values say so, and inherit their inputs' limits.** The Grüneisen parameter can be measured, or
  derived from thermal expansion, sound speed and heat capacity. A derivation's inputs must share their
  conditions, or the result is labelled mixed; the result carries the specimen facts of all its inputs
  (section 4.11); the method guide states the derivation's assumptions. The Grüneisen parameter of water
  changes by roughly half between 20 and 37 °C (recalled), so inputs taken at different temperatures are
  not a detail.
- **A conversion that needs another quantity is a derivation.** Per mass to per volume, or emu per gram to
  amperes per metre, needs a density, and is recorded as a derivation with that density's provenance.
  Rescaling, such as millimetres to metres, is a unit conversion.
- **A value evaluated from a reference formulation** (water's density and viscosity from the IAPWS
  formulations, recalled) has that origin, with the formulation, its version and the evaluation as evidence
  in place of a quote (section 4.7).

### 4.4 Seven value forms

| Form | Read side | Example |
|---|---|---|
| Constant | read the number, at the conditions it was measured at | density |
| Sampled table | interpolate by the table's declared scheme, inside its range, never across a declared edge | absorption against wavelength |
| Power law `a * x^b` | evaluate inside its stated range | attenuation against frequency |
| Interval | read the bounds with their basis; never a nominal (section 4.9) | an unmeasured property bounded by related tissues; "below 0.1" |
| Composition | read component identifiers and fractions with their basis (by mass, volume or mole) | elemental composition of soft tissue; an NdFeB grade |
| Model parameter set | evaluate the named family with your own implementation, after verifying the record's check points | a hyperelastic fit; a Cole-Cole fit |
| Reference data | read; used to check fits, never as a property | a digitised stress-stretch curve; a measured spectrum |

The first five are the forms a reader computes from or reads directly. Anything richer is either evaluated on
the write side and baked into one of them, or is a model parameter set, whose meaning the family definition
fixes. A composition states its sum rule; where the source's fractions do not sum to one (one source in
prototype P4 stated a composition summing to 114 %), the stated sum is kept as a fact and the composition is
not normalised silently.

Every form carries the range it was measured or fitted over, and a reader refuses outside it rather than
extrapolate (principle 10), unless the consumer declared an extrapolation with its basis (section 3.5). An
unknown token in any enumerated field (an interpolation scheme, a statistics basis, an uncertainty structure
that a reader does not know) refuses that field. A table also declares:

- **its interpolation scheme**, because the right one depends on the quantity: mass attenuation against
  photon energy is interpolated on log-log axes (recalled: the practice for NIST's tables);
- **its edges**, where the quantity jumps and nothing may be interpolated across: absorption edges (iodine's
  K-edge at 33.2 keV and neodymium's at 43.6 keV, recalled, both inside the diagnostic X-ray band), phase
  changes;
- **the source's own validity range**, where it differs from the range tabulated (a formulation valid more
  widely than the points written out, or a table whose source warns about its ends);
- **evidence per point** where points come from different places in a source.

A power law also states the basis of its exponent (fitted, assumed or theoretical). Attenuation is stored as
an amplitude coefficient in nepers per metre per hertz to the power b, always. The source's own unit (decibels
or nepers, per centimetre, per megahertz) and whether it reported an amplitude or an intensity coefficient
(they differ by a factor of two) are extraction facts, with the conversion recorded (prototype P2 found both
traps in real sources and in a consumer's code). A power law whose band the source does not state is read as
unknown, never as valid everywhere. A value measured at several conditions is several values, each with its
conditions; there is no power law whose coefficient varies with a second condition.

**Reference data** have a defined payload: points, each with its own origin and status; or curves, flagged
as digitised where they were, with the digitiser's axis calibration and its estimated error.

**Evaluating a table in a consumer's own code.** A consumer's evaluator gives the same values as the
reference reader, but a derivative at a table's knots and ends depends on a convention: a linear table has a
kink at every interior knot. The conformance cases give, at every interior knot, the value and the derivative
from each side, and at each end the derivative from inside only; a consumer's evaluator states which side it
returns at a knot (JAX's `jnp.interp`, for example, returns the right-hand derivative at interior knots and at
the lower end, and the left-hand one at the upper end; prototype P5). The build reports when a declared
operating condition sits exactly on a knot: in P5 the water table had a knot at 310.15 K, where the two
one-sided slopes of viscosity differ by 1.6 %, so a sensitivity taken there depends on the evaluator's side.
An evaluator also returns whether its condition was in range, because an evaluator that only clamps turns
"outside the record" into a value with a zero derivative: a fit then stalls silently at the table's end (P5).
Clamping is a constant extrapolation, so it needs a declaration (section 3.5), or the in-range flag stops the
run.

A constant can make a model claim without saying so: one viscosity means a Newtonian fluid, one
susceptibility a linear response with no saturation. Such a constant names its trivial family as a label
(for example `materica.fluid.newtonian.v1`; a one-parameter family needs no check points) and the range it
was measured over, so a consumer can check its operating point: blood's viscosity is close to Newtonian
only at high shear rates (recalled). Such a constant is a scalar for the rules on witnesses and statistics
(sections 4.6 and 4.9), not a model parameter set.

A field override (section 5.1) is a sampled table over space and follows the same rules. It also declares its
frame: the world, or a region's reference configuration. A reader refuses to move a world-frame field with a
deforming body; a property that depends on deformation is a family with a deformation input (section 4.5).

### 4.5 Model families

A model family is identified by a namespaced, versioned identifier, for example
`materica.mechanical.ogden_incompressible.v1` or `<org>.dielectric.cole_cole_4term.v1`, never by a common
name alone. The same name hides different formulas in different solvers and papers (as I recall, Ogden's
strain energy appears with different factors on its coefficients and with different volumetric terms), so
a name alone lets one parameter set give different stresses in two solvers with no error anywhere. The
trap is wider than formulas: one name can cover two output measures (nominal and Cauchy stress), and one
symbol two quantities, so the definition states every measure and symbol it uses.

A family definition (a document and its data files) fixes:

| Item | Contents |
|---|---|
| Kind | per loading control: `static`, a response to the current input; or `evolution`, with internal state and a time axis, and optionally events. One model can be both: a spring and dashpot in parallel (Kelvin-Voigt) is static under strain control and an ODE under stress control (prototype P3). Every rate the family takes is marked an input (a history the consumer supplies) or a test condition (the rate the parameters were measured at); one fed as the other gave a 2.2-fold jump in stress at fixed stretch in a real code base. Both kinds are admitted (below) |
| Kinematics and outputs | the deformation or input measure (stretch, Green-Lagrange strain, frequency) and the output measure (Cauchy or first Piola-Kirchhoff stress, complex permittivity), both required, with conversion vectors between the measures a consumer may use; the loading modes covered |
| Equations | the energy or response function, normatively; the treatment of incompressibility; the domain of each term, where a definition switches between forms |
| Parameters | names, units, meaning, order |
| Admissibility | constraints a parameter set must satisfy, as functions of its parameters alone, for example stability conditions; a condition over a range of states is a matter of evaluation and coverage. Each constraint has a name and states whether its boundary is admissible, and each fails a value that is not finite. Bounds on one parameter and linear inequalities over parameters are written as data in the manifest, so a consumer builds its own vectorised predicate and `materica check` evaluates them for any family without running its code; any other constraint is defined in the document and named in the manifest. There are no equalities and no expression language |
| Golden test vectors | inputs and expected outputs at a stated precision, as data files; edge cases; admissibility cases; vectors on both sides of every switch between forms; consistency vectors wherever continuity fixes a derived constant |
| Reference implementation | plain numpy, written for clarity: the executable form of the definition. It ships with the family, not in the core (section 3.1) |
| References | `[@Key]` citations |

Rules:

- Changing anything in a definition creates a new version. Golden vectors are frozen per version.
- A reader that meets a family identifier or version it does not know refuses the value.
- Records hold parameters only in the family's own convention. Conversion to a particular solver's
  convention happens in an adapter or exporter (L6), and each conversion has its own vectors showing that
  the solver's form reproduces the family's outputs.
- Only reviewed pull requests to this project's repositories publish under `materica.`. A family enters that
  namespace when an in-scope record uses it (section 1); until then it lives in its consumer's namespace. It
  is admitted with a definition, golden vectors, a reference implementation and a
  named consumer (`DOCUMENTATION_ARCHITECTURE.md` section 6.4); a family with no consumer for two releases
  is deprecated. A consumer that cannot be named publicly may be attested instead, on conditions
  (`CONTRIBUTING.md`). A family in a publisher's own namespace needs no admission.

**Evolution families.** Much of what MIME and other consumers meet depends on history and rate, not on the
current state alone: viscoelastic and rate-dependent mechanics (tissue, vessel walls, hydrogels), a
viscoelastic fluid such as vitreous humour (recalled), the relaxation of a magnetic particle's moment in a
rotating field, a drug-release law, damage and crack growth, thermal damage (an Arrhenius integral that
reaches a threshold), magnetic hysteresis. They are supported from the start, at two levels:

- **State and history.** A family with internal state variables and a time axis: its definition states the
  state variables, their initial values and the equations that evolve them in continuous time, never as a
  discrete update, so that a time step never becomes a material parameter. Rate enters as an input history,
  and the rates a fit covered are part of its coverage (section 4.10). Viscoelastic and rate-dependent
  mechanics need nothing more.
- **Events.** A family may also declare events: a condition on state and input that crosses zero in a
  stated direction, and what follows: the state changes, or the family's range of states ends. An event's
  time is computed, never given. A family never names the model that takes over when its range ends; that
  is a choice about applicability (section 3.5, rule 3). The consumer declares the chain as pairs of family
  and record (family A with record R1, on event E, hands over to family B with record R2, with a stated
  mapping of state), because the successor's parameters may belong to another record: native liver becomes
  coagulated liver after thermal damage, a record with its own specimen state. The build records the chain
  in the material input sheet, and the run records each hand-over and its time. A hand-over that changes the
  material at a point during a run joins the deferred question of domains that change during a run (section
  13).

Linear history dependence also has a static form in the frequency domain, a complex modulus against
frequency, as Cole-Cole is for permittivity. A linear viscoelastic family can be stored in either form, and
the exact conversion between them is an adapter with its own vectors (the rules above). Nonlinear models
and models with events have only the time-domain form.

The reference implementation states its integrator and its event location, pinned by cases with analytic
answers (relaxation after a step, creep under constant load, a threshold reached at a known time). Three
items change:

| | Static | Evolution |
|---|---|---|
| Golden vectors | inputs and outputs | an initial state and an input history; state, outputs and event times at stated times, with tolerances |
| Check points | responses at a few states | responses to a few standard histories (a step; ramps at stated rates; for a linear family, steady oscillation at stated frequencies), and event times. A history is chosen so that a condition crosses its threshold cleanly: an event time is badly conditioned where the condition only grazes it |
| Witness | a reported value at a state | a reported trajectory (a relaxation or creep curve, a response at stated rates) or event time (section 4.6) |

A family's events are defined independently of any solver (principle 2). Whether a consumer can use them
inside a differentiable step is the consumer's matter: for MIME, an event becomes useful inside its
compiled, differentiated step once MADDENING's differentiable events exist (planned for MADDENING 0.5.0,
recalled from its scope). Until then a consumer evaluates an event-bearing family outside that step, or
watches the event's condition with a runtime monitor (section 9.6). State-and-history families need
nothing from MADDENING beyond what it already offers.

### 4.6 Check points and convention witnesses

When a model parameter set is written, the reference implementation of its family version computes the
response at a handful of states (stated deformations, rates, frequencies, loading modes), from the stored
parameters, or, where a set has no single vector, from each member or from a corner made of the source's
bounds, and the record stores those input-output pairs with a tolerance. A check point never carries a vector
the source did not give. Before using the parameters, a consumer evaluates its own
implementation at the same states and compares. A mismatch is a refusal.

- A convention mismatch then fails loudly even for a consumer that never ran the conformance suite.
- Check points travel with the record into overlays, USD layers and private copies.
- They are required for every shipped model parameter set (reference-only sets ship none, below) and optional
  for the other forms, where they add little.
- Their tolerance is set by what they must tell apart (a convention error, a wrong branch) and by the
  precision consumers declare, never by habit. A check point at a state where every candidate convention
  gives zero (an undeformed state) checks nothing and is not written. Evolution families state tolerances
  that allow for the integrator's discretisation.

**Check points cannot catch an extraction error.** They are baked from the stored parameters, so a parameter
set assigned to the wrong family, or transcribed in another convention, is self-consistent and passes.
Check points show that a consumer evaluates the parameters as the reference implementation does, at the
states checked, and nothing more. They say nothing about whether the record matches its source, and they
are not shown as evidence about a value. They must span the fit's coverage and the family's branch points (a
change of loading mode; a switch between two forms of a function in an implementation); a consumer that
evaluates outside them is told that its range is unverified.

That is the job of the **convention witness**: a response the source itself reports (a stress at a stated
stretch, a modulus, points on a published curve, a permittivity at a stated frequency), stored with its
locator, which the parameter set must reproduce under its assigned family version within a stated
tolerance.

- **A witness must be independent of how the parameters were obtained.** For parameters a source reports,
  any response it also reports will do. For a fit, data used in the fit cannot witness it: fit
  reproduction (section 4.10) cannot fail on a misread axis, and a nominal-stress curve read as Cauchy
  stress is fitted perfectly by the wrong parameters. A fit needs a held-out datum the source states (a
  modulus in the text, a second loading mode, a point left out of the fit), and its curves need their axis
  quantities quoted. A witness record says which fit it is independent of.
- **A witness's tolerance comes from the fit's residual and from how precisely the source states the
  state** (a stretch given to two digits), never from the spread between specimens, which says nothing
  about whether these parameters reproduce this source. Where a source reports the same quantity twice (a
  table and a figure), the two are checked against each other first.
- **A witness may test the family alone, or only through a model of the test.** A relaxation curve from a
  uniform test witnesses a viscoelastic family directly. A force-time trace from a puncture depends also on
  the tool's geometry and on friction; the witness record says so, and the model of the test and its
  inputs become part of the witness and its uncertainty. OpenMaterica has no solver, so `materica check`
  reports such a witness "not checked by `materica check`", and it counts towards admission only if the model
  of the test is itself a family with golden vectors.
- **A parameter set that is the mean of per-specimen fits** may describe no specimen (section 4.9). It is
  witnessed against per-specimen data, or recorded "no independent witness"; its residual against the
  source's mean curve gives no tolerance.
- Every model parameter set taken from a source needs a witness, whoever or whatever extracted it. Without
  an independent one, a parameter set is not admitted to the curated library. In a community namespace it
  carries the flag "no independent witness", which is reported and never shown as a pass, and a consumer
  may refuse it.
- Witness data are reference data (section 4.4) and follow the same tiers. Where a witness cannot be
  shipped, the curator's check at review is recorded and the public check reports "not checked", as for
  fit reproduction.
- **Reference-only parameter sets ship no check points**, because a few check points determine a family's few
  parameters, which would publish them (section 6.2). The fill-in is checked by the witness instead: the
  record ships the witness's locator and an extraction recipe; the user fills in the parameters and the
  witness datum from their own copy, as an overlay in the user's own namespace (section 6.2); `materica
  check` runs the witness locally. The fill-in tool also records
  the identifier and version of the user's copy and compares them with the record's; a mismatch gives
  "unknown", because a preprint and its version of record need not carry the same numbers (in prototype P4, a
  value MIME cites was not in the preprint; the version of record was not checked). The result is reported as
  "fill-in consistent with the user's copy": it catches a typing error that breaks agreement between the
  parameters and the separately typed witness datum, not both taken from the wrong row. The curator's own
  witness result at review is recorded beside it. Check points computed locally after a fill-in verify only
  the consumer's evaluator, which is all check points ever verify.
- On real data, independent witnesses are scarce: in the importer prototype, 1 of 20 parameter sets had a
  passing one, 9 were behind paywalls and 6 had none. The rule stands for the curated library (maintainer,
  2026-10-12), and a figure digitiser with axis calibration is the first curation tool (section 8.2),
  because a published figure is often the only witness available.
- `materica check` runs the witness checks.

### 4.7 Provenance

Each value carries:

| Field | Contents |
|---|---|
| origin | what established the value: measured by the source, measured by the contributor, fitted, derived, evaluated from a reference formulation, or stated without an origin (a number found in code or a datasheet with nothing behind it) |
| source | a key in the source registry (section 6.1), with the document's identifier and version, and a locator that holds for that version: table (quoting the column header with its index), figure, page or equation |
| extraction | the method: a table; the text; digitised from a figure (with the tool, its axis calibration and an estimate of digitising error); a supplementary dataset (with its licence); an own measurement; a derivation (with a method identifier); a fit (with its fit record, section 4.10); and, for text, which text extraction of the document matched |
| conditions | section 4.8 |
| statistics or uncertainty structure | section 4.9 |
| specimen | species, anatomical site, state, preparation, shape (sections 4.8 and 4.11) |
| review | who checked the value against the source, and when; the curator's ORCID; whether the reviewer is independent of the person or tool that extracted it |
| tier | shipped, reference-only or private (section 6.2), computed from the source registry, never written by hand |
| evidence | for a value extracted from text or a table: the verbatim quote (with the conditions and, for a power law, the exponent quoted too), its locator, and the SHA-256 of the document copy it was read from; for a digitised figure, the locator and the copy's hash; for a reference formulation, the formulation, its version and the evaluation. Quotes are required for every such value in the curated library, whoever drafted it, and optional in other namespaces; where one exists, `materica check` verifies it in every namespace. If the legal review rules that quotes may not ship (section 6.5), a record ships the SHA-256 of the normalised quote with its locator, the text stays in the curator's private store, and re-verification compares hashes. Quotes are not published for reference-only values, because a quote contains the value |
| assistance | when a model helped draft the value: tool, model and provider as reported, prompt version, date (section 8.5). The value's origin does not change |
| search record | for a statistic pooled across sources: the queries, databases, date and inclusion criteria that found the sources |
| witness | for a parameter set: its convention witness (section 4.6) |

Rules the prototypes added:

- **A hash identifies a copy, not a document.** Publishers stamp downloaded copies (with the downloader's
  address, in one case), so two people's copies of one paper hash differently. The record keeps the
  document's identifier and version beside the copy's hash, and re-verification means "the quote occurs in
  your copy". Stamped copies hold personal data and never ship.
- **Every status is explicit.** "Not checked" and "none" are values; a missing field is not one of them.
  Fields filled when a record is imported are kept apart from fields filled when it is curated, and a
  parameter set may carry provenance per parameter.
- **A citation found in code is a lead, not provenance.** In the importer prototype, all 10 citations in a
  real code base that could be checked carried an error (4 in the citation itself, 6 in the locator). The
  value is traced to its source and extracted again.
- **The tier is computed from the source registry** (section 6.1), never written per value. What a person
  sets is the source's redistribution status in the registry and each record's review status, and a record
  drafted with a model's help stays reference-only until a person has set both.

MIME's rule that "a number in a config file is a declaration until something fits it" (`MIME:CLAUDE.md`)
applies to values stated without an origin. A measurement a source reports is evidence, within the limits
its conditions and statistics state; it is not a declaration in that sense.

### 4.8 Conditions

Two kinds of fact describe a measurement, and the record keeps them apart:

- **Conditions describe the test**: temperature, frequency, wavelength, strain rate, shear rate, loading
  mode, test method, measurement geometry (a bulk rheometer; a tube of stated diameter), propagation
  direction, and the specimen's shape and size. Numeric conditions have a value or a range; categorical ones
  (loading mode, test method, propagation direction, specimen orientation, specimen shape) take values from a
  vocabulary. Shape and size are conditions, not specimen facts, because they change what a value means, so a
  consumer matches them through a requirement rather than accepting a difference (maintainer, 2026-10-12).
- **Specimen facts describe the thing tested**: species, anatomical site, tissue state, disease and treatment
  state, preparation, preservation and post-mortem interval, donor age (section 4.11).

Both use a controlled vocabulary with an extension mechanism. From the start it has three parts, because
free-text specimen facts in the prototypes never matched a consumer's target: species as NCBI Taxonomy
identifiers, anatomical site as UBERON identifiers (recalled), and a short list of tissue states (in vivo, ex
vivo fresh, frozen and thawed, fixed, phantom). Disease and treatment state is structured too, with "unstated"
as a value, so that a steatotic liver is never compared with a normal one as if they matched. Each condition
and fact also states its basis: stated by the source, or inferred (from a figure's caption, say).

Conditions record what a value was **measured at**, not where it holds. A condition or fact the source does
not state is recorded as a structured "unstated", and a check against it returns unknown, never met
(section 3.5). Some
conditions change what a value means, not only how far it can be trusted:

- a magnetic moment per volume measured on a sphere includes the sphere's demagnetisation, so it describes
  the material and that shape together; with a susceptibility near 2 it differs by about 40 % from the
  value for an elongated body (my arithmetic). Magnetic values therefore require the specimen's shape;
- blood's apparent viscosity in small vessels depends on the vessel's diameter (recalled: the
  Fåhræus-Lindqvist effect), so a bulk rheometer value and a value from a narrow tube are different
  measurements;
- failure values depend on the test method and the specimen's geometry (section 4.2).

Conditions and specimen facts together specify what a value measures: in metrology's terms, the measurand,
which needs the kind of quantity and the state of what carries it (VIM 2.3). What they leave unspecified is
definitional uncertainty (VIM 2.27), and scale is part of it. On one cartilage specimen a 20 nm tip measured a
modulus about a hundred times lower than a 2.5 µm tip did, while an agarose gel gave the same with both (Stolz
et al. 2004); particles of 200 to 500 nm move through mucus almost as through water, although its bulk
viscosity is 10⁴ to 10⁶ times water's (Lai et al. 2009); yet in vitreous a micropropeller met the bulk value
(Wu et al. 2018). So the gap between scales depends on the substance and is never assumed either way: a test
method that probes a length below the specimen's enters the vocabulary only together with a condition stating
the length it probes.

### 4.9 Statistics and uncertainty structures

Literature tissue properties often vary by a factor of two or more between sources (recalled), so a value
without its spread is not honest.

- **Scalar values** carry a statistics block, not just a range: number of specimens and donors, mean,
  standard deviation, minimum, maximum, the distribution if the source states one, and the basis
  (reported standard deviation, reported range, spread across sources, digitising error). Where a source
  gives only a range, the range is recorded with that basis. An uncertainty may be stated as relative, or
  as expanded with a coverage factor or a coverage probability, as metrology reports it, with the
  distribution, degrees of freedom, basis and meaning the source gives. The coverage factor divides out by
  definition; a distribution the source does not state is the consumer's declaration. A datasheet's minimum
  and maximum have the basis "specification limits": a promise about a product, not a measured spread.
- **Every spread says what it represents**: variation between specimens or donors (a population), the
  uncertainty of an estimate (a standard error, a fit's covariance), measurement error, or spread across
  sources. They answer different questions, and the first two differ by about the square root of the
  number of specimens. A consumer declares which its question needs: a population of patients needs the
  first, the uncertainty of a mean the second. Modellers of patient-specific credibility draw the same line
  between population variability and measurement error (Galappaththige et al. 2022). A measurement's spread
  also says the conditions it was obtained under, repeatability, intermediate or reproducibility (VIM 2.20 to
  2.24), because laboratories can disagree by far more than one laboratory repeats itself.
- **A source that reports no spread** is recorded as `dispersion: not_reported`, which is not the same as
  exact.
- **A value known only as an interval** (bounds with their basis, no nominal; or one bound only, such as
  "below 0.1") is recorded as such. A reader
  gives its bounds and refuses a nominal value, which would be a number the source never gave; sampling
  refuses too, because an interval is not a uniform distribution. A consumer that wants either declares it,
  and the run records it as the consumer's assumption. A range taken from other tissues for an unmeasured
  one has the basis "proxy range": a claim that holds at both ends holds over that range, and only if the
  true value lies inside it.
- **Parameter sets** declare an uncertainty structure, and what it represents. There is no default.

| Structure | Contents | Note |
|---|---|---|
| `ensemble` | one fitted parameter vector per member, with the levels the source nests its members in (donor, lot, specimen, repeat test) and each member's group at every level where the source gives it; every member equally likely | preferred: keeps the dependence between parameters without assuming a distribution. Specimens of one donor are not independent draws from a population of donors: a draw at the members' own level, or balanced over an outer level, says which it is, and a draw at an outer level needs one member per group. Restarts and posterior draws are not members |
| `multivariate_normal` | mean and covariance in the space in which the source states its normal approximation, or, for a fit a consumer writes back, the space its producer chose and records as chosen (identity or log, per parameter); a curator never re-expresses a source's covariance in another space | the form a fit's covariance arrives in; it assumes the family is right, so it excludes model-form error |
| `independent` | one marginal per parameter | only with a stated justification for independence |
| `marginals` | statistics per parameter, with "dependence not reported" | the commonest literature form (mean and standard deviation per parameter over n specimens); never sampled jointly; usable for sensitivity one parameter at a time |
| `interval` | bounds per parameter, with their basis, as the source gives them | for corner and sweep analyses. The box is not a claim that every combination exists. A consumer checks every corner, lists those that fail, and takes a worst case from corners only where every corner is admissible, every constraint is a bound or a linear inequality, and it has declared the quantity monotone in each parameter |
| `none` | nominal values only | must not be sampled |

A weighted ensemble or a mixture, if a source ever gives one, is a structure of its own. Where the source
separates anatomical sites, specimens from different sites are alternatives, each with its specimen; where it
pools them, the field's specimen states what the source states, and the build reports the difference.

Fitted parameters are strongly correlated as a rule, so sampling each from its own range produces combinations
that describe no real material, and some that the family's admissibility constraints forbid. Sampling
therefore happens in the space the record states, maps back, and rejects draws that violate admissibility,
counting them per constraint and reporting the acceptance rate. The accepted draws follow the stated
distribution conditioned on admissibility: in total variation they are one minus the acceptance rate from it,
and no map of the inputs moves the output further than that. So a consumer declares, once per sampled run, the
lowest joint acceptance it accepts, and below it the sampler refuses. Bounds a consumer adds of its own (an
optimiser's, say) are its declaration, counted apart from the family's. A consumer that wants the covariance
in another space declares that distribution, and the run records it as its assumption. A consumer that cannot
honour the declared structure refuses to sample. An ensemble has no nominal member, and its mean may describe
no specimen or be inadmissible, so any nominal value the consumer then uses is its own declaration, recorded.
The core ships a reference sampler for tests and simple consumers; production uncertainty quantification
belongs to the consumer (for MIME, to MADDENING: section 9.4).

### 4.10 Fits and reference data

A fitted parameter set records what it was fitted to: the reference data (by identifier, or by DOI and content
hash where the data are not shipped), the fit procedure, the loading modes and ranges covered, and the
residual. That coverage is a fact about the fit, kept as a set of loading modes and ranges, not as a box:
modes fitted separately do not make a joint range. Inside a solver an element's deformation is in no tested
mode, so coverage is also stated in measures that do not depend on the mode (the principal stretches or the
invariants, and the rate), and a general state outside it is "unknown" unless the consumer declares it. For an
evolution family it includes the histories fitted
(the rates, the hold times), and a consumer's requirement can be stated as a history ("strain rates up to 1
per second") and checked against them. A fit with no more data than parameters is recorded as exactly
determined: its residual is zero by construction and shows nothing. It is never a validated or verified
regime; whether a fit applies at an operating point is the consumer's declaration, checked against the
coverage (section 3.5).

Fitted parameters are not intrinsic material properties. They belong to a material, a model, a test protocol
and a fitting procedure together, and several parameter sets can fit one curve equally well. So sources are
compared on curves, not on parameters. Where several fits describe one curve equally well, or one source
supports two, the record keeps both if a consumer is sensitive to the choice (section 3.5, rule 4). For the
same reason a consumer's own fit is not written back as the material's value (section 5.5).

The fit-reproduction check (`DOCUMENTATION_ARCHITECTURE.md` section 6.3) evaluates the parameter set
against its reference data and requires the stated residual. Where the reference data are not shipped, it
reports "not checked", never a pass.

### 4.11 Proxies

Much tissue data comes from a stand-in: another species, another anatomical site, a cadaver for living
tissue, a phantom for tissue. But whether a value is a stand-in depends on what it is used for: porcine data
used in a study of pigs is not a proxy. So a record states its specimen as facts, per section or field
(species, site, state, preparation, shape: section 4.8), and the consumer declares its target. The build
computes how the two differ, per section and field, and the consumer accepts each difference explicitly,
in one declaration per experiment and section if it likes ("accept porcine data for acoustics"). Every
acceptance is recorded in the material input sheet. Most tissue data comes from stand-ins, so refusing them
by default would refuse nearly everything; requiring acceptance makes the choice visible instead.

The facts compared are those of the vocabulary of section 4.8: species, anatomical site, tissue state,
disease and treatment state, preparation and preservation. A fact the record leaves unstated, or marks not
applicable, against a fact the target states is reported as a difference too. A difference is reported
as facts ("species: *Sus scrofa* against *Homo sapiens*"), with the ontology's relation where one exists (a
part of the target site; a sibling of it). It is never graded into a score, which would be a judgement of
adequacy (principle 9). An acceptance names the section and the fact, with a reason.

A record may still say what a phantom or substitute was made to mimic, as its maker states it. That is a
fact about the phantom's design, not a judgement that it is adequate for anything.

### 4.12 Mixing rules

A cell that contains two materials needs one value per property for a consumer whose grid cannot resolve
them. Some mixing rules are identities, fixed by physics: mass density by volume fraction, for materials
that sit side by side in a cell (not for a solution, such as a contrast agent dissolved in blood, whose
density is measured or derived as its own value), and mass attenuation by mass fraction (recalled: Bragg
additivity). Others depend on how the materials are arranged
and on the regime, so no field has one right rule:

- sound speed in a cell that is half soft tissue (1050 kg/m³, 1540 m/s) and half bone (1900 kg/m³,
  3500 m/s) is 2139 m/s by the harmonic mean, the short-wavelength (ray) limit, and 1746 m/s by Wood's
  rule, which averages density and compressibility, the long-wavelength limit (my arithmetic);
- conduction across layers and conduction along them follow different rules (series and parallel);
- failure properties have no general mixing rule.

So the specification fixes only the identities and offers named rules, each with its assumptions
(arrangement, wavelength regime). The consumer picks a rule per node and field, and the material input
sheet records the pick; a field with no general rule refuses to mix. Mixing happens inside a domain only:
at a domain's edge a node gets geometry, not an average (section 3.5, rule 3).

The specification defines each rule, with a numpy reference form (`mixing_rules.md`), and the conformance
suite tests each rule at a single cell, with known fractions and values, rather than through a projector or a
solver, where a wrong rule can pass unnoticed (prototype P1c). Consumers write the rules in their own
framework, as they write evaluators: each is an elementwise average, and the differentiable-use prototype (P5)
wrote the identity rule in one line of JAX. An earlier draft shared one array-API implementation with
consumers; dropping it means no OpenMaterica code runs inside a consumer's computation (principle 2). P5 has
no evidence either way about the non-identity rules; this rests on simplicity, not on a measurement.

### 4.13 Interfaces between materials

Some properties belong to a pair, not to one material: friction and lubrication between a catheter or needle
and tissue, thermal contact resistance, a slip condition. They sit on an **interface** record, a record type
of its own (section 4.1) that names its two members. A pair property belongs to neither material; putting a
fact on the wrong owner is an error the prototypes met more than once (an object's moment of inertia and a
drive's field strength were both offered as material values). USD's own physics material
puts friction on single materials and leaves the combination to the engine (recalled), which loses the
pair.

Properties at the edge of a domain belong here too: a slip length, a wall's permeability to a species. So
does a species' diffusivity in a medium: a solute and a medium are a pair, and share the type.

An interface record carries specimen facts per member and its own conditions (the lubrication state, for
example), and follows every other rule of records. Friction is an interface property only when the source
states the surface conditions and the test method, which become required conditions, as failure's test
method already is. Most published friction coefficients were measured with one tool or one device; such a
number is reference data for checking a model of that system, not a property of the pair (section 1). A
puncture or cutting force stays reference data too (section 4.2).

Three things are settled with the interface body (0.2, R9), before any interface record ships: contact pairs
(two surfaces) are kept apart from solutes in media (no surface, so no surface conditions); an interface
record binds to a pair of regions in a scene, in the plain manifest and in USD (section 5.1), so that a flow
solver at a vessel wall can find its slip record; and members are named by identifier and major version, so a
minor revision of a member does not break the interface and a major one does.

### 4.14 Appearance is not physics

Isaac for Healthcare's ultrasound table mixes physical properties (impedance, attenuation, sound speed) with
renderer settings (speckle parameters). OpenMaterica holds the physical ones. A renderer's settings sit on the
same material in the renderer's own namespace (section 11.1). The speckle parameters are treated as renderer
settings until a first contact settles what they describe; if they describe physical scatterers (their number
density, size and impedance contrast), those are acoustic properties and belong in the acoustic section
(section 13).

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

- **Precedence** among the three 3-D representations, where they overlap, is declared by the scene and
  recorded in the material input sheet. The usual order is field override, then label volume, then region
  binding. A field override is a sampled table over space with the same provenance as any value: a
  CT-derived attenuation map carries the calibration that produced it (itself a model), its statistics and
  its review, or says that it has none.
- **Nested regions** (a vessel inside an organ inside the abdomen): an explicit integer priority on the
  region decides which material owns a point. There is no default taken from depth in the hierarchy, which
  is how a scene is organised, not proof that one region contains another (a capsule at `/World/Capsule`
  moving inside a lumen deeper in the tree would lose its points to the lumen). Where two regions with no
  authored priority claim a point, the reader refuses.
- **What a region is.** A region is marked explicitly, by an applied schema on its prim that carries the
  priority and, where a direction-dependent value is used, an orientation (a quaternion, with its frame
  stated), because a collection's membership includes descendants and cannot say on its own which prims are
  regions (prototype P1c). A region's geometry is its descendant geometry prims with purpose `default`, so a
  visualisation child adds no volume. A binding applies within its region and never across regions: a nested
  region carries its own binding (maintainer, 2026-10-12). An OpenMaterica binding on a prim inside a region
  that is not itself a region is refused when it differs from the region's own: its author meant another
  material there (a calcified plaque in a vessel wall), which needs a region of its own with a priority, or a
  reader would read it as vessel wall. Orientation fields, for axes that vary along a curved bone, come with
  the anisotropic family (section 12.1, A10).
- **Background**: a default material for points no region claims (water, air, agar), declared by the
  scene's author. Without one, such a point has no material, and a consumer that needs one there refuses.
  A declared background is inside every domain that needs it, so mixing where tissue meets the background
  (a voxel half tissue and half air) is mixing inside the domain.
- **Domains.** A domain is a named set of regions in which a consumer's model computes, declared by the
  consumer when it attaches the model (section 3.5) and never inferred from which sections the regions'
  materials have. A flow solver's domain may be the lumen of a vessel while an X-ray projector's is the whole
  scene. Requirements are checked over a domain's regions; mixing happens inside a domain; at its edge a node
  gets geometry and interface records. In plain records a domain is a list of region names; in USD it is a
  collection (`UsdCollectionAPI`, checked in prototype P1c), named relative to the prim that declares it, so a
  scene can be referenced into another without breaking its domains. Every domain is declared, including one
  of a single region. A domain that changes during a run (a failure that opens a path) is a consumer's
  run-time event, recorded in its run log; it waits for the mechanics track and for MADDENING's differentiable
  events.
- A **layered path** is a geometry of its own, read by one-dimensional consumers. MIME 0.3.0's imaging
  physics, acoustics and X-ray, needs it (maintainer, 2026-10-12): a ray or a transducer's beam through
  layered tissue. So its plain and USD forms are specified now (section 5.4). A
  sampling helper (L5) derives a layered path from 3-D geometry along a trajectory, which is also how a
  project checks a hand-authored path against anatomy once it has the anatomy.
- **Thin structures** (a vessel wall, a membrane, a skin layer) thinner than a voxel have no representation
  on the ladder yet. A shell with a thickness, the 3-D analogue of a layered path, is a candidate, added when
  a consumer needs one.
- Thicknesses, the orientation of an anisotropic material's principal axes, and other geometry are scene
  data, not material data. They may carry their own provenance (an anatomical atlas, an image), recorded in
  the scene.

### 5.2 Plain records and scene documents

A record is a JSON document valid against the record JSON Schema. Records are JSON only: a JSON-only reader
must read every record (principle 1), the content hash is defined over JSON (section 5.6), and YAML parses
some numbers differently between versions.

A scene without USD is described by plain **scene documents**, which are scene data, not records (section
4.1), each with a schema of its own:

- a **scene manifest**: the regions (each with a name, a material's identifier, version and hash, a priority,
  an orientation where one is needed, and an opaque reference to its geometry in the consumer's own format),
  the background, the domains as lists of region names, and interface bindings (a pair of regions and an
  interface record);
- a **layered path**: an entry point and a direction (or a reference to the curve it was derived along), the
  intervals with their thicknesses and their materials' identifiers, versions and hashes, and the declared
  assumption of lateral homogeneity;
- a **label crosswalk**: from a reference anatomy's labels, by number or by the segmenter's name, to material
  identifiers, versions and hashes. Its USD form would use `UsdSemantics` labels for the names (a lean, from
  the ecosystem survey; with A1).

The conformance suite has every scene case (nested ownership, domain checks, binding refusals) in both the
plain and the USD form, so a consumer never needs USD to use OpenMaterica.

### 5.3 USD schemas

Checked on 2026-10-11 with USD 0.26.5 and a one-schema prototype in a scratch directory; nothing in a
repository.

- One **single-apply API schema per section**: `MatericaBulkAPI`, `MatericaFluidAPI`, `MatericaMechanicalAPI`,
  `MatericaAcousticAPI`, `MatericaOpticalAPI`, `MatericaThermalAPI`, `MatericaDielectricAPI`,
  `MatericaRadiologicalAPI`, `MatericaMagneticAPI`, `MatericaBiocompatibilityAPI`. Attributes are
  namespaced `materica:<section>:<field>`.
- **No mixing rule on a field.** An earlier draft put one beside each field
  (`materica:acoustic:soundSpeed:mixing = "harmonic"`, with a default in the schema). The consumer now
  picks the rule (section 4.12); only the identities are fixed, in the specification.
- **No fallback values on physical attributes.** USD returns a schema's fallback for an attribute nobody
  authored, and it looks exactly like a value. Physical attributes are declared without fallbacks, and
  readers refuse a value that was not authored (recalled: `HasAuthoredValue`). The conformance suite has
  the case.
- **Resource-only**: `schema.usda` as the source, `generatedSchema.usda` and `plugInfo.json` as the
  registered form, no compiled library. MADDENING already ships its graph schema this way
  (`MADD:src/maddening/usd/__init__.py:29`).
- **Each field is one JSON string, and nothing beside it.** A field's complete plain form (value,
  conditions, statistics, uncertainty structure, provenance, check points) is written as one generated string
  attribute holding its canonical JSON. One reader serves both forms, a JSON parser. A string composes as a
  whole value, so a stronger layer replaces a field's value and provenance together, and the dictionary-merge
  trap of section 5.5 cannot arise. Prototype P1c already carried the consumer's declarations as one JSON
  string. An earlier revision also wrote a typed attribute holding "the value" beside each string, for
  USD-native engines; it was dropped (maintainer, 2026-10-12), because no engine reads OpenMaterica attributes
  today, the two copies could disagree with nothing to notice, and for an interval, competing values, a table
  or a parameter set there is no single value to write without inventing a nominal. It can be added later as
  an additive change, for single constants only, if an engine asks.
- **The envelope on the prim.** A material prim carries its record's identifier, version, `record_type` and
  content hash as attributes. Prim names carry no identity: a record identifier such as `MAT-0001` is
  not a valid prim name (checked), and a lossy mapping could make two records collide.
- A region is marked by an applied `MatericaRegionAPI` carrying its priority and any orientation (section
  5.1). An overlay record is a `MatericaOverlay` prim of its own (section 5.5). The material input sheet is a
  JSON string on the experiment's prim, beside MADDENING's graph (section 9.1).

Checked in the prototype:

- the plug-in registers at run time; `ApplyAPI("MatericaAcousticAPI")` and `HasAPI` work by name;
- schema fallbacks are visible on a material before anything is authored (sound speed read 1540, the
  schema's fallback): the reason for the rule above;
- the plug-in entry must carry `schemaIdentifier`. An `alias` equal to the type's name is refused.

Generated C++ classes are not needed; USD can generate them from the same `schema.usda` if a consumer wants
typed access (recalled).

### 5.4 Materials and binding in USD

- A material is a `UsdShade.Material` prim with the section APIs it needs. Shipped layers do not apply
  `UsdPhysics.MaterialAPI`. An earlier draft did, so that physics engines would see a density, but that API
  reads density in the stage's mass and length units, which a self-contained library layer cannot know (1050
  kg/m³ would read as 1050 kg/cm³ in a centimetre scene), it stores float32 (prototype P1c), and applying it
  exposes friction and restitution with fallbacks of 0.0, so every region would become frictionless to an
  engine (checked). An engine gets its materials from the engine adapter, in the units its engine crosswalk
  states (below).
- Library materials live under a scope of their own, never under `/Materials/<name>`, where they would merge
  silently with MADDENING's display materials of the same name (prototype P1c).
- **Geometry binds an OpenMaterica material with `UsdShade.MaterialBindingAPI` and a purpose of our own,
  `materica`; the `physics` purpose is the engines'** (maintainer, 2026-10-12, reversing the reuse of
  `physics` decided after prototype P1c). An engine never reads an OpenMaterica field: it reads typed
  attributes in its own schemas and in the units it documents, which shipped layers do not carry. Sharing the
  slot therefore gave engines nothing: given a `physics` binding to an OpenMaterica material, OpenUSD's
  reference physics parser reports no material for the shape, so the engine uses its defaults (checked in the
  review of 2026-10-12). Meanwhile the slot is contested. Isaac Lab binds its own physics materials there, by
  default stronger than descendants; SimReady requires every collider's physics binding to target a physics
  material; and NVIDIA's deformable schema binds materials per mesh subset and advises separate rigid and
  deformable materials, more than one target per prim can hold (ecosystem survey, 2026-10-12). Checked with
  USD 0.26.5: binding with purpose `"materica"` writes `material:binding:materica`, which
  `ComputeBoundMaterial` resolves for none of the purposes `physics`, `full`, `preview` and all-purpose, and
  OpenUSD's validators raise nothing for it. Whether NVIDIA's own tools strip unknown purposes was not
  checked.
- **An OpenMaterica value reaches an engine only through an engine adapter** (`usd_binding.md` section 10). An
  engine is declared as a model: its reads, requirements, operating conditions and acceptances work as any
  model's, and an **engine crosswalk**, a pinned data document, lists every attribute of the engine's material
  APIs, with its SI dimension, whether an OpenMaterica field or the consumer's declaration supplies it and a
  locator to the engine's documentation, the schema file that defines each API, pinned by its hash, and the
  engine's unit convention with its source. The adapter writes a value only where the build result is met or
  accepted; converts by one rule from the SI dimension and the stage's units; applies every API the crosswalk
  lists by name and authors every attribute, since a fallback reads like a value (PhysX's deformable Young's
  modulus falls back to 5e7 in stage units, and `UsdPhysics` computes mass with water's density where a
  material's is 0); writes engine materials under a scope of its own, never on an OpenMaterica prim; and
  stamps each with the read requests and declared values it came from, the APIs it applied, each attribute's
  type and dimension, the unit convention and the stage units it was written for, so that the stage check
  re-derives every value from the stamp alone and checks each stamped dimension against its unit. In 0.1.0 the
  only OpenMaterica field an engine receives is `bulk.density`; the rest is declared, with reason and basis,
  until the mechanical section and interfaces arrive.
- **OpenMaterica ships one engine crosswalk, for `UsdPhysics`; a crosswalk for any other engine is the
  consumer's** (maintainer, 2026-10-13). A crosswalk per engine version is adapter upkeep, not a standard: it
  follows each engine's schema changes (NVIDIA's deformable schema is replacing PhysX's and is written to
  become part of `UsdPhysics`; ecosystem survey, 2026-10-12), and needs answers only an engine's users can
  check, such as which mass unit Newton reads. What has to be common is written for no one engine's schema:
  the crosswalk's format, the conversion, the stamp, the check and the engine as a declared model. The
  consumer knows which engine version it runs, and its build fails on whatever the checks can see of a wrong
  crosswalk. To make a crosswalk cheap to write, a scaffold in `openmaterica-authoring` drafts one from the
  engine's schema file (`generatedSchema.usda`, read without registering it), which gives each attribute's
  name and type, and the writer adds what the file does not hold: dimensions, sources, units and the locators
  behind them (checked with USD 0.26.5). Each API in a crosswalk pins its schema file by hash; where that file
  is passed the crosswalk is compared with it, so an omitted attribute is caught, and elsewhere completeness
  is the writer's claim and the check says it was not compared. Only schema files passed explicitly count,
  never a registered plug-in's, so a crosswalk's validity depends on the crosswalk and the files passed, not
  on the install (review of 2026-10-13: usd-core's own `usdPhysics` file differs between 0.25.5 and 0.26.5).
  The cost: where no schema file is passed a crosswalk's completeness, and everywhere its dimensions and unit
  convention, are its writer's claims; Newton's mass unit is a question for whoever writes a Newton crosswalk;
  and two consumers of one engine each write the same crosswalk (section 13, item 10). A consumer whose own
  code sets its engine's parameters, as MIME does for MADDENING, needs no crosswalk: it reads OpenMaterica
  through the read contract at its build. The document was called an engine profile, then an engine map; the
  maintainer chose "engine crosswalk", the data-standards term for a table that maps one vocabulary onto
  another, on 2026-10-13, to avoid clashes with MADDENING's `Mapping`, Python's `map` and OpenUSD's
  `UsdProfiles` (section 13, item 8).
- **The check judges shapes, not regions.** Engines resolve a material per collider, per subset and per
  simulation mesh, and Isaac Lab binds the first colliders below the prim it is given, so the stage check
  takes each collider and each body a held crosswalk names, with instance proxies traversed, and each material
  bound to it with the `physics` purpose (not only those OpenUSD's reference physics parser reports, since it
  drops any material without `PhysicsMaterialAPI`), maps the shape to the innermost region above it, and
  re-derives its engine material from the stamp: a foreign material, a stale or hand-edited one, a scene layer
  written for other units, or a missing one is reported. It holds OpenMaterica's `UsdPhysics` crosswalk and
  the crosswalks passed to it; a build passes the crosswalks its declaration pins, and a stand-alone check
  lists what it could not check without a crosswalk, including every API it does not recognise, rather than
  flag it. The density it compares is the effective one, since `UsdPhysics.MassAPI` overrides a material's
  density. A declared engine model is met only when the check reports none of these for its shapes. The cost
  of leaving `physics` to engines is that the two materials can now disagree, where the shared slot made them
  one prim; the check is what keeps that from being silent.
- **Readers take a region's material only from a `materica`-purpose binding authored on the region's
  prim.** `ComputeBoundMaterial` falls back to an all-purpose binding, usually a display material, for a
  purpose with no binding authored (checked), so readers never call it, and they refuse an all-purpose
  binding to an OpenMaterica material (prototype P1c). Within a region a binding applies to the region's
  descendants; a nested region carries its own (section 5.1). Engine bindings are neither read nor refused.
- **Field overrides and label volumes** use `UsdVol` (checked: `UsdVol` has `OpenVDBAsset` and
  `Field3DAsset`). A volume is a `Gprim` that renderers draw, so it sits outside region geometry, and its
  fields take names a renderer will not bind (to a renderer, `field:density` is smoke).
- **Layered paths** have a typed prim of our own, `MatericaLayeredPath`: an entry point and a direction (or a
  relationship to a curve it was derived along), an array of interval thicknesses, one relationship to the
  distinct materials the path uses, an integer array giving each interval's index into that relationship, and
  the declared assumption of lateral homogeneity. USD keeps a relationship's targets in order only when they
  are distinct, and removes repeats (checked: skin, fat, muscle, fat, skin reads back as skin, fat, muscle),
  so one target per interval would silently drop layers. Readers refuse a path whose arrays differ in length.
  Thicknesses are geometry, in the length units of the layer that holds them, like the entry point. A project
  then moves from one dimension to a full scene without changing representation. A curve prim with one subset
  per interval was the alternative; a typed prim keeps the intervals' thicknesses and the homogeneity
  assumption as data, where a curve would invite renderers to draw it.
- Geometry units follow the stage's `metersPerUnit`; property values are SI whatever the stage says. Readers
  refuse a stage with no authored `metersPerUnit`, and check the units of the layer that defines the
  geometry, which can differ from the root layer's (prototype P1c).
- **Shipped layers are self-contained.** Every USD layer generated for a release has no composition arcs
  (sublayers, references, payloads) and no asset paths; an aggregate layer, if one is shipped, is
  flattened. A scene that uses the library adds its own arcs. Reading a library layer therefore reads that
  one file and nothing else, whoever published it. `materica check` enforces this.

### 5.5 Declared, then fitted

USD composition could hold a declared-then-fitted history: a library layer holds declared values, a scene
references it, a fit writes a stronger layer with fitted values, and the declared values stay intact
underneath (checked: a fitted 1555 m/s in a stronger layer composed over a declared 1570 m/s, and the root
layer still held 1570). OpenMaterica does not use it that way, for the reason below.

**A consumer's fit is not the material's value.** A viscosity fitted to a trajectory absorbs every error of
the model that produced the trajectory (its drag model, its wall treatment, its resolution), so it is a
parameter of the material, that model and that experiment together (section 4.10). Composed as a stronger
layer over a material, it would replace the material's value for every consumer on the stage, including
models it was never fitted with. So a fit, like any scene-level or private replacement, is an **overlay
record** (section 4.1):

- it names its base record by identifier and hash, the fields it replaces, and its scope;
- in USD it is a `MatericaOverlay` prim of its own, with a relationship to its base material and its scope
  as a JSON string, never an edit of the material's attributes, so composing layers cannot apply it;
- a consumer applies it only by declaring it, and the material input sheet records the declaration; whether
  the fitted or the library's value is used is the consumer's pick, not an order of layers;
- its scope is the hash of the whole model configuration that produced it (for MIME, the graph's
  `to_dict()`, with its mesh, time step and precision), not only a model's name and version, because a rerun
  at another resolution is exactly the kind of difference a fitted value absorbs. A consumer whose
  configuration differs gets "not met" unless it accepts the overlay explicitly.

While a fit runs, the field it moves is a parameter, not the record's value: the material input sheet marks
it "record value used only as the initial value", so a sheet never reports a record as met for a value that
an optimiser has since changed.

A fit that only one model can use is still worth keeping: it is that model's calibration, with its
provenance.

**A trap the prototype found.** USD merges dictionary metadata key by key across layers. When a fitted layer
wrote its provenance without a range, the composed provenance read "fitted" with the declared value's range.
The encoding of section 5.3 removes the trap: a field's value and provenance travel in one string, which a
stronger layer replaces whole, and a plain overlay likewise replaces a value's provenance whole, never key by
key.

### 5.6 Versions and hashes

- The record schema and the USD schema share one semantic version, independent of the package's. Additive
  changes are minor; removals, renames and changes of meaning are major, with a deprecation period.
- Every record records the schema version it was written against.
- Each family version is frozen (section 4.5).
- Each record has its own version and a **content hash**: SHA-256 of the record's canonical serialisation (RFC
  8785, recalled: an existing JSON canonicalisation that fixes number types and formatting, which prototype
  P1c found a hash must do), taken over the whole record, including its type, identity, licence and any
  extensions, and the schema and family versions it is read under, minus an explicit exclusion list: the hash
  itself, review records, card prose, and evidence tied to one copy of a source (a copy's hash). So a second
  review or a reworded card changes no pin, and a record cannot change type and keep its hash. The conformance
  suite has hash test vectors. A simulation that records the hashes of the records it read can show which
  records it read. What its nodes received after overlays, unit conversion, mixing and derivation is shown by
  the derivation chain in the material input sheet (`DOCUMENTATION_ARCHITECTURE.md` section 9.1), not by the
  hash.
- **Adding without breaking.** Any section, field, record type or extension can be added later as a minor
  schema change if five rules hold. Sections are optional, and a reader ignores sections it does not use. An
  added field never changes the meaning of an existing one; a change that would is major. An added member is
  never one slip from a member valid at its place (specification `record_format.md` section 10), since a
  reader refuses such a near-typo (maintainer, 2026-10-14). A condition a reader
  does not know gives "unknown", refused unless waived, because some conditions change what a value means
  (section 4.8); and an unknown token in an enumerated field (a new interpolation scheme, statistics basis or
  uncertainty structure) refuses that field, so an old reader never falls back to a default it does know. A
  reader skips a record type it does not know when listing, and refuses it when referenced (section 4.1). A
  reader that knows schema 1.2 therefore reads a 1.3 record, refusing exactly what it cannot interpret, and
  refuses a 2.0 record. Before 1.0.0 a minor version may still change shapes, so a reader reads only records
  of its own minor version (maintainer, 2026-10-12); consumers pin exact versions anyway (section 12.4). USD
  follows: a new section is a new API schema, and an older plug-in still reads its attributes as plain
  attributes (recalled; to check).
- **Advisories** (a note for later: built at the first retraction, or before the first release a regulated
  consumer takes). A pinned hash cannot learn that its source was later corrected, retracted or contested.
  An advisory index, kept outside the records and versioned on its own, lists such notices by record and
  hash, as a package index marks a yanked release. A build reports any that apply to the records it pins,
  without changing their values.

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
who judged it and when, and the source's role. Values point at registry keys. Because one source can exist
in several versions and copies (a preprint and a version of record; a publisher's copy and an archive's),
the entry also records, per copy, how it was retrieved, which version it is, and the licence that copy came
under (prototypes P2 and P4).

### 6.2 Three tiers

| Tier | What is published | Typical sources |
|---|---|---|
| Shipped | values and provenance | open-licence papers and datasets; own measurements; own fits and check points; individual factual values judged safe |
| Reference-only | provenance, locator and an extraction recipe; the values are filled in locally from the user's own copy of the source | sources whose redistribution status is not permitted or unknown |
| Private | nothing; an organisation's own overlay in the same format | proprietary or unpublished measurements |

The tools treat the three tiers identically, so the public library can be conservative without making
OpenMaterica weaker. Fits the curator makes from published curves are the curator's own work and can often be
shipped where the curves themselves stay reference-only. So can a shipped fit's check points.

The tools treat the tiers identically in mechanism, not in evidence. A user fills in a reference-only value
as an overlay record in their own namespace, whose base is the reference-only record by hash (maintainer,
2026-10-12). The curated record never changes, so every user and every scene that pins it holds the same
record; the overlay carries the user's licence, the evidence from the user's copy and the user's review, and
a reader labels every value read through it user-extracted. The material input sheet shows that label and
the overlay's review status. In a reference-only value the statistics are withheld too, since a mean is the
number itself, and the withheld state is what the public repository holds: the number lives only in the
curator's private store, never in the repository's history. Shipping the check points
of a reference-only parameter set would publish its parameters, since two points determine a two-parameter
family, so none are shipped; the witness checks the fill-in instead (section 4.6).

### 6.3 Extraction

- Primary literature, never bulk copies of a secondary database.
- The extraction method is recorded per value (section 4.7), because the risk, legal and numerical, differs
  by method.

### 6.4 Licences

Code is Apache-2.0. The curated library's data is **CC0-1.0** (decided 2026-10-12), and each record states
the licence it is distributed under.

- The aim is a standard others adopt and recombine, including in regulated products. CC0 removes attribution
  stacking in databases built from several sources (recalled: the reason Wikidata chose CC0), and an adopter
  needs no legal reading of it.
- Credit does not depend on the licence: every value carries its source and its curator's ORCID, and each
  release has a DOI (section 10).
- Values whose sources restrict them stay reference-only whatever the library's licence says (section 6.2).
  The IT'IS database's archive terms forbid redistribution (read in prototype P2), so it is a lead to
  primary sources, never a source to copy.
- Short quotes kept as evidence are third-party text and are not relicensed. Whether a shipped record may
  carry them is one of the legal review's four questions (section 6.5).
- The licence field in a record is structured: it states the licence of the values and excludes evidence
  text (quotes) from the CC0 grant, so a downstream user who relies on the machine-readable field never
  copies a publisher's text as if it were CC0.
- Publishers in other namespaces choose their own licence.

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
  versions used, specimen facts per section, fit-reproduction status, witness status (independent, or
  none), curators' ORCIDs. Check-point status is not shown: it shows that the reference implementation has
  not drifted, not anything about the values. The header is what an index, a viewer or a search reads.
- **Prose sections**, adapted from "Datasheets for Datasets" (recalled: Gebru et al.): motivation (why the
  material was curated, and for which consumer); composition (sections, value forms, conditions); collection
  (sources and extraction methods); processing (conversions, derivations, fits); what was measured and what
  was not (the specimens, the conditions outside which nothing was measured, disagreements between sources),
  never a statement that the material suits a use; distribution (tier and licence); maintenance (who curates
  it, and how to report a problem).

The prose is stored in the record as fields, so the record stays the single source of truth and the card
only assembles it. Cards replace the data sheets of earlier drafts.

### 6.7 Distribution and hosting

**Proposal: git repositories and static releases, no hosted service.** Three reasons:

- **The library is small.** Records, digitised curves and spectra are kilobytes each. Large data
  (CT-derived volumes, measured property maps) are not hosted here; a scene that uses them as field
  overrides gives them the same provenance as any value (section 5.1).
- **Static releases are what can be assessed.** A tagged release with a DOI and content hashes is under
  configuration management and can be assessed as SOUP. A live database that changes under its users
  cannot, and a hosted service would add uptime, access control and a cybersecurity boundary of its own.
- **The closest model needs no hosting to copy.** The Hugging Face Hub is git repositories plus an index,
  metadata cards and viewers, plus hosting for everyone. OpenMaterica can build the first three statically.

The repository is the database:

```
records in git ── pull request + review ──> materica check ──> build ──────────────> release
(source of truth)  (curation)                 (ingestion)       cards, USD layers,    GitHub release, archived on
                                                                index.json, plots     Zenodo with a DOI; a static
                                                                                      site on GitHub Pages
```

- **A release is one archive**: the records, the generated USD layers and cards, a generated `index.json`
  (every record's identifier, version, content hash, sections, tier and licence), and the shipped reference
  data. It is published as a GitHub release and archived on Zenodo with a DOI. A consumer pins a release by
  DOI or hash and needs nothing online afterwards.
- **Two linked Zenodo records, a third later** (proposal, 2026-10-13; revised the same day after a survey of
  the tools that index Zenodo, below). OpenMaterica looks like a blend of software and data, but the project
  already splits it along the lines Zenodo's resource types draw, so each part is archived as what it is:
  - **Software:** the OpenMaterica repository (the core, the specification, the conformance cases, the
    families), Apache-2.0, one Zenodo record with a new version on each GitHub release.
  - **Dataset:** each library release, CC0-1.0, its description stating that quoted evidence is excluded from
    that licence (section 6.4), one record with a new version per release. The archive itself is uploaded, not
    a link to it: Web of Science's Data Citation Index excludes data that is only referenced (Clarivate's
    selection policy, undated).
  - **Both are published through Zenodo's API by the release workflows**, not the software through Zenodo's
    GitHub integration as first proposed. An affiliation's ROR identifier and a funder's identifier reach
    DataCite only when chosen from Zenodo's own vocabularies, which the API can do; on the records observed on
    2026-10-13, a GitHub-integration release carried them only when someone added them on Zenodo afterwards
    (whether `.zenodo.json` can carry a ROR identifier was not verified). The cost is a Zenodo token held by
    the release workflow; the alternative was the GitHub integration plus editing each software version on
    Zenodo by hand. The API route is decided (maintainer, 2026-10-13); the rest of this item is a proposal.
  - **Links**, with DataCite relation types Zenodo offers (checked against its vocabulary, 2026-10-13): the
    dataset *is compiled by* the software version that checked it and generated its layers, cards and index,
    and *is documented by* that version, whose specification defines its format; the software carries the
    inverses, *compiles* and *documents*. These links are for navigation. DataCite counts as citations only
    *cites*, *references* and *is supplement to* and their inverses (DataCite support, 20 August 2026), and
    OpenMaterica's own records never cite one another, so no count is raised by self-citation.
  - **The dataset references its sources:** every source with a DOI that a release's records cite is listed as
    *references*, which DataCite records as a reference (same page), so that the measurements' authors are
    credited wherever those links are counted.
  - **One record would not do:** the licences differ by design (Apache-2.0 for code, CC0-1.0 for data), the
    two are released on different schedules (new values need no code release, a fix needs no data release),
    and they are cited for different things (implementers cite the software, curators and users the data).
  - **Later, a Standard record for the specification** (Zenodo's "Publication: Standard" type), so that an
    implementer in another language can cite the format without citing the Python package. It *documents* the
    software and the dataset, and from then on the dataset *is documented by* it. (The first proposal linked
    it as *is supplement to* the software, which DataCite would count as the software citing itself.) It is
    deposited as a Standard, under its lasting title, from its first version, because OpenAlex takes a
    record's type and title from its first version: one specification deposited as a Standard at 1.3.0 shows
    in OpenAlex as a report, titled as its 0.2 version was (RO-Crate, observed 2026-10-13). Before 1.0.0 the
    specification changes with every release and is already in the software archive, so its trigger is the
    first stable schema version or a second implementation. Zenodo now marks a Standard's page with a
    schema.org type that does not exist (`https://schema.org/other`), so search engines get no type for it.
    It comes from InvenioRDM's resource-type vocabulary, on which Zenodo runs; the maintainer reports it there
    before the first Standard deposit (decided 2026-10-13). The fault stays on Zenodo's own pages: DataCite's
    metadata for the same record gives `Standard`, mapped to schema.org `CreativeWork`, as does the DOI's
    content negotiation, so the indexes that read DataCite (OpenAlex, OpenAIRE, ORCID) and every citation
    count are unaffected (checked 2026-10-13), and the specification is deposited as a Standard whether or not
    it is fixed.
  - **Optionally a Zenodo community** grouping the records, and later the releases of other publishers'
    namespaces (whether the name is free was not confirmed).
  - **Pinning and citing:** each record has a concept DOI (every version) and a DOI per version. A consumer
    pins by version DOI and archive hash, as MIME's material input sheet records them; the concept DOI is for
    citing OpenMaterica in general, and the README gives its reference ready to paste.
- **Who finds and counts which record** (survey of 2026-10-13; what was not verified is marked):
  - **Google Scholar indexes no Zenodo record**, of any type (Zenodo's FAQ, 2024); Scopus indexes none either
    (its content coverage guide, 2023); Web of Science reaches Zenodo only through its Data Citation Index,
    whose current coverage of Zenodo was not verified. A paper is the only route into them (the table below).
  - **Google Dataset Search** reads only schema.org `Dataset` markup, which Zenodo writes for a dataset and
    not for software, so it finds the library and not the software. It needs a description of 50 to 5,000
    characters (Google Search Central, 8 September 2026).
  - **DataCite Commons and ORCID** see all three. DataCite counts citations per DOI without adding up
    versions, and shows no views or downloads for any Zenodo record, because Zenodo reports none to it; the
    usage figures to quote are Zenodo's and OpenAIRE's. An author's ORCID record is updated only once the
    author has enabled DataCite's auto-update, and only for versions published or changed after that (DataCite
    support, 7 August 2026), so each author enables it before the first release.
  - **OpenAlex and OpenAIRE** see all three, as software, dataset and standard (OpenAIRE: "other literature"),
    with ORCID, ROR and funder identifiers. OpenAlex merges all versions of a Zenodo record into one work,
    titled and typed by the first, so each record's title is chosen once, before its first deposit, and kept.
  - **Software Heritage** archives the software's source from Zenodo and shows its identifier on the record
    (Zenodo, 21 October 2024); some recent releases lacked one, so each release is checked. Its indexer reads
    `CITATION.cff`, as GitHub's "Cite this repository" does, so `CITATION.cff` stays in the repository, and
    the release tooling checks it against the deposit's metadata.
  - **Registries**, applied to by hand: an RRID (SciCrunch) for the software and the library (its scope read
    only in a search excerpt); FAIRsharing for the library as a knowledgebase and, once others use it, for the
    specification as a format. re3data does not fit (it lists repositories with an operating legal entity, and
    Zenodo is already listed), nor does bio.tools (it excludes programming libraries).
  - **Counts disagree by counter, and each is a lower bound.** On 2026-10-13 the IT'IS tissue database's
    version 4.0, the nearest published analogue, had 64 citations in DataCite, 98 in OpenAIRE and 134 in
    OpenAlex. A count OpenMaterica quotes names its counter and its date.
  - Not verified: whether BASE, Dimensions or the Data Citation Index cover Zenodo today; whether Zenodo
    passes DataCite relation types outside its vocabulary.
- **"The first library release" means the first such archived release with a DOI** (section 12.1, R8). Its
  prerequisites are the curation tools (R15), the legal review (section 6.5), and the publishers file with
  its template. Earlier tags of the library (M10) are unpublished pins for MIME's spikes, not releases.
- **Federation without hosting, from the first library release.** Any publisher keeps records in their own
  repository, under their own namespace (section 4.1), and runs the same `materica check`. Nothing needs
  this project's permission. Waiting for a second publisher before building the way to publish would make
  one less likely, so the first library release carries both pieces:
  - **a publishers file** (`publishers.yaml`) in the library repository: namespace, repository URL and the
    content hashes of releases, registered by pull request, first come first served, with CI that runs the
    data checks on each registered release. It hosts no data. Julia's package registry works this way
    (recalled), folded here into a repository that exists anyway. The file labels the curated namespace
    apart from community ones, and lists third-party families as well as records. The library's CI runs
    no third-party code: check points and witnesses of families outside `materica.` are reported "not
    checked (third-party family)", and a namespaced record type's body is never checked;
  - **a template repository**: a publisher uses it, adds records and pushes, CI checks them, and a one-line
    pull request registers the namespace.
- **MIME is the first other publisher.** Its `mime` namespace, published from the MIME repository, holds
  the records that do not belong in the curated library: a parameter set with no independent witness, MIME's
  fit overlays (which are scoped to MIME's models, section 5.5), and calibrations of MIME's own devices as
  record types of MIME's own (`mime:emns_calibration`, section 4.1), since a calibration is a system, not a
  substance. Federation and record types are then tested from the start on a real case.
- **Data too big for git** goes on Zenodo. A record points to it by DOI and SHA-256, and a tool fetches it
  only on explicit request, never when a record is read (`DOCUMENTATION_ARCHITECTURE.md` section 15,
  constraint 11), as Homebrew and Spack pin downloads by checksum.

Later, each when its trigger arrives:

| Item | Trigger |
|---|---|
| a separate index repository, if the publishers file outgrows the library repository | many publishers |
| a data wheel of the library on PyPI | the first Python consumer outside MIME |
| a viewer on the static site (fits plotted over their reference data); a SQLite build queryable in the browser (recalled: Datasette Lite, sql.js) | a library big enough to browse |
| an issue form that a bot turns into a draft record pull request | contributors who do not use git |
| a mirror of each release on the Hugging Face Hub, for discoverability only | adoption work (section 10) |
| a software paper (JOSS: no charge, a Crossref DOI, not indexed by Scopus or Web of Science's core collection) | the repository public for six months, with evidence of research use (JOSS's requirements) |
| a data paper (Scientific Data, Data in Brief; an article charge) | a library big enough to describe |

Not planned unless the scope changes: a hosted database, a query API, accounts, an upload portal. Their
triggers would be large imaging data, or many writers who cannot work through pull requests; both are
outside OpenMaterica's scope.

## 7. The core package

### 7.1 Layout (the 0.1 module list, agreed by the maintainer, 2026-10-13)

```
materica/                 the package a consumer's product depends on (distribution `openmaterica`); py.typed
  schema/0.1/             writer JSON Schemas (the source of structure); reader schemas generated
                          from them; schema.usda, generatedSchema.usda, plugInfo.json             (L0)
  data/                   conformance/ (cases and inputs), vocabulary/ (generated from the
                          specification's tables), engine_crosswalks/ (UsdPhysics)              (L1)
  shapes.py, shapes.pyi   the public API's JSON shapes as TypedDicts, generated from the schemas
  core/                   strict JSON, the canonical form and the hash, identifiers, vocabulary,
                          records and the store, the reader and its forms, conditions, overlays,
                          units, scenes and locations, declarations and the build, crosswalks,
                          record checks                                                (L2, stdlib only)
  io/                     plain.py; usd/ (needs pxr; every pxr call behind usd/_pxr.py)         (L4)
  sample/                 layered_path_helper.py (0.1); label fractions and the reference
                          sampler later                                                  (L5, numpy)
  tools/                  check.py: python -m materica check, --stage, --crosswalk, --schema    (L6)

materica_authoring/       curation tooling, where records are written
  integrations/engines/   the engine adapter and the crosswalk scaffold (0.1)          (L6, lazy imports)
  authoring/              compose, derive, fit records, bake check points; curation tools (8.2),
                          after 0.1                                                             (L3)
```

The MCP server is not in the 0.1 list; it comes with A9 (section 12.1). It is part of the core, in L6, and
runs only with the `[mcp]` extra, which brings the MCP library. No other module of the core imports the
server, so the core runs without that library (section 8.1; maintainer, 2026-10-16). Its module is proposed as
`materica/tools/mcp_server.py`, started by `python -m materica mcp`; both names are final with A9 (maintainer,
2026-10-17). That module alone loads sibling code, and only through the entry-point group of section 8.2.
Every static import of a sibling from `materica` stays refused, by a test with a control that must fail
(maintainer, 2026-10-17). Today the test that walks the imports (`tests/unit/test_source_files.py`) refuses
`materica_authoring`; `materica_families` is to be added to it. The 0.1 module list was agreed before the
first code (maintainer, 2026-10-13), together with making the writer JSON Schemas the single hand-edited
source of structure: the reader schemas and the TypedDict shapes are generated from them, and the
specification's member tables are checked against them.

Families, with their golden vectors and reference implementations, sit beside the core in the same repository
and ship as `openmaterica-families` (section 3.1). Its import package is `materica_families`, not a part of
`materica` (maintainer, 2026-10-17), since a distribution of its own cannot add modules to the core's regular
package. `materica_authoring` ships as `openmaterica-authoring`. Each sibling has a directory of its own in
the repository (`authoring/`, `families/`) with its own `pyproject.toml`, version line and changelog (section
7.2; `DOCUMENTATION_ARCHITECTURE.md` section 2). The library repository has its own layout
(`DOCUMENTATION_ARCHITECTURE.md` section 2).

### 7.2 Dependencies and distribution

- `openmaterica`: no run-time dependency beyond Python's standard library (maintainer, 2026-10-13): the
  reader's envelope checks are written by hand, which the specification's README allows
  (`docs/specification/README.md`, "Suites and case numbers"), so the core adds nothing to a consumer's SOUP
  list but OpenMaterica itself; each extra adds its own. Extras: `[check]` for `jsonschema` (`materica check`
  and the writer schema), `[usd]` for `usd-core`, `[sample]` for numpy and whatever else L5 needs, `[mcp]`
  for the MCP server's library (section 8.1), and `[authoring]`, `[families]` and `[all]`, which pin the
  matching siblings (below). Type
  checkers read `typing_extensions` through the `.pyi` files and `TYPE_CHECKING` imports; nothing imports it
  at run time. `openmaterica-authoring` carries the curation tools' heavier dependencies (PDF text extraction,
  the digitiser) and the only network access in the project: registry drafting from DOI and Crossref, a
  command a person runs with an explicit flag, which the MCP server does not load (section 8.2; maintainer,
  2026-10-17).
- **What runs where.** The core never runs inside a consumer's computation (its simulation step, compiled
  program and gradient path; principle 2). It does run at a consumer's build: MIME's build calls the reader,
  the requirement checks over domains, the material input sheet, L5's label fractions and, where it samples,
  the reference sampler, and their outputs become node data. So `openmaterica` is third-party software in a
  product built on MIME and is assessed as such (`DOCUMENTATION_ARCHITECTURE.md` section 10);
  `openmaterica-authoring` is not part of a consumer's product unless the consumer's build runs it, as a build
  that runs the engine adapter does; engine results themselves are computed in `openmaterica[usd]`
  (maintainer, 2026-10-13).
- `pxr` is imported from whatever USD is installed. Isaac Sim ships its own USD build, and `usd-core` 26.8
  publishes wheels for macOS, Linux x86_64 and Windows only (checked 2026-10-11), while Isaac for
  Healthcare also supports Linux on aarch64. So `usd-core` must never be a hard requirement.
- **Python versions** (maintainer, 2026-10-13): a floor of 3.11, and every Python that is not at end of life
  and that a named consumer or engine needs in-process. OpenMaterica need not share an interpreter with an
  engine: it runs at the build and hands over data (JSON results and USD layers), so it can run in its own
  environment while the engine opens the files.
- **One repository, three distributions** (maintainer, 2026-10-16). Each distribution has its own
  `pyproject.toml`, version line and changelog. The repository is a uv workspace, and each distribution is
  released from tags of its own prefix (`DOCUMENTATION_ARCHITECTURE.md` section 12). The curated library keeps
  a repository of its own (section 6.7). The layout, with the core at the root and each sibling in a directory
  of its own, is `DOCUMENTATION_ARCHITECTURE.md` section 2's. OpenMaterica's own families stay in this
  repository (maintainer, 2026-10-17; section 3.1).
- **The siblings' versions** (maintainer, 2026-10-16, except where a later date is given):
  - A sibling's MAJOR.MINOR is the core's MAJOR.MINOR it is built for; its patch number is its own. It depends
    on `openmaterica>=X.Y.F,<X.(Y+1)`, X.Y.F being the oldest core release it works with, before 1.0 and after
    it: a sibling stays in lockstep with the core's minor for life (maintainer, 2026-10-17, replacing `<(X+1)`
    after 1.0). So its range, its import guard and CI against the current core (below) agree.
  - A core minor is a release train: every sibling is released for it the same day, so every core minor has a
    matching sibling. The core's extras `[authoring]` and `[families]` pin the matching sibling with a range,
    `>=X.Y.0,<X.(Y+1)`, never `==`, and `[all]` brings both siblings only, not `[usd]` (no `usd-core` wheel
    for Linux on aarch64, above) or `[mcp]` (maintainer, 2026-10-17). So one `pip install -U
    "openmaterica[...]"` upgrades them consistently.
  - A sibling refuses to import against a core of another MAJOR.MINOR, with a message naming the command that
    fixes it. `python -m materica versions` lists the installed distributions, checks them against each other,
    and says which siblings exist for the installed core. Nothing updates itself.
  - CI tests each sibling against the oldest core in its range and against the current one.
  - Each sibling's first real pre-release goes out early, to claim its name on PyPI. For
    `openmaterica-authoring` that is a `0.1.0.devN`, once the uv workspace and the release workflow's change
    land, since a pending publisher on PyPI does not reserve a name (maintainer, 2026-10-17). Before a
    sibling's first real release, each earlier core minor gets an **explainer release** of it: versioned for
    that minor, depending on that core minor, and holding only an import that raises a message naming the
    first core minor the sibling exists for and the install that works. A resolver picks it only when the core
    is pinned to that minor. So `openmaterica-families` 0.1.0, published at core 0.1.0a1 or 0.1.0, says that
    families begin with 0.2 (R5, section 12.1) and claims the name. Not used: an sdist that fails its build
    with the message, which `--only-binary` skips and whose message build output buries.
  - The release workflow writes a compatibility table, each core version with its siblings' versions, into the
    documentation.
  - When (maintainer, 2026-10-17): `python -m materica versions`, the import guard, the extras and the CI
    matrix are built with `openmaterica-authoring`'s first release. None of it is built yet (section 14).
  - A regulated consumer pins exact versions all the same (sections 5.6 and 12.4).
- Release artifacts: the wheels on PyPI, and the schemas (L0) and conformance data (L1) as a separate
  archive for projects in other languages to vendor. Golden vectors live only with their families; the
  archive cites each family version's hash. Library releases are separate (section 6.7).

### 7.3 Uncertainty and sampling

The reference sampler honours the structures of section 4.9. Where a requirement samples a field, it never
samples `marginals` jointly, samples an `interval` or a spread with no stated distribution only from one the
consumer declares, and never samples `none`; a field no requirement samples is held. It rejects inadmissible
draws and reports the acceptance rate and the rejections per named constraint. It defines the behaviour and
tests consumers through the sampling suite, whose core arms map given normals exactly and whose statistical
arms compare with analytic values in exact regions, never with another sampler's draws. It is not a UQ engine.
A consumer that uses it in an analysis labels its results so. MIME moves to MADDENING's joint sampling once
its mapping passes the suite (section 9.4).

### 7.4 Conformance

Small cases, each with expected answers, as data files. They are enumerated in the case tables of the
specification (`docs/specification/`) and described suite by suite in `DOCUMENTATION_ARCHITECTURE.md` section
6.1; this section only describes them. Any implementation, in any
language, checks itself against them. That is what makes a second reader trustworthy without a second
implementation of everything.

The cases are grouped into **suites**, because no reader does everything: plain read; USD read; table
evaluation, with the derivative convention; mixing; family evaluation; sampling; build checks. A claim of
conformance names the suites passed, so a C++ reader with only a JSON parser can claim the plain-read
suite honestly. They cover refusals (an unknown family version, a failed check point, an undeclared
structure, an attribute nobody authored, interpolation across an edge or outside a range, a nominal for an
interval, mixing a field with no general rule, an unknown token, a referenced record of an unknown type),
three-valued checks (unknown, not met, for an unstated or unknown condition; a requirement checked over a
domain's regions only; a declared extrapolation recorded, an undeclared one refused), scene cases in both the
plain and the USD form (the owner of a point inside nested regions; a binding inside a region that differs
from the region's own; a layered path whose arrays differ in length), values at the edges of tables (both
one-sided derivatives at interior knots, the inside one at ends; the in-range output), unit conversions (an
intensity attenuation coefficient converted to an amplitude one), mixing at a single cell, analytic volume
fractions of the canonical test phantoms, and hash test vectors. Sampling cases map given normals exactly, or
compare with analytic values in exact regions; none compares one sampler's draws with another's.

### 7.5 The read side in another language

What a consumer does, with no OpenMaterica code:

1. Read a record with a JSON parser; or, with no plug-in needed, detect OpenMaterica schemas by name in each
   prim's composed `apiSchemas` and take each
   region's material from the `materica`-purpose binding authored on the region's prim, never from
   `ComputeBoundMaterial`'s fall-back to an all-purpose binding, and leave `physics` bindings to engines
   (section 5.4). Skip record types
   you do not know when listing; refuse them when referenced.
2. Read SI values; refuse attributes that were not authored and tokens you do not know; interpolate tables by
   their declared scheme, inside their range and never across an edge, stating your derivative convention at
   knots and returning whether the condition was in range; evaluate power laws inside their range.
3. For a parameter set: confirm the family identifier and version are known; evaluate your own
   implementation at the record's check points; refuse on a mismatch. For a reference-only set, fill in the
   values from your own copy as an overlay in your own namespace and run its witness locally (sections 4.6,
   6.2).
4. Apply the mixing rule you declared, inside your domain, and the identities where they exist; honour the
   precedence your scene declares (section 5.1); take provenance as in section 5.5.
5. Sample only as the declared uncertainty structure allows, and only the spread your question needs
   (section 4.9).

Everything else (composition, unit conversion, derivation, fitting) was done when the record was written.

### 7.6 Scope rules

- **Admission.** A section, family or library material enters when a named consumer needs it, with its
  evidence (`DOCUMENTATION_ARCHITECTURE.md` section 6.4 for families, `CONTRIBUTING.md` for materials). A
  family enters `materica.` when an in-scope record uses it (section 4.5).
- **Non-goals.** No solver, no mesher, no query service, no hosting of large datasets, no description of
  systems (section 1), no judgement of applicability (the consumer declares it: section 3.5), no fast or
  differentiable model evaluation, and no code that runs inside a consumer's computation (principle 2).
  Consumers write their own evaluators and mixing rules (MIME's are JAX) and verify them against the
  conformance cases, golden vectors and check points. Prototype P5 found this enough for gradients: a ten-line
  JAX evaluator matched the reference reader exactly and gave exact gradients with respect to the condition
  and every table entry.

### 7.7 Governance

- Apache-2.0 for code (decided); CC0-1.0 for the curated library's data (decided; section 6.4).
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

- **OpenMaterica calls no model and holds no keys.** It exposes deterministic tools over the Model Context
  Protocol (MCP). The researcher's own agent (any MCP client: a coding agent, an IDE assistant, a custom
  command-line tool) brings the model and the key. Bring-your-own-key holds by construction, not by
  configuration.
- **The MCP server** is part of the core, in L6, and runs only with the `[mcp]` extra, which adds an MCP
  server library and no model SDK (maintainer, 2026-10-16). It loads the tools of the core and of the listed
  siblings that are installed (section 8.2). It speaks MCP over stdio only and opens no socket (maintainer,
  2026-10-17). It makes no network requests, since no tool it loads makes one (section 8.2), and reads only
  files the user points it at, such as their own copies of papers. Fetching papers is the agent's business, on
  the user's request (`DOCUMENTATION_ARCHITECTURE.md` section 15, constraint 19).
- **MCP sampling** would let the server request completions from the client's model, keeping
  bring-your-own-key while letting OpenMaterica sequence the steps. Client support was uneven when last
  recalled; the design assumes an agent-driven loop and does not use sampling at first (decided
  2026-10-12).
- **Nothing a model touches is on the read side.** No model runs in a reader, in `materica check`, in a
  release build, or in any consumer's build. MIME's build binds materials by identifier and content hash
  and never calls a model.

### 8.2 The deterministic toolset

MCP's three primitives map onto OpenMaterica as follows (recalled from the MCP specification; check before
building):

| Primitive | Exposes |
|---|---|
| Resources (read-only) | records, cards, `index.json`, family definitions, the source registry |
| Tools (deterministic) | query the index; get a record (values bundled with conditions, specimen facts, tier and hash); compare sources on curves; gap analysis against a consumer's required properties; create a draft; attach and verify a quote; parse a unit string; run the convention checker; digitise with a stated axis calibration; run a fit; bake check points; run `materica check` |
| Prompts | the extraction procedures and review checklists (section 8.3), versioned, so any MCP client gets them; the same text ships as agent skills |

- **Tools first, MCP second.** Every tool is first a plain library function, in the core or in L3, and a
  command, usable by a person with no model at all; the MCP server only exposes them. Prototype P4's estimate
  of full provenance by hand (a model's estimate, not a timing) was 36 to 109 minutes per value, well above
  the 15 minutes assumed, and the maintainer chose tooling over deleting fields. So five tools are
  prerequisites of the first library release, in this order: a digitiser with axis calibration and an overlay
  (the witness bottleneck of section 4.6, chosen first by the maintainer); draft templates that mark fields
  "not applicable" by the value's type and record "unstated" in structure; quote attach-and-verify, per copy;
  registry drafting from DOI, Crossref and licence pages; formulation evaluators and check-point bakers. They
  ship in `openmaterica-authoring` (section 7.2). Registry drafting goes online, so the server does not load
  it (below). The MCP server stays a later item (section 12).
- **How the server finds the tools.** A sibling's tools are plain functions registered by entry point, and no
  sibling imports an MCP library; only the server does, so the base install of every distribution stays free
  of MCP dependencies (maintainer, 2026-10-16). The server loads tools from a closed list in the core: the
  core, `openmaterica-authoring` and `openmaterica-families`. The core's own read-side tools, such as getting
  a record or running `materica check`, register through the same entry-point group. An installed package
  outside the list adds no tool, so installing one cannot widen what a model can call (maintainer,
  2026-10-17). A listed sibling that is missing, or built for another core MAJOR.MINOR (section 7.2), is
  skipped with a logged reason (maintainer, 2026-10-16). The group's name is chosen with A9.
- **No network through the server** (maintainer, 2026-10-17). No tool the server loads makes a network
  request. Registry drafting stays a command a person runs, with its explicit flag (section 7.2).
- **Skills** (a proposal). The extraction procedures and checklists would ship as package data. The server
  would expose them as prompts, and a command would export them for clients that read skill files.
- **Capability scoping.** Draft tools write only to a drafts area of the user's working tree. No tool can
  merge, push or open a pull request on its own, set a record's review status, set or change a redistribution
  status, write a check point other than by baking it, or edit a released record. A person opens and
  merges the pull request. An agent that follows instructions injected through a paper can at worst write a
  bad draft, which the rest of the pipeline exists to stop. With the closed list above, this holds for every
  tool the server can load.
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

What the prototypes' agents contributed most was not extraction but flags: contradictions inside a source,
values swapped between rows, implausible spreads, specimen states mislabelled. No deterministic check
produces these. The review checklist asks for them by name, and a pass told to refute a draft, not to
confirm it, is part of the pipeline: in the prototypes, such passes found more than the primary work did.

### 8.4 The query layer

A model turns a question into a structured query, and a deterministic tool answers it. "Acoustic
attenuation in human or porcine liver at 37 °C, 1 to 5 MHz" becomes ontology identifiers and condition
ranges, matched against `index.json`. Ontology hierarchies supply the "semantic" part without embeddings,
which would add another model-dependent, unreproducible step; a local embedding index built from a release
stays an option.

- Tools return values only bundled with their conditions, specimen facts, tier and content hash, so an answer
  cannot lose them unless the agent discards them.
- An optional checker confirms that every number in an answer appears in a tool result.
- The query layer is advisory. A simulation binds a material by identifier and content hash, never by a
  natural-language query.
- It makes no applicability judgements. The prompts say so, and the claim lint applies to anything it
  saves.
- Expanding a query along an ontology (human to mammal; an organ to a part of it) is a proxy inference made
  by the tool. Results say how their specimens differ from the query's target, computed as in section 4.11.
  Ontology classes cannot express disease state either, so a query for fatty liver can return normal
  liver; the result says so.

### 8.5 Traceability and the SOUP boundary

- **Provenance records the assistance** (section 4.7): tool, model and provider as reported, prompt version,
  date. The value's origin does not change: a value read from a source's table has the origin the source gives
  it, whether a person or a model drafted it. A manufacturer can ask which inputs were model-assisted and get
  an exact answer.
- **The evidence does not depend on the model.** The quote, its locator and the SHA-256 of the document
  copy let anyone re-verify a value without any model, after the model is withdrawn. Model outputs are not
  reproducible and need not be.
- **Accountability is human.** The review record names who checked what against a checklist: value, unit,
  conditions, statistic, primary or cited, family and witness.
- **The release fails closed.** `materica check --release` refuses any value without a review record.
  Drafts may exist in a working tree; they cannot enter a release.
- **The curation tools in `openmaterica-authoring` are curation tooling, outside the SOUP package**, like the
  CI scripts.
- **The MCP server is part of the core's assessed wheel** (maintainer, 2026-10-17). The SOUP package lists it
  as present, imported by no reader, check or consumer's build, and never run at a consumer's build: it runs
  only with the `[mcp]` extra. A test, built with the server (A9), is to enforce that import boundary.
- **Their use is curation.** Every value the server and the curation tools help draft is independently
  verified before release, which is the usual argument for light validation of a tool used in a quality system
  (recalled: ISO 13485:2016 clause 4.1.6). OpenMaterica operates under no QMS, but a manufacturer reasoning
  about it will look for exactly this argument. The SOUP package states how many library values were
  model-assisted and which procedure versions drafted them (`DOCUMENTATION_ARCHITECTURE.md` section 10).

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
| Query answers with numbers not from tools, or without their conditions and specimen facts | bundled tool outputs; the number checker; binding only by identifier and hash |
| A sibling's tools run against a core of another minor version, whose records and checks they do not know | the sibling refuses to import against another core MAJOR.MINOR, and the server skips it with a logged reason (sections 7.2 and 8.2) |
| An installed package registers tools that widen what a model can call | the server loads tools only from a closed list in the core (section 8.2) |
| A tool exposed to an agent reaches the network, or the server listens on a socket | no tool the server loads makes a network request, and registry drafting stays a person's command; stdio only (sections 8.1 and 8.2) |

## 9. Interface with MIME

### 9.1 Where it attaches

MIME depends on the OpenMaterica core (with the `[usd]` and `[sample]` extras) and the families it uses. The
adapter lives in MIME, beside the things of structure draft 4.1. OpenMaterica knows nothing of nodes, graphs
or JAX.

```
USD stage (or plain records): geometry + bindings + OpenMaterica materials     (OpenMaterica L0, L1, L4)
    -> MIME things: Body, Medium, Apparatus                       plain views of prims and records
    -> each effect or observation model declares required properties (section, field or family, unit,
       conditions and tolerances), its domain, its target and its picks (mixing rule, competing values)
    -> Experiment.build(): requirements checked over each domain (met, not met, unknown; waivers recorded);
       volume fractions inside each node's domain (OpenMaterica L5 for label volumes; MIME's own for meshes
       and moving bodies);
       MIME's JAX evaluators of value forms and model families, verified against the conformance cases
       and each record's check points;
       the declared mixing rules, written by MIME in JAX
    -> gm.params (differentiable) or static data (scope doc class P3)
    -> the material input sheet, with the derivation of every node parameter, written onto the stage
       beside MADDENING's graph and into the run's provenance
```

### 9.2 What changes in MIME

| Structure draft | Change |
|---|---|
| 4.1 Things | bodies and media hold OpenMaterica materials; apparatus may hold material records from MIME's own namespace (a coil's copper, a detector's scintillator), since an apparatus's materials are outside the curated scope (section 1) |
| 4.2, 4.3 Models | required properties become typed: section, field or family, unit, conditions and tolerances, declared with a domain and a target; results are met, not met or unknown; replaces presence-only checks (scope doc H1) |
| 5.1 Build order | a step after the things: resolve materials, verify check points, check required properties over each model's domain, compute validity. The structure draft lists the property check as step 1, before the things exist; it belongs after them |
| 5.5 Saved form (scope doc D2) | the stage holds things and materials; the experiment file holds models, controller and run settings |
| 8 Metadata | provenance moves to the material; biocompatibility is declared on the `Body`, citing its materials' test evidence (section 4.2); open question 8.8 is answered by one record; `MimeAssetSchema` refers to materials by identifier |
| 3.8, 3.10 New nodes | OpenMaterica is a prerequisite for every new family: acoustics, X-ray, transport, photoacoustics |
| 7.4 N3 | shared parameters become more pressing (9.3); MADDENING has taken this up as O.2, second in its 0.5.0 order |

### 9.3 Differentiability

The split that keeps gradients:

- **Which material is where** is geometry. OpenMaterica L5 computes volume fractions from label volumes on a
  node's grid once (static data); MIME computes them for meshes, and for a moving body recomputes them per
  frame from a soft distance function in JAX, as for the X-ray rung (structure draft 3.9). Soft fractions are
  MIME's discretisation at an edge: declared, and tested for convergence (section 3.5, rule 3).
- **What the material's values are** become MIME parameters. A node's property field is the mixing rule
  applied to fractions and values, in JAX, in MIME's own code. Model-family parameters go through MIME's own
  JAX implementation of the family.

So gradients reach material values (fitting an absorption map, a sound-speed map, a viscosity, a
hyperelastic parameter set) and, for moving bodies, poses, in every node that takes the value as a parameter.
MIME's finite-volume node does not yet: it takes viscosity through a static configuration, so no gradient
reaches it today (structure draft 3.7). Prototype P5 measured what the rest takes:

- **Mix in the step whenever values or poses are differentiated.** Mixed in the step, gradients with respect
  to region values were exact and those with respect to a moving body's pose agreed with finite differences.
  A field baked at build from the initial pose had a gradient of exactly zero, and nothing warned.
- **A soft fraction needs a form that keeps its precision in the tail.** Written as `0.5 (1 + tanh x)` it lost
  relative precision on rays that barely touch a body, and the pre-registered check failed; the equivalent
  logistic form passed when tried after the run. Derivative checks on soft fields use an absolute floor as
  well as a relative tolerance.
- **One material value usually feeds several nodes.** MADDENING cannot yet tie a parameter across nodes
  (its O.2, structure draft N3): two copies fitted together drifted 2.88 % apart in ten steps, and nothing
  flagged it. Until the tie exists, MIME feeds one value to every node that reads it from a single adapter
  node, which kept the readers identical through a fit when tried after the run, and holds no constant copies
  elsewhere.

### 9.4 Uncertainty

MIME maps a record's statistics and uncertainty structure into MADDENING's UQ types, choosing the spread its
question needs (section 4.9). MADDENING's `UncertainParameter` describes one parameter at a time, with a
nominal value, bounds and a distribution that defaults to uniform, and has no standard deviation
(`MADD:src/maddening/core/compliance/uq.py`, read at `f2aa830e`). So:

- a mean and a standard deviation cannot be carried as they stand. Turning them into the bounds of a
  uniform distribution would invent a distribution. MIME asks MADDENING for a stated parameterisation per
  distribution and a record of what each spread represents;
- an interval-only value has no nominal, so it goes to a sweep over its bounds, not to UQ, unless MIME
  declares a nominal itself;
- joint distributions (a covariance in the space its record states, an ensemble, admissibility constraints)
  have been requested of MADDENING for a later release. Until then MIME samples `ensemble` and
  `multivariate_normal` structures with OpenMaterica's reference sampler and labels the results as such
  (section 7.3), or uses values it declares.

### 9.5 Round trip

A MIME fit writes its results as an overlay scoped to the field, the MIME model and its version, and the
run (section 5.5), with check points from the family's reference implementation and a covariance where the
fit produces one. It is MIME's calibration of that model, not the material's value. The library's values
stay as they were, and another model, including another MIME model, uses the overlay only by declaring it.

### 9.6 Validity

MIME computes operating points from material values and the run: Reynolds number, acoustic Mach number, the
diffusion approximation's condition for light. That is structure draft 8.5's "one validity declaration,
checked against a computed operating point". A fitted parameter set adds its coverage (section 4.10), which
MIME checks its operating point against. Coverage is never mapped onto MADDENING's `ValidatedRegime`, whose
docstring reads "within which the node has been verified": a fit's range is not a verified regime.
Quantities that change during a run (a Reynolds number from a velocity, heating) are watched by runtime
monitors, which mark the results; they cannot be refused at build.

A condition that an optimiser moves is one of them, and the watch sits on the condition, not only on the
value derived from it; a model-validity guard on the value itself (MIME's finite-volume node bounds its own
viscosity) stays. In prototype P5 a fit moved water's temperature out of its table's range at the third step;
the clamped evaluator then gave a zero gradient, and the fit stalled silently for 197 steps. Re-running the
build's check after each step, an in-range flag from the adapter node, and bounds declared on the temperature
all caught it at the third step. A bound on the viscosity never fired, because the clamp kept the viscosity
inside the table, and a transform that keeps the temperature in range only turned the problem into a stall
at the table's edge. So MIME's evaluators return their in-range result (section 4.4), and its monitors read
it. MADDENING has agreed that MIME builds such monitors first and that it generalises from them later.

### 9.7 Beside MADDENING and MICROROBOTICA

- MADDENING's USD live stage and graph schema describe the simulation; OpenMaterica describes the scene's
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
  - a convention checker: given parameters and a claimed convention, report every family version that
    reproduces a reference curve, and say when the data cannot tell them apart (conventions that differ
    only in their volumetric terms look alike on incompressible uniaxial data; recalled).
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
- **Criteria.** For example, within a year of the library's first release: two consumers outside the founding
  projects, a stated number of curated materials, and one outside contributor or publisher. Measured from
  Zenodo, PyPI and GitHub release downloads and, once it exists, the index. If they are not met, OpenMaterica
  narrows to an internal tool, which is still worth having.

An earlier materials-data exchange format, MatML, went from NIST to an OASIS technical committee in
2003-2004; the committee is listed as completed. How widely it was adopted is still unknown. What a literature
review of October 2026 found about adoption: the standards that spread gave authors a validator through a
gatekeeper already in their path (ThermoML through journals and NIST's data centre; STRENDA DB before
publication); importers are maintained products, which took NOMAD some ten to twenty person-years; and domain
experts contributed to dictionaries rather than to data models (ISO 13399). The only reasons given in primary
sources for stalled efforts were that barrier and a general lack of incentive and tools.

## 11. Interface with Isaac for Healthcare

None of this exists or has been proposed to them. Each row is a possible adapter, in the order I would try
them.

| Their component | Today | OpenMaterica touchpoint | Adapter |
|---|---|---|---|
| Ultrasound simulator | six materials hard-coded in C++ | fill its material table from records | a build-time generator in `openmaterica-authoring` that writes a drop-in `material.cpp`; their Python API cannot replace the table, so a change of materials needs a rebuild (prototype P2, at their commit `8bb07d9`; their own values round-tripped bit for bit, a test that covers 12 of the table's 48 fields) |
| Patient twin | CT to labels to meshes and USD, no properties | a step that binds a library material to each label | a label crosswalk from their label names to library materials, plus a binding function that applies `MatericaRegionAPI`, with the material reference and a priority, and a `materica`-purpose binding beside their all-purpose display binding. They identify a structure by the segmenter's name (`anatomy:name`), not its path, and attach CT in millimetre stages (read at their commit `9a779a4` by the ecosystem survey, 2026-10-12) |
| X-ray simulator | linear map from CT number to attenuation | per-material attenuation from a label volume, computed by the adapter for a stated spectrum (an effective value depends on path length and filtration, so it is the adapter's model, labelled) | builds an attenuation volume; their renderer takes one in mm⁻¹, mapped from CT number, and models no tube voltage, spectrum or filtration (their preset documentation, read by the ecosystem survey, 2026-10-12; not run) |
| Physics (Newton, the XPBD catheter, soft tissue) | engine materials | mechanical families to engine parameters; interfaces (4.13) for catheter-wall friction | the engine adapter, by an engine crosswalk the consumer writes (OpenMaterica ships only `UsdPhysics`'s), writing engine materials of its own bound `physics` (5.4); position-based solvers use compliance, which depends on the discretisation, so it is a declared engine value, not a conversion |
| Workflows and scenes | USD scenes | scenes reference library layers | none: plain USD composition |

### 11.1 The ultrasound adapter in more detail

- Their `Material(impedance, attenuation, speed_of_sound, mu0, mu1, sigma, specularity)` computes density as
  impedance times 1e6 over sound speed (`material.cpp:36-38`). Their header documents impedance in MRayl,
  attenuation in dB/(cm⋅MHz) and sound speed in m/s (`material.hpp`, same commit; found by the ecosystem
  survey and checked against prototype P2's copy of the header, 2026-10-12; an earlier draft inferred the
  attenuation unit from the values), and calls `mu0` a scattering density and `sigma` a scattering
  coefficient, which bears on open question 5 of section 13.
- From OpenMaterica's bulk and acoustic sections: impedance as density times sound speed, sound speed
  directly, attenuation converted from SI to their units. A unit linear in frequency (dB per cm per MHz)
  assumes attenuation is linear in frequency, which holds only approximately for tissue and not at all for
  water (recalled: water's rises with the square of frequency), so each converted value carries a label
  with its error over the band used.
- Their four speckle parameters are treated as renderer settings until a first contact settles what they
  describe (section 4.14). As settings, they would sit on the same material prim in their own namespace (for
  example `i4h:ultrasound:mu0`), outside OpenMaterica's schema.

### 11.2 Why this could interest them

- One patient twin would feed their ultrasound, X-ray and physics simulators, and other people's solvers.
- It is framework-neutral, Apache-2.0, and competes with nothing of theirs.
- The first adapter changes none of their logic: it generates a replacement for the one file that holds
  the table, which their build then compiles. Changing materials still needs their rebuild.

I would rank this above the physics bridges of structure draft 7.7 as a first contribution.

### 11.3 Caveats

- NVIDIA's schemas were surveyed on 2026-10-12, with citations, in a private report. SimReady's non-visual
  sensor materials are category tokens with no quantities, carried on visual materials, and `skin` is their
  only tissue. PhysX's deformable materials are being replaced by a deformable schema written to become part
  of `UsdPhysics`, in stage units. Neither carries what OpenMaterica does, so OpenMaterica stays compatible
  with both and maps onto them through adapters, and leaves them the `physics` binding slot (5.4). The
  Alliance for OpenUSD's Physics working group has physical material properties in its charter, deformable
  bodies after rigid ones; an engine-facing tissue material would be standardised there, so it is worth
  following.
- A standard succeeds by adoption. Round-tripping their patient twin's output matters more than a complete
  schema.

## 12. Phasing for MIME 0.3.0 (proposal)

MIME is the first consumer, so its 0.3.0 release sets the order. **Direction (maintainer, 2026-10-11):** aim
between the realistic and ambitious sets below. Anything that touches MIME is first proven by a spike (section
12.3), while MIME waits for MADDENING 0.4.0's release, so that MIME 0.3.0 work starts from results rather than
proposals. The cut in section 12.2 was my proposal; the maintainer then moved R1 and R14 into 0.1, with
nothing to slip (2026-10-12). The rows and spikes were revised on 2026-10-12 after the review of section 15.

Each feature names what it serves, as document, section number and *heading*:

- **AD**: this architecture draft;
- **DA**: `DOCUMENTATION_ARCHITECTURE.md`;
- **SD**: the structure draft, MIME's private 0.3.0 planning document;
- **RS**: the scope doc, MIME's private refactor scope.

### 12.1 Three sets

Each set includes the one before it. A MIME row is done first as the spike named in brackets.

**Minimal: MIME's things hold materials, and no result changes.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| M1 | Plain records and their JSON Schema, JSON only: the envelope every record shares, with `record_type` (material and overlay defined, interface reserved; unknown types skipped when listing and refused when referenced) and an `extensions` block; namespaced identifiers; a schema version; content hashes over the whole record minus a stated exclusion list, with hash test vectors | OpenMaterica | AD 4.1 *Material, section, value*; AD 5.2 *Plain records and scene documents*; AD 5.6 *Versions and hashes* |
| M2 | Sections for what MIME's experiments use today: bulk (density, elemental composition), fluid (viscosity with its trivial family and shear-rate range), magnetic (remanence, saturation, susceptibility, with the specimen's shape), biocompatibility (test evidence, never a device's status) | OpenMaterica | AD 4.2 *Sections*; AD 4.8 *Conditions*; SD 8.4 *Where each piece would go* (the `BiocompatibilityMeta` row) |
| M3 | Five value forms: constant, table, power law, interval and composition, each with its range; tables with an interpolation scheme and edges; attenuation stored as an amplitude coefficient. No model families yet | OpenMaterica | AD 4.4 *Seven value forms* |
| M4 | Provenance per value (origin, source, extraction, review with the reviewer's independence); conditions, starting with temperature, with unstated conditions recorded as such; scalar statistics with what they represent, `not_reported` and interval-only values; specimen facts | OpenMaterica | AD 4.7 *Provenance*; AD 4.8 *Conditions*; AD 4.9 *Statistics and uncertainty structures*; AD 4.11 *Proxies*; SD 8.3 *Principle: metadata sits on what it describes* |
| M5 | A deterministic reader for plain records: a value in SI, with its provenance, at stated conditions. A refusal comes back as a structured result, never as a guess: no value that was not authored, nothing outside a range or across an edge, no nominal for an interval | OpenMaterica | AD 3.2 *Layers inside the core* (L2, L4); AD 7.5 *The read side in another language*; DA 15 *Project Constraints* (nos. 13, 24) |
| M6 | Required properties as a type (section, field, unit, conditions with tolerances), declared with a domain and a target; a check over the domain's regions with three results (met, not met, unknown) and recorded waivers | OpenMaterica | AD 3.5 *Facts, declarations and the build*; AD 9.1 *Where it attaches*; SD 5.1 *Build order*; RS H1 *What the layer does today* (presence-only checks) |
| M7 | Conformance cases as data files | OpenMaterica | AD 7.4 *Conformance*; DA 6.1 *Conformance suite (the read side)* |
| M8 | `materica check`: schema, provenance, plausibility | OpenMaterica | DA 6.5 *CI checks* |
| M9 | A seed library from primary sources (water as a table over temperature, evaluated from its reference formulation; SU-8, NdFeB grades, the tube materials); its source registry, per copy; the data licence (CC0-1.0, decided). MIME's current constants are not transcribed into it: they stay inline in MIME (M11) | library | AD 6.1 *Source registry*; AD 6.2 *Three tiers*; AD 6.4 *Licences*; AD 13 *Open questions* (no. 8) |
| M10 | Tagged releases of the packages, each from tags of its own prefix, with the explainer release `openmaterica-families` 0.1.0 (section 7.2), and tags of the library that MIME pins exactly: unpublished pins for MIME's spikes, not the first library release (R8; section 6.7) | OpenMaterica | AD 6.7 *Distribution and hosting*; AD 7.2 *Dependencies and distribution*; DA 7.1 *Four version lines* |
| M11 | The seam: `Body` and `Medium` hold a material reference (identifier and hash) or an inline value labelled "declared in the experiment", with the origin "stated without an origin"; an adapter resolves either into what the nodes take today | MIME (S1) | SD 4.1 *Things*; AD 9.2 *What changes in MIME*; AD 4.7 *Provenance* |
| M12 | Migration control: experiments built through the seam, from inline values, reproduce today's outputs exactly. Library values then replace inline ones one at a time, each a separate change with its measured effect | MIME (S1) | SD 8.2 *What is wrong with it* (point 4); RS *TODO: what it takes* (item 56, "results reproduce") |

**Realistic: MIME 0.3.0's new nodes and its saved form use it.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| R1 | Scene documents in plain form (the scene manifest, regions, domains) and the USD binding: schemas for the sections in use, read and write, with no fallback values on physical attributes; region binding; domains as collections; overlays; self-contained shipped layers; the stage check (`materica check --stage`); the engine crosswalk, with OpenMaterica's one crosswalk (OpenUSD's `UsdPhysics` rigid materials) and a scaffold for consumers' crosswalks; the engine adapter. Crosswalks for Isaac Sim's deformable materials, Newton or any other engine are their consumers' (maintainer, 2026-10-13), and each needs a source for its engine's units. Built in 0.1 (section 12.2) | OpenMaterica | AD 5.1 *The geometry ladder*; AD 5.3 *USD schemas*; AD 5.4 *Materials and binding in USD*; DA 15 *Project Constraints* (no. 18) |
| R2 | Acoustic section (longitudinal and, for solids, shear sound speed, with propagation direction where the material is anisotropic; attenuation as an amplitude coefficient, a power law over a stated band with its exponent's basis, for each wave type, so shear attenuation too; B/A), for both body and medium; density from the bulk section | OpenMaterica | AD 4.2 *Sections*; SD 3.5 *Acoustics with MIME's own kernels (decided)*; SD 3.8 *Nodes planned for 0.3.0* (row 6) |
| R3 | Radiological section: mass attenuation against photon energy, interpolated log-log, with its absorption edges declared, derived where needed from the bulk section's composition; the spectral axis built generally, so that the optical section adds fields later; the consumer computes any effective value for its own spectrum; seed materials water, soft tissue, bone, NdFeB and iodine, from a public-domain table (recalled: NIST's; terms to check) | OpenMaterica, library | AD 4.2 *Sections*; AD 4.4 *Seven value forms*; SD 3.8 *Nodes planned for 0.3.0* (rows 7, 8); SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks* |
| R4 | Mixing rules specified: the identities fixed, named rules with their assumptions, numpy reference forms and conformance cases at a single cell; the consumer implements its pick and the pick is recorded | OpenMaterica | AD 4.12 *Mixing rules*; AD 3.5 *Facts, declarations and the build*; AD 9.3 *Differentiability* |
| R5 | The family machinery, with both kinds: static, and evolution with state and history and optional events (section 4.5), shipped as `openmaterica-families` with each reference implementation beside its family. The first family, `materica.magnetic.langevin.v1`, with golden vectors, a reference implementation and check points that span its branch points; its named consumer is MIME's superparamagnetic response node. Its first parameter set is a substance record: the composite of the Landers capsule, measured as a sphere, with the sphere as a condition (section 1). It enters `materica` only with an independent witness (the preprint's full magnetisation curve, digitised, can supply one); otherwise it goes to MIME's namespace flagged "no independent witness", and the family lives in `mime.` until an in-scope record uses it (sections 4.5, 6.7). The capsule's own as-built quantities stay MIME's. Rate-dependent families follow as soon as a consumer names one. The importer of section 12.5 exercises the same machinery on mechanics families and real papers | OpenMaterica | AD 4.5 *Model families*; AD 4.6 *Check points and convention witnesses*; AD 6.7 *Distribution and hosting*; AD 7.6 *Scope rules*; SD 3.8 *Nodes planned for 0.3.0* (the eMNS pair) |
| R6 | Uncertainty structures, each saying what it represents, and the reference sampler. MIME maps the spread its question needs onto MADDENING's UQ types where they can carry it; a mean and a standard deviation need a MADDENING change (section 9.4) | OpenMaterica, MIME (S5) | AD 4.9 *Statistics and uncertainty structures*; AD 7.3 *Uncertainty and sampling*; AD 9.4 *Uncertainty* |
| R7 | `materica.compliance`: `collect_material_inputs` and the material input sheet, written into each MIME run's provenance, with the derivation chain of every node parameter, review status, and the consumer's declarations, picks and waivers | OpenMaterica, MIME (S5) | DA 9.1 *Where it fits*; DA 9.3 *What this would add to OpenMaterica*; AD 3.5 *Facts, declarations and the build* |
| R8 | Material cards; the legal review; the library's first archived release, with a DOI | library | AD 6.5 *Process*; AD 6.6 *Material cards*; AD 6.7 *Distribution and hosting* |
| R9 | The interface record's body: contact pairs apart from solutes in media; how an interface binds to a pair of regions (manifest and USD); members named by identifier and major version. Design only; records ship with A6 and A7 | OpenMaterica | AD 4.13 *Interfaces between materials*; AD 13 *Open questions* (no. 11); SD 3.8 *Nodes planned for 0.3.0* (row 9); SD 9 *Open decisions* (no. 10) |
| R10 | Typed required properties on MIME's effect and observation models, with domains, targets and tolerances, checked at build against the records and a computed operating point; unknown refused unless waived | MIME (S2) | SD 8.5 *One validity declaration, checked against a computed operating point*; AD 3.5 *Facts, declarations and the build*; AD 9.6 *Validity*; RS H1 *What the layer does today* |
| R11 | MIME's JAX evaluators of value forms, mixing rules and the Langevin family, with gradients through tables and mixing rules, each stating its derivative convention at table knots and ends and returning whether its condition is in range, tested against OpenMaterica's conformance cases and golden vectors in MIME's default test lane | MIME (S3) | AD 9.3 *Differentiability*; AD 7.6 *Scope rules* (consumers write their own evaluators); DA 6.1 *Conformance suite (the read side)* |
| R12 | Inputs derived where nothing better exists, with each derivation recorded: a magnet's dipole moment from remanence and volume, and, where the moment was also measured on the magnet, both kept as competing values with MIME's pick recorded; a density difference from two materials; a composite body's mass and buoyancy from its regions' materials, not its inertia or centre of mass. Biocompatibility is not derived: a device's status is declared on the `Body` | MIME (S6) | SD 8.2 *What is wrong with it* (point 1); SD 8.4 *Where each piece would go*; AD 4.2 *Sections* (biocompatibility); AD 4.3 *Laws, tables and composition* |
| R13 | The saved form on a USD stage: MIME's things and OpenMaterica's layers composed with MADDENING's graph | MIME (S4) | RS *TODO: what it takes* (decision D2); RS H5 *The `Experiment`: what stays, what moves, where the other sides attach (a proposal)*; SD 5.5 *The saved form*; AD 9.7 *Beside MADDENING and MICROROBOTICA* |
| R14 | Layered paths: the plain form and the USD typed prim `MatericaLayeredPath`; the L5 helper that derives one from 3-D geometry along a trajectory. Needed by MIME 0.3.0's imaging physics, acoustics and X-ray (maintainer, 2026-10-12). Built in 0.1, with R1 | OpenMaterica | AD 5.1 *The geometry ladder*; AD 5.4 *Materials and binding in USD*; SD 3.8 *Nodes planned for 0.3.0* (rows 6 to 8) |
| R15 | The curation tools, before the first library release (R8), in `openmaterica-authoring`: a digitiser with axis calibration and an overlay first; then draft templates by value type; quote attach-and-verify per copy; registry drafting; formulation evaluators and check-point bakers. Library functions and commands first; the MCP server later (A9) | OpenMaterica | AD 8.2 *The deterministic toolset*; AD 4.6 *Check points and convention witnesses* (the witness bottleneck); AD 6.1 *Source registry* |

**Ambitious: images from materials, fits written back, and the pair properties.**

| # | Feature | Where | Ties to |
|---|---|---|---|
| A1 | Label volumes, and field overrides that carry provenance like any value | OpenMaterica | AD 5.1 *The geometry ladder*; SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks* (the voxel-grid source of attenuation) |
| A2 | Sampling helpers (L5): volume fractions from label volumes inside a node's domain, and the analytic fractions of the canonical test phantoms as conformance data. MIME's soft-distance fractions for meshes and moving bodies, its declared discretisation, are checked against them | OpenMaterica, MIME (S7) | AD 3.2 *Layers inside the core* (L5); AD 9.3 *Differentiability*; AD 13 *Open questions* (no. 10) |
| A3 | Joint uncertainty structures used in MIME's UQ through the reference sampler, before MADDENING supports them, with the results labelled | MIME (S5) | AD 9.4 *Uncertainty*; AD 4.9 *Statistics and uncertainty structures*; AD 7.3 *Uncertainty and sampling* |
| A4 | Fit write-back: a MIME fit stored as an overlay scoped to its field, the MIME model and the run, with check points and a covariance, published in MIME's namespace; never the material's value | OpenMaterica, MIME (S8) | AD 4.10 *Fits and reference data*; AD 5.5 *Declared, then fitted*; AD 6.7 *Distribution and hosting*; AD 9.5 *Round trip* |
| A5 | X-ray from materials: the analytic and ray-marched rungs take mass attenuation against energy from records and a stated spectrum, polychromatically, with gradients to pose and to attenuation values | MIME (S7) | SD 3.8 *Nodes planned for 0.3.0* (rows 7, 8); SD 3.9 *The ray-marched X-ray projector: what it is and what it unlocks*; AD 4.4 *Seven value forms* |
| A6 | Interface records for friction | OpenMaterica | AD 4.13 *Interfaces between materials*; SD 3.8 *Nodes planned for 0.3.0* (existing nodes: surface contact, the contact-friction stub) |
| A7 | Transport records: a species' diffusivity in a medium; contrast agents | OpenMaterica | SD 3.8 *Nodes planned for 0.3.0* (row 9); AD A.4 *Prerequisites, in order* (item 2) |
| A8 | Optical and thermal sections, for photoacoustics' cheap rungs: optical fields added to the radiological section's spectral machinery, optical composition by named component added to the bulk section, without breaking the schema | OpenMaterica | AD 4.2 *Sections*; AD 5.6 *Versions and hashes*; AD A.3 *A fidelity ladder (proposal)*; AD A.4 *Prerequisites, in order* (item 1) |
| A9 | The MCP server, the extraction prompts and the gold set | OpenMaterica (`openmaterica[mcp]`) | AD 8 *Layer 6: MCP tooling and curation* |
| A10 | Anisotropic solids: a linear elastic family with a declared symmetry class, its constants in Voigt form in the material's principal axes; orientation fields for axes that vary in space; bone as its first material. Its consumer is MIME's acoustics through bone; stretch (maintainer, 2026-10-12). Measured speeds with their propagation direction come earlier, with R2 | OpenMaterica, library | AD 4.2 *Sections* (anisotropic solids); AD 4.5 *Model families*; AD 5.1 *The geometry ladder* (orientation) |

Not in any set, for want of a MIME consumer (section 7.6): the dielectric section and a non-Newtonian blood
family. The evolution form of families is part of R5, so that a rate-dependent family can be admitted as soon
as a consumer names one. Mechanics, with failure, has a consumer of its own and its own track (section 12.2).

### 12.2 The target and the release order

**Proposed cut:** all of minimal and realistic, and A1 to A5 from ambitious. Each of A1 to A5 serves a node
MIME 0.3.0 plans (the X-ray rungs) or MIME's rule that a declared value stays a declaration until something
fits it (section 5.5). A6 to A9 are stretch: none of them blocks a 0.3.0 node.

**Floor:** the minimal set. Because the seam (M11) also accepts inline values, MIME 0.3.0 never waits for
OpenMaterica; an experiment whose materials are not ready keeps declaring its values inline.

**USD and layered paths in 0.1** (maintainer, 2026-10-12). The core read path depends on scenes (a read's
target can be a region, and requirements are checked over a domain or a path), so the code is designed with
them from the start. 0.1 is built in this order: plain records, the reader and the hash; record checks; plain
scene documents (regions, domains, layered paths with the L5 helper, label crosswalks); declarations and build
checks; the USD binding, the stage check, the engine crosswalk and the engine adapter. Scenes come before
declarations because the build checks requirements over domains and paths (maintainer, 2026-10-13, reordering
the 2026-10-12 order). Nothing slips: the maintainer ruled out a cut line. USD is how MIME saves scenes and
how the patient twin of Isaac for Healthcare would carry OpenMaterica materials; its novel parts (the
layered-path prim, overlay prims, region markers, binding refusals, the units rules, engine materials) are
found only by implementing them. The material input sheet stays R7, in 0.2. Label volumes, field overrides and
the label crosswalk's USD form stay with A1.

| OpenMaterica | Set | Contents | Proven in MIME by | Consumers |
|---|---|---|---|---|
| 0.1 | minimal, and R1 and R14 | M1 to M10, R1 and R14 | S1 and S4 | the MIME spikes |
| 0.2 | realistic | R2 to R9 and R15 | S2, S3, S5, S6 | MIME 0.3.0: the release it is expected to pin |
| 0.3 | target | A1, A2 and A4 (the OpenMaterica side) | S7, S8 | MIME 0.3.0 if ready when its work starts; otherwise a later MIME minor release |
| 0.4 | stretch | A6 to A10; the first exporters; the convention checker | none needed | photoacoustics in MIME (Appendix A); curators; contact |
| with 0.2 | the mechanics track: not a priority, but progressing | mechanics with isotropic linear elasticity (A10 adds the anisotropic form), one hyperelastic family and rate-dependent families as that track's consumer needs them; failure properties and failure criteria, static or with events; the importer from an existing per-paper calibration code base, as the design's acceptance test (section 12.5) | none needed | that code base |
| with a consumer | | the optical, thermal and dielectric sections, added without breaking the schema (section 5.6); further families, of either kind | | |
| with a consumer | transcranial focused ultrasound, for microrobotics in the brain (maintainer, 2026-10-12; not scheduled) | acoustic properties of skull bone as tables over porosity (substance data); the scanner's calibration from CT number to density as a system record in the consumer's namespace; the patient's property map as a field override (A1) carrying that calibration as provenance; shear attenuation (R2); the thermal section, since skull heating is usually the binding safety limit (recalled); anisotropy (A10) after these. On MIME's side it needs an elastic-wave solver | | MIME |
| beside 0.2 or 0.3 | | the ultrasound adapter and the label crosswalk for the patient twin. Its library values are sourced records, with the extrapolations outside their measured bands declared and labelled (section 3.5); a local copy of Isaac for Healthcare's own six materials, never published, serves as the adapter's test oracle, from the integration testing at the end of 0.1 (maintainer, 2026-10-12) | | Isaac for Healthcare, if they want it |

A spike runs against the release that carries its features, before the next set starts, and a failed spike
changes the next release's contents. Nothing here is sized. The publishers file and the template
repository come with the first library release; the other hosting items (a data wheel, a viewer) follow
their triggers in section 6.7. The prototypes of section 12.5 come before all of it.

### 12.3 MIME spikes

The spikes live in the maintainer's private planning directory, as the Warp spike before them did. They import MIME without changing it
and run on MADDENING `release/0.4.0`. Each records its result in a README; the experiments each uses are named
in SD 4.1 *Things*. Each has a control: a run that must come out differently if the spike's claim is false.
The controls were rewritten on 2026-10-12, because several of the first set could not fail (section 15).

| Spike | Does | Passes when | Control | Features |
|---|---|---|---|---|
| S1 Seam and migration | resolves inline values, declared in the experiment, through the seam into today's node parameters, for two experiments that run on MADDENING 0.4.0 | outputs are bitwise equal to today's, at the same precision settings | a reach matrix: perturb each resolved field in turn, and assert that every node parameter that should depend on it changes and nothing else does; viscosity at least, since it enters drag in every backend. It also finds values that still come from node constructor defaults and bypass the seam. Density is not a usable control: with a Stokeslet backend it reaches no node, and in umr's lattice-Boltzmann setup it only rescales the time step at umr's operating point, where the body sits at its angular-velocity clamp for the whole run; beyond the clamp its effect is untested | M11, M12 |
| S2 Requirements and validity | typed requirements with domains, targets and tolerances for the drag, magnetic and gravity effects, and for the planned radiation-force node (acoustic sections of body and medium) | the build refuses a missing field, a wrong unit and a temperature outside a table's range; returns unknown for an unstated condition and refuses it unless waived, recording the waiver; a valid experiment builds the same graph as S1 | two materials with every field present, one measured at the wrong temperature and one whose temperature is unstated. A presence-only check passes both; the typed check must refuse the first and return unknown for the second | M6, R10 |
| S3 Differentiable evaluation | runs MIME's JAX evaluators against the conformance cases and the Langevin vectors and check points, in float32 and float64; takes gradients through a table's interpolation and a mixing rule | agreement within the tolerances the cases state; gradients match finite differences, with the derivative convention at table knots and ends that the conformance cases state | on the read side, a MIME evaluator with a deliberately wrong convention (the field in millitesla, not tesla) must fail the check points. On the write side, a parameter set extracted in the wrong convention passes its own check points, as section 4.6 says, and must fail its independent witness or be reported "no independent witness" | R4, R5, R11 |
| S4 Saved form on USD | writes a stage with things, OpenMaterica layers, domains and MADDENING's graph; reloads and builds | `gm.to_dict()`, every material hash and every declaration are equal after the round trip, with a value other than the default in every field type | delete one authored attribute: the build must refuse, not read a fallback. A library layer with a composition arc is refused | R1, R13 |
| S5 Provenance and UQ | writes the material input sheet into `SimulationProvenance.custom`; maps the spreads MIME's questions need; samples a joint structure with the reference sampler | the sheet's derivation chain explains every node parameter: base record and hash, overlays, conversions, mixing, defaults | compare the sheet with node parameters read independently from the built graph, not with the values the sheet was written from; a node default planted to bypass the seam must show as unexplained | R6, R7, A3 |
| S6 Derived inputs | derives a dipole moment, a density difference and a composite body's mass, and compares each with today's typed value | each derived value matches, or both are kept as competing values and the test fails until a pick is recorded | each typed value is compared with its derivation before anything replaces it; SD 4.1 names two that may not match | R12 |
| S7 X-ray from materials | the analytic and ray-marched rungs, polychromatic, from mass attenuation against energy, a stated spectrum, a label volume and soft-distance fractions | the ray-marched image of a sphere matches the analytic chord, computed polychromatically, to a stated tolerance; gradients to pose and to an attenuation value match finite differences | a series of thicknesses where one effective attenuation must disagree with the polychromatic result: beam hardening shows that an effective value is the consumer's model | A1, A2, A5 |
| S8 Fit write-back | fits a viscosity, or a Langevin field scale, to a trajectory; writes a scoped overlay; reloads | with the same model generating and fitting, the known value is recovered within the fit's stated uncertainty; the overlay's check points pass; the library's value is unchanged | a model-form arm: generate with a wall-corrected model and fit with a free-space one. The fitted value differs from the truth, and any model other than the one that produced the overlay refuses it | A4 |

### 12.4 What MIME needs to rely on it

| Requirement | Ties to |
|---|---|
| Exact pins: package, schema, library release and record hashes. No version ranges until the schema is stable | AD 5.6 *Versions and hashes*; DA 7.1 *Four version lines* |
| A reader whose behaviour is defined by conformance data, not only by its code | AD 7.4 *Conformance*; DA 6.1 *Conformance suite (the read side)* |
| Fail closed, with structured results that MIME can report | DA 15 *Project Constraints* (no. 13) |
| Unknown is never passed: an unstated condition, an attribute nobody authored and a field a model reads without declaring it are reported, and refused unless waived | AD 3.5 *Facts, declarations and the build*; DA 15 *Project Constraints* (no. 24) |
| Every declaration, pick and waiver is recorded in the run's material input sheet | AD 3.5 *Facts, declarations and the build*; DA 9.1 *Where it fits* |
| Advisories on pinned records are reported at build | AD 5.6 *Versions and hashes* |
| No network access and no code execution at build or import; the library comes from the pinned release | DA 15 *Project Constraints* (nos. 11, 19); AD 6.7 *Distribution and hosting* |
| No language model anywhere on MIME's build path | DA 15 *Project Constraints* (no. 20); AD 8.1 *The BYOK boundary* |
| SI in the records. MIME converts to each node's units in its adapter, with tests: some of its nodes run in dimensionless units | DA 15 *Project Constraints* (no. 5) |
| The migration first reproduces today's results exactly (S1); each correction then follows with its measured effect | SD 8.2 *What is wrong with it* (point 4) |
| The comparisons of R11 run in MIME's default test lane. Tests marked `slow` or `gpu` do not run in its CI | DA 6.1 *Conformance suite (the read side)*; AD 7.6 *Scope rules* |

From MADDENING, nothing blocks. Shared parameters across nodes (MADDENING's O.2, second in its 0.5.0 order;
SD 7.4, N3) would replace MIME's single adapter node that feeds one material value to every node that reads
it (section 9.3). Joint uncertainty, and a
stated parameterisation for `UncertainParameter`, are requested for a later release (section 9.4). The anomaly
validator's version field affects only OpenMaterica's own CI (DA 8.1 *Adopted unchanged*).

### 12.5 Prototypes before the package

Added 2026-10-12, from a simplification pass (section 15): the design had been elaborated on paper, and
every problem found so far was found by reading text. Before the package exists, each consumer's critical
path gets the cheapest prototype that could show the design wrong, as a private spike, with hand-written
JSON records and a throwaway reader. What survives shapes OpenMaterica 0.1, and the specification is then
rewritten shorter from it.

| Order | Prototype | Shows | Could show wrong |
|---|---|---|---|
| 1 | MIME, one multi-region stage: a vessel in tissue; the FVM in the lumen's domain; the X-ray projector over the whole scene; OpenMaterica material bindings composed with `maddening.usd`'s graph layers; S1's reach matrix and S2's three-valued checks run here, early | domains, the USD binding, mixing inside a domain, the seam | whether domains and bindings are the right shapes for a real scene |
| 2 | Isaac for Healthcare's ultrasound material table (water, blood, fat, liver, muscle, bone), built offline from records and compared with their hard-coded values | the acoustic section; derivations such as attenuation in dB per cm per MHz, which assumes attenuation linear in frequency | whether the standard serves its first outside consumer without a change on their side |
| 3 | The importer: an existing per-paper calibration code base's parameter sets as records with one mechanics family; a differential test of the original code against the reference implementation; witnesses on real papers | families, check points, independent witnesses, provenance on real data | whether the family machinery survives real conventions |
| 4 | Five records with full provenance (water, an NdFeB grade from a datasheet, SU-8, a tissue acoustic value from a paper, the Landers capsule with both fits), with the cost of curation per value estimated. As run: model-assisted drafts, and a model's estimate of the time a person would take, not a timing | the cost of curation per value | whether one maintainer can afford the provenance schema; the trigger for the MCP layer (section 8) |

Fields that are always unstated, or never filled, in prototypes 3 and 4 are candidates for deletion.

All four ran on 2026-10-11 and 12, with a fifth on differentiable use in MIME (P5). Each was pre-registered,
and each pre-registration was reviewed by a pass told to break it; of the results, only P2's had a reviewer
told to refute them. No field was deleted: the fields P4 flagged depend on the value's type,
and "unstated" turned out to be information, so the maintainer chose type-dependent templates and tooling
instead (section 8.2). This revision carries the rest of what they found (section 15).

## 13. Open questions

The 22 questions of the earlier drafts were answered on 2026-10-12 by the maintainer, after the prototypes.
Each answer is written into the section named.

| # | Question | Answer |
|---|---|---|
| 1 | Source of truth for library materials | plain records; USD generated from them (3.4) |
| 2 | Binding purpose | a purpose of our own, `materica`, with `physics` left to engines; readers take only a `materica`-purpose binding authored on the region's prim; an engine adapter writes engine materials from a declared engine model, by a pinned engine crosswalk (OpenMaterica's for `UsdPhysics`, the consumer's for any other engine), stamped with their reads; the stage check re-derives them per shape (5.4). Reversed on 2026-10-12 from reusing `physics`, after the ecosystem survey |
| 3 | The USD form of a layered path | a typed prim of our own, with one relationship to its distinct materials and an index per interval (USD removes repeated targets), specified now because MIME 0.3.0's acoustics and X-ray need it (5.1, 5.4) |
| 4 | Family registry scope | families only for a named consumer; only reviewed pull requests publish under `materica.`; third-party families in their publishers' namespaces; one `openmaterica-families` distribution with a hash per family version (3.1, 4.5); OpenMaterica's own families kept in this repository, a second publisher's in its own (maintainer, 2026-10-17; 3.1) |
| 5 | Where reference implementations sit | with their families; the core only runs vectors and check points (3.1) |
| 6 | Where the rules are normative | the specification only; schema doc strings are short and point to it |
| 7 | USD encoding of parameter sets, statistics, uncertainty structures and check points | one generated JSON string per field and nothing beside it; the typed value first proposed beside it was dropped after review (5.3) |
| 8 | The data licence | CC0-1.0 for the curated library (6.4) |
| 9 | Sources and ontologies to start from | NCBI Taxonomy, UBERON and a short state list (4.8); water from its reference formulation (4.3); NIST's attenuation tables (12.1, R3; terms to check); tissues from primary literature, with the IT'IS database as a lead only (6.4) |
| 10 | How much sampling belongs in OpenMaterica | label volumes and layered paths; mesh inside-tests stay with consumers; analytic test phantoms as conformance data (3.2, 7.4) |
| 11 | Interfaces | a record type of their own (4.13) |
| 12 | Deforming tissue | values belong to the material, so a binding moves with its mesh; a field override declares its frame (4.4) |
| 13 | Temperature coupling | no new mechanism: a consumer evaluates a table over temperature at its simulated temperature, its evaluator returns whether the temperature is in range, and its monitors read that (4.4, 9.6); irreversible change is an evolution family with an event (4.5) |
| 14 | Maintenance beyond the first version | one maintainer for now; reviewed at the first library release against the adoption criteria of section 10, with a co-maintainer sought from the first outside publisher |
| 15 | The form of namespaces | short names, first come first served in the publishers file (4.1, 6.7) |
| 16 | The MCP server's packaging | no sampling at first; the tools exist first as library functions and commands (8.1, 8.2). First answered as a separate distribution; since 2026-10-16 the core's `[mcp]` extra, whose one server loads the tools of whichever siblings are installed (maintainer; 7.1, 8.1); since 2026-10-17 from a closed list, over stdio only, and no tool it loads makes a network request (maintainer; 8.1, 8.2) |
| 17 | Quotes for every extracted value | required for values extracted from text or tables in the curated library; optional elsewhere (4.7) |
| 18 | Events: what takes over, and how a chain is recorded | the consumer declares the chain; a family never names its successor; the sheet and the run record it (3.5, 4.5) |
| 19 | Check points for reference-only parameter sets | none shipped; the fill-in is checked against the witness locally (4.6) |
| 20 | Sections in another namespace | an `extensions` block keyed by namespace, outside the curated library's review; data that is not a material uses a record type of its own, the first specified after MIME prototypes one (4.1) |
| 21 | The form of domains | collections in USD, lists in plain records, named relative to their prim; domains that change during a run are deferred (5.1) |
| 22 | Which specimen facts are compared, and how | the vocabulary's facts, reported as facts with their ontology relation, never as a score; acceptance per section and fact, with a reason (4.11) |

Still open:

1. The record envelope's exact fields, and how a namespace publishes the schema of a record type of its own;
   settled with MIME's prototype of the Navion's calibration, which also needs a value form for arrays of
   vectors (4.1).
2. (Closed by the maintainer, 2026-10-13: settled by the specification.) The overlay record's exact fields and
   its USD prim, now specified in `record_format.md` section 4.4 and `usd_binding.md` section 6 (4.1, 5.5).
3. Thin structures: a shell with a thickness, when a consumer needs one (5.1).
4. Domains that change during a run, with the mechanics track, including event chains whose successor is
   another record (4.5, 5.1).
5. What Isaac for Healthcare's speckle parameters describe: a renderer's tuning, or physical scatterers that
   would belong in the acoustic section (4.14). A question for a first contact.
6. The legal review's four questions (6.5).
7. Whether an OpenMaterica material prim carries a semantic label (`SemanticsLabelsAPI:material`), which
   SimReady's validators require of every material prim. A label is not a field value, so the one-string
   rule allows it. Decided before material prims are built (maintainer, 2026-10-13).
8. Names that clash, settled by the maintainer on 2026-10-13: conformance profiles are
   **conformance suites** (OpenUSD 26.08's `UsdProfiles` and MADDENING's profiler use "profile"); engine
   profiles, briefly engine maps, are **engine crosswalks**, and label mappings are **label crosswalks**
   (MADDENING's coupling class is `Mapping`); "field" stays, written `RecordField` in code, though MIME and
   MADDENING use the word for spatial fields.
9. Whether `materica check --stage` is built as validators in OpenUSD's `usdValidation` framework (26.08),
   which already flags a binding without `MaterialBindingAPI` applied. Decided before the stage check is built
   (maintainer, 2026-10-13).
10. Whether OpenMaterica hosts consumers' engine crosswalks for others to reuse, unreviewed (a directory or a
    separate repository), once two consumers write crosswalks for the same engine (5.4).

## 14. Not examined

- Nothing was built in a repository. The USD checks of section 5 ran in a scratch directory against
  USD 0.26.5, with one prototype schema. Five throwaway prototypes (section 12.5) then ran outside any
  repository, with hand-written records and a throwaway reader: plain records, domains and bindings on a
  multi-region stage, Isaac for Healthcare's ultrasound table, families with check points and witnesses on
  real papers, the cost of curation (a model's estimate, not a timing) and differentiable use in MIME. They
  cover parts of spikes S1, S2 and S3. The record envelope, the encoding of section 5.3, the layered-path
  prim, the stiffness-tensor family and the sampler are unprototyped.
- No legal review has been done. Section 6 rests on a short search and is not legal advice.
- Isaac for Healthcare was read at its main branches on 2026-10-09 to 2026-10-11 by documentation and file
  search. On 2026-10-12 an ecosystem survey read SimReady's specifications, NVIDIA's physics schemas, Newton's
  importer, Isaac for Healthcare's patient twin and simulators, and the ontologies, unit systems, medical
  label standards and solver formats a consumer would meet, with citations, in a private report; its findings
  on units, bindings and label crosswalks are applied in sections 5.4 and 11. Its review the same day ran
  stages through OpenUSD's reference physics parser with usd-core 0.26.5 (instancing, payloads, subsets,
  `MassAPI`, layered composition). The engine adapter, the engine crosswalks and the per-shape stage check are
  unprototyped, and no NVIDIA engine was run. On 2026-10-13 usd-core 0.26.5's schema registry and its
  `usdPhysics` schema file were read for the scaffold (names, types and fallbacks given; no units), and the
  review that day ran the reference parser, built-in APIs and `MassAPI` zeros; nothing of the scaffold was
  built.
- The adoption history of earlier materials-data formats was partly researched in October 2026 (section 10);
  why ASTM E49 and CODATA's task group ended was not found.
- The hosting and registry examples of section 6.7 (Zenodo, PyPI, Julia's registry, Datasette Lite, the
  Hugging Face Hub) are recalled; none was checked for limits or terms.
- No MCP server was prototyped. MCP's primitives and client support are recalled. The failure modes of
  section 8.7 come from general experience, not from measurements on tissue literature; the gold set
  exists to measure them.
- Nothing of the sibling machinery (sections 7.2 and 8.2) was built or tried: the uv workspace, the siblings'
  tags, the siblings' version checks, the server's closed list and entry-point loading, and the explainer
  release. The version machinery is to be built with `openmaterica-authoring`'s first release, and the server
  with A9 (sections 7.2 and 12.1). That a resolver picks an explainer release only when the core is pinned to
  its minor is reasoned, not run.
- The papers, databases and ontologies named here are recalled, except where the survey checked them.
- The photoacoustic figures in Appendix A are my arithmetic on assumed values.
- MIME's material needs in section 12.1 were found by searching its node and experiment files. None of the
  spikes of section 12.3 has run as specified; prototype P1a/b ran the two experiments chosen for S1 on
  MADDENING's `release/0.4.0` branch (`f2aa830e`).
- The review of 2026-10-12 (section 15) read these documents and MIME's code in two independent passes, one
  told to break the design. Its figures for mixing, the compressibility of solids and demagnetisation are
  my arithmetic. The absorption edges, the Fåhræus-Lindqvist effect, ISO 10993-1's scope, USD's fallback
  behaviour and the units of `UsdPhysics` density are recalled.

## 15. Revisions of 2026-10-11 to 2026-10-17

A design review, using an existing per-paper tissue calibration code base as a case study, changed the
draft as follows. A follow-up the same day on distribution, drawing on the Hugging Face Hub, added four rows
(namespaced identifiers to self-contained layers); a third revision added model-assisted curation (the
witness and MCP rows); a fourth set the phasing by MIME 0.3.0's needs (the phasing row).

On 2026-10-12 a review tested the draft against two principles it had not stated (principles 9 and 10),
in two independent passes, one told to break the design rather than confirm it. The draft disclaimed
judging applicability (section 7.6) and then judged it in at least eight places, and several spike
controls could not fail. The rows after the phasing row record what changed. A simplification pass the
same day (asking who needs each requirement, deferring what nobody needs yet, and prototyping before
standardising) added the last three rows.

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
| catalogue numbers under one prefix, `<prefix>-MAT-XXXX` | namespaced identifiers `<namespace>/<local id>` | anyone can publish without a central authority; retrofitting would break the schema |
| data sheets | material cards: a metadata header and prose sections | a landing page that tools and people both read |
| hosting unstated | git repositories, static archived releases, federation through an index; no hosted service | small data; static releases can be assessed; no service to run |
| USD composition trusted | shipped layers self-contained, checked | reading a library layer reads one file, whoever published it |
| check points only | check points plus a convention witness per parameter set | check points are baked from the stored parameters, so they cannot catch an extraction error |
| none | model-assisted curation and query through MCP: bring-your-own-key, deterministic tools, quotes, human review, fail-closed release | extraction is the bottleneck; a model must never become an authority |
| phasing by section; MIME "if timing allows"; a mechanics family first | three sets for MIME 0.3.0, each feature tied to what it serves; MIME-facing features proven by spikes first; the Langevin magnetisation family first, mechanics on a track of its own | the first consumer sets the order; a spike is cheaper than a design reversed after release |
| none | principles 9 and 10; section 3.5: records hold facts, consumers declare choices, the build records the relation; checks with three results | "the data exists" was being read as "the model applies" |
| proxy flags on records | specimen facts; the difference from a declared target computed; acceptance declared and recorded | whether data stands in for something depends on its use |
| a mixing rule per field, with a default in the schema | identities fixed; named rules picked by the consumer, inside a domain | the right rule depends on arrangement and regime |
| no domains; a background material by default | domains declared by the consumer; precedence and background declared by the scene | a fluid section on a tissue does not make the tissue part of a flow |
| fit coverage as a "validity envelope" | coverage, kept as a set; never a verified regime | a fitted range is not a verified one |
| a consumer's fit as a stronger layer | an overlay scoped to field, model and run | a fitted value absorbs the errors of the model that produced it |
| schema fallbacks; linear interpolation everywhere; "uses the nominal values"; no statistics for "exact" values | no fallbacks; schemes, ranges and edges; nominal values only by declaration; `dispersion: not_reported`; interval-only values | nothing may stand in for a value without saying so |
| a curator's fit "witnessed by construction" | a witness independent of the fit; witnesses through a model of the test labelled | a witness that cannot fail is not one |
| one kind of statistic | each spread says what it represents | a population's spread and an estimate's uncertainty answer different questions |
| provenance `kind`: declared, measured, fitted, derived | `origin`, separate from how a value was transcribed | a reported measurement is not a declaration |
| static families only | evolution families with state and history, and optional events, specified in the core from the start; failure properties under mechanics | viscoelastic, rate-dependent, damage and release models depend on history; much of MIME's physics does |
| biocompatibility status on a material | test evidence on the material; status declared on the device | biocompatibility belongs to a device in its use |
| eight spike controls | rewritten so that each can fail | several could not |
| an index repository once a second publisher exists | a publishers file and a template repository from the first library release, with MIME's namespace as the first entry | waiting for a second publisher made one less likely |
| every section specified together | sections specified when a consumer needs them; three rules make adding one later a minor schema change | a section added later must never break a reader |
| MIME spikes after the first release | prototypes first: a multi-region MIME stage, the ultrasound table, the importer, timed hand-written records (section 12.5) | a schema should meet real data and real consumers before it is frozen |

Later on 2026-10-12 the prototypes ran (section 12.5), and the maintainer decided on their findings and on
every open question (section 13). The rows below record what changed.

| Before | After | Why |
|---|---|---|
| bodies, tissues, phantoms and devices, with the boundary open | substances in and around the human body, never systems; five rules, including the transfer test (section 1) | a test over 64 real cases gave no clearly wrong answer (7 needed a closer look); systems (a calibration, one object's inertia, a drive) had been offered as material values |
| every record a material | an envelope every record shares, with a record type; materials and interfaces are OpenMaterica's; other namespaces may define types readers skip (4.1) | MIME's device calibrations need the machinery but are not materials |
| density under fluid and acoustic | a bulk section with density and elemental composition (4.2) | the X-ray projector needs density everywhere, and solids had no section for it |
| the stiffness tensor deferred | anisotropic linear elasticity with a symmetry class, and propagation direction on speeds (4.2) | bone, for ultrasound and mechanics (maintainer) |
| layered paths with the mechanics track, USD form open | specified now, plain and as a typed prim (5.1, 5.4; R14) | MIME 0.3.0's acoustics and X-ray need them (maintainer) |
| shared array-API mixing functions | rules specified, numpy references and conformance at a single cell; consumers implement them (4.12) | the core then never runs inside a consumer's computation; P5 wrote the identity rule in one line |
| derivatives of tables undefined | conformance gives both one-sided derivatives at knots and ends; evaluators return whether they are in range (4.4) | P5: a clamping evaluator stalled a fit silently |
| guards on the run in general | guards on the condition an optimiser moves, never on the derived value (3.5, 9.6) | P5: a bound on viscosity never fired |
| USD dictionaries for rich data, with a rule for readers | one JSON string per field beside a typed value (5.3, 5.5) | the dictionary-merge trap cannot arise; one reader for both forms |
| reuse `physics` as a lean | decided, with readers refusing all-purpose and purpose-less bindings and an explicit region marker (5.1, 5.4) | P1c: a naive reader accepted the all-purpose fallback and a purpose-less binding; collections include descendants |
| a successor named by the event | the consumer declares the chain (3.5, 4.5) | which model follows is a choice about applicability |
| check points for every parameter set | none for reference-only sets; the witness checks the fill-in locally (4.6) | check points would publish the parameters |
| quotes when a model assisted | quotes for every value extracted from text or tables in the curated library (4.7) | which values a model touched cannot be audited |
| a data licence open | CC0-1.0 (6.4) | a standard others recombine; credit travels with provenance |
| curation tools with the MCP layer | five tools before the first library release; MCP later (8.2; R15) | P4's estimate was 2 to 7 times the threshold, and tooling replaced deleting fields |
| an Isaac adapter in Python with no C++ change | a build-time generator of their table (11) | P2: their Python API cannot replace it |

The revision above was then reviewed in two independent passes, one checking that it carried the decisions
faithfully and one told to break it, which walked five consumers through it (MIME's multi-region fit, a C++
reader with only a JSON parser, a curator importing tissue models, a second publisher, a regulated
manufacturer). The maintainer decided the points that changed an answer; the rest were fixed within the
decisions. The rows below record what changed.

| Before | After | Why |
|---|---|---|
| the transfer test decides scope | the line between a specimen (shape and size as conditions) and a made object (section 1) | the test put a capsule's effective susceptibility in while the statement's own example put it out |
| a typed value beside each field's JSON string in USD | the JSON string alone (5.3) | no engine reads it; the two could disagree silently; for most forms there is no single value to write |
| unknown record types skipped | skipped when listing, refused when referenced; an `overlay` type; the first namespaced type after MIME prototypes one (4.1) | a region bound to a skipped record would fall to the background silently; overlays fitted neither type |
| fits as stronger USD layers, scoped by model and version | overlay prims applied only when declared, scoped by a hash of the whole model configuration (5.5) | a stronger layer applies to every reader; a rerun at another resolution passed the old scope |
| one material relationship target per layered-path interval | distinct materials and an index per interval (5.4) | USD removes repeated targets (checked), which dropped layers silently |
| `UsdPhysics.MaterialAPI` on library materials | not applied in shipped layers (5.4) | its density reads in the stage's units, and it exposed zero friction |
| 3-D binding expressible only in USD | plain scene documents: a manifest, layered paths, label crosswalks (5.2) | a consumer with only a JSON parser could not describe a scene |
| five value forms; attenuation in either unit convention | seven, with interval and composition; attenuation stored as an amplitude coefficient (4.4) | composition and interval-only values had no form; dB and intensity conventions passed every check |
| no extrapolation | a consumer may declare one, with its basis, recorded (3.5) | the maintainer's earlier decision D2, lost before the first revision |
| unknown conditions reported as present and unchecked | unknown, refused unless waived; an unknown token refuses its field (4.4, 5.6) | an old reader could fall back to a default it knew |
| a run-time watch on an evaluator's own axis | a watch for every declared condition and tolerance (3.5) | a constant has no axis |
| five uncertainty structures | plus `marginals`, never sampled jointly (4.9) | mean and standard deviation per parameter, the commonest literature form, had no honest home |
| a hash over listed parts of a record | the whole record minus a stated exclusion list, with test vectors (5.6) | a retyped record kept its hash; a second review broke every pin |
| "the core never runs inside a consumer's computation", undefined | defined as the step, compiled program and gradient path; the core runs at build; `openmaterica` and `openmaterica-authoring` split (2, 7.2) | MIME's build runs the reader and the checks, and the core bundled tools with network access |
| priority defaulting to depth; a one-region default domain | refused or declared (5.1) | hierarchy is not containment |
| the stiffness tensor in 0.2 | stretch, A10 (12.1) | the maintainer's call; for the skull, porosity and shear matter more (12.2) |

The specification was then written (`docs/specification/`) and reviewed in two passes, one building a reader
from it alone and one told to break it (124 findings). The maintainer answered three points; the rest were
fixed within the decisions. The rows below record what the design gained.

| Before | After | Why |
|---|---|---|
| a user fills in a reference-only record in place | a fill-in is an overlay in the user's namespace, based on the curated record by hash (6.2) | in place, the record kept the curated identity, licence and review for numbers the curator never saw |
| a reader reads any newer minor version | before 1.0.0, only its own minor version (5.6) | a pre-1.0 minor version may still change shapes |
| specimen shape as a specimen fact | shape and size are conditions (4.8) | they change what a value means, so they are matched by requirement, not accepted |
| a reader validates against the record's schema | a closed writer schema and an open reader schema; an unknown token refuses its field, not the record | a validating reader would refuse every newer record whole |
| conditions checked against what the consumer declared | every condition the field holds is checked: by tolerance, accept list or waiver, else unknown | an unstated condition the consumer never mentioned passed as met |
| overlays scoped by configuration | scoped by model and configuration, base by identifier, version and hash; conflicts refused | another model in the same experiment would apply a fit |

The ecosystem survey of 2026-10-12, the maintainer's decisions on it, and a two-pass review of the result
(40 findings) gave the rows below.

| Before | After | Why |
|---|---|---|
| USD binding and layered paths in OpenMaterica 0.2 | in 0.1, with no cut line (12.2) | the read path depends on scenes; MIME saves scenes in USD and Isaac for Healthcare's patient twin is USD (maintainer) |
| reuse the `physics` binding purpose | a purpose of our own, `materica`; engine materials written by adapters, stamped with their source, bound `physics`; the stage check flags a mismatch or a simulated region with none (5.4) | NVIDIA's tools write the `physics` slot, and an engine reads nothing from an OpenMaterica material (ecosystem survey; maintainer) |
| attenuation in `Np/m` | registered as `/m`, nepers stated in the field's definition | `Np/m` is not valid UCUM (survey) |
| an adapter configured by an undefined "engine configuration", checked per region by a label | an engine is a declared model; a pinned engine profile per engine version; one conversion rule by SI dimension; a stamp of the reads; a per-shape stage check that re-derives values, with `MassAPI` and instance proxies (5.4) | engines bind colliders, not regions; a label is never compared with values; `MassAPI` overrides a material's density (review) |
| schemas found with `HasAPI` | by name in the composed `apiSchemas` | without a plug-in, USD omits unregistered schemas, so a reader found no regions (review, checked) |
| instances, payloads, point instancers, time samples unspecified | traversed through instance proxies; unloaded payloads, prototypes and time samples refused | each let a point read the background silently (review, checked) |

The maintainer's decision of 2026-10-13 on who writes engine crosswalks, and its two-pass review, gave the
rows below.

| Before | After | Why |
|---|---|---|
| OpenMaterica ships an engine profile per engine version (proposed: `UsdPhysics` rigid materials, Isaac Sim's deformables, Newton later) | OpenMaterica specifies the engine crosswalk and ships one, for `UsdPhysics`; the consumer that runs any other engine writes and pins its crosswalk, drafted by a scaffold from the engine's schema file and compared with the schema file it pins by hash, never with what is installed (5.4) | a crosswalk per engine version is adapter upkeep, not a standard; the consumer knows the engine version it runs (maintainer) |
| the stamp names its profile, and the check needs the profile to re-derive; engine materials as the reference parser reports them | the stamp carries the APIs applied and each attribute's type and dimension and the unit convention, so the check re-derives every value without the crosswalk and checks the stamp against its units, and against the crosswalk when held; engine materials are those bound `physics`; unrecognised APIs are listed | a stand-alone check would otherwise flag every consumer's material it has no crosswalk for, or trust a stamp it cannot see past; the parser drops any material without `PhysicsMaterialAPI` (review) |
| an engine fallback per attribute; dimensions in M, L and T | no fallback member, since the adapter authors every attribute; dimensions over the seven SI base units; one engine model per region | `UsdPhysics` uses water's density, not its schema fallback, for an unauthored density; magnetic quantities need the ampere; two adapters would overwrite each other's bindings (review) |
| "engine profile" (then "engine map", proposed); "conformance profile"; "label mapping" | "engine crosswalk"; "conformance suite"; "label crosswalk" (maintainer, 2026-10-13) | "profile" clashed with OpenUSD's `UsdProfiles` and MADDENING's profiler, "map" and "mapping" with MADDENING's `Mapping` and Python's `map` (13, item 8) |

The maintainer's decisions before the first code (2026-10-13) gave the rows below.

| Before | After | Why |
|---|---|---|
| the core depends on numpy and a JSON Schema validator | no run-time dependency beyond the standard library; `[check]`, `[usd]` and `[sample]` extras (7.2) | four or five more packages (by Python version), one a compiled Rust extension, would enter every consumer's build; the specification's README allows the envelope checks to be written by hand |
| `openmaterica-authoring` never in a consumer's product; engine results unplaced | engine results in `openmaterica[usd]`; authoring part of a product whose build runs the adapter (7.2) | the build gives engine results; a build that runs the adapter runs authoring |
| declarations before scene documents | scene documents before declarations (12.2) | the build checks requirements over domains and paths |
| record and scene shapes defined in Markdown tables and JSON Schemas separately | the writer JSON Schemas are the single source of structure; reader schemas and typed shapes generated; Markdown tables checked (7.1) | one hand-edited home for every fact |
| Python versions unstated | a floor of 3.11 and a standing rule (7.2) | 3.10 reached end of life on 2026-10-01; Isaac Sim 5.x runs 3.11 |
| a proposed layout | the 0.1 module list, with versioned schemas (`schema/0.1/`) and generated vocabulary files (7.1) | agreed before the first code |
| typing unstated | the package typed (`py.typed`), checked by mypy and pyright; no public function returns a `pxr` object, and every `pxr` call goes through one module (7.1; DA 15) | consumers type-check their declarations; a returned `pxr` object would spread an unchecked type through their code |
| every record check in `materica check` | the checks that need the source registry, a source copy, the previous release or the history in the library's tooling (DA 6.5) | they need inputs a record does not carry |
| AD 13 items 2, 7 and 9 open | item 2 closed; items 7 and 9 decided before the code that needs them (13) | the specification settled item 2 |

The maintainer's decision of 2026-10-14 on the project's name gave the row below.

| Before | After | Why |
|---|---|---|
| the working name the drafts used before the first release, since removed from the public files, in the distribution, package, reserved namespace, family namespace, binding purpose, attribute namespace and command, the schema classes' prefix, the local ids and the registry prefixes | OpenMaterica: distribution `openmaterica`, package `materica`, and `materica` for each of the others; schema classes `Materica…`; local ids `MAT-NNNN` and `INT-NNNN`; registry prefixes `OMAT-ANO-`, `OMAT-VER-` and `OMAT-MTH-` (4.1, 5.3, 5.4, 7.1; DA 8.3) | a name cleared for the project's use, chosen before any release, while no identifier was yet frozen (maintainer, 2026-10-14) |

The maintainer's decisions of 2026-10-14 on the questions on the read of values (specification `changes.md`,
entry of that date), gave the rows below, each written as its question was ruled. They take in a
review of the uncertainty data MADDENING 0.5.0's consumers need, and a literature review of materials-data
practice; both are private working files.

| Before | After | Why |
|---|---|---|
| one meaning and basis per statistics block; an expanded uncertainty with its coverage factor | each relative or expanded uncertainty carries its own meaning, basis, distribution, coverage factor or probability and degrees of freedom, and its precision conditions where it is a measurement's; Student t by scale and beta registered (4.9) | a block could not hold a population spread beside a measurement uncertainty; a t's scale is not its standard deviation |
| a spread with no level, and counts that could count publications as specimens | `population_level`, `n_sources` and `precision_conditions` present where the spread's meaning calls for them; the search record's weighting and inputs | a pooled specimen spread was drawn as a spread between donors, and five publications read as five specimens |
| record checks report findings only | findings, and a listing that never fails | a faithful record of a source's bounds or fits could not pass |
| `params` always a vector | a vector where the source reports one, the mean of per-specimen fits included and labelled; check points per member or at a corner made of the source's bounds (4.6) | ensembles and intervals forced a vector the source never gave |
| mean and covariance in "a declared space" | in the space the source states, or the one a fit's producer recorded; never re-expressed (4.9, 9.4) | the word did not say whose choice it was |
| the rejection count reported | the acceptance rate per run and per block, counted per constraint, with a minimum declared once per run (4.9) | the run's joint acceptance bounds how far the output can move |
| admissibility as prose and a numpy reference | named constraints, bounds and linear inequalities as data, every constraint failing a non-finite value (4.5) | vectorised consumers re-implemented constraints, and could drift |
| one-level ensembles of specimens or donors | ordered levels and groups, equal weights; draws named for what they are; restarts and posterior draws are not members (4.9) | specimens of one donor were drawn as donors |
| every corner and member must pass admissibility | members and corners listed; a worst case from corners only under three conditions (4.9) | curators would have had to drop the source's own fits and bounds |
| a nominal only for an interval's value | nominal vectors for parameter sets | a parameter set with no vector had no declared nominal |
| sampler behaviour defined by the reference sampler's draws | the sampling suite as the contract, its core arms from given normals (7.3, 7.4) | samplers built on different generators cannot be compared draw by draw |
| independence ruled within a parameter set only | declared between fields too (3.5) | sampling fields jointly assumed independence silently |
| precision undeclared | declared per model, with the sheet; the table evaluation suite's tolerance given per precision | tolerances and conformance assumed it |
| a condition's ± lost, or stored as a covered range | a numeric condition may carry the source's ± (a bound, a standard deviation, both, or one of unstated kind) and whether it was a set-point; a bound narrows a met condition, and any other ± alone turns it into unknown | a range read as covered passed a value measured 2 K away against a 1 K tolerance |
| condition checks written as floating-point expressions | made on the exact values of the numbers read | for the check's four comparisons, floating point as written can err only towards met |
| a consumer that accepted a tube read its value without the tube's diameter | a condition another requires is checked like a required one | the diameter changes what a narrow-tube viscosity means |
| what a read checks named only by document | the members a read uses or returns, the statistics block included; a review never refuses a read, and an unreadable one reads as not checked | a reader refused, or passed, what it never read; a review lies outside the hash |
| a status object beside other members undefined | a closed table of the members that may hold a status object, each with the tokens it may hold; there an object holding `status` is a status object, refused where it also holds a member of the shape it stands for, where that shape is a number, a string or a token and it holds any member but `reason`, or where its token is one its row does not allow; a read refuses only in the members it checks | two conforming readers could read one record two ways (in a number, a string or a token, refusing other members amends the first ruling, which ignored them: maintainer, 2026-10-14) |
| biocompatibility evidence never withheld | withheld entry by entry, every member but provenance; a partly withheld list reads unknown | one reference-only report withheld every other, and its words would have shipped |
| device materials described by free text; a commercial product a record by product and lot | `supply_form` and `lot` as specimen facts; one record per grade or product, with measurements on particular lots as alternatives naming their lot | a lot's measurement and a grade's datasheet could not be told apart by a target |
| remanence read without its magnetic circuit | a closed-circuit test method, and the method required on remanence and saturation | a closed-circuit remanence and an open-circuit one on a cylinder read alike |
| probe test methods unconstrained | a probe method enters only with a condition stating the length it probes (4.8) | values probed at 20 nm and at 2.5 µm differed a hundredfold on one specimen |
| data used to choose a model could witness it | `used_in_selection`, never a witness | a curve that chose the model was reported as its held-out check |
| computed and predicted values unaddressed | no 0.1.0 origin for them; a database source pinned by release and entry | a value with no release re-extracts to another number |
| acceptances in a read scheduled with alternatives and overlays | each step brings the acceptances it applies; a nominal outside the bounds is `nominal_invalid`; implied conditions that disagree are a fault of the request | the read of values applies implied conditions and nominals before overlays exist (maintainer, changing the schedule decided 2026-10-13) |
| OpenMaterica's relation to materiomics unstated; the adoption history of earlier formats not researched | adjacent to materiomics, not its infrastructure (1); adoption evidence recorded (10, 14) | neither school of materiomics defines a record; the standards that spread had a gatekeeper and a validator |
| a member the reader does not know ignored wherever it stands | ignored unless it is one slip from a member named at its place, which is refused; the names valid at one place kept more than one slip apart, now and in later minor versions (5.6) | a misspelt `plus_minus`, a field's `specimen` or a request's `acceptances` dropped what it held, and the read gave `met` (maintainer, 2026-10-14) |

The maintainer's decisions of 2026-10-16 on the sibling distributions and the MCP server gave the rows below.

| Before | After | Why |
|---|---|---|
| a separate MCP distribution, `openmaterica-mcp`, depending on the core and an MCP server library | no MCP distribution: the core's `[mcp]` extra brings the one server, in L6, which loads the tools of whichever siblings are installed (7.1, 8.1, 13) | one server whatever is installed, and the base install of every distribution free of MCP dependencies |
| none | a sibling's tools are plain functions registered by entry point, and no sibling imports an MCP library; the server skips a missing or mismatched sibling with a logged reason (8.2) | a sibling needs no extra of its own for the server to find its tools |
| this repository holding the core and, at first, the families, with `authoring/` and `mcp/` beside them; the siblings' release tags and their relation to the core's versions unstated | one repository for every Python distribution, a uv workspace with tag-prefixed releases, each distribution with its own `pyproject.toml`, version line and changelog, in DA 2's layout (the core at the root, `authoring/` and `families/`); the library in a repository of its own (7.1, 7.2; DA 2, DA 12) | the maintainer's call; each distribution is released from tags of its own prefix |
| a SemVer line for each Python distribution (DA 7.1), its relation to the core's unstated | a sibling's MAJOR.MINOR is the core's it is built for, its patch its own; `openmaterica>=X.Y.F,<X.(Y+1)` before 1.0 and `>=X.Y.F,<(X+1)` after; a core minor is a release train; `[authoring]`, `[families]` and `[all]` extras on the core; a sibling refuses a core of another MAJOR.MINOR, naming the fix; `python -m materica versions`; nothing updates itself; CI against the oldest core in range and the current one (7.2; DA 7.1) | a sibling's version says which core it works with, and one `pip install -U "openmaterica[...]"` upgrades consistently |
| a sibling's PyPI name unclaimed until its first release | each sibling's first real pre-release goes out early; before its first real release, an explainer release for each earlier core minor, today `openmaterica-families` 0.1.0 at core 0.1.0a1 or 0.1.0 (7.2; 12.1, M10) | it claims the name, and a user whose core is pinned to an earlier minor gets a message naming the install that works. An sdist that fails its build was not used: `--only-binary` skips it, and build output buries its message |
| none | the release workflow writes a compatibility table of each core version and its siblings' versions into the documentation, and `python -m materica versions` says which siblings exist for the installed core (7.2; DA 7.1, DA 12) | which siblings exist for a core can be read without installing them |

The maintainer's rulings of 2026-10-17 on the open points of those decisions gave the rows below. The names
proposed with them (the server's module and command, section 7.1) and the skills (section 8.2) remain
proposals.

| Before | After | Why |
|---|---|---|
| the MCP server as curation tooling outside the SOUP package, then a separate distribution (8.5; DA 10) | part of the core's assessed wheel: the SOUP package lists it as present, imported by no reader, check or consumer's build, and never run at a consumer's build, with a test that enforces the import boundary (8.5; DA 10) | the core's wheel is assessed whole, and its hashes cover the server |
| none: which installed packages the server loads tools from unstated | a closed list in the core (the core, `openmaterica-authoring`, `openmaterica-families`); an installed package outside it adds no tool; a listed sibling missing or mismatched is skipped with a logged reason; the core's own read-side tools register through the same entry-point group (8.2) | installing an unrelated package cannot widen what a model can call; one way to find every tool |
| the server "makes no network requests", with registry drafting among the tools it exposes; its transport unstated | no tool the server loads makes a network request, and registry drafting stays a command a person runs with its explicit flag; stdio only, no socket (8.1, 8.2) | both claims hold by construction |
| nothing in `materica` imports `materica_authoring`, proved by a test that walks the imports | entry-point loading in the server's module only; every static import of a sibling from `materica` still refused, by a test with a control that must fail (3.2, 7.1) | the server loads sibling code at run time, which a check of static imports cannot see |
| the families moving into repositories of their own when a second publisher of families appears (3.1) | OpenMaterica's own families stay in this repository; a second publisher publishes its families from its own repository, under its own namespace (3.1, 13; DA 2) | the maintainer's call, once one repository held every Python distribution |
| the families' files under `families/materica/mechanical/<family>/`, overlapping the core's import package `materica` (DA 2) | the families' import package is `materica_families`, not a part of `materica` (3.1, 7.1; DA 2) | a distribution of its own cannot add modules to the core's regular package |
| `openmaterica>=X.Y.F,<(X+1)` after 1.0 | `openmaterica>=X.Y.F,<X.(Y+1)` after 1.0 as before: a sibling stays in lockstep with the core's minor for life (7.2; DA 7.1) | the range, the import guard and CI against the current core agree; the release train gives every core minor a matching sibling |
| the core's extras `[authoring]`, `[families]` and `[all]` pinning the matching siblings | `[authoring]` and `[families]` pin the matching minor with a range, `>=X.Y.0,<X.(Y+1)`, never `==`; `[all]` brings both siblings only, not `[usd]` or `[mcp]` (7.2; DA 7.1) | a sibling's patch needs no core release; `usd-core` has no wheel for Linux on aarch64 |
| one CHANGELOG with a **Families** section, the one DA 14's update policy names | family entries in `families/CHANGELOG.md`; DA 14 names each changelog a consumer reviews (DA 7.4, DA 14) | a consumer's update review would otherwise miss family changes |
| when the version machinery is built, and how authoring's name is claimed, unstated | built with `openmaterica-authoring`'s first release; authoring's name claimed by a `0.1.0.devN` once the uv workspace and the release workflow's change land (7.2, 14) | the maintainer's call; a pending publisher on PyPI does not reserve a name |

## Appendix A. Photoacoustics in MIME: the first consumer of the optical sections

**Direction (maintainer, 2026-10-11):** good to have in MIME 0.3.0 but not necessary; expected by 0.5.0 to
0.6.0. A medium-term vision.

Why it matters for MIME:

- It images microrobots in tissue. As I recall, PA tomography has guided microrobots in the intestine (Wu et
  al., Science Robotics 2019), and optoacoustics has tracked magnetic microrobots in mouse brain
  vasculature (Wrede et al., Science Advances 2022, Razansky's group). Recalled, not checked.
- It chains three physics (light, heat, sound) through one material, so it tests OpenMaterica.
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

1. OpenMaterica's optical and thermal sections, with composition (section 12.1, A8).
2. Scalar transport in MIME.
3. The time-domain acoustic kernel.
4. Observation models that run per frame.
5. A sensor model and a reconstruction.
