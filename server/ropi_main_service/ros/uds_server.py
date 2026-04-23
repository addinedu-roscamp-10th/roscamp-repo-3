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
    def __init__(self, *, goal_pose_action_client, manipulation_action_client=None):
        self.goal_pose_action_client = goal_pose_action_client
        self.manipulation_action_client = manipulation_action_client
        self._command_handlers = {
            "navigate_to_goal": self._dispatch_navigate_to_goal,
            "execute_manipulation": self._dispatch_execute_manipulation,
        }

    def dispatch(self, command: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        handler = self._command_handlers.get(command)

        if handler is None:
            raise RosServiceCommandDispatchError(
                "UNKNOWN_COMMAND",
                f"Unsupported ROS service command: {command}",
            )

        return handler(payload)

    def _dispatch_navigate_to_goal(self, payload: dict) -> dict:
        pinky_id = self._get_required_identifier(
            payload,
            field_name="pinky_id",
            error_code="PINKY_ID_REQUIRED",
            error_message="navigate_to_goal command requires pinky_id.",
        )
        goal = payload.get("goal") or {}

        return self.goal_pose_action_client.send_goal(
            action_name=f"/ropi/control/{pinky_id}/navigate_to_goal",
            goal=goal,
        )

    def _dispatch_execute_manipulation(self, payload: dict) -> dict:
        arm_id = self._get_required_identifier(
            payload,
            field_name="arm_id",
            error_code="ARM_ID_REQUIRED",
            error_message="execute_manipulation command requires arm_id.",
        )
        goal = payload.get("goal") or {}
        action_client = self._require_action_client(
            self.manipulation_action_client,
            error_code="MANIPULATION_SERVICE_UNAVAILABLE",
            error_message="execute_manipulation command requires manipulation action client.",
        )

        return action_client.send_goal(
            action_name=f"/ropi/arm/{arm_id}/execute_manipulation",
            goal=goal,
        )

    @staticmethod
    def _get_required_identifier(
        payload: dict,
        *,
        field_name: str,
        error_code: str,
        error_message: str,
    ) -> str:
        value = str(payload.get(field_name) or "").strip()
        if not value:
            raise RosServiceCommandDispatchError(
                error_code,
                error_message,
            )
        return value

    @staticmethod
    def _require_action_client(action_client, *, error_code: str, error_message: str):
        if action_client is None:
            raise RosServiceCommandDispatchError(
                error_code,
                error_message,
            )
        return action_client


class RosServiceUdsServer:
    def __init__(
        self,
        *,
        socket_path: str | None = None,
        goal_pose_action_client,
        manipulation_action_client=None,
    ):
        ipc_config = get_ros_service_ipc_config()
        self.socket_path = socket_path or ipc_config["socket_path"]
        self.dispatcher = RosServiceCommandDispatcher(
            goal_pose_action_client=goal_pose_action_client,
            manipulation_action_client=manipulation_action_client,
        )
        self._server = None

    async def start(self):
        self._cleanup_existing_socket()
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
        )
        return self._server

    async def serve_forever(self):
        if self._server is None:
            await self.start()

        async with self._server:
            await self._server.serve_forever()

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
