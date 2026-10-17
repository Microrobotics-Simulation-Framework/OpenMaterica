# SPDX-License-Identifier: Apache-2.0
"""Fail unless the known-anomalies registry keeps MADDENING's record schema, as the registry's header says.

    python scripts/check_anomalies.py [REGISTRY] [--pyproject PYPROJECT]

It stands in for MADDENING's validator (`python -m maddening.compliance check-anomalies`), which accepts the
version field `materica_version` from MADDENING 0.4.0 but reads each `affected_components` entry as an
importable Python name, which this registry's component names are not. The rules are MADDENING's record
schema (`maddening.compliance._validate`, 0.4.1), with this registry's prefix, version field and component
names:

- the top level holds `schema_version`, `materica_version`, `generated_date` (`YYYY-MM-DD`) and `anomalies`, a
  list, and nothing else; `materica_version` is the package's version, from `pyproject.toml`;
- each entry holds MADDENING's required fields, each a non-empty string, and no field outside MADDENING's
  record;
- each `anomaly_id` is `OMAT-ANO-` and three digits, and no two entries share one;
- `severity` is one of DOCUMENTATION_ARCHITECTURE.md section 8.2's, and `safety_relevance` and
  `resolution_status` are among MADDENING's values;
- every entry's `affected_versions` is a PEP 440 version specifier set, or `none`, the empty set;
- each `affected_components` entry is `schema:`, `reader:`, `method:`, `model:` or `data:` and a name.

Standard library only, so that the gate runs it before any dependency is installed. So it reads the registry's
YAML as a subset: block mappings and sequences; values quoted on one line, block scalars (`|` and `>`), plain
words that start with a letter, `null`, `~` and `[]`; and comments. It refuses anything else, a number or a
date unquoted and a key given twice among them, at its line, rather than guess; what it reads, it reads as
PyYAML does (`tests/unit/test_check_anomalies.py`).
"""

import argparse
import datetime
import re
import string
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import TypeAlias

REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY = REPOSITORY / "docs" / "validation" / "known_anomalies.yaml"
PYPROJECT = REPOSITORY / "pyproject.toml"

# What the YAML subset reads: a string, null, a list or a mapping.
Value: TypeAlias = "str | list[Value] | dict[str, Value] | None"

# MADDENING's record schema, from `maddening.compliance._validate` at 0.4.1, with this registry's version
# field.
VERSION_FIELD = "materica_version"
TOP_LEVEL = ("schema_version", VERSION_FIELD, "generated_date", "anomalies")
REQUIRED = (
    "anomaly_id",
    "title",
    "description",
    "severity",
    "safety_relevance",
    "safety_relevance_rationale",
    "resolution_status",
)
OPTIONAL = (
    "affected_components",
    "affected_versions",
    "workaround",
    "resolution_version",
    "verification",
    "residual_risk",
    "github_issue",
)
ENUMERATIONS = {
    # DOCUMENTATION_ARCHITECTURE.md section 8.2 applies MADDENING's definitions to data and families.
    "severity": ("critical", "major", "minor", "enhancement"),
    "safety_relevance": ("safety_relevant", "not_safety_relevant", "context_dependent"),
    "resolution_status": ("open", "resolved", "partially_resolved", "wont_fix", "duplicate"),
}

# This registry's own: its identifiers (CONTRIBUTING, "Identifier prefixes") and the kinds of component an
# entry names (DOCUMENTATION_ARCHITECTURE.md section 8.3).
ANOMALY_ID = re.compile(r"OMAT-ANO-[0-9]{3}")
COMPONENT_KINDS = ("schema", "reader", "method", "model", "data")
COMPONENT = re.compile(rf"(?:{'|'.join(COMPONENT_KINDS)}):\S+")
_KINDS = f"{', '.join(f'{kind}:' for kind in COMPONENT_KINDS[:-1])} or {COMPONENT_KINDS[-1]}:"
EMPTY_RANGE = "none"

