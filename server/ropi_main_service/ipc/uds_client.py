import asyncio
import socket
from contextlib import suppress

from server.ropi_main_service.ipc.config import get_ros_service_ipc_config
from server.ropi_main_service.ipc.uds_protocol import (
    UDSProtocolError,
    build_request_message,
    encode_message,
    read_message_from_stream,
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

    def send_command(self, command: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        request = build_request_message(command, payload)
        socket_timeout = self.timeout if timeout is None else timeout

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(socket_timeout)
                sock.connect(self.socket_path)
                sock.sendall(encode_message(request))
                response = read_message_from_socket(sock)
        except (OSError, UDSProtocolError) as exc:
            raise RosServiceCommandError(
                f"ROS service command failed: {command}: {exc}"
            ) from exc

        if not response.get("ok"):
            raise RosServiceCommandError(str(response.get("error", "ROS service IPC failed.")))

        return response.get("payload", {})

    async def async_send_command(self, command: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        request = build_request_message(command, payload)
        socket_timeout = self.timeout if timeout is None else timeout
        writer = None

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=socket_timeout,
            )
            writer.write(encode_message(request))
            await asyncio.wait_for(writer.drain(), timeout=socket_timeout)
            response = await asyncio.wait_for(
                read_message_from_stream(reader),
                timeout=socket_timeout,
            )
        except (OSError, asyncio.TimeoutError, UDSProtocolError) as exc:
            raise RosServiceCommandError(
                f"ROS service command failed: {command}: {exc}"
            ) from exc
        finally:
            if writer is not None:
                writer.close()
                with suppress(OSError, ConnectionError):
                    await writer.wait_closed()

        if not response.get("ok"):
            raise RosServiceCommandError(str(response.get("error", "ROS service IPC failed.")))

        return response.get("payload", {})
