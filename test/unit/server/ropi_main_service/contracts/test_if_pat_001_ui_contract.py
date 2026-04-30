from unittest.mock import patch

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_PATROL_CREATE_TASK,
)
from ui.utils.network.service_clients import DeliveryRequestRemoteService


def test_create_patrol_task_forwards_if_pat_001_request_fields():
    request_payload = {
        "request_id": "req_patrol_001",
        "caregiver_id": 1,
        "patrol_area_id": "patrol_ward_night_01",
        "priority": "NORMAL",
        "idempotency_key": "idem_patrol_001",
    }

    with patch(
        "ui.utils.network.service_clients.send_request",
        return_value={
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": 2001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky3",
                "patrol_area_id": "patrol_ward_night_01",
                "patrol_area_name": "야간 병동 순찰",
                "patrol_area_revision": 7,
            },
        },
    ) as send_request:
        response = DeliveryRequestRemoteService().create_patrol_task(
            **request_payload
        )

    send_request.assert_called_once_with(
        MESSAGE_CODE_PATROL_CREATE_TASK,
        request_payload,
    )
    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 2001
    assert response["assigned_robot_id"] == "pinky3"
    assert response["patrol_area_revision"] == 7
