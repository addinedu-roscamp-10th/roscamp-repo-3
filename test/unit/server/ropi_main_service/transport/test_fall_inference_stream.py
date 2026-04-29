import asyncio

import pytest

from server.ropi_main_service.transport.fall_inference_stream import (
    FallInferenceStreamClient,
    FallInferenceStreamError,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
    TCPFrame,
    encode_frame,
    read_frame_from_stream,
)


def test_fall_inference_stream_client_subscribes_and_consumes_push_batch():
    requests = []
    batches = []

    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        requests.append(request)

        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
                    sequence_no=request.sequence_no,
                    payload={
                        "result_code": "ACCEPTED",
                        "result_message": None,
                        "accepted_consumer_id": "control_service_ai_fall",
                        "subscribed_pinky_id": "pinky3",
                    },
                    is_response=True,
                )
            )
        )
        await writer.drain()

        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
                    sequence_no=541,
                    payload={
                        "batch_end_seq": 541,
                        "results": [
                            {
                                "result_seq": 541,
                                "frame_id": "front_cam_frame_541",
                                "frame_ts": "2026-04-29T12:34:56Z",
                                "fall_detected": True,
                                "confidence": 0.94,
                                "fall_streak_ms": 1200,
                            }
                        ],
                    },
                    is_push=True,
                )
            )
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def scenario():
        server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
        host, port = server.sockets[0].getsockname()[:2]
        client = FallInferenceStreamClient(
            host=host,
            port=port,
            consumer_id="control_service_ai_fall",
            last_seq=540,
            pinky_id="pinky3",
        )

        try:
            summary = await client.subscribe_and_listen(
                lambda batch: batches.append(batch),
                max_batches=1,
            )
            return client, summary
        finally:
            server.close()
            await server.wait_closed()

    client, summary = asyncio.run(scenario())

    assert len(requests) == 1
    request = requests[0]
    assert request.message_code == MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE
    assert request.is_response is False
    assert request.payload == {
        "consumer_id": "control_service_ai_fall",
        "last_seq": 540,
        "pinky_id": "pinky3",
    }
    assert batches == [
        {
            "batch_end_seq": 541,
            "results": [
                {
                    "result_seq": 541,
                    "frame_id": "front_cam_frame_541",
                    "frame_ts": "2026-04-29T12:34:56Z",
                    "fall_detected": True,
                    "confidence": 0.94,
                    "fall_streak_ms": 1200,
                }
            ],
        }
    ]
    assert client.last_seq == 541
    assert summary == {
        "ack": {
            "result_code": "ACCEPTED",
            "result_message": None,
            "accepted_consumer_id": "control_service_ai_fall",
            "subscribed_pinky_id": "pinky3",
        },
        "batch_count": 1,
        "last_seq": 541,
    }


def test_fall_inference_stream_client_rejects_invalid_subscribe_ack():
    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
                    sequence_no=request.sequence_no,
                    payload={
                        "result_code": "INVALID_REQUEST",
                        "result_message": "consumer_id is required.",
                    },
                    is_response=True,
                )
            )
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def scenario():
        server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
        host, port = server.sockets[0].getsockname()[:2]
        client = FallInferenceStreamClient(
            host=host,
            port=port,
            consumer_id="",
        )

        try:
            with pytest.raises(FallInferenceStreamError, match="INVALID_REQUEST"):
                await client.subscribe_and_listen(max_batches=1)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())
