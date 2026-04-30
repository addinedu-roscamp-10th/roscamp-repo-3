import asyncio

from server.ropi_main_service.application.fall_response_command import (
    CLEAR_AND_RESTART,
    START_FALL_ALERT,
    FallResponseCommandService,
)


class FakeCommandClient:
    def __init__(self, response=None):
        self.response = response or {"accepted": True, "message": ""}
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        self.calls.append((command, payload, timeout))
        return self.response

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append((command, payload, timeout))
        return self.response


class FakeRecorder:
    def __init__(self):
        self.specs = []

    def record(self, spec, command_runner):
        self.specs.append(spec)
        return command_runner()

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


def test_send_clear_and_restart_uses_pat_002_payload_and_command_spec():
    command_client = FakeCommandClient(response={"accepted": True, "message": "restart"})
    recorder = FakeRecorder()
    service = FallResponseCommandService(
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=3.0,
    )

    response = service.send_clear_and_restart(
        task_id="2001",
        robot_id="pinky3",
    )

    assert response == {"accepted": True, "message": "restart"}
    assert command_client.calls == [
        (
            "fall_response_control",
            {"task_id": "2001", "command_type": CLEAR_AND_RESTART},
            3.0,
        )
    ]
    assert recorder.specs[0].command_type == "FALL_RESPONSE_CONTROL"
    assert recorder.specs[0].command_phase == "PATROL_RESUME"
    assert recorder.specs[0].target_robot_id == "pinky3"
    assert recorder.specs[0].target_endpoint == "/ropi/control/pinky3/fall_response_control"


def test_async_send_start_fall_alert_keeps_pinky_id_in_payload():
    command_client = FakeCommandClient(response={"accepted": True})
    recorder = FakeRecorder()
    service = FallResponseCommandService(
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=5.0,
    )

    response = asyncio.run(
        service.async_send_start_fall_alert(
            task_id=2001,
            robot_id="pinky3",
        )
    )

    assert response == {"accepted": True}
    assert command_client.calls == [
        (
            "fall_response_control",
            {
                "pinky_id": "pinky3",
                "task_id": "2001",
                "command_type": START_FALL_ALERT,
            },
            5.0,
        )
    ]
    assert recorder.specs[0].command_phase == "FALL_ALERT_START"


def test_fall_response_command_acceptance_helper():
    assert FallResponseCommandService.is_accepted({"accepted": True}) is True
    assert FallResponseCommandService.is_accepted({"accepted": False}) is False
    assert FallResponseCommandService.is_accepted(None) is False
