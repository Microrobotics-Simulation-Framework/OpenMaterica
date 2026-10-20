# SPDX-License-Identifier: Apache-2.0
"""Step 8's checks of what every form of a value field shares (`read_side_contract.md` section 3, step 8).

- **The record's structure.** A member one slip from a member named at its place (`record_format.md` section
  10 item 5): in the envelope, the licence, a material's body or its section names, it refuses every field
  read from the record; in a section's members or its field names, every field read from that section.
- **A section's `specimen`**, whose fault refuses every field read from that section.
- **A field's shared members:** `unit`, as a string or a status object (step 9 compares it); `conditions`,
  each of a name the reader knows; `specimen`; the statistics block and its uncertainties; in `provenance`,
  `origin`, `source` and a derived value's `derivation`; and `label`. A status object stands only in a member
  whose row allows one, with a token the row allows (`provenance.md` section 1 item 5).

Hand-written, as `envelope.py` is. Each shape is the writer schema's, opened as a reader is: a member the
reader does not know is ignored unless it is one slip from a member named at its place, and nothing a read
neither uses nor returns is checked. T1 (`tests/spec_sync/test_t1.py`) holds them to the writer schema and to
the reader schema's `$defs`. Each check makes all its checks and appends a reason for each fault:
`form_invalid`, or `unknown_token` for a token the reader knows for no member of that name.
"""

from collections.abc import Callable, Collection, Mapping
from typing import get_args, get_type_hints, is_typeddict

from materica import shapes
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.slips import slipped
from materica.core.vocabulary import STATUS_TOKENS, VOCABULARY, ConditionSpec, RecordFieldSpec

JsonObject = dict[str, JsonValue]
Found = list[Reason]


def an_object(value: JsonValue) -> JsonObject:
    """`value`, which a step before found to be an object: anything else is a defect of the core, never of a
    record or a request, and raises."""
    if not isinstance(value, dict):
        raise TypeError(f"the steps before let through no {type(value).__name__} here")
    return value


def a_list(value: JsonValue) -> list[JsonValue]:
    """`value`, which a step before found to be a list, as `an_object` does an object."""
    if not isinstance(value, list):
        raise TypeError(f"the steps before let through no {type(value).__name__} here")
    return value


Check = Callable[[JsonValue, str, Found], None]
"""A member's check, given its value, where it sits (in words, for a reason's detail) and the reasons found
so far, to which it appends its own."""
Members = Mapping[str, Check]

# The members named at each place of a material record's structure (`record_format.md` sections 2 and 4).
ENVELOPE_MEMBERS = (
    "schema_version",
    "record_type",
    "id",
    "version",
    "name",
    "licence",
    "content_hash",
    "card",
    "body",
)
LICENCE_MEMBERS = ("values", "evidence")
MATERIAL_BODY_MEMBERS = ("sections", "extensions")
SECTION_MEMBERS = ("fields", "specimen")

# A value field's members (`record_format.md` section 5), and each form's own member: `value` for a constant,
# otherwise the member named like the form. `alternatives` is named at a field's place too, in place of them.
FIELD_MEMBERS = ("form", "unit", "conditions", "specimen", "statistics", "provenance", "label", "fit")
FORM_MEMBERS = {form: "value" if form == "constant" else form for form in VOCABULARY.token_lists["form"]}
PROVENANCE_MEMBERS = (
    "origin",
    "source",
    "extraction",
    "evidence",
    "assistance",
    "review",
    "derivation",
    "formulation",
    "search",
    "import",
    "per_parameter",
    "recipe",
)

