import asyncio

import pytest

from server.ropi_main_service.transport.fall_evidence_image_client import (
    FallEvidenceImageClient,
    FallEvidenceImageClientError,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    TCPFrame,
    encode_frame,
    read_frame_from_stream,
)


def test_fall_evidence_image_client_sends_if_pat_006_request_and_returns_response():
    requests = []

    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        requests.append(request)

        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
                    sequence_no=request.sequence_no,
                    payload={
                        "result_code": "OK",
                        "result_message": None,
                        "evidence_image_id": "fall_evidence_pinky3_541",
                        "result_seq": 541,
                        "frame_id": "front_cam_frame_541",
                        "frame_ts": "2026-04-30T06:09:38Z",
                        "image_format": "jpeg",
                        "image_encoding": "base64",
                        "image_data": "/9j/AA==",
                        "image_width_px": 640,
                        "image_height_px": 480,
                        "detections": [],
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
        client = FallEvidenceImageClient(host=host, port=port)

        try:
            response = await client.async_query_evidence_image(
                consumer_id="control_service_ai_fall",
                evidence_image_id="fall_evidence_pinky3_541",
                result_seq=541,
                pinky_id="pinky3",
            )
            return response
        finally:
            server.close()
            await server.wait_closed()

    response = asyncio.run(scenario())

    assert response["result_code"] == "OK"
    assert requests[0].message_code == MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY
    assert requests[0].payload == {
        "consumer_id": "control_service_ai_fall",
        "evidence_image_id": "fall_evidence_pinky3_541",
        "result_seq": 541,
        "pinky_id": "pinky3",
    }


def test_fall_evidence_image_client_rejects_unexpected_response_code():
    async def handle_client(reader, writer):
        request = await read_frame_from_stream(reader)
        writer.write(
            encode_frame(
                TCPFrame(
                    message_code=0x9999,
                    sequence_no=request.sequence_no,
                    payload={"result_code": "OK"},
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
        client = FallEvidenceImageClient(host=host, port=port)

        try:
            with pytest.raises(FallEvidenceImageClientError, match="message_code"):
                await client.async_query_evidence_image(
                    consumer_id="control_service_ai_fall",
                    evidence_image_id="fall_evidence_pinky3_541",
                )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_fall_evidence_image_client_from_env_uses_common_ai_server_host(monkeypatch):
    monkeypatch.delenv("AI_FALL_EVIDENCE_HOST", raising=False)
    monkeypatch.delenv("AI_FALL_STREAM_HOST", raising=False)
    monkeypatch.delenv("AI_FALL_EVIDENCE_PORT", raising=False)
    monkeypatch.delenv("AI_FALL_STREAM_PORT", raising=False)
    monkeypatch.setenv("AI_SERVER_HOST", "192.168.0.89")

    client = FallEvidenceImageClient.from_env()

    assert client.host == "192.168.0.89"
    assert client.port == 6000
