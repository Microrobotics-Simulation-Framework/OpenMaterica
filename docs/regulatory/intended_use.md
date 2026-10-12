# Intended Use and Regulatory Boundary

This document follows the structure of MADDENING's and MIME's `docs/regulatory/intended_use.md`. The
reasoning behind each statement is in `DOCUMENTATION_ARCHITECTURE.md` section 3.

## Platform positioning statement

Vesalius is an open material schema and a software toolkit for describing the physical properties of
substances in and around the human body for simulation. It is research software distributed under the
Apache License 2.0.

**Vesalius is not a medical device** as defined by EU MDR (EU 2017/745) Article 2(1). It has no medical
purpose. It does not diagnose, monitor, predict, treat or alleviate disease, and it makes no clinical
interpretation of anything it stores. Under MDCG 2019-11 it is general-purpose software, comparable to a
units library or a materials database. It has not been CE-marked, cleared or approved by any regulatory
body.

When incorporated into a regulated medical device, Vesalius is classified as SOUP (Software of Unknown
Provenance) under IEC 62304:2006+AMD1:2015. The device manufacturer bears full responsibility for assessing
its suitability for their context of use and for all required verification and validation.

## Scope

Vesalius describes substances in and around the human body: tissues and body fluids, the media and phantoms
that stand in for them, agents introduced into them, and the materials of devices that enter or touch them.
It does not describe systems: an apparatus or its calibration, the quantities of one object (its moment,
inertia or mean density), a drive, a procedure, or a simulator's tuning.

- **Specimens, not objects.** A value of a substance, or of a mixture given by its composition, measured on a
  test specimen whose shape and size are recorded as conditions, is in. A value of a made object as built (a
  device, a product, an assembled robot) is out: its consumer computes or records it. A value that depends
  on the specimen's shape (a magnetic value measured on a sphere, a blood viscosity measured in a tube of
  stated diameter) is in, with the shape as a condition.
- **Pairs.** A property of two substances in contact (friction, slip, a solute's diffusivity) is in, as an
  interface record, when the source states the surface conditions and the test method, which become
  required conditions. A number measured with one tool or device is reference data for checking a model.
- **Geometry is scene data.** Vesalius defines how geometry binds to materials, and ships only small test
  phantoms and label mappings from reference anatomies, never anatomy.
- **Behaviour.** Behaviour computed from geometry and materials (an implant's heating in MRI, a puncture
  force) is the consumer's output; measured behaviour is reference data in the consumer's namespace.
- **Entry.** Content enters when a named consumer needs it, and the curated library starts with the body
  and the materials of devices that enter or touch it. An apparatus's materials (a coil's copper, a
  detector's scintillator) are published as material records in other namespaces. Other publishers may use
  the same machinery in their own namespaces, including for data Vesalius does not curate. Such data is a
  record of a type of its own: its envelope and value machinery are checked as for any record, but Vesalius
  does not check its body, never treats it as a material and never curates it.

## Data statement

The values in the Vesalius material library are **taken from cited sources**, or are fits to cited data,
labelled by origin. For each value, the library states what its source gives (or what its recorded fit
produces), converted to SI, with the specimen, conditions and statistics the record states; and that each
shipped model parameter set reproduces its check points under the family definition it names, and its
independent convention witness where the record has one. `DOCUMENTATION_ARCHITECTURE.md` section 6 says how
each of these statements is checked; nothing more is claimed. Vesalius does **not** state or check that a
value describes any particular patient, tissue sample, phantom batch or device, nor that a source is itself
correct or current. Whether a library value is applicable to a given use is the user's and the
manufacturer's judgement.

Many values were measured on specimens that differ from a user's target: another species, another anatomical
site, a cadaver for living tissue, a phantom for tissue. Each record states its specimen per section or field.
Whether a specimen stands in adequately for a target is the user's declaration, which the user's build
records, never the library's.

Subject to the legal review planned before the first library release, every value in the curated library
that was extracted from text or a table carries the verbatim quote it was read from, with the identity and
version of the document. If quotes may not ship, the record carries the SHA-256 of the normalised quote with
its locator, and the text stays with the curator. Some values are drafted with the help of a language model;
each such value says so. Every value, assisted or not, is checked against its source by a named reviewer
before release.

Library records come in three tiers. A **shipped** record publishes its values. A **reference-only** record
publishes provenance, a locator and an extraction recipe but no values, because the source does not permit
redistribution or its status is unknown. A user fills its values in from their own copy of the source, as an
overlay record in their own namespace; the curated record never changes, and every value read through the
overlay is labelled user-extracted. Vesalius states nothing about those values beyond one check, reported as
"fill-in consistent with the user's copy": the filled parameters reproduce the witness datum filled from the
same copy, whose identity and version match the record's. A **private** overlay is an organisation's own data
in the same format, and is entirely theirs.

Biocompatibility fields record test evidence reported for a material. They are never a biocompatibility
assessment or a safety claim, and never a device's status, which belongs to a finished device in its intended
use. A manufacturer performs their own ISO 10993 evaluation.

## Cybersecurity boundary statement (MDCG 2019-16)

Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation beyond
validating records against the record schema. A USD stage can pull in other files through its composition
(sublayers, references, payloads) and through the host's asset resolver, so reading a stage may read any
file that stage names. Every USD layer Vesalius ships is self-contained (no composition arcs, no asset
paths), so reading a library layer reads that file alone. Vesalius itself makes no network requests and runs
no code from the files it reads: records and family vectors are data, and family reference implementations
are code shipped in the `vesalius-families` distribution, never loaded from a record. Loading third-party
records and stages, and the security of the asset resolver, are the responsibility of the integrating
application.

## Licence

Vesalius's code is licensed under the Apache License 2.0, which is permissive and includes an express
patent grant. No copyleft obligation follows a product that incorporates it. The curated material library's
data is released under CC0-1.0, stated on each record. A value whose source restricts redistribution stays
reference-only whatever that licence says, and a short quote kept as evidence is the source's text, not
relicensed: a record's licence field is structured, and excludes the evidence text from the CC0 grant. Other
publishers choose their own licences. This is a description, not legal advice.

## Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Family definitions and reference implementations agree | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | golden test vectors |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, fit reproduction, data checks |
| A consumer's own code inside its computation (readers, mixing rules and family evaluators in its step, compiled program or gradient path) | downstream user | IEC 62304 Clause 5.6 (their own) | the conformance profiles it passes; the record's check points; the family's golden vectors |
| Vesalius code a consumer runs at build (the reader, requirement checks, the material input sheet, label-volume fractions, the reference sampler) | Vesalius, assessed by the manufacturer as SOUP | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite; the SOUP package |
| Choosing a material; declaring its domain, target, mixing rule, picks and any extrapolation; accepting differences between specimen and target | downstream user | ASME V&V 40 (model inputs) | the user's input justification and the material input sheet |
| Watching, during a run, every declared condition that the run or an optimiser moves | downstream user | ASME V&V 40 | the run-time watches the build emits, and the evaluators' in-range outputs, recorded with the results |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

## Commercial boundary

Vesalius is an open-source research tool. It will not seek CE marking and carries no manufacturer liability.
A regulated product that uses it is built by a commercial entity that takes on the QMS, the Notified Body
relationship, post-market surveillance and manufacturer liability, as described in MADDENING's
`DOCUMENTATION_ARCHITECTURE.md` section 2.
