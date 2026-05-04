from ui.utils.pages.caregiver.coordinate_boundary_editing import (
    boundary_json_from_vertices,
)


def build_operation_zone_save_payload(
    *,
    mode,
    selected_operation_zone,
    map_profile,
    zone_id,
    zone_name,
    zone_type,
    is_enabled,
):
    if str(mode or "").strip() == "create":
        profile = map_profile if isinstance(map_profile, dict) else {}
        return {
            "zone_id": _stripped_text(zone_id),
            "zone_name": _stripped_text(zone_name),
            "zone_type": _stripped_text(zone_type),
            "map_id": profile.get("map_id"),
            "is_enabled": bool(is_enabled),
        }

    selected = (
        selected_operation_zone
        if isinstance(selected_operation_zone, dict)
        else {}
    )
    return {
        "zone_id": _stripped_text(zone_id),
        "expected_revision": _int_or_default(selected.get("revision")),
        "zone_name": _stripped_text(zone_name),
        "zone_type": _stripped_text(zone_type),
        "is_enabled": bool(is_enabled),
    }


def build_operation_zone_boundary_save_payload(
    *,
    selected_operation_zone,
    boundary_vertices,
    frame_id,
):
    selected = (
        selected_operation_zone
        if isinstance(selected_operation_zone, dict)
        else {}
    )
    return {
        "zone_id": _stripped_text(selected.get("zone_id")),
        "expected_revision": _int_or_default(selected.get("revision")),
        "boundary_json": boundary_json_from_vertices(
            boundary_vertices,
            frame_id=_frame_id_or_default(frame_id),
        ),
    }


def operation_zone_from_save_response(response):
    response = response if isinstance(response, dict) else {}
    operation_zone = response.get("operation_zone")
    return operation_zone if isinstance(operation_zone, dict) else None


def _frame_id_or_default(value, default="map"):
    frame_id = _stripped_text(value)
    return frame_id or default


def _int_or_default(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _stripped_text(value):
    return str(value or "").strip()


__all__ = [
    "build_operation_zone_boundary_save_payload",
    "build_operation_zone_save_payload",
    "operation_zone_from_save_response",
]
