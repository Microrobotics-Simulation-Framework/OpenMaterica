# Contributing to Vesalius

Vesalius is at the design stage. These rules apply from the first code commit; the reasons for them are in
[`DOCUMENTATION_ARCHITECTURE.md`](DOCUMENTATION_ARCHITECTURE.md), section 15. The material library will
live in a repository of its own; until it exists, its rules are kept here.

## Constraints

1. **Sign off every commit.** Use `git commit -s`. The sign-off certifies the
   [Developer Certificate of Origin](https://developercertificate.org/): you wrote the change, or have the
   right to submit it under Apache-2.0. A pull request with an unsigned commit is not merged. The design
   commits made before the first code are exempt.
2. **Apache-2.0 for code.** Every code contribution is licensed Apache-2.0. Do not add a runtime dependency
   under a copyleft licence.
3. **No simulator or ML-framework dependency at runtime.** Not MIME, MADDENING, JAX, PyTorch, Warp or Isaac.
   The core depends on numpy and a JSON Schema validator only. USD is an optional extra
   (`pip install vesalius[usd]`), and code must work with whatever USD build is installed, including the one
   Isaac Sim ships.
4. **Keep the read side implementable without Vesalius code**, with a JSON parser or with USD. Compute on the
   write side and store the result. Readers only read numbers, interpolate tables, evaluate power laws, apply
   the mixing rules their consumer declared, and evaluate model families with their own implementations after
   verifying check points.
5. **SI units in stored values.** Convert in importers and adapters, never in the stored data. Store
   parameter sets only in their family's convention; conversion to a solver's convention belongs in an
   adapter or exporter, with vectors.
6. **No value without provenance** (see "Adding or changing a library material").
7. **The specification is normative.** A change to it needs conformance cases in the same pull request.
8. **Do not hand-edit generated files.** USD layers, material cards and the index are generated from the
   plain records.
9. **No claims beyond the data.** Library values are taken from cited sources, or are fits to cited data,
   labelled by origin. Biocompatibility fields record test evidence, never a safety claim or a device's
   status. Do not describe a value as validated for a patient, or as suited to any use.
10. **Never delete an anomaly entry.** Resolve it.
11. **No network access and no code execution from data**, at import or when reading files.
12. **Keep the anomaly registry in MADDENING's schema.** Do not add fields. CI checks it with MADDENING's
    validator, which is a development-time dependency only; nothing in the package imports MADDENING. The
    registry's version field is `vesalius_version`, which MADDENING's validator does not accept yet
    (`DOCUMENTATION_ARCHITECTURE.md` section 8.1).
13. **Fail closed.** Readers refuse an unknown family or version, a failed check point, a request to
    sample an undeclared uncertainty structure, an attribute that was not authored, and interpolation across
    an edge or outside a range. Never add a fallback that guesses.
14. **Check points and a convention witness on every model parameter set.** Check points are computed by
    the family's reference implementation; never type them in. The witness is a response the source itself
    reports, independent of how the parameters were obtained (for a fit, a held-out datum); without one, a
    parameter set is not admitted to the curated library.
15. **Family versions are frozen.** Any change to a released definition or its vectors is a new version.
16. **Ship nothing non-redistributable.** A value from a source whose redistribution status is not
    permitted, or is unknown, is reference-only. Every pull request that adds data carries the data
    attestation.
17. **Data and code licences are separate.** Library records are under the library's data licence, stated
    on each record.
18. **Shipped USD layers are self-contained**: no composition arcs and no asset paths.
19. **Static releases.** No feature may require a hosted service, and nothing is fetched from the network
    unless the user asks.
20. **No model on the read side.** No language model in a reader, in `vesalius check`, in a release build
    or in any consumer's build. Vesalius calls no model and holds no keys.
21. **Quotes and human review.** A value a model helped draft carries its quote, locator, document hash and
    assistance record. No value enters a release without a human review record.
22. **A model never decides** a tier, a redistribution status, a unit conversion, a check point, a witness
    or a fit result.
23. **Records hold facts; consumers declare choices.** No record, card, check or default says where, in what
    state or in which regime a model applies, which stand-in is acceptable, which mixing rule to use beyond
    the identities, or which of competing values wins.
24. **Nothing stands in for a value without saying so.** No fallback values on physical attributes; no
    nominal, distribution or extrapolation the source does not give; an unstated condition is unknown, never
    met; every spread says what it represents.
25. **A check is reported for what it can show.** A witness is independent of how the parameters were
    obtained, or the record says "no independent witness". Check points are not presented as evidence about
    a value. An attestation by an interested party says that it is one.

## Identifier prefixes

| Category | Format | Example |
|---|---|---|
| Anomalies | `VES-ANO-XXX` | `VES-ANO-001` |
| Verification items | `VES-VER-XXX` | `VES-VER-001` |
| Materials | `<namespace>/<local id>`; in the curated library `vesalius/VES-MAT-XXXX` | `vesalius/VES-MAT-0001` |
| Methods | `VES-MTH-XXX` | `VES-MTH-001` |
| Model families | `<namespace>.<section>.<name>.v<N>` | `vesalius.mechanical.ogden_incompressible.v1` |

The prefix `VES` is distinct from `MADD` (MADDENING), `MIME` and `MBOT` (MICROROBOTICA).

## Commit messages

Prefixes as in MADDENING and MIME, plus three:

| Prefix | Meaning |
|---|---|
| `feat:` | new feature |
| `fix:` | bug fix |
| `refactor:` | restructuring, no behaviour change |
| `docs:` | documentation only |
| `test:` | tests |
| `perf:` | performance |
| `verify:` | verification evidence |
| `break:` | breaking change |
| `deprecate:` | deprecation notice |
| `security:` | security-relevant change |
| `schema:` | a change to the specification, the record schema or the USD schema |
| `family:` | a new family version, or a deprecation |
| `data:` | a change to the material library |

## Changing the schema

One pull request carries all of: the specification text in `docs/specification/`, the conformance cases,
the record schema and USD schema files, the reader change, an entry in `docs/specification/changes.md`, and
a CHANGELOG entry under **Schema**. The version rules are in `DOCUMENTATION_ARCHITECTURE.md` section 7.

## Adding a model family

A family is admitted with all of the following, in one pull request:

- a `definition.md` following `DOCUMENTATION_ARCHITECTURE.md` section 5.2: its kind (`static`; an
  `evolution` family is not admitted until that form is specified), kinematics and outputs, equations,
  parameters with units, admissibility, references, and the known conventions elsewhere;
- golden test vectors as data files, including edge cases and admissibility cases, with their precision;
- a reference implementation in plain numpy, written for clarity, that reproduces the vectors;
- a **named consumer**: who needs the family, and for what.

The identifier is namespaced and versioned. Publishing under `vesalius.` is for families this project
maintains; anyone may publish families in their own namespace with the same checks, and needs no admission
from this project. A released version never changes: a correction is a new version, and the old one is
deprecated with a pointer to it. A family with no consumer for two releases is deprecated. Record the change
under **Families** in the CHANGELOG.

**A consumer that cannot be named.** A family under `vesalius.` may be admitted for a consumer that cannot
be named publicly, on three conditions. The maintainer attests that the consumer exists and says nothing
else about it. Where the maintainer also owns that consumer, the attestation certifies itself, and the
admission record says so in those words. And the family reproduces a published dataset end to end (its
witness and a fit), so that every claim in its record can be checked without the consumer: that
reproduction is the check that carries weight. The attestation is renewed each release, or the
two-release deprecation applies. A family that only a private project needs is better published in that
project's own namespace, which needs no admission.

## Adding or changing a library material

Every value needs (the full standard is `DOCUMENTATION_ARCHITECTURE.md` section 5.3):

- its **origin**: measured by the source, measured by you, fitted, derived, or stated without an origin;
- a **source** as a key in the source registry, with a locator (table, figure, page or equation);
- the **extraction** method: table, text, digitised figure (with the tool and an estimate of digitising
  error), supplementary dataset (with its licence), own measurement, derivation or fit;
- the **conditions** as the source states them, from the conditions vocabulary, with any it does not state
  recorded as unstated; the specimen's shape for magnetic values; the test method and specimen geometry
  for failure values;
- for a table or a power law, the **range** it covers; for a table, its **interpolation scheme** and
  **edges**;
- **statistics** for a scalar: specimens and donors, mean, standard deviation, minimum, maximum, basis, and
  what the spread represents (a population, an estimate, measurement error or spread across sources); at
  least a range with its basis; `dispersion: not_reported` if the source gives none; an interval with its
  basis if that is all that is known. For a parameter set, an **uncertainty structure** (`ensemble`,
  `multivariate_normal`, `independent` with a justification, `interval` or `none`) and what it represents;
- for a parameter set, **check points** baked by the family's reference implementation, spanning the fit's
  coverage and the family's branch points, and an **independent witness**: a response the source reports
  that was not used to obtain the parameters, or the flag "no independent witness". For a fit, the **fit
  record** (reference data, procedure, coverage, residual);
- **specimen facts**, per section or field: species, site, state, preparation, shape; for a phantom or a
  substitute, what its maker says it mimics. Do not write what the data is a proxy for: that depends on
  each consumer's target;
- for biocompatibility, the **test evidence** only: endpoint, standard and part, contact category and
  duration tested, material form and processing; never a status;
- a **tier**: shipped, reference-only or private;
- a **review record**: who checked the value against the source, when, and their ORCID, and whether the
  reviewer is independent of whoever, or whatever, extracted it. Agreement with another database is not a
  review.

Every material also needs the prose its card shows (architecture draft section 6.6): why it was curated and
for which consumer, what was measured and what was not, and who maintains it. Do not write that it suits a
use. Write it in the record; the card is generated.

Rules for data:

- Extract from primary literature. Never copy a secondary database in bulk.
- Do not enter numbers found in code or datasheets with nothing behind them as library values. They stay in
  their consumer as declared values until a source replaces them.
- Keep competing values where sources disagree and a consumer's result depends on the choice; do not pick
  one. The consumer picks.
- Check the source's redistribution status in the source registry before shipping a value. If there is no
  entry, add one; if the status is not permitted or unknown, the value is reference-only: publish the
  provenance, the locator and an extraction recipe, not the value.
- Fits you make yourself from published curves are your own work and can usually be shipped even when the
  curves stay reference-only. Say so in the fit record.
- Own measurements published under an open licence are welcome and are the cleanest data the library can
  hold.

Run `python -m vesalius check` before opening a pull request; CI runs it too.

You do not need the curated library to publish records. Keep them in your own repository under your own
namespace and run the same `vesalius check`. The template repository sets that up. To list your namespace,
open a pull request adding one line to the library's `publishers.yaml` (architecture draft section 6.7).

A change is recorded under **Data** in the library's CHANGELOG with a new material version. A value that
faithfully transcribes a source later found wrong is a data update, not an anomaly; consumers that pin the old
version learn of it from the advisory index (architecture draft section 5.6).

### Model-assisted extraction

You may draft values with a language model through the MCP tools (architecture draft section 8), using your
own agent and key. Then:

- record the assistance: tool, model and provider as reported, the procedure's `VES-MTH-` entry and
  version, and the date;
- keep the evidence for every value: the verbatim quote, its locator and the SHA-256 of the document copy.
  Do not publish quotes for reference-only values; a quote contains the value;
- let deterministic tools convert units, bake check points and run fits. Never accept a model's number for
  any of them;
- for a parameter set, attach its independent witness and run the convention checker; the model's guess at
  the family is only a proposal;
- set tiers and redistribution statuses yourself;
- review every value at its locator on the rendered page, not only the quote, and record the checklist;
- before relying on a model, run the procedure against the gold set and look at its per-field errors.

The MCP tools can only write drafts. Opening and merging the pull request are yours.

### Data attestation

Every pull request that adds or changes library data includes this statement, ticked, in the pull-request
template:

> I attest that each value in this pull request was extracted from the cited source by the method recorded
> for it, or comes from a measurement or fit I describe; that every value a language model helped draft is
> recorded as such and was checked by a named reviewer against the source at its locator; that nothing was
> copied in bulk from a secondary database; that each value's tier matches its source's redistribution
> status in the source registry; and that I have the right to contribute the shipped values under the
> library's data licence.

### Takedown

A rights holder who objects to a shipped value or reference dataset can write to
**nick@microrobotica.org**. The request is acknowledged within 5 business days. While it is assessed, the
affected values are moved to reference-only in the next library patch release, and the change is recorded
under **Data** in the library's CHANGELOG. A takedown is not an anomaly: the values are not wrong.

## Anomaly lifecycle

Adopted from MADDENING unchanged (its `CONTRIBUTING.md` and `DOCUMENTATION_ARCHITECTURE.md` section 9.7).

1. **Discovery.** Open an issue with the anomaly template (`.github/ISSUE_TEMPLATE/anomaly.yml`). Fill in
   severity, safety relevance and its rationale, affected components, affected versions and any workaround.
   Apply `anomaly:critical`, `anomaly:major` or `anomaly:minor`, and `safety-relevant` where it applies.
2. **Formalisation.** Add an entry to `docs/validation/known_anomalies.yaml` by hand. This is a deliberate
   review step and is never automated.
3. **Verification.** When resolved, set the status and version, and cite the test that shows the fix.

Severity follows MADDENING's definitions; `DOCUMENTATION_ARCHITECTURE.md` section 8.2 applies them to data
and families. **A silent wrong result is never `minor`.** A library value that differs from its source is a
silent wrong result; so is a reference implementation that differs from its family definition.

Name affected components without adding fields: `schema:<API name>`, `reader:<function>`,
`method:<VES-MTH id>`, `model:<family identifier>`, `data:<VES-MAT id>`.

Every defect a release carried gets an entry. Every `critical` or `major` defect found during a development
cycle gets one, even if no release carried it.

## Release gate

As MADDENING's: a `safety-relevant`, `critical` or `major` anomaly closed in a release must be in the
registry before that release is tagged; a `minor` one within two release cycles.
