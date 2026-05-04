import asyncio

from server.ropi_main_service.transport.frame_router import ControlFrameRouter
from server.ropi_main_service.transport.tcp_protocol import TCPFrame


def test_control_frame_router_routes_sync_message_code_with_payload_and_loop():
    calls = []

    def handler(frame, payload, *, loop=None):
        calls.append((frame, payload, loop))
        return {"handled": True, "sequence_no": frame.sequence_no}

    router = ControlFrameRouter(sync_routes={0x2001: handler})
    frame = TCPFrame(
        message_code=0x2001,
        sequence_no=7,
        payload={"task_id": 101},
    )
    loop = object()

    result = router.dispatch(frame, loop=loop)

    assert result.handled is True
    assert result.response == {"handled": True, "sequence_no": 7}
    assert calls == [(frame, {"task_id": 101}, loop)]


def test_control_frame_router_returns_unknown_message_code_error():
    router = ControlFrameRouter(sync_routes={})
    frame = TCPFrame(message_code=0x9999, sequence_no=1, payload={})

    result = router.dispatch(frame)

    assert result.handled is False
    assert result.error_code == "UNKNOWN_MESSAGE_CODE"
    assert result.error_message == "지원하지 않는 message_code입니다: 0x9999"


def test_control_frame_router_async_stream_required_error():
    async def handler(_frame, _payload):
        raise AssertionError("stream-required message must not use normal async route")

    router = ControlFrameRouter(
        async_routes={0x1003: handler},
        async_stream_required_codes={0x1003},
    )
    frame = TCPFrame(message_code=0x1003, sequence_no=2, payload={})

    result = asyncio.run(router.async_dispatch(frame))

    assert result.handled is False
    assert result.error_code == "STREAM_REQUIRED"
    assert result.error_message == "task event subscribe는 persistent TCP stream에서만 처리됩니다."


def test_control_frame_router_routes_async_message_code():
    calls = []

    async def handler(frame, payload):
        calls.append((frame, payload))
        return {"result_code": "ACCEPTED"}

    router = ControlFrameRouter(async_routes={0x4001: handler})
    frame = TCPFrame(
        message_code=0x4001,
        sequence_no=3,
        payload={"visitor_id": 1},
    )

    result = asyncio.run(router.async_dispatch(frame))

    assert result.handled is True
    assert result.response == {"result_code": "ACCEPTED"}
    assert calls == [(frame, {"visitor_id": 1})]
