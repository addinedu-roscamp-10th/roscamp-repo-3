def test_coordinate_config_bundle_normalizes_only_dict_rows():
    from ui.utils.pages.caregiver.coordinate_zone_settings_bundle import (
        normalize_coordinate_config_bundle,
    )

    normalized = normalize_coordinate_config_bundle(
        {
            "map_profile": {"map_id": "map_test"},
            "operation_zones": [{"zone_id": "room_301"}, "invalid"],
            "goal_poses": [None, {"goal_pose_id": "delivery_room_301"}],
            "patrol_areas": [{"patrol_area_id": "patrol_ward_night_01"}, 42],
            "fms_waypoints": [{"waypoint_id": "corridor_01"}, ""],
            "fms_edges": [{"edge_id": "edge_corridor_01_02"}, None],
        }
    )

    assert normalized.source["map_profile"]["map_id"] == "map_test"
    assert normalized.map_profile == {"map_id": "map_test"}
    assert normalized.operation_zones == [{"zone_id": "room_301"}]
    assert normalized.goal_poses == [{"goal_pose_id": "delivery_room_301"}]
    assert normalized.patrol_areas == [{"patrol_area_id": "patrol_ward_night_01"}]
    assert normalized.fms_waypoints == [{"waypoint_id": "corridor_01"}]
    assert normalized.fms_edges == [{"edge_id": "edge_corridor_01_02"}]


def test_coordinate_config_bundle_handles_non_dict_payload():
    from ui.utils.pages.caregiver.coordinate_zone_settings_bundle import (
        normalize_coordinate_config_bundle,
    )

    normalized = normalize_coordinate_config_bundle(None)

    assert normalized.source == {}
    assert normalized.map_profile == {}
    assert normalized.operation_zones == []
    assert normalized.goal_poses == []
    assert normalized.patrol_areas == []
    assert normalized.fms_waypoints == []
    assert normalized.fms_edges == []
