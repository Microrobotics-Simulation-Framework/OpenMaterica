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
4. **Keep the read side implementable without Vesalius code**, with a JSON parser or with USD. Compute on
   the write side and store the result. Readers only read numbers, interpolate tables, evaluate power laws,
   apply declared mixing rules, and evaluate model families with their own implementations after verifying
   check points.
5. **SI units in stored values.** Convert in importers and adapters, never in the stored data. Store
   parameter sets only in their family's convention; conversion to a solver's convention belongs in an
   adapter or exporter, with vectors.
6. **No value without provenance** (see "Adding or changing a library material").
7. **The specification is normative.** A change to it needs conformance cases in the same pull request.
8. **Do not hand-edit generated files.** USD layers, material cards and the index are generated from the
   plain records.
9. **No claims beyond the data.** Library values are declarations from cited sources, or fits to cited
   data. Biocompatibility fields are never a safety claim. Do not describe a value as validated for a
   patient.
10. **Never delete an anomaly entry.** Resolve it.
11. **No network access and no code execution from data**, at import or when reading files.
12. **Keep the anomaly registry in MADDENING's schema.** Do not add fields. CI checks it with MADDENING's
    validator, which is a development-time dependency only; nothing in the package imports MADDENING. The
    registry's version field is `vesalius_version`, which MADDENING's validator does not accept yet
    (`DOCUMENTATION_ARCHITECTURE.md` section 8.1).
13. **Fail closed.** Readers refuse an unknown family or version, a failed check point, or a request to
    sample an undeclared uncertainty structure. Never add a fallback that guesses.
14. **Check points on every model parameter set**, computed by the family's reference implementation.
    Never type them in.
15. **Family versions are frozen.** Any change to a released definition or its vectors is a new version.
16. **Ship nothing non-redistributable.** A value from a source whose redistribution status is not
    permitted, or is unknown, is reference-only. Every pull request that adds data carries the data
    attestation.
17. **Data and code licences are separate.** Library records are under the library's data licence, stated
    on each record.
18. **Shipped USD layers are self-contained**: no composition arcs and no asset paths.
19. **Static releases.** No feature may require a hosted service, and nothing is fetched from the network
    unless the user asks.

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

- a `definition.md` following `DOCUMENTATION_ARCHITECTURE.md` section 5.2: kinematics and outputs,
  equations, parameters with units, admissibility, references, and the known conventions elsewhere;
- golden test vectors as data files, including edge cases and admissibility cases, with their precision;
- a reference implementation in plain numpy, written for clarity, that reproduces the vectors;
- a **named consumer**: who needs the family, and for what.

The identifier is namespaced and versioned. Publishing under `vesalius.` is for families this project
maintains; anyone may publish families in their own namespace under the same rules. A released version
never changes: a correction is a new version, and the old one is deprecated with a pointer to it. A family
with no consumer for two releases is deprecated. Record the change under **Families** in the CHANGELOG.

## Adding or changing a library material

Every value needs (the full standard is `DOCUMENTATION_ARCHITECTURE.md` section 5.3):

- its **kind**: declared, measured, fitted or derived;
- a **source** as a key in the source registry, with a locator (table, figure, page or equation);
- the **extraction** method: table, text, digitised figure (with the tool and an estimate of digitising
  error), supplementary dataset (with its licence), own measurement, derivation or fit;
- the **conditions** the source states, from the conditions vocabulary;
- **statistics** for a scalar (specimens and donors, mean, standard deviation, minimum, maximum, basis; at
  least a range with its basis), or an **uncertainty structure** for a parameter set (`ensemble`,
  `multivariate_normal`, `independent` with a justification, or `none`), or the reason there is none;
- for a parameter set, **check points** baked by the family's reference implementation; for a fit, the
  **fit record** (reference data, procedure, coverage, residual);
- a **proxy** declaration, per section or field: none, or what it stands in for and why;
- a **tier**: shipped, reference-only or private;
- a **review record**: who checked the value against the source, when, and their ORCID. Agreement with
  another database is not a review.

Every material also needs the prose its card shows (architecture draft section 6.6): why it was curated and
for which consumer, its uses and limitations, and who maintains it. Write it in the record; the card is
generated.

Rules for data:

- Extract from primary literature. Never copy a secondary database in bulk.
- Check the source's redistribution status in the source registry before shipping a value. If there is no
  entry, add one; if the status is not permitted or unknown, the value is reference-only: publish the
  provenance, the locator and an extraction recipe, not the value.
- Fits you make yourself from published curves are your own work and can usually be shipped even when the
  curves stay reference-only. Say so in the fit record.
- Own measurements published under an open licence are welcome and are the cleanest data the library can
  hold.

Run `python -m vesalius check` before opening a pull request; CI runs it too.

You do not need the curated library to publish records. Keep them in your own repository under your own
namespace and run the same `vesalius check`. Once an index of namespaces exists, listing in it is by pull
request (architecture draft section 6.7).

A change is recorded under **Data** in the library's CHANGELOG with a new material version. A value that
faithfully transcribes a source later found wrong is a data update, not an anomaly.

### Data attestation

Every pull request that adds or changes library data includes this statement, ticked, in the pull-request
template:

> I attest that each value in this pull request was extracted from the cited source by the method recorded
> for it, or comes from a measurement or fit I describe; that nothing was copied in bulk from a secondary
> database; that each value's tier matches its source's redistribution status in the source registry; and
> that I have the right to contribute the shipped values under the library's data licence.

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
