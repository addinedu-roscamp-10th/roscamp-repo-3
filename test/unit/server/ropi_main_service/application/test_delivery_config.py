import math

import pytest

from server.ropi_main_service.application.delivery_config import (
    get_delivery_navigation_config,
    get_delivery_runtime_config,
)


RUNTIME_CONFIG_ENV_NAMES = (
    "ROPI_DELIVERY_PINKY_ID",
    "ROPI_DELIVERY_PICKUP_ARM_ID",
    "ROPI_DELIVERY_DESTINATION_ARM_ID",
    "ROPI_DELIVERY_ROBOT_SLOT_ID",
    "ROPI_DELIVERY_NAVIGATION_TIMEOUT_SEC",
)


def _clear_runtime_config_env(monkeypatch):
    for env_name in RUNTIME_CONFIG_ENV_NAMES:
        monkeypatch.delenv(env_name, raising=False)


def test_delivery_runtime_config_uses_phase1_defaults(monkeypatch):
    _clear_runtime_config_env(monkeypatch)

    config = get_delivery_runtime_config()

    assert config.pinky_id == "pinky2"
    assert config.pickup_arm_id == "arm1"
    assert config.destination_arm_id == "arm2"
    assert config.arm_ids == ("arm1", "arm2")
    assert config.robot_slot_id == "robot_slot_a1"
    assert config.navigation_timeout_sec == 120.0


def test_delivery_runtime_config_reads_robot_values_from_env(monkeypatch):
    monkeypatch.setenv("ROPI_DELIVERY_PINKY_ID", "pinky9")
    monkeypatch.setenv("ROPI_DELIVERY_PICKUP_ARM_ID", "arm7")
    monkeypatch.setenv("ROPI_DELIVERY_DESTINATION_ARM_ID", "arm8")
    monkeypatch.setenv("ROPI_DELIVERY_ROBOT_SLOT_ID", "slot_b2")
    monkeypatch.setenv("ROPI_DELIVERY_NAVIGATION_TIMEOUT_SEC", "45.5")

    config = get_delivery_runtime_config()

    assert config.pinky_id == "pinky9"
    assert config.pickup_arm_id == "arm7"
    assert config.destination_arm_id == "arm8"
    assert config.arm_ids == ("arm7", "arm8")
    assert config.robot_slot_id == "slot_b2"
    assert config.navigation_timeout_sec == 45.5


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


def test_delivery_navigation_config_reads_key_value_pose_string_envs(monkeypatch):
    monkeypatch.delenv("ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON", raising=False)
    monkeypatch.delenv("ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON", raising=False)
    monkeypatch.delenv("ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON", raising=False)
    monkeypatch.setenv(
        "ROPI_DELIVERY_PICKUP_GOAL_POSE",
        "x=0.1665755137108074,y=-0.4496830900440016,yaw_deg=90.0",
    )
    monkeypatch.setenv(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES",
        "room2=x=1.6946025435218914,y=0.0043433854992070454,yaw_deg=0.0",
    )
    monkeypatch.setenv(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE",
        "x=0.8577123880386353,y=0.25597259402275085,yaw_deg=0.0",
    )

    config = get_delivery_navigation_config()

    pickup_goal_pose = config["pickup_goal_pose"]
    assert pickup_goal_pose["pose"]["position"]["x"] == pytest.approx(0.1665755137108074)
    assert pickup_goal_pose["pose"]["position"]["y"] == pytest.approx(-0.4496830900440016)
    assert pickup_goal_pose["pose"]["orientation"]["z"] == pytest.approx(math.sqrt(0.5))
    assert pickup_goal_pose["pose"]["orientation"]["w"] == pytest.approx(math.sqrt(0.5))

    destination_goal_pose = config["destination_goal_poses"]["room2"]
    assert destination_goal_pose["pose"]["position"]["x"] == pytest.approx(1.6946025435218914)
    assert destination_goal_pose["pose"]["position"]["y"] == pytest.approx(0.0043433854992070454)
    assert destination_goal_pose["pose"]["orientation"]["z"] == pytest.approx(0.0)
    assert destination_goal_pose["pose"]["orientation"]["w"] == pytest.approx(1.0)

    return_to_dock_goal_pose = config["return_to_dock_goal_pose"]
    assert return_to_dock_goal_pose["pose"]["position"]["x"] == pytest.approx(0.8577123880386353)
    assert return_to_dock_goal_pose["pose"]["position"]["y"] == pytest.approx(0.25597259402275085)
    assert return_to_dock_goal_pose["pose"]["orientation"]["z"] == pytest.approx(0.0)
    assert return_to_dock_goal_pose["pose"]["orientation"]["w"] == pytest.approx(1.0)
