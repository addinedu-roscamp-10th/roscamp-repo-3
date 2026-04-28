from unittest.mock import patch

from server.ropi_main_service.transport.tcp_protocol import MESSAGE_CODE_DELIVERY_CREATE_TASK
from ui.utils.network.service_clients import DeliveryRequestRemoteService


def test_create_delivery_task_forwards_if_del_001_request_fields():
    request_payload = {
        "request_id": "req_001",
        "caregiver_id": "1",
        "item_id": "1",
        "quantity": 2,
        "destination_id": "delivery_room_301",
        "priority": "NORMAL",
        "notes": "Medication after meals",
        "idempotency_key": "idem_delivery_001",
    }

    with patch(
        "ui.utils.network.service_clients.send_request",
        return_value={
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": 101,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
            },
        },
    ) as send_request:
        response = DeliveryRequestRemoteService().create_delivery_task(**request_payload)

    send_request.assert_called_once_with(
        MESSAGE_CODE_DELIVERY_CREATE_TASK,
        request_payload,
    )
    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 101
    assert response["assigned_robot_id"] == "pinky2"
    assert "assigned_pinky_id" not in response
