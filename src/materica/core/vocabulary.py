# SPDX-License-Identifier: Apache-2.0
"""The tokens of schema 0.1, as the specification's tables give them, read from `schema/0.1/vocabulary/`.

`scripts/gen_vocabulary.py` writes those files from the tables, and CI fails when they differ, so a token is
written in one place. A file of another shape is a broken installation, and loading it raises.
"""

from dataclasses import dataclass
from importlib import resources
from typing import Literal, get_args, get_type_hints

from materica import shapes
from materica.core import jsonio
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.shapes import ReadStatus, ReasonCode

_REASON_CODES: dict[str, ReasonCode] = {code: code for code in get_args(ReasonCode)}
_READ_STATUSES: dict[str, ReadStatus] = {status: status for status in get_args(ReadStatus)}


@dataclass(frozen=True)
class ReasonSpec:
    """A row of `read_side_contract.md` section 4: a code, and the status it gives."""

    code: ReasonCode
    status: ReadStatus


@dataclass(frozen=True)
class ConditionSpec:
    """A row of `provenance.md` section 6.1: a numeric condition and its unit, or a token one and tokens."""

    name: str
    shape: Literal["numeric", "token"]
    unit: str | None
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class RecordFieldSpec:
    """A row of `record_format.md` section 4.1. `unit` is a UCUM code or a status object, and `label` the
    label's token, where the row names one; when a label applies is the row's prose, so it is code."""

    name: str
    unit: JsonValue
    forms: tuple[str, ...]
    requires: tuple[str, ...]
    label: str | None

    @property
    def section(self) -> str:
        return self.name.partition(".")[0]


@dataclass(frozen=True)
class FactSpec:
    """A row of `provenance.md` section 6.2: a specimen fact, and the tokens of its `token` member, if any."""

    name: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class Vocabulary:
    reasons: dict[str, ReasonSpec]
    conditions: dict[str, ConditionSpec]
    fields: dict[str, RecordFieldSpec]
    facts: dict[str, FactSpec]
    acceptance_kinds: tuple[str, ...]
    token_lists: dict[str, tuple[str, ...]]
    """Every token list the vocabulary's files define in their `$defs`, by its name there (`central`,
    `statistics_distribution`, `origin`, `form`): the tokens of the members the specification's tables
    list. The other definitions there, the writer's bindings and patterns, are no token list."""

    @property
    def sections(self) -> frozenset[str]:
        """The sections of schema 0.1, those its field table names."""
        return frozenset(field.section for field in self.fields.values())


def load() -> Vocabulary:
    reasons = _object(_file("reasons.json")["reasons"])
    conditions = _object(_file("conditions.json")["conditions"])
    fields = _object(_file("fields.json")["fields"])
    facts = _object(_file("specimen_facts.json")["facts"])
    return Vocabulary(
        reasons={code: _reason(code, _object(row)) for code, row in reasons.items()},
        conditions={name: _condition(name, _object(row)) for name, row in conditions.items()},
        fields={name: _field(name, _object(row)) for name, row in fields.items()},
        facts={name: FactSpec(name, _strings(_object(row)["tokens"])) for name, row in facts.items()},
        acceptance_kinds=_strings(_file("acceptances.json")["kinds"]),
        token_lists=_token_lists(),
    )


def _reason(code: str, row: dict[str, JsonValue]) -> ReasonSpec:
    return ReasonSpec(_REASON_CODES[code], _READ_STATUSES[_string(row["status"])])


def _condition(name: str, row: dict[str, JsonValue]) -> ConditionSpec:
    if row["shape"] == "numeric":
        return ConditionSpec(name, "numeric", _string(row["unit"]), ())
    if row["shape"] == "token":
        return ConditionSpec(name, "token", None, _strings(row["tokens"]))
    raise ValueError(f"the condition {name} has no shape this reader knows")


def _field(name: str, row: dict[str, JsonValue]) -> RecordFieldSpec:
    label = row.get("label")
    return RecordFieldSpec(
        name,
        row["unit"],
        _strings(row["forms"]),
        _strings(row["requires"]),
        None if label is None else _string(label),
    )


def _token_lists() -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    names = sorted(path.name for path in resources.files("materica").joinpath(*_LOCATION).iterdir())
    for file_name in (name for name in names if name.endswith(".json")):
        for name, definition in _object(_file(file_name).get("$defs", {})).items():
            tokens = _object(definition).get("enum")
            if tokens is None:
                continue
            if name in found:
                raise ValueError(f"the vocabulary defines the token list {name} twice")
            found[name] = _strings(tokens)
    return found


_LOCATION = ("schema", "0.1", "vocabulary")


def _file(name: str) -> dict[str, JsonValue]:
    return _object(jsonio.parse(resources.files("materica").joinpath(*_LOCATION, name).read_bytes()))


def _object(value: JsonValue | Reason) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"the vocabulary holds {value!r} where an object belongs")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise ValueError(f"the vocabulary holds {value!r} where a string belongs")
    return value


def _strings(value: JsonValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"the vocabulary holds {value!r} where a list belongs")
    return tuple(_string(item) for item in value)


VOCABULARY = load()

STATUS_TOKENS: tuple[str, ...] = get_args(get_type_hints(shapes.StatusObject)["status"])
"""The five tokens a status object holds (`provenance.md` section 1 item 2), as the writer schema's status
object lists them: they sit in no table, so the vocabulary has no file of them."""
