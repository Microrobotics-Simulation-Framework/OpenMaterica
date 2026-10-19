# SPDX-License-Identifier: Apache-2.0
"""A throwaway git repository for the repository scripts' tests, cut off from any repository around the run.

Git exports `GIT_DIR` to the commands it runs, `git rebase --exec` among them. Under it, a test's
`git init` would re-initialise the outer repository, setting `core.bare` in its shared config, and the
test's commits would land on the outer HEAD. So every `GIT_` variable is removed first, and the only
configuration is the test's own.

It runs no automatic maintenance. After a commit git starts `git maintenance run --auto`, detached, and
from git 2.54 its default task repacks once about 256 objects are loose: a test of a few hundred commits
meets it. Its `prune-packed` removes each emptied directory of `.git/objects`, while the test's next command
may have just made one to write an object in; that write then fails with "unable to create temporary file:
No such file or directory".
"""

import os
import subprocess
from pathlib import Path

import pytest


def throwaway_repository(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.chdir(root)
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "config", "maintenance.auto", "false"], check=True)
    return root
