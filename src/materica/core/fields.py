# SPDX-License-Identifier: Apache-2.0
"""A record's value fields (`record_format.md` sections 5 and 6): finding the field a read names and checking
the shape of the alternatives it may hold (step 7 of `read_side_contract.md` section 3), checking its form and
shape (step 8) and its units (step 9).

Step 8 checks the form token against the field's row, a composition's basis included, then the members every
form shares (`value_shapes.py`), then the form's own member, where the row allows the form: a constant's, a
table's, an interval's, a composition's and evidence's, and for a table its axis condition too. A form the row
does not allow is refused whatever its own member holds, which the read neither uses nor returns.

Step 9 compares each unit the field states with the one registered for it, code point for code point, as
step 0 does a request's, and a unit registered as a status object by its token (`record_format.md` section
4.2): none is parsed or converted. A table's `axis_unit` is compared with its axis condition's unit.
"""

import itertools
from collections.abc import Collection
from dataclasses import dataclass
from typing import get_type_hints

from materica import shapes
from materica.core.jsonio import JsonValue
from materica.core.reasons import Reason
from materica.core.slips import slipped
from materica.core.value_shapes import (
    CONDITIONS,
    FIELD_MEMBERS,
    FORM_MEMBERS,
    Check,
    Found,
    JsonObject,
    a_list,
    an_object,
    field_problems,
    in_order,
    invalid,
    is_status_object,
    listed,
    members,
    number,
    or_status,
    provenance,
    record_problems,
    section_problems,
    slips,
    statistics_block,
    status_or,
    status_row,
    string,
    unit,
    unknown_token,
    whole,
)
from materica.core.vocabulary import STATUS_TOKENS, VOCABULARY, RecordFieldSpec
from materica.shapes import Suite

# The forms whose own member step 8 reads, each with the shape of a field of that form: every form a row of
# schema 0.1 allows.
FIELD_SHAPES: dict[str, type] = {
    "constant": shapes.ConstantField,
    "table": shapes.TableField,
    "interval": shapes.IntervalField,
    "composition": shapes.CompositionField,
    "evidence": shapes.EvidenceField,
}


@dataclass(frozen=True)
class RecordField:
    """A value field as stored, never mutated, with the section it sits in and its row of `record_format.md`
    section 4.1."""

    spec: RecordFieldSpec
    value: JsonValue
    section: JsonObject

    def specimen(self) -> JsonObject:
        """The specimen facts of a field that passed step 8: the section's, each overridden by the field's
        fact of that name (`record_format.md` section 4 item 2)."""
        value = an_object(self.value)
        return {**an_object(self.section.get("specimen", {})), **an_object(value.get("specimen", {}))}


def find_field(record: JsonObject, spec: RecordFieldSpec) -> RecordField | Reason:
    """Step 7: the field `spec` names, in a material record that passed step 3, or `absent`."""
    section_name, _, name = spec.name.partition(".")
    sections = an_object(an_object(record["body"])["sections"])
    if section_name not in sections:
        return Reason("absent", detail=f"the record holds no section {section_name}")
    section = an_object(sections[section_name])
    fields = an_object(section["fields"])
    if name not in fields:
        return Reason("absent", detail=f"the section {section_name} holds no field {name}")
    return RecordField(spec, fields[name], section)


def alternatives_problems(holder: JsonObject, name: str) -> Found:
    """Step 7's check of a field holding alternatives (`record_format.md` section 5): a non-empty list of
    objects, none holding `alternatives` of its own, and beside it no member of a value field, nor a member
    one slip from `alternatives` or from one of those. An alternative that breaks a value field's shape
    otherwise is its own fault, found when it is read at step 8."""
    found: Found = []
    named = (*FIELD_MEMBERS, *dict.fromkeys(FORM_MEMBERS.values()))
    if beside := [member for member in named if member in holder]:
        found.append(Reason("form_invalid", detail=f"{name} holds {beside} beside its alternatives"))
    for member, near in slipped(holder, ("alternatives", *named)):
        found.append(Reason("form_invalid", detail=f"{name} holds {member!r}, one slip from {near!r}"))
    alternatives = holder["alternatives"]
    if not isinstance(alternatives, list) or not alternatives:
        found.append(Reason("form_invalid", detail=f"{name}.alternatives is not a list of one or more"))
    elif any(not isinstance(entry, dict) or "alternatives" in entry for entry in alternatives):
        found.append(
            Reason(
                "form_invalid", detail=f"{name}.alternatives holds a non-object or one holding alternatives"
            )
        )
    return found


