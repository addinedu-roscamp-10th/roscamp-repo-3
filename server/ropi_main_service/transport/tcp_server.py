import argparse
import asyncio
import logging
import os
import socket
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from server.ropi_main_service.application.auth import AuthService
from server.ropi_main_service.application.delivery_runtime import build_delivery_request_service
from server.ropi_main_service.application.fall_inference_runtime import (
    start_fall_inference_stream_if_enabled,
)
from server.ropi_main_service.application.guide_tracking_runtime import (
    start_guide_tracking_stream_if_enabled,
)
from server.ropi_main_service.application.guide_navigation_runtime import (
    GuideNavigationRuntimeStarter,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)
from server.ropi_main_service.application.patrol_runtime import build_patrol_request_service
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService
from server.ropi_main_service.application.rpc_service_registry import SERVICE_REGISTRY
from server.ropi_main_service.application.visit_guide import VisitGuideService
from server.ropi_main_service.observability import configure_logging, log_event
from server.ropi_main_service.persistence.async_connection import close_pool
from server.ropi_main_service.persistence.background_db_writer import (
    get_default_background_db_writer,
)
from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_GUIDE_CREATE_TASK,
    MESSAGE_CODE_HEARTBEAT,
    MESSAGE_CODE_INTERNAL_RPC,
    MESSAGE_CODE_LOGIN,
    MESSAGE_CODE_PATROL_CREATE_TASK,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    MESSAGE_CODE_TASK_STATUS_QUERY,
    TCPFrame,
    TCPFrameError,
    build_frame,
    encode_frame,
    read_frame_from_stream,
)
from server.ropi_main_service.transport.frame_handlers import ControlFrameHandlers
from server.ropi_main_service.transport.frame_router import ControlFrameRouter
from server.ropi_main_service.transport.rpc_dispatcher import ControlRpcDispatcher
from server.ropi_main_service.transport.task_event_subscription_handler import (
    TaskEventSubscriptionHandler,
)
from server.ropi_main_service.transport.task_event_stream import TaskEventStreamHub
from server.ropi_main_service.transport.task_update_event_publisher import (
    TaskUpdateEventPublisher,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

CONTROL_SERVER_HOST = os.getenv("CONTROL_SERVER_HOST", "127.0.0.1")
CONTROL_SERVER_PORT = int(os.getenv("CONTROL_SERVER_PORT", "5050"))
AI_HEALTH_CONNECT_TIMEOUT_SEC = float(os.getenv("AI_HEALTH_CONNECT_TIMEOUT_SEC", "0.5"))
logger = logging.getLogger(__name__)


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value


def _ai_server_endpoint():
    host = (
        os.getenv("AI_FALL_EVIDENCE_HOST")
        or os.getenv("AI_GUIDE_TRACKING_STREAM_HOST")
        or os.getenv("AI_FALL_STREAM_HOST")
        or os.getenv("AI_SERVER_HOST")
    )
    host = str(host or "").strip()
    if not host:
        return None

    port = (
        os.getenv("AI_FALL_EVIDENCE_PORT")
        or os.getenv("AI_GUIDE_TRACKING_STREAM_PORT")
        or os.getenv("AI_FALL_STREAM_PORT")
        or "6000"
    )
    return host, int(port)


def _ai_not_configured_status():
    return {
        "ok": False,
        "disabled": True,
        "detail": "AI server endpoint is not configured.",
    }


def _check_ai_server_status():
    endpoint = _ai_server_endpoint()
    if endpoint is None:
        return _ai_not_configured_status()

    host, port = endpoint
    try:
        with socket.create_connection(
            (host, port),
            timeout=AI_HEALTH_CONNECT_TIMEOUT_SEC,
        ):
            return {"ok": True, "detail": {"host": host, "port": port}}
    except OSError as exc:
        return {"ok": False, "detail": str(exc)}


async def _async_check_ai_server_status():
    endpoint = _ai_server_endpoint()
    if endpoint is None:
        return _ai_not_configured_status()

    host, port = endpoint
    writer = None
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=AI_HEALTH_CONNECT_TIMEOUT_SEC,
        )
        return {"ok": True, "detail": {"host": host, "port": port}}
    except (OSError, asyncio.TimeoutError) as exc:
        return {"ok": False, "detail": str(exc)}
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()


