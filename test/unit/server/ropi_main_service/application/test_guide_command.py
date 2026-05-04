from server.ropi_main_service.application.guide_command import GuideCommandService


class FakeCommandClient:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"accepted": False, "result_code": "REJECTED"}


class PassthroughCommandExecutionRecorder:
    def record(self, spec, command_runner):
        self.spec = spec
        return command_runner()


def test_guide_command_service_uses_socket_default_timeout_by_default():
    command_client = FakeCommandClient()
    recorder = PassthroughCommandExecutionRecorder()
    service = GuideCommandService(
        command_client=command_client,
        command_execution_recorder=recorder,
    )

    response = service.send(
        task_id=3001,
        pinky_id="pinky1",
        command_type="WAIT_TARGET_TRACKING",
    )

    assert response["result_code"] == "REJECTED"
    assert command_client.calls[0]["command"] == "guide_command"
    assert command_client.calls[0]["timeout"] is None
    assert recorder.spec.command_type == "GUIDE_COMMAND"