def form_problems(field: RecordField, record: JsonObject, claims: Collection[Suite]) -> Found:
    """Step 8: every reason the record's structure, the field's section and the field give."""
    found = record_problems(record) + section_problems(field.spec.section, field.section)
    if not isinstance(field.value, dict):
        return [*found, invalid(f"{field.spec.name} is not an object")]
    form, allowed = _form(field.value, field.spec, claims, found)
    found += field_problems(field.value, field.spec, form)
    if form is not None and allowed:
        _own_member(field.value, field.spec.name, form, found)
    if form == "table" and allowed:
        _axis_condition(field.value, field.spec.name, found)
    if "evidence" in field.spec.forms:
        # `record_format.md` section 4.3 item 3 binds the evidence field, whatever its form: "`conditions`
        # holds no registered condition: one there is a shape error" (maintainer, 2026-10-19: a table there
        # holding its axis condition gives `form_invalid` beside `form_not_registered`).
        _no_registered_condition(field.value.get("conditions"), f"{field.spec.name}.conditions", found)
    return found


def _form(
    field: JsonObject, spec: RecordFieldSpec, claims: Collection[Suite], found: Found
) -> tuple[str | None, bool]:
    """The field's form, where it is a token the reader knows, and whether its row allows it, a composition's
    basis included (`record_format.md` section 4.1)."""
    form = field.get("form")
    where = f"{spec.name}.form"
    if "form" not in field or not isinstance(form, str):
        found.append(invalid(f"{where} is missing or not a string"))
        return None, False
    if form not in VOCABULARY.token_lists["form"]:
        found.append(unknown_token(f"{where} holds {form!r}, which the reader knows for no form"))
        return None, False
    if form not in spec.forms:
        found.append(Reason("form_not_registered", detail=f"{where} is {form}, which its row does not allow"))
    if form == "parameter_set" and "family_evaluation" not in claims:
        found.append(Reason("family_suite_absent", detail=f"{where} is a parameter set"))
    return form, form in spec.forms and _basis_allowed(field, spec, form, found)


def _basis_allowed(field: JsonObject, spec: RecordFieldSpec, form: str, found: Found) -> bool:
    """Whether the basis of a form whose bases the row restricts (`composition (basis `mass_fraction`)`) is
    one the row allows. A basis of the form's own list that the row does not allow is `form_not_registered`;
    any other basis, or none, is the form's own member's to judge."""
    allowed = spec.bases.get(form)
    member = field.get(FORM_MEMBERS[form])
    basis = member.get("basis") if isinstance(member, dict) else None
    if allowed is None or basis not in VOCABULARY.token_lists.get(f"{form}_basis", ()) or basis in allowed:
        return True
    where = f"{spec.name}.{FORM_MEMBERS[form]}.basis"
    found.append(Reason("form_not_registered", detail=f"{where} is {basis}, which its row does not allow"))
    return False


# The forms' own members (`record_format.md` section 6).


def table(value: JsonValue, where: str, found: Found) -> None:
    """A table's members, each checked, so that a table returned as stored holds only checked members
    (`read_side_contract.md` section 3, step 8): items 1, 2 and 4's rules on them, each a function of its
    own, and `points`, a reserved name, refused by its presence whatever it holds (item 5)."""
    entry = members(value, where, found, TABLE, TABLE_OPTIONAL, named=TABLE_RESERVED)
    if entry is None:
        return
    _points(entry, where, found)
    x, y, edges = (_numbers(entry.get(name)) for name in ("x", "y", "edges"))
    if x is not None:
        _abscissae(x, edges, where, found)
    if x is not None and y is not None:
        _one_y_for_each_x(x, y, where, found)
    if edges is not None:
        _edges_once(edges, where, found)
    _positive_where_log_log(entry.get("scheme"), [*(x or ()), *(y or ())], where, found)
    source_range = _numbers(entry.get("source_range"))
    if x is not None and edges is not None and source_range is not None and len(source_range) == 2:
        _shares_a_value_no_edge(source_range, x, edges, f"{where}.source_range", found)


