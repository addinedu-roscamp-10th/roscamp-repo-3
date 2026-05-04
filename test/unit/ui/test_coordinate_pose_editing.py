from ui.utils.pages.caregiver.coordinate_pose_editing import (
    coerce_point2d,
    coerce_pose2d,
    delete_index,
    move_index,
    nearest_pose_index,
    replace_index,
)


def test_coordinate_pose_editing_normalizes_points_and_poses():
    assert coerce_point2d({"x": "1.25", "y": 2, "yaw": 99}) == {
        "x": 1.25,
        "y": 2.0,
    }
    assert coerce_pose2d({"x": "1.25", "y": 2}, default_yaw=1.57) == {
        "x": 1.25,
        "y": 2.0,
        "yaw": 1.57,
    }
    assert coerce_pose2d({"x": "1.25", "y": 2, "yaw": "3.14"}) == {
        "x": 1.25,
        "y": 2.0,
        "yaw": 3.14,
    }
    assert coerce_point2d({"x": "bad", "y": 2}) is None
    assert coerce_pose2d(None) is None


def test_coordinate_pose_editing_selects_nearest_pose_inside_threshold():
    poses = [
        {"x": 0.0, "y": 0.0},
        {"x": "bad", "y": 0.0},
        {"x": 0.04, "y": 0.03},
        {"x": 0.5, "y": 0.5},
    ]

    assert nearest_pose_index(poses, {"x": 0.0, "y": 0.0}) == 0
    assert nearest_pose_index(poses, {"x": 0.05, "y": 0.04}) == 2
    assert nearest_pose_index(poses, {"x": 0.3, "y": 0.3}) is None
    assert nearest_pose_index(poses, {"x": "bad", "y": 0.0}) is None


def test_coordinate_pose_editing_replaces_deletes_and_moves_items_without_mutation():
    rows = [
        {"x": 0.0, "y": 0.0},
        {"x": 1.0, "y": 1.0},
        {"x": 2.0, "y": 2.0},
    ]

    replaced = replace_index(rows, 1, {"x": 9.0, "y": 9.0})
    assert replaced == [
        {"x": 0.0, "y": 0.0},
        {"x": 9.0, "y": 9.0},
        {"x": 2.0, "y": 2.0},
    ]
    assert rows[1] == {"x": 1.0, "y": 1.0}
    assert replace_index(rows, 99, {"x": 9.0, "y": 9.0}) is None

    deleted, next_index = delete_index(rows, 1)
    assert deleted == [{"x": 0.0, "y": 0.0}, {"x": 2.0, "y": 2.0}]
    assert next_index == 1
    deleted_last, next_index = delete_index(rows, 2)
    assert deleted_last == [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]
    assert next_index == 1
    assert delete_index(rows, 99) is None

    moved, next_index = move_index(rows, 1, -1)
    assert moved == [
        {"x": 1.0, "y": 1.0},
        {"x": 0.0, "y": 0.0},
        {"x": 2.0, "y": 2.0},
    ]
    assert next_index == 0
    assert move_index(rows, 0, -1) is None
