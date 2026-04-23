import socket
from itertools import count

from server.ropi_main_service.tcp_protocol import (
    build_frame,
    encode_frame,
    read_frame_from_socket,
    resolve_message_code,
)
from ui.utils.config.network_config import (
    CONTROL_SERVER_HOST,
    CONTROL_SERVER_PORT,
    CONTROL_SERVER_TIMEOUT,
)


class TcpClientError(RuntimeError):
    """Raised when TCP communication with the control server fails."""


_SEQUENCE_COUNTER = count(1)


def _next_sequence_no() -> int:
    return next(_SEQUENCE_COUNTER) & 0xFFFFFFFF


def send_request(message_code: int | str, payload: dict | None = None, *, timeout: float | None = None) -> dict:
    resolved_message_code = resolve_message_code(message_code)
    sequence_no = _next_sequence_no()
    request_frame = build_frame(resolved_message_code, sequence_no, payload or {})

    try:
        with socket.create_connection(
            (CONTROL_SERVER_HOST, CONTROL_SERVER_PORT),
            timeout=CONTROL_SERVER_TIMEOUT if timeout is None else timeout,
        ) as sock:
            sock.settimeout(CONTROL_SERVER_TIMEOUT if timeout is None else timeout)
            sock.sendall(encode_frame(request_frame))
            response_frame = read_frame_from_socket(sock)
    except OSError as exc:
        raise TcpClientError(f"서버와 통신할 수 없습니다: {exc}") from exc

    if response_frame.message_code != request_frame.message_code:
        raise TcpClientError("서버 응답의 message_code가 요청과 일치하지 않습니다.")

    if response_frame.sequence_no != request_frame.sequence_no:
        raise TcpClientError("서버 응답의 sequence_no가 요청과 일치하지 않습니다.")

    if not response_frame.is_response:
        raise TcpClientError("서버 응답 프레임에 response flag가 설정되어 있지 않습니다.")

    if response_frame.is_error:
        return {
            "ok": False,
            **response_frame.payload,
        }

    return {
        "ok": True,
        "payload": response_frame.payload,
    }
