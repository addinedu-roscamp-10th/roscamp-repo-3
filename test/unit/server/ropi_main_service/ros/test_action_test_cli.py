import io
import json
import tomllib
from pathlib import Path

from server.ropi_main_service.ros import action_test_cli


class FakeCommandClient:
    def __init__(self, response=None):
        self.response = response or {"result_code": "SUCCESS", "result_message": "ok"}
        self.calls = []

    def send_command(self, command, payload=None, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def test_action_test_cli_nav_sends_single_navigation_action_without_full_readiness():
    command_client = FakeCommandClient()
    stdout = io.StringIO()

    exit_code = action_test_cli.run(
        [
            "nav",
            "--pinky-id",
            "pinky9",
            "--task-id",
            "manual_nav_001",
            "--nav-phase",
            "DELIVERY_PICKUP",
            "--pose",
            "1.0,2.0,0.0",
            "--timeout-sec",
            "12",
        ],
        command_client=command_client,
        stdout=stdout,
    )

    assert exit_code == 0
    assert command_client.calls == [
        {
            "command": "navigate_to_goal",
            "payload": {
                "pinky_id": "pinky9",
                "goal": {
                    "task_id": "manual_nav_001",
                    "nav_phase": "DELIVERY_PICKUP",
                    "goal_pose": {
                        "header": {
                            "stamp": {"sec": 0, "nanosec": 0},
                            "frame_id": "map",
                        },
                        "pose": {
                            "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        },
                    },
                    "timeout_sec": 12,
                },
            },
            "timeout": 14.0,
        }
    ]
    assert json.loads(stdout.getvalue()) == {"result_code": "SUCCESS", "result_message": "ok"}


def test_action_test_cli_arm_sends_single_manipulation_action_without_pinky():
    command_client = FakeCommandClient()
    stdout = io.StringIO()

    exit_code = action_test_cli.run(
        [
            "arm",
            "--arm-id",
            "arm1",
            "--task-id",
            "manual_arm_001",
            "--transfer-direction",
            "TO_ROBOT",
            "--item-id",
            "1",
            "--quantity",
            "2",
            "--robot-slot-id",
            "robot_slot_a1",
        ],
        command_client=command_client,
        stdout=stdout,
    )

    assert exit_code == 0
    assert command_client.calls == [
        {
            "command": "execute_manipulation",
            "payload": {
                "arm_id": "arm1",
                "goal": {
                    "task_id": "manual_arm_001",
                    "transfer_direction": "TO_ROBOT",
                    "item_id": "1",
                    "quantity": 2,
                    "robot_slot_id": "robot_slot_a1",
                },
            },
            "timeout": 30.0,
        }
    ]
    assert json.loads(stdout.getvalue()) == {"result_code": "SUCCESS", "result_message": "ok"}


def test_action_test_cli_status_can_check_arm_without_navigation_readiness():
    command_client = FakeCommandClient(response={"ready": True, "checks": []})
    stdout = io.StringIO()

    exit_code = action_test_cli.run(
        [
            "status",
            "--arm-id",
            "arm2",
        ],
        command_client=command_client,
        stdout=stdout,
    )

    assert exit_code == 0
    assert command_client.calls == [
        {
            "command": "get_runtime_status",
            "payload": {
                "arm_ids": ["arm2"],
                "include_navigation": False,
            },
            "timeout": 2.0,
        }
    ]
    assert json.loads(stdout.getvalue()) == {"ready": True, "checks": []}


def test_action_test_cli_is_registered_as_project_script():
    pyproject = tomllib.loads((Path(__file__).parents[5] / "pyproject.toml").read_text())

    assert (
        pyproject["project"]["scripts"]["ropi-ros-action-test"]
        == "server.ropi_main_service.ros.action_test_cli:main"
    )