# Each member a check here reads a token from, by name, and every token list a record or a declaration binds
# to a member of that name. A token of one of them where the member's own row does not allow it is a token
# the reader knows for a member of that name (`form_invalid`); one of none of them, a token it knows for no
# member of that name (`unknown_token`). A condition's or a specimen fact's `token` takes its row's tokens.
BOUND: dict[str, tuple[str, ...]] = {
    "form": ("form",),
    "central": ("central",),
    "distribution": ("statistics_distribution", "uncertainty_distribution", "distribution"),
    "basis": (
        "statistics_basis",
        "uncertainty_basis",
        "interval_basis",
        "composition_basis",
        "basis",
        "mimics_basis",
    ),
    "represents": ("represents", "uncertainty_represents"),
    "level": ("level",),
    "within": ("level",),
    "precision_conditions": ("precision_conditions",),
    "dispersion": ("dispersion",),
    "origin": ("origin",),
    "stated_as": ("stated_as",),
    "set_or_measured": ("set_or_measured",),
    "label": ("label",),
    "sum_rule": ("sum_rule",),
    "component": ("component",),
}
ROW_TOKENS = frozenset(
    {token for spec in VOCABULARY.conditions.values() for token in spec.tokens}
    | {token for spec in VOCABULARY.facts.values() for token in spec.tokens}
)
# The basis a result's condition entry gives the value an implied condition supplies (`read_side_contract.md`
# section 2 item 6): a token the reader writes, and so knows, for a member named `basis`, which no row of a
# record allows (`form_invalid` there, never `unknown_token`).
IMPLIED_BASIS = "implied"
KNOWN: dict[str, frozenset[str]] = {
    member: frozenset(token for name in lists for token in VOCABULARY.token_lists[name])
    | frozenset({IMPLIED_BASIS} if member == "basis" else ())
    for member, lists in BOUND.items()
} | {"token": ROW_TOKENS}


def invalid(detail: str) -> Reason:
    return Reason("form_invalid", detail=detail)


def unknown_token(detail: str) -> Reason:
    return Reason("unknown_token", detail=detail)


# Members of one JSON type, or of a range of values (`read_side_contract.md` section 3, step 8's list).


def number(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float):
        found.append(invalid(f"{where} is not a number"))


