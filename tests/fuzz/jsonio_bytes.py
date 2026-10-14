# SPDX-License-Identifier: Apache-2.0
# Atheris installs on Python 3.12 to 3.14 only; elsewhere its stub in typings/ stands in for it.
# pyright: reportMissingModuleSource=false
"""Fuzz target: raw bytes into `materica.core.jsonio.parse` (`record_format.md` section 1 item 6).

    python -m tests.fuzz.jsonio_bytes --seed CORPUS        # copy the seed corpus into CORPUS
    python -m tests.fuzz.jsonio_bytes CORPUS -dict=tests/fuzz/json.dict [libFuzzer options]

Every input must give a JSON value or `malformed`, never an exception. It must also agree with a reference
reader built here from the standard library's json, with hooks that refuse exactly the faults the item lists:
a value it accepts must equal the reference's, numbers bit for bit, and a refusal must be one of those faults.
"""

import codecs
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

import atheris

# Imported first, and inside this block, so that Atheris instruments the core for its coverage.
with atheris.instrument_imports(include=["materica"]):
    from materica.core import jsonio

from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from tests.fuzz import seeded_fault
from tests.property.support import same

CONFORMANCE = Path(jsonio.__file__).parents[1] / "data" / "conformance"
LISTED = (
    "byte_order_mark",
    "not_utf8",
    "grammar",
    "repeated_name",
    "nan_or_infinity",
    "rounds_to_infinity",
    "unpaired_surrogate",
    "too_deep",
)
_SURROGATE = re.compile("[\ud800-\udfff]")


class Refused(Exception):
    """The reference reader's refusal, naming the fault of item 6 it found."""

    def __init__(self, fault: str) -> None:
        super().__init__(fault)
        self.fault = fault


def reference(data: bytes) -> JsonValue | Refused:
    """`data` read by item 6 with the standard library's json, or the refusal of the fault it holds."""
    try:
        return _reference(data)
    except Refused as refusal:
        return refusal


def _reference(data: bytes) -> JsonValue:
    if data.startswith(codecs.BOM_UTF8):
        raise Refused("byte_order_mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("not_utf8") from None
    try:
        value: JsonValue = json.loads(
            text,
            object_pairs_hook=_no_repeats,
            parse_constant=_no_constant,
            parse_float=_finite,
            parse_int=_finite,
        )
    except RecursionError:
        raise Refused("too_deep") from None
    except json.JSONDecodeError:
        raise Refused("grammar") from None
    if _depth(value) > 64:
        raise Refused("too_deep")
    if any(_SURROGATE.search(string) for string in _strings(value)):
        raise Refused("unpaired_surrogate")
    return value


def _no_repeats(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    if len({name for name, _ in pairs}) < len(pairs):
        raise Refused("repeated_name")
    return dict(pairs)


def _no_constant(name: str) -> float:
    raise Refused("nan_or_infinity")


def _finite(text: str) -> float:
    number = float(text)
    if math.isinf(number):
        raise Refused("rounds_to_infinity")
    return number


def _depth(value: JsonValue) -> int:
    if isinstance(value, list):
        return 1 + max((_depth(item) for item in value), default=0)
    if isinstance(value, dict):
        return 1 + max((_depth(member) for member in value.values()), default=0)
    return 0


def _strings(value: JsonValue) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [string for item in value for string in _strings(item)]
    if isinstance(value, dict):
        return [*value, *(string for member in value.values() for string in _strings(member))]
    return []


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
