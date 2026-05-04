import asyncio

import pytest

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.goal_pose_navigation import (
    GoalPoseNavigationService,
)


class FakeRosCommandClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        }

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.result


class FakeAsyncRosCommandClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        }

    def send_command(self, command, payload, timeout=None):
        raise AssertionError("async_navigate should not use sync send_command")

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.result


class RecordingCommandExecutionRecorder:
    def __init__(self):
        self.specs = []

    def record(self, spec, command_runner):
        self.specs.append(spec)
        return command_runner()

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


def build_goal_pose(*, frame_id="map"):
    return {
        "header": {
            "stamp": {
                "sec": 1776554120,
                "nanosec": 0,
            },
            "frame_id": frame_id,
        },
        "pose": {
            "position": {
                "x": 18.4,
                "y": 7.2,
                "z": 0.0,
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": 1.0,
                "w": 0.0,
            },
        },
    }


def test_navigate_delivery_destination_sends_if_com_007_command_to_ros_service():
    command_client = FakeRosCommandClient()
    command_execution_recorder = RecordingCommandExecutionRecorder()
    service = GoalPoseNavigationService(
        command_client=command_client,
        command_execution_recorder=command_execution_recorder,
    )

    response = service.navigate(
        task_id="task_delivery_001",
        nav_phase="DELIVERY_DESTINATION",
        goal_pose=build_goal_pose(),
        timeout_sec=120,
    )

    assert command_client.calls == [
        {
            "command": "navigate_to_goal",
            "payload": {
                "pinky_id": "pinky2",
                "goal": {
                    "task_id": "task_delivery_001",
                    "nav_phase": "DELIVERY_DESTINATION",
                    "goal_pose": build_goal_pose(),
                    "timeout_sec": 120,
                },
            },
            "timeout": 125.0,
        }
    ]
    assert response["result_code"] == "SUCCESS"
    assert response["result_message"] == "navigation done"
    assert len(command_execution_recorder.specs) == 1
    spec = command_execution_recorder.specs[0]
    assert spec.task_id == "task_delivery_001"
    assert spec.transport == "ROS_ACTION"
    assert spec.command_type == "NAVIGATE_TO_GOAL"
    assert spec.command_phase == "DELIVERY_DESTINATION"
    assert spec.target_robot_id == "pinky2"
    assert spec.target_endpoint == "/ropi/control/pinky2/navigate_to_goal"


def test_async_navigate_uses_async_ros_service_command_client():
    command_client = FakeAsyncRosCommandClient()
    command_execution_recorder = RecordingCommandExecutionRecorder()
    service = GoalPoseNavigationService(
        command_client=command_client,
        command_execution_recorder=command_execution_recorder,
    )

    response = asyncio.run(
        service.async_navigate(
            task_id="task_delivery_001",
            nav_phase="DELIVERY_DESTINATION",
            goal_pose=build_goal_pose(),
            timeout_sec=120,
        )
    )

    assert command_client.calls == [
        {
            "command": "navigate_to_goal",
            "payload": {
                "pinky_id": "pinky2",
                "goal": {
                    "task_id": "task_delivery_001",
                    "nav_phase": "DELIVERY_DESTINATION",
                    "goal_pose": build_goal_pose(),
                    "timeout_sec": 120,
                },
            },
            "timeout": 125.0,
        }
    ]
    assert response["result_code"] == "SUCCESS"
    assert command_execution_recorder.specs[0].command_type == "NAVIGATE_TO_GOAL"


def test_navigate_uses_runtime_config_pinky_id():
    command_client = FakeRosCommandClient()
    service = GoalPoseNavigationService(
        command_client=command_client,
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky9"),
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    service.navigate(
        task_id="task_delivery_001",
        nav_phase="DELIVERY_DESTINATION",
        goal_pose=build_goal_pose(),
        timeout_sec=120,
    )

    assert command_client.calls[0]["payload"]["pinky_id"] == "pinky9"


def test_navigate_guide_destination_can_override_pinky_id():
    command_client = FakeRosCommandClient()
    command_execution_recorder = RecordingCommandExecutionRecorder()
    service = GoalPoseNavigationService(
        command_client=command_client,
        command_execution_recorder=command_execution_recorder,
    )

    response = service.navigate(
        task_id="3001",
        pinky_id="pinky1",
        nav_phase="GUIDE_DESTINATION",
        goal_pose=build_goal_pose(),
        timeout_sec=120,
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls[0]["payload"]["pinky_id"] == "pinky1"
    assert command_client.calls[0]["payload"]["goal"]["nav_phase"] == "GUIDE_DESTINATION"
    assert command_execution_recorder.specs[0].target_robot_id == "pinky1"
    assert (
        command_execution_recorder.specs[0].target_endpoint
        == "/ropi/control/pinky1/navigate_to_goal"
    )


def test_navigate_defaults_goal_pose_frame_id_to_map():
    command_client = FakeRosCommandClient()
    service = GoalPoseNavigationService(
        command_client=command_client,
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    service.navigate(
        task_id="task_delivery_002",
        nav_phase="DELIVERY_PICKUP",
        goal_pose=build_goal_pose(frame_id=""),
        timeout_sec=90,
    )

    forwarded_goal_pose = command_client.calls[0]["payload"]["goal"]["goal_pose"]
    assert forwarded_goal_pose["header"]["frame_id"] == "map"


def test_navigate_accepts_return_to_dock_phase_in_phase1_runtime():
    command_client = FakeRosCommandClient()
    service = GoalPoseNavigationService(
        command_client=command_client,
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    response = service.navigate(
        task_id="task_delivery_003",
        nav_phase="RETURN_TO_DOCK",
        goal_pose=build_goal_pose(),
        timeout_sec=60,
    )

    assert command_client.calls[0]["payload"]["goal"]["nav_phase"] == "RETURN_TO_DOCK"
    assert response["result_code"] == "SUCCESS"


def test_navigate_rejects_unknown_phase_in_phase1():
    command_client = FakeRosCommandClient()
    service = GoalPoseNavigationService(command_client=command_client)

    with pytest.raises(ValueError, match="nav_phase"):
        service.navigate(
            task_id="task_delivery_003",
            nav_phase="GUIDE_UNKNOWN",
            goal_pose=build_goal_pose(),
            timeout_sec=60,
        )

    assert command_client.calls == []
