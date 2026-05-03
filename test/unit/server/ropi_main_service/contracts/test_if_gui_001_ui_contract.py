from unittest.mock import patch

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_GUIDE_CREATE_TASK,
)
from ui.utils.network.service_clients import VisitGuideRemoteService


def test_create_guide_task_forwards_if_gui_001_request_fields():
    request_payload = {
        "request_id": "req_guide_001",
        "visitor_id": 1,
        "idempotency_key": "idem_guide_001",
    }

    with patch(
        "ui.utils.network.service_clients.send_request",
        return_value={
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": 3001,
                "task_status": "WAITING_DISPATCH",
                "resident_name": "김*수",
                "room_no": "301",
                "destination_id": "delivery_room_301",
            },
        },
    ) as send_request:
        response = VisitGuideRemoteService().create_guide_task(**request_payload)

    send_request.assert_called_once_with(
        MESSAGE_CODE_GUIDE_CREATE_TASK,
        request_payload,
    )
    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert response["destination_id"] == "delivery_room_301"
