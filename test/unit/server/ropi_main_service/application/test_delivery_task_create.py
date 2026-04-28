import asyncio

from server.ropi_main_service.application.delivery_task_create import DeliveryTaskCreateService


class FakeDeliveryTaskRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_delivery_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)

    async def async_create_delivery_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)


class FakeDeliveryWorkflowStarter:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def build_request_payload():
    return {
        "request_id": "req_001",
        "caregiver_id": "1",
        "item_id": "1",
        "quantity": 2,
        "destination_id": "delivery_room_301",
        "priority": "NORMAL",
        "notes": "Medication after meals",
        "idempotency_key": "idem_delivery_001",
    }


def build_accepted_response():
    return {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": 101,
        "task_status": "WAITING_DISPATCH",
        "assigned_robot_id": "pinky2",
    }


def test_delivery_task_create_service_creates_task_and_starts_workflow():
    repository = FakeDeliveryTaskRepository(response=build_accepted_response())
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryTaskCreateService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [build_request_payload()]
    assert workflow_starter.calls == [
        {
            "task_id": "101",
            "item_id": "1",
            "quantity": 2,
            "destination_id": "delivery_room_301",
        }
    ]


def test_delivery_task_create_service_rejects_invalid_request_without_repository_call():
    repository = FakeDeliveryTaskRepository(response=build_accepted_response())
    service = DeliveryTaskCreateService(repository=repository)

    response = service.create_delivery_task(
        **{
            **build_request_payload(),
            "item_id": "",
        }
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "ITEM_ID_INVALID"
    assert repository.calls == []


def test_async_delivery_task_create_service_awaits_async_precheck():
    precheck_calls = []
    repository = FakeDeliveryTaskRepository(response=build_accepted_response())

    async def async_precheck(**kwargs):
        precheck_calls.append(kwargs)
        return None

    service = DeliveryTaskCreateService(
        repository=repository,
        async_delivery_request_precheck=async_precheck,
    )

    response = asyncio.run(service.async_create_delivery_task(**build_request_payload()))

    assert response["result_code"] == "ACCEPTED"
    assert precheck_calls == [build_request_payload()]
    assert repository.calls == [build_request_payload()]
