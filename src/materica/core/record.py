# SPDX-License-Identifier: Apache-2.0
"""The records a read resolves a reference among (`read_side_contract.md` section 3, step 1).

The store indexes loosely: a source that parses to an object with a string `id` and `version` is a candidate,
whatever else is wrong with it, so that a broken record is found and refused at its step rather than passed
over. Nothing else is checked when a source is added. The checks that depend on a record alone (steps 2, 3 and
5) run when a read or a listing first needs them, and are kept on the record.
"""

from dataclasses import dataclass
from functools import cached_property

from materica.core import jsonio
from materica.core.envelope import SCHEMA_VERSION, envelope_problems
from materica.core.identifiers import parse_version
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason

# `record_format.md` section 3: `interface` is a reserved name in 0.1, and its body not yet specified.
READABLE_TYPES = ("material", "overlay")


@dataclass(frozen=True, eq=False)
class Record:
    """A candidate: a source, its bytes, and the object they parse to, which is never mutated."""

    source: str
    data: bytes
    value: dict[str, JsonValue]
    id: str
    version: str

    @cached_property
    def version_refusal(self) -> Reason | None:
        """Step 2: a `schema_version` absent or off its pattern, or of a MAJOR.MINOR not the reader's."""
        stated = self.value.get("schema_version")
        version = parse_version(stated) if isinstance(stated, str) else None
        if version is None:
            return Reason(
                "malformed", detail=f"{self.source}: schema_version is not MAJOR.MINOR.PATCH: {stated!r}"
            )
        if (version.major, version.minor) != (SCHEMA_VERSION.major, SCHEMA_VERSION.minor):
            return Reason("other_version", detail=f"{self.source}: schema_version {stated}")
        return None

    @cached_property
    def envelope_refusal(self) -> Reason | None:
        """Step 3: the envelope and the body's structure against the reader schema."""
        problems = envelope_problems(self.value)
        return Reason("malformed", detail=f"{self.source}: " + "; ".join(problems)) if problems else None

    @cached_property
    def type_refusal(self) -> Reason | None:
        """Step 5: a record of a type this reader cannot read."""
        record_type = self.value.get("record_type")
        if record_type in READABLE_TYPES:
            return None
        return Reason("unknown_type", detail=f"{self.source}: record_type {record_type!r}")


class RecordStore:
    """The sources a read may resolve against: candidates by `id` and `version`, and the unreadable sources.

    An object with a `document_type` and no `record_type` is a document, not a record (`record_format.md`
    section 3 item 2), and is set aside: it is neither a candidate nor unreadable.
    """

    def __init__(self) -> None:
        self._candidates: dict[tuple[str, str], list[Record]] = {}
        self._unparsed: list[tuple[str, Reason]] = []

    def add(self, source: str, data: bytes) -> None:
        value = jsonio.parse(data)
        if isinstance(value, Reason):
            self._unparsed.append((source, value))
        elif isinstance(value, dict) and "document_type" in value and "record_type" not in value:
            return
        elif (
            isinstance(value, dict)
            and isinstance(id_ := value.get("id"), str)
            and isinstance(version := value.get("version"), str)
        ):
            self._candidates.setdefault((id_, version), []).append(Record(source, data, value, id_, version))
        else:
            detail = "neither a document nor an object with a string id and version"
            self._unparsed.append((source, Reason("malformed", detail=detail)))

    def get(self, id: str, version: str) -> list[Record]:
        """The candidates of `id` and `version`, in the order they were added."""
        return list(self._candidates.get((id, version), []))

    def unparsed(self) -> list[tuple[str, Reason]]:
        """The unreadable sources and why: those that did not parse, or parsed to neither a document nor an
        object with a string `id` and `version`."""
        return list(self._unparsed)

    def list_records(self) -> list[Record]:
        """The candidates that pass steps 2, 3 and 5 on their own (README, "Operations"). Of the others, and
        of every other source, a listing says nothing."""
        return [
            record
            for records in self._candidates.values()
            for record in records
            if record.version_refusal is None
            and record.envelope_refusal is None
            and record.type_refusal is None
        ]
