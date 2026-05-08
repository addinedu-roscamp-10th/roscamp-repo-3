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


def test_goal_pose_editor_controller_tracks_selection_and_dirty_state():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        GoalPoseEditorController,
    )

    controller = GoalPoseEditorController()
    selected = controller.select(
        1,
        [
            {"goal_pose_id": "pickup_supply", "pose_x": 0.1},
            {"goal_pose_id": "delivery_room_301", "pose_x": 1.7},
        ],
    )

    assert selected == {"goal_pose_id": "delivery_room_301", "pose_x": 1.7}
    assert controller.selected_row == selected
    assert controller.selected_index == 1
    assert controller.mode == "edit"
    assert controller.dirty is False

    assert controller.mark_dirty(selected_edit_type="patrol_area") is False
    assert controller.dirty is False
    assert controller.mark_dirty(selected_edit_type="goal_pose") is True
    assert controller.dirty is True

    controller.syncing_form = True
    assert controller.mark_dirty(selected_edit_type="goal_pose") is False


def test_goal_pose_editor_controller_builds_create_draft_and_applies_saved_row():
    from ui.utils.pages.caregiver.coordinate_goal_pose_editing import (
        GoalPoseEditorController,
    )

    controller = GoalPoseEditorController()

    draft = controller.start_create(frame_id="map")

    assert draft == {
        "goal_pose_id": "",
        "zone_id": None,
        "purpose": "DESTINATION",
        "pose_x": 0.0,
        "pose_y": 0.0,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "is_enabled": True,
    }
    assert controller.selected_row is None
    assert controller.selected_index is None
    assert controller.mode == "create"
    assert controller.dirty is False

    controller.apply_saved_row(
        {
            "goal_pose_id": "delivery_room_302",
            "pose_x": 2.1,
        }
    )

    assert controller.selected_row == {
        "goal_pose_id": "delivery_room_302",
        "pose_x": 2.1,
    }
    assert controller.mode == "edit"
    assert controller.dirty is False
