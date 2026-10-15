# SPDX-License-Identifier: Apache-2.0
"""Names one slip apart, and names with two meanings, in the schemas, the vocabulary and the specification.

A reader ignores a member it does not know (`record_format.md` section 10), so a slip that lands on another
valid name passes every check and means something else. Section 10 keeps the names valid at one place more
than one slip apart, and this check holds the schema to it. A namespace is the names valid together at one
place: the members of one object, those of the definitions its `allOf` refers to included, or one token list.
Names come from:
- every schema file but the generated reader schema, `$ref`s followed across files, and the vocabulary;
- the specification's fenced JSON examples, and its tables of members and of tokens (member names only);
- its name-keyed sentences: "`x`, wherever it sits", "a member named `x`".

Two rules, each giving flags:
- **A, one name, two meanings.** A member's meaning is its shape: its JSON type, its token list or its
  members. Shapes that cannot be one meaning (a number and an object, a closed token list and a value outside
  it, two token lists no list holds both of) make a name with two or more meanings, flagged with their count.
  Also flagged: a registered name (a section, field, condition or specimen fact) used as an ordinary member;
  one token in the lists of two sibling members; and a member whose example values come from another
  member's token list as well as from elsewhere.
- **B, one slip.** Two names of one namespace one slip apart, as section 10 defines it, single letters
  aside, and the condition and specimen-fact names together, since they are sibling maps of one value field.
  A name is `[a-z][a-z0-9_]*`: the components `element:<symbol>` are IUPAC's symbols, minimal pairs by design
  that no rename can keep apart.

`name_overlaps.json` allows a flag the maintainer judged intended, with its reason and the text that keeps it
safe, which must stay in its document: an entry whose flag is gone, whose safeguard is gone, or whose rule-A
name gains a meaning, fails the check, as does any flag no entry allows.
"""

import fnmatch
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from materica.core.jsonio import JsonValue
from scripts.gen_vocabulary import cells

SCHEMA = Path("src/materica/schema/0.1")
SPECIFICATION = Path("docs/specification")
# Generated from record.writer.json with every token list opened on purpose.
GENERATED = ("record.reader.json",)
# Tables the vocabulary holds already, read from the vocabulary instead: the line above each table.
VOCABULARY_TABLES = (
    "## 4. Reason codes",
    "### 4.1 Sections and fields of schema 0.1.0",
    "### 6.1 Conditions of schema 0.1.0",
    "### 6.2 Specimen facts of schema 0.1.0",
    "### 4.1 The list",
    "The element symbols are IUPAC's 118 (the last four named on 28 November 2016):",
)
# Members whose value is an object keyed by names, in documents with no schema yet (declarations, families,
# scenes, crosswalks): its keys are not members.
MAPS = frozenset(
    "attributes bounds counts domains families groups initial_values input mean operating_conditions output "
    "params per_parameter ranges region_conditions region_values replaces rules space state_mapping values "
    "verdicts".split()
)
# Keywords that declare no member or token list: annotations, and conditions on members declared elsewhere.
CONSTRAINTS = frozenset("enum const required description $comment title if then else not contains".split())
NAME = re.compile(r"[a-z][a-z0-9_]*")
NAME_KEYED = (
    re.compile(r"((?:`[a-z_]+`(?:,? (?:or|and) |, )?)+),? wherever (?:it|a block) sits"),
    re.compile(r"members? named ((?:`[a-z_]+`(?: or | and |, )?)+)"),
)
PLURALS = {"datum": "data", "index": "indices", "matrix": "matrices"}


@dataclass(frozen=True)
class Shape:
    """What a member holds at one place: `kind` is one of `string` (with `names` the values an example shows
    it hold, if any), `tokens` (a closed list, `names`), `number`, `boolean`, `object` (with `names` its
    members), `map` (keyed by names), `array` (of `item`) or `unknown`."""

    kind: str
    names: frozenset[str] = frozenset()
    item: "Shape | None" = None