# One PEP 440 version specifier, as `packaging.specifiers.Specifier` reads one: `===` takes any string
# without whitespace; `==` and `!=` a version with a local label or a trailing `.*`; `~=` a release of two
# components or more; `<=`, `>=`, `<` and `>` a version without either.
_RELEASE = r"v?(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*"
_PRE = r"(?:[-_.]?(?:alpha|beta|preview|pre|a|b|c|rc)[-_.]?[0-9]*)?"
_POST = r"(?:-[0-9]+|[-_.]?(?:post|rev|r)[-_.]?[0-9]*)?"
_DEV = r"(?:[-_.]?dev[-_.]?[0-9]*)?"
_LOCAL = r"(?:\+[a-z0-9]+(?:[-_.][a-z0-9]+)*)?"
SPECIFIER = re.compile(
    rf"\s*(?:===\s*[^\s;)]*"
    rf"|(?:==|!=)\s*{_RELEASE}(?:\.\*|{_PRE}{_POST}{_DEV}{_LOCAL})"
    rf"|~=\s*v?(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)+{_PRE}{_POST}{_DEV}"
    rf"|(?:<=|>=|<|>)\s*{_RELEASE}{_PRE}{_POST}{_DEV})\s*",
    re.IGNORECASE,
)


def is_specifier_set(text: str) -> bool:
    """Whether `text` is a PEP 440 version specifier set: specifiers separated by commas, none empty."""
    return all(SPECIFIER.fullmatch(part) for part in text.split(","))


class RegistryFormatError(ValueError):
    """The registry's text, at a line, is outside the YAML this check reads."""


# The characters PyYAML reads, but for the line breaks other than `\n` (`\r`, U+0085, U+2028 and U+2029),
# which it reads as line breaks and this check would not.
_UNREAD = re.compile("[^\t\n\x20-\x7e\xa0-\u2027\u202a-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")
_KEY = re.compile(r"(?P<key>[a-z_][a-z0-9_]*):(?: +(?P<rest>.*))?")
# Words PyYAML reads as a boolean or as null, not as the string they spell, in any of their cases.
_NOT_STRINGS = frozenset({"yes", "no", "true", "false", "on", "off", "null"})
# A plain value this check reads: `~`, `[]`, or a word that starts with a letter, which PyYAML reads as a
# string unless it is one of the words above.
_WORD = re.compile(r"(?P<word>~|\[ *\]|[A-Za-z][A-Za-z0-9_.-]*)(?: +(?:#.*)?)?")
_AFTER_QUOTE = re.compile(r"(?: +(?:#.*)?)?")
_BLOCK_HEADER = re.compile(r"(?P<style>[|>])(?P<chomping>[-+]?)(?: +(?:#.*)?)?")
_ESCAPES = {
    "0": "\0",
    "a": "\a",
    "b": "\b",
    "t": "\t",
    "\t": "\t",
    "n": "\n",
    "v": "\v",
    "f": "\f",
    "r": "\r",
    "e": "\x1b",
    " ": " ",
    '"': '"',
    "/": "/",
    "\\": "\\",
    "N": "\x85",
    "_": "\xa0",
    "L": "\u2028",
    "P": "\u2029",
}
_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def _is_item(text: str) -> bool:
    return text == "-" or text.startswith("- ")


def _double_quoted(rest: str) -> tuple[str, int] | None:
    """The double-quoted scalar `rest` starts with, and where it ends; None where it ends on a later line."""
    found: list[str] = []
    at = 1
    while at < len(rest):
        character = rest[at]
        if character == '"':
            return "".join(found), at + 1
        if character != "\\":
            found.append(character)
            at += 1
            continue
        escape = rest[at + 1 : at + 2]
        if not escape:
            return None
        if escape in _ESCAPES:
            found.append(_ESCAPES[escape])
            at += 2
            continue
        digits = rest[at + 2 : at + 2 + _HEX_ESCAPES.get(escape, 0)]
        if escape not in _HEX_ESCAPES or len(digits) != _HEX_ESCAPES[escape]:
            raise RegistryFormatError(f"the escape \\{escape} is not one YAML defines")
        if not all(digit in string.hexdigits for digit in digits) or int(digits, 16) > sys.maxunicode:
            raise RegistryFormatError(f"the escape \\{escape}{digits} is not one YAML defines")
        found.append(chr(int(digits, 16)))
        at += 2 + len(digits)
    return None


