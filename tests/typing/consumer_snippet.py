# SPDX-License-Identifier: Apache-2.0
# pyright: strict, reportUnnecessaryTypeIgnoreComment=error
"""A consumer's code, type-checked by CI against the installed wheel rather than the source tree.

mypy refuses the imports when the wheel lacks `py.typed`, and `assert_type` fails when a public type changes.
Both checkers report an ignore that silences nothing: mypy under `--strict`, pyright by the line above.
"""

from typing import assert_type

import materica
from materica.core.hashing import content_hash, hashable_view
from materica.core.jsonio import JsonValue, parse
from materica.core.read import ReadResult
from materica.core.reasons import Reason
from materica.core.record import RecordStore
from materica.shapes import ReadRequest, ReadStatus, ReasonCode

record = parse(b'{"card": "prose", "body": {"value": 1.0}}')
assert_type(record, JsonValue | Reason)
if isinstance(record, Reason):
    assert_type(record.code, ReasonCode)
    assert_type(record.condition, str | None)
else:
    assert_type(materica.content_hash(record), str)
    assert_type(content_hash(record), str)
    assert_type(hashable_view(record), JsonValue)

store = materica.load_records(["water.json"])
assert_type(store, RecordStore)
request: ReadRequest = {
    "target": {
        "record": {"id": "conformance/water", "version": "1.0.0", "content_hash": "sha256:0"},
        "field": "fluid.dynamic_viscosity",
    },
    "operating_conditions": {"temperature": {"value": 310.15, "unit": "K"}},
    "requirement": {
        "want": "value",
        "conditions": {"temperature": {"tolerance": {"value": 1.0, "unit": "K"}}},
    },
}
result = materica.read(request, store, claims={"plain_read"})
assert_type(result, ReadResult)
shape = result.to_json()
assert_type(shape["status"], ReadStatus)
# A result's shape is read-only (PEP 705, from shapes.pyi), so both checkers refuse this write; were it ever
# accepted, both would report the ignore as unused (CI's control removes `ReadOnly` from the stub to show it).
shape["status"] = "met"  # type: ignore[typeddict-readonly-mutated]
assert_type(materica.read(b"{}", store), ReadResult)
assert_type(materica.read("{}", store), ReadResult)
