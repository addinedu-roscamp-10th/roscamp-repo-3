def test_build_patrol_area_path_save_payload_uses_if_loc_005_fields():
    from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
        build_patrol_area_path_save_payload,
    )

    payload = build_patrol_area_path_save_payload(
        selected_patrol_area={"revision": "7"},
        patrol_area_id=" patrol_ward_night_01 ",
        frame_id=" map ",
        waypoints=[
            {"x": "0.1666", "y": "-0.4497", "yaw": "1.5708"},
            {"x": 1.6946, "y": 0.0043, "yaw": None},
            "invalid",
        ],
    )

    assert payload == {
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


def test_patrol_area_path_save_response_requires_patrol_area_dict():
    from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
        patrol_area_from_path_save_response,
    )

    patrol_area = {
        "patrol_area_id": "patrol_ward_night_01",
        "revision": 8,
        "path_json": {"header": {"frame_id": "map"}, "poses": []},
    }

    assert patrol_area_from_path_save_response({"patrol_area": patrol_area}) == patrol_area
    assert patrol_area_from_path_save_response({"patrol_area": None}) is None
    assert patrol_area_from_path_save_response("invalid") is None


def test_patrol_path_poses_from_save_payload_for_validation():
    from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
        patrol_path_poses_from_save_payload,
    )

    poses = [
        {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
        {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
    ]

    assert patrol_path_poses_from_save_payload(
        {"path_json": {"header": {"frame_id": "map"}, "poses": poses}}
    ) == poses
    assert patrol_path_poses_from_save_payload({"path_json": {}}) == []
    assert patrol_path_poses_from_save_payload("invalid") == []


def test_patrol_area_editor_controller_tracks_selection_and_dirty_state():
    from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
        PatrolAreaEditorController,
    )

    controller = PatrolAreaEditorController(selected_waypoint_index=2)
    selected = controller.select(
        1,
        [
            {"patrol_area_id": "patrol_ward_day_01", "revision": 3},
            {"patrol_area_id": "patrol_ward_night_01", "revision": 7},
        ],
    )

    assert selected == {"patrol_area_id": "patrol_ward_night_01", "revision": 7}
    assert controller.selected_row == selected
    assert controller.selected_index == 1
    assert controller.selected_waypoint_index is None
    assert controller.mode == "edit"
    assert controller.dirty is False

    assert controller.mark_dirty(selected_edit_type="goal_pose") is False
    assert controller.dirty is False
    assert controller.mark_dirty(selected_edit_type="patrol_area") is True
    assert controller.dirty is True

    controller.syncing_area_form = True
    assert controller.mark_dirty(selected_edit_type="patrol_area") is False
    controller.syncing_area_form = False
    controller.syncing_waypoint_form = True
    assert controller.mark_dirty(selected_edit_type="patrol_area") is False


def test_patrol_area_editor_controller_builds_create_draft_and_applies_saved_row():
    from ui.utils.pages.caregiver.coordinate_patrol_area_editing import (
        PatrolAreaEditorController,
    )

    controller = PatrolAreaEditorController(
        selected_row={"patrol_area_id": "old"},
        selected_index=4,
        selected_waypoint_index=1,
        mode="edit",
        dirty=True,
    )

    draft = controller.start_create(frame_id="map")

    assert draft == {
        "patrol_area_id": "",
        "patrol_area_name": "",
        "revision": 0,
        "path_json": {
            "header": {"frame_id": "map"},
            "poses": [],
        },
        "is_enabled": True,
    }
    assert controller.selected_row is None
    assert controller.selected_index is None
    assert controller.selected_waypoint_index is None
    assert controller.mode == "create"
    assert controller.dirty is False

    controller.apply_saved_row(
        {
            "patrol_area_id": "patrol_ward_night_01",
            "revision": 8,
        }
    )

    assert controller.selected_row == {
        "patrol_area_id": "patrol_ward_night_01",
        "revision": 8,
    }
    assert controller.mode == "edit"
    assert controller.dirty is False
