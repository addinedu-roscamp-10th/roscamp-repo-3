def test_normalize_operation_zone_input_uses_if_loc_002_and_003_fields():
    from server.ropi_main_service.application.coordinate_config_validators import (
        normalize_operation_zone_input,
    )

    normalized, error = normalize_operation_zone_input(
        zone_id=" room_301 ",
        zone_name=" 301호 ",
        zone_type=" room ",
        is_enabled="yes",
    )

    assert error is None
    assert normalized == {
        "zone_id": "room_301",
        "zone_name": "301호",
        "zone_type": "ROOM",
        "is_enabled": True,
    }

    normalized, error = normalize_operation_zone_input(
        zone_id="room_301",
        zone_name="301호",
        zone_type="unknown",
        is_enabled=True,
    )

    assert normalized is None
    assert error == {
        "result_code": "INVALID_REQUEST",
        "result_message": "zone_type이 유효하지 않습니다.",
        "reason_code": "ZONE_TYPE_INVALID",
        "operation_zone": None,
    }


def test_normalize_operation_zone_boundary_input_uses_if_loc_007_fields():
    from server.ropi_main_service.application.coordinate_config_validators import (
        normalize_operation_zone_boundary_input,
    )

    normalized, error = normalize_operation_zone_boundary_input(
        zone_id=" room_301 ",
        expected_revision="2",
        boundary_json={
            "type": "polygon",
            "header": {"frame_id": "map"},
            "vertices": [
                {"x": "0.0", "y": "0.2"},
                {"x": 1.2, "y": 0.2},
                {"x": 1.2, "y": 1.1},
            ],
        },
        active_frame_id="map",
    )

    assert error is None
    assert normalized == {
        "zone_id": "room_301",
        "expected_revision": 2,
        "boundary_json": {
            "type": "POLYGON",
            "header": {"frame_id": "map"},
            "vertices": [
                {"x": 0.0, "y": 0.2},
                {"x": 1.2, "y": 0.2},
                {"x": 1.2, "y": 1.1},
            ],
        },
    }

    normalized, error = normalize_operation_zone_boundary_input(
        zone_id="room_301",
        expected_revision="2",
        boundary_json=None,
        active_frame_id="map",
    )

    assert error is None
    assert normalized == {
        "zone_id": "room_301",
        "expected_revision": 2,
        "boundary_json": None,
    }


def test_normalize_goal_pose_input_uses_if_loc_004_fields():
    from server.ropi_main_service.application.coordinate_config_validators import (
        normalize_goal_pose_input,
    )

    normalized, error = normalize_goal_pose_input(
        goal_pose_id=" delivery_room_301 ",
        expected_updated_at=" 2026-05-02T12:01:00 ",
        zone_id=" room_301 ",
        purpose=" destination ",
        pose_x="1.7",
        pose_y="0.02",
        pose_yaw="0",
        frame_id="map",
        is_enabled="false",
        active_frame_id="map",
    )

    assert error is None
    assert normalized == {
        "goal_pose_id": "delivery_room_301",
        "expected_updated_at": "2026-05-02T12:01:00",
        "zone_id": "room_301",
        "purpose": "DESTINATION",
        "pose_x": 1.7,
        "pose_y": 0.02,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "is_enabled": False,
    }

    normalized, error = normalize_goal_pose_input(
        goal_pose_id="delivery_room_301",
        expected_updated_at=None,
        zone_id=None,
        purpose="GUIDE",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
        active_frame_id="map",
    )

    assert normalized is None
    assert error["reason_code"] == "GOAL_POSE_PURPOSE_INVALID"
    assert error["goal_pose"] is None


def test_normalize_patrol_area_path_input_uses_if_loc_005_fields():
    from server.ropi_main_service.application.coordinate_config_validators import (
        normalize_patrol_area_path_input,
    )

    normalized, error = normalize_patrol_area_path_input(
        patrol_area_id=" patrol_ward_night_01 ",
        expected_revision="7",
        path_json={
            "header": {"frame_id": "map"},
            "poses": [
                {"x": "0.1666", "y": "-0.4497", "yaw": "1.5708"},
                {"x": "1.6946", "y": "0.0043", "yaw": "0"},
            ],
        },
        active_frame_id="map",
    )

    assert error is None
    assert normalized == {
        "patrol_area_id": "patrol_ward_night_01",
        "expected_revision": 7,
        "path_json": {
            "header": {"frame_id": "map"},
            "poses": [
                {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
                {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
            ],
        },
    }

    normalized, error = normalize_patrol_area_path_input(
        patrol_area_id="patrol_ward_night_01",
        expected_revision="7",
        path_json={
            "header": {"frame_id": "map"},
            "poses": [{"x": 0.0, "y": 0.0, "yaw": 0.0}],
        },
        active_frame_id="map",
    )

    assert normalized is None
    assert error["reason_code"] == "PATROL_PATH_TOO_SHORT"
    assert error["patrol_area"] is None
