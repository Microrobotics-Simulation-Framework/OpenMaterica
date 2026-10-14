# SPDX-License-Identifier: Apache-2.0
# pyright: strict
"""A consumer's code, type-checked by CI against the installed wheel rather than the source tree.

mypy refuses the imports when the wheel lacks `py.typed`, and `assert_type` fails when a public type changes.
"""

from typing import assert_type

import materica
from materica.core.hashing import content_hash, hashable_view
from materica.core.jsonio import JsonValue, parse
from materica.core.reasons import Reason

record = parse(b'{"card": "prose", "body": {"value": 1.0}}')
assert_type(record, JsonValue | Reason)
if isinstance(record, Reason):
    assert_type(record.code, str)
    assert_type(record.condition, str | None)
else:
    assert_type(materica.content_hash(record), str)
    assert_type(content_hash(record), str)
    assert_type(hashable_view(record), JsonValue)
