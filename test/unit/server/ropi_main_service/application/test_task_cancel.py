import asyncio

from server.ropi_main_service.application.task_request import TaskRequestService


class FakeTaskCancelRepository:
    def __init__(self, task_type):
        self.task_type = task_type
        self.target_calls = []

    async def async_get_task_cancel_target(self, task_id):
        self.target_calls.append(task_id)
        return {
            "result_code": "ACCEPTED",
            "task_id": task_id,
            "task_type": self.task_type,
            "task_status": "RUNNING",
            "assigned_robot_id": "pinky3",
        }


class FakeDeliveryCancelService:
    def __init__(self):
        self.calls = []

    async def async_cancel_delivery_task(self, task_id, action_name=None):
        self.calls.append((task_id, action_name))
        return {
            "result_code": "CANCEL_REQUESTED",
            "task_id": task_id,
            "task_type": "DELIVERY",
            "task_status": "CANCEL_REQUESTED",
        }


class FakePatrolCancelService:
    def __init__(self):
        self.calls = []

    async def async_cancel_patrol_task(
        self,
        *,
        task_id,
        caregiver_id,
        reason,
        action_name=None,
    ):
        self.calls.append(
            {
                "task_id": task_id,
                "caregiver_id": caregiver_id,
                "reason": reason,
                "action_name": action_name,
            }
        )
        return {
            "result_code": "CANCEL_REQUESTED",
            "task_id": task_id,
            "task_type": "PATROL",
            "task_status": "CANCEL_REQUESTED",
        }


def test_cancel_task_dispatches_delivery_to_existing_cancel_service():
    repository = FakeTaskCancelRepository("DELIVERY")
    delivery_cancel_service = FakeDeliveryCancelService()
    patrol_cancel_service = FakePatrolCancelService()
    service = TaskRequestService(
        repository=repository,
        delivery_cancel_service=delivery_cancel_service,
        patrol_cancel_service=patrol_cancel_service,
    )

    response = asyncio.run(
        service.async_cancel_task(
            task_id="1001",
            caregiver_id=7,
            reason="operator_cancel",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert repository.target_calls == ["1001"]
    assert delivery_cancel_service.calls == [("1001", None)]
    assert patrol_cancel_service.calls == []


def test_cancel_task_dispatches_patrol_to_patrol_cancel_service():
    repository = FakeTaskCancelRepository("PATROL")
    delivery_cancel_service = FakeDeliveryCancelService()
    patrol_cancel_service = FakePatrolCancelService()
    service = TaskRequestService(
        repository=repository,
        delivery_cancel_service=delivery_cancel_service,
        patrol_cancel_service=patrol_cancel_service,
    )

    response = asyncio.run(
        service.async_cancel_task(
            task_id="2001",
            caregiver_id=7,
            reason="operator_cancel",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert delivery_cancel_service.calls == []
    assert patrol_cancel_service.calls == [
        {
            "task_id": "2001",
            "caregiver_id": 7,
            "reason": "operator_cancel",
            "action_name": None,
        }
    ]
