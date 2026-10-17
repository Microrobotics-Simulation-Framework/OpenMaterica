# SPDX-License-Identifier: Apache-2.0
"""The site check passes a staged copy whose pages keep their policy and whose local links, images and icons
resolve, and fails each way it is meant to, on copies written here, never on the repository's own site, which
CI's `site` job checks."""

import json
from pathlib import Path

import pytest

from scripts import check_site

POLICY = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; manifest-src 'self'"
META = f'<meta http-equiv="Content-Security-Policy" content="{POLICY}">'
CANONICAL = '<link rel="canonical" href="https://example.org/">'
ICON = '<link rel="icon" href="/icon.png">'
HEAD = f"""<meta charset="utf-8">
{META}
{CANONICAL}
{ICON}
<link rel="manifest" href="/app.webmanifest">
<style>body {{ background: url("data:image/png;base64,AAAA"); }}</style>"""
BODY = """<h1 id="top"><img src="/logo.png" srcset="/logo.png 1x, logo@2x.png 2x" alt=""></h1>
<p><a href="#top">Top</a>, <a href="notes/">notes</a>, <a href="notes/#part">a part</a>,
<a href="https://example.org/elsewhere">elsewhere</a>, <a href="mailto:someone@example.org">mail</a>.</p>"""


def page(head: str = HEAD, body: str = BODY) -> str:
    return f"<!doctype html>\n<html>\n<head>\n{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n"


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A staged copy that passes: a home page, a directory's page, the images, an icon and a manifest."""
    root = tmp_path / "site"
    (root / "notes").mkdir(parents=True)
    (root / "home.html").write_text(page(), encoding="utf-8")
    (root / "notes" / "index.html").write_text(page(body='<p id="part">A part.</p>'), encoding="utf-8")
    for name in ("logo.png", "logo@2x.png", "icon.png", "large.png"):
        (root / name).write_bytes(b"\x89PNG")
    manifest = {"name": "Example", "icons": [{"src": "/large.png", "sizes": "512x512"}]}
    (root / "app.webmanifest").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def problems(site: Path) -> list[str]:
    """The check's problems with the copy, as its command finds them, but the README's."""
    files, found = check_site.copy_files(site)
    pages = [path for path in files if path.suffix.lower() in check_site.PAGE_SUFFIXES]
    return found + [line for path in pages for line in check_site.page_problems(site, path)]


def test_a_copy_whose_pages_keep_their_policy_and_resolve_passes(site: Path) -> None:
    assert problems(site) == []


