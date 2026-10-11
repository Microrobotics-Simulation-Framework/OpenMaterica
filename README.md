# Vesalius
> *Vesalius* is an OpenUSD material schema and Python toolkit for biomedical digital twins. It binds acoustic, optical, thermal, and fluid properties directly to anatomical geometry, providing a unified physical foundation for high-fidelity solvers (like [MIME](https://github.com/Microrobotics-Simulation-Framework/MIME) and real-time simulators (like [NVIDIA Isaac for Healthcare](https://github.com/isaac-for-healthcare)).

## Status

Design stage. There is no code or release yet. The architecture concept is in
[`design/ARCHITECTURE_DRAFT.md`](design/ARCHITECTURE_DRAFT.md).

## Intended use and disclaimers

> **Vesalius is research software.** It is not a medical device as defined by EU MDR (EU 2017/745) or US FDA
> regulations. It has no medical purpose and has not been CE-marked, cleared or approved by any regulatory
> body. When used as a component within regulated medical software, Vesalius is SOUP (Software of Unknown
> Provenance) under IEC 62304, and the device manufacturer is responsible for assessing its suitability.
>
> Material values in the Vesalius library are declarations taken from cited sources. They are not
> measurements of any particular patient, sample or device, and biocompatibility fields are never a safety
> claim. See [`docs/regulatory/intended_use.md`](docs/regulatory/intended_use.md).

## Documentation

| Document | Description |
|---|---|
| [design/ARCHITECTURE_DRAFT.md](design/ARCHITECTURE_DRAFT.md) | Architecture concept: layers, data model, USD form, MIME and Isaac for Healthcare interfaces |
| [DOCUMENTATION_ARCHITECTURE.md](DOCUMENTATION_ARCHITECTURE.md) | How Vesalius is documented and verified, and its SOUP readiness |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Project constraints (including commit sign-off), identifiers, anomaly lifecycle |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [docs/regulatory/](docs/regulatory/) | Intended use and regulatory boundary |
| [docs/validation/](docs/validation/) | Known anomalies registry |

## License

Apache License 2.0. See [LICENSE](LICENSE).
