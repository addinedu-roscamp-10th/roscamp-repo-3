import asyncio
import logging
import os

from server.ropi_main_service.ipc.config import get_ros_service_ipc_config
from server.ropi_main_service.ipc.uds_protocol import (
    UDSProtocolError,
    build_response_message,
    encode_message,
    read_message_from_stream,
)
from server.ropi_main_service.observability import log_event
from server.ropi_main_service.ros.command_dispatcher import (
    RosServiceCommandDispatchError,
    RosServiceCommandDispatcher,
)


logger = logging.getLogger(__name__)


class RosServiceUdsServer:
    def __init__(
        self,
        *,
        socket_path: str | None = None,
        goal_pose_action_client,
        manipulation_action_client=None,
        runtime_config=None,
    ):
        ipc_config = get_ros_service_ipc_config()
        self.socket_path = socket_path or ipc_config["socket_path"]
        self.dispatcher = RosServiceCommandDispatcher(
            goal_pose_action_client=goal_pose_action_client,
            manipulation_action_client=manipulation_action_client,
            runtime_config=runtime_config,
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
        self.dispatcher.close()
        self._cleanup_existing_socket()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while not reader.at_eof():
                try:
                    request = await read_message_from_stream(reader)
                except UDSProtocolError:
                    break

                command = str(request.get("command") or "").strip()
                payload = request.get("payload") or {}
                log_event(
                    logger,
                    logging.INFO,
                    "ros_service_request_received",
                    command=command,
                    pinky_id=payload.get("pinky_id"),
                    arm_id=payload.get("arm_id"),
                )
                response = await self._dispatch_request(request)
                if response.get("ok"):
                    log_event(
                        logger,
                        logging.INFO,
                        "ros_service_request_succeeded",
                        command=command,
                    )
                else:
                    log_event(
                        logger,
                        logging.WARNING,
                        "ros_service_request_failed",
                        command=command,
                        error_code=response.get("error_code"),
                        error=response.get("error"),
                    )
                writer.write(encode_message(response))
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _dispatch_request(self, request: dict) -> dict:
        try:
            return build_response_message(
                ok=True,
                payload=await self.dispatcher.async_dispatch(
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
