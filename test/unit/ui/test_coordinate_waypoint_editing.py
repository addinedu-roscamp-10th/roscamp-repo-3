def test_patrol_waypoint_table_rows_format_pose_values():
    from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
        patrol_waypoint_table_rows,
    )

    assert patrol_waypoint_table_rows(
        [
            {"x": 0, "y": 0.2, "yaw": 0},
            {"x": 1.23456, "y": "2.5", "yaw": None},
        ]
    ) == [
        ["1", "0.0000", "0.2000", "0.0000"],
        ["2", "1.2346", "2.5000", "0.0000"],
    ]


def test_replace_selected_patrol_waypoint_uses_form_values():
    from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
        replace_selected_patrol_waypoint,
    )

    edit = replace_selected_patrol_waypoint(
        [
            {"x": 0.0, "y": 0.2, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 1.57},
        ],
        1,
        x=2.0,
        y=3.0,
        yaw=0.5,
    )

    assert edit is not None
    assert edit.selected_index == 1
    assert edit.waypoints == [
        {"x": 0.0, "y": 0.2, "yaw": 0.0},
        {"x": 2.0, "y": 3.0, "yaw": 0.5},
    ]


def test_move_selected_patrol_waypoint_to_world_preserves_yaw():
    from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
        move_selected_patrol_waypoint_to_world,
    )

    edit = move_selected_patrol_waypoint_to_world(
        [
            {"x": 0.0, "y": 0.2, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 1.57},
        ],
        1,
        {"x": 0.4, "y": 0.6},
    )

    assert edit is not None
    assert edit.selected_index == 1
    assert edit.waypoints[1] == {"x": 0.4, "y": 0.6, "yaw": 1.57}


def test_patrol_waypoint_delete_move_and_button_state():
    from ui.utils.pages.caregiver.coordinate_waypoint_editing import (
        delete_selected_patrol_waypoint,
        move_selected_patrol_waypoint,
        patrol_waypoint_buttons_state,
    )

    moved = move_selected_patrol_waypoint(
        [
            {"x": 0.0, "y": 0.2, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 1.57},
        ],
        1,
        -1,
    )
    assert moved is not None
    assert moved.selected_index == 0
    assert moved.waypoints[0] == {"x": 1.0, "y": 1.0, "yaw": 1.57}
    assert patrol_waypoint_buttons_state(moved.waypoints, moved.selected_index) == {
        "delete": True,
        "up": False,
        "down": True,
    }

    deleted = delete_selected_patrol_waypoint(moved.waypoints, moved.selected_index)
    assert deleted is not None
    assert deleted.selected_index == 0
    assert deleted.waypoints == [{"x": 0.0, "y": 0.2, "yaw": 0.0}]
