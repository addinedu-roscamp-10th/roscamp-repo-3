from server.ropi_main_service.application.robot_localization import (
    RobotLocalizationService,
)


class FakeCommandClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "result_code": "ACCEPTED",
            "robot_id": "pinky1",
            "topic": "/pinky1/initialpose",
        }

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def test_robot_localization_service_sends_initial_pose_command():
    command_client = FakeCommandClient()
    service = RobotLocalizationService(command_client=command_client)

    response = service.set_initial_pose(
        robot_id="pinky1",
        frame_id="map",
        x=1.25,
        y=-0.5,
        yaw=1.57,
    )

    assert response["result_code"] == "ACCEPTED"
    assert command_client.calls == [
        {
            "command": "set_initial_pose",
            "payload": {
                "robot_id": "pinky1",
                "frame_id": "map",
                "x": 1.25,
                "y": -0.5,
                "yaw": 1.57,
                "covariance": None,
            },
            "timeout": 1.0,
        }
    ]


def test_robot_localization_service_rejects_absolute_robot_namespace():
    command_client = FakeCommandClient()
    service = RobotLocalizationService(command_client=command_client)

    response = service.set_initial_pose(
        robot_id="/pinky1",
        x=0,
        y=0,
        yaw=0,
    )

    assert response == {
        "result_code": "INVALID_REQUEST",
        "reason_code": "INVALID_ROBOT_ID",
        "result_message": "robot_id는 상대 robot namespace여야 합니다.",
    }
    assert command_client.calls == []
