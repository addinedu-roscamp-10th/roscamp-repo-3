def test_build_goal_pose_update_payload_uses_if_loc_004_fields():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        build_goal_pose_update_payload,
    )

    payload = build_goal_pose_update_payload(
        selected_goal_pose={"updated_at": "2026-05-02T03:00:00Z"},
        goal_pose_id=" delivery_room_301 ",
        zone_id="room_301",
        purpose=" DESTINATION ",
        pose_x="1.72",
        pose_y=0.03,
        pose_yaw="1.57",
        frame_id=" map ",
        is_enabled=True,
    )

    assert payload == {
        "goal_pose_id": "delivery_room_301",
        "expected_updated_at": "2026-05-02T03:00:00Z",
        "zone_id": "room_301",
        "purpose": "DESTINATION",
        "pose_x": 1.72,
        "pose_y": 0.03,
        "pose_yaw": 1.57,
        "frame_id": "map",
        "is_enabled": True,
    }


def test_build_goal_pose_save_payload_omits_stale_check_for_create():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        build_goal_pose_save_payload,
    )

    payload = build_goal_pose_save_payload(
        mode="create",
        selected_goal_pose={"updated_at": "2026-05-02T03:00:00Z"},
        goal_pose_id=" delivery_room_302 ",
        zone_id=None,
        purpose=" destination ",
        pose_x="2.1",
        pose_y="0.12",
        pose_yaw="0",
        frame_id=" map ",
        is_enabled=True,
    )

    assert payload == {
        "goal_pose_id": "delivery_room_302",
        "zone_id": None,
        "purpose": "destination",
        "pose_x": 2.1,
        "pose_y": 0.12,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "is_enabled": True,
    }
    assert "expected_updated_at" not in payload


def test_goal_pose_save_response_requires_goal_pose_dict():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        goal_pose_from_save_response,
    )

    goal_pose = {
        "goal_pose_id": "delivery_room_301",
        "pose_x": 1.72,
        "pose_y": 0.03,
        "pose_yaw": 1.57,
    }

    assert goal_pose_from_save_response({"goal_pose": goal_pose}) == goal_pose
    assert goal_pose_from_save_response({"goal_pose": None}) is None
    assert goal_pose_from_save_response("invalid") is None


def test_goal_pose_world_point_from_payload_for_bounds_check():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        goal_pose_world_point_from_payload,
    )

    assert goal_pose_world_point_from_payload(
        {
            "pose_x": "1.72",
            "pose_y": 0.03,
        }
    ) == {"x": 1.72, "y": 0.03}
    assert goal_pose_world_point_from_payload({"pose_x": "bad", "pose_y": 0.03}) is None
