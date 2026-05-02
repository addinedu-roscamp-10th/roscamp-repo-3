import json
from datetime import date, datetime, timezone


def test_format_map_profile_uses_if_loc_001_response_fields():
    from server.ropi_main_service.application.coordinate_config_formatters import (
        format_map_profile,
    )

    assert format_map_profile(
        {
            "map_id": "map_test11_0423",
            "map_name": "map_test11_0423",
            "map_revision": "1",
            "frame_id": "",
            "yaml_path": "maps/map.yaml",
            "pgm_path": "maps/map.pgm",
            "is_active": 1,
        }
    ) == {
        "map_id": "map_test11_0423",
        "map_name": "map_test11_0423",
        "map_revision": 1,
        "frame_id": "map",
        "yaml_path": "maps/map.yaml",
        "pgm_path": "maps/map.pgm",
        "is_active": True,
    }


def test_format_operation_zone_keeps_boundary_metadata_when_payload_hidden():
    from server.ropi_main_service.application.coordinate_config_formatters import (
        format_operation_zone,
    )

    boundary = {
        "type": "POLYGON",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": 0.0, "y": 0.2},
            {"x": 1.2, "y": 0.2},
            {"x": 1.2, "y": 1.1},
        ],
    }

    formatted = format_operation_zone(
        {
            "zone_id": "room_301",
            "map_id": "map_test11_0423",
            "zone_name": "301호",
            "zone_type": "ROOM",
            "revision": "2",
            "boundary_json": json.dumps(boundary),
            "is_enabled": "true",
            "created_at": datetime(2026, 5, 2, 12, 0, 0),
            "updated_at": date(2026, 5, 3),
        },
        include_boundary=False,
    )

    assert formatted["boundary_json"] is None
    assert formatted["boundary_vertex_count"] == 3
    assert formatted["boundary_frame_id"] == "map"
    assert formatted["created_at"] == "2026-05-02T12:00:00"
    assert formatted["updated_at"] == "2026-05-03"


def test_format_goal_pose_and_patrol_area_normalize_numeric_fields():
    from server.ropi_main_service.application.coordinate_config_formatters import (
        format_goal_pose,
        format_patrol_area,
    )

    assert format_goal_pose(
        {
            "goal_pose_id": "delivery_room_301",
            "map_id": "map_test11_0423",
            "zone_id": "room_301",
            "zone_name": "301호",
            "purpose": "DESTINATION",
            "pose_x": "1.6946",
            "pose_y": "",
            "pose_yaw": None,
            "frame_id": "",
            "is_enabled": "0",
        }
    )["pose_x"] == 1.6946

    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
            {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
        ],
    }
    formatted_patrol_area = format_patrol_area(
        {
            "patrol_area_id": "patrol_ward_night_01",
            "map_id": "map_test11_0423",
            "patrol_area_name": "야간 병동 순찰",
            "revision": "7",
            "path_json": path_json,
            "waypoint_count": None,
            "path_frame_id": None,
            "is_enabled": 1,
        },
        include_patrol_path=False,
    )

    assert formatted_patrol_area["path_json"] is None
    assert formatted_patrol_area["waypoint_count"] == 2
    assert formatted_patrol_area["path_frame_id"] == "map"


def test_coordinate_config_primitive_formatters_are_stable():
    from server.ropi_main_service.application.coordinate_config_formatters import (
        bool_value,
        generated_at,
        json_object,
        normalize_optional_text,
        optional_float,
        optional_int,
    )

    assert json_object(b'{"value": 1}') == {"value": 1}
    assert json_object("[1, 2]") == {}
    assert bool_value("yes") is True
    assert bool_value("no") is False
    assert optional_int("12") == 12
    assert optional_int("bad") is None
    assert optional_float("1.5") == 1.5
    assert optional_float("") is None
    assert normalize_optional_text("  room_301 ") == "room_301"
    assert normalize_optional_text("") is None
    assert generated_at(lambda: datetime(2026, 5, 2, 3, 10, tzinfo=timezone.utc)) == (
        "2026-05-02T03:10:00+00:00"
    )
