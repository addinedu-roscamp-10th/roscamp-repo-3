from unittest.mock import patch

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_INTERNAL_RPC,
    TCPFrame,
    decode_frame_bytes,
    encode_frame,
)
from ui.utils.network.tcp_client import send_request


class FakeSocket:
    def __init__(self, recv_chunks):
        self._recv_chunks = list(recv_chunks)
        self.sent_data = []
        self.timeout = None

    def recv(self, buffer_size):
        if self._recv_chunks:
            chunk = self._recv_chunks.pop(0)
            head = chunk[:buffer_size]
            tail = chunk[buffer_size:]
            if tail:
                self._recv_chunks.insert(0, tail)
            return head
        return b""

    def sendall(self, data):
        self.sent_data.append(data)

    def settimeout(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_send_request_serializes_custom_frame_and_parses_framed_response():
    fake_socket = FakeSocket(
        [
            encode_frame(
                TCPFrame(
                    message_code=MESSAGE_CODE_INTERNAL_RPC,
                    sequence_no=77,
                    payload={"items": 3},
                    is_response=True,
                )
            )
        ]
    )

    with (
        patch("ui.utils.network.tcp_client.socket.create_connection", return_value=fake_socket) as create_connection,
        patch("ui.utils.network.tcp_client._next_sequence_no", return_value=77),
    ):
        response = send_request(
            MESSAGE_CODE_INTERNAL_RPC,
            {"service": "task_request", "method": "get_product_names"},
        )

    assert response == {"ok": True, "payload": {"items": 3}}
    create_connection.assert_called_once()
    assert fake_socket.timeout is not None

    request = decode_frame_bytes(fake_socket.sent_data[0])
    assert request.message_code == MESSAGE_CODE_INTERNAL_RPC
    assert request.sequence_no == 77
    assert request.is_response is False
    assert request.payload == {"service": "task_request", "method": "get_product_names"}
