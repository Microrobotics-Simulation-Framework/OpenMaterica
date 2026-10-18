# Example records

Three records that show what a record holds and how a read uses it, each with its sources cited.

> **Examples, not reviewed library data.** These records are not yet fully human-reviewed, and may change in a
> later commit. They are not the curated material library, which will be released separately
> ([`DOCUMENTATION_ARCHITECTURE.md`](../DOCUMENTATION_ARCHITECTURE.md) section 2), and they do not ship in the
> `openmaterica` wheel.

| File | Record | Field | Value | Conditions | Source |
|---|---|---|---|---|---|
| [`records/water.json`](records/water.json) | `example/water` | `bulk.density` | 998.207 kg/m³; 993.330 kg/m³ | 293.15 K; 310.15 K; 0.101325 MPa | evaluated from IAPWS R6-95(2018) |
| | | `fluid.dynamic_viscosity` | 1.00160 mPa·s; 0.691304 mPa·s | 293.15 K; 310.15 K; 0.101325 MPa; shear rate unstated | evaluated from IAPWS R12-08 |
| [`records/ndfeb_n45.json`](records/ndfeb_n45.json) | `example/ndfeb_n45` | `magnetic.remanence` | 1.32 to 1.37 T, a datasheet's limits | "room temperature", recorded as unstated; specimen shape and test method unstated | supermagnete.de, "Physical Magnet Data" and the data sheet of article W-01-N, accessed 2026-10-17 |
| [`records/human_plasma.json`](records/human_plasma.json) | `example/human_plasma` | `fluid.dynamic_viscosity` | 1.33 mPa·s, "± 0.03" of unstated kind, 25 donors | 310.15 K; shear rate 10 to 100 s⁻¹; rotational rheometer | Marcinkowska-Gapinska and Nawrocka-Bogusz 2013, doi:10.1155/2013/490410, Table 1 (CC BY 3.0) |

Each record's `card` says what it holds and how, and each value's `provenance` names its source, the place in
it and how the value was taken from it. The values are stored in SI units: 1.00160 mPa·s is `0.0010016` Pa·s.

## What a read gives in this release

This release reads a field that holds one constant, an interval, a composition or evidence, and applies a
declared nominal to an interval (`read_side_contract.md` steps 0 to 13). It does not read a table, a pick, an
overlay or an extrapolation (S3 and S4), nor the one alternative left once the others are set aside (S4). So:

- `example/human_plasma` reads `met` at 310.15 K when the request gives a shear-rate range inside 10 to
  100 s⁻¹, requires tolerances on temperature (0.5 K, say) and on shear rate (0 suffices for a range inside
  the stated one), and accepts the test method. A stated condition with no tolerance in the request reads
  `unknown` (`condition_unchecked`).
- `example/water` holds each field at two temperatures, as alternatives (`record_format.md` section 5). This
  release reads alternatives only where none has a reason of its own. A density request that both
  alternatives meet gives `unknown` with `no_pick`, and holds both values. A density request at one of the
  two temperatures, which sets the other aside, raises `NotImplementedError` until choosing between
  alternatives is built (S4). The viscosity states no shear rate, which is a reason of each alternative's
  own, so a viscosity request raises `NotImplementedError` at any temperature; once S4 reads alternatives it
  gives `unknown` (`condition_unstated`) until the consumer's declaration waives it.
- `example/ndfeb_n45` is an interval, read since S2b-1. `want: bounds` gives its limits as stored, 1.32 and
  1.37 T with the basis `specification_limits`, and the status `unknown`: its origin is `stated_without_origin`,
  and its temperature, specimen shape and test method are unstated, so the reasons are `stated_without_origin`
  and `condition_unstated` for each of the three. `want: value` gives `not_met` (`want_mismatch`) and no value, since an
  interval is not a number; only a nominal the consumer declares inside the bounds supplies one
  (`declarations.md` section 4.1).

`tests/examples/` checks these outcomes, so this list changes when the reader does.

## How they were made

- **Namespace.** `example` is not reserved (`record_format.md` section 7 item 1) and not registered, so its
  identifiers are not unique: pin each record by its content hash, as every read does.
- **Water.** Each value is evaluated from the formulation, at the stated temperature and 0.101325 MPa, with
  the Python package `iapws` 1.5.5, which reproduces the check values the releases print, and rounded to 6
  significant digits. Schema 0.1.0 has no pressure condition, so the pressure is an input of each
  evaluation, in its `formulation`. The density's tolerance has no statistical meaning, and so is stated in
  words, not as an uncertainty.
- **N45.** A vendor's table of grade limits, with no measurement behind it, so its origin is
  `stated_without_origin` and its basis `specification_limits`. No quote of the vendor's text is recorded,
  since its terms of reuse were not found.
- **Plasma.** The quote and the copy's hash are from the article's full-text XML at Europe PMC (PMC3775424).
  The paper does not say whether its "±" is a standard deviation or a standard error, and schema 0.1.0 has no
  member for a spread of unstated kind, so the record states it in words.
- The sources were researched with AI assistance (Claude, Anthropic), as each value's `assistance` says, and
  checked by the maintainer at a first look. A detailed check is still to come: every review is
  `not_checked`.
- Each `source.key` names no registry entry: a record's keys are checked against the library's registry
  (`provenance.md` section 8), and the examples are outside the library.
- The values are licensed CC0-1.0, and quoted evidence is excluded from that licence, as in every record.
- The script that first wrote these files is not part of the repository. The files are the source: after an
  edit, recompute the record's `content_hash` (`record_format.md` section 9).
