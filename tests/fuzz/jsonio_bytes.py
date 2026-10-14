# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target: raw bytes into `materica.core.jsonio.parse` (`record_format.md` section 1 item 6).

    python -m tests.fuzz.jsonio_bytes --seed CORPUS        # copy the seed corpus into CORPUS
    python -m tests.fuzz.jsonio_bytes CORPUS -dict=tests/fuzz/json.dict [libFuzzer options]

Every input must give a JSON value or `malformed`, never an exception. It must also agree with the reference
reader (`tests/conformance/reference_reader.py`), the standard library's json with hooks that refuse exactly
the faults the item lists: a value it accepts must equal the reference's, numbers bit for bit, and a refusal
must be one of those faults.
"""

import os
import shutil
import sys
from pathlib import Path

import atheris

# Imported first, and inside this block, so that Atheris instruments the core for its coverage.
with atheris.instrument_imports(include=["materica"]):
    from materica.core import jsonio

from materica.core.reasons import Reason
from tests.conformance.reference_reader import LISTED, Refused, reference
from tests.fuzz import seeded_fault
from tests.property.support import same

CONFORMANCE = Path(jsonio.__file__).parents[1] / "data" / "conformance"


def test_one_input(data: bytes) -> None:
    result = jsonio.parse(data)
    expected = reference(data)
    if isinstance(expected, Refused):
        assert expected.fault in LISTED, expected.fault
        assert result == Reason("malformed"), f"accepted what item 6 refuses ({expected.fault})"
        return
    assert not isinstance(result, Reason), f"refused what item 6 accepts: {result.detail}"
    assert same(expected, result), "read otherwise than the reference"


def seed_corpus(directory: Path) -> None:
    """Copies every conformance input, valid and broken, into `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    for path in sorted(CONFORMANCE.glob("*/inputs/*")):
        shutil.copyfile(path, directory / f"{path.parent.parent.name}-{path.name}")


def main(arguments: list[str]) -> None:
    if arguments[1:2] == ["--seed"]:
        seed_corpus(Path(arguments[2]))
        return
    seeded_fault.seed_if_asked()
    # libFuzzer re-executes its argv[0] to merge a corpus or minimise a crash: the wrapper beside this file,
    # run with this interpreter.
    os.environ.setdefault("MATERICA_FUZZ_PYTHON", sys.executable)
    atheris.Setup([str(Path(__file__).with_suffix(".sh")), *arguments[1:]], test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main(sys.argv)
