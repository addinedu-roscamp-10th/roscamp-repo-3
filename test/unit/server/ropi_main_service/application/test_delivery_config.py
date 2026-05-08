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
    "ROPI_DELIVERY_PICKUP_ARM_ROBOT_ID",
    "ROPI_DELIVERY_DESTINATION_ARM_ROBOT_ID",
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
    assert config.pickup_arm_robot_id == "jetcobot1"
    assert config.destination_arm_robot_id == "jetcobot2"
    assert config.robot_slot_id == "robot_slot_a1"
    assert config.navigation_timeout_sec == 120.0


def test_delivery_runtime_config_reads_robot_values_from_env(monkeypatch):
    monkeypatch.setenv("ROPI_DELIVERY_PINKY_ID", "pinky9")
    monkeypatch.setenv("ROPI_DELIVERY_PICKUP_ARM_ID", "arm7")
    monkeypatch.setenv("ROPI_DELIVERY_DESTINATION_ARM_ID", "arm8")
    monkeypatch.setenv("ROPI_DELIVERY_PICKUP_ARM_ROBOT_ID", "jetcobot7")
    monkeypatch.setenv("ROPI_DELIVERY_DESTINATION_ARM_ROBOT_ID", "jetcobot8")
    monkeypatch.setenv("ROPI_DELIVERY_ROBOT_SLOT_ID", "slot_b2")
    monkeypatch.setenv("ROPI_DELIVERY_NAVIGATION_TIMEOUT_SEC", "45.5")

    config = get_delivery_runtime_config()

    assert config.pinky_id == "pinky9"
    assert config.pickup_arm_id == "arm7"
    assert config.destination_arm_id == "arm8"
    assert config.arm_ids == ("arm7", "arm8")
    assert config.pickup_arm_robot_id == "jetcobot7"
    assert config.destination_arm_robot_id == "jetcobot8"
    assert config.robot_slot_id == "slot_b2"
    assert config.navigation_timeout_sec == 45.5


def test_delivery_navigation_config_reads_return_to_dock_goal_pose_from_env(monkeypatch):
    monkeypatch.setenv("ROPI_DELIVERY_GOAL_POSE_SOURCE", "env")
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
    monkeypatch.setenv("ROPI_DELIVERY_GOAL_POSE_SOURCE", "env")
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
    monkeypatch.setenv("ROPI_DELIVERY_GOAL_POSE_SOURCE", "env")
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
    monkeypatch.setenv("ROPI_DELIVERY_GOAL_POSE_SOURCE", "env")
    monkeypatch.delenv("ROPI_DELIVERY_PICKUP_GOAL_POSE_JSON", raising=False)
    monkeypatch.delenv("ROPI_DELIVERY_DESTINATION_GOAL_POSES_JSON", raising=False)
    monkeypatch.delenv("ROPI_RETURN_TO_DOCK_GOAL_POSE_JSON", raising=False)
    monkeypatch.setenv(
        "ROPI_DELIVERY_PICKUP_GOAL_POSE",
        "x=0.64,y=-0.44,yaw_deg=180.0",
    )
    monkeypatch.setenv(
        "ROPI_DELIVERY_DESTINATION_GOAL_POSES",
        "room2=x=1.6838363409042358,y=-0.4915957748889923,yaw_deg=90.0",
    )
    monkeypatch.setenv(
        "ROPI_RETURN_TO_DOCK_GOAL_POSE",
        "x=-0.009538442827761173,y=-0.006931785028427839,yaw_deg=0.0",
    )

    config = get_delivery_navigation_config()

    pickup_goal_pose = config["pickup_goal_pose"]
    assert pickup_goal_pose["pose"]["position"]["x"] == pytest.approx(0.64)
    assert pickup_goal_pose["pose"]["position"]["y"] == pytest.approx(-0.44)
    assert pickup_goal_pose["pose"]["orientation"]["z"] == pytest.approx(1.0)
    assert pickup_goal_pose["pose"]["orientation"]["w"] == pytest.approx(0.0)

    destination_goal_pose = config["destination_goal_poses"]["room2"]
    assert destination_goal_pose["pose"]["position"]["x"] == pytest.approx(1.6838363409042358)
    assert destination_goal_pose["pose"]["position"]["y"] == pytest.approx(-0.4915957748889923)
    assert destination_goal_pose["pose"]["orientation"]["z"] == pytest.approx(math.sqrt(0.5))
    assert destination_goal_pose["pose"]["orientation"]["w"] == pytest.approx(math.sqrt(0.5))

    return_to_dock_goal_pose = config["return_to_dock_goal_pose"]
    assert return_to_dock_goal_pose["pose"]["position"]["x"] == pytest.approx(-0.009538442827761173)
    assert return_to_dock_goal_pose["pose"]["position"]["y"] == pytest.approx(-0.006931785028427839)
    assert return_to_dock_goal_pose["pose"]["orientation"]["z"] == pytest.approx(0.0)
    assert return_to_dock_goal_pose["pose"]["orientation"]["w"] == pytest.approx(1.0)


def test_delivery_navigation_config_defaults_to_db_goal_pose_rows(monkeypatch):
    monkeypatch.delenv("ROPI_DELIVERY_GOAL_POSE_SOURCE", raising=False)

    class FakeGoalPoseRepository:
        def get_enabled_goal_poses(self):
            return [
                {
                    "goal_pose_id": "pickup_supply",
                    "purpose": "PICKUP",
                    "pose_x": 0.64,
                    "pose_y": -0.44,
                    "pose_yaw": 3.141592653589793,
                    "frame_id": "map",
                },
                {
                    "goal_pose_id": "delivery_room_301",
                    "purpose": "DESTINATION",
                    "pose_x": 1.6838363409042358,
                    "pose_y": -0.4915957748889923,
                    "pose_yaw": 1.5707963267948966,
                    "frame_id": "map",
                },
                {
                    "goal_pose_id": "dock_home",
                    "purpose": "DOCK",
                    "pose_x": -0.009538442827761173,
                    "pose_y": -0.006931785028427839,
                    "pose_yaw": 0.0,
                    "frame_id": "map",
                },
            ]

    config = get_delivery_navigation_config(repository=FakeGoalPoseRepository())

    assert config["pickup_goal_pose"]["pose"]["position"]["x"] == pytest.approx(
        0.64
    )
    assert config["pickup_goal_pose"]["pose"]["orientation"]["z"] == pytest.approx(
        1.0
    )
    assert list(config["destination_goal_poses"]) == ["delivery_room_301"]
    assert config["destination_goal_poses"]["delivery_room_301"]["pose"]["position"] == {
        "x": 1.6838363409042358,
        "y": -0.4915957748889923,
        "z": 0.0,
    }
    assert config["return_to_dock_goal_pose"]["pose"]["position"]["x"] == pytest.approx(
        -0.009538442827761173
    )
    assert config["return_to_dock_goal_pose"]["pose"]["position"]["y"] == pytest.approx(
        -0.006931785028427839
    )
    assert config["return_to_dock_goal_pose"]["pose"]["orientation"]["z"] == pytest.approx(
        0.0
    )
    assert config["return_to_dock_goal_pose"]["pose"]["orientation"]["w"] == pytest.approx(
        1.0
    )
