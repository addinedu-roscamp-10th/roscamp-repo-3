from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
    patrol_path_payload_poses,
)


def build_patrol_area_path_save_payload(
    *,
    selected_patrol_area,
    patrol_area_id,
    frame_id,
    waypoints,
):
    selected = selected_patrol_area if isinstance(selected_patrol_area, dict) else {}
    return {
        "patrol_area_id": str(patrol_area_id or "").strip(),
        "expected_revision": _int_or_default(selected.get("revision")),
        "path_json": {
            "header": {"frame_id": _frame_id_or_default(frame_id)},
            "poses": patrol_path_payload_poses(waypoints),
        },
    }


def build_patrol_area_save_payload(
    *,
    mode,
    selected_patrol_area,
    patrol_area_id,
    patrol_area_name,
    frame_id,
    waypoints,
    is_enabled,
):
    payload = {
        "patrol_area_id": str(patrol_area_id or "").strip(),
        "patrol_area_name": str(patrol_area_name or "").strip(),
        "path_json": {
            "header": {"frame_id": _frame_id_or_default(frame_id)},
            "poses": patrol_path_payload_poses(waypoints),
        },
        "is_enabled": bool(is_enabled),
    }
    if str(mode or "").strip() != "create":
        selected = (
            selected_patrol_area
            if isinstance(selected_patrol_area, dict)
            else {}
        )
        payload["expected_revision"] = _int_or_default(selected.get("revision"))
    return payload


def patrol_area_from_path_save_response(response):
    response = response if isinstance(response, dict) else {}
    patrol_area = response.get("patrol_area")
    return patrol_area if isinstance(patrol_area, dict) else None


def patrol_area_from_save_response(response):
    return patrol_area_from_path_save_response(response)


def patrol_path_poses_from_save_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    path_json = payload.get("path_json")
    path_json = path_json if isinstance(path_json, dict) else {}
    poses = path_json.get("poses")
    return poses if isinstance(poses, list) else []


def _frame_id_or_default(value, default="map"):
    frame_id = str(value or "").strip()
    return frame_id or default


def _int_or_default(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


__all__ = [
    "build_patrol_area_save_payload",
    "build_patrol_area_path_save_payload",
    "patrol_area_from_save_response",
    "patrol_area_from_path_save_response",
    "patrol_path_poses_from_save_payload",
]
