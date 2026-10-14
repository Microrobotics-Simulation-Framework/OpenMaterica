# SPDX-License-Identifier: Apache-2.0
"""A read's status, `met`, `not_met` or `unknown` (`read_side_contract.md` section 2).

`ReadStatus` is the result's status, never a status object (`provenance.md` section 1), which is a member's
value where it has none.
"""

from collections.abc import Iterable

from materica.shapes import ReadStatus as ReadStatus

_ORDER: tuple[ReadStatus, ...] = ("met", "unknown", "not_met")


def worst(statuses: Iterable[ReadStatus]) -> ReadStatus:
    """`not_met` over `unknown` over `met` (section 2 item 2); `met` where there are none."""
    return _ORDER[max((_ORDER.index(status) for status in statuses), default=0)]
