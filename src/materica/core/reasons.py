# SPDX-License-Identifier: Apache-2.0
"""Reasons, which say why a result is not `met` (`read_side_contract.md` sections 2 and 4)."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import cast

from materica import shapes
from materica.shapes import ReasonCode


@dataclass(frozen=True)
class Reason:
    """A code from the reason table, the condition it concerns if any, the index of the alternative it was
    found reading if any, and a detail for people.

    A reason is identified by its code, condition and alternative (`read_side_contract.md` section 2 item 2),
    so `detail` takes no part in equality.
    """

    code: ReasonCode
    condition: str | None = None
    detail: str | None = field(default=None, compare=False)
    alternative: int | None = field(default=None, kw_only=True)

    @classmethod
    def from_json(cls, reason: shapes.Reason) -> "Reason":
        alternative = reason.get("alternative")
        return cls(
            reason["code"],
            reason.get("condition"),
            reason.get("detail"),
            alternative=None if alternative is None else int(alternative),
        )

    def to_json(self) -> shapes.Reason:
        """The reason as JSON, its index written as an integer (the code design's rule 5)."""
        written: dict[str, object] = {"code": self.code}
        if self.condition is not None:
            written["condition"] = self.condition
        if self.alternative is not None:
            written["alternative"] = self.alternative
        if self.detail is not None:
            written["detail"] = self.detail
        return cast(shapes.Reason, written)


def merged(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """Each code, condition and alternative once, in the order first found, with the details of its repeats
    joined: a check that fails more than once still gives one reason (section 2 item 2)."""
    details: dict[Reason, list[str]] = {}
    for reason in reasons:
        details.setdefault(reason, [])
        if reason.detail is not None:
            details[reason].append(reason.detail)
    return tuple(
        Reason(reason.code, reason.condition, "; ".join(found) or None, alternative=reason.alternative)
        for reason, found in details.items()
    )


def tagged(reasons: Iterable[Reason], alternative: int) -> tuple[Reason, ...]:
    """`reasons`, found reading one alternative, each copied with that alternative's index among the stored
    alternatives of the field read (section 2 item 2)."""
    return tuple(
        Reason(reason.code, reason.condition, reason.detail, alternative=alternative) for reason in reasons
    )