def _single_quoted(rest: str) -> tuple[str, int] | None:
    found: list[str] = []
    at = 1
    while at < len(rest):
        if rest[at] == "'":
            if rest[at + 1 : at + 2] != "'":
                return "".join(found), at + 1
            at += 1
        found.append(rest[at])
        at += 1
    return None


class _Reader:
    """The registry's lines, read from the top; `at` is the first line not yet read."""

    def __init__(self, text: str) -> None:
        if text and not text.endswith("\n"):
            raise RegistryFormatError("its last line has no line break")
        self.raw = text[:-1].split("\n") if text else []
        self.at = 0
        # The first key of a mapping that is a sequence's item, read at its own column, after the `- `.
        self.shifted: dict[int, tuple[int, str]] = {}
        for at, raw in enumerate(self.raw):
            unread = _UNREAD.search(raw)
            if unread:
                raise self.error(at, f"holds U+{ord(unread[0]):04X}; write it as an escape in a quoted value")
            if raw.lstrip(" ").startswith("\t"):
                raise self.error(at, "is indented with a tab; YAML indents with spaces")

    def error(self, at: int, problem: str) -> RegistryFormatError:
        return RegistryFormatError(f"line {at + 1} {problem}")

    def line(self, at: int) -> tuple[int, str]:
        """A line's indentation and its text after it."""
        if at in self.shifted:
            return self.shifted[at]
        text = self.raw[at].lstrip(" ")
        return len(self.raw[at]) - len(text), text

    def next_content(self) -> int | None:
        """The first line from `at` that is neither blank nor a comment."""
        for at in range(self.at, len(self.raw)):
            text = self.line(at)[1]
            if text and not text.startswith("#"):
                return at
        return None

    def document(self) -> dict[str, Value]:
        first = self.next_content()
        if first is None:
            raise RegistryFormatError("it holds no mapping")
        if self.line(first)[0] != 0:
            raise self.error(first, "is indented; the top level starts in the first column")
        return self.mapping(0)

    def mapping(self, indent: int) -> dict[str, Value]:
        found: dict[str, Value] = {}
        while (at := self.next_content()) is not None:
            own, text = self.line(at)
            if own < indent:
                break
            if own > indent:
                raise self.error(at, "is indented more than the key above it")
            if _is_item(text):
                raise self.error(at, "is a sequence's item where a key belongs")
            key = _KEY.fullmatch(text)
            if key is None:
                raise self.error(at, "is not `key: value` with a key of lowercase letters, digits and `_`")
            if key["key"] in _NOT_STRINGS:
                raise self.error(at, f"has the key {key['key']!r}, which YAML reads as a boolean or null")
            if key["key"] in found:
                raise self.error(at, f"gives {key['key']!r} a second time")
            self.at = at + 1
            found[key["key"]] = self.value(key["rest"] or "", own, at)
        return found

    def value(self, rest: str, indent: int, at: int) -> Value:
        if rest == "" or rest.startswith("#"):
            following = self.next_content()
            if following is None:
                return None
            own, text = self.line(following)
            if own > indent or (own == indent and _is_item(text)):
                if not _is_item(text):
                    raise self.error(following, "holds a value below its key; quote it on the key's line")
                return self.sequence(own)
            return None
        if rest[0] in "|>":
            return self.block(rest, indent, at)
        return self.scalar(rest, at)

    def scalar(self, rest: str, at: int) -> Value:
        word = _WORD.fullmatch(rest)
        if word and word["word"] in ("null", "~"):
            return None
        if word and word["word"].startswith("["):
            return []
        if word and word["word"].lower() not in _NOT_STRINGS:
            return word["word"]
        if rest[0] not in "\"'":
            raise self.error(
                at, f"has the value {rest!r} unquoted, which YAML may read as no string; quote it"
            )
        try:
            quoted = _double_quoted(rest) if rest[0] == '"' else _single_quoted(rest)
        except RegistryFormatError as error:
            raise self.error(at, f"has {error}") from None
        if quoted is None:
            raise self.error(at, "has a quoted value that does not end on it; use a block scalar (`>`)")
        found, end = quoted
        if not _AFTER_QUOTE.fullmatch(rest[end:]):
            raise self.error(at, f"has {rest[end:]!r} after a quoted value")
        return found

    def block(self, rest: str, indent: int, at: int) -> str:
        """A block scalar. `|` keeps its line breaks; `>` folds a break between two lines that start at the
        block's indentation into a space, or into the blank lines between them, and keeps the others. `-`
        strips the final line breaks, `+` keeps them all, and neither keeps one."""
        header = _BLOCK_HEADER.fullmatch(rest)
        if header is None:
            raise self.error(at, "has a block scalar header other than `|` or `>`, and `-` or `+`")
        texts: list[str] = []
        content: int | None = None
        for below in range(at + 1, len(self.raw)):
            raw = self.raw[below]
            own = len(raw) - len(raw.lstrip(" "))
            blank = own == len(raw)
            if content is None:
                if blank:
                    raise self.error(below, "is blank before a block scalar's first line")
                if own <= indent:
                    break
                content = own
            if blank:
                if own > content:
                    raise self.error(below, "holds spaces past its block scalar's indentation; remove them")
                texts.append("")
            elif own < content:
                break
            else:
                texts.append(raw[content:])
            self.at = below + 1
        if content is None:
            raise self.error(at, "starts a block scalar with no line")
        found = ""
        blanks = 0
        previous: str | None = None
        for text in texts:
            if not text:
                blanks += 1
                continue
            if previous is not None:
                folds = header["style"] == ">" and not previous.startswith(" ") and not text.startswith(" ")
                found += ("\n" * blanks or " ") if folds else "\n" * (1 + blanks)
            found += text
            previous, blanks = text, 0
        return found + {"-": "", "": "\n", "+": "\n" * (1 + blanks)}[header["chomping"]]

    def sequence(self, indent: int) -> list[Value]:
        items: list[Value] = []
        while (at := self.next_content()) is not None:
            own, text = self.line(at)
            if own > indent:
                raise self.error(at, "is indented more than the sequence's items")
            if own < indent or not _is_item(text):
                break
            rest = text[1:].lstrip(" ")
            if not rest or rest.startswith("#"):
                raise self.error(at, "is an item with nothing on its line")
            if _KEY.fullmatch(rest):
                self.shifted[at] = (own + len(text) - len(rest), rest)
                self.at = at
                items.append(self.mapping(self.shifted[at][0]))
            else:
                self.at = at + 1
                items.append(self.scalar(rest, at))
        return items


