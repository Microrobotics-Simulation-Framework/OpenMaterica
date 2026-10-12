# Vesalius
> *Vesalius* is an open material schema, with an OpenUSD binding, and a Python toolkit for biomedical
> digital twins. It describes substances in and around the human body (tissues and body fluids, the media
> and phantoms that stand in for them, agents introduced into them, and the materials of devices that enter
> or touch them): their fluid, mechanical, acoustic, optical, thermal, dielectric, radiological and magnetic
> properties, with the provenance and uncertainty of every value. It binds them to anatomical geometry, from
> a one-dimensional layered path to a full USD scene. It aims to be one physical foundation for
> high-fidelity solvers (like
> [MIME](https://github.com/Microrobotics-Simulation-Framework/MIME)) and real-time simulators (like
> [NVIDIA Isaac for Healthcare](https://github.com/isaac-for-healthcare)).
>
> Records are plain files any language can read; USD is the primary binding but never required. Model
> parameter sets name a versioned model family and carry check points, so a solver that reads them in the
> wrong convention fails loudly instead of silently.

## Scope

Vesalius describes substances, never systems: not an apparatus or its calibration, not the quantities of one
object (its moment, inertia or mean density), not a drive, a procedure or a simulator's tuning. A value
belongs here if it would hold for another object made of the same substance under the same conditions.
Geometry is scene data: Vesalius defines how geometry binds to materials and ships small test phantoms, never
anatomy. Other publishers can use the same machinery in their own namespaces, for data Vesalius does not
curate. The full statement is in [`docs/regulatory/intended_use.md`](docs/regulatory/intended_use.md).

## Status

Design stage. There is no code or release yet. The architecture concept is in
[`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md).

## Intended use and disclaimers

> **Vesalius is research software.** It is not a medical device as defined by EU MDR (EU 2017/745) or US FDA
> regulations. It has no medical purpose and has not been CE-marked, cleared or approved by any regulatory
> body. When used as a component within regulated medical software, Vesalius is SOUP (Software of Unknown
> Provenance) under IEC 62304, and the device manufacturer is responsible for assessing its suitability.
>
> Material values in the Vesalius library are taken from cited sources, or are fits to cited data. They are
> not measurements of any particular patient, sample or device; each record states the specimen it was
> measured on, and whether that specimen stands in for yours is your declaration, not the library's.
> Biocompatibility fields are never a safety claim. See
> [`docs/regulatory/intended_use.md`](docs/regulatory/intended_use.md).

## Documentation

| Document | Description |
|---|---|
| [design/ARCHITECTURE_DRAFT.md](design/ARCHITECTURE_DRAFT.md) | Architecture concept: components, data model, model families, geometry and USD binding, library and licensing, MIME and Isaac for Healthcare interfaces |
| [DOCUMENTATION_ARCHITECTURE.md](DOCUMENTATION_ARCHITECTURE.md) | How Vesalius is documented and verified, and its SOUP readiness |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Project constraints (including commit sign-off), identifiers, family and data rules, data attestation, takedown, anomaly lifecycle |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [docs/regulatory/](docs/regulatory/) | Intended use and regulatory boundary |
| [docs/validation/](docs/validation/) | Known anomalies registry |

## License

Code: Apache License 2.0. See [LICENSE](LICENSE). The curated material library will be released
separately, as static archived releases with a DOI, under CC0-1.0.
