# SPDX-License-Identifier: Apache-2.0
"""Rules over the source files.

The package is built in layers (AD 7.1): a module imports from its own layer or a lower one, and nothing in
it imports `materica_authoring`. The core imports only the standard library, itself and the generated shapes,
and `typing_extensions` only for type checkers; `shapes.py` imports only the standard library, and its stub
`shapes.pyi` `typing_extensions` besides (AD 7.2, CONTRIBUTING constraint 3). Relative imports are resolved
against the module's package and checked like absolute ones. Every Python file starts with its SPDX header.
"""

import ast
import sys
from pathlib import Path

import pytest

import materica.core
from tests.conftest import SHARDS

REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE = Path(materica.__file__).parent
CORE = Path(materica.core.__file__).parent
# REUSE-IgnoreStart
SPDX = "# SPDX-License-Identifier: Apache-2.0"
# REUSE-IgnoreEnd

# The layers that hold Python modules: the shapes, generated from the schemas (L0), the core (L2) and the
# readers of files (L4). `materica/__init__.py`, the public API, imports from every layer.
LAYERS = {"materica.shapes": 0, "materica.core": 2, "materica.io": 4}
CORE_MAY_IMPORT = ("materica.core", "materica.shapes")


def within(module: str, packages: tuple[str, ...]) -> bool:
    return any(module == package or module.startswith(package + ".") for package in packages)


