# SPDX-License-Identifier: Apache-2.0
"""A released schema version never changes (maintainer, 2026-10-14): no file under its directory is added,
removed or changed, each `$id` is still its path, and every version listed as released has its directory.

`released_schemas.json` lists each released version with every file's SHA-256, and `scripts/freeze_schema.py`
writes a version's entry at release. Where this fails, the manifest holds: a change to a released version is a
new minor version in a new directory. While no version is released the first test checks nothing, so the
controls run the check on a copy of the schema tree, with schema 0.1 frozen in a manifest of their own, and
require it to fail on each kind of change.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.freeze_schema import (
    ID_ROOT,
    MANIFEST,
    SCHEMAS,
    freeze,
    manifest_text,
    read_manifest,
    released_problems,
)


def test_every_released_schema_version_is_as_it_was_released() -> None:
    assert released_problems(MANIFEST, SCHEMAS) == []


@pytest.fixture
def frozen(tmp_path: Path) -> tuple[Path, Path]:
    """A copy of the schema tree and a manifest of its own, in which schema 0.1 is released and unchanged."""
    schemas = tmp_path / "schema"
    shutil.copytree(SCHEMAS, schemas)
    manifest = tmp_path / "released_schemas.json"
    manifest.write_text(manifest_text({}), encoding="utf-8")
    assert freeze("0.1", manifest, schemas) == []
    assert released_problems(manifest, schemas) == []
    return manifest, schemas


def test_a_changed_file_fails(frozen: tuple[Path, Path]) -> None:
    manifest, schemas = frozen
    case = schemas / "0.1" / "case.json"
    # A blank line: no JSON reader sees it, and the published bytes still differ.
    case.write_bytes(case.read_bytes() + b"\n")
    assert released_problems(manifest, schemas) == ["0.1/case.json changed"]


def test_an_added_file_fails(frozen: tuple[Path, Path]) -> None:
    manifest, schemas = frozen
    added = schemas / "0.1" / "vocabulary" / "units.json"
    added.write_text(json.dumps({"$id": f"{ID_ROOT}0.1/vocabulary/units.json"}), encoding="utf-8")
    assert released_problems(manifest, schemas) == ["0.1/vocabulary/units.json was added"]


def test_a_removed_file_fails(frozen: tuple[Path, Path]) -> None:
    manifest, schemas = frozen
    (schemas / "0.1" / "vocabulary" / "README.md").unlink()
    assert released_problems(manifest, schemas) == ["0.1/vocabulary/README.md was removed"]


def test_a_released_version_without_its_directory_fails(frozen: tuple[Path, Path]) -> None:
    manifest, schemas = frozen
    shutil.rmtree(schemas / "0.1")
    assert released_problems(manifest, schemas) == ["schema 0.1 is released but has no directory"]


def test_a_released_id_that_is_not_its_path_fails(frozen: tuple[Path, Path]) -> None:
    """A manifest edited by hand, past the helper's refusal, to freeze a file whose `$id` is wrong: the check
    reads the `$id`s, not only the digests."""
    manifest, schemas = frozen
    case = schemas / "0.1" / "case.json"
    contents = json.loads(case.read_text(encoding="utf-8"))
    contents["$id"] = f"{ID_ROOT}0.1/cases.json"
    case.write_text(json.dumps(contents), encoding="utf-8")
    released = read_manifest(manifest)
    released["0.1"]["case.json"] = hashlib.sha256(case.read_bytes()).hexdigest()
    manifest.write_text(manifest_text(released), encoding="utf-8")
    assert released_problems(manifest, schemas) == [
        f"0.1/case.json: {ID_ROOT}0.1/cases.json (an $id that is not its path)"
    ]
