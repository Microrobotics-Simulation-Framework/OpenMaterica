# SPDX-License-Identifier: Apache-2.0
"""`scripts/schema_index.py`: the index pages Pages publishes for the schema tree."""

import json
import re
import shutil
from collections.abc import Collection
from pathlib import Path

import pytest

import scripts.freeze_schema
import scripts.schema_index
from scripts.freeze_schema import read_manifest
from scripts.schema_index import draft_note, main, released_versions, write_indexes

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
    assert released_versions(scripts.schema_index.MANIFEST) == set(read_manifest(MANIFEST))


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


def _numbers_in(note: str) -> set[str]:
    """Each version number the note names, so a number that is no part of its version's shows."""
    return set(re.findall(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", note))


@pytest.mark.parametrize("line", ["0.1", "0.2", "1.0", "10.12"])
def test_the_note_of_a_version_not_released_names_that_version(tmp_path: Path, line: str) -> None:
    schema = _tree(tmp_path)
    (schema / line).mkdir(exist_ok=True)
    write_indexes(schema, {"0.1"} - {line})
    note = (schema / line / "index.html").read_text()
    assert (
        f"<strong>Draft until {line}.0.</strong> These {line} schema files may change until OpenMaterica "
        in note
    )
    assert f"{line}.0 is released. From that release they are frozen" in note
    assert _numbers_in(draft_note(line)) == {line, f"{line}.0"}


@pytest.mark.parametrize("line", ["0.2", "1.0", "10.12"])
def test_the_note_of_a_development_directory_names_its_line(tmp_path: Path, line: str) -> None:
    note = draft_note(f"{line}-dev")
    assert f"<strong>Draft until {line}.0.</strong> These files are the development of schema {line} " in note
    assert f"until OpenMaterica {line}.0 is released. At that release schema {line} is frozen as " in note
    assert _numbers_in(note) == {line, f"{line}.0"}


NOT_VERSIONS = [
    "next",
    "0.1-draft",
    "0.1x",
    "0.1-devx",
    "0.1-dev-dev",
    "0.1-DEV",
    "0.1.2",
    "0.1.0",
    "01.2",
    "0.01",
    "00.1",
    "1",
    "1.",
    ".1",
    "v0.1",
    "-dev",
    "0.1-",
    "0.1\n",
    " 0.1",
    "1\u0660.1",  # Arabic-Indic digits, which `\d` would take
    "0.1\u0661",
    "0x1",  # a dot that matches any character
    "0-1",
    "0_1",
]


@pytest.mark.parametrize("name", NOT_VERSIONS)
def test_a_name_that_is_no_versions_directory_has_no_note(name: str) -> None:
    with pytest.raises(ValueError, match="is not a schema version's directory"):
        draft_note(name)


@pytest.mark.parametrize("name", ["0.1-draft", "0.1x", "0.1-devx", "01.2", "0.1.2"])
def test_a_directory_that_only_begins_like_a_version_is_refused(tmp_path: Path, name: str) -> None:
    schema = _tree(tmp_path)
    (schema / name).mkdir()
    with pytest.raises(ValueError, match="is not a schema version's directory"):
        write_indexes(schema, NO_VERSION_RELEASED)
    assert not (schema / "index.html").exists()


@pytest.mark.parametrize("name", ["0.1", "0.2", "0.10", "1.0", "10.0", "0.2-dev", "10.12-dev"])
def test_the_names_of_a_versions_directory_are_accepted(name: str) -> None:
    assert 'class="draft"' in draft_note(name)


def test_the_root_page_says_that_a_version_not_released_may_change(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema, NO_VERSION_RELEASED)
    root = (schema / "index.html").read_text()
    assert "Until a version is released its files here may change, and its page says so." in root
    assert "pre-release" not in root


def manifest_problems(generator: Path, freezer: Path) -> list[str]:
    """Where the generator's path to the manifest, or the freezer's, is not the real file."""
    real = REPOSITORY / "tests" / "spec_sync" / "released_schemas.json"
    return [
        f"{who} reads {path}, not {real}"
        for who, path in (("the generator", generator), ("the freezer", freezer))
        if path != real or not path.is_file()
    ]


def test_the_generators_and_the_freezers_path_to_the_manifest_is_the_real_file() -> None:
    assert manifest_problems(scripts.schema_index.MANIFEST, scripts.freeze_schema.MANIFEST) == []
    assert released_versions(scripts.schema_index.MANIFEST) == set(
        read_manifest(scripts.freeze_schema.MANIFEST)
    )


def test_the_check_of_the_manifests_path_fails_where_a_path_is_wrong() -> None:
    wrong = REPOSITORY / "scripts" / "tests" / "spec_sync" / "released_schemas.json"
    assert manifest_problems(wrong, MANIFEST) == [f"the generator reads {wrong}, not {MANIFEST}"]
    assert manifest_problems(MANIFEST, wrong) == [f"the freezer reads {wrong}, not {MANIFEST}"]


@pytest.mark.parametrize("line", ["0.2", "10.12"])
def test_a_line_in_both_its_forms_is_refused_before_anything_is_written(tmp_path: Path, line: str) -> None:
    schema = _tree(tmp_path)
    (schema / f"{line}-dev").mkdir()
    (schema / line).mkdir(exist_ok=True)
    with pytest.raises(ValueError, match=f"{line}-dev/ and {line}/ both exist"):
        write_indexes(schema, {"0.1", line})
    assert not (schema / "index.html").exists()
    assert not (schema / "0.1" / "index.html").exists()
    assert main([str(schema)]) == 1


def test_a_line_in_one_form_each_is_accepted(tmp_path: Path) -> None:
    """The control of the refusal above: a development directory beside another line's release is fine."""
    schema = _tree(tmp_path)
    (schema / "0.2-dev").mkdir()
    write_indexes(schema, {"0.1"})
    assert note_problems(schema, {"0.1"}) == []