UNKNOWN = Shape("unknown")


@dataclass
class Namespace:
    """Names valid together at one place: the members of one object, or one token list."""

    kind: Literal["members", "tokens"]
    owner: str
    origin: str
    shapes: dict[str, Shape] = field(default_factory=dict[str, Shape])
    samples: dict[str, set[str]] = field(default_factory=dict[str, set[str]])

    def add(self, name: str, shape: Shape = UNKNOWN, samples: set[str] | None = None) -> None:
        if name in self.shapes and self.shapes[name] != shape:
            self.shapes[name] = UNKNOWN if UNKNOWN in (shape, self.shapes[name]) else shape
        else:
            self.shapes.setdefault(name, shape)
        if samples:
            self.samples.setdefault(name, set()).update(samples)


@dataclass
class Corpus:
    namespaces: list[Namespace] = field(default_factory=list[Namespace])
    registered: dict[str, str] = field(
        default_factory=dict[str, str]
    )  # name -> what the vocabulary registers it as
    name_keyed: dict[str, str] = field(default_factory=dict[str, str])  # name -> the sentence's origin
    registries: set[int] = field(default_factory=set[int])  # ids of namespaces that are a registry's own map
    maps: set[str] = field(default_factory=set[str])  # members the schemas give as an object keyed by names

    def new(self, kind: Literal["members", "tokens"], owner: str, origin: str) -> Namespace:
        namespace = Namespace(kind, owner, origin)
        self.namespaces.append(namespace)
        return namespace


@dataclass(frozen=True)
class Flag:
    rule: Literal["A", "B"]
    names: tuple[str, ...]
    owner: str
    detail: str
    meanings: int = 0

    def __str__(self) -> str:
        return f"[{self.rule}] {' ~ '.join(self.names)} (owner {self.owner}): {self.detail}"


