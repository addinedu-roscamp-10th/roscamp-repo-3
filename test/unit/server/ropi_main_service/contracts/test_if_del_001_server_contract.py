from unittest.mock import patch

from server.ropi_main_service.application.task_request import DeliveryRequestService


def test_create_delivery_task_rejects_empty_item_id():
    with patch(
        "server.ropi_main_service.application.task_request.DeliveryRequestRepository"
    ) as repository_cls:
        service = DeliveryRequestService()

        response = service.create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="",
            quantity=2,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes="Medication after meals",
            idempotency_key="idem_delivery_001",
        )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "ITEM_ID_INVALID"
    assert "assigned_robot_id" in response
    assert "assigned_pinky_id" not in response
    repository_cls.return_value.create_delivery_task.assert_not_called()


def test_create_delivery_task_returns_if_del_001_success_payload():
    with patch(
        "server.ropi_main_service.application.task_request.DeliveryRequestRepository"
    ) as repository_cls:
        repository_cls.return_value.create_delivery_task.return_value = {
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": 101,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky2",
        }
        service = DeliveryRequestService()

        response = service.create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=2,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes="Medication after meals",
            idempotency_key="idem_delivery_001",
        )

    repository_cls.return_value.create_delivery_task.assert_called_once_with(
        request_id="req_001",
        caregiver_id="1",
        item_id="1",
        quantity=2,
        destination_id="delivery_room_301",
        priority="NORMAL",
        notes="Medication after meals",
        idempotency_key="idem_delivery_001",
    )
    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 101
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["assigned_robot_id"] == "pinky2"
    assert "assigned_pinky_id" not in response


def test_create_delivery_task_returns_precheck_failure_before_repository_call():
    with patch(
        "server.ropi_main_service.application.task_request.DeliveryRequestRepository"
    ) as repository_cls:
        service = DeliveryRequestService(
            delivery_request_precheck=lambda **_: {
                "result_code": "REJECTED",
                "result_message": "ROS service가 준비되지 않았습니다.",
                "reason_code": "ROS_SERVICE_UNAVAILABLE",
            }
        )

        response = service.create_delivery_task(
            request_id="req_001",
            caregiver_id="1",
            item_id="1",
            quantity=2,
            destination_id="delivery_room_301",
            priority="NORMAL",
            notes="Medication after meals",
            idempotency_key="idem_delivery_001",
        )

    assert response == {
        "result_code": "REJECTED",
        "result_message": "ROS service가 준비되지 않았습니다.",
        "reason_code": "ROS_SERVICE_UNAVAILABLE",
    }
    repository_cls.return_value.create_delivery_task.assert_not_called()