def resolved(node: ast.ImportFrom, package: str) -> str:
    """The module a `from` import names, a relative one resolved against `package`; one that climbs above the
    top-level package stays as written, so that no rule allows it."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".") if package else []
    if node.level - 1 >= len(parts):
        return "." * node.level + (node.module or "")
    base = ".".join(parts[: len(parts) - (node.level - 1)])
    return f"{base}.{node.module}" if node.module else base


def imports(source: str, package: str = "") -> list[tuple[str, bool]]:
    """Each module `source`, a module of `package`, imports, and whether it does so for type checkers only."""
    found: list[tuple[str, bool]] = []

    def visit(node: ast.AST, *, type_checking: bool) -> None:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for statement in node.body:
                visit(statement, type_checking=True)
            for statement in node.orelse:
                visit(statement, type_checking=type_checking)
            return
        if isinstance(node, ast.Import):
            found.extend((alias.name, type_checking) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # `from materica import shapes` imports the module `materica.shapes`, and so does `from .. import
            # shapes` in the core.
            module = resolved(node, package)
            names = [f"{module}.{alias.name}" for alias in node.names] if module == "materica" else [module]
            found.extend((name, type_checking) for name in names)
        for child in ast.iter_child_nodes(node):
            visit(child, type_checking=type_checking)

    visit(ast.parse(source), type_checking=False)
    return found


def foreign_imports(source: str, package: str = "materica.core") -> list[str]:
    """The modules `source`, a module of the core, imports that the core may not."""
    return [
        module
        for module, type_checking in imports(source, package)
        if not (
            module.partition(".")[0] in sys.stdlib_module_names
            or within(module, CORE_MAY_IMPORT)
            or (type_checking and module.partition(".")[0] == "typing_extensions")
        )
    ]


def layer_violations(source: str, layer: int, package: str = "") -> list[str]:
    """The modules of this package, or of `materica_authoring`, that a module of `layer` may not import."""
    return [
        module
        for module, _ in imports(source, package)
        if module.partition(".")[0] == "materica_authoring"
        or (
            module.partition(".")[0] == "materica"
            and not any(within(module, (name,)) and number <= layer for name, number in LAYERS.items())
        )
    ]


def outside_the_standard_library(source: str, package: str = "materica") -> list[str]:
    return [
        module
        for module, _ in imports(source, package)
        if module.partition(".")[0] not in sys.stdlib_module_names
    ]


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(PACKAGE.parent).with_suffix("").parts).removesuffix(".__init__")


def package_name(path: Path) -> str:
    return module_name(path) if path.name == "__init__.py" else module_name(path).rpartition(".")[0]


@pytest.mark.parametrize("path", sorted(CORE.rglob("*.py")), ids=lambda path: path.name)
def test_the_core_imports_only_the_standard_library_itself_and_the_shapes(path: Path) -> None:
    assert foreign_imports(path.read_text(encoding="utf-8"), package_name(path)) == []


def test_the_shapes_import_only_the_standard_library_and_their_stub_typing_extensions() -> None:
    assert outside_the_standard_library((PACKAGE / "shapes.py").read_text(encoding="utf-8")) == []
    stub = (PACKAGE / "shapes.pyi").read_text(encoding="utf-8")
    assert set(outside_the_standard_library(stub)) <= {"typing_extensions"}


@pytest.mark.parametrize(
    ("source", "outside"),
    [
        ("from __future__ import annotations\nfrom typing import Literal, NotRequired, TypedDict", []),
        ("from typing_extensions import ReadOnly", ["typing_extensions"]),
        ("from materica.core.jsonio import JsonValue", ["materica.core.jsonio"]),
        ("from . import core", ["materica.core"]),
        ("from .core.jsonio import JsonValue", ["materica.core.jsonio"]),
    ],
)
def test_the_shapes_check_can_fail(source: str, outside: list[str]) -> None:
    assert outside_the_standard_library(source) == outside


@pytest.mark.parametrize(
    ("source", "foreign"),
    [
        ("import json\nfrom materica.core.reasons import Reason\nfrom . import jsonio", []),
        ("from materica import shapes\nfrom materica.shapes import ReasonCode", []),
        ("import numpy", ["numpy"]),
        ("from materica import io", ["materica.io"]),
        ("from materica.io.plain import load_records", ["materica.io.plain"]),
        ("import typing_extensions", ["typing_extensions"]),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from typing_extensions import TypeIs", []),
        ("def f():\n    import jsonschema", ["jsonschema"]),
        ("from ..io import plain", ["materica.io"]),
        ("from .. import io, shapes", ["materica.io"]),
        ("from ..io.plain import load_records", ["materica.io.plain"]),
        ("from .reasons import Reason\nfrom .. import shapes", []),
        ("from .... import elsewhere", ["...."]),
    ],
)
def test_the_import_check_can_fail(source: str, foreign: list[str]) -> None:
    assert foreign_imports(source) == foreign


def layer(path: Path) -> int:
    (number,) = [number for name, number in LAYERS.items() if within(module_name(path), (name,))]
    return number


LAYERED = sorted(path for path in PACKAGE.rglob("*.py") if path != PACKAGE / "__init__.py")


@pytest.mark.parametrize("path", LAYERED, ids=lambda path: str(path.relative_to(PACKAGE)))
def test_a_module_imports_only_its_own_layer_or_a_lower_one(path: Path) -> None:
    assert layer_violations(path.read_text(encoding="utf-8"), layer(path), package_name(path)) == []


@pytest.mark.parametrize(
    ("source", "level", "violations"),
    [
        ("from materica.core.read import read\nfrom materica import shapes", 4, []),
        ("from materica.io.plain import load_records", 2, ["materica.io.plain"]),
        ("from materica.core import jsonio", 0, ["materica.core"]),
        ("import materica", 4, ["materica"]),
        ("from materica import content_hash", 4, ["materica.content_hash"]),
        ("import materica_authoring.scaffold", 6, ["materica_authoring.scaffold"]),
        ("from ..io import plain", 2, ["materica.io"]),
        ("from .. import io", 2, ["materica.io"]),
        ("from . import jsonio\nfrom .. import shapes", 2, []),
    ],
)
def test_the_layer_check_can_fail(source: str, level: int, violations: list[str]) -> None:
    assert layer_violations(source, level, "materica.core") == violations


PYTHON_FILES = sorted(
    path for directory in ("src", "tests", "scripts") for path in (REPOSITORY / directory).rglob("*.py")
)


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda path: str(path.relative_to(REPOSITORY)))
def test_every_python_file_starts_with_its_spdx_header(path: Path) -> None:
    assert path.read_text(encoding="utf-8").partition("\n")[0] == SPDX


def test_every_property_module_is_in_one_shard() -> None:
    modules = sorted(path.stem for path in (REPOSITORY / "tests" / "property").glob("test_*.py"))
    assert sorted(module for shard in SHARDS.values() for module in shard) == modules


def hypothesis_shards(workflow: str) -> list[str]:
    """The shards CI's Hypothesis job runs, from its matrix line `shard: [a, b]`."""
    found = [line.strip() for line in workflow.splitlines() if line.strip().startswith("shard: [")]
    return [shard.strip() for line in found for shard in line.removeprefix("shard: [").rstrip("]").split(",")]


def test_ci_runs_every_shard() -> None:
    """A shard CI's matrix left out would never run there (the S2a-2 fix round's `step8_mutants`)."""
    workflow = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert sorted(hypothesis_shards(workflow)) == sorted(SHARDS)
    assert sorted(hypothesis_shards("        shard: [json, records, writer]\n")) != sorted(SHARDS)
