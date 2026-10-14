#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# The program libFuzzer re-executes to merge a corpus or minimise a crash. It re-executes argv[0], which under
# `python -m` is the module's file, not a program; `jsonio_bytes.py` passes this instead.
cd "$(dirname "$0")/../.." && exec "$MATERICA_FUZZ_PYTHON" -m tests.fuzz.jsonio_bytes "$@"