def _points(entry: JsonObject, where: str, found: Found) -> None:
    """Item 5: `points_unsupported` for a table holding `points`, whatever it holds; and `form_invalid` for
    `null` there, in a member step 8 checks (`record_format.md` section 1 item 5)."""
    if "points" not in entry:
        return
    found.append(
        Reason("points_unsupported", detail=f"{where} holds points, which this reader does not read")
    )
    if entry["points"] is None:
        found.append(invalid(f"{where}.points is null"))


def _one_y_for_each_x(x: list[float], y: list[float], where: str, found: Found) -> None:
    """Item 1: "`y` holds one number for each entry of `x`"."""
    if len(y) != len(x):
        found.append(invalid(f"{where}.y holds {len(y)} numbers, not one for each of x's {len(x)}"))


def _edges_once(edges: list[float], where: str, found: Found) -> None:
    """Item 1: no number twice in `edges`, compared by value, so `-0` repeats `0`."""
    if len(set(edges)) < len(edges):
        found.append(invalid(f"{where}.edges lists a number twice"))


def _positive_where_log_log(scheme: JsonValue, values: list[float], where: str, found: Found) -> None:
    """Item 2: "A `loglog` table holds only positive `x` and `y`", `-0` no more than `0`."""
    if scheme == "loglog" and any(value <= 0 for value in values):
        found.append(invalid(f"{where} is log-log and holds an x or a y that is not positive"))


def numbers(value: JsonValue, where: str, found: Found) -> None:
    if _numbers(value) is None:
        found.append(invalid(f"{where} is not a list of numbers"))


def _numbers(value: JsonValue) -> list[float] | None:
    if isinstance(value, list) and all(isinstance(item, float) for item in value):
        return [item for item in value if isinstance(item, float)]
    return None


def _abscissae(x: list[float], edges: list[float] | None, where: str, found: Found) -> None:
    """Item 1's rules on `x`, numbers compared by value (`-0` equals `0`): at least two distinct values, in
    an order that never decreases; each edge strictly between `x[0]` and `x[-1]` (an empty `x` has no ends
    to hold one between), in `x` exactly twice and consecutively; and no other value of `x` twice. `x` is
    indexed once, so that the edges are checked in time linear in the table's length."""
    if len(set(x)) < 2:
        found.append(invalid(f"{where}.x holds fewer than two distinct values"))
    if any(later < earlier for earlier, later in itertools.pairwise(x)):
        found.append(invalid(f"{where}.x decreases"))
    held = _indexes_by_value(x)
    for edge in edges or ():
        if not (x and x[0] < edge < x[-1]):
            found.append(invalid(f"{where}.edges holds {edge!r}, not strictly between x's ends"))
        at = held.get(edge, [])
        if len(at) != 2 or at[1] != at[0] + 1:
            found.append(invalid(f"{where}.edges holds {edge!r}, which x does not hold twice in a row"))
    edged = set(edges or ())
    if repeated := sorted(value for value, at in held.items() if len(at) > 1 and value not in edged):
        found.append(invalid(f"{where}.x repeats {repeated}, which are no edges"))


def _indexes_by_value(x: list[float]) -> dict[float, list[int]]:
    """Each value of `x` and the indexes that hold it. A float key is found by value, so `-0` and `0` are one
    key."""
    held: dict[float, list[int]] = {}
    for index, value in enumerate(x):
        held.setdefault(value, []).append(index)
    return held


def _shares_a_value_no_edge(
    source_range: list[float], x: list[float], edges: list[float], where: str, found: Found
) -> None:
    """Item 4: `source_range`, two numbers in order, shares with `[x[0], x[-1]]` at least one value that is no
    edge. Two ranges that overlap in more than a point share infinitely many values, and so one that is no
    edge. An empty `x` has no range to share a value with, and item 1 refuses it already."""
    lo, hi = source_range
    if lo > hi or not x:
        return
    shared_lo, shared_hi = max(lo, x[0]), min(hi, x[-1])
    if shared_lo > shared_hi or (shared_lo == shared_hi and shared_lo in edges):
        found.append(invalid(f"{where} shares no value that is no edge with x's range"))


