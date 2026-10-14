# OpenMaterica — working notes for Claude

This repository is public. Everything in it, this file and commit messages included, is public once pushed.

## Where things are

- **The specification** (`docs/specification/`) is normative: what a record holds, what a reader must do, what
  a consumer declares. Every normative statement carries a conformance case or `[not yet covered]`. A change
  to it is a schema change (`DOCUMENTATION_ARCHITECTURE.md` section 7.2).
- **The architecture draft** (`design/ARCHITECTURE_DRAFT.md`, "AD") holds the reasons. When a decision
  changes, its section changes and a row goes into AD section 15's revision tables.
- **The documentation plan** (`DOCUMENTATION_ARCHITECTURE.md`) holds the regulatory framing, the conformance
  list (section 6.1) and the project constraints (section 15, mirrored in `CONTRIBUTING.md`).
- **Private, unversioned working files** are in the sibling directory `../plans/`: the prototypes, their
  findings, the maintainer's decision tables and the reviews are under `../plans/spikes/vesalius_prototypes/`.
  The code design for 0.1, agreed before any code and detailed step by step, is
  `../plans/OPENMATERICA_0.1_CODE_DESIGN.md` (its reviews in `../plans/vesalius_code_design_review/`). Nothing
  from there is copied into this repository without checking it against the confidentiality rules below.
- Sibling repositories: `../MIME` (OpenMaterica's first consumer), `../MADDENING` (the simulation framework
  MIME runs on). The shared Python environment is `../.venv` (it has `usd-core` 0.26.5 for USD checks).

## How work proceeds

- **Design before code.** Before any code, write a throwaway design document: the modules, the classes and
  what each is responsible for, the data passed between them, and the call sequence of the main paths
  (reading a record, checking a consumer's declarations, writing the material input sheet). The maintainer
  reads and agrees it first, and reviews every line of code in detail. So code is written in steps that map
  onto the agreed design: a step may be several files, but each step ends with the maintainer's review, and
  the next starts only after it. Never develop the whole package iteratively on your own. No class,
  abstraction or module boundary appears in code that the design did not cover without raising it first.
- **Prototype before standardising.** A claim about the design is tested by the cheapest prototype that could
  show it wrong, pre-registered (criteria and predictions written before the run), with a control that must
  come out differently if the claim is false. A pass told to break the pre-registration reviews it before the
  run. Throwaway prototypes live in `../plans/spikes/`, never here.
- **Review by refutation.** Consequential revisions get two independent passes: one checks fidelity to the
  maintainer's decisions, one is told to break the design by walking concrete consumers through it. The
  passes told to refute have repeatedly found more than the primary work. Verify a reviewer's factual claims
  before acting on them.
- **Cases check a specification better than more prose review.** On the S1 text (2026-10-13), four prose
  review passes found 44, 24, 18 and 16 points, falling in severity but not in number; writing the conformance
  cases from the text, with an independent reference model checking them, then found ambiguities those passes
  had missed. Once prose passes stop finding high-severity points, write the cases.
- **The maintainer decides; the record says so.** Anything that changes an answer the maintainer approved goes
  back to the maintainer, with a recommendation. A decision the maintainer made is recorded where it lands
  ("maintainer, date"), and a lost decision is a defect: check new revisions against every earlier decision
  table, not only the latest.
- OpenMaterica work never edits MIME or MADDENING. Anything that tests OpenMaterica against MIME runs as a
  read-only spike that imports MIME and changes nothing. Requests of MADDENING go into
  `../plans/MIME_MADDENING_050_ASKS.md`, never into MADDENING itself.
- Commits: **every commit carries a DCO sign-off** (constraint in `CONTRIBUTING.md`); only the design commits
  made before the first code commit are exempt. Push only when the maintainer asks. Every change reaches
  `main` through a pull request: since 2026-10-14 a ruleset requires linear history, rebase merges and the
  check "CI result", which fails on a commit without a sign-off. `docs/design-foundation` was squashed into
  `main` in pull request #4.

## Confidentiality and licences

- One downstream project is private. Refer to it only as "the regulated project". Never name it, and never put
  its identifying details (its anatomy, the failure questions it studies, its file paths or decision numbers)
  into this repository or a commit message. Lessons from it enter only as generic requirements with
  literature-generic examples.
- Licensed source copies never enter this repository and are never uploaded anywhere: publishers' PDFs (often
  stamped with the downloader's IP address, which is personal data), database archives whose terms forbid
  redistribution (the IT'IS database's, for one), and anything under `../plans/spikes/*/sources/`.
- Values from sources whose redistribution status is not "permitted" stay reference-only, and so do their
  quotes (AD 6.2, 4.7).

## Design rules to hold on every change

- **Data existing never means a model applies** (principles 9 and 10, AD 3.5). A record states facts: what
  was measured, on what, under which conditions, and how it is known. The consumer declares the choices
  (domain, target, family, mixing rule, picks, tolerances, waivers, any extrapolation or nominal). The build
  checks the declarations against the records with three results (met, not met, unknown) and records
  everything. Ask of any new mechanism: "what decides that this applies here, and who declared it?"
- **Carry what the evidence supports, no more and no less.** No default, fallback, nominal, distribution,
  interpolation across an edge or extrapolation that the source does not give. A check is reported for what
  it can show, and a check that cannot fail is not a check.
- **Fail closed.** A reader refuses rather than guesses: unknown tokens, unknown types when referenced,
  unauthored attributes, values outside their range. Refusal is a result, never a crash.
- **Substances, not systems** (AD 1). A value of a substance or a mixture, measured on a specimen whose shape
  and size are recorded as conditions, is in. A value of a made object as built (a device, a product, an
  assembled robot, a calibration) is its consumer's. Geometry is scene data.
- **The core never runs inside a consumer's computation** (its simulation step, compiled program or gradient
  path). Consumers write their own evaluators and mixing rules there and verify them against conformance
  data. The core may run at a consumer's build, and is then third-party software in that consumer's product.
