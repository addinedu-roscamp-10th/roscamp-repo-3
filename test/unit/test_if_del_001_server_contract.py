from unittest.mock import patch

from server.ropi_main_service.application.task_request import DeliveryRequestService


def test_create_delivery_task_rejects_empty_item_id():
    with patch(
        "server.ropi_main_service.application.task_request.DeliveryRequestRepository"
    ) as repository_cls:
        service = DeliveryRequestService()

        response = service.create_delivery_task(
            request_id="req_001",
            caregiver_id="cg_001",
            item_id="",
            quantity=2,
            destination_id="room_301",
            priority="NORMAL",
            notes="Medication after meals",
            idempotency_key="idem_delivery_001",
        )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "ITEM_ID_INVALID"
    repository_cls.return_value.create_delivery_task.assert_not_called()


def test_create_delivery_task_returns_if_del_001_success_payload():
    with patch(
        "server.ropi_main_service.application.task_request.DeliveryRequestRepository"
    ) as repository_cls:
        repository_cls.return_value.create_delivery_task.return_value = {
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": "task_delivery_001",
            "task_status": "WAITING_DISPATCH",
            "assigned_pinky_id": "pinky2",
        }
        service = DeliveryRequestService()

        response = service.create_delivery_task(
            request_id="req_001",
            caregiver_id="cg_001",
            item_id="supply_001",
            quantity=2,
            destination_id="room_301",
            priority="NORMAL",
            notes="Medication after meals",
            idempotency_key="idem_delivery_001",
        )

    repository_cls.return_value.create_delivery_task.assert_called_once_with(
        request_id="req_001",
        caregiver_id="cg_001",
        item_id="supply_001",
        quantity=2,
        destination_id="room_301",
        priority="NORMAL",
        notes="Medication after meals",
        idempotency_key="idem_delivery_001",
    )
    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == "task_delivery_001"
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["assigned_pinky_id"] == "pinky2"