def rewrite(site: Path, old: str, new: str, name: str = "home.html") -> None:
    text = (site / name).read_text(encoding="utf-8")
    assert old in text
    (site / name).write_text(text.replace(old, new), encoding="utf-8")


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        # Local links, images and icons that resolve to nothing.
        ('src="/logo.png"', 'src="/missing.png"', "home.html: <img src> '/missing.png' names no file"),
        ("logo@2x.png 2x", "logo@3x.png 3x", "home.html: <img srcset> 'logo@3x.png' names no file"),
        ('href="/icon.png"', 'href="/favicon.ico"', "home.html: <link href> '/favicon.ico' names no file"),
        ('href="notes/"', 'href="drafts/"', "home.html: <a href> 'drafts/' names no file"),
        (
            'href="#top"',
            'href="#bottom"',
            "home.html: <a href> '#bottom' names no anchor 'bottom' in home.html",
        ),
        ('href="notes/#part"', 'href="notes/#whole"', "names no anchor 'whole' in notes/index.html"),
        ('href="notes/"', 'href="../outside.html"', "home.html: <a href> '../outside.html' names no file"),
        # The policy.
        (META, "", "0 content security policies"),
        (CANONICAL, f"{META}\n{CANONICAL}", "2 content security policies"),
        ("default-src 'none'", "default-src 'self'", "its policy's default-src is [\"'self'\"], not 'none'"),
        (
            "img-src 'self' data:",
            "img-src 'self' https://cdn.example.org",
            "img-src allows https://cdn.example.org",
        ),
        ("img-src 'self' data:", "img-src *", "its policy's img-src allows *, a source elsewhere"),
        ("img-src 'self' data:", "img-src https:", "its policy's img-src allows https:, a source elsewhere"),
        (
            f"{META}\n{CANONICAL}\n{ICON}",
            f"{ICON}\n{META}",
            "its content security policy comes after an element that loads something",
        ),
        (
            f'{META}\n{CANONICAL}\n{ICON}\n<link rel="manifest" href="/app.webmanifest">',
            "<style>p { color: red; }</style>\n" + f"{META}\n{CANONICAL}",
            "its content security policy comes after an element that loads something, or a style",
        ),
        # A directive given twice: a browser keeps the first, which here allows everything.
        ("default-src 'none'", "default-src *; default-src 'none'", "its policy gives default-src twice"),
        (
            "img-src 'self' data:",
            "img-src https://cdn.example.org; img-src 'self' data:",
            "its policy gives img-src twice",
        ),
        # A keyword off the closed list: under 'strict-dynamic' a script a hash trusts loads from anywhere.
        (
            "img-src 'self' data:",
            "img-src 'self' data:; script-src 'strict-dynamic' 'sha256-AAAA'",
            "its policy's script-src allows 'strict-dynamic', a keyword not on the check's list",
        ),
        # A directive that names sources without `-src`.
        (
            "img-src 'self' data:",
            "img-src 'self' data:; form-action https://x.example",
            "its policy's form-action allows https://x.example, a source elsewhere",
        ),
        # The policy in the body: a browser ignores it there.
        (f"{META}\n", "", "0 content security policies in its head"),
        # Loads from elsewhere.
        (
            'src="/logo.png"',
            'src="https://example.org/logo.png"',
            "<img src> loads 'https://example.org/logo.png'",
        ),
        ('href="/icon.png"', 'href="//example.org/icon.png"', "<link href> loads '//example.org/icon.png'"),
        ("<h1", '<script src="https://example.org/a.js"></script>\n<h1', "<script src> loads"),
        ('url("data:image/png;base64,AAAA")', 'url("https://example.org/b.png")', "a style loads"),
        (
            "body {{",
            '@import "https://example.org/c.css";\nbody {{',
            "a style loads 'https://example.org/c.css'",
        ),
    ],
    ids=[
        "an-image",
        "an-image-of-a-srcset",
        "an-icon",
        "a-directory",
        "a-fragment",
        "a-fragment-in-another-page",
        "outside-the-site",
        "no-policy",
        "two-policies",
        "a-default-not-none",
        "a-host",
        "any-source",
        "a-scheme",
        "a-policy-too-late",
        "a-style-before-the-policy",
        "a-default-given-twice",
        "a-source-directive-given-twice",
        "strict-dynamic",
        "form-action-elsewhere",
        "the-policy-out-of-the-head",
        "an-image-from-elsewhere",
        "an-icon-from-a-host",
        "a-script-from-elsewhere",
        "a-style-url-from-elsewhere",
        "an-import-from-elsewhere",
    ],
)
def test_the_site_check_can_fail(site: Path, old: str, new: str, problem: str) -> None:
    rewrite(site, old.replace("{{", "{"), new.replace("{{", "{"))
    if problem == "0 content security policies in its head":
        rewrite(site, "<h1", f"{META}\n<h1")
    found = problems(site)
    assert any(problem in line for line in found), found


def test_a_link_to_a_file_outside_the_copy_does_not_resolve(site: Path) -> None:
    """The file exists, beside the copy, but Pages serves the copy alone."""
    (site.parent / "outside.html").write_text(page(), encoding="utf-8")
    rewrite(site, 'href="notes/"', 'href="../outside.html"')
    assert problems(site) == ["home.html: <a href> '../outside.html' names no file of the site"]


BODY_TEXT = "<p>A page.</p>"


@pytest.mark.parametrize(
    "text",
    [
        f"<html><head><title>p</title><body>{META}{BODY_TEXT}</body></html>",
        f"<html><head><title>p</title><p>x</p>{META}</head><body>{BODY_TEXT}</body></html>",
        f"<html><head>Some text{META}</head><body>{BODY_TEXT}</body></html>",
        f"<html><head><noscript>{META}</noscript></head><body>{BODY_TEXT}</body></html>",
        f"<html><head><title>{META}</title></head><body>{BODY_TEXT}</body></html>",
        f"<html><head></head><head>{META}</head><body>{BODY_TEXT}</body></html>",
    ],
    ids=[
        "the-body-opened-before-it",
        "after-an-element-a-head-cannot-hold",
        "after-text",
        "inside-noscript",
        "inside-the-title",
        "in-a-second-head",
    ],
)
def test_a_policy_a_browser_does_not_read_as_in_the_head_is_not_counted(site: Path, text: str) -> None:
    """A browser ends the head at the first element or text it cannot hold, `</head>` or not, and reads a
    policy only as an element of the head itself."""
    (site / "home.html").write_text(text, encoding="utf-8")
    assert "home.html: 0 content security policies in its head, not one" in problems(site)


