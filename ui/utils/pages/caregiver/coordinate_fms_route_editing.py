def fms_route_row_from_form(page):
    return {
        "route_id": page.fms_route_id_input.text().strip(),
        "route_name": page.fms_route_name_input.text().strip(),
        "route_scope": page.fms_route_scope_combo.currentText().strip(),
        "revision": _optional_int(page.fms_route_revision_label.text()),
        "waypoint_sequence": [
            _normalized_route_waypoint(index, row)
            for index, row in enumerate(page.fms_route_waypoint_rows, start=1)
        ],
        "is_enabled": page.fms_route_enabled_check.isChecked(),
    }


def build_fms_route_payload(route_row, *, expected_revision=None):
    route_row = route_row if isinstance(route_row, dict) else {}
    return {
        "route_id": str(route_row.get("route_id") or "").strip(),
        "expected_revision": expected_revision,
        "route_name": str(route_row.get("route_name") or "").strip(),
        "route_scope": str(route_row.get("route_scope") or "").strip().upper(),
        "waypoint_sequence": [
            _payload_waypoint(index, row)
            for index, row in enumerate(
                route_row.get("waypoint_sequence") or [], start=1
            )
            if isinstance(row, dict)
        ],
        "is_enabled": bool(route_row.get("is_enabled")),
    }


def fms_route_from_save_response(response):
    if not isinstance(response, dict):
        return None
    route = response.get("route")
    return dict(route) if isinstance(route, dict) else None


def fms_route_waypoint_table_rows(sequence, waypoint_label_by_id=None):
    labels = waypoint_label_by_id if isinstance(waypoint_label_by_id, dict) else {}
    rows = []
    for index, waypoint in enumerate(sequence or [], start=1):
        if not isinstance(waypoint, dict):
            continue
        waypoint_id = str(waypoint.get("waypoint_id") or "").strip()
        display = waypoint_id
        if waypoint_id in labels:
            display = f"{waypoint_id} ({labels[waypoint_id]})"
        rows.append(
            {
                "sequence_no": str(index),
                "waypoint_id": display,
                "stop_required": "정차"
                if bool(waypoint.get("stop_required", True))
                else "통과",
                "yaw_policy": str(waypoint.get("yaw_policy") or "AUTO_NEXT"),
                "dwell_sec": _display_optional_float(waypoint.get("dwell_sec")),
            }
        )
    return rows


def _normalized_route_waypoint(index, row):
    row = row if isinstance(row, dict) else {}
    yaw_policy = str(row.get("yaw_policy") or "AUTO_NEXT").strip().upper()
    fixed_pose_yaw = row.get("fixed_pose_yaw")
    if yaw_policy != "FIXED":
        fixed_pose_yaw = None
    return {
        "sequence_no": index,
        "waypoint_id": str(row.get("waypoint_id") or "").strip(),
        "yaw_policy": yaw_policy,
        "fixed_pose_yaw": fixed_pose_yaw,
        "stop_required": bool(row.get("stop_required", True)),
        "dwell_sec": row.get("dwell_sec"),
    }


def _payload_waypoint(index, row):
    normalized = _normalized_route_waypoint(index, row)
    return {
        "sequence_no": normalized["sequence_no"],
        "waypoint_id": normalized["waypoint_id"],
        "yaw_policy": normalized["yaw_policy"],
        "fixed_pose_yaw": normalized["fixed_pose_yaw"],
        "stop_required": normalized["stop_required"],
        "dwell_sec": normalized["dwell_sec"],
    }


def _optional_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _display_optional_float(value):
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


__all__ = [
    "build_fms_route_payload",
    "fms_route_from_save_response",
    "fms_route_row_from_form",
    "fms_route_waypoint_table_rows",
]
