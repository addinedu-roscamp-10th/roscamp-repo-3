from dataclasses import dataclass

from PyQt6.QtWidgets import QTableWidgetItem


@dataclass(frozen=True)
class CoordinateConfigBundle:
    source: dict
    map_profile: dict
    operation_zones: list
    goal_poses: list
    patrol_areas: list
    fms_waypoints: list
    fms_edges: list
    fms_routes: list


def normalize_coordinate_config_bundle(bundle):
    source = bundle if isinstance(bundle, dict) else {}
    map_profile = source.get("map_profile")
    return CoordinateConfigBundle(
        source=source,
        map_profile=map_profile if isinstance(map_profile, dict) else {},
        operation_zones=_dict_rows(source.get("operation_zones")),
        goal_poses=_dict_rows(source.get("goal_poses")),
        patrol_areas=_dict_rows(source.get("patrol_areas")),
        fms_waypoints=_dict_rows(source.get("fms_waypoints", source.get("waypoints"))),
        fms_edges=_dict_rows(source.get("fms_edges", source.get("edges"))),
        fms_routes=_dict_rows(source.get("fms_routes", source.get("routes"))),
    )


def find_row_index_by_value(rows, key, value):
    if value in (None, ""):
        return None
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if isinstance(row, dict) and row.get(key) == value:
            return index
    return None


def set_table_rows(table, rows, columns):
    rows = rows if isinstance(rows, list) else []
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        for column_index, column in enumerate(columns):
            value = _column_value(row, column)
            table.setItem(row_index, column_index, QTableWidgetItem(value))


def _dict_rows(rows):
    return [row for row in rows or [] if isinstance(row, dict)]


def _column_value(row, column):
    if isinstance(column, tuple):
        key, formatter = column
        return formatter(row, row.get(key))
    return _display(row.get(column))


def _display(value):
    if value is None or value == "":
        return "-"
    return str(value)


def _enabled_text(_row, value):
    return "활성" if bool(value) else "비활성"


def _zone_label(row, value):
    return _display(value or row.get("zone_id"))


def _goal_pose_text(row, _value):
    try:
        x = float(row.get("pose_x"))
        y = float(row.get("pose_y"))
        yaw = float(row.get("pose_yaw"))
    except (TypeError, ValueError):
        return "-"
    return f"x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"


def _waypoint_count_text(row, value):
    if value not in (None, ""):
        return str(value)
    path_json = row.get("path_json")
    poses = path_json.get("poses") if isinstance(path_json, dict) else []
    return str(len(poses)) if isinstance(poses, list) else "0"


def _edge_direction_text(_row, value):
    return "양방향" if bool(value) else "단방향"


def _route_waypoint_count_text(row, _value):
    sequence = row.get("waypoint_sequence")
    return str(len(sequence)) if isinstance(sequence, list) else "0"


OPERATION_ZONE_TABLE_COLUMNS = [
    "zone_id",
    "zone_name",
    "zone_type",
    ("is_enabled", _enabled_text),
]
GOAL_POSE_TABLE_COLUMNS = [
    "goal_pose_id",
    "purpose",
    ("zone_name", _zone_label),
    ("pose", _goal_pose_text),
]
PATROL_AREA_TABLE_COLUMNS = [
    "patrol_area_id",
    "revision",
    ("waypoint_count", _waypoint_count_text),
    ("is_enabled", _enabled_text),
]
FMS_WAYPOINT_TABLE_COLUMNS = [
    "waypoint_id",
    "display_name",
    "waypoint_type",
    ("pose_x", _goal_pose_text),
    ("is_enabled", _enabled_text),
]
FMS_EDGE_TABLE_COLUMNS = [
    "edge_id",
    "from_waypoint_id",
    "to_waypoint_id",
    ("is_bidirectional", _edge_direction_text),
    ("is_enabled", _enabled_text),
]
FMS_ROUTE_TABLE_COLUMNS = [
    "route_id",
    "route_name",
    "route_scope",
    ("waypoint_sequence", _route_waypoint_count_text),
    ("is_enabled", _enabled_text),
]


__all__ = [
    "CoordinateConfigBundle",
    "FMS_EDGE_TABLE_COLUMNS",
    "FMS_ROUTE_TABLE_COLUMNS",
    "FMS_WAYPOINT_TABLE_COLUMNS",
    "GOAL_POSE_TABLE_COLUMNS",
    "OPERATION_ZONE_TABLE_COLUMNS",
    "PATROL_AREA_TABLE_COLUMNS",
    "find_row_index_by_value",
    "normalize_coordinate_config_bundle",
    "set_table_rows",
]
