# `materica`

The Python package. It implements the reader side of the OpenMaterica specification (`docs/specification/`).
The specification is normative: where this code and it differ, the code is wrong.

## Layers

The package is built in layers (AD 7.1), and a module imports only from its own layer or a lower one.

| Layer | Directory | What it holds |
|---|---|---|
| L1, data | `data/conformance/` | the specification's conformance cases and the inputs they supply; their own `README.md` says how to read them |
| L2, core | `core/` | strict JSON, the canonical form and the content hash; Python's standard library only (`core/README.md`) |

The schemas (L0), the readers of files and USD stages (`io/`, L4), the sampling helpers (`sample/`, L5) and
the command line (`tools/`, L6) arrive in later steps. Until they do, the layer rule comes down to one check:
`core/` imports nothing but the standard library and itself (`tests/unit/test_source_files.py`).

## What holds across the package

- No run-time dependency (AD 7.2): the built wheel declares none (`scripts/check_wheel.py`).
- It is typed (PEP 561) and ships `py.typed`. `mypy --strict` and pyright in strict mode pass over it, and a
  consumer's code type-checks against the installed wheel (`tests/typing/`).
- The conformance data ships in the wheel byte for byte, since its inputs are byte-exact
  (`docs/specification/README.md`, "Case files"; `scripts/check_wheel.py`).
- `__init__.py` holds the public API built so far: `content_hash`.