TABLE: dict[str, Check] = {
    "axis": listed("axis", "axis"),
    "axis_unit": unit,
    "x": numbers,
    "y": numbers,
    "scheme": listed("scheme", "table_scheme"),
    "edges": numbers,
}
TABLE_OPTIONAL: dict[str, Check] = {"source_range": in_order}
# Item 5: "`points` counts as a member named at a table's place"; a 0.1.0 reader refuses it by its presence.
TABLE_RESERVED = ("points",)


def _axis_condition(field: JsonObject, name: str, found: Found) -> None:
    """Item 1: the field's `conditions` hold a known axis as `{"status": "not_applicable"}`, a `reason`
    allowed. An axis the reader does not know was refused as a token, and its rule is not checked (item 2)."""
    table_member, conditions = field.get("table"), field.get("conditions")
    if (
        not isinstance(table_member, dict)
        or is_status_object(table_member)
        or not isinstance(conditions, dict)
    ):
        return
    axis = table_member.get("axis")
    if not isinstance(axis, str) or axis not in VOCABULARY.token_lists["axis"]:
        return
    held = conditions.get(axis)
    if not (is_status_object(held) and an_object(held)["status"] == "not_applicable"):
        found.append(invalid(f"{name}.conditions does not hold its table's axis {axis} as not_applicable"))


def interval(value: JsonValue, where: str, found: Found) -> None:
    """`lower` and `upper`, each a number or `{"status": "none"}`, not both `none`, and `lower <= upper`
    where both are numbers; and `basis`, a token of the interval's list (`record_format.md` section 6,
    interval items 1 and 2)."""
    entry = members(
        value, where, found, {"lower": INTERVAL_BOUND, "upper": INTERVAL_BOUND, "basis": INTERVAL_BASIS}
    )
    if entry is None:
        return
    lower, upper = entry.get("lower"), entry.get("upper")
    if _none(lower) and _none(upper):
        found.append(invalid(f"{where} holds none for both bounds"))
    elif isinstance(lower, float) and isinstance(upper, float) and lower > upper:
        found.append(invalid(f"{where} has its lower bound above its upper"))


def _none(bound: JsonValue) -> bool:
    return is_status_object(bound) and an_object(bound)["status"] == "none"


INTERVAL_BOUND = or_status(number, shapes.Interval, "lower")
INTERVAL_BASIS = listed("basis", "interval_basis")


def composition(value: JsonValue, where: str, found: Found) -> None:
    """`basis` and `sum_rule`, tokens of their lists; `stated_sum`, where present, a number; and `components`
    (`record_format.md` section 6, composition items 1 to 3 and 5). A basis of the composition's list that the
    row does not allow was refused before, as a form the row does not allow."""
    members(
        value,
        where,
        found,
        {"basis": COMPOSITION_BASIS, "sum_rule": SUM_RULE, "components": components},
        {"stated_sum": number},
    )


def components(value: JsonValue, where: str, found: Found) -> None:
    """At least one component, none twice, each `element:<symbol>` of the table, its `fraction` a number
    from 0 to 1, and its own statistics block, where it has one, checked as a field's."""
    if not (isinstance(value, list) and value):
        found.append(invalid(f"{where} is not a non-empty list"))
        return
    seen: set[str] = set()
    for index, item in enumerate(value):
        here = f"{where}[{index}]"
        entry = members(item, here, found, COMPONENT, {"statistics": COMPONENT_STATISTICS})
        name = entry.get("component") if entry is not None else None
        if isinstance(name, str) and name in seen:
            found.append(invalid(f"{where} names {name!r} twice"))
        if isinstance(name, str):
            seen.add(name)


def fraction(value: JsonValue, where: str, found: Found) -> None:
    if not isinstance(value, float) or not 0 <= value <= 1:
        found.append(invalid(f"{where} is not a number from zero to one"))


COMPOSITION_BASIS = listed("basis", "composition_basis")
SUM_RULE = listed("sum_rule", "sum_rule")
COMPONENT: dict[str, Check] = {"component": listed("component", "component"), "fraction": fraction}
COMPONENT_STATISTICS = or_status(statistics_block, shapes.CompositionComponent, "statistics")


