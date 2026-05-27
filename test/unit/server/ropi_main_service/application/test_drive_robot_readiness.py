from server.ropi_main_service.application.drive_robot_readiness import (
    DriveRobotReadinessService,
)


class FakeCommandClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def send_command(self, command, payload, *, timeout):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def test_drive_robot_readiness_requires_nav2_lifecycle_checks_when_reported():
    response = {
        "ready": False,
        "checks": [
            {
                "name": "pinky1.navigate_to_pose",
                "action_name": "/pinky1/navigate_to_pose",
                "ready": True,
            },
            {
                "name": "pinky1.nav2_lifecycle.bt_navigator",
                "node_name": "/pinky1/bt_navigator",
                "ready": False,
                "state_label": "inactive",
            },
        ],
    }
    client = FakeCommandClient(response)
    service = DriveRobotReadinessService(command_client=client)

    assert service.is_robot_ready("pinky1") is False
    assert client.calls[0]["payload"]["include_nav2_navigation"] is True
    assert client.calls[0]["payload"]["include_nav2_lifecycle"] is True


def test_drive_robot_readiness_accepts_ready_action_and_active_lifecycle():
    response = {
        "ready": True,
        "checks": [
            {
                "name": "pinky3.navigate_to_pose",
                "action_name": "/pinky3/navigate_to_pose",
                "ready": True,
            },
            {
                "name": "pinky3.nav2_lifecycle.bt_navigator",
                "node_name": "/pinky3/bt_navigator",
                "ready": True,
                "state_label": "active",
            },
        ],
    }
    service = DriveRobotReadinessService(command_client=FakeCommandClient(response))

    assert service.is_robot_ready("pinky3") is True
