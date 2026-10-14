# SPDX-License-Identifier: Apache-2.0
"""Fail unless every commit in `base..head` carries a DCO sign-off by its author (CONTRIBUTING constraint 1).

    python scripts/check_signoff.py <base> <head>

Only trailers in a message's last paragraph count, as git reads them, and a sign-off counts when its email is
the author's. Merge commits are checked like any other.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence

# The last design commit before the first code commit: it and its ancestors are the design commits that
# CONTRIBUTING constraint 1 exempts. Ancestry cannot be claimed by a later commit, as a date or a path could;
# and a rebase that rewrites these commits gives them new hashes, so they lose the exemption: it fails closed.
DESIGN_HISTORY = "fb28765fb45e87ac870ff812dd0254c9a285f04a"

_SIGNER = re.compile(r".+ <(?P<email>[^<>]+)>")


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], capture_output=True, text=True, check=check)


def is_design_commit(commit: str, design_history: str) -> bool:
    return git("merge-base", "--is-ancestor", commit, design_history, check=False).returncode == 0


def unsigned_commits(base: str, head: str, design_history: str = DESIGN_HISTORY) -> list[str]:
    """One line per commit in `base..head` that lacks its author's sign-off."""
    problems: list[str] = []
    for commit in git("rev-list", f"{base}..{head}").stdout.split():
        if is_design_commit(commit, design_history):
            continue
        author, subject, signers = (
            git(
                "show",
                "-s",
                "--format=%ae%x00%s%x00%(trailers:key=Signed-off-by,valueonly,separator=%x01)",
                commit,
            )
            .stdout.rstrip("\n")
            .split("\x00")
        )
        emails = {
            match["email"].lower() for signer in signers.split("\x01") if (match := _SIGNER.fullmatch(signer))
        }
        if author.lower() not in emails:
            problems.append(f"{commit[:12]} {subject}: no Signed-off-by from its author <{author}>")
    return problems


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that every commit in base..head is signed off.")
    parser.add_argument("base")
    parser.add_argument("head")
    options = parser.parse_args(arguments)
    problems = unsigned_commits(options.base, options.head)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print("Sign off with `git commit -s` (CONTRIBUTING, constraint 1).", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
