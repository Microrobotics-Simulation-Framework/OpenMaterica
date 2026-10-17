# SPDX-License-Identifier: Apache-2.0
"""`scripts/schema_index.py`: the index pages Pages publishes for the schema tree."""

import json
import re
import shutil
from collections.abc import Collection
from pathlib import Path

import pytest

import scripts.schema_index
from scripts.freeze_schema import read_manifest
from scripts.schema_index import main, released_versions, write_indexes

REPOSITORY = Path(__file__).resolve().parents[2]
SCHEMA = REPOSITORY / "src" / "materica" / "schema"
MANIFEST = REPOSITORY / "tests" / "spec_sync" / "released_schemas.json"
NO_VERSION_RELEASED: frozenset[str] = frozenset()


def _tree(root: Path) -> Path:
    vocabulary = root / "schema" / "0.1" / "vocabulary"
    vocabulary.mkdir(parents=True)
    identifier = "https://w3id.org/materica/schema/0.1/"
    a = {"$id": f"{identifier}a.json", "title": "A <b>", "description": "x & y"}
    (root / "schema" / "0.1" / "a.json").write_text(json.dumps(a))
    (vocabulary / "v.json").write_text(json.dumps({"$id": f"{identifier}vocabulary/v.json"}))
    (root / "schema" / "0.1" / "README.md").write_text("notes")
    return root / "schema"


def test_every_directory_gets_a_page_linking_what_it_holds(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    written = write_indexes(schema, NO_VERSION_RELEASED)
    assert sorted(written) == sorted(
        [schema / "index.html", schema / "0.1" / "index.html", schema / "0.1" / "vocabulary" / "index.html"]
    )
    assert '<a href="0.1/">0.1/</a>' in (schema / "index.html").read_text()
    version = (schema / "0.1" / "index.html").read_text()
    assert '<a href="vocabulary/">vocabulary/</a>' in version
    assert '<a href="README.md">README.md</a>' in version
    assert "<code>https://w3id.org/materica/schema/0.1/a.json</code>" in version
    assert '<a href="v.json">v.json</a>' in (schema / "0.1" / "vocabulary" / "index.html").read_text()


def test_text_from_a_schema_is_escaped(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)
    version = (schema / "0.1" / "index.html").read_text()
    assert "<strong>A &lt;b&gt;</strong>" in version
    assert "x &amp; y" in version
    assert "A <b>" not in version


def test_breadcrumbs_lead_back_to_the_site(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)
    vocabulary = (schema / "0.1" / "vocabulary" / "index.html").read_text()
    crumbs = '<a href="../../../">OpenMaterica</a> / <a href="../../">schema</a> / <a href="../">0.1</a>'
    assert crumbs in vocabulary


def test_an_existing_index_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "0.1" / "vocabulary" / "index.html").write_text("published")
    with pytest.raises(ValueError, match="already holds"):
        write_indexes(schema, NO_VERSION_RELEASED)
    assert not (schema / "index.html").exists()
    assert main([str(schema)]) == 1


def test_a_json_file_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "0.1" / "list.json").write_text("[]")
    with pytest.raises(ValueError, match="no JSON object"):
        write_indexes(schema, NO_VERSION_RELEASED)


def test_the_published_tree_links_every_file_with_its_identifier(tmp_path: Path) -> None:
    schema = tmp_path / "schema"
    shutil.copytree(SCHEMA, schema)
    write_indexes(schema, released_versions(MANIFEST))
    for path in SCHEMA.rglob("*"):
        if path.is_file():
            page = (schema / path.parent.relative_to(SCHEMA) / "index.html").read_text()
            assert f'<a href="{path.name}">{path.name}</a>' in page
            if path.suffix == ".json":
                identifier = json.loads(path.read_text())["$id"]
                assert re.search(f"<code>{re.escape(identifier)}</code>", page)


NOTE = 'class="draft"'


def note_problems(schema: Path, released: Collection[str]) -> list[str]:
    """Each page of `schema` that has the draft note where its version is not released, lacks it where its
    version is, or has it beyond a version's own page."""
    problems: list[str] = []
    for page in sorted(schema.rglob("index.html")):
        parts = page.relative_to(schema).parts[:-1]
        wanted = len(parts) == 1 and parts[0] not in released
        if (NOTE in page.read_text()) != wanted:
            problems.append(f"{'/'.join(parts) or 'schema'}: the note is {'missing' if wanted else 'there'}")
    return problems


