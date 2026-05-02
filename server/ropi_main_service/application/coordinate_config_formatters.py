import json
from datetime import date, datetime


def generated_at(clock):
    value = clock()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def format_map_profile(row):
    return {
        "map_id": row.get("map_id"),
        "map_name": row.get("map_name"),
        "map_revision": optional_int(row.get("map_revision")) or 0,
        "frame_id": row.get("frame_id") or "map",
        "yaml_path": row.get("yaml_path"),
        "pgm_path": row.get("pgm_path"),
        "is_active": bool_value(row.get("is_active")),
    }


def format_operation_zone(row, *, include_boundary=True):
    boundary_json = json_object(row.get("boundary_json"))
    if not boundary_json:
        boundary_json = None

    vertices = []
    boundary_frame_id = None
    if boundary_json is not None:
        raw_vertices = boundary_json.get("vertices")
        if isinstance(raw_vertices, list):
            vertices = raw_vertices
        header = boundary_json.get("header")
        if isinstance(header, dict):
            boundary_frame_id = normalize_optional_text(header.get("frame_id"))

    return {
        "zone_id": row.get("zone_id"),
        "map_id": row.get("map_id"),
        "zone_name": row.get("zone_name"),
        "zone_type": row.get("zone_type"),
        "revision": optional_int(row.get("revision")) or 0,
        "boundary_json": boundary_json if include_boundary else None,
        "boundary_vertex_count": len(vertices),
        "boundary_frame_id": boundary_frame_id,
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


def format_goal_pose(row):
    return {
        "goal_pose_id": row.get("goal_pose_id"),
        "map_id": row.get("map_id"),
        "zone_id": row.get("zone_id"),
        "zone_name": row.get("zone_name"),
        "purpose": row.get("purpose"),
        "pose_x": optional_float(row.get("pose_x")) or 0.0,
        "pose_y": optional_float(row.get("pose_y")) or 0.0,
        "pose_yaw": optional_float(row.get("pose_yaw")) or 0.0,
        "frame_id": row.get("frame_id") or "map",
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


def format_patrol_area(row, *, include_patrol_path):
    path_json = json_object(row.get("path_json"))
    poses = path_json.get("poses")
    if not isinstance(poses, list):
        poses = []

    header = (
        path_json.get("header")
        if isinstance(path_json.get("header"), dict)
        else {}
    )
    waypoint_count = optional_int(row.get("waypoint_count"))
    if waypoint_count is None:
        waypoint_count = len(poses)

    return {
        "patrol_area_id": row.get("patrol_area_id"),
        "map_id": row.get("map_id"),
        "patrol_area_name": row.get("patrol_area_name"),
        "revision": optional_int(row.get("revision")) or 0,
        "path_json": path_json if include_patrol_path else None,
        "waypoint_count": waypoint_count,
        "path_frame_id": row.get("path_frame_id") or header.get("frame_id"),
        "is_enabled": bool_value(row.get("is_enabled")),
        "created_at": isoformat(row.get("created_at")),
        "updated_at": isoformat(row.get("updated_at")),
    }


def json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    return bool(value)


def optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_optional_text(value):
    text = str(value or "").strip()
    return text or None


def isoformat(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


__all__ = [
    "bool_value",
    "format_goal_pose",
    "format_map_profile",
    "format_operation_zone",
    "format_patrol_area",
    "generated_at",
    "isoformat",
    "json_object",
    "normalize_optional_text",
    "optional_float",
    "optional_int",
]
