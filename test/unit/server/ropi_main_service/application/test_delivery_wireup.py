from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeDeliveryRequestRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_delivery_task(self, **kwargs):
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


def test_create_delivery_task_starts_delivery_workflow_after_acceptance():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": 101,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky2",
        }
    )
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryRequestService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "ACCEPTED"
    assert workflow_starter.calls == [
        {
            "task_id": "101",
            "item_id": "1",
            "quantity": 2,
            "destination_id": "delivery_room_301",
        }
    ]


def test_create_delivery_task_does_not_start_delivery_workflow_when_request_is_rejected():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
            "reason_code": "ITEM_NOT_FOUND",
            "task_id": None,
            "task_status": None,
            "assigned_robot_id": None,
        }
    )
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryRequestService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "REJECTED"
    assert workflow_starter.calls == []
