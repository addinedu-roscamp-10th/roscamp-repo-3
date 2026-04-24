import math

import pytest

from server.ropi_main_service.navigation.config import get_delivery_navigation_config


def test_delivery_navigation_config_reads_return_to_dock_goal_pose_from_env(monkeypatch):
    monkeypatch.setenv(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        '{"header":{"frame_id":"map","stamp":{"sec":0,"nanosec":0}},"pose":{"position":{"x":0.5,"y":0.5,"z":0.0},"orientation":{"x":0.0,"y":0.0,"z":0.0,"w":1.0}}}',
    )

    config = get_delivery_navigation_config()

    assert config["return_to_dock_goal_pose"] == {
        "header": {
            "frame_id": "map",
            "stamp": {"sec": 0, "nanosec": 0},
        },
        "pose": {
            "position": {"x": 0.5, "y": 0.5, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def test_delivery_navigation_config_converts_simple_2d_pose_specs_to_pose_stamped(monkeypatch):
    monkeypatch.setenv(
        "ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON",
        '{"x":1.5,"y":2.5,"yaw":1.5707963267948966}',
    )
    monkeypatch.setenv(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON",
        '{"room2":{"x":18.4,"y":7.2,"yaw":0.0}}',
    )
    monkeypatch.setenv(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON",
        '{"x":0.5,"y":0.5,"yaw":3.141592653589793,"frame_id":"map"}',
    )

    config = get_delivery_navigation_config()

    pickup_goal_pose = config["pickup_goal_pose"]
    assert pickup_goal_pose["header"]["frame_id"] == "map"
    assert pickup_goal_pose["pose"]["position"] == {"x": 1.5, "y": 2.5, "z": 0.0}
    assert pickup_goal_pose["pose"]["orientation"]["x"] == 0.0
    assert pickup_goal_pose["pose"]["orientation"]["y"] == 0.0
    assert pickup_goal_pose["pose"]["orientation"]["z"] == pytest.approx(math.sqrt(0.5))
    assert pickup_goal_pose["pose"]["orientation"]["w"] == pytest.approx(math.sqrt(0.5))

    destination_goal_pose = config["destination_goal_poses"]["room2"]
    assert destination_goal_pose["pose"]["position"] == {"x": 18.4, "y": 7.2, "z": 0.0}
    assert destination_goal_pose["pose"]["orientation"] == {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "w": 1.0,
    }

    return_to_dock_goal_pose = config["return_to_dock_goal_pose"]
    assert return_to_dock_goal_pose["pose"]["position"] == {"x": 0.5, "y": 0.5, "z": 0.0}
    assert return_to_dock_goal_pose["pose"]["orientation"]["z"] == pytest.approx(1.0)
    assert return_to_dock_goal_pose["pose"]["orientation"]["w"] == pytest.approx(0.0)


def test_delivery_navigation_config_reads_plain_string_envs_without_json(monkeypatch):
    monkeypatch.delenv("ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON", raising=False)
    monkeypatch.delenv("ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON", raising=False)
    monkeypatch.delenv("ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON", raising=False)
    monkeypatch.setenv("ROPI_DELIVERY_PICKUP_GOAL_POSE", "1.5,2.5,1.5707963267948966")
    monkeypatch.setenv(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES",
        "room2=18.4,7.2,0.0;room3=12.0,5.0,3.141592653589793",
    )
    monkeypatch.setenv("ROPI_RETURN_TO_DOCK_GOAL_POSE", "0.5,0.5,3.141592653589793")

    config = get_delivery_navigation_config()

    assert config["pickup_goal_pose"]["pose"]["position"] == {"x": 1.5, "y": 2.5, "z": 0.0}
    assert config["pickup_goal_pose"]["pose"]["orientation"]["z"] == pytest.approx(math.sqrt(0.5))
    assert config["pickup_goal_pose"]["pose"]["orientation"]["w"] == pytest.approx(math.sqrt(0.5))
    assert config["destination_goal_poses"]["room2"]["pose"]["position"] == {
        "x": 18.4,
        "y": 7.2,
        "z": 0.0,
    }
    assert config["destination_goal_poses"]["room3"]["pose"]["orientation"]["z"] == pytest.approx(1.0)
    assert config["destination_goal_poses"]["room3"]["pose"]["orientation"]["w"] == pytest.approx(0.0)
    assert config["return_to_dock_goal_pose"]["pose"]["position"] == {"x": 0.5, "y": 0.5, "z": 0.0}
