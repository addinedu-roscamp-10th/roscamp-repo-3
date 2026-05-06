def fms_edge_row_from_form(page):
    return {
        "edge_id": page.fms_edge_id_input.text().strip(),
        "from_waypoint_id": page.fms_edge_from_waypoint_combo.currentData(),
        "to_waypoint_id": page.fms_edge_to_waypoint_combo.currentData(),
        "is_bidirectional": page.fms_edge_bidirectional_check.isChecked(),
        "traversal_cost": page.fms_edge_traversal_cost_spin.value(),
        "priority": page.fms_edge_priority_spin.value(),
        "is_enabled": page.fms_edge_enabled_check.isChecked(),
    }


def build_fms_edge_payload(edge_row, *, expected_updated_at=None):
    edge_row = edge_row if isinstance(edge_row, dict) else {}
    return {
        "edge_id": str(edge_row.get("edge_id") or "").strip(),
        "expected_updated_at": expected_updated_at,
        "from_waypoint_id": edge_row.get("from_waypoint_id"),
        "to_waypoint_id": edge_row.get("to_waypoint_id"),
        "is_bidirectional": bool(edge_row.get("is_bidirectional")),
        "traversal_cost": edge_row.get("traversal_cost"),
        "priority": edge_row.get("priority"),
        "is_enabled": bool(edge_row.get("is_enabled", True)),
    }


def fms_edge_from_save_response(response):
    if not isinstance(response, dict):
        return None
    edge = response.get("edge")
    return dict(edge) if isinstance(edge, dict) else None


__all__ = [
    "build_fms_edge_payload",
    "fms_edge_from_save_response",
    "fms_edge_row_from_form",
]