def read_registry(text: str) -> dict[str, Value]:
    """The registry's top-level mapping, from the YAML subset this module's docstring names."""
    return _Reader(text).document()


def top_level_problems(registry: dict[str, Value], version: str) -> list[str]:
    problems: list[str] = []
    keys = set(registry)
    missing = [key for key in TOP_LEVEL if key not in keys]
    if "maddening_version" in keys and VERSION_FIELD in missing:
        problems.append(f"the version field is {VERSION_FIELD}, not MADDENING's maddening_version")
        keys.remove("maddening_version")
        missing.remove(VERSION_FIELD)
    problems += [f"the top-level field {key} is missing" for key in missing]
    problems += [
        f"the top-level field {key} is not one of MADDENING's ({', '.join(TOP_LEVEL)})"
        for key in sorted(keys - set(TOP_LEVEL))
    ]
    schema_version = registry.get("schema_version", "-")
    if not (isinstance(schema_version, str) and schema_version):
        problems.append("schema_version is not a quoted, non-empty string")
    registered = registry.get(VERSION_FIELD, version)
    if registered != version:
        problems.append(
            f"{VERSION_FIELD} is {registered!r}, but the package's version (pyproject.toml) is {version!r}: "
            f"a version's bump updates the registry too"
        )
    date = registry.get("generated_date", "2000-01-01")
    if not (isinstance(date, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date) and _is_a_date(date)):
        problems.append(f"generated_date is {date!r}, not a date written YYYY-MM-DD")
    if not isinstance(registry.get("anomalies", []), list):
        problems.append("anomalies is not a list (`[]` when empty)")
    return problems


