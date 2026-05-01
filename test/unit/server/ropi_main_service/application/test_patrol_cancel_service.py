import asyncio

from server.ropi_main_service.application.patrol_cancel import PatrolCancelService


class FakeRepository:
    def __init__(self):
        self.recorded = []

    async def async_get_patrol_task_cancel_target(self, task_id):
        return {
            "result_code": "ACCEPTED",
            "task_id": task_id,
            "task_status": "RUNNING",
            "assigned_robot_id": "pinky3",
        }

    async def async_record_patrol_task_cancel_result(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        cancel_response,
    ):
        self.recorded.append(
            {
                "task_id": task_id,
                "caregiver_id": caregiver_id,
                "reason": reason,
                "cancel_response": cancel_response,
            }
        )
        return {
            "result_code": "CANCEL_REQUESTED",
            "task_id": task_id,
            "task_type": "PATROL",
            "task_status": "CANCEL_REQUESTED",
            "assigned_robot_id": "pinky3",
            "cancel_requested": True,
        }


class FakeCommandClient:
    def __init__(self):
        self.calls = []

    async def async_send_command(self, command, payload, timeout):
        self.calls.append((command, payload, timeout))
        return {
            "result_code": "CANCEL_REQUESTED",
            "task_id": payload["task_id"],
            "cancel_requested": True,
        }


class FakeRecorder:
    def __init__(self):
        self.specs = []

    async def async_record(self, spec, callback):
        self.specs.append(spec)
        return await callback()


def test_patrol_cancel_service_records_cancel_action_and_result():
    repository = FakeRepository()
    command_client = FakeCommandClient()
    recorder = FakeRecorder()
    service = PatrolCancelService(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        timeout_sec=3.0,
    )

    response = asyncio.run(
        service.async_cancel_patrol_task(
            task_id="2001",
            caregiver_id=7,
            reason="operator_cancel",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == [
        ("cancel_action", {"task_id": "2001"}, 3.0)
    ]
    assert recorder.specs[0].task_id == "2001"
    assert recorder.specs[0].target_robot_id == "pinky3"
    assert repository.recorded[0]["caregiver_id"] == 7
    assert repository.recorded[0]["reason"] == "operator_cancel"
    assert repository.recorded[0]["cancel_response"]["cancel_requested"] is True
