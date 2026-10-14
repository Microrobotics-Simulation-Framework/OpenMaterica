# SPDX-License-Identifier: Apache-2.0
"""`scripts/freeze_schema.py` writes a version's entry with every file and its digest, never rewrites one, and
refuses a version it must not freeze and a manifest it cannot read, writing nothing."""

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import freeze_schema
from scripts.freeze_schema import ID_ROOT, SCHEMAS, ManifestError, manifest_text, read_manifest

EMPTY = manifest_text({})


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A copy of the schema tree and an empty manifest, which the script's `main` reads in place of the
    repository's."""
    schemas = tmp_path / "schema"
    shutil.copytree(SCHEMAS, schemas)
    manifest = tmp_path / "released_schemas.json"
    manifest.write_text(EMPTY, encoding="utf-8")
    monkeypatch.setattr(freeze_schema, "SCHEMAS", schemas)
    monkeypatch.setattr(freeze_schema, "MANIFEST", manifest)
    return manifest, schemas


def test_freezing_lists_every_file_with_its_digest_and_then_checks(tree: tuple[Path, Path]) -> None:
    manifest, schemas = tree
    assert freeze_schema.main(["0.1"]) == 0
    version = schemas / "0.1"
    files = sorted(path.relative_to(version).as_posix() for path in version.rglob("*") if path.is_file())
    assert "vocabulary/reasons.json" in files
    entry = read_manifest(manifest)["0.1"]
    assert list(entry) == files
    assert entry["case.json"] == hashlib.sha256((version / "case.json").read_bytes()).hexdigest()
    assert freeze_schema.main(["--check"]) == 0


def test_versions_are_written_in_numeric_order() -> None:
    entry = {"README.md": "0" * 64}
    text = manifest_text({"0.10": entry, "1.0": entry, "0.9": entry})
    assert list(json.loads(text)["released"]) == ["0.9", "0.10", "1.0"]


def test_freezing_again_passes_only_if_nothing_changed(
    tree: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, schemas = tree
    assert freeze_schema.main(["0.1"]) == 0
    frozen = manifest.read_bytes()
    assert freeze_schema.main(["0.1"]) == 0
    assert manifest.read_bytes() == frozen
    readme = schemas / "0.1" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nA late note.\n", encoding="utf-8")
    assert freeze_schema.main(["0.1"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        "schema 0.1 is released, and its files never change",
        "0.1/README.md changed",
    ]
    assert manifest.read_bytes() == frozen
    assert freeze_schema.main(["--check"]) == 1


def misplace_an_id(schemas: Path) -> None:
    case = schemas / "0.1" / "case.json"
    contents = json.loads(case.read_text(encoding="utf-8"))
    contents["$id"] = f"{ID_ROOT}0.2/case.json"
    case.write_text(json.dumps(contents), encoding="utf-8")


@pytest.mark.parametrize(
    ("version", "prepare", "refusal"),
    [
        pytest.param("0.1.0", None, "'0.1.0' is not a schema version, MAJOR.MINOR", id="patch_version"),
        pytest.param("../0.1", None, "'../0.1' is not a schema version, MAJOR.MINOR", id="outside_the_tree"),
        pytest.param("0.2", None, "schema 0.2 has no directory", id="no_directory"),
        pytest.param(
            "0.1",
            misplace_an_id,
            f"0.1/case.json: {ID_ROOT}0.2/case.json (an $id that is not its path)",
            id="misplaced_id",
        ),
    ],
)
def test_a_version_that_must_not_be_frozen_is_refused(
    tree: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    version: str,
    prepare: Callable[[Path], None] | None,
    refusal: str,
) -> None:
    manifest, schemas = tree
    if prepare is not None:
        prepare(schemas)
    assert freeze_schema.main([version]) == 1
    assert capsys.readouterr().err.splitlines() == [refusal]
    assert manifest.read_text(encoding="utf-8") == EMPTY


def released(versions: str) -> str:
    return '{"$comment": "", "released": ' + versions + "}"


FILE = '{"a.json": "' + "0" * 64 + '"}'


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("{", id="not_json"),
        pytest.param('{"released": {}}', id="no_comment"),
        pytest.param('{"$comment": "", "released": {}, "draft": {}}', id="another_member"),
        pytest.param(released("[]"), id="released_not_an_object"),
        pytest.param(released('{"v0.1": ' + FILE + "}"), id="not_a_version"),
        pytest.param(released('{"0.1": {}}'), id="no_files"),
        pytest.param(released('{"0.1": ' + FILE.replace("00", "0", 1) + "}"), id="short_digest"),
        pytest.param(released('{"0.1": ' + FILE.replace("0", "g", 1) + "}"), id="not_hexadecimal"),
        pytest.param(released('{"0.1": ' + FILE + ', "0.1": ' + FILE + "}"), id="repeated_version"),
    ],
)
def test_a_manifest_that_is_not_one_is_refused(tree: tuple[Path, Path], text: str) -> None:
    manifest, _ = tree
    manifest.write_text(text, encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(manifest)
    assert freeze_schema.main(["--check"]) == 1
    assert freeze_schema.main(["0.1"]) == 1
    assert manifest.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("arguments", [[], ["0.1", "--check"], ["--help"]])
def test_other_arguments_are_a_usage_error(arguments: list[str]) -> None:
    assert freeze_schema.main(arguments) == 2
