# `materica.core`

The core (layer L2, AD 7.1): the code that reads and checks records. It uses Python's standard library only
(AD 7.2, CONTRIBUTING constraint 3), so it adds nothing to a consumer's dependencies.

## The data path

```
bytes ─▶ jsonio.parse ─▶ value ─▶ hashing.hashable_view ─▶ view ─▶ canonical.canonicalize ─▶ bytes ─▶ SHA-256
            │                       (hashing.content_hash runs these three, and writes "sha256:<hex>")
            └─▶ Reason("malformed")
```

`jsonio` uses `reasons`; `canonical` uses `jsonio`'s `JsonValue`; `hashing` uses both of them.

The specification's documents are in `docs/specification/`.

| Module | Implements |
|---|---|
| `reasons.py` | a reason as `read_side_contract.md` section 2 shapes it; codes from the table in section 4 |
| `jsonio.py` | `record_format.md` section 1 item 6, strict JSON; `JsonValue`, the type of what it reads |
| `canonical.py` | `record_format.md` section 9 item 2: RFC 8785, with no Unicode normalisation |
| `hashing.py` | `record_format.md` section 9 items 1 and 2: what the hash leaves out, and the hash |

The conformance cases HS-001 to HS-003 check this path end to end (`tests/conformance/`).

## Invariants

- **Results, never exceptions, for content.** `parse` gives a value or `malformed` for any bytes, running out
  of stack or memory included. An exception means a misuse of the Python API: `canonicalize` refuses a value
  that `parse` would never give. (`tests/property/test_jsonio_properties.py`, `tests/unit/test_jsonio.py`.)
- **Every number is a float.** An integer reads as the nearest double; `JsonValue` has no `int`, and
  `canonicalize` refuses one. (The reader's properties compare types exactly; `tests/unit/test_canonical.py`.)
- **Stored JSON is never mutated.** `hashable_view` builds new containers and leaves its argument as it was
  (`tests/unit/test_hashing.py`).
- **Standard library only**, with `typing_extensions` allowed only under `TYPE_CHECKING`
  (`tests/unit/test_source_files.py`).
