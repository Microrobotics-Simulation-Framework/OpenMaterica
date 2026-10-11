# Contributing to Vesalius

Vesalius is at the design stage. These rules apply from the first code commit; the reasons for them are in
[`DOCUMENTATION_ARCHITECTURE.md`](DOCUMENTATION_ARCHITECTURE.md), section 15.

## Constraints

1. **Sign off every commit.** Use `git commit -s`. The sign-off certifies the
   [Developer Certificate of Origin](https://developercertificate.org/): you wrote the change, or have the
   right to submit it under Apache-2.0. A pull request with an unsigned commit is not merged. The design
   commits made before the first code are exempt.
2. **Apache-2.0 only.** Every contribution is licensed Apache-2.0. Do not add a runtime dependency under a
   copyleft licence.
3. **No simulator or ML-framework dependency at runtime.** Not MIME, MADDENING, JAX, PyTorch, Warp or Isaac.
   The core depends on numpy only. USD is an optional extra (`pip install vesalius[usd]`), and code must work
   with whatever USD build is installed, including the one Isaac Sim ships.
4. **Keep the read side implementable with USD alone.** Compute on the write side and store the result.
   Readers only read numbers, interpolate tables, evaluate power laws and apply declared mixing rules.
5. **SI units in stored values.** Convert in importers and adapters, never in the stored data.
6. **No value without provenance** (see "Adding or changing a library material").
7. **The specification is normative.** A change to it needs conformance cases in the same pull request.
8. **Do not hand-edit generated files.** Material data sheets are generated from the library.
9. **No claims beyond the data.** Library values are declarations from cited sources. Biocompatibility
   fields are never a safety claim. Do not describe a value as validated for a patient.
10. **Never delete an anomaly entry.** Resolve it.
11. **No network access and no code execution from data**, at import or when reading files.
12. **Keep the anomaly registry in MADDENING's schema.** Do not add fields. CI checks it with MADDENING's
    validator, which is a development-time dependency only; nothing in the package imports MADDENING. The
    registry's version field is `vesalius_version`, which MADDENING's validator does not accept yet
    (`DOCUMENTATION_ARCHITECTURE.md` section 8.1).

## Identifier prefixes

| Category | Format | Example |
|---|---|---|
| Anomalies | `VES-ANO-XXX` | `VES-ANO-001` |
| Verification items | `VES-VER-XXX` | `VES-VER-001` |
| Library materials | `VES-MAT-XXXX` | `VES-MAT-0001` |
| Methods | `VES-MTH-XXX` | `VES-MTH-001` |

The prefix `VES` is distinct from `MADD` (MADDENING), `MIME` and `MBOT` (MICROBOTICA).

## Commit messages

Prefixes as in MADDENING and MIME, plus two:

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
| `schema:` | a change to the specification or the USD schema |
| `data:` | a change to the material library |

## Changing the schema

One pull request carries all of: the specification text in `docs/specification/`, the conformance cases,
the USD schema files, the reader change, an entry in `docs/specification/changes.md`, and a CHANGELOG entry
under **Schema**. The version rules are in `DOCUMENTATION_ARCHITECTURE.md` section 7.

## Adding or changing a library material

Every value needs: its kind (declared, measured, fitted or derived); a source as a `[@Key]` in
`docs/bibliography.bib` with a locator (table, figure, page or equation); the conditions the source states;
a range with its basis, or the reason there is none; and a review record (who checked the value against the
source, and when). Agreement with another database is not a review.

A change is recorded under **Data** in the CHANGELOG with a new material version. A value that faithfully
transcribes a source later found wrong is a data update, not an anomaly.

## Anomaly lifecycle

Adopted from MADDENING unchanged (its `CONTRIBUTING.md` and `DOCUMENTATION_ARCHITECTURE.md` section 9.7).

1. **Discovery.** Open an issue with the anomaly template (`.github/ISSUE_TEMPLATE/anomaly.yml`). Fill in
   severity, safety relevance and its rationale, affected components, affected versions and any workaround.
   Apply `anomaly:critical`, `anomaly:major` or `anomaly:minor`, and `safety-relevant` where it applies.
2. **Formalisation.** Add an entry to `docs/validation/known_anomalies.yaml` by hand. This is a deliberate
   review step and is never automated.
3. **Verification.** When resolved, set the status and version, and cite the test that shows the fix.

Severity follows MADDENING's definitions; `DOCUMENTATION_ARCHITECTURE.md` section 8.2 applies them to data.
**A silent wrong result is never `minor`.** A library value that differs from its source is a silent wrong
result.

Name affected components without adding fields: `schema:<API name>`, `reader:<function>`,
`method:<VES-MTH id>`, `data:<VES-MAT id>`.

Every defect a release carried gets an entry. Every `critical` or `major` defect found during a development
cycle gets one, even if no release carried it.

## Release gate

As MADDENING's: a `safety-relevant`, `critical` or `major` anomaly closed in a release must be in the
registry before that release is tagged; a `minor` one within two release cycles.