def evidence(value: JsonValue, where: str, found: Found) -> None:
    """At least one entry, never a status, each withheld whole or not at all (`record_format.md` section 4.3
    items 1 and 2): `withheld` where every entry is withheld, `entries_withheld` where some are
    (`read_side_contract.md` section 3, step 8)."""
    if not (isinstance(value, list) and value):
        found.append(invalid(f"{where} is not a non-empty list"))
        return
    withheld = [evidence_entry(item, f"{where}[{index}]", found) for index, item in enumerate(value)]
    if all(withheld):
        found.append(Reason("withheld", detail=f"every entry of {where} is withheld"))
    elif any(withheld):
        found.append(
            Reason(
                "entries_withheld",
                detail=f"{sum(withheld)} of the {len(value)} entries of {where} are withheld",
            )
        )


def evidence_entry(value: JsonValue, where: str, found: Found) -> bool:
    """A test report, holding every member; its provenance checked as a field's is, the members that check
    leaves unchecked returned as found (`record_format.md` section 4.3 item 2). Whether it is withheld: each
    member but its provenance a withheld marker that keeps its shape."""
    if not isinstance(value, dict):
        found.append(invalid(f"{where} is not an object"))
        return False
    slips(value, (*REPORT, "provenance"), where, found)
    withheld: list[bool] = []
    for name, check in REPORT.items():
        if name not in value:
            found.append(invalid(f"{where} holds no {name}"))
            continue
        here: Found = []
        check(value[name], f"{where}.{name}", here)
        found += here
        withheld.append(
            not here and is_status_object(value[name]) and an_object(value[name])["status"] == "withheld"
        )
    if "provenance" in value:
        provenance(value["provenance"], f"{where}.provenance", found)
    else:
        found.append(invalid(f"{where} holds no provenance"))
    whole = len(withheld) == len(REPORT) and all(withheld)
    if any(withheld) and not whole:
        found.append(invalid(f"{where} is an entry withholding some of its members, not every one"))
    return whole


def _no_registered_condition(conditions: JsonValue, where: str, found: Found) -> None:
    """Evidence's `conditions` hold no registered condition (`record_format.md` section 4.3 item 3); a name
    the reader does not know gives `unknown` at step 10, as anywhere, and `conditions` that are not an object
    are the shared checks' fault."""
    if isinstance(conditions, dict) and (registered := [name for name in conditions if name in CONDITIONS]):
        found.append(
            invalid(f"{where} holds a registered condition, which evidence takes none of: {registered}")
        )


def standard(value: JsonValue, where: str, found: Found) -> None:
    members(value, where, found, {"designation": string, "year": whole})


def _report_member(name: str, check: Check) -> Check:
    """A member of a test report: its shape, or a status object with any of the five tokens (`provenance.md`
    section 1 item 5's table: "any; `withheld` only in every one of them at once", which `evidence_entry`
    judges)."""
    _, defines = status_row(shapes.EvidenceEntry, name)
    return status_or(check, STATUS_TOKENS, defines)


REPORT: dict[str, Check] = {
    name: _report_member(name, standard if name == "standard" else string)
    for name in get_type_hints(shapes.EvidenceEntry)
    if name != "provenance"
}

# Each form's own member as a field of that form holds it: its shape, or `withheld` in a reference-only value
# (`provenance.md` section 7), but evidence, which never holds a status object (section 1 item 5).
OWN_MEMBERS: dict[str, Check] = {
    "constant": or_status(number, shapes.ConstantField, "value"),
    # `points` is named at a table's place (`record_format.md` section 6, table item 5), so a status object
    # standing for a table that holds a member one slip from it breaks its shape; `points` itself, which the
    # table's shape does not define, is ignored there: "Elsewhere a member beside `status` and `reason` that S
    # does not define is ignored" (`provenance.md` section 1 item 5).
    "table": or_status(table, shapes.TableField, "table", named=TABLE_RESERVED),
    "interval": or_status(interval, shapes.IntervalField, "interval"),
    "composition": or_status(composition, shapes.CompositionField, "composition"),
    "evidence": evidence,
}


