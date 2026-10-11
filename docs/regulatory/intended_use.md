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

The values in the Vesalius material library are **declarations taken from cited sources**. Vesalius
warrants that each value is what its source gives, converted correctly to SI, with the conditions and range
the source reports. Vesalius does **not** warrant that a value describes any particular patient, tissue
sample, phantom batch or device, nor that a source is itself correct or current. Whether a library value is
applicable to a given use is the user's and the manufacturer's judgement.

Biocompatibility fields are information about what has been reported for a material. They are never a
biocompatibility assessment or a safety claim. A manufacturer performs their own ISO 10993 evaluation.

## Cybersecurity boundary statement (MDCG 2019-16)

Vesalius assumes trusted input files. It performs no authentication, authorisation or sanitisation. A USD
stage can pull in other files through its composition (sublayers, references, payloads) and through the
host's asset resolver, so reading a stage may read any file that stage names. Vesalius itself makes no
network requests and runs no code from the files it reads. Loading third-party stages, and the security of
the asset resolver, are the responsibility of the integrating application.

## Licence

Vesalius is licensed under the Apache License 2.0, which is permissive and includes an express patent grant.
No copyleft obligation follows a product that incorporates it. This is a description, not legal advice.

## Layered responsibility model

| Responsibility | Owner | Standard | Evidence |
|---|---|---|---|
| Specification and read-side correctness | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | conformance suite |
| Fidelity of library values to their sources, and their units | Vesalius | IEC 62304 Clause 5.6 (via SOUP assessment) | transcription review records, data checks |
| Choosing a material and judging its applicability | downstream user | ASME V&V 40 (model inputs) | the user's input justification |
| Calculation verification of a simulation | downstream user | ASME V&V 40 | the simulator's own evidence |
| SOUP assessment of Vesalius | device manufacturer | IEC 62304 Clauses 5.3.3, 5.3.4, 7.1.3 | Vesalius SOUP package and anomaly registry |
| Risk management, clinical evidence, submission | device manufacturer | ISO 14971, EU MDR | the manufacturer's files |

## Commercial boundary

Vesalius is an open-source research tool. It will not seek CE marking and carries no manufacturer liability.
A regulated product that uses it is built by a commercial entity that takes on the QMS, the Notified Body
relationship, post-market surveillance and manufacturer liability, as described in MADDENING's
`DOCUMENTATION_ARCHITECTURE.md` section 2.