@pytest.mark.parametrize(
    "text",
    [
        f"<!doctype html>{META}<title>p</title><p>{BODY_TEXT}</p>",
        f"<html>\n<head>\n<!-- a comment -->\n{META}\n<title>p</title>\n</head>\n<body>{BODY_TEXT}</body>",
        f"<html><head><title>p</title><noscript><p>x</p></noscript>{META}</head><body>{BODY_TEXT}</body></html>",
    ],
    ids=["a-head-without-its-tags", "whitespace-and-a-comment", "after-a-noscript"],
)
def test_a_policy_a_browser_reads_as_in_the_head_is_counted(site: Path, text: str) -> None:
    """The controls: a head a browser implies without `<head>`, whitespace and comments in the head, and an
    element inside a `<noscript>`, none of which ends it."""
    (site / "home.html").write_text(text, encoding="utf-8")
    assert [line for line in problems(site) if line.startswith("home.html")] == []


@pytest.mark.parametrize(
    "sources",
    [
        "'self'",
        "'NONE'",
        "'unsafe-inline'",
        "'sha256-AAAA+/='",
        "'sha512-x_y-z'",
        "'nonce-abc123=='",
        "data:",
    ],
)
def test_the_sources_on_the_closed_list_pass(site: Path, sources: str) -> None:
    rewrite(site, "img-src 'self' data:", f"img-src 'self' data:; script-src {sources}")
    assert problems(site) == []


STYLESHEET = '<link rel="stylesheet" href="/style.css">'


@pytest.mark.parametrize(
    ("css", "problem"),
    [
        (
            '@import url("https://elsewhere.example/x.css");',
            "home.html: its stylesheet style.css loads 'https://elsewhere.example/x.css' from elsewhere",
        ),
        (
            "body { background: url(missing.png); }",
            "its stylesheet style.css's address 'missing.png' names no file",
        ),
        (
            '@import "more.css";',
            "its stylesheet more.css loads 'https://elsewhere.example/y.png' from elsewhere",
        ),
    ],
    ids=["an-import-from-elsewhere", "a-local-image-missing", "a-local-import-loading-from-elsewhere"],
)
def test_a_stylesheet_of_the_copy_is_read_for_its_addresses(site: Path, css: str, problem: str) -> None:
    (site / "style.css").write_text(css, encoding="utf-8")
    (site / "more.css").write_text(
        "p { background: url(https://elsewhere.example/y.png); }", encoding="utf-8"
    )
    rewrite(site, ICON, f"{ICON}\n{STYLESHEET}")
    found = problems(site)
    assert any(problem in line for line in found), found


def test_a_stylesheet_whose_addresses_resolve_passes(site: Path) -> None:
    """The control: a local image beside the stylesheet, `data:` and a local import, which imports it back."""
    (site / "css").mkdir()
    (site / "css" / "style.css").write_text(
        '@import "more.css";\nh1 { background: url("../logo.png"); }\n'
        "p { background: url(data:image/png;base64,AA); }",
        encoding="utf-8",
    )
    (site / "css" / "more.css").write_text("@import url(style.css);", encoding="utf-8")
    rewrite(site, ICON, f'{ICON}\n<link rel="stylesheet" href="css/style.css">')
    assert problems(site) == []


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (
            "<h1",
            '<svg><image href="https://elsewhere.example/x.png"/></svg>\n<h1',
            "home.html: <image href> loads 'https://elsewhere.example/x.png' from elsewhere",
        ),
        (
            "<h1",
            '<svg><use xlink:href="https://elsewhere.example/s.svg#a"/></svg>\n<h1',
            "home.html: <use xlink:href> loads",
        ),
        ("<h1", '<svg><use href="/sprite.svg#a"/></svg>\n<h1', "<use href> '/sprite.svg#a' names no file"),
        ("<h1", '<svg><use href="#nowhere"/></svg>\n<h1', "names no anchor 'nowhere' in home.html"),
        (
            '<h1 id="top">',
            '<h1 id="top" background="https://elsewhere.example/x.png">',
            "home.html: <h1 background> loads 'https://elsewhere.example/x.png' from elsewhere",
        ),
        (
            ICON,
            f'{ICON}\n<link rel="preload" as="image" imagesrcset="https://elsewhere.example/a.png 1x">',
            "home.html: <link imagesrcset> loads 'https://elsewhere.example/a.png' from elsewhere",
        ),
        (ICON, f'{ICON}\n<base href="/">', "home.html: a <base>, which changes where each address resolves"),
    ],
    ids=[
        "an-svg-image",
        "an-svg-use-xlink",
        "an-svg-use-missing",
        "an-svg-use-of-no-anchor",
        "a-background",
        "an-imagesrcset",
        "a-base",
    ],
)
def test_the_site_check_reads_svg_backgrounds_and_base(site: Path, old: str, new: str, problem: str) -> None:
    rewrite(site, old, new)
    found = problems(site)
    assert any(problem in line for line in found), found


def test_an_svg_that_uses_its_own_symbol_passes(site: Path) -> None:
    """The control of the SVG cases."""
    rewrite(site, "<h1", '<svg><symbol id="a"></symbol><use href="#a"/></svg>\n<h1')
    assert problems(site) == []


