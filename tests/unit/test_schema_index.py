# SPDX-License-Identifier: Apache-2.0
"""`scripts/schema_index.py`: the index pages Pages publishes for the schema tree."""

import json
import re
import shutil
from pathlib import Path

import pytest

from scripts.schema_index import main, write_indexes

SCHEMA = Path(__file__).resolve().parents[2] / "src" / "materica" / "schema"


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
    written = write_indexes(schema)
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
    write_indexes(schema)
    version = (schema / "0.1" / "index.html").read_text()
    assert "<strong>A &lt;b&gt;</strong>" in version
    assert "x &amp; y" in version
    assert "A <b>" not in version


def test_breadcrumbs_lead_back_to_the_site(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    write_indexes(schema)
    vocabulary = (schema / "0.1" / "vocabulary" / "index.html").read_text()
    crumbs = '<a href="../../../">OpenMaterica</a> / <a href="../../">schema</a> / <a href="../">0.1</a>'
    assert crumbs in vocabulary


def test_an_existing_index_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "0.1" / "vocabulary" / "index.html").write_text("published")
    with pytest.raises(ValueError, match="already holds"):
        write_indexes(schema)
    assert not (schema / "index.html").exists()
    assert main([str(schema)]) == 1


def test_a_json_file_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    schema = _tree(tmp_path)
    (schema / "0.1" / "list.json").write_text("[]")
    with pytest.raises(ValueError, match="no JSON object"):
        write_indexes(schema)


def test_the_published_tree_links_every_file_with_its_identifier(tmp_path: Path) -> None:
    schema = tmp_path / "schema"
    shutil.copytree(SCHEMA, schema)
    write_indexes(schema)
    for path in SCHEMA.rglob("*"):
        if path.is_file():
            page = (schema / path.parent.relative_to(SCHEMA) / "index.html").read_text()
            assert f'<a href="{path.name}">{path.name}</a>' in page
            if path.suffix == ".json":
                identifier = json.loads(path.read_text())["$id"]
                assert re.search(f"<code>{re.escape(identifier)}</code>", page)
