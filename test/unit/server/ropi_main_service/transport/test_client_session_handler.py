import asyncio

from server.ropi_main_service.transport.client_session_handler import (
    ControlClientSessionHandler,
)
from server.ropi_main_service.transport.task_event_subscription_handler import (
    TaskEventSubscribeResult,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrame,
    build_frame,
)


class FakeReader:
    def __init__(self, frames):
        self.frames = list(frames)

    def at_eof(self):
        return not self.frames


class FakeWriter:
    def __init__(self, events):
        self.events = events

    def write(self, data):
        self.events.append(("write", data))

    async def drain(self):
        self.events.append("drain")

    def close(self):
        self.events.append("close")

    async def wait_closed(self):
        self.events.append("wait_closed")


class FakeStreamHub:
    def __init__(self, events):
        self.events = events

    async def unsubscribe(self, *, writer):
        self.events.append(("unsubscribe", writer))


class FakeSubscriptionHandler:
    def __init__(self, events, result):
        self.events = events
        self.result = result

    async def subscribe(self, payload, *, writer):
        self.events.append(("subscribe", payload, writer))
        return self.result

    async def replay_after_subscribe(self, payload, *, subscribe_accepted):
        self.events.append(("replay", payload, subscribe_accepted))


async def _read_frame(reader):
    frame = reader.frames.pop(0)
    return frame


def test_client_session_handler_dispatches_normal_frame_and_closes_writer():
    events = []
    request = TCPFrame(
        message_code=MESSAGE_CODE_HEARTBEAT,
        sequence_no=10,
        payload={},
    )
    response = build_frame(
        MESSAGE_CODE_HEARTBEAT,
        10,
        {"result_code": "OK"},
        is_response=True,
    )

    async def build_response_frame(frame):
        events.append(("build_response", frame))
        return response

    def encode_response(frame):
        events.append(("encode", frame))
        return b"encoded-response"

    handler = ControlClientSessionHandler(
        stream_hub=FakeStreamHub(events),
        task_event_subscription_handler=FakeSubscriptionHandler(
            events,
            TaskEventSubscribeResult(accepted=True, payload={}),
        ),
        build_response_frame=build_response_frame,
        encode_response=encode_response,
        success_response=lambda frame, payload: build_frame(
            frame.message_code,
            frame.sequence_no,
            payload,
            is_response=True,
        ),
        error_response=lambda frame, error_code, error: build_frame(
            frame.message_code,
            frame.sequence_no,
            {"error_code": error_code, "error": error},
            is_response=True,
            is_error=True,
        ),
        read_frame=_read_frame,
    )
    reader = FakeReader([request])
    writer = FakeWriter(events)

    asyncio.run(handler.handle_client(reader, writer))

    assert events == [
        ("build_response", request),
        ("encode", response),
        ("write", b"encoded-response"),
        "drain",
        ("unsubscribe", writer),
        "close",
        "wait_closed",
    ]


def test_client_session_handler_subscribe_acks_drains_then_replays():
    events = []
    request = TCPFrame(
        message_code=MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
        sequence_no=11,
        payload={"consumer_id": "monitor-1", "last_seq": 42},
    )

    def encode_response(frame):
        events.append(("encode", frame.payload))
        return b"subscribe-ack"

    handler = ControlClientSessionHandler(
        stream_hub=FakeStreamHub(events),
        task_event_subscription_handler=FakeSubscriptionHandler(
            events,
            TaskEventSubscribeResult(
                accepted=True,
                payload={"result_code": "ACCEPTED", "consumer_id": "monitor-1"},
            ),
        ),
        build_response_frame=(
            lambda _frame: (_ for _ in ()).throw(
                AssertionError("subscribe must not use normal dispatch"),
            )
        ),
        encode_response=encode_response,
        success_response=lambda frame, payload: build_frame(
            frame.message_code,
            frame.sequence_no,
            payload,
            is_response=True,
        ),
        error_response=lambda frame, error_code, error: build_frame(
            frame.message_code,
            frame.sequence_no,
            {"error_code": error_code, "error": error},
            is_response=True,
            is_error=True,
        ),
        read_frame=_read_frame,
    )
    reader = FakeReader([request])
    writer = FakeWriter(events)

    asyncio.run(handler.handle_client(reader, writer))

    assert events == [
        ("subscribe", request.payload, writer),
        ("encode", {"result_code": "ACCEPTED", "consumer_id": "monitor-1"}),
        ("write", b"subscribe-ack"),
        "drain",
        ("replay", request.payload, True),
        ("unsubscribe", writer),
        "close",
        "wait_closed",
    ]


def test_client_session_handler_rejected_subscribe_does_not_replay():
    events = []
    request = TCPFrame(
        message_code=MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
        sequence_no=12,
        payload={},
    )

    handler = ControlClientSessionHandler(
        stream_hub=FakeStreamHub(events),
        task_event_subscription_handler=FakeSubscriptionHandler(
            events,
            TaskEventSubscribeResult(
                accepted=False,
                payload={"result_code": "INVALID_REQUEST"},
                error_code="TASK_EVENT_SUBSCRIBE_ERROR",
                error_message="consumer_id가 필요합니다.",
            ),
        ),
        build_response_frame=lambda _frame: None,
        encode_response=lambda _frame: b"subscribe-error",
        success_response=lambda frame, payload: build_frame(
            frame.message_code,
            frame.sequence_no,
            payload,
            is_response=True,
        ),
        error_response=lambda frame, error_code, error: build_frame(
            frame.message_code,
            frame.sequence_no,
            {"error_code": error_code, "error": error},
            is_response=True,
            is_error=True,
        ),
        read_frame=_read_frame,
    )
    reader = FakeReader([request])
    writer = FakeWriter(events)

    asyncio.run(handler.handle_client(reader, writer))

    assert not any(event[0] == "replay" for event in events if isinstance(event, tuple))
