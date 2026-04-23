import unittest
from unittest.mock import patch

from server.ropi_main_service import tcp_server
from server.ropi_main_service.tcp_protocol import (
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    TCPFrame,
)


class FakeTaskRequestService:
    def get_product_names(self):
        return ["기저귀", "물티슈"]


class ControlServiceServerContractTest(unittest.TestCase):
    def setUp(self):
        self.server = tcp_server.ControlServiceServer()

    def test_heartbeat_with_db_check_puts_db_status_under_payload(self):
        request = TCPFrame(
            message_code=MESSAGE_CODE_HEARTBEAT,
            sequence_no=1,
            payload={"check_db": True},
        )

        with patch("server.ropi_db.connection.test_connection", return_value=(True, {"ok": 1})):
            response = self.server.dispatch_frame(request)

        self.assertTrue(response.is_response)
        self.assertEqual(response.message_code, MESSAGE_CODE_HEARTBEAT)
        self.assertEqual(response.sequence_no, 1)
        self.assertEqual(response.payload["message"], "메인 서버 연결 정상")
        self.assertEqual(response.payload["db"], {"ok": True, "detail": {"ok": 1}})

    def test_rpc_dispatch_routes_to_registered_service(self):
        payload = TCPFrame(
            message_code=MESSAGE_CODE_INTERNAL_RPC,
            sequence_no=2,
            payload={
                "service": "task_request",
                "method": "get_product_names",
                "kwargs": {},
            },
        )

        with patch.dict(tcp_server.SERVICE_REGISTRY, {"task_request": FakeTaskRequestService}):
            response = self.server.dispatch_frame(payload)

        self.assertEqual(
            response.payload,
            ["기저귀", "물티슈"],
        )
        self.assertEqual(response.message_code, MESSAGE_CODE_INTERNAL_RPC)
        self.assertEqual(response.sequence_no, 2)
        self.assertTrue(response.is_response)

    def test_rpc_dispatch_rejects_unknown_service(self):
        response = self.server.dispatch_frame(
            TCPFrame(
                message_code=MESSAGE_CODE_INTERNAL_RPC,
                sequence_no=3,
                payload={"service": "missing", "method": "noop", "kwargs": {}},
            )
        )

        self.assertTrue(response.is_error)
        self.assertEqual(response.payload["error_code"], "UNKNOWN_SERVICE")
        self.assertIn("missing", response.payload["error"])


if __name__ == "__main__":
    unittest.main()
