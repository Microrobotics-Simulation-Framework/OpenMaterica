# SPDX-License-Identifier: Apache-2.0
"""The oracle by which fuzz target 4 (`read_field_bytes.py`) sees a refusal step 8 is missing, apart from the
target, which needs Atheris, so that a unit test can show it fails (`tests/unit/test_fuzz_oracle.py`).

Until S2a-4's reference model can say what each read must give, the target holds step 8 to T1's third
relation (`tests/spec_sync/test_t1.py`): what the reader `$defs` refuse, step 8 refuses.
"""

from urllib.parse import urljoin

from materica.core.jsonio import JsonValue
from materica.core.vocabulary import VOCABULARY
from tests.property.value_field_strategies import AFTER_STEP_8
from tests.spec_sync.schemas import BASE, takes, why_refused

CONSTANT = "record.reader.json#/$defs/constant_field"
# jsonschema-rs alone, on every input the target reaches: T1 holds its verdicts on that definition to
# python-jsonschema's (`tests/property/test_validators_agree.py`).
READER_TAKES = takes(CONSTANT)
WHY = why_refused({"$ref": urljoin(BASE, CONSTANT)})


def passed_step_8(result: JsonValue) -> bool:
    """Whether a read's result, as the target takes it, is one of a field that passed step 8: "not yet", where
    a step not built yet decides it, or a refusal of a later step alone."""
    if result == "not yet":
        return True
    reasons = result.get("reasons") if isinstance(result, dict) else None
    codes = (
        [reason.get("code") for reason in reasons if isinstance(reason, dict)]
        if isinstance(reasons, list)
        else []
    )
    return bool(codes) and all(code in AFTER_STEP_8 for code in codes)


def check_no_refusal_missing(field_name: str, field: JsonValue, result: JsonValue) -> None:
    """A field step 8 lets through (`passed_step_8`), a constant its row allows that holds no alternatives,
    is one the reader `$defs` take."""
    if not (isinstance(field, dict) and passed_step_8(result) and field.get("form") == "constant"):
        return
    if "alternatives" not in field and "constant" in VOCABULARY.fields[field_name].forms:
        assert READER_TAKES(field), f"step 8 passed a constant the reader $defs refuse: {WHY(field)[:1]}"
