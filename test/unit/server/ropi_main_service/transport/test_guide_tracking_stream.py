import asyncio

import pytest

from server.ropi_main_service.transport.guide_tracking_stream import (
    GuideTrackingStreamClient,
    GuideTrackingStreamError,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
    TCPFrame,
    encode_frame,
    read_frame_from_stream,
)


def test_guide_tracking_stream_client_subscribes_and_consumes_push_batch():
    requests = []
    batches = []

    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        requests.append(request)

        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
                    sequence_no=request.sequence_no,
                    payload={
                        "result_code": "ACCEPTED",
                        "result_message": None,
                        "accepted_consumer_id": "control_service_ai_guide",
                        "subscribed_pinky_id": "pinky1",
                        "subscribed_tracking_mode": "KEEP_TRACK",
                    },
                    is_response=True,
                )
            )
        )
        await writer.drain()

        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
                    sequence_no=881,
                    payload={
                        "batch_end_seq": 881,
                        "results": [
                            {
                                "result_seq": 881,
                                "pinky_id": "pinky1",
                                "frame_ts": "2026-04-19T12:35:10Z",
                                "tracking_status": "TRACKING",
                                "active_track_id": "track_17",
                                "confidence": 0.91,
                                "image_width_px": 640,
                                "image_height_px": 480,
                                "candidate_tracks": [
                                    {
                                        "track_id": "track_17",
                                        "bbox_xyxy": [120, 80, 300, 420],
                                        "score": 0.91,
                                    }
                                ],
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
        client = GuideTrackingStreamClient(
            host=host,
            port=port,
            consumer_id="control_service_ai_guide",
            last_seq=880,
            pinky_id="pinky1",
            tracking_mode="KEEP_TRACK",
            expected_track_id="track_17",
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
    assert request.message_code == MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE
    assert request.payload == {
        "consumer_id": "control_service_ai_guide",
        "last_seq": 880,
        "pinky_id": "pinky1",
        "tracking_mode": "KEEP_TRACK",
        "expected_track_id": "track_17",
    }
    assert batches[0]["results"][0]["candidate_tracks"][0]["bbox_xyxy"] == [
        120,
        80,
        300,
        420,
    ]
    assert client.last_seq == 881
    assert summary["ack"]["result_code"] == "ACCEPTED"
    assert summary["batch_count"] == 1
    assert summary["last_seq"] == 881


def test_guide_tracking_stream_client_rejects_invalid_subscribe_ack():
    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
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
        client = GuideTrackingStreamClient(host=host, port=port, consumer_id="")

        try:
            with pytest.raises(GuideTrackingStreamError, match="INVALID_REQUEST"):
                await client.subscribe_and_listen(max_batches=1)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_guide_tracking_stream_client_from_env_uses_common_ai_server_host(monkeypatch):
    monkeypatch.delenv("AI_GUIDE_TRACKING_STREAM_HOST", raising=False)
    monkeypatch.delenv("AI_GUIDE_TRACKING_STREAM_PORT", raising=False)
    monkeypatch.delenv("AI_GUIDE_TRACKING_STREAM_PINKY_ID", raising=False)
    monkeypatch.setenv("AI_SERVER_HOST", "192.168.0.89")
    monkeypatch.setenv("AI_GUIDE_TRACKING_STREAM_MODE", "KEEP_TRACK")
    monkeypatch.setenv("AI_GUIDE_TRACKING_STREAM_EXPECTED_TRACK_ID", "track_17")

    client = GuideTrackingStreamClient.from_env()

    assert client.host == "192.168.0.89"
    assert client.port == 6000
    assert client.pinky_id is None
    assert client._build_subscribe_payload() == {
        "consumer_id": "control_service_ai_guide",
        "last_seq": 0,
        "tracking_mode": "KEEP_TRACK",
        "expected_track_id": "track_17",
    }
