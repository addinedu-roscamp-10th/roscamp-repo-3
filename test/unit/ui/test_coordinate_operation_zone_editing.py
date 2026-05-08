def test_build_operation_zone_create_payload_uses_if_loc_002_fields():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        build_operation_zone_save_payload,
    )

    payload = build_operation_zone_save_payload(
        mode="create",
        selected_operation_zone={"revision": 9},
        map_profile={"map_id": "map_test11_0423"},
        zone_id=" caregiver_room ",
        zone_name=" Staff Station ",
        zone_type=" STAFF_STATION ",
        is_enabled=True,
    )

    assert payload == {
        "zone_id": "caregiver_room",
        "zone_name": "Staff Station",
        "zone_type": "STAFF_STATION",
        "map_id": "map_test11_0423",
        "is_enabled": True,
    }


def test_build_operation_zone_update_payload_uses_if_loc_003_fields():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        build_operation_zone_save_payload,
    )

    payload = build_operation_zone_save_payload(
        mode="edit",
        selected_operation_zone={"revision": "2"},
        map_profile={"map_id": "map_test11_0423"},
        zone_id=" room_301 ",
        zone_name=" Room 301 ",
        zone_type=" ROOM ",
        is_enabled=False,
    )

    assert payload == {
        "zone_id": "room_301",
        "expected_revision": 2,
        "zone_name": "Room 301",
        "zone_type": "ROOM",
        "is_enabled": False,
    }


def test_build_operation_zone_boundary_save_payload_uses_if_loc_007_fields():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        build_operation_zone_boundary_save_payload,
    )

    payload = build_operation_zone_boundary_save_payload(
        selected_operation_zone={"zone_id": "room_301", "revision": "2"},
        boundary_vertices=[
            {"x": "0.0", "y": "0.2"},
            {"x": 1.2, "y": 0.2},
            {"x": 1.2, "y": 1.1},
        ],
        frame_id=" map ",
    )

    assert payload == {
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


def test_operation_zone_save_response_requires_operation_zone_dict():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        operation_zone_from_save_response,
    )

    operation_zone = {
        "zone_id": "room_301",
        "zone_name": "Room 301",
        "revision": 3,
    }

    assert operation_zone_from_save_response(
        {"operation_zone": operation_zone}
    ) == operation_zone
    assert operation_zone_from_save_response({"operation_zone": None}) is None
    assert operation_zone_from_save_response("invalid") is None


def test_operation_zone_editor_controller_tracks_selection_and_dirty_state():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        OperationZoneEditorController,
    )

    controller = OperationZoneEditorController()
    selected = controller.select(
        1,
        [
            {"zone_id": "room_301", "zone_name": "Room 301"},
            {"zone_id": "caregiver_room", "zone_name": "Staff Station"},
        ],
    )

    assert selected == {"zone_id": "caregiver_room", "zone_name": "Staff Station"}
    assert controller.selected_row == selected
    assert controller.selected_index == 1
    assert controller.mode == "edit"
    assert controller.dirty is False

    assert controller.mark_dirty(selected_edit_type="goal_pose") is False
    assert controller.dirty is False
    assert controller.mark_dirty(selected_edit_type="operation_zone") is True
    assert controller.dirty is True

    controller.syncing_form = True
    assert controller.mark_dirty(selected_edit_type="operation_zone") is False


def test_operation_zone_editor_controller_builds_create_draft_and_applies_saved_row():
    from ui.utils.pages.caregiver.coordinate_operation_zone_editing import (
        OperationZoneEditorController,
    )

    controller = OperationZoneEditorController()

    draft = controller.start_create()

    assert draft == {
        "zone_id": "",
        "zone_name": "",
        "zone_type": "ROOM",
        "is_enabled": True,
    }
    assert controller.selected_row is None
    assert controller.selected_index is None
    assert controller.mode == "create"
    assert controller.dirty is False

    controller.apply_saved_row(
        {
            "zone_id": "caregiver_room",
            "zone_name": "Staff Station",
        }
    )

    assert controller.selected_row == {
        "zone_id": "caregiver_room",
        "zone_name": "Staff Station",
    }
    assert controller.mode == "edit"
    assert controller.dirty is False
