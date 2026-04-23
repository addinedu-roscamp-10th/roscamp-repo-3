import os
import socket

from server.ropi_main_service.ipc.uds_protocol import (
    build_request_message,
    read_message_from_socket,
    encode_message,
)


DEFAULT_ROS_SERVICE_SOCKET_PATH = os.getenv(
    "ROPI_ROS_SERVICE_SOCKET_PATH",
    "/tmp/ropi_control_ros_service.sock",
)
DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT = float(
    os.getenv("ROPI_ROS_SERVICE_SOCKET_TIMEOUT", "1.0")
)


class RosServiceCommandError(RuntimeError):
    """Raised when the ROS service returns an application-level IPC error."""


class UnixDomainSocketCommandClient:
    def __init__(
        self,
        *,
        socket_path: str = DEFAULT_ROS_SERVICE_SOCKET_PATH,
        timeout: float = DEFAULT_ROS_SERVICE_SOCKET_TIMEOUT,
    ):
        self.socket_path = socket_path
        self.timeout = timeout

    def send_command(self, command: str, payload: dict | None = None) -> dict:
        request = build_request_message(command, payload)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.sendall(encode_message(request))
            response = read_message_from_socket(sock)

        if not response.get("ok"):
            raise RosServiceCommandError(str(response.get("error", "ROS service IPC failed.")))

        return response.get("payload", {})
