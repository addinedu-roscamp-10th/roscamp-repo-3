import asyncio

from server.ropi_main_service.transport.frame_handlers import ControlFrameHandlers
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_HEARTBEAT,
    TCPFrame,
)


def test_control_frame_handlers_heartbeat_uses_injected_readiness_service():
    class FakeReadinessService:
        def get_status(self):
            return {
                "ready": True,
                "checks": [{"name": "pinky2.navigate_to_goal", "ready": True}],
            }

    handlers = ControlFrameHandlers(
        ros_readiness_service_factory=FakeReadinessService,
    )
    frame = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=1,
        payload={"check_ros": True},
    )

    response = handlers.handle_heartbeat(frame, frame.payload)

    assert response.is_response is True
    assert response.message_code == MESSAGE_CODE_HEARTBEAT
    assert response.payload["ros"] == {
        "ok": True,
        "detail": {
            "ready": True,
            "checks": [{"name": "pinky2.navigate_to_goal", "ready": True}],
        },
    }


def test_control_frame_handlers_async_delivery_create_publishes_task_update():
    published = []

    class FakeDeliveryRequestService:
        async def async_create_delivery_task(self, **payload):
            return {
                "result_code": "ACCEPTED",
                "task_id": 101,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
                "destination_id": payload["destination_id"],
            }

    class FakeTaskUpdateEventPublisher:
        async def publish_from_response(self, result, **metadata):
            published.append((result, metadata))

    handlers = ControlFrameHandlers(
        delivery_request_service_builder=(
            lambda **_kwargs: FakeDeliveryRequestService()
        ),
        task_update_event_publisher=FakeTaskUpdateEventPublisher(),
    )
    frame = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=7,
        payload={
            "request_id": "req_001",
            "caregiver_id": 1,
            "item_id": 1,
            "quantity": 1,
            "destination_id": "delivery_room_301",
        },
    )

    response = asyncio.run(
        handlers.handle_delivery_create_task_async(frame, frame.payload),
    )

    assert response.is_response is True
    assert response.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK
    assert response.payload["result_code"] == "ACCEPTED"
    assert response.payload["destination_id"] == "delivery_room_301"
    assert published == [
        (
            response.payload,
            {"source": "DELIVERY_CREATE"},
        )
    ]
