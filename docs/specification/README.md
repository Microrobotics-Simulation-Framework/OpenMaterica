# OpenMaterica specification

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
| `geometry.md` | scene documents: the scene manifest, layered paths, label crosswalks; regions, domains, precedence |
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
- **JSON.** Records and scene documents are JSON (RFC 8259), UTF-8, with no duplicate member names and no NaN
  or infinity, as I-JSON requires (RFC 7493, recalled). Numbers are IEEE 754 double precision, integers
  included. A reader refuses what breaks these rules as malformed, by the exact list of `record_format.md`
  section 1 item 6. Most JSON libraries need configuring for it: a stock parser call accepts a byte-order
  mark, other encodings, repeated member names or `NaN`, or replaces bad bytes; Python's `json` keeps
  `9007199254740993` exact and reads `-0` as the integer 0; C++'s `strtod` reports a range error on `3e-324`
  although its result is right, and `std::from_chars` reports one on `1e-400` and leaves its output unwritten.
  `null` is never written; how a reader treats one it meets is in `record_format.md` section 1 item 5.
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

## Suites and case numbers

A reader claims conformance by naming the schema version and the suites it passes. Plain read needs a JSON
parser and the reader schema's checks, which are structural and can be written by hand; every reader compares
a record's stated hash with any pin. Recomputing content hashes also needs an RFC 8785 serialiser and SHA-256
(suite HS). No read suite requires another, but a reader without HS labels `hash_not_checked` every result
that reaches the hash step. The EA suite, and the build checks of an engine model (BC-039), also need USD read
and the stage check.

| Prefix | Suite | Who needs it |
|---|---|---|
| PR | plain read | every reader |
| HS | hash | readers that verify the content hashes of records, and of families (an RFC 8785 serialiser and SHA-256) |
| SC | scene documents | readers of plain scene manifests, layered paths and label crosswalks |
| FD | fits and reference data | readers of fit records, coverage and reference data |
| UR | USD read | readers that take records from a USD stage |
| TE | table evaluation | consumers that evaluate tables or power laws in their own code and report derivatives |
| MX | mixing | consumers that mix materials in a cell |
| FE | family evaluation | consumers that evaluate model parameter sets |
| SA | sampling | consumers that sample uncertainty |
| BC | build checks | consumers that check declarations at build (`declarations.md`) |
| RC | record checks | `materica check` and any other checker of records, on the write side; `materica check --stage` |
| EA | engine adapters | writers of engine materials from a declared engine model, by an engine crosswalk (`usd_binding.md` section 10) |

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
| `usd_binding.md` | UR-001 to UR-099; RC-100 to RC-119; RC-140 to RC-159; EA-001 to EA-049 |
| `mixing_rules.md` | MX-001 to MX-049 |
| `declarations.md` | BC-001 to BC-049 |

## Case files

A case is one JSON file, `data/conformance/<suite>/cases/<case id>.json`, or one file per variant,
`cases/<case id>.<variant>.json`, where a case has several arms (below); the files cases supply sit in
`data/conformance/<suite>/inputs/`, each once, however many cases use it. Inputs are byte-exact: a repository
that holds them must not convert their line endings or encodings. Case files themselves follow
`record_format.md` section 1 item 6. The records and documents cases supply are conformance fixtures, in the
namespace `conformance`, and illustrative only (`record_format.md` section 7 item 1).

```json
{"case": "PR-305", "suite": "plain_read", "schema_version": "0.1.0",
 "inputs": {"records": ["water_fixture.json"]},
 "request": {"target": {"record": {"id": "conformance/water_fixture", "version": "1.0.0",
                                   "content_hash": "sha256:..."},
                        "field": "fluid.dynamic_viscosity"},
             "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
             "requirement": {"want": "value",
                             "conditions": {"temperature": {"tolerance": {"value": 1.0, "unit": "K"}}}}},
 "expected": {"status": "unknown", "reasons": [{"code": "condition_unstated", "condition": "shear_rate"}],
              "value": 0.000692},
 "compare": {"members": ["status", "reasons", "value"], "relative_tolerance": 1e-12}}
```

