import asyncio

import pytest

from server.ropi_main_service.application.nav2_navigation import (
    Nav2PoseNavigationService,
)


class FakeRosCommandClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "result_code": "SUCCESS",
            "result_message": "Nav2 goal reached.",
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


class FakeAsyncRosCommandClient(FakeRosCommandClient):
    def send_command(self, command, payload, timeout=None):
        raise AssertionError("async_navigate should use async_send_command")

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


def build_goal_pose():
    return {
        "header": {"frame_id": "map"},
        "pose": {
            "position": {"x": 1.25, "y": -0.5, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def build_normalized_goal_pose():
    goal_pose = build_goal_pose()
    goal_pose["header"]["stamp"] = {"sec": 0, "nanosec": 0}
    return goal_pose


def test_nav2_navigation_sends_namespaced_navigate_to_pose_command():
    command_client = FakeRosCommandClient()
    recorder = RecordingCommandExecutionRecorder()
    service = Nav2PoseNavigationService(
        command_client=command_client,
        command_execution_recorder=recorder,
    )

    response = service.navigate(
        task_id=3001,
        robot_id="pinky1",
        nav_phase="DRIVE_WAYPOINT_1",
        goal_pose=build_goal_pose(),
        timeout_sec=120,
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls == [
        {
            "command": "navigate_to_pose",
            "payload": {
                "robot_id": "pinky1",
                "goal": {
                    "task_id": "3001",
                    "nav_phase": "DRIVE_WAYPOINT_1",
                    "pose": build_normalized_goal_pose(),
                    "behavior_tree": "",
                    "timeout_sec": 120,
                },
            },
            "timeout": 125.0,
        }
    ]

    spec = recorder.specs[0]
    assert spec.command_type == "NAV2_NAVIGATE_TO_POSE"
    assert spec.command_phase == "DRIVE_WAYPOINT_1"
    assert spec.target_robot_id == "pinky1"
    assert spec.target_endpoint == "/pinky1/navigate_to_pose"


def test_nav2_navigation_accepts_pinky_id_alias_for_drive_runtime_compatibility():
    command_client = FakeRosCommandClient()
    service = Nav2PoseNavigationService(
        command_client=command_client,
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    service.navigate(
        task_id=3001,
        pinky_id="pinky3",
        nav_phase="DRIVE_WAYPOINT_2",
        goal_pose=build_goal_pose(),
        timeout_sec=90,
    )

    assert command_client.calls[0]["payload"]["robot_id"] == "pinky3"
    assert command_client.calls[0]["payload"]["goal"]["timeout_sec"] == 90


def test_nav2_navigation_uses_async_ros_service_command_client():
    command_client = FakeAsyncRosCommandClient()
    recorder = RecordingCommandExecutionRecorder()
    service = Nav2PoseNavigationService(
        command_client=command_client,
        command_execution_recorder=recorder,
    )

    response = asyncio.run(
        service.async_navigate(
            task_id=3001,
            robot_id="pinky1",
            nav_phase="DRIVE_WAYPOINT_1",
            goal_pose=build_goal_pose(),
            timeout_sec=120,
        )
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls[0]["command"] == "navigate_to_pose"
    assert recorder.specs[0].target_endpoint == "/pinky1/navigate_to_pose"


def test_nav2_navigation_rejects_absolute_robot_namespace():
    service = Nav2PoseNavigationService(
        command_client=FakeRosCommandClient(),
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    with pytest.raises(ValueError, match="robot_id"):
        service.navigate(
            task_id=3001,
            robot_id="/pinky1",
            nav_phase="DRIVE_WAYPOINT_1",
            goal_pose=build_goal_pose(),
            timeout_sec=120,
        )
