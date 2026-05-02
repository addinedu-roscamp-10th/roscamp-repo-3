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
