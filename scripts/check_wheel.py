# SPDX-License-Identifier: Apache-2.0
"""Fail unless a built wheel holds what the package ships, and only that.

    python scripts/check_wheel.py dist/openmaterica-<version>-py3-none-any.whl

It checks `materica/py.typed` (PEP 561); every file under `src/materica/data/` and `src/materica/schema/`,
byte for byte, and no other there: the conformance cases, the vocabulary the reader loads and the schemas; the
licence as an SPDX expression with its file (PEP 639); no run-time dependency; and nothing outside the package
and its metadata.
"""

import sys
import zipfile
from collections.abc import Sequence
from email.parser import HeaderParser
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
PACKAGE = REPOSITORY / "src" / "materica"


def wheel_problems(wheel: Path, package: Path = PACKAGE, licence: Path = REPOSITORY / "LICENSE") -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        dist_info = {
            name.partition("/")[0] for name in names if name.partition("/")[0].endswith(".dist-info")
        }
        if len(dist_info) != 1:
            return [f"expected one .dist-info directory, found {sorted(dist_info)}"]
        (dist_info_name,) = dist_info

        if f"{package.name}/py.typed" not in names:
            problems.append(f"{package.name}/py.typed is missing")

        for tree in (package / "data", package / "schema"):
            shipped = {
                path.relative_to(package.parent).as_posix(): path
                for path in tree.rglob("*")
                if path.is_file()
            }
            for name, path in sorted(shipped.items()):
                if name not in names:
                    problems.append(f"{name} is missing")
                elif archive.read(name) != path.read_bytes():
                    problems.append(f"{name} differs from the source tree")
            prefix = tree.relative_to(package.parent).as_posix() + "/"
            problems += [
                f"{name} is not in the source tree"
                for name in sorted(names)
                if name.startswith(prefix) and name not in shipped
            ]

        metadata = HeaderParser().parsestr(archive.read(f"{dist_info_name}/METADATA").decode("utf-8"))
        if metadata["License-Expression"] != "Apache-2.0":
            problems.append(f"License-Expression is {metadata['License-Expression']!r}, not 'Apache-2.0'")
        if metadata.get_all("License-File") != [licence.name]:
            problems.append(f"License-File is {metadata.get_all('License-File')}, not [{licence.name!r}]")
        licence_name = f"{dist_info_name}/licenses/{licence.name}"
        if licence_name not in names or archive.read(licence_name) != licence.read_bytes():
            problems.append(f"{licence_name} is missing or differs from {licence.name}")
        if metadata.get_all("Requires-Dist"):
            problems.append(f"run-time dependencies: {metadata.get_all('Requires-Dist')}")

        stray = sorted({name.partition("/")[0] for name in names} - {package.name, dist_info_name})
        if stray:
            problems.append(f"outside the package and its metadata: {stray}")
    return problems


def main(arguments: Sequence[str] | None = None) -> int:
    wheels = [Path(argument) for argument in (sys.argv[1:] if arguments is None else arguments)]
    if len(wheels) != 1:
        print("usage: python scripts/check_wheel.py <wheel>", file=sys.stderr)
        return 2
    problems = wheel_problems(wheels[0])
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
