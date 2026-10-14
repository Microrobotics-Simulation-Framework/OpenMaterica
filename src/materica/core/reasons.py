# SPDX-License-Identifier: Apache-2.0
"""Reasons, which say why a result is not `met` (`read_side_contract.md` sections 2 and 4)."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from materica import shapes
from materica.shapes import ReasonCode


@dataclass(frozen=True)
class Reason:
    """A code from the reason table, the condition it concerns if any, and a detail for people.

    A reason is identified by its code and condition (`read_side_contract.md` section 2 item 2), so `detail`
    takes no part in equality.
    """

    code: ReasonCode
    condition: str | None = None
    detail: str | None = field(default=None, compare=False)

    @classmethod
    def from_json(cls, reason: shapes.Reason) -> "Reason":
        return cls(reason["code"], reason.get("condition"), reason.get("detail"))

    def to_json(self) -> shapes.Reason:
        # A result's shapes are read-only, so each is written whole.
        if self.condition is None:
            return {"code": self.code} if self.detail is None else {"code": self.code, "detail": self.detail}
        if self.detail is None:
            return {"code": self.code, "condition": self.condition}
        return {"code": self.code, "condition": self.condition, "detail": self.detail}


def merged(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """Each code and condition once, in the order first found, with the details of its repeats joined: a check
    that fails more than once still gives one reason (section 2 item 2)."""
    details: dict[Reason, list[str]] = {}
    for reason in reasons:
        details.setdefault(reason, [])
        if reason.detail is not None:
            details[reason].append(reason.detail)
    return tuple(
        Reason(reason.code, reason.condition, "; ".join(found) or None) for reason, found in details.items()
    )
