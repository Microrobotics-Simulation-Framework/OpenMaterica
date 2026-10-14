# SPDX-License-Identifier: Apache-2.0
"""Write an `index.html` into a published schema tree and every directory under it.

    python3 scripts/schema_index.py <site>/schema

The Pages workflow runs it on its staged copy of `src/materica/schema/`, since GitHub Pages lists no
directory by itself. Each page links what its directory holds, and gives each JSON file's `$id`, its permanent
identifier, with the schema's `title` and `description` where it has them. It uses the standard library only,
so the workflow needs no environment, and it refuses a tree that already holds an `index.html`, rather than
overwrite a file that would otherwise be published.
"""

import html
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

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
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
         font-size: 0.85em; background: var(--surface); padding: 0.05em 0.2em; border-radius: 0.2em;
         overflow-wrap: anywhere; }
  a { color: var(--link); text-underline-offset: 0.15em; }
  a:visited { color: var(--visited); }
  a:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; border-radius: 0.125rem; }
  footer { margin-top: 2.5rem; padding: 1rem 0 3rem; border-top: 1px solid var(--rule); color: var(--muted);
           font-size: 0.9375rem; }
"""


def write_indexes(root: Path) -> list[Path]:
    """Write every directory's `index.html` and return their paths, or raise before writing any."""
    directories = [root, *sorted(path for path in root.rglob("*") if path.is_dir())]
    existing = [directory / "index.html" for directory in directories if (directory / "index.html").exists()]
    if existing:
        raise ValueError(f"the tree already holds {', '.join(str(path) for path in existing)}")
    pages = {directory / "index.html": _page(root, directory) for directory in directories}
    for path, text in pages.items():
        path.write_text(text, encoding="utf-8")
    return list(pages)


def _page(root: Path, directory: Path) -> str:
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
        "<code>$id</code>, under <code>https://w3id.org/materica/schema/</code>. OpenMaterica is "
        "pre-release, and until a version is released its files here may change.</p>"
        if not parts
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
        written = write_indexes(Path(argv[0]))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"wrote {len(written)} index pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