@pytest.mark.parametrize("name", ["page.htm", "page.xhtml", "PAGE.HTML"])
def test_every_page_pages_serves_is_checked(site: Path, name: str) -> None:
    (site / name).write_text('<p><img src="https://elsewhere.example/x.png"></p>', encoding="utf-8")
    assert problems(site) == [
        f"{name}: 0 content security policies in its head, not one",
        f"{name}: <img src> loads 'https://elsewhere.example/x.png' from elsewhere",
    ]


def test_a_symbolic_link_or_a_hidden_path_in_the_copy_is_refused(site: Path, tmp_path: Path) -> None:
    """The Pages artifact is a `tar --dereference --exclude=.[^/]*` of the copy: a link publishes its target's
    content, and a hidden path is not served."""
    (tmp_path / "outside.txt").write_text("outside the site", encoding="utf-8")
    (site / "linked.txt").symlink_to(tmp_path / "outside.txt")
    (site / "linked").symlink_to(tmp_path)
    (site / ".well-known").mkdir()
    (site / ".well-known" / "security.txt").write_text("Contact: x", encoding="utf-8")
    (site / "notes" / ".draft.html").write_text(page(), encoding="utf-8")
    assert problems(site) == [
        ".well-known: a hidden path, which the Pages artifact leaves out",
        "linked: a symbolic link, whose target the Pages artifact would publish",
        "linked.txt: a symbolic link, whose target the Pages artifact would publish",
        "notes/.draft.html: a hidden path, which the Pages artifact leaves out",
    ]


def test_the_manifests_icons_resolve_and_come_from_the_site(site: Path) -> None:
    """Both pages link the manifest, so each reports it."""
    manifest = site / "app.webmanifest"
    manifest.write_text(json.dumps({"icons": [{"src": "/huge.png"}]}), encoding="utf-8")
    assert problems(site) == [
        f"{name}: its manifest's icon '/huge.png' names no file of the site"
        for name in ("home.html", "notes/index.html")
    ]
    manifest.write_text(json.dumps({"icons": [{"src": "https://example.org/huge.png"}]}), encoding="utf-8")
    assert (
        "home.html: its manifest's icon 'https://example.org/huge.png' is loaded from elsewhere"
        in problems(site)
    )
    manifest.write_text("[]", encoding="utf-8")
    assert problems(site)[0].startswith("home.html: its manifest is not a JSON object")


RAW = "https://raw.githubusercontent.com/Microrobotics-Simulation-Framework/OpenMaterica/"
README = f"""<h1 align="center"><img src="{RAW}main/art/logo.png" alt="Logo" width="70%"></h1>

An image ![diagram](art/diagram.png), and a badge from elsewhere ![badge](https://img.example.org/b.svg).
"""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "art" / "diagram.png").write_bytes(b"\x89PNG")
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    return tmp_path


def test_the_readmes_images_name_files_of_the_tree(tree: Path) -> None:
    assert check_site.readme_problems(tree / "README.md") == []
    (tree / "art" / "logo.png").unlink()
    (tree / "art" / "diagram.png").unlink()
    assert check_site.readme_problems(tree / "README.md") == [
        "README.md: its image 'https://raw.githubusercontent.com/Microrobotics-Simulation-Framework/OpenMaterica/"
        "main/art/logo.png' names art/logo.png, which the tree does not hold",
        "README.md: its image 'art/diagram.png' names art/diagram.png, which the tree does not hold",
    ]


@pytest.mark.parametrize(
    ("url", "path"),
    [
        (
            "https://raw.githubusercontent.com/Microrobotics-Simulation-Framework/OpenMaterica/main/a/b.png",
            "a/b.png",
        ),
        (
            "https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/raw/main/a/b%20c.png",
            "a/b c.png",
        ),
        (
            "https://github.com/Microrobotics-Simulation-Framework/OpenMaterica/blob/v1/a.png?raw=true",
            "a.png",
        ),
        ("a/b.png#x", "a/b.png"),
        ("https://raw.githubusercontent.com/another/repository/main/a.png", None),
    ],
)
def test_an_image_names_a_file_of_this_repository_by_url_or_by_path(url: str, path: str | None) -> None:
    assert check_site.repository_path(url) == path


def test_the_command_checks_every_page_and_the_readme(
    site: Path, tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_site.main([str(site), "--readme", str(tree / "README.md")]) == 0
    assert capsys.readouterr().out == "2 pages checked; 0 problems\n"
    (site / "logo.png").unlink()
    assert check_site.main([str(site)]) == 1
    captured = capsys.readouterr()
    assert "home.html: <img src> '/logo.png' names no file of the site" in captured.err
    assert captured.out == "2 pages checked; 2 problems\n"
    empty = tree / "empty"
    empty.mkdir()
    assert check_site.main([str(empty)]) == 1
