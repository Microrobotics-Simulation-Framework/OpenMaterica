# Vesalius specification

**Status: draft for schema version 0.1.0.** Nothing here is stable until schema 1.0.0. Written 2026-10-12 from
the architecture draft (`design/ARCHITECTURE_DRAFT.md`, cited as AD) after five prototypes and two reviews.

This specification is **normative**. It says what a record contains, what a reader must do with it, and what
a consumer declares. It does not say why: the reasons are in the AD, cited by section. Where the Python
package and this text disagree, the package is wrong (`DOCUMENTATION_ARCHITECTURE.md` section 4).

## Documents

Read them in this order.

| Document | Defines |
|---|---|
| `record_format.md` | records: the envelope, record types, the material body, value fields and the seven value forms, units, identifiers, versions and the content hash |
| `provenance.md` | where a value came from: origin, source registry, locators, evidence, review; conditions and specimen facts; tiers |
| `uncertainty.md` | statistics and what a spread represents; uncertainty structures; sampling |
| `model_families.md` | what a family definition fixes; parameter sets; check points; witnesses; events |
| `fits_and_reference_data.md` | fit records; reference data; fit reproduction |
| `geometry.md` | scene documents: the scene manifest, layered paths, label mappings; regions, domains, precedence |
| `usd_binding.md` | the same in USD: API schemas, envelope attributes, bindings, overlays, layered paths, units |
| `mixing_rules.md` | identities and named rules for cells holding more than one material |
| `declarations.md` | what a consumer declares, the three results of a check, and the material input sheet |
| `read_side_contract.md` | the read procedure in order, every refusal, and what an evaluator reports |
| `changes.md` | schema versions |

## Conventions

- **Key words.** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as in RFC 2119 and RFC 8174 (recalled):
  only in capitals do they carry that meaning.
- **Every normative statement carries a case.** A bracketed identifier such as [PR-012] names the
  conformance case that tests the statement; `[not yet covered]` marks a statement with no case yet. Each
  document ends with a table of its cases. A case is a data file under `data/conformance/<profile>/` holding
  its inputs and its expected result, so a reader in any language can run it (`DOCUMENTATION_ARCHITECTURE.md`
  section 6.1).
- **JSON.** Records and scene documents are JSON (RFC 8259), UTF-8, with no duplicate member names and no
  NaN or infinity, as I-JSON requires (RFC 7493, recalled). Numbers are IEEE 754 double precision.
- **Units.** Every stored value is in SI. A field registers exactly one unit, written as a UCUM case-sensitive
  code (recalled: for example `kg/m3`, `Pa.s`, `Np/m`, `1` for a dimensionless value).
- **Statuses.** Where a member has no ordinary value it holds `{"status": <token>}`, with one of five
  tokens: `unstated`, `not_checked`, `none`, `not_applicable` and `withheld` (`provenance.md` section 1).
  Nothing is ever left empty or null to mean one of these.
- **Refuse.** "Refuse" means the reader returns the result `not_met` with a reason, never a value, and never
  stops with an error. "Unknown" means the result `unknown`, which carries the value where the record holds
  one (`declarations.md`).
- **Identifiers** (`record_format.md` section 7):
  - a namespace is `[a-z0-9_]+`;
  - a record is `<namespace>/<local id>`;
  - a family is `<namespace>.<path>.v<N>`;
  - a namespaced record type is `<namespace>:<type>`.

## Profiles and case numbers

A reader claims conformance by naming the schema version and the profiles it passes. A reader with only a
JSON parser can claim plain read without running any USD case.

| Prefix | Profile | Who needs it |
|---|---|---|
| PR | plain read | every reader |
| UR | USD read | readers that take records from a USD stage |
| TE | table evaluation | readers that evaluate tables or power laws in their own code, and report derivatives |
| MX | mixing | consumers that mix materials in a cell |
| FE | family evaluation | consumers that evaluate model parameter sets |
| SA | sampling | consumers that sample uncertainty |
| BC | build checks | consumers that check declarations at build (`declarations.md`) |
| RC | record checks | `vesalius check` and any other checker of records, on the write side |

Numbers are reserved by document, so each document can add cases without colliding:

| Document | Ranges |
|---|---|
| `record_format.md` | PR-001 to PR-099; RC-001 to RC-019 |
| `provenance.md` | PR-100 to PR-149; RC-020 to RC-049 |
| `uncertainty.md` | PR-150 to PR-199; SA-001 to SA-049; RC-050 to RC-059 |
| `fits_and_reference_data.md` | PR-200 to PR-249; RC-080 to RC-089 |
| `geometry.md` | PR-250 to PR-299; RC-090 to RC-099 |
| `read_side_contract.md` | PR-300 to PR-349; TE-001 to TE-049 |
| `model_families.md` | FE-001 to FE-049; RC-060 to RC-079 |
| `usd_binding.md` | UR-001 to UR-099; RC-100 to RC-119 |
| `mixing_rules.md` | MX-001 to MX-049 |
| `declarations.md` | BC-001 to BC-049 |

## What 0.1.0 covers

Schema 0.1.0 is the minimal set of the AD's phasing (section 12.1, M1 to M10): plain records with the
envelope, the bulk, fluid, magnetic and biocompatibility sections, five of the seven value forms in use
(constant, sampled table, power law, interval, composition), provenance, conditions, statistics, the reader
and its refusals, declarations and the three results, and `vesalius check`. The other two forms (model
parameter set, reference data), families, the USD binding, scene documents and mixing are specified here so
that 0.1.0's records do not have to change when they arrive, and their profiles are optional until the minor
version that brings their first consumer (AD 12.2).
