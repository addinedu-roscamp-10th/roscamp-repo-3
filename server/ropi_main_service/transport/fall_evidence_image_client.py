import asyncio
import os
import socket
from contextlib import suppress

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    TCPFrame,
    TCPFrameError,
    encode_frame,
    read_frame_from_socket,
    read_frame_from_stream,
)


DEFAULT_CONSUMER_ID = "control_service_ai_fall"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6000
DEFAULT_CONNECT_TIMEOUT_SEC = 3.0


class FallEvidenceImageClientError(RuntimeError):
    """Raised when IF-PAT-006 evidence-image query fails at the transport layer."""


class FallEvidenceImageClient:
    def __init__(
        self,
        *,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        connect_timeout_sec=DEFAULT_CONNECT_TIMEOUT_SEC,
        sequence_no_start=1,
    ):
        self.host = str(host or DEFAULT_HOST).strip() or DEFAULT_HOST
        self.port = int(port)
        self.connect_timeout_sec = float(connect_timeout_sec)
        self._next_sequence_no = int(sequence_no_start)

    @classmethod
    def from_env(cls):
        host = (
            os.getenv("AI_FALL_EVIDENCE_HOST")
            or os.getenv("AI_FALL_STREAM_HOST")
            or DEFAULT_HOST
        )
        port = (
            os.getenv("AI_FALL_EVIDENCE_PORT")
            or os.getenv("AI_FALL_STREAM_PORT")
            or str(DEFAULT_PORT)
        )
        timeout = (
            os.getenv("AI_FALL_EVIDENCE_CONNECT_TIMEOUT_SEC")
            or os.getenv("AI_FALL_STREAM_CONNECT_TIMEOUT_SEC")
            or str(DEFAULT_CONNECT_TIMEOUT_SEC)
        )
        return cls(
            host=host,
            port=int(port),
            connect_timeout_sec=float(timeout),
        )

    def query_evidence_image(
        self,
        *,
        consumer_id=DEFAULT_CONSUMER_ID,
        evidence_image_id,
        result_seq=None,
        pinky_id=None,
    ):
        sequence_no = self._allocate_sequence_no()
        request = TCPFrame(
            message_code=MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
            sequence_no=sequence_no,
            payload=self._build_payload(
                consumer_id=consumer_id,
                evidence_image_id=evidence_image_id,
                result_seq=result_seq,
                pinky_id=pinky_id,
            ),
        )

        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.connect_timeout_sec,
            ) as sock:
                sock.settimeout(self.connect_timeout_sec)
                sock.sendall(encode_frame(request))
                response = read_frame_from_socket(sock)
        except (OSError, TCPFrameError) as exc:
            raise FallEvidenceImageClientError(
                f"IF-PAT-006 evidence image query failed: {exc}"
            ) from exc

        return self._parse_response(response, sequence_no=sequence_no)

    async def async_query_evidence_image(
        self,
        *,
        consumer_id=DEFAULT_CONSUMER_ID,
        evidence_image_id,
        result_seq=None,
        pinky_id=None,
    ):
        sequence_no = self._allocate_sequence_no()
        request = TCPFrame(
            message_code=MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
            sequence_no=sequence_no,
            payload=self._build_payload(
                consumer_id=consumer_id,
                evidence_image_id=evidence_image_id,
                result_seq=result_seq,
                pinky_id=pinky_id,
            ),
        )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.connect_timeout_sec,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise FallEvidenceImageClientError(
                f"IF-PAT-006 evidence image query connection failed: {exc}"
            ) from exc

        try:
            writer.write(encode_frame(request))
            await writer.drain()
            response = await read_frame_from_stream(reader)
        except (OSError, TCPFrameError) as exc:
            raise FallEvidenceImageClientError(
                f"IF-PAT-006 evidence image query failed: {exc}"
            ) from exc
        finally:
            writer.close()
            with suppress(OSError, ConnectionError):
                await writer.wait_closed()

        return self._parse_response(response, sequence_no=sequence_no)

    @staticmethod
    def _build_payload(*, consumer_id, evidence_image_id, result_seq=None, pinky_id=None):
        payload = {
            "consumer_id": str(consumer_id or "").strip() or DEFAULT_CONSUMER_ID,
            "evidence_image_id": str(evidence_image_id or "").strip(),
        }
        if result_seq not in (None, ""):
            payload["result_seq"] = int(result_seq)
        if str(pinky_id or "").strip():
            payload["pinky_id"] = str(pinky_id).strip()
        return payload

    @staticmethod
    def _parse_response(frame, *, sequence_no):
        if frame.message_code != MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY:
            raise FallEvidenceImageClientError(
                f"unexpected IF-PAT-006 response message_code: 0x{frame.message_code:04x}"
            )
        if frame.sequence_no != sequence_no:
            raise FallEvidenceImageClientError(
                f"unexpected IF-PAT-006 response sequence_no: {frame.sequence_no}"
            )
        if not frame.is_response:
            raise FallEvidenceImageClientError("IF-PAT-006 response flag is missing.")

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        if frame.is_error:
            return {
                "result_code": payload.get("result_code") or "UPSTREAM_ERROR",
                "result_message": payload.get("result_message")
                or payload.get("error")
                or "AI Service returned an error frame.",
                **payload,
            }
        return payload

    def _allocate_sequence_no(self):
        sequence_no = self._next_sequence_no
        self._next_sequence_no += 1
        return sequence_no & 0xFFFFFFFF


__all__ = [
    "DEFAULT_CONSUMER_ID",
    "FallEvidenceImageClient",
    "FallEvidenceImageClientError",
]