def test_a_version_not_released_has_the_draft_note_on_its_page_alone(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)
    version = (schema / "0.1" / "index.html").read_text()
    assert (
        "<strong>Draft until 0.1.0.</strong> These 0.1 schema files may change until OpenMaterica 0.1.0 is "
        in version
    )
    assert (
        "From that release they are frozen: CI fails any change to them, and a change is a new minor "
        in version
    )
    assert note_problems(schema, NO_VERSION_RELEASED) == []
    assert NOTE not in (schema / "index.html").read_text()
    assert NOTE not in (schema / "0.1" / "vocabulary" / "index.html").read_text()


def test_a_released_version_has_no_draft_note(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, {"0.1"})
    assert "Draft" not in (schema / "0.1" / "index.html").read_text()
    assert note_problems(schema, {"0.1"}) == []


def test_the_check_fails_where_the_note_is_dropped_from_a_version_not_released(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, {"0.1"})  # a page without the note ...
    assert note_problems(schema, NO_VERSION_RELEASED) == [
        "0.1: the note is missing"
    ]  # ... where it is required


def test_the_check_fails_where_the_note_is_kept_on_a_released_version(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)  # a page with the note ...
    assert note_problems(schema, {"0.1"}) == ["0.1: the note is there"]  # ... where the version is released


def test_the_check_fails_where_the_note_is_beyond_a_versions_page(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)
    page = schema / "0.1" / "vocabulary" / "index.html"
    page.write_text(page.read_text().replace("<main>", f"<main><p {NOTE}>x</p>"))
    assert note_problems(schema, NO_VERSION_RELEASED) == ["0.1/vocabulary: the note is there"]


def test_the_development_of_the_next_line_names_its_release(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "0.2-dev").mkdir()
    write_indexes(schema, {"0.1"})
    dev = (schema / "0.2-dev" / "index.html").read_text()
    assert (
        "<strong>Draft until 0.2.0.</strong> These files are the development of schema 0.2 and may change"
        in dev
    )
    assert "At that release schema 0.2 is frozen as <code>0.2/</code>." in dev
    assert note_problems(schema, {"0.1"}) == []


def test_a_directory_that_is_no_version_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "next").mkdir()
    with pytest.raises(ValueError, match="next is not a schema version"):
        write_indexes(schema, NO_VERSION_RELEASED)
    assert not (schema / "index.html").exists()


def test_the_released_versions_are_the_manifests(tmp_path: Path) -> None:
    manifest = tmp_path / "released.json"
    manifest.write_text(json.dumps({"released": {"0.1": {"a.json": "0" * 64}}}))
    assert released_versions(manifest) == {"0.1"}
    assert released_versions(MANIFEST) == set(read_manifest(MANIFEST))


@pytest.mark.parametrize("text", ["{", "[]", "{}", '{"released": []}'])
def test_a_manifest_that_lists_no_released_object_is_refused(tmp_path: Path, text: str) -> None:
    manifest = tmp_path / "released.json"
    manifest.write_text(text)
    with pytest.raises(ValueError, match=r"released\.json"):
        released_versions(manifest)
    with pytest.raises(ValueError, match=r"released\.json"):
        released_versions(tmp_path / "absent" / "released.json")


def test_the_note_leaves_the_page_when_the_manifest_lists_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "released.json"
    manifest.write_text(json.dumps({"released": {}}))
    monkeypatch.setattr(scripts.schema_index, "MANIFEST", manifest)
    schema = _tree(tmp_path)
    assert main([str(schema)]) == 0
    assert NOTE in (schema / "0.1" / "index.html").read_text()
    shutil.rmtree(tmp_path / "schema")
    schema = _tree(tmp_path)
    manifest.write_text(json.dumps({"released": {"0.1": {"a.json": "0" * 64}}}))
    assert main([str(schema)]) == 0
    assert NOTE not in (schema / "0.1" / "index.html").read_text()


def test_the_published_trees_notes_follow_the_manifest(tmp_path: Path) -> None:
    schema = tmp_path / "schema"
    shutil.copytree(SCHEMA, schema)
    released = released_versions(MANIFEST)
    write_indexes(schema, released)
    assert note_problems(schema, released) == []
    versions = {path.name for path in SCHEMA.iterdir() if path.is_dir()}
    for version in versions:
        assert (NOTE in (schema / version / "index.html").read_text()) == (version not in released)
