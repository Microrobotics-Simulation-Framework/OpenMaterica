# SPDX-License-Identifier: Apache-2.0
"""Write an `index.html` into a published schema tree and every directory under it.

    python3 scripts/schema_index.py <site>/schema

The Pages workflow runs it on its staged copy of `src/materica/schema/`, since GitHub Pages lists no
directory by itself. Each page links what its directory holds, and gives each JSON file's `$id`, its permanent
identifier, with the schema's `title` and `description` where it has them. It uses the standard library only,
so the workflow needs no environment, and it refuses a tree that already holds an `index.html`, rather than
overwrite a file that would otherwise be published.

The page of a schema version that is not yet released opens with a draft note: its files may change until the
release, and the release freezes them. A version is released when `tests/spec_sync/released_schemas.json`
lists it (`scripts/freeze_schema.py`), so the note leaves the page with the freezing commit, and the page of a
released version has none. A `<MAJOR>.<MINOR>-dev` directory, the development of the next line, holds the
note until its release, which publishes the schema as `<MAJOR>.<MINOR>/` (CONTRIBUTING, "Release gate").
"""

import html
import json
import re
import sys
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import cast

MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "spec_sync" / "released_schemas.json"
# A schema version's directory: the version, or the development of the line that will release it.
VERSION = re.compile(r"(?P<line>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))(?P<development>-dev)?")

# The landing page's policy (site/index.html): nothing is fetched from anywhere.
POLICY = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
SOURCE = "https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/tree/main/src/materica/schema"

# The landing page's colours and type (site/index.html), cut down to what an index uses.
STYLE = """
  :root { --bg: #fdfdfc; --surface: #f2f4f6; --fg: #1f2328; --muted: #4d5761; --link: #0a55b0;
          --visited: #6a3fa0; --rule: #c9d0d8; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121417; --surface: #1c2026; --fg: #e8eaed; --muted: #adb5bf; --link: #8cbcff;
            --visited: #c5a6f5; --rule: #3d444d; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 0 1rem; background: var(--bg); color: var(--fg); font: 1.0625rem/1.6 system-ui,
         -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
  header, main, footer { max-width: 40rem; margin: 0 auto; }
  header { padding: 2.5rem 0 0.5rem; }
  h1 { font-size: 1.75rem; line-height: 1.2; margin: 0.25rem 0 0.75rem; overflow-wrap: anywhere; }
  p, ul { margin: 0 0 1rem; }
  ul { padding-left: 1.25rem; }
  li { margin: 0.75rem 0; }
  .muted { color: var(--muted); }
  .draft { border-left: 0.25rem solid var(--link); padding-left: 0.75rem; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
         font-size: 0.85em; background: var(--surface); padding: 0.05em 0.2em; border-radius: 0.2em;
         overflow-wrap: anywhere; }
  a { color: var(--link); text-underline-offset: 0.15em; }
  a:visited { color: var(--visited); }
  a:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; border-radius: 0.125rem; }
  footer { margin-top: 2.5rem; padding: 1rem 0 3rem; border-top: 1px solid var(--rule); color: var(--muted);
           font-size: 0.9375rem; }
"""


def released_versions(manifest: Path) -> frozenset[str]:
    """The schema versions the manifest lists as released."""
    try:
        value: object = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"{manifest}: {error}") from error
    released = cast(dict[str, object], value).get("released") if isinstance(value, dict) else None
    if not isinstance(released, dict):
        raise ValueError(f"{manifest} holds no `released` object")
    return frozenset(cast(dict[str, object], released))