- **Small.** A section, family or library material enters when a named consumer needs it. A later addition
  must be possible as a minor schema change (AD 5.6); if it is not, decide it before 0.1.
- **Engine knowledge is the consumer's.** OpenMaterica ships one engine crosswalk, for `UsdPhysics`; a
  crosswalk for any other engine is written and pinned by the consumer that runs it (maintainer, 2026-10-13,
  AD 5.4). Do not add crosswalks for other engines to `materica`; improve the scaffold and the checks instead.
- **The core has no run-time dependency** (maintainer, 2026-10-13, AD 7.1 and 7.2): Python's standard library
  only; `typing_extensions` is for type checkers only; `jsonschema`, `usd-core` and numpy come with the
  `[check]`, `[usd]` and `[sample]` extras. Structure is edited in the writer JSON Schemas and tokens in the
  specification's tables; the reader schemas, the vocabulary and the typed shapes are generated from them, and
  the specification's member tables are checked against the schemas.
- **Names that clash are settled** (maintainer, 2026-10-13, AD 13 item 8): conformance *suites*, engine
  *crosswalks*, label *crosswalks*. Do not reintroduce "profile" (OpenUSD's `UsdProfiles`, MADDENING's
  profiler) or "map"/"mapping" (MADDENING's `Mapping`, Python's `map`) for these. "Field" stays; in code it is
  `RecordField`.

## Gotchas, checked

USD, with `usd-core` 0.26.5:
- A stage with no authored `metersPerUnit` is in centimetres (fallback 0.01). Referenced layers are not
  rescaled. `UsdPhysics` reads density in the stage's mass and length units (`kilogramsPerUnit` falls back to
  1).
- A relationship keeps its targets in order only when they are distinct: `[skin, fat, muscle, fat, skin]`
  reads back as three. Never encode a sequence as repeated targets.
- A schema fallback reads exactly like a value; only `HasAuthoredValue` tells them apart.
- Applying `UsdPhysics.MaterialAPI` exposes friction and restitution with fallbacks of 0.0.
- `ComputeBoundMaterial(purpose)` falls back to the all-purpose binding, usually a display material, when no
  binding of that purpose is authored. A binding authored without `MaterialBindingAPI` applied still
  resolves, with a warning.
- Without its plug-in, an applied API schema is missing from `HasAPI` and `GetAppliedSchemas()`; only
  `GetPrimTypeInfo().GetAppliedAPISchemas()` lists it. Detect OpenMaterica and engine schemas by name there.
- The default traversal skips prims inside instances; use `Usd.TraverseInstanceProxies()`. An unloaded
  payload's prims are simply absent.