class ControlServiceServer:
    def __init__(self, host: str = CONTROL_SERVER_HOST, port: int = CONTROL_SERVER_PORT):
        self.host = host
        self.port = port
        self._server = None
        self.db_writer = get_default_background_db_writer()
        self.delivery_workflow_task_manager = get_default_workflow_task_manager()
        self.guide_navigation_runtime_starter = GuideNavigationRuntimeStarter(
            workflow_task_manager=self.delivery_workflow_task_manager,
        )
        self.task_event_stream_hub = TaskEventStreamHub()
        self.task_event_subscription_handler = TaskEventSubscriptionHandler(
            stream_hub=self.task_event_stream_hub,
        )
        self.task_update_event_publisher = TaskUpdateEventPublisher(
            publish_event=(
                lambda event_type, payload: self.task_event_stream_hub.publish(
                    event_type,
                    payload,
                )
            ),
        )
        self.rpc_dispatcher = ControlRpcDispatcher(
            service_registry=SERVICE_REGISTRY,
            async_service_builder=self._build_runtime_service,
            task_update_publisher=self.task_update_event_publisher.publish_from_response,
            task_monitor_watermark_provider=(
                lambda: self.task_event_stream_hub.current_watermark()
            ),
        )
        self.frame_handlers = ControlFrameHandlers(
            service_registry=SERVICE_REGISTRY,
            rpc_dispatcher=self.rpc_dispatcher,
            task_update_event_publisher=self.task_update_event_publisher,
            auth_service_factory=lambda: AuthService(),
            ros_readiness_service_factory=lambda: RosRuntimeReadinessService(),
            delivery_request_service_builder=(
                lambda **kwargs: build_delivery_request_service(**kwargs)
            ),
            patrol_request_service_builder=(
                lambda **kwargs: build_patrol_request_service(**kwargs)
            ),
            sync_ai_status_checker=lambda: _check_ai_server_status(),
            async_ai_status_checker=lambda: _async_check_ai_server_status(),
        )
        self.frame_router = ControlFrameRouter(
            sync_routes=self._build_sync_frame_routes(),
            async_routes=self._build_async_frame_routes(),
            async_stream_required_codes={MESSAGE_CODE_TASK_EVENT_SUBSCRIBE},
        )
        self.fall_inference_stream_task = None
        self.guide_tracking_stream_task = None

    def dispatch_frame(self, frame: TCPFrame, *, loop=None) -> TCPFrame:
        result = self.frame_router.dispatch(frame, loop=loop)
        if not result.handled:
            return self._error_response(frame, result.error_code, result.error_message)
        return result.response

    async def async_dispatch_frame(self, frame: TCPFrame) -> TCPFrame:
        result = await self.frame_router.async_dispatch(frame)
        if not result.handled:
            return self._error_response(frame, result.error_code, result.error_message)
        return result.response

    def _build_sync_frame_routes(self):
        return {
            MESSAGE_CODE_HEARTBEAT: self.frame_handlers.handle_heartbeat,
            MESSAGE_CODE_LOGIN: self.frame_handlers.handle_login,
            MESSAGE_CODE_DELIVERY_CREATE_TASK: (
                self.frame_handlers.handle_delivery_create_task
            ),
            MESSAGE_CODE_PATROL_CREATE_TASK: (
                self.frame_handlers.handle_patrol_create_task
            ),
            MESSAGE_CODE_PATROL_RESUME_TASK: (
                self.frame_handlers.handle_patrol_resume_task
            ),
            MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY: (
                self.frame_handlers.handle_fall_evidence_image_query
            ),
            MESSAGE_CODE_GUIDE_CREATE_TASK: self.frame_handlers.handle_guide_create_task,
            MESSAGE_CODE_TASK_STATUS_QUERY: (
                self.frame_handlers.handle_task_status_query
            ),
            MESSAGE_CODE_INTERNAL_RPC: self.frame_handlers.handle_rpc,
        }

    def _build_async_frame_routes(self):
        return {
            MESSAGE_CODE_HEARTBEAT: self.frame_handlers.handle_heartbeat_async,
            MESSAGE_CODE_LOGIN: self.frame_handlers.handle_login_async,
            MESSAGE_CODE_DELIVERY_CREATE_TASK: (
                self.frame_handlers.handle_delivery_create_task_async
            ),
            MESSAGE_CODE_PATROL_CREATE_TASK: (
                self.frame_handlers.handle_patrol_create_task_async
            ),
            MESSAGE_CODE_PATROL_RESUME_TASK: (
                self.frame_handlers.handle_patrol_resume_task_async
            ),
            MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY: (
                self.frame_handlers.handle_fall_evidence_image_query_async
            ),
            MESSAGE_CODE_GUIDE_CREATE_TASK: (
                self.frame_handlers.handle_guide_create_task_async
            ),
            MESSAGE_CODE_TASK_STATUS_QUERY: (
                self.frame_handlers.handle_task_status_query_async
            ),
            MESSAGE_CODE_INTERNAL_RPC: self.frame_handlers.handle_rpc_async,
        }

    def _build_runtime_service(self, service_name, factory):
        if service_name == "visit_guide" and factory is VisitGuideService:
            return VisitGuideService(
                guide_navigation_starter=(
                    self.guide_navigation_runtime_starter.start_destination_navigation
                ),
            )
        return factory()

    async def start(self):
        self.db_writer.start()
        self.fall_inference_stream_task = start_fall_inference_stream_if_enabled(
            loop=asyncio.get_running_loop(),
            task_event_publisher=self.task_event_stream_hub,
            workflow_task_manager=self.delivery_workflow_task_manager,
        )
        self.guide_tracking_stream_task = start_guide_tracking_stream_if_enabled(
            loop=asyncio.get_running_loop(),
            task_event_publisher=self.task_event_stream_hub,
            workflow_task_manager=self.delivery_workflow_task_manager,
        )
        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                host=self.host,
                port=self.port,
            )
        except BaseException:
            await self._shutdown_resources()
            raise

        sockets = self._server.sockets or []
        bound_host, bound_port = self.host, self.port
        if sockets:
            sockname = sockets[0].getsockname()
            bound_host, bound_port = sockname[0], sockname[1]

        print(
            f"ROPI Control Service listening on {bound_host}:{bound_port}",
            flush=True,
        )
        log_event(
            logger,
            logging.INFO,
            "control_service_started",
            host=bound_host,
            port=bound_port,
        )
        return self._server

    async def serve_forever(self):
        if self._server is None:
            await self.start()

        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            await self._shutdown_resources()

    async def _shutdown_resources(self):
        try:
            await self.delivery_workflow_task_manager.shutdown()
        finally:
            try:
                await self.db_writer.stop()
            finally:
                await close_pool()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        try:
            while not reader.at_eof():
                try:
                    request_frame = await read_frame_from_stream(reader)
                except TCPFrameError:
                    break

                if request_frame.message_code == MESSAGE_CODE_TASK_EVENT_SUBSCRIBE:
                    response_frame = await self._handle_task_event_subscribe(
                        request_frame,
                        writer,
                    )
                    writer.write(self._encode_response(response_frame))
                    await writer.drain()
                    await self._replay_task_events_after_subscribe(
                        request_frame,
                        response_frame,
                    )
                    continue

                response_frame = await self._build_response_frame(request_frame)
                writer.write(self._encode_response(response_frame))
                await writer.drain()
        finally:
            await self.task_event_stream_hub.unsubscribe(writer=writer)
            writer.close()
            await writer.wait_closed()

    async def _handle_task_event_subscribe(
        self,
        frame: TCPFrame,
        writer: asyncio.StreamWriter,
    ) -> TCPFrame:
        result = await self.task_event_subscription_handler.subscribe(
            frame.payload or {},
            writer=writer,
        )
        if not result.accepted:
            return self._error_response(
                frame,
                result.error_code,
                result.error_message,
            )
        return self._success_response(frame, result.payload)

    async def _replay_task_events_after_subscribe(
        self,
        frame: TCPFrame,
        response_frame: TCPFrame,
    ):
        if response_frame.is_error:
            return

        await self.task_event_subscription_handler.replay_after_subscribe(
            frame.payload or {},
            subscribe_accepted=True,
        )

    async def _build_response_frame(self, frame: TCPFrame):
        try:
            return await self.async_dispatch_frame(frame)
        except Exception as exc:  # pragma: no cover
            return self._error_response(frame, "INTERNAL_ERROR", str(exc))

    @staticmethod
    def _encode_response(response: TCPFrame) -> bytes:
        serialized_payload = _serialize(response.payload)
        return encode_frame(
            TCPFrame(
                magic=response.magic,
                version=response.version,
                flags=response.flags,
                message_code=response.message_code,
                reserved=response.reserved,
                sequence_no=response.sequence_no,
                payload=serialized_payload,
            )
        )

    @staticmethod
    def _success_response(frame: TCPFrame, payload: dict) -> TCPFrame:
        return build_frame(
            frame.message_code,
            frame.sequence_no,
            payload,
            is_response=True,
        )

    @staticmethod
    def _error_response(frame: TCPFrame, error_code: str, error: str) -> TCPFrame:
        return build_frame(
            frame.message_code,
            frame.sequence_no,
            {
                "error_code": error_code,
                "error": error,
            },
            is_response=True,
            is_error=True,
        )


def parse_args():
    parser = argparse.ArgumentParser(description="ROPI Main Control Service TCP server")
    parser.add_argument("--host", default=CONTROL_SERVER_HOST)
    parser.add_argument("--port", type=int, default=CONTROL_SERVER_PORT)
    return parser.parse_args()


async def _run_server(host: str, port: int):
    server = ControlServiceServer(host, port)
    await server.serve_forever()


def main():
    args = parse_args()
    configure_logging()
    try:
        asyncio.run(_run_server(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
