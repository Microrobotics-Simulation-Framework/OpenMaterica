# SPDX-License-Identifier: Apache-2.0
"""Check the site as GitHub Pages will serve it, on the copy the Pages workflow's staging step writes.

    python3 scripts/check_site.py <staged site> [--readme README.md]

CI's `site` job stages the site exactly as `.github/workflows/pages.yml` does, then runs this on the copy.
That every file the workflow copies exists is the staging step's own check: it runs under `bash -eo pipefail`,
so a `cp` of a missing file fails it. This fails where, in any page of the copy:

- a local link, image or icon, or an icon its web manifest names, resolves to no file of the copy (a
  directory to its `index.html`), or a fragment to no `id` or `name` in the page it names;
- there is not exactly one content security policy in its head, as a browser reads the head (it ends at
  the first element or text a head cannot hold, `</head>` left out or not), or it comes after an element that
  loads something or a style; a directive is given twice (a browser keeps the first); its default is not
  `'none'`; or a directive that names sources allows anything but `'none'`, `'self'`, `'unsafe-inline'`, a
  hash, a nonce and `data:` (a host, another scheme, `*`, or a keyword such as `'strict-dynamic'`, which lets
  a trusted script load scripts from any host);
- an element loads something from elsewhere (an image, an icon, a script, a style, a frame or the manifest),
  or a style's `url(...)` or `@import` names an address elsewhere; links to other sites (`<a href>`) are
  navigation, not loads, and are not checked;

and where an image of the README, by a path or by a URL into this repository, names a file the tree does not
hold. Standard library only, so the job needs no environment.
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

# The attributes by which each element loads what it names.
LOADING = {
    "img": ("src", "srcset"),
    "script": ("src",),
    "iframe": ("src",),
    "frame": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "source": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
    "input": ("src",),
    "link": ("href",),
}
# A `<link>` loads what it names, but where it only describes the page.
DESCRIBING_LINKS = {"canonical", "alternate"}
# The attributes by which an element links to what it names, without loading it.
LINKING = {"a": ("href",), "area": ("href",)}
# The directives of a policy that name where things may come from.
SOURCE_DIRECTIVE = re.compile(r".+-src(-elem|-attr)?|base-uri|form-action|frame-ancestors")
# The sources such a directive may hold, a closed list: none lets anything load from elsewhere.
ALLOWED_SOURCE = re.compile(
    r"'none'|'self'|'unsafe-inline'|'(?:sha256|sha384|sha512)-[A-Za-z0-9+/_-]+=*'|'nonce-[A-Za-z0-9+/_-]+=*'|data:",
    re.I,
)
# The elements a head holds ("the in head insertion mode", HTML): any other element, or text, ends the head,
# `</head>` or not; and the elements that hold nothing.
HEAD_ELEMENTS = frozenset(
    "base basefont bgsound link meta noframes noscript script style template title".split()
)
VOID_ELEMENTS = frozenset(
    {
        *"area base basefont bgsound br col embed frame hr img input keygen".split(),
        *"link meta param source track wbr".split(),
    }
)
CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)|@import\s+(['"])(.*?)\3""", re.I | re.S)
# Where an image of the README may name a file of this repository by URL.
REPOSITORY_URLS = (
    "https://raw.githubusercontent.com/Microrobotics-Simulation-Framework/OpenMaterica/",
    "https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/raw/",
    "https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/blob/",
)
README_IMAGE = re.compile(r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']|!\[[^\]]*\]\(\s*<?([^)\s>]+)""", re.I)


class Page(HTMLParser):
    """What the checks read of a page: its elements in order, whether each is in its head itself (not inside
    another of its elements, such as a `<noscript>`), its ids and names, and the text of its styles. The head
    is read as a browser reads it: one begins at the first element a head holds, `<head>` or not, and ends at
    `</head>` or at the first element or text it cannot hold."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str], bool]] = []
        self.anchors: set[str] = set()
        self.styles: list[str] = []
        self.head = "before"
        self.open_in_head: list[str] = []
        self.in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if self.head == "before" and tag not in ("html", "head"):
            self.head = "in" if tag in HEAD_ELEMENTS else "after"
        elif self.head == "before" and tag == "head":
            self.head = "in"
        elif self.head == "in" and not self.open_in_head and tag not in HEAD_ELEMENTS and tag != "head":
            self.head = "after"
        in_head = self.head == "in" and not self.open_in_head and tag != "head"
        self.elements.append((tag, attributes, in_head))
        if self.head == "in" and tag != "head" and tag not in VOID_ELEMENTS:
            self.open_in_head.append(tag)
        self.anchors |= {attributes[name] for name in ("id", "name") if attributes.get(name)}
        if "style" in attributes:
            self.styles.append(attributes["style"])
        self.in_style = tag == "style"

    def handle_endtag(self, tag: str) -> None:
        if tag in self.open_in_head:
            del self.open_in_head[self.open_in_head.index(tag) :]
        elif tag == "head" and self.head == "in":
            self.head = "after"
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.styles.append(data)
        if data.strip() and not self.open_in_head and self.head in ("before", "in"):
            self.head = "after"


def parsed(page: Path) -> Page:
    reader = Page()
    reader.feed(page.read_text(encoding="utf-8"))
    reader.close()
    return reader


def is_elsewhere(url: str) -> bool:
    """Whether `url` names something on another site: any scheme but `data:`, or a host."""
    parts = urlsplit(url.strip())
    return bool(parts.netloc) or (bool(parts.scheme) and parts.scheme.lower() != "data")


def is_local(url: str) -> bool:
    parts = urlsplit(url.strip())
    return not parts.scheme and not parts.netloc


def candidates(attribute: str, value: str) -> list[str]:
    """The addresses an attribute names: each of a `srcset`'s, or the value."""
    if attribute == "srcset":
        return [entry.split()[0] for entry in value.split(",") if entry.strip()]
    return [value]


def loads(page: Page) -> list[tuple[int, str, str, str]]:
    """Each address an element of the page loads, with the element's place, its tag and the attribute."""
    found: list[tuple[int, str, str, str]] = []
    for index, (tag, attributes, _) in enumerate(page.elements):
        if tag == "link" and set(attributes.get("rel", "").lower().split()) <= DESCRIBING_LINKS:
            continue
        for attribute in LOADING.get(tag, ()):
            if attribute in attributes:
                found += [
                    (index, tag, attribute, url) for url in candidates(attribute, attributes[attribute])
                ]
    return found


def resolved(site: Path, base: Path, url: str) -> tuple[Path | None, str]:
    """The file of the copy a local address names from the file `base`, and its fragment; None where it names
    none, or a place outside the copy."""
    parts = urlsplit(url.strip())
    path = unquote(parts.path)
    if not path:
        return base, parts.fragment
    target = Path(
        os.path.normpath((site / path.lstrip("/")) if path.startswith("/") else (base.parent / path))
    )
    if not target.is_relative_to(site):
        return None, parts.fragment
    if target.is_dir():
        target = target / "index.html"
    return (target if target.is_file() else None), parts.fragment


def policy_problems(where: str, policy: str) -> list[str]:
    directives: dict[str, list[str]] = {}
    problems: list[str] = []
    for part in policy.split(";"):
        words = part.split()
        if words and words[0].lower() in directives:
            problems.append(
                f"{where}: its policy gives {words[0].lower()} twice, and a browser keeps the first"
            )
        elif words:
            directives[words[0].lower()] = words[1:]
    if [source.lower() for source in directives.get("default-src", [])] != ["'none'"]:
        problems.append(f"{where}: its policy's default-src is {directives.get('default-src')}, not 'none'")
    for name, sources in directives.items():
        if SOURCE_DIRECTIVE.fullmatch(name):
            problems += [
                f"{where}: its policy's {name} allows {source}, "
                + ("a keyword not on the check's list" if source.startswith("'") else "a source elsewhere")
                for source in sources
                if not ALLOWED_SOURCE.fullmatch(source)
            ]
    return problems


def reference_problems(site: Path, base: Path, where: str, what: str, url: str) -> list[str]:
    """Where a local address does not resolve, or its fragment names no anchor of the page it names."""
    target, fragment = resolved(site, base, url)
    if target is None:
        return [f"{where}: {what} {url!r} names no file of the site"]
    if fragment and target.suffix == ".html" and fragment not in parsed(target).anchors:
        return [
            f"{where}: {what} {url!r} names no anchor {fragment!r} in {target.relative_to(site).as_posix()}"
        ]
    return []


def manifest_problems(site: Path, manifest: Path, where: str) -> list[str]:
    try:
        written: object = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as error:
        return [f"{where}: its manifest is not JSON ({error})"]
    if not isinstance(written, dict):
        return [f"{where}: its manifest is not a JSON object"]
    icons = cast(dict[str, object], written).get("icons", [])
    problems: list[str] = []
    for icon in cast(list[object], icons) if isinstance(icons, list) else []:
        entry = cast(dict[str, object], icon) if isinstance(icon, dict) else {}
        source = str(entry.get("src", ""))
        if is_elsewhere(source):
            problems.append(f"{where}: its manifest's icon {source!r} is loaded from elsewhere")
        elif is_local(source):
            problems += reference_problems(site, manifest, where, "its manifest's icon", source)
    return problems


def page_problems(site: Path, page: Path) -> list[str]:
    where = page.relative_to(site).as_posix()
    reader = parsed(page)
    problems: list[str] = []
    policies = [
        (index, attributes.get("content", ""))
        for index, (tag, attributes, in_head) in enumerate(reader.elements)
        if tag == "meta" and attributes.get("http-equiv", "").lower() == "content-security-policy" and in_head
    ]
    loaded = loads(reader)
    if len(policies) != 1:
        problems.append(f"{where}: {len(policies)} content security policies in its head, not one")
    else:
        place, policy = policies[0]
        if any(index < place for index, *_ in loaded) or any(
            tag == "style" for tag, _, _ in reader.elements[:place]
        ):
            problems.append(
                f"{where}: its content security policy comes after an element that loads something, "
                "or a style"
            )
        problems += policy_problems(where, policy)
    for index, tag, attribute, url in loaded:
        what = f"<{tag} {attribute}>"
        if is_elsewhere(url):
            problems.append(f"{where}: {what} loads {url!r} from elsewhere")
        elif is_local(url):
            problems += reference_problems(site, page, where, what, url)
            manifest, _ = resolved(site, page, url)
            if (
                manifest is not None
                and "manifest" in reader.elements[index][1].get("rel", "").lower().split()
            ):
                problems += manifest_problems(site, manifest, where)
    for style in reader.styles:
        for match in CSS_URL.finditer(style):
            address = match[2] if match[2] is not None else match[4]
            if is_elsewhere(address):
                problems.append(f"{where}: a style loads {address!r} from elsewhere")
            elif is_local(address) and address.strip():
                problems += reference_problems(site, page, where, "a style's address", address)
    for tag, attributes, _ in reader.elements:
        for attribute in LINKING.get(tag, ()):
            if attribute in attributes and is_local(attributes[attribute]):
                problems += reference_problems(
                    site, page, where, f"<{tag} {attribute}>", attributes[attribute]
                )
    return problems


def repository_path(url: str) -> str | None:
    """The path of the file an image of the README names in this repository, by a URL (`<prefix><ref>/<path>`)
    or a path, or None for another site."""
    for prefix in REPOSITORY_URLS:
        if url.startswith(prefix):
            return unquote(urlsplit(url[len(prefix) :]).path.partition("/")[2])
    return unquote(urlsplit(url).path) if is_local(url) else None


def readme_problems(readme: Path) -> list[str]:
    problems: list[str] = []
    for match in README_IMAGE.finditer(readme.read_text(encoding="utf-8")):
        url = match[1] or match[2]
        path = repository_path(url)
        if path is not None and not (readme.parent / path).is_file():
            problems.append(f"{readme.name}: its image {url!r} names {path}, which the tree does not hold")
    return problems


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").partition("\n")[0])
    parser.add_argument(
        "site", type=Path, help="the copy of the site the Pages workflow's staging step wrote"
    )
    parser.add_argument("--readme", type=Path, help="the README, whose images must name files of the tree")
    options = parser.parse_args(arguments)
    site = options.site.resolve()
    pages = sorted(site.rglob("*.html"))
    problems = [] if pages else [f"{site}: no page"]
    for page in pages:
        problems += page_problems(site, page)
    if options.readme is not None:
        problems += readme_problems(options.readme)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{len(pages)} pages checked; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