def not_below_zero(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or value < 0:
        found.append(invalid(f"{where} is not a number from zero up"))


def above_zero(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or value <= 0:
        found.append(invalid(f"{where} is not a number above zero"))


def probability(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not 0 < value <= 1:
        found.append(invalid(f"{where} is not a number above zero and at most one"))


def whole(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not value.is_integer():
        found.append(invalid(f"{where} is not a whole number"))


def count(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not value.is_integer() or value < 0:
        found.append(invalid(f"{where} is not a whole number from zero up"))


def string(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, str):
        found.append(invalid(f"{where} is not a string"))


def boolean(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, bool):
        found.append(invalid(f"{where} is not true or false"))


def strings(value: JsonValue, where: str, found: Found) -> None:
    if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
        found.append(invalid(f"{where} is not a list of strings"))


def in_order(value: JsonValue, where: str, found: Found) -> None:
    """A range `[lo, hi]`, two numbers with `lo` not above `hi`."""
    lo, hi = value if isinstance(value, list) and len(value) == 2 else (None, None)
    if not (isinstance(lo, float) and isinstance(hi, float)):
        found.append(invalid(f"{where} is not two numbers"))
    elif lo > hi:
        found.append(invalid(f"{where} has lo above hi"))


def token(member: str, allowed: Collection[str]) -> Check:
    """A token of `allowed`, the tokens the row of a member named `member` allows."""

    def check(value: JsonValue, where: str, found: Found) -> None:
        token_problems(value, member, allowed, where, found)

    return check


def token_problems(value: JsonValue, member: str, allowed: Collection[str], where: str, found: Found) -> None:
    if not isinstance(value, str):
        found.append(invalid(f"{where} is not a token"))
    elif value in KNOWN[member] and value not in allowed:
        found.append(invalid(f"{where} holds {value!r}, a token its row does not allow"))
    elif value not in allowed:
        found.append(unknown_token(f"{where} holds {value!r}, a token the reader knows for no {member}"))


def listed(member: str, token_list: str) -> Check:
    """A token of the vocabulary's list `token_list`, in a member named `member`."""
    return token(member, VOCABULARY.token_lists[token_list])


# Objects, and the status objects that may stand in a member.


def slips(value: JsonObject, named: Collection[str], where: str, found: Found) -> None:
    for member, name in slipped(value, named):
        found.append(invalid(f"{where} holds {member!r}, one slip from {name!r}"))


def members(
    value: JsonValue,
    where: str,
    found: Found,
    required: Members,
    optional: Members | None = None,
    *,
    named: Collection[str] = (),
) -> JsonObject | None:
    """`value` as an object that holds each member of `required` and may hold those of `optional`, each
    passing its check, and holds no member one slip from one of them or from `named`, members its place
    names that another check reads. None, with a reason, where it is not an object."""
    if not isinstance(value, dict):
        found.append(invalid(f"{where} is not an object"))
        return None
    optional = optional or {}
    slips(value, (*required, *optional, *named), where, found)
    for name, check in required.items():
        if name in value:
            check(value[name], f"{where}.{name}", found)
        else:
            found.append(invalid(f"{where} holds no {name}"))
    for name, check in optional.items():
        if name in value:
            check(value[name], f"{where}.{name}", found)
    return value


def is_status_object(value: JsonValue) -> bool:
    """In a member whose row allows a status object, an object holding `status` is one."""
    return isinstance(value, dict) and "status" in value


def status_row(shape: type, member: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The row of `provenance.md` section 1 item 5 for `member` of `shape`, as the writer schema gives it and
    the generated shapes carry it: the status tokens it may hold, and the members of the shape S a status
    object stands in for there, none where S is a number, a string or a token."""
    tokens: tuple[str, ...] = ()
    defines: list[str] = []
    for alternative in get_args(get_type_hints(shape)[member]):
        if is_typeddict(alternative) and set(get_type_hints(alternative)) <= {"status", "reason"}:
            tokens = get_args(get_type_hints(alternative)["status"])
        elif is_typeddict(alternative):
            defines += get_type_hints(alternative)
    if not tokens:
        raise ValueError(f"{member} of {shape.__name__} takes no status object")
    return tokens, tuple(defines)


def or_status(check: Check, shape: type, member: str, defines: Collection[str] | None = None) -> Check:
    """`member` of `shape`, whose row allows a status object in place of its own shape S, which `check`
    checks. A status object holds a status token its row allows, and is refused where it also holds a member S
    defines (`defines`, where the row's are not S's own) or, where S is a number, a string or a token, any
    member but `status` and `reason` (`provenance.md` section 1 item 5)."""
    tokens, own = status_row(shape, member)
    return status_or(check, tokens, own if defines is None else tuple(defines))


def status_or(check: Check, tokens: Collection[str] | None, defines: Collection[str]) -> Check:
    """A status object with one of `tokens`, any token where None, or what `check` takes."""

    def checked(value: JsonValue, where: str, found: Found) -> None:
        if isinstance(value, dict) and "status" in value:
            status_object(value, where, tokens, defines, found)
        else:
            check(value, where, found)

    return checked


def status_object(
    value: JsonObject, where: str, tokens: Collection[str] | None, defines: Collection[str], found: Found
) -> None:
    """A status object that breaks its shape is read for nothing else, so its token gives no reason of its
    own (`provenance.md` section 1 item 5); a member one slip from `status`, `reason` or a member S defines
    breaks it, as a member S defines does."""
    status = value["status"]
    broken: Found = []
    if not isinstance(status, str):
        broken.append(invalid(f"{where}.status is not a string"))
    if "reason" in value and not isinstance(value["reason"], str):
        broken.append(invalid(f"{where}.reason is not a string"))
    others = sorted(value.keys() - {"status", "reason"})
    if not defines and others:
        broken.append(
            invalid(f"{where} holds {others} beside its status, where a number, string or token goes")
        )
    elif beside := [member for member in others if member in defines]:
        broken.append(
            invalid(f"{where} holds {beside} beside its status, members of the shape it stands for")
        )
    else:
        slips(value, ("status", "reason", *defines), where, broken)
    found.extend(broken)
    if broken or tokens is None:
        return
    if status in STATUS_TOKENS and status not in tokens:
        found.append(invalid(f"{where} holds the status {status!r}, which its row does not allow"))
    elif status not in tokens:
        found.append(unknown_token(f"{where} holds the status {status!r}, which the reader does not know"))


unit = status_or(string, None, ())
"""A unit, wherever it sits, a specimen fact's included: a string, or a status object whose token, known or
not, step 9 alone compares, with the unit the field's, the condition's or the fact's row registers or fixes
(`record_format.md` section 4.2, `read_side_contract.md` section 3 step 9)."""


def based(
    required: Members,
    optional: Members | None = None,
    rule: Check | None = None,
    *,
    fixed_basis: str | None = None,
    other_kind: Collection[str] = (),
) -> Check:
    """A condition's or a specimen fact's shape: `required` and `optional` with a `basis`, `stated`, or
    `inferred` with the text `inferred_from` (`provenance.md` section 6); then `rule`, a rule between its
    members, on an object. A row that fixes the basis to one token (`mimics`, `stated`) leaves nothing to
    infer from, so its shape names no `inferred_from`. A condition's `other_kind` are the members of the other
    kind of condition's shape, named at its place: one of them, whatever it holds, or a slip of one breaks its
    shape."""
    basis = listed("basis", "basis") if fixed_basis is None else token("basis", (fixed_basis,))
    inferred: Members = {"inferred_from": string} if fixed_basis is None else {}

    def check(value: JsonValue, where: str, found: Found) -> None:
        entry = members(
            value,
            where,
            found,
            {**required, "basis": basis},
            {**(optional or {}), **inferred},
            named=other_kind,
        )
        if entry is None:
            return
        found.extend(
            invalid(f"{where} holds {name!r}, a member of the other kind of condition's shape")
            for name in other_kind
            if name in entry
        )
        if inferred and entry.get("basis") == "inferred" and "inferred_from" not in entry:
            found.append(invalid(f"{where} is inferred and does not say from what"))
        if rule is not None:
            rule(entry, where, found)

    return check


def one_of_value_and_range(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict) and ("value" in value) == ("range" in value):
        found.append(invalid(f"{where} holds both or neither of value and range"))


# Conditions (`provenance.md` section 6.1).

# The members a status object standing for a condition may not hold beside it: those of every condition's
# shape, numeric or token, whatever the condition's own (`provenance.md` section 1 item 5).
CONDITION_MEMBERS = tuple(
    dict.fromkeys(
        member for name in VOCABULARY.conditions for member in status_row(shapes.Conditions, name)[1]
    )
)


def plus_minus(value: JsonValue, where: str, found: Found) -> None:
    """A non-empty list of `{"stated_as", "value", "unit"}`, at most one entry of each kind, and an entry of
    unstated kind alone (item 6)."""
    if not (isinstance(value, list) and value):
        found.append(invalid(f"{where} is not a non-empty list"))
        return
    stated_as = or_status(listed("stated_as", "stated_as"), shapes.PlusMinusEntry, "stated_as")
    kinds: list[str] = []
    for index, item in enumerate(value):
        entry = members(
            item, f"{where}[{index}]", found, {"stated_as": stated_as, "value": not_below_zero, "unit": unit}
        )
        kind = entry.get("stated_as") if entry is not None else None
        if kind in ("bound", "sd"):
            kinds.append(str(kind))
        elif isinstance(kind, dict) and kind.get("status") == "unstated":
            kinds.append("unstated")
    if len(set(kinds)) < len(kinds):
        found.append(invalid(f"{where} holds two entries of one kind"))
    if "unstated" in kinds and len(value) > 1:
        found.append(invalid(f"{where} holds an entry of unstated kind beside another"))


# The members of the other kind of condition's shape, which a condition never holds, whatever they hold, nor a
# slip of one (`provenance.md` section 6.1 item 1, the maintainer's ruling of 2026-10-19): a numeric
# condition's `token`, and a token condition's `value`, `range`, `plus_minus` and `set_or_measured`; a token
# condition's `unit` has a rule of its own, step 9's.
OF_THE_OTHER_KIND: dict[str, tuple[str, ...]] = {
    "numeric": ("token",),
    "token": ("value", "range", "plus_minus", "set_or_measured"),
}
NUMERIC_CONDITION = based(
    {"unit": unit},
    {
        "value": number,
        "range": in_order,
        "plus_minus": plus_minus,
        "set_or_measured": listed("set_or_measured", "set_or_measured"),
    },
    one_of_value_and_range,
    other_kind=OF_THE_OTHER_KIND["numeric"],
)


def condition(spec: ConditionSpec) -> Check:
    """A condition the reader knows: its row's shape, or a status object with any token. A token condition
    may hold a `unit`, which step 9 refuses, so step 8 checks only that it is a string or a status object."""
    own = (
        NUMERIC_CONDITION
        if spec.shape == "numeric"
        else based(
            {"token": token("token", spec.tokens)}, {"unit": unit}, other_kind=OF_THE_OTHER_KIND["token"]
        )
    )
    return or_status(own, shapes.Conditions, spec.name, CONDITION_MEMBERS)


CONDITIONS = {name: condition(spec) for name, spec in VOCABULARY.conditions.items()}


def conditions(value: JsonValue, where: str, found: Found) -> None:
    """Each condition the reader knows; a name it does not know gives `unknown` at step 10, so it is neither
    checked nor refused as a slip here (`record_format.md` section 10 item 2)."""
    if not isinstance(value, dict):
        found.append(invalid(f"{where} is not an object"))
        return
    for name, entry in value.items():
        if name in CONDITIONS:
            CONDITIONS[name](entry, f"{where}.{name}", found)


# Specimen facts (`provenance.md` section 6.2), each its row's shape or a status object with any token.


def other_with_text(value: JsonValue, where: str, found: Found) -> None:
    if isinstance(value, dict) and value.get("token") == "other" and "text" not in value:
        found.append(invalid(f"{where} holds other with no text"))


# The states whose text names the disease or the treatment: `text` is present exactly beside one of them,
# judged against the token as stored, so a text beside a token the reader does not know is refused too.
NAMED_STATES = ("diseased", "treated")


def text_exactly_for_named_states(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, dict):
        return
    named = value.get("token") in NAMED_STATES
    if named and "text" not in value:
        found.append(invalid(f"{where} holds {value.get('token')!r} with no text naming it"))
    elif not named and "text" in value:
        found.append(invalid(f"{where} holds a text, and its token is neither diseased nor treated"))


def fact_token(name: str) -> Check:
    return token("token", VOCABULARY.facts[name].tokens)


FACT_SHAPES: dict[str, tuple[Members, Members, Check | None]] = {
    "species": ({"ncbi_taxon": whole, "label": string}, {}, None),
    "anatomical_site": ({"uberon": string, "label": string}, {}, None),
    "tissue_state": ({"token": fact_token("tissue_state")}, {}, None),
    "disease_and_treatment_state": (
        {"token": fact_token("disease_and_treatment_state")},
        {"text": string},
        text_exactly_for_named_states,
    ),
    "preparation": ({"text": string}, {}, None),
    "preservation": ({"token": fact_token("preservation")}, {"text": string}, other_with_text),
    "post_mortem_interval": ({"value": number, "unit": unit}, {}, None),
    "donor_age": (
        {"unit": unit},
        {"value": number, "range": in_order},
        one_of_value_and_range,
    ),
    "mimics": ({"text": string}, {}, None),
    "supply_form": ({"token": fact_token("supply_form")}, {}, None),
    "lot": ({"text": string}, {}, None),
}
FACTS: dict[str, Check] = {
    name: or_status(
        based(required, optional, rule, fixed_basis=VOCABULARY.facts[name].fixed.get("basis")),
        shapes.Specimen,
        name,
    )
    for name, (required, optional, rule) in FACT_SHAPES.items()
}


def specimen(value: JsonValue, where: str, found: Found) -> None:
    """Specimen facts by name: each fact the reader knows has its row's shape, and a name one slip from a
    known fact's refuses, since an unknown fact is ignored."""
    if not isinstance(value, dict):
        found.append(invalid(f"{where} is not an object"))
        return
    slips(value, FACTS, where, found)
    for name, fact in value.items():
        if name in FACTS:
            FACTS[name](fact, f"{where}.{name}", found)


# The statistics block and its uncertainties (`uncertainty.md` sections 1 and 4).


def present_exactly_where(
    value: JsonObject, by_represents: Mapping[str, str], where: str, found: Found
) -> None:
    """Each conditional member present exactly where the `represents` beside it holds its token."""
    for represents, member in by_represents.items():
        if member in value and value.get("represents") != represents:
            found.append(invalid(f"{where} holds {member}, and represents is not {represents}"))
        elif member not in value and value.get("represents") == represents:
            found.append(invalid(f"{where} holds no {member}, and represents is {represents}"))


def uncertainty_rules(value: JsonObject, where: str, found: Found) -> None:
    """At least one of the coverage factor and probability a number, and `dof` a number exactly where the
    distribution is `student_t`; otherwise a status object."""
    if not any(
        isinstance(value.get(member), float) for member in ("coverage_factor", "coverage_probability")
    ):
        found.append(invalid(f"{where} has neither a coverage factor nor a coverage probability"))
    dof = value.get("dof")
    if value.get("distribution") == "student_t" and is_status_object(dof):
        found.append(invalid(f"{where}.dof is not a number, under student_t"))
    elif value.get("distribution") != "student_t" and isinstance(dof, float):
        found.append(invalid(f"{where}.dof is a number, under another distribution than student_t"))
    present_exactly_where(value, {"measurement": "precision_conditions"}, where, found)


UNCERTAINTY: tuple[Members, Members] = (
    {
        "value": not_below_zero,
        "coverage_factor": or_status(above_zero, shapes.Uncertainty, "coverage_factor"),
        "coverage_probability": or_status(probability, shapes.Uncertainty, "coverage_probability"),
        "distribution": or_status(
            listed("distribution", "uncertainty_distribution"), shapes.Uncertainty, "distribution"
        ),
        "dof": or_status(above_zero, shapes.Uncertainty, "dof"),
        "basis": listed("basis", "uncertainty_basis"),
        "represents": or_status(
            listed("represents", "uncertainty_represents"), shapes.Uncertainty, "represents"
        ),
    },
    {
        "precision_conditions": or_status(
            listed("precision_conditions", "precision_conditions"), shapes.Uncertainty, "precision_conditions"
        )
    },
)


def uncertainty(value: JsonValue, where: str, found: Found) -> None:
    entry = members(value, where, found, *UNCERTAINTY)
    if entry is not None:
        uncertainty_rules(entry, where, found)


def population_level(value: JsonValue, where: str, found: Found) -> None:
    within = or_status(listed("within", "level"), shapes.PopulationLevel, "within")
    members(value, where, found, {"level": listed("level", "level"), "within": within})


STATISTICS: tuple[Members, Members] = (
    {
        "central": or_status(listed("central", "central"), shapes.StatisticsBlock, "central"),
        "n_specimens": or_status(count, shapes.StatisticsBlock, "n_specimens"),
        "n_donors": or_status(count, shapes.StatisticsBlock, "n_donors"),
        "mean": or_status(number, shapes.StatisticsBlock, "mean"),
        "sd": or_status(not_below_zero, shapes.StatisticsBlock, "sd"),
        "min": or_status(number, shapes.StatisticsBlock, "min"),
        "max": or_status(number, shapes.StatisticsBlock, "max"),
        "distribution": or_status(
            listed("distribution", "statistics_distribution"), shapes.StatisticsBlock, "distribution"
        ),
        "basis": or_status(listed("basis", "statistics_basis"), shapes.StatisticsBlock, "basis"),
        "represents": or_status(listed("represents", "represents"), shapes.StatisticsBlock, "represents"),
        "dispersion": listed("dispersion", "dispersion"),
        "relative_uncertainty": or_status(uncertainty, shapes.StatisticsBlock, "relative_uncertainty"),
        "expanded_uncertainty": or_status(uncertainty, shapes.StatisticsBlock, "expanded_uncertainty"),
    },
    {
        "population_level": or_status(population_level, shapes.StatisticsBlock, "population_level"),
        "n_sources": or_status(count, shapes.StatisticsBlock, "n_sources"),
        "precision_conditions": or_status(
            listed("precision_conditions", "precision_conditions"),
            shapes.StatisticsBlock,
            "precision_conditions",
        ),
    },
)
BY_REPRESENTS = {
    "population": "population_level",
    "across_sources": "n_sources",
    "measurement": "precision_conditions",
}


def statistics_block(value: JsonValue, where: str, found: Found) -> None:
    block = members(value, where, found, *STATISTICS)
    if block is not None:
        present_exactly_where(block, BY_REPRESENTS, where, found)


# A field's statistics block, or a status object: `withheld` in a reference-only value (`provenance.md`
# section 7), and on reference data `not_applicable` too (`fits_and_reference_data.md` section 1).
FIELD_STATISTICS = or_status(statistics_block, shapes.ConstantField, "statistics")
REFERENCE_DATA_STATISTICS = or_status(statistics_block, shapes.ReferenceDataField, "statistics")


# The provenance members a read uses (`provenance.md` sections 2 and 5).


def source(value: JsonValue, where: str, found: Found) -> None:
    """The source's `key`, a string, which a result returns alone; its `document` and `locator` are the record
    checks' (`provenance.md` section 2 item 6)."""
    members(value, where, found, {"key": string}, named=("document", "locator"))


def pinned_record(value: JsonValue, where: str, found: Found) -> None:
    members(value, where, found, {"id": string, "version": string, "content_hash": string})


def derivation_input(value: JsonValue, where: str, found: Found) -> None:
    members(value, where, found, {"record": pinned_record, "field": string})


def derivation_inputs(value: JsonValue, where: str, found: Found) -> None:
    if not (isinstance(value, list) and value):
        found.append(invalid(f"{where} is not a non-empty list"))
        return
    for index, item in enumerate(value):
        derivation_input(item, f"{where}[{index}]", found)


def input_specimens(value: JsonValue, where: str, inputs: int | None, found: Found) -> None:
    """A list of `{"input": <index into inputs>, "specimen": <specimen facts>}` (`provenance.md` section 5
    item 3); the index is checked against the inputs' count where `inputs` is a list."""
    if not isinstance(value, list):
        found.append(invalid(f"{where} is not a list"))
        return
    for index, item in enumerate(value):
        here = f"{where}[{index}]"
        entry = members(item, here, found, {"input": count, "specimen": specimen})
        position = entry.get("input") if entry is not None else None
        if inputs is not None and isinstance(position, float) and position >= inputs:
            found.append(invalid(f"{here}.input is past the last input"))


def derivation(value: JsonValue, where: str, found: Found) -> None:
    entry = members(
        value,
        where,
        found,
        {"method": string, "inputs": derivation_inputs, "assumptions": strings},
        {"mixed_conditions": boolean},
        named=("input_specimens",),
    )
    if entry is None:
        return
    if "input_specimens" not in entry:
        found.append(invalid(f"{where} holds no input_specimens"))
        return
    inputs = entry.get("inputs")
    count_of_inputs = len(inputs) if isinstance(inputs, list) else None
    input_specimens(entry["input_specimens"], f"{where}.input_specimens", count_of_inputs, found)


def provenance(value: JsonValue, where: str, found: Found) -> None:
    """`origin`; `source`, present for `measured_by_source` and checked wherever present; and the
    `derivation` of a derived value. `review` never refuses, and the other members are the record checks'
    (`provenance.md` section 2 item 6)."""
    entry = members(
        value,
        where,
        found,
        {"origin": listed("origin", "origin")},
        {"source": source},
        named=PROVENANCE_MEMBERS,
    )
    if entry is None:
        return
    origin = entry.get("origin")
    if origin == "measured_by_source" and "source" not in entry:
        found.append(invalid(f"{where} holds no source, which the origin measured_by_source requires"))
    if origin == "derived" and "derivation" not in entry:
        found.append(invalid(f"{where} holds no derivation, which the origin derived requires"))
    elif origin == "derived":
        derivation(entry["derivation"], f"{where}.derivation", found)


# A field's label (`record_format.md` section 4.1, "Labels" and the Label column).


def label_allowed(spec: RecordFieldSpec, form: str | None, field: JsonObject) -> bool:
    """Whether the row lets its label go on a field of this form: on a constant, and on a table whose axis is
    not the condition the row names, where it names one (`vocabulary/fields.json`, `label_not_on_axis`)."""
    if form == "constant":
        return spec.label is not None
    if form == "table" and spec.label is not None and spec.label_not_on_axis is not None:
        table = field.get("table")
        return not (isinstance(table, dict) and table.get("axis") == spec.label_not_on_axis)
    return False


def label(
    value: JsonValue, where: str, spec: RecordFieldSpec, form: str | None, field: JsonObject, found: Found
) -> None:
    """A label the reader knows, the one the row names for this field and its form. Beside a form token the
    reader does not know, the row names it for no such form; where the form is missing or not a string, which
    refuses the field on its own, there is no form to judge it on."""
    if not isinstance(value, str):
        found.append(invalid(f"{where} is not a string"))
    elif value not in KNOWN["label"]:
        found.append(unknown_token(f"{where} holds {value!r}, a label the reader does not know"))
    elif value != spec.label:
        found.append(invalid(f"{where} holds {value!r}, which the row does not name for this field"))
    elif isinstance(stored := field.get("form"), str) and not label_allowed(spec, form, field):
        beside = (
            f"a field of form {form}" if form is not None else f"{stored!r}, a form the reader does not know"
        )
        found.append(invalid(f"{where} holds {value!r}, which the row does not name for {beside}"))


# The checks a read makes: on the record's structure, on the section a field sits in, and on the field.


def record_problems(record: JsonObject) -> Found:
    """The members one slip from a member named at its place in a material record's envelope, licence, body
    and section names: each refuses every field read from the record. Step 3 found the body and its sections
    to be objects."""
    found: Found = []
    slips(record, ENVELOPE_MEMBERS, "the record", found)
    licence, body = record.get("licence"), record.get("body")
    if isinstance(licence, dict):
        slips(licence, LICENCE_MEMBERS, "licence", found)
    if isinstance(body, dict):
        slips(body, MATERIAL_BODY_MEMBERS, "body", found)
        sections = body.get("sections")
        if isinstance(sections, dict):
            slips(sections, VOCABULARY.sections, "body.sections", found)
    return found


def section_problems(name: str, section: JsonObject) -> Found:
    """A slip in a section's members or field names, and a fault in its `specimen`: each refuses every field
    read from the section."""
    found: Found = []
    where = f"body.sections.{name}"
    slips(section, SECTION_MEMBERS, where, found)
    fields = section.get("fields")
    if isinstance(fields, dict):
        registered = [
            field.partition(".")[2] for field in VOCABULARY.fields if field.partition(".")[0] == name
        ]
        slips(fields, registered, f"{where}.fields", found)
    if "specimen" in section:
        specimen(section["specimen"], f"{where}.specimen", found)
    return found


def field_problems(field: JsonObject, spec: RecordFieldSpec, form: str | None) -> Found:
    """A field's shared members. `form` is its form where the reader knows the token, and None where not; it
    decides the own member named at the field's place (every form's, for None) and whether a statistics block
    is required (not for evidence). The form's own member is its reader's (`fields.py`)."""
    found: Found = []
    where = spec.name
    own = (FORM_MEMBERS[form],) if form is not None else tuple(FORM_MEMBERS.values())
    required: dict[str, Check] = {"unit": unit, "conditions": conditions, "provenance": provenance}
    if form == "reference_data":
        required["statistics"] = REFERENCE_DATA_STATISTICS
    elif form != "evidence":
        required["statistics"] = FIELD_STATISTICS
    members(
        field, where, found, required, {"specimen": specimen}, named=(*FIELD_MEMBERS, *own, "alternatives")
    )
    if "label" in field:
        label(field["label"], f"{where}.label", spec, form, field, found)
    return found
