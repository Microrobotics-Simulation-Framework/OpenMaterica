# `materica.io`

The readers of files (layer L4, AD 7.1): they turn files into the core's types, and leave every check to the
core. They may import the core; the core never imports them.

| Module | Reads |
|---|---|
| `plain.py` | plain records: each file's bytes into a `RecordStore`, under its path (`load_records`). Nothing is checked on loading: a file that is not a record is kept as an unreadable source, which a read takes into account (`read_side_contract.md` section 3, step 1) |

A path that cannot be read is a misuse of the API, and raises `OSError`.