def _own_member(field: JsonObject, name: str, form: str, found: Found) -> None:
    """The form's own member: its shape, and `withheld` where it holds a withheld marker that keeps its shape
    (`provenance.md` section 1 item 5)."""
    member = FORM_MEMBERS[form]
    if member not in field:
        found.append(invalid(f"{name} holds no {member}"))
        return
    value = field[member]
    before = len(found)
    OWN_MEMBERS[form](value, f"{name}.{member}", found)
    if isinstance(value, dict) and value.get("status") == "withheld" and len(found) == before:
        found.append(Reason("withheld", detail=f"{name} is a reference-only value"))


def same_unit(stored: JsonValue, registered: JsonValue) -> bool:
    """`record_format.md` section 4.2: a string equal to the registered one code point for code point, or,
    where a status object is registered, a status object holding its `status` token, whatever its `reason`."""
    if isinstance(registered, dict):
        return is_status_object(stored) and an_object(stored)["status"] == registered["status"]
    return isinstance(stored, str) and stored == registered


def unit_problems(field: RecordField) -> Found:
    """Step 9, for a field that passed step 8 (`read_side_contract.md` section 3): `unit_mismatch` for each
    unit other than the one registered for it: the field's; a table's `axis_unit`, with its axis; a known
    numeric condition's and its `plus_minus` entries', with that condition; a `unit` on a token condition,
    which registers none, with that condition; and a specimen fact's, against the unit its row fixes, wherever
    step 8 checks the fact (the section's specimen, the field's, and a derived value's inputs')."""
    value = an_object(field.value)
    found: Found = []
    _compare_unit(value["unit"], field.spec.unit, f"{field.spec.name}.unit", None, found)
    if value["form"] == "table" and not is_status_object(table_member := value["table"]):
        axis = str(an_object(table_member)["axis"])
        held = an_object(table_member)["axis_unit"]
        _compare_unit(
            held, VOCABULARY.conditions[axis].unit, f"{field.spec.name}.table.axis_unit", axis, found
        )
    for name, condition in an_object(value["conditions"]).items():
        spec = VOCABULARY.conditions.get(name)
        if spec is None or is_status_object(condition):
            continue
        held = an_object(condition)
        where = f"{field.spec.name}.conditions.{name}"
        if spec.unit is None:
            if "unit" in held:
                found.append(
                    _mismatch(f"{where} holds a unit, which a token condition does not register", name)
                )
            continue
        _compare_unit(held["unit"], spec.unit, f"{where}.unit", name, found)
        for index, entry in enumerate(a_list(held.get("plus_minus", []))):
            _compare_unit(
                an_object(entry)["unit"], spec.unit, f"{where}.plus_minus[{index}].unit", name, found
            )
    for where, specimen in _specimens(field):
        for name, fact in specimen.items():
            fixed = VOCABULARY.facts[name].fixed.get("unit") if name in VOCABULARY.facts else None
            if fixed is not None and not is_status_object(fact):
                _compare_unit(an_object(fact)["unit"], fixed, f"{where}.{name}.unit", None, found)
    return found


def _compare_unit(
    stored: JsonValue, registered: JsonValue, where: str, condition: str | None, found: Found
) -> None:
    if not same_unit(stored, registered):
        found.append(_mismatch(f"{where} is {stored!a}, not the registered {registered!a}", condition))


def _mismatch(detail: str, condition: str | None) -> Reason:
    return Reason("unit_mismatch", condition, detail)


def _specimens(field: RecordField) -> list[tuple[str, JsonObject]]:
    """Each specimen step 8 checks for `field`, and where it is: the section's, the field's, and a derived
    value's inputs'."""
    value = an_object(field.value)
    section = field.spec.section
    found = [
        (where, an_object(holder["specimen"]))
        for where, holder in (
            (f"body.sections.{section}.specimen", field.section),
            (f"{field.spec.name}.specimen", value),
        )
        if "specimen" in holder
    ]
    provenance = an_object(value["provenance"])
    if provenance["origin"] == "derived":
        inputs = a_list(an_object(provenance["derivation"])["input_specimens"])
        found += [
            (
                f"{field.spec.name}.provenance.derivation.input_specimens[{index}].specimen",
                an_object(an_object(item)["specimen"]),
            )
            for index, item in enumerate(inputs)
        ]
    return found
