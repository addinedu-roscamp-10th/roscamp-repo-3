def test_replace_row_by_key_updates_existing_row_and_index():
    from ui.utils.pages.caregiver.coordinate_zone_settings_edit_state import (
        replace_row_by_key,
    )

    replacement = replace_row_by_key(
        [
            {"goal_pose_id": "pickup_supply", "pose_x": 0.1},
            {"goal_pose_id": "delivery_room_301", "pose_x": 1.7},
        ],
        {"goal_pose_id": "delivery_room_301", "pose_x": 1.9},
        "goal_pose_id",
    )

    assert replacement.rows == [
        {"goal_pose_id": "pickup_supply", "pose_x": 0.1},
        {"goal_pose_id": "delivery_room_301", "pose_x": 1.9},
    ]
    assert replacement.selected_index == 1


def test_replace_row_by_key_appends_missing_row():
    from ui.utils.pages.caregiver.coordinate_zone_settings_edit_state import (
        replace_row_by_key,
    )

    replacement = replace_row_by_key(
        [{"zone_id": "room_301"}],
        {"zone_id": "caregiver_room"},
        "zone_id",
    )

    assert replacement.rows == [
        {"zone_id": "room_301"},
        {"zone_id": "caregiver_room"},
    ]
    assert replacement.selected_index == 1


def test_edit_save_state_requires_matching_edit_type_dirty_map_and_idle_worker():
    from ui.utils.pages.caregiver.coordinate_zone_settings_edit_state import (
        edit_discard_enabled,
        edit_save_enabled,
    )

    assert (
        edit_save_enabled(
            selected_edit_type="goal_pose",
            expected_edit_type="goal_pose",
            dirty=True,
            map_loaded=True,
            save_thread=None,
        )
        is True
    )
    assert (
        edit_save_enabled(
            selected_edit_type="goal_pose",
            expected_edit_type="goal_pose",
            dirty=True,
            map_loaded=True,
            save_thread=object(),
        )
        is False
    )
    assert (
        edit_save_enabled(
            selected_edit_type="patrol_area",
            expected_edit_type="goal_pose",
            dirty=True,
            map_loaded=True,
            save_thread=None,
        )
        is False
    )
    assert (
        edit_discard_enabled(
            selected_edit_type="goal_pose",
            expected_edit_type="goal_pose",
            dirty=True,
        )
        is True
    )
    assert (
        edit_discard_enabled(
            selected_edit_type="goal_pose",
            expected_edit_type="goal_pose",
            dirty=False,
        )
        is False
    )
