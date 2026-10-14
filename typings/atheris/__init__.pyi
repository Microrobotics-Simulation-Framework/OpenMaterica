# SPDX-License-Identifier: Apache-2.0
"""The part of Atheris's API the fuzz targets in `tests/fuzz/` use, typed: Atheris 3.1.0 ships no types.

For type checkers in development only; nothing in the package imports Atheris.
"""

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from typing import NoReturn

def Setup(argv: Sequence[str], test_one_input: Callable[[bytes], None], /) -> list[str]: ...
def Fuzz() -> NoReturn: ...
def instrument_imports(
    include: Sequence[str] | None = None, exclude: Sequence[str] | None = None
) -> AbstractContextManager[None]: ...
