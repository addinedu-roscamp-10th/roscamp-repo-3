import unittest
from unittest.mock import patch

from server.ropi_main_service.tcp_protocol import MESSAGE_CODE_DELIVERY_CREATE_TASK
from ui.utils.network.service_clients import DeliveryRequestRemoteService


class IFDEL001UIContractTest(unittest.TestCase):
    def test_create_delivery_task_forwards_if_del_001_request_fields(self):
        request_payload = {
            "request_id": "req_001",
            "caregiver_id": "cg_001",
            "item_id": "supply_001",
            "quantity": 2,
            "destination_id": "room_301",
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
                    "task_id": "task_delivery_001",
                    "task_status": "WAITING_DISPATCH",
                    "assigned_pinky_id": None,
                },
            },
        ) as send_request:
            response = DeliveryRequestRemoteService().create_delivery_task(**request_payload)

        send_request.assert_called_once_with(
            MESSAGE_CODE_DELIVERY_CREATE_TASK,
            request_payload,
        )
        self.assertEqual(response["result_code"], "ACCEPTED")
        self.assertEqual(response["task_id"], "task_delivery_001")


if __name__ == "__main__":
    unittest.main()
