from ui.utils.pages.caregiver.coordinate_pose_editing import coerce_point2d


def build_fms_waypoint_payload(row, *, expected_updated_at=None):
    row = row if isinstance(row, dict) else {}
    return {
        "waypoint_id": str(row.get("waypoint_id") or "").strip(),
        "expected_updated_at": expected_updated_at,
        "display_name": str(row.get("display_name") or "").strip(),
        "waypoint_type": str(row.get("waypoint_type") or "").strip().upper(),
        "pose_x": _float_or_default(row.get("pose_x")),
        "pose_y": _float_or_default(row.get("pose_y")),
        "pose_yaw": _float_or_default(row.get("pose_yaw")),
        "frame_id": str(row.get("frame_id") or "map").strip(),
        "snap_group": _optional_text(row.get("snap_group")),
        "is_enabled": bool(row.get("is_enabled")),
    }


def fms_waypoint_from_save_response(response):
    response = response if isinstance(response, dict) else {}
    waypoint = response.get("waypoint")
    return dict(waypoint) if isinstance(waypoint, dict) else None


def fms_waypoint_world_point_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    return coerce_point2d(
        {
            "x": payload.get("pose_x"),
            "y": payload.get("pose_y"),
        }
    )


def fms_waypoint_row_from_form(page):
    return {
        "waypoint_id": page.fms_waypoint_id_input.text().strip(),
        "display_name": page.fms_waypoint_name_input.text().strip(),
        "waypoint_type": page.fms_waypoint_type_combo.currentText().strip(),
        "pose_x": page.fms_waypoint_x_spin.value(),
        "pose_y": page.fms_waypoint_y_spin.value(),
        "pose_yaw": page.fms_waypoint_yaw_spin.value(),
        "frame_id": page.fms_waypoint_frame_id_label.text().strip() or "map",
        "snap_group": _optional_text(page.fms_waypoint_snap_group_input.text()),
        "is_enabled": page.fms_waypoint_enabled_check.isChecked(),
    }


def _optional_text(value):
    text = str(value or "").strip()
    return text or None


def _float_or_default(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "build_fms_waypoint_payload",
    "fms_waypoint_from_save_response",
    "fms_waypoint_row_from_form",
    "fms_waypoint_world_point_from_payload",
]