def _is_a_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def entry_problems(entry: Value, position: int) -> list[str]:
    if not isinstance(entry, dict):
        return [f"entry {position} is not a mapping"]
    identifier = entry.get("anomaly_id")
    name = identifier if isinstance(identifier, str) and identifier else f"entry {position}"
    problems = [
        f"{name}: {field} is missing, or not a quoted, non-empty string"
        for field in REQUIRED
        if not (isinstance(entry.get(field), str) and entry.get(field))
    ]
    problems += [
        f"{name}: the field {field} is not one of MADDENING's record"
        for field in sorted(set(entry) - {*REQUIRED, *OPTIONAL})
    ]
    if isinstance(identifier, str) and identifier and not ANOMALY_ID.fullmatch(identifier):
        problems.append(f"{name}: the anomaly_id is not OMAT-ANO- and three digits")
    for field, values in ENUMERATIONS.items():
        found = entry.get(field)
        if isinstance(found, str) and found and found not in values:
            problems.append(f"{name}: the {field} {found!r} is none of {', '.join(values)}")
    affected = entry.get("affected_versions")
    if not (isinstance(affected, str) and (affected.strip() == EMPTY_RANGE or is_specifier_set(affected))):
        problems.append(
            f"{name}: affected_versions is {affected!r}, neither a PEP 440 version specifier set nor "
            f"{EMPTY_RANGE!r}"
        )
    components = entry.get("affected_components")
    if components is not None and not isinstance(components, list):
        problems.append(f"{name}: affected_components is not a list")
    for component in components if isinstance(components, list) else []:
        if not (isinstance(component, str) and COMPONENT.fullmatch(component)):
            problems.append(f"{name}: the affected component {component!r} is not {_KINDS} and a name")
    return problems


def schema_problems(registry: dict[str, Value], version: str) -> list[str]:
    """Every way `registry` breaks the rules of this module's docstring, for a package at `version`."""
    problems = top_level_problems(registry, version)
    anomalies = registry.get("anomalies")
    seen: set[str] = set()
    for position, entry in enumerate(anomalies if isinstance(anomalies, list) else [], start=1):
        problems += entry_problems(entry, position)
        identifier = entry.get("anomaly_id") if isinstance(entry, dict) else None
        if isinstance(identifier, str) and identifier:
            if identifier in seen:
                problems.append(f"{identifier}: another entry has this anomaly_id")
            seen.add(identifier)
    return problems


def package_version(pyproject: Path) -> str:
    version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    if not isinstance(version, str):
        raise TypeError(f"{pyproject}: the project's version is not a string")
    return version


def registry_problems(registry: Path = REGISTRY, pyproject: Path = PYPROJECT) -> list[str]:
    try:
        found = read_registry(registry.read_text(encoding="utf-8"))
    except RegistryFormatError as error:
        return [f"{registry}: {error}"]
    return [f"{registry}: {problem}" for problem in schema_problems(found, package_version(pyproject))]


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the known-anomalies registry against MADDENING's schema."
    )
    parser.add_argument("registry", nargs="?", type=Path, default=REGISTRY)
    parser.add_argument(
        "--pyproject", type=Path, default=PYPROJECT, help="whose version the registry carries"
    )
    options = parser.parse_args(arguments)
    problems = registry_problems(options.registry, options.pyproject)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
