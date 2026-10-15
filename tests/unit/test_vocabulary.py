# SPDX-License-Identifier: Apache-2.0
"""The vocabulary as the core reads it: every token list the vocabulary's files define, and the status tokens,
which no file holds."""

import json

import pytest

from materica.core import vocabulary
from materica.core.jsonio import JsonValue
from materica.core.vocabulary import STATUS_TOKENS, VOCABULARY
from tests.spec_sync.schemas import SCHEMA


def test_every_token_list_of_every_file_is_read_by_its_name() -> None:
    expected: dict[str, list[str]] = {}
    for path in sorted((SCHEMA / "vocabulary").glob("*.json")):
        for name, definition in json.loads(path.read_text(encoding="utf-8")).get("$defs", {}).items():
            if "enum" in definition:
                expected[name] = definition["enum"]
    assert {name: list(tokens) for name, tokens in VOCABULARY.token_lists.items()} == expected
    assert VOCABULARY.token_lists["statistics_distribution"] == ("normal", "lognormal")


def test_a_binding_or_a_pattern_is_no_token_list() -> None:
    assert {"units", "sections", "bulk.density", "anatomical_site_uberon"}.isdisjoint(VOCABULARY.token_lists)
    assert "density_kind_token" in VOCABULARY.token_lists


def test_the_status_tokens_are_the_writer_schemas() -> None:
    writer = json.loads((SCHEMA / "record.writer.json").read_text(encoding="utf-8"))
    assert list(STATUS_TOKENS) == writer["$defs"]["status_object"]["properties"]["status"]["enum"]


def test_two_token_lists_of_one_name_are_a_broken_installation(monkeypatch: pytest.MonkeyPatch) -> None:
    def every_file_alike(name: str) -> dict[str, JsonValue]:
        return {"$defs": {"central": {"enum": ["mean"]}}}

    monkeypatch.setattr(vocabulary, "_file", every_file_alike)
    with pytest.raises(ValueError, match="central twice"):
        vocabulary._token_lists()  # pyright: ignore[reportPrivateUsage]  # the loader the fault is fed to