def one_slip(a: str, b: str) -> str | None:
    """The slip that makes `a` into `b` (`record_format.md` section 10), or None where there is none."""
    first, second = a.split("_"), b.split("_")
    if len(first) == len(second):
        differing = [(x, y) for x, y in zip(first, second, strict=True) if x != y]
        if len(differing) == 1 and plural_of(*differing[0]):
            return "singular or plural"
    if len(a) == len(b):
        positions = [index for index, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(positions) == 1:
            return "a character substituted"
        if len(positions) == 2 and positions[1] == positions[0] + 1:
            i, j = positions
            if a[i] == b[j] and a[j] == b[i]:
                return "two characters swapped"
        return None
    shorter, longer = sorted((a, b), key=len)
    if len(longer) - len(shorter) == 1:
        for index, character in enumerate(longer):
            if longer[:index] + longer[index + 1 :] == shorter:
                return "an underscore added" if character == "_" else "a character added"
    return None


def plural_of(a: str, b: str) -> bool:
    """Whether one word is the other made plural or singular, as section 10 lists the ways."""
    singular, plural = sorted((a, b), key=len)
    return (
        plural in (singular + "s", singular + "es")
        or (singular.endswith("y") and plural == singular[:-1] + "ies")
        or PLURALS.get(singular) == plural
        or PLURALS.get(plural) == singular
    )


# The schemas and the vocabulary.


def mapping(value: JsonValue) -> dict[str, JsonValue]:
    assert isinstance(value, dict)
    return value


def listing(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def load(root: Path) -> dict[str, JsonValue]:
    """Every schema file by its path under the schema version's directory, the vocabulary's included."""
    files: dict[str, JsonValue] = {}
    for path in sorted((root / SCHEMA).rglob("*.json")):
        name = path.relative_to(root / SCHEMA).as_posix()
        if name not in GENERATED:
            files[name] = json.loads(path.read_text(encoding="utf-8"))
    return files


class Schemas:
    """The schema files, walked for namespaces; a member's shape follows `$ref`s across files."""

    def __init__(self, files: dict[str, JsonValue], corpus: Corpus) -> None:
        self.files = files
        self.corpus = corpus

    def resolve(self, reference: str, current: str) -> tuple[JsonValue, str]:
        target, _, pointer = reference.partition("#")
        name = current if not target else str(Path(current).parent / target).removeprefix("./")
        node = self.files[name]
        for part in filter(None, pointer.split("/")):
            node = mapping(node)[part]
        return node, name

    def shape(self, node: JsonValue, current: str, depth: int = 0) -> Shape:
        if not isinstance(node, dict) or depth > 12:
            return UNKNOWN
        if "$ref" in node:
            reference = str(node["$ref"])
            # Any value, a placeholder not yet written, or a status object: no meaning of its own.
            if reference.endswith(("/json_value", "/json_object", "/placeholder")) or "/status_" in reference:
                return UNKNOWN
            return self.shape(*self.resolve(reference, current), depth + 1)
        if "enum" in node:
            return Shape("tokens", frozenset(str(token) for token in listing(node["enum"])))
        if "const" in node:
            return Shape("tokens", frozenset({str(node["const"])}))
        for choice in ("oneOf", "anyOf"):
            if choice in node:
                shapes = {self.shape(sub, current, depth + 1) for sub in listing(node[choice])} - {UNKNOWN}
                return shapes.pop() if len(shapes) == 1 else UNKNOWN
        if node.get("type") == "object" or "properties" in node:
            members = frozenset(mapping(node.get("properties", {})))
            if isinstance(node.get("additionalProperties"), dict) or (
                members and members <= set(self.corpus.registered)
            ):
                return Shape("map")
            return Shape("object", members) if members else UNKNOWN
        if node.get("type") == "array":
            items = node.get("items") or listing(node.get("prefixItems", [None]))[0]
            return Shape("array", item=self.shape(items, current, depth + 1))
        kind = {"string": "string", "number": "number", "integer": "number", "boolean": "boolean"}
        return (
            Shape(kind[declared])
            if isinstance(declared := node.get("type"), str) and declared in kind
            else UNKNOWN
        )

    def members(self, node: dict[str, JsonValue], current: str) -> dict[str, tuple[JsonValue, str]]:
        """The members valid at `node`: its own, and those of each definition its `allOf` refers to, which
        the same object holds (a value field's `unit` beside its form's `form`), each with its file."""
        found: dict[str, tuple[JsonValue, str]] = {}
        for conjunct in listing(node.get("allOf", [])):
            if isinstance(conjunct, dict) and "$ref" in conjunct:
                base, file = self.resolve(str(conjunct["$ref"]), current)
                found |= self.members(mapping(base), file)
        properties = node.get("properties", {})
        return found | {name: (subschema, current) for name, subschema in mapping(properties).items()}

    def walk(self, node: JsonValue, current: str, pointer: str, owner: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                self.walk(item, current, f"{pointer}/{index}", owner)
            return
        if not isinstance(node, dict):
            return
        origin = f"{SCHEMA / current}#{pointer}"
        if isinstance(node.get("properties", {}), dict) and (valid := self.members(node, current)):
            members = self.corpus.new("members", owner, origin)
            if set(valid) <= set(self.corpus.registered):
                self.corpus.registries.add(id(members))
            for member, (subschema, file) in valid.items():
                members.add(member, self.shape(subschema, file))
                if members.shapes[member].kind == "map":
                    self.corpus.maps.add(member)
        if isinstance(tokens := node.get("enum"), list):
            namespace = self.corpus.new("tokens", owner, origin)
            for token in tokens:
                namespace.add(str(token))
        for keyword, value in node.items():
            if keyword in ("properties", "$defs") and isinstance(value, dict):
                for name, subschema in value.items():
                    self.walk(subschema, current, f"{pointer}/{keyword}/{name}", name)
            elif keyword not in CONSTRAINTS:
                self.walk(value, current, f"{pointer}/{keyword}", owner)


def vocabulary(files: dict[str, JsonValue], corpus: Corpus) -> None:
    """The names the vocabulary registers, each list a namespace: sections, fields per section, conditions and
    specimen facts; and its lists of tokens that are no enumeration in `$defs`, which the schema walk reads:
    each token condition's tokens and the acceptance kinds."""

    def entries(name: str, member: str) -> dict[str, JsonValue]:
        return mapping(mapping(files[f"vocabulary/{name}"])[member])

    sections: dict[str, Namespace] = {}
    every = corpus.new("tokens", "sections", "vocabulary/fields.json")
    for qualified in entries("fields.json", "fields"):
        section, _, name = qualified.partition(".")
        if section not in sections:
            sections[section] = corpus.new("tokens", f"{section}.fields", "vocabulary/fields.json")
        sections[section].add(name)
        every.add(section)
        corpus.registered.setdefault(name, f"the field {qualified}")
        corpus.registered.setdefault(section, "a section")
    for name, member, registered in [
        ("conditions.json", "conditions", "a condition"),
        ("specimen_facts.json", "facts", "a specimen fact"),
    ]:
        namespace = corpus.new("tokens", member, f"vocabulary/{name}")
        for registered_name in entries(name, member):
            namespace.add(registered_name)
            corpus.registered.setdefault(registered_name, registered)
    for condition, entry in entries("conditions.json", "conditions").items():
        if isinstance(tokens := mapping(entry).get("tokens"), list):
            namespace = corpus.new("tokens", condition, "vocabulary/conditions.json")
            for token in tokens:
                namespace.add(str(token))
    namespace = corpus.new("tokens", "acceptance", "vocabulary/acceptances.json")
    for kind in listing(mapping(files["vocabulary/acceptances.json"])["kinds"]):
        namespace.add(str(kind))


# The specification.


def examples(text: str) -> Iterator[tuple[int, JsonValue]]:
    """Each fenced JSON example and its line, a fragment wrapped in braces and `...` read as null."""
    for block in re.finditer(r"```json\n(.*?)\n```", text, re.S):
        body = block[1].strip()
        line = text.count("\n", 0, block.start()) + 2
        for candidate in (body, "{" + body + "}"):
            for variant in (candidate, re.sub(r'(?<!["\w])\.\.\.(?!["\w])', "null", candidate)):
                try:
                    yield line, json.loads(variant)
                except json.JSONDecodeError:
                    continue
                break
            else:
                continue
            break
        else:
            raise ValueError(f"line {line}: a JSON example that does not parse")


def example_shape(value: JsonValue, key: str, corpus: Corpus) -> Shape:
    if isinstance(value, bool):
        return Shape("boolean")
    if isinstance(value, int | float):
        return Shape("number")
    if isinstance(value, str):
        return Shape("string", frozenset({value}))
    if isinstance(value, list):
        shapes = {example_shape(item, f"{key}[]", corpus) for item in value} - {UNKNOWN}
        return Shape("array", item=shapes.pop() if len(shapes) == 1 else UNKNOWN)
    if isinstance(value, dict):
        if is_status(value) or not value:
            return UNKNOWN
        if is_map(value, key, corpus):
            return Shape("map")
        return Shape("object", frozenset(value))
    return UNKNOWN


def strings(value: JsonValue) -> set[str]:
    """The strings an example member holds: itself, or the items of a list."""
    items = value if isinstance(value, list) else [value]
    return {item for item in items if isinstance(item, str)}


def is_status(value: dict[str, JsonValue]) -> bool:
    return "status" in value and set(value) <= {"status", "reason"}


def is_map(value: dict[str, JsonValue], key: str, corpus: Corpus) -> bool:
    """Whether an example object is keyed by names: the value of a member that holds a map, or one whose every
    key is registered or no name at all."""
    return key in MAPS | corpus.maps or all(
        name in corpus.registered or not NAME.fullmatch(name) for name in value
    )


def walk_example(value: JsonValue, origin: str, key: str, corpus: Corpus) -> None:
    if isinstance(value, list):
        for item in value:
            walk_example(item, origin, f"{key}[]", corpus)
        return
    if not isinstance(value, dict):
        return
    keyed = is_map(value, key, corpus)
    if value and not keyed and not is_status(value):
        members = corpus.new("members", key, origin)
        for member, held in value.items():
            if NAME.fullmatch(member):
                members.add(member, example_shape(held, member, corpus), strings(held))
    for member, held in value.items():
        walk_example(held, origin, key if keyed else member, corpus)


def tables(text: str) -> Iterator[tuple[str, str, int, list[list[str]]]]:
    """Each table, with the heading it sits under, the line above it, and the line it starts at."""
    lines = text.splitlines()
    heading = above = ""
    index = 0
    while index < len(lines):
        if lines[index].startswith("|"):
            start = index
            while index < len(lines) and lines[index].startswith("|"):
                index += 1
            yield heading, above, start + 1, [cells(line) for line in lines[start:index]]
            continue
        if lines[index].startswith("#"):
            heading = lines[index].lstrip("# ")
        if lines[index].strip():
            above = lines[index]
        index += 1


def read_tables(name: str, text: str, corpus: Corpus) -> None:
    """The member names of each table whose first column is `Member`, and the tokens of each whose first
    column names a token list (`` `want` ``, `Token`, `Method`)."""
    for heading, above, line, rows in tables(text):
        if above in VOCABULARY_TABLES or len(rows) < 3:
            continue
        first, body = rows[0][0], rows[2:]
        if first == "Member":
            namespace = corpus.new("members", heading, f"{SPECIFICATION / name}:{line}")
        elif re.fullmatch(r"`[a-z_]+`|Token|Method", first):
            namespace = corpus.new("tokens", first.strip("`"), f"{SPECIFICATION / name}:{line}")
        else:
            continue
        for row in body:
            if re.fullmatch(r"`[a-z0-9_]+`(?:(?:,|, and| and| or|, or) `[a-z0-9_]+`)*", row[0]):
                for found in re.findall(r"`([a-z0-9_]+)`", row[0]):
                    namespace.add(found)


def specification(root: Path, corpus: Corpus) -> None:
    for path in sorted((root / SPECIFICATION).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for line, value in examples(text):
            walk_example(value, f"{SPECIFICATION / path.name}:{line}", "", corpus)
        read_tables(path.name, text, corpus)
        flowing = re.sub(r"\s+", " ", text)
        for pattern in NAME_KEYED:
            for match in pattern.finditer(flowing):
                for name in re.findall(r"`([a-z_]+)`", match[1]):
                    corpus.name_keyed.setdefault(name, f"{SPECIFICATION / path.name}")


def collect(root: Path) -> Corpus:
    corpus = Corpus()
    files = load(root)
    vocabulary(files, corpus)
    schemas = Schemas(files, corpus)
    for name, contents in files.items():
        schemas.walk(contents, name, "", Path(name).stem)
    specification(root, corpus)
    return corpus


# Rule A.


def one_meaning(shapes: set[Shape], lists: list[frozenset[str]]) -> bool:
    """Whether shapes can all be one meaning: of one JSON type; strings either free, or each value an example
    shows and each token list held by one list of the corpus (a list restricted at each place: a block's
    `distribution` and an uncertainty's, both distribution tokens); objects joined by shared members; arrays
    of items that can be one meaning."""
    shapes = shapes - {UNKNOWN}
    kinds = {"string" if shape.kind == "tokens" else shape.kind for shape in shapes}
    if len(kinds) != 1:
        return len(kinds) == 0
    kind = kinds.pop()
    if kind == "string":
        held = [shape.names for shape in shapes if shape.kind == "tokens"]
        needed = frozenset[str]().union(*(shape.names for shape in shapes))
        return not held or any(needed <= tokens for tokens in lists)
    if kind == "object":
        objects = sorted((shape.names for shape in shapes), key=sorted)
        reached = set(objects.pop(0))
        while joined := [names for names in objects if names & reached]:
            for names in joined:
                reached |= names
                objects.remove(names)
        return not objects
    if kind == "array":
        return one_meaning({shape.item or UNKNOWN for shape in shapes}, lists)
    return True


def meanings(places: list[set[Shape]], lists: list[frozenset[str]]) -> list[set[Shape]]:
    """The places of one name grouped into meanings. A place is the shapes one object gives the name (a
    region's analytic or external `geometry` in one example), one meaning by definition; it joins every
    meaning it can be one with, together, or else the first."""
    groups: list[set[Shape]] = []
    for place in places:
        shapes = place - {UNKNOWN}
        if not shapes:
            continue
        joined = [index for index, group in enumerate(groups) if one_meaning(group | shapes, lists)]
        together = shapes.union(*(groups[index] for index in joined))
        if len(joined) > 1 and not one_meaning(together, lists):
            joined, together = joined[:1], shapes | groups[joined[0]]
        groups = [group for index, group in enumerate(groups) if index not in joined] + [together]
    return groups


def describe(shape: Shape) -> str:
    if shape.kind in ("tokens", "object"):
        return f"{shape.kind} {{{', '.join(sorted(shape.names))}}}"
    if shape.kind == "array" and shape.item is not None:
        return f"array of {describe(shape.item)}"
    return shape.kind


def rule_a(corpus: Corpus) -> list[Flag]:
    flags: list[Flag] = []
    places: dict[str, dict[tuple[str, str], set[Shape]]] = {}
    lists = [frozenset(namespace.shapes) for namespace in corpus.namespaces if namespace.kind == "tokens"]
    for namespace in corpus.namespaces:
        if namespace.kind == "members":
            for name, shape in namespace.shapes.items():
                places.setdefault(name, {}).setdefault((namespace.origin, namespace.owner), set()).add(shape)
                if shape.kind == "tokens":
                    lists.append(shape.names)
    for name, found in sorted(places.items()):
        groups = meanings(list(found.values()), lists)
        if len(name) > 1 and len(groups) > 1:
            keyed = f"; addressed by name in {corpus.name_keyed[name]}" if name in corpus.name_keyed else ""
            detail = " | ".join(" or ".join(sorted(map(describe, group))) for group in groups) + keyed
            flags.append(Flag("A", (name,), "*", detail, len(groups)))
    for name, registered in sorted(corpus.registered.items()):
        owners = sorted(
            {
                namespace.owner
                for namespace in corpus.namespaces
                if namespace.kind == "members"
                and name in namespace.shapes
                and id(namespace) not in corpus.registries
            }
        )
        if owners:
            flags.append(
                Flag("A", (name,), "registered", f"{registered}, and a member of {', '.join(owners)}")
            )
    return flags + sibling_tokens(corpus) + two_vocabularies(corpus)


def sibling_tokens(corpus: Corpus) -> list[Flag]:
    """One token in the lists of two members of one object, neither list holding the other: moved between the
    two, it passes both."""
    found: dict[tuple[str, str], Flag] = {}
    for namespace in corpus.namespaces:
        lists = [(name, shape.names) for name, shape in namespace.shapes.items() if shape.kind == "tokens"]
        for i, (first, a) in enumerate(lists):
            for second, b in lists[i + 1 :]:
                if not (a <= b or b <= a):
                    for token in sorted(a & b):
                        owner = " | ".join(sorted((first, second)))
                        found.setdefault(
                            (token, owner), Flag("A", (token,), owner, f"a token of both {owner}")
                        )
    return list(found.values())


def two_vocabularies(corpus: Corpus) -> list[Flag]:
    """A member whose example values hold two or more tokens of another member's list, and other values too: a
    value of one vocabulary standing in a member of another."""
    samples: dict[str, set[str]] = {}
    lists: list[tuple[str, frozenset[str]]] = []
    for namespace in corpus.namespaces:
        for name, values in namespace.samples.items():
            samples.setdefault(name, set()).update(values)
        lists += [(name, shape.names) for name, shape in namespace.shapes.items() if shape.kind == "tokens"]
    flags: list[Flag] = []
    for name, values in sorted(samples.items()):
        for owner, tokens in lists:
            inside = values & tokens
            if owner != name and len(inside) >= 2 and values - inside:
                detail = f"holds {sorted(inside)} of `{owner}`, and {sorted(values - inside)[:4]}"
                flags.append(Flag("A", (name,), owner, detail))
                break
    return flags


# Rule B.


def rule_b(corpus: Corpus) -> list[Flag]:
    """Pairs one slip apart in one namespace; then, in the condition and specimen-fact names taken together,
    the pairs no namespace of its own has given."""
    sibling_maps = Namespace("tokens", "conditions | facts", "vocabulary")
    for namespace in corpus.namespaces:
        if namespace.owner in ("conditions", "facts") and namespace.origin.startswith("vocabulary/"):
            for name in namespace.shapes:
                sibling_maps.add(name)
    flags = {(flag.names, flag.owner): flag for namespace in corpus.namespaces for flag in slips(namespace)}
    pairs = {names for names, _ in flags}
    return list(flags.values()) + [flag for flag in slips(sibling_maps) if flag.names not in pairs]


def slips(namespace: Namespace) -> Iterator[Flag]:
    names = sorted(name for name in namespace.shapes if NAME.fullmatch(name))
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if (len(a) > 1 or len(b) > 1) and (slip := one_slip(a, b)):
                yield Flag("B", (a, b), namespace.owner, slip)


# The allowlist.


def normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def allowed(flags: list[Flag], allowlist: dict[str, JsonValue], root: Path) -> tuple[list[Flag], list[str]]:
    """The flags no entry allows, and the problems of the entries: one that allows no flag, one whose
    safeguard is gone from its document, and one with no safeguard that does not say why."""
    entries = [mapping(entry) for entry in listing(allowlist["entries"])]
    problems: list[str] = []
    live: list[bool] = []
    for entry in entries:
        names = sorted(str(name) for name in listing(entry["names"]))
        safeguard = entry.get("safeguard")
        if safeguard is None:
            live.append(bool(entry.get("no_safeguard_because")))
            if not live[-1]:
                problems.append(f"{names}: no safeguard, and no reason why none is needed")
            continue
        document, quote = str(mapping(safeguard)["document"]), str(mapping(safeguard)["quote"])
        path = root / document
        live.append(path.is_file() and normalised(quote) in normalised(path.read_text(encoding="utf-8")))
        if not live[-1]:
            problems.append(f"{names}: its safeguard is gone from {document}")
    used = [False] * len(entries)
    remaining: list[Flag] = []
    for flag in flags:
        index = next((index for index, entry in enumerate(entries) if allows(entry, flag)), None)
        if index is None or not live[index]:
            remaining.append(flag)
        if index is not None:
            used[index] = True
    problems += [
        f"{sorted(str(name) for name in listing(entry['names']))}: allows no flag"
        for entry, use in zip(entries, used, strict=True)
        if not use
    ]
    return remaining, problems


def allows(entry: dict[str, JsonValue], flag: Flag) -> bool:
    return (
        entry["rule"] == flag.rule
        and sorted(str(name) for name in listing(entry["names"])) == sorted(flag.names)
        and fnmatch.fnmatchcase(flag.owner, str(entry.get("owner", "*")))
        and entry.get("meanings", float(flag.meanings)) == flag.meanings
    )


def check(root: Path, allowlist: dict[str, JsonValue]) -> tuple[list[Flag], list[str]]:
    """Every flag the allowlist does not allow, and every problem with the allowlist."""
    corpus = collect(root)
    return allowed(rule_a(corpus) + rule_b(corpus), allowlist, root)
