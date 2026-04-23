import asyncio
import os

from server.ropi_main_service.ipc.config import get_ros_service_ipc_config
from server.ropi_main_service.ipc.uds_protocol import (
    UDSProtocolError,
    build_response_message,
    encode_message,
    read_message_from_stream,
)


class RosServiceCommandDispatchError(RuntimeError):
    def __init__(self, error_code: str, error: str):
        super().__init__(error)
        self.error_code = error_code


class RosServiceCommandDispatcher:
    def __init__(self, *, goal_pose_action_client):
        self.goal_pose_action_client = goal_pose_action_client

    def dispatch(self, command: str, payload: dict | None = None) -> dict:
        payload = payload or {}

        if command == "navigate_to_goal":
            pinky_id = str(payload.get("pinky_id") or "").strip()
            goal = payload.get("goal") or {}

            if not pinky_id:
                raise RosServiceCommandDispatchError(
                    "PINKY_ID_REQUIRED",
                    "navigate_to_goal command requires pinky_id.",
                )

            return self.goal_pose_action_client.send_goal(
                action_name=f"/ropi/control/{pinky_id}/navigate_to_goal",
                goal=goal,
            )

        raise RosServiceCommandDispatchError(
            "UNKNOWN_COMMAND",
            f"Unsupported ROS service command: {command}",
        )


class RosServiceUdsServer:
    def __init__(self, *, socket_path: str | None = None, goal_pose_action_client):
        ipc_config = get_ros_service_ipc_config()
        self.socket_path = socket_path or ipc_config["socket_path"]
        self.dispatcher = RosServiceCommandDispatcher(
            goal_pose_action_client=goal_pose_action_client,
        )
        self._server = None

    async def start(self):
        self._cleanup_existing_socket()
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
        )
        return self._server

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._cleanup_existing_socket()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while not reader.at_eof():
                try:
                    request = await read_message_from_stream(reader)
                except UDSProtocolError:
                    break

                response = self._dispatch_request(request)
                writer.write(encode_message(response))
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def _dispatch_request(self, request: dict) -> dict:
        try:
            return build_response_message(
                ok=True,
                payload=self.dispatcher.dispatch(
                    request.get("command", ""),
                    request.get("payload") or {},
                ),
            )
        except RosServiceCommandDispatchError as exc:
            return build_response_message(
                ok=False,
                error_code=exc.error_code,
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover
            return build_response_message(
                ok=False,
                error_code="ROS_SERVICE_INTERNAL_ERROR",
                error=str(exc),
            )

    def _cleanup_existing_socket(self):
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
