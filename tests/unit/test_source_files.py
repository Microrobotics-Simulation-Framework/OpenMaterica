# SPDX-License-Identifier: Apache-2.0
"""Rules over the source files.

The core imports only the standard library and itself (AD 7.2, CONTRIBUTING constraint 3), and
`typing_extensions` only for type checkers. Every Python file starts with its SPDX header.
"""

import ast
import sys
from pathlib import Path

import pytest

import materica.core

REPOSITORY = Path(__file__).resolve().parents[2]
CORE = Path(materica.core.__file__).parent
SPDX = "# SPDX-License-Identifier: Apache-2.0"


def foreign_imports(source: str) -> list[str]:
    """The modules `source` imports that the core may not."""
    foreign: list[str] = []

    def visit(node: ast.AST, *, type_checking: bool) -> None:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for statement in node.body:
                visit(statement, type_checking=True)
            for statement in node.orelse:
                visit(statement, type_checking=type_checking)
            return
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules = [node.module or ""]
        else:
            modules = []
        for module in modules:
            top = module.partition(".")[0]
            allowed = (
                top in sys.stdlib_module_names
                or module == "materica.core"
                or module.startswith("materica.core.")
                or (type_checking and top == "typing_extensions")
            )
            if not allowed:
                foreign.append(module)
        for child in ast.iter_child_nodes(node):
            visit(child, type_checking=type_checking)

    visit(ast.parse(source), type_checking=False)
    return foreign


@pytest.mark.parametrize("path", sorted(CORE.rglob("*.py")), ids=lambda path: path.name)
def test_the_core_imports_only_the_standard_library_and_itself(path: Path) -> None:
    assert foreign_imports(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("source", "foreign"),
    [
        ("import json\nfrom materica.core.reasons import Reason\nfrom . import jsonio", []),
        ("import numpy", ["numpy"]),
        ("from materica import io", ["materica"]),
        ("import typing_extensions", ["typing_extensions"]),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from typing_extensions import TypeIs", []),
        ("def f():\n    import jsonschema", ["jsonschema"]),
    ],
)
def test_the_import_check_can_fail(source: str, foreign: list[str]) -> None:
    assert foreign_imports(source) == foreign


PYTHON_FILES = sorted(
    path for directory in ("src", "tests", "scripts") for path in (REPOSITORY / directory).rglob("*.py")
)


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda path: str(path.relative_to(REPOSITORY)))
def test_every_python_file_starts_with_its_spdx_header(path: Path) -> None:
    assert path.read_text(encoding="utf-8").partition("\n")[0] == SPDX
