<h1 align="center"><img src="https://raw.githubusercontent.com/Microrobotics-Simulation-Framework/OpenMaterica/main/assets/images/logo.png" alt="OpenMaterica" width="70%"></h1>

[![CI](https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/pypi/v/openmaterica?include_prereleases)](https://pypi.org/project/openmaterica/)
[![Code licence: Apache-2.0](https://img.shields.io/pypi/l/openmaterica?label=code%20licence)](https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/blob/main/LICENSE)

> *OpenMaterica* is an open material schema, with an OpenUSD binding, and a Python toolkit for biomedical
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

OpenMaterica describes substances, never systems: not an apparatus or its calibration, not the quantities of
one object (its moment, inertia or mean density), not a drive, a procedure or a simulator's tuning. A value
belongs here if it is a substance's, measured on a test specimen whose shape and size are recorded; a value
of a made object as built (a device, an assembled robot) belongs to its consumer.
Geometry is scene data: OpenMaterica defines how geometry binds to materials and ships small test phantoms,
never anatomy. Other publishers can use the same machinery in their own namespaces, for data OpenMaterica does
not curate. The full statement is in [`docs/regulatory/intended_use.md`](docs/regulatory/intended_use.md).

## Status

Pre-release. `0.1.0.dev1` is on [PyPI](https://pypi.org/project/openmaterica/). It holds strict JSON, the
content hash, records and the read up to step 5, and the schemas and vocabulary of 0.1. Reading values arrives
in later steps, and the schema 0.1 files may change until 0.1.0 is released. The curated material library does
not exist yet. The architecture concept is in [`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md).

## Install

```sh
pip install openmaterica==0.1.0.dev1
```

It needs Python 3.11 or later. To check where a release came from, verify its PyPI attestation (PEP 740), which
names the repository that built it:

```sh
uvx pypi-attestations verify pypi \
  --repository https://github.com/Microrobotics-Simulation-Framework/OpenMaterica \
  pypi:openmaterica-0.1.0.dev1-py3-none-any.whl
```

The command prints `OK` for a file built from this repository, and fails for any other repository.

## Intended use and disclaimers

> **OpenMaterica is research software.** It is not a medical device as defined by EU MDR (EU 2017/745) or US
> FDA regulations. It has no medical purpose and has not been CE-marked, cleared or approved by any regulatory
> body. When used as a component within regulated medical software, OpenMaterica is SOUP (Software of Unknown
> Provenance) under IEC 62304, and the device manufacturer is responsible for assessing its suitability.
>
> Material values in the OpenMaterica library are taken from cited sources, or are fits to cited data. They
> are not measurements of any particular patient, sample or device; each record states the specimen it was
> measured on, and whether that specimen stands in for yours is your declaration, not the library's.
> Biocompatibility fields are never a safety claim. See
> [`docs/regulatory/intended_use.md`](docs/regulatory/intended_use.md).

## Documentation

| Document | Description |
|---|---|
| [docs/user_guide/quickstart.md](docs/user_guide/quickstart.md) | Quickstart: write a record and read a value from it; this release reads constants, intervals, compositions and evidence, and alternatives with no pick, not yet tables or picks |
| [examples/](examples/) | Three example records, cited (water, NdFeB grade N45, human blood plasma): examples, not reviewed library data, not yet fully human-reviewed, and they may change in a later commit |
| [design/ARCHITECTURE_DRAFT.md](design/ARCHITECTURE_DRAFT.md) | Architecture concept: components, data model, model families, geometry and USD binding, library and licensing, MIME and Isaac for Healthcare interfaces |
| [DOCUMENTATION_ARCHITECTURE.md](DOCUMENTATION_ARCHITECTURE.md) | How OpenMaterica is documented and verified, and its SOUP readiness |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Project constraints (including commit sign-off), code rules, identifiers, family and data rules, data attestation, takedown, anomaly lifecycle |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [docs/regulatory/](docs/regulatory/) | Intended use and regulatory boundary |
| [docs/validation/](docs/validation/) | Known anomalies registry |

## License

Code: Apache License 2.0. See [LICENSE](LICENSE). The curated material library will be released
separately, as static archived releases with a DOI, under CC0-1.0.
