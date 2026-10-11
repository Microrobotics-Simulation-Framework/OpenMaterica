# Intended Use and Regulatory Boundary

This document follows the structure of MADDENING's and MIME's `docs/regulatory/intended_use.md`. The
reasoning behind each statement is in `DOCUMENTATION_ARCHITECTURE.md` section 3.

## Platform positioning statement

Vesalius is an open material schema and a software toolkit for describing the physical properties of
tissues, phantoms and devices for simulation. It is research software distributed under the Apache
License 2.0.

**Vesalius is not a medical device** as defined by EU MDR (EU 2017/745) Article 2(1). It has no medical
purpose. It does not diagnose, monitor, predict, treat or alleviate disease, and it makes no clinical
interpretation of anything it stores. Under MDCG 2019-11 it is general-purpose software, comparable to a
units library or a materials database. It has not been CE-marked, cleared or approved by any regulatory
body.

When incorporated into a regulated medical device, Vesalius is classified as SOUP (Software of Unknown
Provenance) under IEC 62304:2006+AMD1:2015. The device manufacturer bears full responsibility for assessing
its suitability for their context of use and for all required verification and validation.

## Data statement

The values in the Vesalius material library are **taken from cited sources**, or are fits to cited data,
labelled by origin. Vesalius warrants that each value is what its source gives (or what its recorded fit
produces), converted correctly to SI, with the specimen, conditions and statistics the record states; and that
each model parameter set reproduces its check points under the family definition it names, and its independent
convention witness where the record has one. Vesalius does **not** warrant that a value describes any
particular patient, tissue sample, phantom batch or device, nor that a source is itself correct or current.
Whether a library value is applicable to a given use is the user's and the manufacturer's judgement.

Many values were measured on specimens that differ from a user's target: another species, another anatomical
site, a cadaver for living tissue, a phantom for tissue. Each record states its specimen per section or field.
Whether a specimen stands in adequately for a target is the user's declaration, which the user's build
records, never the library's.

Some values are drafted with the help of a language model. Each such value says so, with the quote and the
document it was read from, and every value, assisted or not, is checked against its source by a named
reviewer before release.

Library records come in three tiers. A **shipped** record publishes its values. A **reference-only** record
publishes provenance, a locator and an extraction recipe but no values, because the source does not permit
redistribution or its status is unknown; its values are whatever the user fills in from their own copy of
the source, and Vesalius warrants nothing about them. A **private** overlay is an organisation's own data in
the same format, and is entirely theirs.

Biocompatibility fields record test evidence reported for a material. They are never a biocompatibility
assessment or a safety claim, and never a device's status, which belongs to a finished device in its intended
use. A manufacturer performs their own ISO 10993 evaluation.

## Cybersecurity boundary statement (MDCG 2019-16)

Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation beyond
validating records against the record schema. A USD stage can pull in other files through its composition
(sublayers, references, payloads) and through the host's asset resolver, so reading a stage may read any
file that stage names. Every USD layer Vesalius ships is self-contained (no composition arcs, no asset
paths), so reading a library layer reads that file alone. Vesalius itself makes no network requests and
runs no code from the files it reads:
records and family vectors are data, and family reference implementations are code shipped in the package,
never loaded from a record. Loading third-party records and stages, and the security of the asset resolver,
are the responsibility of the integrating application.

## Licence

Vesalius's code is licensed under the Apache License 2.0, which is permissive and includes an express
patent grant. No copyleft obligation follows a product that incorporates it. The material library's data is
under a separate data licence, stated on each record. This is a description, not legal advice.

## Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Family definitions and reference implementations agree | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | golden test vectors |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, fit reproduction, data checks |
| A consumer's own implementation of a family | downstream user | IEC 62304 Clause 5.6 (their own) | the record's check points; the family's golden vectors |
| Choosing a material; declaring its domain, target, mixing rule and picks; accepting differences between specimen and target | downstream user | ASME V&V 40 (model inputs) | the user's input justification and the material input sheet |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

## Commercial boundary

Vesalius is an open-source research tool. It will not seek CE marking and carries no manufacturer liability.
A regulated product that uses it is built by a commercial entity that takes on the QMS, the Notified Body
relationship, post-market surveillance and manufacturer liability, as described in MADDENING's
`DOCUMENTATION_ARCHITECTURE.md` section 2.
