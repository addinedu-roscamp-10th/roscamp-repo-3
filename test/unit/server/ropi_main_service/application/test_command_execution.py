import asyncio

import pytest

from server.ropi_main_service.application.command_execution import (
    CommandExecutionRecorder,
    CommandExecutionSpec,
)


class FakeCommandExecutionRepository:
    def __init__(self):
        self.calls = []

    def start_command_execution(self, **kwargs):
        self.calls.append(("start", kwargs))
        return 501

    async def async_start_command_execution(self, **kwargs):
        self.calls.append(("async_start", kwargs))
        return 502

    def finish_command_execution(self, **kwargs):
        self.calls.append(("finish", kwargs))

    async def async_finish_command_execution(self, **kwargs):
        self.calls.append(("async_finish", kwargs))


def build_spec():
    return CommandExecutionSpec(
        task_id="101",
        transport="ROS_ACTION",
        command_type="NAVIGATE_TO_GOAL",
        command_phase="DELIVERY_PICKUP",
        target_component="ros_service",
        target_robot_id="pinky2",
        target_endpoint="/ropi/control/pinky2/navigate_to_goal",
        request_payload={"goal": {"task_id": "101"}},
    )


def test_record_starts_and_finishes_successful_command():
    repository = FakeCommandExecutionRepository()
    recorder = CommandExecutionRecorder(repository=repository)

    response = recorder.record(
        build_spec(),
        lambda: {
            "accepted": True,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        },
    )

    assert response["result_code"] == "SUCCESS"
    assert repository.calls[0][0] == "start"
    assert repository.calls[0][1]["command_type"] == "NAVIGATE_TO_GOAL"
    assert repository.calls[1] == (
        "finish",
        {
            "command_execution_id": 501,
            "accepted": True,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
            "response_payload": response,
        },
    )


def test_record_finishes_failed_command_before_reraising():
    repository = FakeCommandExecutionRepository()
    recorder = CommandExecutionRecorder(repository=repository)

    def raise_error():
        raise RuntimeError("ros service unavailable")

    with pytest.raises(RuntimeError, match="ros service unavailable"):
        recorder.record(build_spec(), raise_error)

    assert repository.calls[1] == (
        "finish",
        {
            "command_execution_id": 501,
            "accepted": False,
            "result_code": "FAILED",
            "result_message": "ros service unavailable",
            "response_payload": {
                "error_type": "RuntimeError",
                "error": "ros service unavailable",
            },
        },
    )


def test_async_record_starts_and_finishes_successful_command():
    repository = FakeCommandExecutionRepository()
    recorder = CommandExecutionRecorder(repository=repository)

    async def scenario():
        async def run_command():
            return {
                "accepted": True,
                "result_code": "SUCCESS",
                "result_message": "navigation done",
            }

        return await recorder.async_record(build_spec(), run_command)

    response = asyncio.run(scenario())

    assert response["result_code"] == "SUCCESS"
    assert repository.calls[0][0] == "async_start"
    assert repository.calls[1][0] == "async_finish"
    assert repository.calls[1][1]["command_execution_id"] == 502
