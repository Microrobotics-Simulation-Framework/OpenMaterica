# `materica.core`

The core (layer L2, AD 7.1): the code that reads and checks records. It uses Python's standard library only
(AD 7.2, CONTRIBUTING constraint 3), so it adds nothing to a consumer's dependencies; the shapes it types its
results with (`materica.shapes`, generated) use the standard library only too.

## The data paths

The content hash:

```
bytes ─▶ jsonio.parse ─▶ value ─▶ hashing.hashable_view ─▶ view ─▶ canonical.canonicalize ─▶ bytes ─▶ SHA-256
            │                       (hashing.content_hash runs these three, and writes "sha256:<hex>")
            └─▶ Reason("malformed")
```

A read, steps 0 to 5 of `read_side_contract.md` section 3:

```
request ─▶ read.ReadRequest.from_json ─▶ step 0, the request on its own ─▶ reasons, or a ReadRequest
                                                                                │
sources ─▶ record.RecordStore.add ─▶ candidates by id and version,              ▼
           and the unreadable sources                      resolve.resolve_record
                                                           1 the candidate that states the pin
                                                           2 its schema version     ┐
                                                           3 envelope.py's checks   ├ kept on the Record
                                                           5 its type               ┘
                                                           4 the hash, with HS: recomputed on every read,
                                                             between steps 3 and 5
                                                                  │
               read.ReadResult (status, reasons, labels) ◀────────┘   or NotImplementedError for steps 6 to 13
```

| Module | Implements |
|---|---|
| `reasons.py` | a reason as `read_side_contract.md` section 2 shapes it, each code and condition once; codes from the table in section 4 |
| `status.py` | the three statuses of a read, and the worst of several (section 2) |
| `jsonio.py` | `record_format.md` section 1 item 6, strict JSON; `JsonValue`, the type of what it reads |
| `canonical.py` | `record_format.md` section 9 item 2: RFC 8785, with no Unicode normalisation |
| `hashing.py` | `record_format.md` section 9 items 1 and 2: what the hash leaves out, and the hash |
| `identifiers.py` | `record_format.md` sections 7 and 8: identifiers and versions, matched in full; material references |
| `slips.py` | `record_format.md` section 10: names one slip apart, by which a reader refuses a member it does not know that is one slip from a member named at its place |
| `vocabulary.py` | the tokens of the specification's tables, read from `schema/0.1/vocabulary/` |
| `envelope.py` | the reader schema's checks by hand (`record_format.md` section 1 item 2) |
| `record.py` | the records a read resolves among, and the checks that depend on one record alone (steps 2, 3 and 5) |
| `resolve.py` | steps 1 to 5: a material reference to the record it pins, or the reasons it is refused |
| `read.py` | the request's own check (step 0), and the read; steps 6 to 13 are not built yet |

The conformance cases HS-001 to HS-003 check the hash end to end; the plain-read cases, HS-010 and HS-011 the
read up to step 5 (`tests/conformance/`).

## Invariants

- **Results, never exceptions, for content.** `parse` gives a value or `malformed` for any bytes, running out
  of stack or memory included, and a read gives a result for any request and any records. An exception means
  a misuse of the Python API (`canonicalize` given a value `parse` would never give; claims no reader makes, a
  suite that does not exist or claims without plain read) or a step not built yet: a read whose answer a later
  step would decide raises `NotImplementedError` rather than give one, whatever else is wrong with the request
  (`tests/property/test_read_properties.py`, `tests/unit/test_read.py`).
- **A request is JSON text or a value.** Text is a `str` or bytes-like (`bytes`, `bytearray`, `memoryview`),
  read like a record's bytes; a `str` is always text, as a JSON string is never a request. Any other value is
  read as the JSON text `json.dumps` writes of it.
- **Every number is a float.** An integer reads as the nearest double; `JsonValue` has no `int`, and
  `canonicalize` refuses one. A request given as a Python value is read through JSON text, so its integers too.
  (The reader's properties compare types exactly; `tests/unit/test_canonical.py`.)
- **Stored JSON is never mutated.** `hashable_view` builds new containers and leaves its argument as it was
  (`tests/unit/test_hashing.py`); a `Record` keeps the value its bytes parse to as it is.
- **Identifiers match in full**, by `re.fullmatch` with character classes written out
  (`tests/property/test_version_properties.py`).
- **One envelope check, in two forms.** `envelope.py` and `schema/0.1/record.reader.json` accept and refuse
  the same records (`tests/spec_sync/test_envelope.py`, `tests/property/test_envelope_properties.py`).
- **Standard library only**, with `materica.shapes`, itself standard library only, and, for type checkers
  only, `typing_extensions`; relative imports are checked like absolute ones (`tests/unit/test_source_files.py`).
