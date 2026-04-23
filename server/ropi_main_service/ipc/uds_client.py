import socket

from server.ropi_main_service.ipc.config import get_ros_service_ipc_config
from server.ropi_main_service.ipc.uds_protocol import (
    build_request_message,
    encode_message,
    read_message_from_socket,
)


class RosServiceCommandError(RuntimeError):
    """Raised when the ROS service returns an application-level IPC error."""


class UnixDomainSocketCommandClient:
    def __init__(
        self,
        *,
        socket_path: str | None = None,
        timeout: float | None = None,
    ):
        ipc_config = get_ros_service_ipc_config()
        self.socket_path = socket_path or ipc_config["socket_path"]
        self.timeout = ipc_config["timeout"] if timeout is None else timeout

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
