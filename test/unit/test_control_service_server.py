from unittest.mock import patch

import pytest

from server.ropi_main_service.transport import tcp_server
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    TCPFrame,
)


class FakeTaskRequestService:
    def get_product_names(self):
        return ["기저귀", "물티슈"]


@pytest.fixture
def control_service_server():
    return tcp_server.ControlServiceServer()


def test_heartbeat_with_db_check_puts_db_status_under_payload(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=1,
        payload={"check_db": True},
    )

    with patch("server.ropi_main_service.persistence.connection.test_connection", return_value=(True, {"ok": 1})):
        response = control_service_server.dispatch_frame(request)

    assert response.is_response is True
    assert response.message_code == MESSAGE_CODE_HEARTBEAT
    assert response.sequence_no == 1
    assert response.payload["message"] == "메인 서버 연결 정상"
    assert response.payload["db"] == {"ok": True, "detail": {"ok": 1}}


def test_heartbeat_with_ros_check_puts_ros_status_under_payload(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=4,
        payload={"check_ros": True},
    )

    with patch(
        "server.ropi_main_service.transport.tcp_server.RosRuntimeReadinessService"
    ) as readiness_service_cls:
        readiness_service_cls.return_value.get_status.return_value = {
            "ready": True,
            "checks": [
                {"name": "pinky2.navigate_to_goal", "ready": True},
                {"name": "arm1.execute_manipulation", "ready": True},
                {"name": "arm2.execute_manipulation", "ready": True},
            ],
        }
        response = control_service_server.dispatch_frame(request)

    assert response.is_response is True
    assert response.payload["ros"] == {
        "ok": True,
        "detail": {
            "ready": True,
            "checks": [
                {"name": "pinky2.navigate_to_goal", "ready": True},
                {"name": "arm1.execute_manipulation", "ready": True},
                {"name": "arm2.execute_manipulation", "ready": True},
            ],
        },
    }


def test_rpc_dispatch_routes_to_registered_service(control_service_server):
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
        response = control_service_server.dispatch_frame(payload)

    assert response.payload == ["기저귀", "물티슈"]
    assert response.message_code == MESSAGE_CODE_INTERNAL_RPC
    assert response.sequence_no == 2
    assert response.is_response is True


def test_rpc_dispatch_rejects_unknown_service(control_service_server):
    response = control_service_server.dispatch_frame(
        TCPFrame(
            message_code=MESSAGE_CODE_INTERNAL_RPC,
            sequence_no=3,
            payload={"service": "missing", "method": "noop", "kwargs": {}},
        )
    )

    assert response.is_error is True
    assert response.payload["error_code"] == "UNKNOWN_SERVICE"
    assert "missing" in response.payload["error"]