- A `float` attribute is single precision: 1.05e-3 reads back about 4e-8 relative off.
- Dictionary metadata merges key by key across layers, so provenance written as a dictionary can be read with
  another layer's keys mixed in.
- `MAT-0001` is not a valid prim name. A schema plug-in entry needs `schemaIdentifier`; a second
  codeless-schema plug-in must register before `import maddening.usd`, or use `PXR_PLUGINPATH_NAME`.
- A material under `/Materials/<name>` merges silently with MADDENING's display material of the same name.
- OpenUSD's reference physics parser ignores a `physics` binding, direct or inherited, on a prim without
  `MaterialBindingAPI`; it reports only materials that carry `PhysicsMaterialAPI`, an all-purpose binding to
  one included. A binding cannot be authored on an instance proxy.
- The schema registry (`Usd.SchemaRegistry().FindAppliedAPIPrimDefinition`) gives an API's attribute names,
  types and fallbacks, but no units: the customData of `PhysicsMaterialAPI`'s four attributes holds only a
  one-line `userDocBrief`. An API whose plug-in is not registered gives `None`. A plug-in's
  `generatedSchema.usda` reads with Sdf without registering it, and composed `apiSchemas` never lists an API's
  built-in APIs. The file differs between usd-core versions (usdPhysics: 0.25.5 against 0.26.5), so never
  compare a crosswalk with an installed one.
- `UsdPhysics` mass computation ignores a `MassAPI` density or mass of 0, and uses 1000 kg/m³ where a
  material's density is unauthored or 0.

From the ecosystem survey of 2026-10-12 and its review (sources in their private reports, not re-checked
here):
- Engines never read an OpenMaterica field. The `physics` binding purpose is the engines' (Isaac Lab and
  SimReady write it); OpenMaterica binds with `materica`, and the engine adapter writes engine materials of
  its own (AD 5.4). Engines bind colliders and simulation meshes, not regions, and `UsdPhysics.MassAPI`
  overrides a material's density.

Sibling tools:
- MADDENING's anomaly validator (read at `f2aa830e`) accepts only `maddening_version` as a registry's version
  field, so it refuses OpenMaterica's anomaly registry (`DOCUMENTATION_ARCHITECTURE.md` section 8.1).
- MADDENING's USD live stage authors `metersPerUnit` 1.0 by default; a stage from elsewhere may author none.

Data:
- Attenuation comes in decibels or nepers, per centimetre or per metre, per megahertz or not, and as an
  amplitude or an intensity coefficient (a factor of two). Isaac for Healthcare's water value is water's
  frequency-squared coefficient applied as linear. Store only the amplitude coefficient, in nepers per metre,
  registered as `/m`: `Np/m` is not valid UCUM, because the neper cannot be part of a quotient.
- A segmenter's clinical code for an organ and UBERON's cross-reference for it can differ; join label
  crosswalks by name or number within one vocabulary, never by code across vocabularies.
- A preprint and its version of record need not carry the same numbers; record which one was read.
- A citation found in code is a lead, not provenance: in one real code base all ten checkable citations
  carried an error.
- A source can state one composition twice, inconsistently (one summed to 114 %). Keep the stated sum; never
  normalise silently.
- A magnetic value measured on a sphere includes the sphere's demagnetisation: the specimen's shape is part
  of the value.
- Independent witnesses are scarce: 1 of 20 real parameter sets had one. A published figure, digitised with a
  calibrated axis, is often the only witness available.

## Claim hygiene

- Mark what was not checked: "recalled" for something from memory, "my arithmetic" for a calculation not run,
  "would" for a proposal. A statement with a file path or a version was read or run.
- State what an estimate is: the curation-cost figures of prototype P4 are a model's estimate, not a timing.
- Do not round a result up. "Pre-registered, with the pre-registration reviewed" is not "checked by a pass
  told to refute it"; "64 cases, 17 of them edge cases raised in review" is not "64 real cases"; a result
  found after the run is labelled post hoc.
- Before asserting a mechanism, check the operating point it holds at, and attach a control.
- When a documentation commit summarises a review, say how many findings there were and which the maintainer
  decided.

## Writing

Plain words, active voice, short sentences, no marketing tone. Wrap prose at 110 columns. Keep each document's
house style. The sibling project is spelled MICROROBOTICA (some sibling documents have "MICROBOTICA", which is
wrong). Specification text uses MUST, SHOULD and MAY in capitals, each statement with its case.
