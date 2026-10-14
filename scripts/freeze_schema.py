# SPDX-License-Identifier: Apache-2.0
"""Freeze a schema version at its release, and check that no released version has changed since.

    python scripts/freeze_schema.py 0.1        # at release: add schema 0.1 to the manifest
    python scripts/freeze_schema.py --check    # fail where a released version differs from the manifest

Until a schema version is released its files may change; once it is released they never change, and a change
is a new minor version in a new directory (maintainer, 2026-10-14). The manifest,
`tests/spec_sync/released_schemas.json`, lists each released version with every file under
`src/materica/schema/<version>/`, by its path there, and the SHA-256 of its bytes. It lies outside the
published tree, so the wheel and the site hold the schemas and nothing else.

A version is frozen only if each of its JSON files has its path under `https://w3id.org/materica/schema/` as
its `$id`. An entry is never rewritten: freezing a released version again passes only if nothing changed.
`--check` reports, for each released version, a file added, removed or changed, an `$id` that is not its path,
and a missing directory; `tests/spec_sync/test_released_schemas.py` runs the same check.
"""

import hashlib
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
SCHEMAS = REPOSITORY / "src" / "materica" / "schema"
MANIFEST = REPOSITORY / "tests" / "spec_sync" / "released_schemas.json"
ID_ROOT = "https://w3id.org/materica/schema/"
COMMENT = (
    "Each released schema version, with every file under src/materica/schema/<version>/ and the SHA-256 of "
    "its bytes. Written by scripts/freeze_schema.py at release. A released version's files never change "
    "(tests/spec_sync/test_released_schemas.py)."
)
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
DIGEST = re.compile(r"[0-9a-f]{64}")

Json = bool | int | float | str | list["Json"] | dict[str, "Json"] | None
Released = dict[str, dict[str, str]]


class ManifestError(ValueError):
    """A manifest that is not exactly a map from released versions to their files' digests."""


def digests(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def misplaced_ids(root: Path, base: str) -> list[str]:
    """Each JSON file under `root` whose `$id` is not `base` followed by its path under `root`."""
    misplaced: list[str] = []
    for path in sorted(root.rglob("*.json")):
        name = path.relative_to(root).as_posix()
        try:
            contents: Json = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            contents = None
        stated = contents.get("$id") if isinstance(contents, dict) else None
        if stated != base + name:
            misplaced.append(f"{name}: {stated}")
    return misplaced


def _unique_names(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    members = dict(pairs)
    if len(members) != len(pairs):
        raise ManifestError(f"a name is repeated among {sorted(members)}")
    return members


def read_manifest(manifest: Path) -> Released:
    try:
        contents: Json = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=_unique_names)
    except json.JSONDecodeError as error:
        raise ManifestError(f"not JSON: {error}") from error
    if not isinstance(contents, dict) or set(contents) != {"$comment", "released"}:
        raise ManifestError("expected an object of `$comment` and `released`")
    released = contents["released"]
    if not isinstance(released, dict):
        raise ManifestError("`released` is not an object")
    checked: Released = {}
    for version, files in released.items():
        if not (VERSION.fullmatch(version) and isinstance(files, dict) and files):
            raise ManifestError(f"{version!r} is not a schema version with its files")
        checked[version] = {}
        for name, digest in files.items():
            if not (isinstance(digest, str) and DIGEST.fullmatch(digest)):
                raise ManifestError(f"{version}/{name}: {digest!r} is not a SHA-256 digest")
            checked[version][name] = digest
    return checked


def manifest_text(released: Released) -> str:
    def components(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))

    ordered = {
        version: dict(sorted(released[version].items())) for version in sorted(released, key=components)
    }
    return json.dumps({"$comment": COMMENT, "released": ordered}, indent=2) + "\n"


def _differences(version: str, frozen: dict[str, str], present: dict[str, str]) -> list[str]:
    return [
        *(f"{version}/{name} was removed" for name in sorted(frozen.keys() - present.keys())),
        *(f"{version}/{name} was added" for name in sorted(present.keys() - frozen.keys())),
        *(
            f"{version}/{name} changed"
            for name in sorted(frozen.keys() & present.keys())
            if frozen[name] != present[name]
        ),
    ]


def _misplaced(version: str, directory: Path) -> list[str]:
    return [
        f"{version}/{entry} (an $id that is not its path)"
        for entry in misplaced_ids(directory, f"{ID_ROOT}{version}/")
    ]


def released_problems(manifest: Path, schemas: Path) -> list[str]:
    """What differs in each released version from what was frozen: nothing, where none has changed."""
    problems: list[str] = []
    for version, frozen in read_manifest(manifest).items():
        directory = schemas / version
        if not directory.is_dir():
            problems.append(f"schema {version} is released but has no directory")
            continue
        problems += _differences(version, frozen, digests(directory))
        problems += _misplaced(version, directory)
    return problems


def freeze(version: str, manifest: Path, schemas: Path) -> list[str]:
    """Add `version`'s entry to the manifest, or write nothing and return why it cannot be frozen."""
    if not VERSION.fullmatch(version):
        return [f"{version!r} is not a schema version, MAJOR.MINOR"]
    directory = schemas / version
    if not directory.is_dir():
        return [f"schema {version} has no directory"]
    present = digests(directory)
    if not present:
        return [f"schema {version} has no files"]
    misplaced = _misplaced(version, directory)
    if misplaced:
        return misplaced
    released = read_manifest(manifest)
    if version in released:
        differences = _differences(version, released[version], present)
        if differences:
            return [f"schema {version} is released, and its files never change", *differences]
        return []
    manifest.write_text(manifest_text({**released, version: present}), encoding="utf-8")
    return []


def main(arguments: Sequence[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1 or (arguments[0].startswith("-") and arguments[0] != "--check"):
        print("usage: python scripts/freeze_schema.py <MAJOR.MINOR> | --check", file=sys.stderr)
        return 2
    try:
        if arguments[0] == "--check":
            problems = released_problems(MANIFEST, SCHEMAS)
        else:
            problems = freeze(arguments[0], MANIFEST, SCHEMAS)
    except ManifestError as error:
        problems = [f"{MANIFEST.name}: {error}"]
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
