# Example records

| Test | Checks |
|---|---|
| `test_example_records.py` | each record in `examples/records/`: the writer and reader schemas take it (both JSON Schema libraries, `spec_sync/schemas.py`), the envelope checks and its content hash, and the record checks it can be given alone (its identifier in the namespace `example`, each field's required conditions and label, every review `not_checked`); each number in it, outside its provenance, against a table of its source's number, the conversion and the place in the source, and the statements schema 0.1.0 keeps only in words; the note that the examples are not yet fully human-reviewed, in `README.md`, `examples/README.md` and each record's `card`; and what a read of each gives at this release, as those documents say: `met` for the plasma, for the water, `no_pick` for the density where both alternatives meet, and `NotImplementedError` where one is set aside and for the viscosity at any temperature (its shear rate is unstated; S4), and for N45's interval `unknown` with its bounds under `want: bounds` and `not_met` (`want_mismatch`) under `want: value` |

The record, source and note checks have controls that must fail: a record given a token the writer refuses, a
structure the reader refuses, a value changed without its hash, a reserved namespace, a malformed identifier or version, a required condition, a
label or a review dropped; a number changed in each record, a number with no source, a statement in words
dropped, a sourced member removed; and each document with its note's lines removed. The read outcomes are
pinned as exact values, with no control of their own in the suite, so a pin is as sharp as its assertion: the
one-temperature water pins match the one guard's message.

Limits. The record check makes the record checks a reader of this release can make alone (identifier and
version, required conditions, the label, every review `not_checked`) and leaves RC-020, RC-037, RC-043,
RC-045, RC-051, RC-052 and RC-058 to `materica check`; the plasma record breaks RC-058 (the pull request's
open point 7). The note check holds each document to carry the note's three phrases and cannot see a
sentence elsewhere that contradicts them.

When S4 lands (choosing between alternatives), the water pins fail on purpose: update them, and
`examples/README.md`'s account of what this release reads, with them. When S3 lands (tables, extrapolation),
no pin here fails, because no example holds a table and no pinned request carries an extrapolation; the prose
that says tables are not read yet goes stale instead, in `examples/README.md` and the README's documentation
table, and is updated by hand.
