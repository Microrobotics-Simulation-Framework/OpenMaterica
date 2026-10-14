# SPDX-License-Identifier: Apache-2.0
"""Plain records from files: each file's bytes into a `RecordStore`, under its path."""

import os
from collections.abc import Iterable
from pathlib import Path

from materica.core.record import RecordStore


def load_records(paths: Iterable[str | os.PathLike[str]]) -> RecordStore:
    """A store of the files at `paths`. Nothing is checked here: a file that is not a record is kept as an
    unreadable source, and a read resolves among them all (`read_side_contract.md` section 3, step 1)."""
    store = RecordStore()
    for path in paths:
        store.add(os.fspath(path), Path(path).read_bytes())
    return store
