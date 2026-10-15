# SPDX-License-Identifier: Apache-2.0
"""The oracle by which fuzz target 4 (`read_field_bytes.py`) sees a refusal step 8 is missing, apart from the
target, which needs Atheris, so that a unit test can show it fails (`tests/unit/test_fuzz_oracle.py`).

Until S2a-4's reference model can say what each read must give, the target holds step 8 to T1's third
relation (`tests/spec_sync/test_t1.py`): what the reader `$defs` refuse, step 8 refuses.
"""

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.spec_sync.schemas import validator

READER_CONSTANT = validator("record.reader.json#/$defs/constant_field")


def check_no_refusal_missing(field_name: str, field: JsonValue, result: JsonValue) -> None:
    """A field step 8 lets through (`result` is "not yet"), a constant its row allows that holds no
    alternatives, is one the reader `$defs` take."""
    if not (isinstance(field, dict) and result == "not yet" and field.get("form") == "constant"):
        return
    if "alternatives" not in field and "constant" in VOCABULARY.fields[field_name].forms:
        errors = READER_CONSTANT(field)
        assert not errors, f"step 8 passed a constant the reader $defs refuse: {errors[:1]}"
