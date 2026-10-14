# SPDX-License-Identifier: Apache-2.0
"""The wheel check passes a complete wheel, and fails on each thing a wheel can lack or add."""

import zipfile
from pathlib import Path

import pytest

from scripts import check_wheel

CASE = "materica/data/conformance/hash/cases/HS-001.arm.json"
VOCABULARY = "materica/schema/0.1/vocabulary/reasons.json"
SCHEMA = "materica/schema/0.1/record.reader.json"
SHIPPED = {CASE: b'{"case": "HS-001"}\n', VOCABULARY: b"{}\n", SCHEMA: b'{"type": "object"}\n'}
METADATA = "openmaterica-0.1.0.dist-info/METADATA"
LICENCE = b"Apache License\n"


def wheel_contents() -> dict[str, bytes]:
    return {
        "materica/__init__.py": b"",
        "materica/py.typed": b"",
        **SHIPPED,
        METADATA: b"Metadata-Version: 2.4\nLicense-Expression: Apache-2.0\nLicense-File: LICENSE\n",
        "openmaterica-0.1.0.dist-info/licenses/LICENSE": LICENCE,
    }


def problems(tmp_path: Path, contents: dict[str, bytes]) -> list[str]:
    package = tmp_path / "src" / "materica"
    for name, data in SHIPPED.items():
        (package.parent / name).parent.mkdir(parents=True, exist_ok=True)
        (package.parent / name).write_bytes(data)
    licence = tmp_path / "LICENSE"
    licence.write_bytes(LICENCE)
    wheel = tmp_path / "openmaterica-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    return check_wheel.wheel_problems(wheel, package=package, licence=licence)


def test_a_complete_wheel_passes(tmp_path: Path) -> None:
    assert problems(tmp_path, wheel_contents()) == []


@pytest.mark.parametrize(
    ("name", "data"),
    [
        pytest.param("materica/py.typed", None, id="no_py_typed"),
        pytest.param(CASE, None, id="case_missing"),
        pytest.param(CASE, b'{"case": "HS-002"}\n', id="case_differs"),
        pytest.param("materica/data/conformance/hash/cases/extra.json", b"{}", id="case_added"),
        pytest.param(VOCABULARY, None, id="vocabulary_missing"),
        pytest.param(SCHEMA, b"{}", id="schema_differs"),
        pytest.param("materica/schema/0.1/extra.json", b"{}", id="schema_added"),
        pytest.param(METADATA, b"Metadata-Version: 2.4\nLicense-File: LICENSE\n", id="no_licence_expression"),
        pytest.param("openmaterica-0.1.0.dist-info/licenses/LICENSE", b"other", id="licence_differs"),
        pytest.param(
            METADATA,
            wheel_contents()[METADATA] + b"Requires-Dist: numpy\n",
            id="run_time_dependency",
        ),
        pytest.param("tests/test_x.py", b"", id="outside_the_package"),
    ],
)
def test_each_fault_is_found(tmp_path: Path, name: str, data: bytes | None) -> None:
    contents = wheel_contents()
    if data is None:
        del contents[name]
    else:
        contents[name] = data
    assert problems(tmp_path, contents)
