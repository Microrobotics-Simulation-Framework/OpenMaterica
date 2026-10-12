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
| `record_format.md` | records: the envelope, record types, the material body, value fields and the eight form tokens (the seven value forms of AD 4.4, and evidence), units, identifiers, versions and the content hash |
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
  document ends with a table of its cases. Until its data file exists, a case is planned, not run: the files
  are written with the first implementation (section "Case files").
- **JSON.** Records and scene documents are JSON (RFC 8259), UTF-8, with no duplicate member names and no
  NaN or infinity, as I-JSON requires (RFC 7493, recalled). Numbers are IEEE 754 double precision. `null` is
  never used.
- **Units.** Every stored value is in SI. A field, and a condition, registers exactly one unit, written as a
  UCUM case-sensitive code (for example `kg/m3`, `Pa.s`, `/m`, `1` for a dimensionless value), or
  `{"status": "not_applicable"}` for a field with no unit (`biocompatibility.evidence`).
- **Status objects.** Where a member has no ordinary value it holds a status object: an object whose only
  members are `status`, with one of five tokens, and optionally `reason`, a text. The tokens are `unstated`,
  `not_checked`, `none`, `not_applicable` and `withheld` (`provenance.md` section 1). A member named `status`
  in any other object is not a status object and has its own tokens, and every other object avoids the name.
- **Results.** A read gives `met`, `not_met` or `unknown`, with a list of reason codes
  (`read_side_contract.md`). "Refuse" means the result `not_met`, never an error. "Unknown" carries the value
  where the record holds one. Under a declared extrapolation or nominal, the status stays `not_met`, the value
  is present, and the result names the declaration it rests on.
- **Identifiers** (`record_format.md` section 7):
  - a namespace is `[a-z0-9_]+`;
  - a record is `<namespace>/<local id>`;
  - a family is `<namespace>.<segment>(.<segment>)*.v<N>`.

## Versions and stability

- Before 1.0.0, a reader reads only records of its own `MAJOR.MINOR`; every other version is refused
  (`record_format.md` section 8). Consumers pin exact versions anyway (AD 12.4). From 1.0.0, a reader reads a
  newer minor version by the additive rules of `record_format.md` section 10.
- Every member and field in schema 0.1.0 is **experimental**: it may change in the next minor version. Later
  versions mark each field `provisional` or `stable` (`DOCUMENTATION_ARCHITECTURE.md` section 7.3).
- Each version has a closed **writer schema** and an open **reader schema**, as JSON Schema files in `schema/`
  (`record_format.md` section 1). They are written with the first implementation; until then the tables of
  this specification define the shapes.

## Profiles and case numbers

A reader claims conformance by naming the schema version and the profiles it passes. Plain read needs a JSON
parser and the reader schema's checks, which are structural and can be written by hand; every reader compares
a record's stated hash with any pin. Recomputing content hashes also needs an RFC 8785 serialiser and SHA-256
(profile HS). No profile requires another, but a reader without HS labels its results `hash_not_checked`.

| Prefix | Profile | Who needs it |
|---|---|---|
| PR | plain read | every reader |
| HS | hash | readers that verify the content hashes of records, and of families (an RFC 8785 serialiser and SHA-256) |
| SC | scene documents | readers of plain scene manifests, layered paths and label mappings |
| FD | fits and reference data | readers of fit records, coverage and reference data |
| UR | USD read | readers that take records from a USD stage |
| TE | table evaluation | consumers that evaluate tables or power laws in their own code and report derivatives |
| MX | mixing | consumers that mix materials in a cell |
| FE | family evaluation | consumers that evaluate model parameter sets |
| SA | sampling | consumers that sample uncertainty |
| BC | build checks | consumers that check declarations at build (`declarations.md`) |
| RC | record checks | `vesalius check` and any other checker of records, on the write side |

Numbers are reserved by document, so each document can add cases without colliding:

| Document | Ranges |
|---|---|
| `record_format.md` | PR-001 to PR-099; HS-001 to HS-009; RC-001 to RC-019; RC-120 to RC-139 |
| `provenance.md` | PR-100 to PR-149; RC-020 to RC-049 |
| `uncertainty.md` | PR-150 to PR-199; SA-001 to SA-049; FE-040 to FE-049; RC-050 to RC-059 |
| `fits_and_reference_data.md` | FD-001 to FD-049; RC-080 to RC-089 |
| `geometry.md` | SC-001 to SC-049; RC-090 to RC-099 |
| `read_side_contract.md` | PR-300 to PR-349; HS-010 to HS-019; TE-001 to TE-049 |
| `model_families.md` | FE-001 to FE-039; RC-060 to RC-079 |
| `usd_binding.md` | UR-001 to UR-099; RC-100 to RC-119 |
| `mixing_rules.md` | MX-001 to MX-049 |
| `declarations.md` | BC-001 to BC-049 |

## Case files

A case is one JSON file, `data/conformance/<profile>/<case id>.json`:

```json
{"case": "PR-305", "profile": "plain_read", "schema_version": "0.1.0",
 "inputs": {"records": ["water.json"]},
 "request": {"target": {"record": {"id": "vesalius/VES-MAT-0002", "version": "1.0.0",
                                   "content_hash": "sha256:..."},
                        "field": "fluid.dynamic_viscosity"},
             "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
             "requirement": {"want": "value",
                             "conditions": {"temperature": {"tolerance": {"value": 1.0, "unit": "K"}}}}},
 "expected": {"status": "unknown", "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
              "value": 0.000692},
 "compare": {"members": ["status", "reasons.code", "value"], "relative_tolerance": 1e-12}}
```

`inputs` names the files the case supplies, relative to its directory; `request` is the read request of
`read_side_contract.md` section 1; `expected` holds the members to compare, and `compare` says which, and the
relative tolerance for numbers (absolute where an expected number is zero). Reason codes are compared, reason
texts never. An input the case does not need is omitted. In this example, `water.json` holds the viscosity as
a constant of exactly 0.000692 Pa·s measured at 310.15 K, with its shear rate unstated. `profile` is one of
`plain_read`, `hash`, `scene_documents`, `fits_and_reference_data`, `usd_read`, `table_evaluation`, `mixing`,
`family_evaluation`, `sampling`, `build_checks` and `record_checks`.

## What 0.1.0 covers

Schema 0.1.0 is the minimal set of the AD's phasing (section 12.1, M1 to M10) and, built last, the scene
documents and the USD binding (R1 and R14): plain records with the envelope, the bulk, fluid, magnetic and
biocompatibility sections, the constant, table, interval, composition and evidence forms in use, provenance,
conditions, statistics, the reader and its reasons, declarations and the three results, `vesalius check`, the
plain scene manifest with regions, domains and layered paths, and their USD form. Their cases are planned for
0.1.0. Label volumes, field overrides and the label mapping's USD form wait for the minor version that brings
their first consumer. The other forms (the power law, whose first field arrives with the acoustic section; the
model parameter set; reference data), families and mixing are specified here so that 0.1.0's records do not
have to change when they arrive; their profiles are optional until that version (AD 12.2). Every profile is a
claim a reader chooses to make: a reader of plain records need not claim USD read.
