# SPDX-License-Identifier: Apache-2.0
"""Reasons, which say why a result is not `met` (`read_side_contract.md` sections 2 and 4)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Reason:
    """A code from the reason table, the condition it concerns if any, and a detail for people.

    A reason is identified by its code and condition (`read_side_contract.md` section 2 item 2), so `detail`
    takes no part in equality.
    """

    code: str
    condition: str | None = None
    detail: str | None = field(default=None, compare=False)
