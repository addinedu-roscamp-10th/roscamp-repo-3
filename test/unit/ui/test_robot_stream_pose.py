import math

import pytest

from ui.utils.pages.caregiver.robot_stream_pose import (
    normalize_stream_pose,
    robot_id_from_action_name,
)


def test_normalize_stream_pose_accepts_flat_pose_with_fallbacks():
    assert normalize_stream_pose(
        {"x": "2.5", "y": 1.5},
        fallback_map_id="map_0504",
        fallback_frame_id="odom",
        updated_at="2026-05-11T20:15:54+00:00",
    ) == {
        "map_id": "map_0504",
        "frame_id": "odom",
        "x": 2.5,
        "y": 1.5,
        "yaw": 0.0,
        "updated_at": "2026-05-11T20:15:54+00:00",
    }


def test_normalize_stream_pose_accepts_pose_stamped_shape():
    pose = normalize_stream_pose(
        {
            "header": {"frame_id": "map"},
            "pose": {
                "position": {"x": 0.5, "y": -0.2, "z": 0.0},
                "orientation": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": math.sin(math.pi / 4.0),
                    "w": math.cos(math.pi / 4.0),
                },
            },
        },
        fallback_map_id="map_patrol",
    )

    assert pose["map_id"] == "map_patrol"
    assert pose["frame_id"] == "map"
    assert pose["x"] == 0.5
    assert pose["y"] == -0.2
    assert pose["yaw"] == pytest.approx(math.pi / 2.0)
    assert pose["updated_at"] is None


def test_robot_id_from_action_name_extracts_control_and_arm_ids():
    assert (
        robot_id_from_action_name("/ropi/control/pinky2/navigate_to_goal")
        == "pinky2"
    )
    assert robot_id_from_action_name("/ropi/arm/arm1/execute_manipulation") == "arm1"
    assert robot_id_from_action_name("/unexpected/name") is None
