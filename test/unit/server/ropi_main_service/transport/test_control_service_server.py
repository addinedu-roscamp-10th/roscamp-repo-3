import asyncio
import logging
import time
from unittest.mock import patch

import pytest

from server.ropi_main_service.transport import tcp_server
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
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


def test_async_heartbeat_with_db_check_uses_async_connection(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=14,
        payload={"check_db": True},
    )

    async def fake_async_test_connection():
        return True, {"ok": 1}

    async def scenario():
        with patch(
            "server.ropi_main_service.persistence.async_connection.async_test_connection",
            new=fake_async_test_connection,
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("DB heartbeat should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload["db"] == {"ok": True, "detail": {"ok": 1}}


def test_async_heartbeat_with_ros_check_uses_async_readiness_service(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=18,
        payload={"check_ros": True},
    )

    class FakeReadinessService:
        def get_status(self):
            raise AssertionError("async heartbeat should not use sync ROS readiness")

        async def async_get_status(self):
            return {
                "ready": True,
                "checks": [
                    {"name": "pinky2.navigate_to_goal", "ready": True},
                ],
            }

    async def scenario():
        with patch(
            "server.ropi_main_service.transport.tcp_server.RosRuntimeReadinessService",
            return_value=FakeReadinessService(),
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("ROS heartbeat should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload["ros"] == {
        "ok": True,
        "detail": {
            "ready": True,
            "checks": [
                {"name": "pinky2.navigate_to_goal", "ready": True},
            ],
        },
    }


def test_async_dispatch_login_uses_native_async_auth(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_LOGIN,
        sequence_no=12,
        payload={
            "login_id": "1",
            "password": "1234",
            "role": "caregiver",
        },
    )

    class FakeAuthService:
        async def async_authenticate(self, login_id, password, role):
            return True, {
                "user_id": login_id,
                "name": "최보호",
                "role": role,
            }

    async def scenario():
        with patch(
            "server.ropi_main_service.transport.tcp_server.AuthService",
            return_value=FakeAuthService(),
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("login should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload == {
        "user_id": "1",
        "name": "최보호",
        "role": "caregiver",
    }


def test_async_rpc_dispatch_awaits_async_service_method(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_INTERNAL_RPC,
        sequence_no=13,
        payload={
            "service": "caregiver",
            "method": "get_dashboard_bundle",
            "kwargs": {},
        },
    )

    class FakeAsyncCaregiverFacade:
        async def get_dashboard_bundle(self):
            return {"summary": {"available_robot_count": 2}}

    async def scenario():
        with patch.dict(
            tcp_server.SERVICE_REGISTRY,
            {"caregiver": FakeAsyncCaregiverFacade},
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("async RPC should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload == {"summary": {"available_robot_count": 2}}


def test_async_rpc_dispatch_prefers_async_method_alias(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_INTERNAL_RPC,
        sequence_no=16,
        payload={
            "service": "caregiver",
            "method": "get_dashboard_bundle",
            "kwargs": {},
        },
    )

    class FakeAsyncAliasCaregiverFacade:
        def get_dashboard_bundle(self):
            raise AssertionError("sync alias should not be called")

        async def async_get_dashboard_bundle(self):
            return {"summary": {"available_robot_count": 3}}

    async def scenario():
        with patch.dict(
            tcp_server.SERVICE_REGISTRY,
            {"caregiver": FakeAsyncAliasCaregiverFacade},
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload == {"summary": {"available_robot_count": 3}}


def test_caregiver_facade_attaches_action_feedback_to_running_tasks():
    class FakeCaregiverService:
        def get_dashboard_summary(self):
            return {"available_robot_count": 1, "waiting_job_count": 0, "running_job_count": 1}

        def get_robot_board_data(self):
            return []

        def get_flow_board_data(self):
            return {
                "READY": [],
                "ASSIGNED": [],
                "RUNNING": [
                    {
                        "task_id": 101,
                        "task_status": "RUNNING",
                        "description": "delivery task",
                    }
                ],
                "DONE": [],
            }

        def get_timeline_data(self):
            return []

    class FakeActionFeedbackService:
        def get_latest_feedback(self, *, task_id):
            return {
                "result_code": "FOUND",
                "task_id": str(task_id),
                "feedback": [
                    {
                        "client": "navigation",
                        "feedback_type": "NAVIGATION_FEEDBACK",
                        "payload": {
                            "nav_status": "MOVING",
                            "distance_remaining_m": 1.25,
                        },
                    }
                ],
            }

    with patch(
        "server.ropi_main_service.transport.tcp_server.CaregiverService",
        FakeCaregiverService,
    ), patch(
        "server.ropi_main_service.transport.tcp_server.RosActionFeedbackService",
        FakeActionFeedbackService,
    ):
        bundle = tcp_server.CaregiverFacade().get_dashboard_bundle()

    task = bundle["flow_data"]["RUNNING"][0]
    assert task["feedback"]["feedback_type"] == "NAVIGATION_FEEDBACK"
    assert task["feedback_summary"] == "MOVING / 남은 거리 1.25m"


def test_async_rpc_dispatch_offloads_sync_service_method(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_INTERNAL_RPC,
        sequence_no=15,
        payload={
            "service": "task_request",
            "method": "get_product_names",
            "kwargs": {},
        },
    )
    calls = []

    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    async def scenario():
        with patch.dict(
            tcp_server.SERVICE_REGISTRY,
            {"task_request": FakeTaskRequestService},
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            new=fake_to_thread,
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.payload == ["기저귀", "물티슈"]
    assert calls == ["get_product_names"]


def test_async_delivery_create_task_uses_native_async_service(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=17,
        payload={
            "request_id": "req_001",
            "caregiver_id": "1",
            "item_id": "1",
            "quantity": 1,
            "destination_id": "delivery_room_301",
            "priority": "NORMAL",
            "notes": "delivery test",
            "idempotency_key": "idem_001",
        },
    )

    class FakeAsyncDeliveryRequestService:
        async def async_create_delivery_task(self, **payload):
            return {
                "result_code": "ACCEPTED",
                "task_id": 101,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
            }

    async def scenario():
        with patch(
            "server.ropi_main_service.transport.tcp_server.build_delivery_request_service",
            return_value=FakeAsyncDeliveryRequestService(),
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("delivery create should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload["result_code"] == "ACCEPTED"
    assert response.payload["task_id"] == 101


def test_async_rpc_dispatch_routes_delivery_cancel_to_async_service(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_INTERNAL_RPC,
        sequence_no=19,
        payload={
            "service": "task_request",
            "method": "cancel_delivery_task",
            "kwargs": {
                "task_id": "101",
            },
        },
    )

    class FakeDeliveryRequestService:
        def cancel_delivery_task(self, **kwargs):
            raise AssertionError("delivery cancel RPC should prefer async method")

        async def async_cancel_delivery_task(self, **kwargs):
            return {
                "result_code": "CANCEL_REQUESTED",
                "task_id": kwargs["task_id"],
                "cancel_requested": True,
            }

    async def scenario():
        with patch.dict(
            tcp_server.SERVICE_REGISTRY,
            {"task_request": FakeDeliveryRequestService},
        ), patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.to_thread",
            side_effect=AssertionError("delivery cancel should not use thread fallback"),
        ):
            return await control_service_server.async_dispatch_frame(request)

    response = asyncio.run(scenario())

    assert response.is_response is True
    assert response.payload == {
        "result_code": "CANCEL_REQUESTED",
        "task_id": "101",
        "cancel_requested": True,
    }


def test_async_response_build_does_not_block_event_loop(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=11,
        payload={},
    )

    async def slow_dispatch(frame):
        await asyncio.sleep(0.2)
        return control_service_server._success_response(frame, {"ok": True})

    control_service_server.async_dispatch_frame = slow_dispatch

    async def scenario():
        started_at = time.monotonic()
        response_task = asyncio.create_task(control_service_server._build_response_frame(request))
        await asyncio.sleep(0.01)
        elapsed_before_dispatch_finishes = time.monotonic() - started_at
        response = await response_task
        return elapsed_before_dispatch_finishes, response

    elapsed, response = asyncio.run(scenario())

    assert elapsed < 0.1
    assert response.payload == {"ok": True}


def test_serve_forever_closes_background_writer_before_db_pool(control_service_server):
    events = []

    class FakeTcpServer:
        async def __aenter__(self):
            events.append("server_entered")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("server_exited")

        async def serve_forever(self):
            events.append("server_served")

    class FakeBackgroundDbWriter:
        async def stop(self):
            events.append("writer_stopped")

    async def fake_close_pool():
        events.append("pool_closed")

    async def scenario():
        control_service_server._server = FakeTcpServer()
        control_service_server.db_writer = FakeBackgroundDbWriter()

        with patch(
            "server.ropi_main_service.transport.tcp_server.close_pool",
            new=fake_close_pool,
        ):
            await control_service_server.serve_forever()

    asyncio.run(scenario())

    assert events == [
        "server_entered",
        "server_served",
        "server_exited",
        "writer_stopped",
        "pool_closed",
    ]


def test_start_failure_closes_background_writer_and_db_pool(control_service_server):
    events = []

    class FakeBackgroundDbWriter:
        def start(self):
            events.append("writer_started")

        async def stop(self):
            events.append("writer_stopped")

    async def fake_start_server(*args, **kwargs):
        events.append("start_server_failed")
        raise OSError("bind failed")

    async def fake_close_pool():
        events.append("pool_closed")

    async def scenario():
        control_service_server.db_writer = FakeBackgroundDbWriter()

        with patch(
            "server.ropi_main_service.transport.tcp_server.asyncio.start_server",
            new=fake_start_server,
        ), patch(
            "server.ropi_main_service.transport.tcp_server.close_pool",
            new=fake_close_pool,
        ):
            with pytest.raises(OSError, match="bind failed"):
                await control_service_server.start()

    asyncio.run(scenario())

    assert events == [
        "writer_started",
        "start_server_failed",
        "writer_stopped",
        "pool_closed",
    ]


def test_delivery_create_task_rejects_when_ros_service_is_unavailable(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=5,
        payload={
            "request_id": "req_001",
            "caregiver_id": "1",
            "item_id": "1",
            "quantity": 1,
            "destination_id": "delivery_room_301",
            "priority": "NORMAL",
            "notes": "delivery test",
            "idempotency_key": "idem_001",
        },
    )

    with patch(
        "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
        return_value={
            "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
            "destination_goal_poses": {
                "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
            },
            "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
        },
    ), patch(
        "server.ropi_main_service.transport.tcp_server.asyncio.get_running_loop",
        return_value=object(),
    ), patch(
        "server.ropi_main_service.application.delivery_runtime.RosRuntimeReadinessService"
    ) as readiness_service_cls:
        readiness_service_cls.return_value.get_status.side_effect = RuntimeError("socket missing")
        response = control_service_server.dispatch_frame(request)

    assert response.payload["result_code"] == "REJECTED"
    assert response.payload["reason_code"] == "ROS_SERVICE_UNAVAILABLE"
    assert "socket missing" in response.payload["result_message"]


def test_delivery_create_task_rejects_unknown_destination_id(control_service_server):
    request = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=6,
        payload={
            "request_id": "req_001",
            "caregiver_id": "1",
            "item_id": "1",
            "quantity": 1,
            "destination_id": "room1",
            "priority": "NORMAL",
            "notes": "delivery test",
            "idempotency_key": "idem_001",
        },
    )

    with patch(
        "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
        return_value={
            "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
            "destination_goal_poses": {
                "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
            },
            "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
        },
    ), patch(
        "server.ropi_main_service.transport.tcp_server.asyncio.get_running_loop",
        return_value=object(),
    ):
        response = control_service_server.dispatch_frame(request)

    assert response.payload["result_code"] == "INVALID_REQUEST"
    assert response.payload["reason_code"] == "DESTINATION_ID_UNKNOWN"
    assert "room1" in response.payload["result_message"]


def test_delivery_create_task_logs_ros_runtime_readiness_details(control_service_server, caplog):
    request = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=7,
        payload={
            "request_id": "req_001",
            "caregiver_id": "1",
            "item_id": "1",
            "quantity": 1,
            "destination_id": "delivery_room_301",
            "priority": "NORMAL",
            "notes": "delivery test",
            "idempotency_key": "idem_001",
        },
    )

    caplog.set_level(logging.WARNING)

    with patch(
        "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
        return_value={
            "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
            "destination_goal_poses": {
                "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
            },
            "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
        },
    ), patch(
        "server.ropi_main_service.transport.tcp_server.asyncio.get_running_loop",
        return_value=object(),
    ), patch(
        "server.ropi_main_service.application.delivery_runtime.RosRuntimeReadinessService"
    ) as readiness_service_cls:
        readiness_service_cls.return_value.get_status.return_value = {
            "ready": False,
            "checks": [
                {
                    "name": "pinky2.navigate_to_goal",
                    "ready": False,
                    "action_name": "/ropi/control/pinky2/navigate_to_goal",
                },
                {
                    "name": "arm1.execute_manipulation",
                    "ready": True,
                    "action_name": "/ropi/arm/arm1/execute_manipulation",
                },
                {
                    "name": "arm2.execute_manipulation",
                    "ready": False,
                    "action_name": "/ropi/arm/arm2/execute_manipulation",
                },
            ],
        }
        response = control_service_server.dispatch_frame(request)

    assert response.payload["result_code"] == "REJECTED"
    assert response.payload["reason_code"] == "ROS_RUNTIME_NOT_READY"
    assert "delivery_request_precheck_failed" in caplog.text
    assert "/ropi/control/pinky2/navigate_to_goal" in caplog.text
    assert "/ropi/arm/arm2/execute_manipulation" in caplog.text
