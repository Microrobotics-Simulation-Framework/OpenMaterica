# Quickstart

Write a record, then read a value from it, in Python. A test runs every line of code on this page and compares
what it prints with what is shown here (`tests/examples/test_quickstart.py`), so the page and the code cannot
drift apart.

> **This release reads constants, intervals, compositions and evidence.** A read gives the value of a constant
> field, the bounds of an interval, the components of a composition or the reports of evidence. A field holding
> a table, and a request with a pick, an overlay or an extrapolation, are not read yet: the read raises
> `NotImplementedError`, rather than give an answer a later release could contradict. A field holding
> alternatives is read only where none has a reason of its own: choosing between them waits for S4.

> **The example records are examples, not reviewed library data.** They are not yet fully human-reviewed, and
> may change in a later commit ([`examples/README.md`](../../examples/README.md)).

Run it from a checkout of this repository, with the package installed from the checkout (`uv sync`), since it
starts from the example record `examples/records/water.json`. It writes its own record to a temporary
directory, and nothing in the checkout.

## 1. Write a record

The example `example/water` holds liquid water's density at 293.15 K and at 310.15 K as two alternatives of
one field (`record_format.md` section 5). This release does not yet choose between alternatives, so the page
writes a record of its own that holds one of them: the density at 310.15 K, with the example's conditions,
statistics and provenance.

```pycon
>>> import json
>>> import tempfile
>>> from pathlib import Path
>>> from materica import content_hash, load_records, read
>>> example = json.loads(Path("examples/records/water.json").read_text("utf-8"), parse_int=float)
>>> density = example["body"]["sections"]["bulk"]["fields"]["density"]["alternatives"][1]
>>> density["value"], density["unit"], density["conditions"]["temperature"]
(993.33, 'kg/m3', {'value': 310.15, 'unit': 'K', 'basis': 'stated'})
>>> record = {
...     "schema_version": "0.1.0",
...     "record_type": "material",
...     "id": "example/water_310",
...     "version": "0.1.0",
...     "name": "Liquid water at 310.15 K and 0.101325 MPa (quickstart)",
...     "licence": {"values": "CC0-1.0", "evidence": "excluded"},
...     "body": {"sections": {"bulk": {"fields": {"density": density}}}},
... }
>>> record["content_hash"] = content_hash(record)
>>> path = Path(tempfile.mkdtemp()) / "water_310.json"
>>> _ = path.write_text(json.dumps(record, indent=2, ensure_ascii=False), "utf-8")
```

The content hash covers the whole record but the hash itself, its `card`, and each value's review and copy
(`record_format.md` section 9). A reader reads every JSON number as a double (section 1 item 6), and
`content_hash` takes the record as a reader reads it, so the example is parsed with `parse_int=float`.

## 2. Read it

A request names the record by its identifier, version and content hash, and the field. It gives the operating
conditions, and for each condition the record states, what the consumer requires: a tolerance for a number,
the tokens it accepts for a token (`read_side_contract.md` section 1). Here, body temperature to within 0.5 K,
and the density of the whole specimen (`apparent`).

```pycon
>>> store = load_records([path])
>>> pin = {key: record[key] for key in ("id", "version", "content_hash")}
>>> def density_at(kelvin):
...     return {
...         "target": {"record": pin, "field": "bulk.density"},
...         "operating_conditions": {"temperature": {"value": kelvin, "unit": "K"}},
...         "requirement": {
...             "want": "value",
...             "conditions": {
...                 "temperature": {"tolerance": {"value": 0.5, "unit": "K"}},
...                 "density_kind": {"accept": ["apparent"]},
...             },
...         },
...     }
>>> met = read(density_at(310.15), store)
>>> met.status, met.value, met.unit
('met', 993.33, 'kg/m3')
>>> met.provenance.origin, met.provenance.source, met.provenance.review["status"]
('evaluated_from_formulation', 'iapws_r6_95_2018', 'not_checked')
```

Every condition is met, so the result is `met`, and it carries the value with its unit, conditions,
statistics and provenance: the value is evaluated from a formulation (IAPWS R6-95(2018)), and nobody has
reviewed it yet. `met.to_json()` gives the whole result as JSON.

## 3. A refusal, with its reasons

The same request at 298.15 K (25 °C):

```pycon
>>> refused = read(density_at(298.15), store)
>>> refused.status, refused.value
('not_met', None)
>>> [(reason.code, reason.condition) for reason in refused.reasons]
[('condition_outside', 'temperature')]
>>> sorted((entry.name, entry.status) for entry in refused.conditions)
[('density_kind', 'met'), ('temperature', 'not_met')]
```

The record states 310.15 K, which is outside the request's tolerance of 298.15 ± 0.5 K, so the read is refused
and carries no value. A reader never interpolates or extrapolates a value the record does not give, and a
refusal is a result, never an exception: every reason found is reported, each naming the condition it concerns
(`read_side_contract.md` sections 2 and 4).

## What this release does not read yet

- **Alternatives.** The example `example/water` itself. A density request that both alternatives meet
  gives `unknown` with `no_pick`, holding both. A density request at one of its two temperatures raises
  `NotImplementedError` until choosing between alternatives, and the one alternative left, are built (S4).
  The viscosity states no shear rate, which is a reason of each alternative's own, so a viscosity request
  raises `NotImplementedError` at any temperature until S4.
- **Tables and extrapolation** (S3), **picks and overlays** (S4), **scenes** (a region target, and a target
  record that is an overlay), **fit records** (`want: fit` on a field holding one), **sampling**, **USD** and
  **`materica check`**.

The example `example/human_plasma` holds one constant, and reads `met` at 310.15 K when the request gives a
shear-rate range inside 10 to 100 s⁻¹, requires tolerances on temperature (0.5 K, say) and on shear rate (0
suffices for a range inside the stated one), and accepts the test method. The example `example/ndfeb_n45`, a
grade's remanence limits, is an interval, which this release reads: `want: bounds` gives 1.32 and 1.37 T as
stored, with the status `unknown` (its origin is `stated_without_origin`, and its temperature, specimen shape
and test method are unstated), and `want: value` gives `not_met` (`want_mismatch`) and no value, since an
interval is not a number.
