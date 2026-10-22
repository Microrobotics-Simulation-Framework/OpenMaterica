# SPDX-License-Identifier: Apache-2.0
"""The case files of a read the reference model does not agree with, grouped by kind, each kind with its
reason: the exact list `test_cases.py` holds the model to (the maintainer's ruling 3 on S2a-1's open points).
Every kind is a read outside the model's scope, on which it gives no verdict, never a pass; each kind names
the detail of that outcome, so that a file the model gives no verdict on for another reason fails."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal


@dataclass(frozen=True)
class Excepted:
    reason: str
    outcome: Literal["differs", "no verdict"]
    case_files: frozenset[str]
    detail: str | None = None  # the outcome's detail every listed file gives, where the kind names one


EXCEPTIONS: Final[Mapping[str, Excepted]] = {
    "picks": Excepted(
        ("A pick is checked and applied at step 7 (S4); the model reads alternatives with no pick alone."),
        "no verdict",
        frozenset(
            {
                "PR-044.entry_not_object_with_pick.json",
                "PR-304.pick_absent_field.json",
                "PR-304.pick_alternative_not_met.json",
                "PR-304.pick_at_interval_not_applied.json",
                "PR-304.pick_at_record_and_interval_not_applied.json",
                "PR-304.pick_at_record_and_region_not_applied.json",
                "PR-304.pick_at_unnamed_overlay_not_applied.json",
                "PR-304.pick_broken_alternatives.json",
                "PR-304.pick_counts_set_aside.json",
                "PR-304.pick_fault_in_other_refuses_nothing.json",
                "PR-304.pick_index_1e0.json",
                "PR-304.pick_index_huge.json",
                "PR-304.pick_index_minus_zero.json",
                "PR-304.pick_index_one_point_zero.json",
                "PR-304.pick_interval_nominal_applied.json",
                "PR-304.pick_kept_table_extrapolation_applied.json",
                "PR-304.pick_no_location_not_applied.json",
                "PR-304.pick_on_field_without_alternatives.json",
                "PR-304.pick_other_field_not_applied.json",
                "PR-304.pick_other_hash_not_applied.json",
                "PR-304.pick_other_record_not_applied.json",
                "PR-304.pick_past_last.json",
                "PR-304.pick_reads_named.json",
                "PR-330.overlay_acceptance_other_field_without_overlay.json",
                "PR-330.pick_field_not_registered.json",
                "PR-330.pick_index_fractional.json",
                "PR-330.pick_index_missing.json",
                "PR-330.pick_index_negative.json",
                "PR-330.pick_index_not_number.json",
                "PR-330.pick_near_typo_indices.json",
                "PR-330.pick_other_field_index_fractional.json",
                "PR-330.two_picks_one_field.json",
                "PR-330.two_picks_one_field_same_index.json",
                "PR-330.two_picks_one_field_two_records.json",
                "PR-330.two_picks_other_field.json",
                "PR-330.two_picks_two_fields_read.json",
            }
        ),
        detail="a pick acceptance (S4)",
    ),
    "overlays": Excepted(
        ("An overlay is resolved and applied at step 6 (S4); the model applies none."),
        "no verdict",
        frozenset(
            {
                "PR-002.overlay_base_without_content_hash.json",
                "PR-007.overlay_acceptance_names_interface.json",
                "PR-007.overlay_acceptance_names_material.json",
                "PR-011.base_body_slip_fluids.json",
                "PR-011.base_envelope_slip_crad.json",
                "PR-011.base_field_fault_not_refused.json",
                "PR-011.base_section_member_slip_not_refused.json",
                "PR-011.base_section_specimen_slip_not_refused.json",
                "PR-011.fit_overlay_read.json",
                "PR-011.overlay_body_slip_replace.json",
                "PR-011.overlay_envelope_slip_crad.json",
                "PR-011.overlay_field_shape_refused.json",
                "PR-011.overlay_other_field_shape_not_checked.json",
                "PR-011.replaces_whole_field.json",
                "PR-012.overlay_named_for_other_field.json",
                "PR-012.overlay_named_for_other_field_not_resolved.json",
                "PR-039.base_content_hash_uppercase.json",
                "PR-039.base_other_content_hash.json",
                "PR-039.base_other_id.json",
                "PR-039.base_stale_version.json",
                "PR-041.one_overlay_named_twice.json",
                "PR-041.other_field_overlay_no_conflict.json",
                "PR-041.same_id_and_version_other_hash_conflict.json",
                "PR-041.same_overlay_two_fields.json",
                "PR-041.two_overlays_conflict.json",
                "PR-042.broken_marker_in_value_only.json",
                "PR-042.broken_withheld_marker.json",
                "PR-042.fit_over_withheld.json",
                "PR-042.measurement_over_withheld.json",
                "PR-042.purpose_fil_in.json",
                "PR-042.purpose_fil_in_not_replacing_read_field.json",
                "PR-042.purpose_fil_in_over_withheld.json",
                "PR-042.withheld_evidence_entry.json",
                "PR-042.withheld_field_not_replaced.json",
                "PR-042.withheld_in_one_alternative.json",
                "PR-042.withheld_marker_in_statistics_only.json",
                "PR-042.withheld_other_key.json",
                "PR-042.withheld_value_beside_unknown_form.json",
                "PR-046.does_not_replace_read_field.json",
                "PR-046.one_of_two_does_not_replace.json",
                "PR-046.other_key_base_lacks.json",
                "PR-046.other_key_field_lacked_in_held_section.json",
                "PR-106.fill_in_read.json",
                "PR-107.base_holds_alternatives.json",
                "PR-107.base_version_not_string.json",
                "PR-107.base_without_document.json",
                "PR-107.both_hold_alternatives.json",
                "PR-107.fill_in_alternative_picked.json",
                "PR-107.fill_in_alternatives_one_mismatch.json",
                "PR-107.fill_in_identifier_not_string.json",
                "PR-107.fill_in_other_identifier.json",
                "PR-107.fill_in_other_version.json",
                "PR-107.fill_in_version_not_string.json",
                "PR-107.fill_in_without_document.json",
                "PR-304.overlay_alternatives_no_pick.json",
                "PR-304.pick_at_base_of_overlaid_field.json",
                "PR-304.pick_at_overlay.json",
                "PR-304.pick_at_overlay_named_for_other_field.json",
                "PR-304.pick_at_overlay_past_last.json",
                "PR-304.pick_at_overlay_single_value.json",
                "PR-307.at_base_of_overlaid_field.json",
                "PR-307.at_overlay_not_applied.json",
                "PR-310.overlay_absent.json",
                "PR-310.overlay_hash_mismatch.json",
                "PR-310.overlay_hash_mismatch_no_hs.json",
                "PR-310.overlay_other_version.json",
                "PR-310.overlay_pin_mismatch.json",
                "PR-310.overlay_unreadable_source.json",
                "PR-310.two_overlays_two_faults.json",
                "PR-330.overlay_acceptance_without_overlay.json",
                "PR-330.overlay_reference_without_content_hash.json",
            }
        ),
        detail="an overlay acceptance (S4)",
    ),
}