def draft_note(version: str) -> str:
    """The note on the page of a version that is not released, as HTML."""
    match = VERSION.fullmatch(version)
    if match is None:
        raise ValueError(f"{version} is not a schema version's directory")
    line = html.escape(match["line"])
    if match["development"]:
        return (
            f'<p class="draft"><strong>Draft until {line}.0.</strong> These files are the development of '
            f"schema {line} and may change until OpenMaterica {line}.0 is released. At that release schema "
            f"{line} is frozen as <code>{line}/</code>.</p>"
        )
    return (
        f'<p class="draft"><strong>Draft until {line}.0.</strong> These {line} schema files may change until '
        f"OpenMaterica {line}.0 is released. From that release they are frozen: CI fails any change to them, "
        "and a change is a new minor version in a new directory.</p>"
    )


def write_indexes(root: Path, released: Collection[str]) -> list[Path]:
    """Write every directory's `index.html` and return their paths, or raise before writing any.

    `released` names the versions whose pages carry no draft note.
    """
    directories = [root, *sorted(path for path in root.rglob("*") if path.is_dir())]
    existing = [directory / "index.html" for directory in directories if (directory / "index.html").exists()]
    if existing:
        raise ValueError(f"the tree already holds {', '.join(str(path) for path in existing)}")
    pages = {directory / "index.html": _page(root, directory, released) for directory in directories}
    for path, text in pages.items():
        path.write_text(text, encoding="utf-8")
    return list(pages)


def _page(root: Path, directory: Path, released: Collection[str]) -> str:
    parts = directory.relative_to(root).parts
    where = "/schema/" + "".join(f"{part}/" for part in parts)
    crumbs = ['<a href="' + "../" * (len(parts) + 1) + '">OpenMaterica</a>']
    crumbs += [
        f'<a href="{"../" * (len(parts) - depth)}">{html.escape(name)}</a>'
        for depth, name in enumerate(("schema", *parts))
    ]
    entries = [
        f'<li><a href="{html.escape(path.name)}/">{html.escape(path.name)}/</a></li>'
        for path in sorted(directory.iterdir())
        if path.is_dir()
    ]
    entries += [_file_entry(path) for path in sorted(directory.iterdir()) if path.is_file()]
    listing = "\n    ".join(entries)
    intro = (
        "<p>The JSON Schemas and vocabulary of each schema version. A file's permanent identifier is its "
        "<code>$id</code>, under <code>https://w3id.org/materica/schema/</code>. Until a version is released "
        "its files here may change, and its page says so.</p>"
        if not parts
        else draft_note(parts[0])
        if len(parts) == 1 and parts[0] not in released
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{POLICY}">
<meta name="color-scheme" content="light dark">
<title>{html.escape(where)} · OpenMaterica</title>
<link rel="icon" href="data:,">
<style>{STYLE}</style>
</head>
<body>
<header>
  <nav class="muted">{" / ".join(crumbs)}</nav>
  <h1>{html.escape(where)}</h1>
</header>
<main>
  {intro}
  <ul>
    {listing}
  </ul>
</main>
<footer>
  <p>Generated from <a href="{SOURCE}{"".join("/" + html.escape(part) for part in parts)}">the repository</a>,
    where each file's history is.</p>
</footer>
</body>
</html>
"""


def _file_entry(path: Path) -> str:
    link = f'<a href="{html.escape(path.name)}">{html.escape(path.name)}</a>'
    if path.suffix != ".json":
        return f"<li>{link}</li>"
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} holds no JSON object")
    schema = cast(dict[str, object], value)
    lines = [link]
    title, description, identifier = (schema.get(name) for name in ("title", "description", "$id"))
    if isinstance(title, str):
        lines.append(f"<strong>{html.escape(title)}</strong>")
    if isinstance(description, str):
        lines.append(html.escape(description))
    if isinstance(identifier, str):
        lines.append(f'<span class="muted">Identifier: <code>{html.escape(identifier)}</code></span>')
    return "<li>" + "<br>\n      ".join(lines) + "</li>"


def main(argv: Sequence[str]) -> int:
    if len(argv) != 1:
        print("usage: schema_index.py <directory>", file=sys.stderr)
        return 2
    try:
        written = write_indexes(Path(argv[0]), released_versions(MANIFEST))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"wrote {len(written)} index pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
