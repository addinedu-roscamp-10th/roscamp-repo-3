import socket

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrameError,
    build_frame,
    encode_frame,
    read_frame_from_socket,
)
from ui.utils.network import tcp_client
from ui.utils.network.tcp_client import TcpClientError, _next_sequence_no


class TaskEventStreamClient:
    def __init__(self, *, host=None, port=None, timeout=None):
        self.host = host or tcp_client.CONTROL_SERVER_HOST
        self.port = tcp_client.CONTROL_SERVER_PORT if port is None else int(port)
        self.timeout = (
            tcp_client.CONTROL_SERVER_TIMEOUT if timeout is None else float(timeout)
        )
        self._sock = None
        self._closed = False

    def listen(self, *, consumer_id, last_seq=0, on_batch):
        self._closed = False
        sequence_no = _next_sequence_no()
        subscribe_frame = build_frame(
            MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
            sequence_no,
            {
                "consumer_id": str(consumer_id or "").strip(),
                "last_seq": int(last_seq or 0),
            },
        )

        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout,
            ) as sock:
                self._sock = sock
                sock.settimeout(self.timeout)
                sock.sendall(encode_frame(subscribe_frame))
                self._read_subscribe_ack(sock, subscribe_frame)

                sock.settimeout(None)
                while not self._closed:
                    push_frame = read_frame_from_socket(sock)
                    if (
                        push_frame.message_code == MESSAGE_CODE_TASK_EVENT_SUBSCRIBE
                        and push_frame.is_push
                    ):
                        on_batch(push_frame.payload or {})
        except OSError as exc:
            if self._closed:
                return
            raise TcpClientError(f"task event stream 연결이 종료되었습니다: {exc}") from exc
        except TCPFrameError as exc:
            if self._closed:
                return
            raise TcpClientError(f"task event stream 프레임을 읽을 수 없습니다: {exc}") from exc
        finally:
            self._sock = None

    def close(self):
        self._closed = True
        sock = self._sock
        if sock is None:
            return

        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    @staticmethod
    def _read_subscribe_ack(sock, subscribe_frame):
        response_frame = read_frame_from_socket(sock)
        if response_frame.message_code != subscribe_frame.message_code:
            raise TcpClientError("구독 응답의 message_code가 요청과 일치하지 않습니다.")

        if response_frame.sequence_no != subscribe_frame.sequence_no:
            raise TcpClientError("구독 응답의 sequence_no가 요청과 일치하지 않습니다.")

        if not response_frame.is_response:
            raise TcpClientError("구독 응답 프레임에 response flag가 설정되어 있지 않습니다.")

        if response_frame.is_error:
            error = (
                response_frame.payload.get("error")
                if isinstance(response_frame.payload, dict)
                else None
            )
            raise TcpClientError(error or "task event stream 구독이 거부되었습니다.")


__all__ = ["TaskEventStreamClient"]
