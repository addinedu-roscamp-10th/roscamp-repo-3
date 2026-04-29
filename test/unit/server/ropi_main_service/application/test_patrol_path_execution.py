import asyncio

import pytest

from server.ropi_main_service.application.patrol_config import PatrolRuntimeConfig
from server.ropi_main_service.application.patrol_path_execution import (
    PatrolPathExecutionService,
)


class FakeRosCommandClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "result_code": "SUCCESS",
            "result_message": "patrol done",
            "completed_waypoint_count": 2,
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
        raise AssertionError("async_execute should not use sync send_command")

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


def build_path_snapshot():
    return {
        "header": {
            "frame_id": "map",
        },
        "poses": [
            {
                "header": {},
                "pose": {
                    "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
            {
                "pose": {
                    "position": {"x": 3.0, "y": 4.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 1.0, "w": 0.0},
                },
            },
        ],
    }


def test_execute_patrol_path_sends_if_pat_003_command_to_ros_service():
    command_client = FakeRosCommandClient()
    recorder = RecordingCommandExecutionRecorder()
    service = PatrolPathExecutionService(
        command_client=command_client,
        runtime_config=PatrolRuntimeConfig(pinky_id="pinky3"),
        command_execution_recorder=recorder,
    )

    response = service.execute(
        task_id=2001,
        path_snapshot_json=build_path_snapshot(),
        timeout_sec=180,
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls == [
        {
            "command": "execute_patrol_path",
            "payload": {
                "pinky_id": "pinky3",
                "goal": {
                    "task_id": "2001",
                    "path": {
                        "header": {
                            "stamp": {"sec": 0, "nanosec": 0},
                            "frame_id": "map",
                        },
                        "poses": [
                            {
                                "header": {
                                    "stamp": {"sec": 0, "nanosec": 0},
                                    "frame_id": "map",
                                },
                                "pose": {
                                    "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                                    "orientation": {
                                        "x": 0.0,
                                        "y": 0.0,
                                        "z": 0.0,
                                        "w": 1.0,
                                    },
                                },
                            },
                            {
                                "header": {
                                    "stamp": {"sec": 0, "nanosec": 0},
                                    "frame_id": "map",
                                },
                                "pose": {
                                    "position": {"x": 3.0, "y": 4.0, "z": 0.0},
                                    "orientation": {
                                        "x": 0.0,
                                        "y": 0.0,
                                        "z": 1.0,
                                        "w": 0.0,
                                    },
                                },
                            },
                        ],
                    },
                    "timeout_sec": 180,
                },
            },
            "timeout": 185.0,
        }
    ]
    spec = recorder.specs[0]
    assert spec.command_type == "EXECUTE_PATROL_PATH"
    assert spec.command_phase == "PATROL_PATH_EXECUTION"
    assert spec.target_robot_id == "pinky3"
    assert spec.target_endpoint == "/ropi/control/pinky3/execute_patrol_path"


def test_async_execute_patrol_path_uses_async_ros_command_client():
    command_client = FakeAsyncRosCommandClient()
    service = PatrolPathExecutionService(
        command_client=command_client,
        runtime_config=PatrolRuntimeConfig(pinky_id="pinky3"),
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    response = asyncio.run(
        service.async_execute(
            task_id=2001,
            path_snapshot_json=build_path_snapshot(),
            timeout_sec=180,
        )
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls[0]["command"] == "execute_patrol_path"


def test_execute_patrol_path_rejects_empty_path_snapshot():
    service = PatrolPathExecutionService(
        command_client=FakeRosCommandClient(),
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    with pytest.raises(ValueError, match="waypoint"):
        service.execute(task_id=2001, path_snapshot_json={"poses": []}, timeout_sec=180)


def test_execute_patrol_path_converts_config_waypoints_to_pose_stamped_path():
    command_client = FakeRosCommandClient()
    service = PatrolPathExecutionService(
        command_client=command_client,
        runtime_config=PatrolRuntimeConfig(pinky_id="pinky3"),
        command_execution_recorder=RecordingCommandExecutionRecorder(),
    )

    service.execute(
        task_id=2001,
        path_snapshot_json={
            "header": {"frame_id": "map"},
            "poses": [
                {"x": 1.0, "y": 2.0, "yaw": 0.0},
                {"x": 3.0, "y": 4.0, "yaw": 3.141592653589793},
            ],
        },
        timeout_sec=180,
    )

    poses = command_client.calls[0]["payload"]["goal"]["path"]["poses"]
    assert poses[0]["pose"]["position"] == {"x": 1.0, "y": 2.0, "z": 0.0}
    assert poses[0]["pose"]["orientation"] == {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "w": 1.0,
    }
    assert poses[1]["pose"]["position"] == {"x": 3.0, "y": 4.0, "z": 0.0}
    assert round(poses[1]["pose"]["orientation"]["z"], 6) == 1.0
    assert round(poses[1]["pose"]["orientation"]["w"], 6) == 0.0