`inputs` names the files the case supplies, relative to the suite's `inputs/`; `request` is the read request
of `read_side_contract.md` section 1, unless it names an `operation` (below); `expected` holds the members to
compare, and `compare` says which, and the relative tolerance for numbers (absolute where an expected number
is zero), or `"exact": true`, under which numbers are compared as doubles bit for bit, so that `-0` differs
from `0` (case files are read by `record_format.md` section 1 item 6, so `-0` in one is negative zero).
Reasons are compared as a multiset of their `code` and `condition`: never their order, `detail` or text.
`labels` are compared as a set, an absent `labels` counting as empty, and without `hash_not_checked` unless
the case's `claims` has a `hash` member. A member `compare` names and `expected` omits must be absent from the
result (an operation's `value` on `not_met`, say). A case that compares a number gives `relative_tolerance` or
`exact`; there is no default. A case whose request must itself break `record_format.md` section 1 item 6
(PR-330) names a file holding it in `inputs.request`, in place of `request`. An input the case does not need
is omitted. In this example, `water_fixture.json` holds, as an illustrative fixture, the viscosity as a
constant of exactly 0.000692 Pa·s at 310.15 K, with its shear rate unstated. `suite` is one of `plain_read`,
`hash`, `scene_documents`, `fits_and_reference_data`, `usd_read`, `table_evaluation`, `mixing`,
`family_evaluation`, `sampling`, `build_checks`, `record_checks` and `engine_adapter`.

**Variants.** A case with several arms (PR-002 has one per fault) is given as variants, one file per arm, each
with a `variant` member, matching `[a-z0-9_]+` in full, that names its file: `PR-002.bom.json`,
`PR-002.trailing_comma.json`. A variant is a case in every other respect, with its own inputs, request,
expected answer and claims.

**Claims.** A runner is given the suites the implementation under test claims, and runs the cases of those
suites only. Where a case's expected answer depends on them, the case says so in `claims`, mapping a suite to
whether the reader claims it (`{"hash": false}`), and holds only for a reader with those claims; a case with
no `claims` holds for any reader that claims the case's own suite. A case whose answer differs by claim has a
variant per claim: PR-327's label arm is `PR-327.label_hs.json` and `PR-327.label_no_hs.json`; its pin arm,
whose answer is the same under both, is `PR-327.pin.json`, with `PR-327.pin_no_hs.json` to show that the
refusal carries no `hash_not_checked`, which only a `hash` claim makes compared. A runner runs only the
variants whose `claims` agree with the suites it is given, and reports the others as not run, separately from
those that passed or failed. A case passes when at least one of its variants ran, every variant that ran
passed, and none failed; a case none of whose variants ran is not run, and never counts as passed.

**Operations.** Two kinds of plain-read and hash case are not reads, and name an `operation` in `request`.
Both give a result shaped as `read_side_contract.md` section 2 defines:
- `{"operation": "content_hash"}` takes the JSON file `inputs.value` names (one file name), reads it by
  `record_format.md` section 1 item 6, checks no envelope, and gives the content hash of its value, whatever
  that value's JSON type (top-level members are removed only from an object) (`record_format.md` section 9) as
  `value`, with the status `met`; a file that breaks item 6 gives `not_met` and `malformed`, and no value. The
  hash vectors are given this way (HS-001 to HS-003);
- `{"operation": "list_records"}` takes `inputs.records` and gives the status `met`, no reasons, and in
  `value` the `{"id", "version"}` of exactly those sources that are candidates (`read_side_contract.md`
  section 3, step 1) and pass steps 2, 3 and 5 on their own, compared as a set. It says nothing of the other
  sources: sources that did not parse, are not candidates or fail those steps, set-aside documents and records
  of a type the reader cannot read among them, are not listed (`record_format.md` section 3) (PR-006).

Three kinds of case take other inputs. Each names the schema files it passes in `inputs.schemas`
(`usd_binding.md` section 10.1 item 8); a case that names none has none.

- A **stage-check case** (`usd_binding.md` section 9) names its stage in `inputs.stage` and the engine
  crosswalks it passes in `inputs.crosswalks`, and has no `request`. `expected.items` lists what the check
  reports, each as `{"item": "<the rule's case id>", "prim": "<path>", "detail"?}`. `expected.listing` gives,
  per shape, `{"shape", "region", "material", "engine_materials", "effective_density"}`: each engine material
  as `{"material", "crosswalks", "crosswalk_status"}`, with `crosswalks` the stamped pin, or the pins of the
  held crosswalks whose APIs an unstamped material carries, and `crosswalk_status` one of `held`, `not_held`
  (stamped), `matched` (they agree on the density attribute), `ambiguous` (they do not) and `unmatched`
  (none); the density a number, or `{"status": "not_checked", "reason"}` where it is not compared.
  `expected.crosswalks_held` lists the pins held, `expected.unrecognised_apis` lists `{"prim", "api"}`, and
  `expected.not_compared` lists `{"crosswalk", "api", "reason"}`.
- A **crosswalk-validation case** (RC-140, RC-142, RC-143) names a crosswalk in `inputs.crosswalk` and has no
  stage and no `request`; `expected.items` lists what the check reports, each as `{"item", "pointer",
  "detail"?}`, with `pointer` a JSON pointer into the crosswalk, and `expected.not_compared` as above.
- An **engine-adapter case** names a stage, a declaration and the engine crosswalks it passes in `inputs`; its
  `request` is `{"model": "<the engine model's name>"}`; and `expected` holds, per shape, the attributes
  written and their values, or the reasons the adapter refused. A build-check case of an engine model
  (BC-039 to BC-041) names the same inputs and expects the build's results.

## What 0.1.0 covers

Schema 0.1.0 is the minimal set of the AD's phasing (section 12.1, M1 to M10) with the scene documents,
layered paths and the USD binding (R1 and R14), built in that order: plain records with the envelope, the
bulk, fluid, magnetic and biocompatibility sections, the constant, table, interval, composition and evidence
forms in use, provenance, conditions, statistics, the reader and its reasons, `materica check`; then the plain
scene manifest with regions, domains, layered paths and label crosswalks, with the helper that derives a
layered path from 3-D geometry (AD 12.1, R14); then declarations and the three results; then the scene
documents' USD form, the stage check, the engine crosswalk with OpenMaterica's one crosswalk (`UsdPhysics`),
and the engine adapter. Their cases are planned for 0.1.0, except the material input sheet's (R7, 0.2); the
scaffold that drafts engine crosswalks is an `openmaterica-authoring` tool, tested there. Label volumes, field
overrides and the label crosswalk's USD form wait for the minor version that brings their first consumer. The
other forms (the power law, whose first field arrives with the acoustic section; the model parameter set;
reference data), families and mixing are specified here so that 0.1.0's records do not have to change when
they arrive; their suites are optional until that version (AD 12.2). Every suite is a claim a reader chooses
to make: a reader of plain records need not claim USD read.
