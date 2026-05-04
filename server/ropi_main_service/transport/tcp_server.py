import argparse
import asyncio
import logging
import os
import socket
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from server.ropi_main_service.application.auth import AuthService
from server.ropi_main_service.application.action_feedback import RosActionFeedbackService
from server.ropi_main_service.application.caregiver import CaregiverService
from server.ropi_main_service.application.coordinate_config import CoordinateConfigService
from server.ropi_main_service.application.delivery_runtime import build_delivery_request_service
from server.ropi_main_service.application.fall_inference_runtime import (
    start_fall_inference_stream_if_enabled,
)
from server.ropi_main_service.application.guide_tracking_runtime import (
    start_guide_tracking_stream_if_enabled,
)
from server.ropi_main_service.application.fall_evidence_image import (
    FallEvidenceImageService,
)
from server.ropi_main_service.application.guide_navigation_runtime import (
    GuideNavigationRuntimeStarter,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)
from server.ropi_main_service.application.patrol_runtime import build_patrol_request_service
from server.ropi_main_service.application.inventory import InventoryService
from server.ropi_main_service.application.kiosk_visitor import KioskVisitorService
from server.ropi_main_service.application.patient import PatientService
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService
from server.ropi_main_service.application.staff_call import StaffCallService
from server.ropi_main_service.application.task_monitor import TaskMonitorService
from server.ropi_main_service.application.task_request import TaskRequestService
from server.ropi_main_service.application.visit_guide import VisitGuideService
from server.ropi_main_service.application.visitor_info import VisitorInfoService
from server.ropi_main_service.application.visitor_register import VisitorRegisterService
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


class CaregiverFacade:
    def __init__(self):
        self.service = CaregiverService()
        self.action_feedback_service = RosActionFeedbackService()

    def get_dashboard_bundle(self):
        flow_data = self.service.get_flow_board_data()
        self._attach_action_feedback(flow_data)
        return {
            "summary": self.service.get_dashboard_summary(),
            "robots": self.service.get_robot_board_data(),
            "flow_data": flow_data,
            "timeline_rows": self.service.get_timeline_data(),
        }

    async def async_get_dashboard_bundle(self):
        flow_data = await self.service.async_get_flow_board_data()
        await self._async_attach_action_feedback(flow_data)
        return {
            "summary": await self.service.async_get_dashboard_summary(),
            "robots": await self.service.async_get_robot_board_data(),
            "flow_data": flow_data,
            "timeline_rows": await self.service.async_get_timeline_data(),
        }

    def get_robot_status_bundle(self):
        return self.service.get_robot_status_bundle()

    async def async_get_robot_status_bundle(self):
        return await self.service.async_get_robot_status_bundle()

    def get_alert_log_bundle(self, **filters):
        return self.service.get_alert_log_bundle(**filters)

    async def async_get_alert_log_bundle(self, **filters):
        return await self.service.async_get_alert_log_bundle(**filters)

    def _attach_action_feedback(self, flow_data):
        for task in self._iter_feedback_target_tasks(flow_data):
            task_id = task.get("task_id")
            if not task_id:
                continue

            try:
                response = self.action_feedback_service.get_latest_feedback(task_id=task_id)
            except Exception:
                continue

            self._apply_feedback_response(task, response)

    async def _async_attach_action_feedback(self, flow_data):
        for task in self._iter_feedback_target_tasks(flow_data):
            task_id = task.get("task_id")
            if not task_id:
                continue

            try:
                response = await self.action_feedback_service.async_get_latest_feedback(task_id=task_id)
            except Exception:
                continue

            self._apply_feedback_response(task, response)

    @staticmethod
    def _iter_feedback_target_tasks(flow_data):
        for column_key in ("IN_PROGRESS", "CANCELING", "RUNNING"):
            for task in flow_data.get(column_key, []):
                if not isinstance(task, dict):
                    continue
                if task.get("task_status") not in ("RUNNING", "CANCEL_REQUESTED"):
                    continue
                yield task

    @classmethod
    def _apply_feedback_response(cls, task, response):
        feedback_records = response.get("feedback") or []
        if not feedback_records:
            return

        feedback = feedback_records[0]
        task["feedback"] = feedback
        task["feedback_summary"] = cls._build_feedback_summary(feedback)

    @staticmethod
    def _build_feedback_summary(feedback):
        payload = feedback.get("payload") or {}
        feedback_type = feedback.get("feedback_type")

        if feedback_type == "NAVIGATION_FEEDBACK":
            nav_status = payload.get("nav_status") or "NAVIGATION"
            distance = payload.get("distance_remaining_m")
            if distance is None:
                return str(nav_status)
            return f"{nav_status} / 남은 거리 {float(distance):.2f}m"

        if feedback_type == "MANIPULATION_FEEDBACK":
            processed_quantity = payload.get("processed_quantity")
            if processed_quantity is None:
                return "로봇팔 작업 중"
            return f"처리 수량 {processed_quantity}"

        return str(feedback_type or "ACTION_FEEDBACK")


SERVICE_REGISTRY = {
    "caregiver": CaregiverFacade,
    "coordinate_config": CoordinateConfigService,
    "patient": PatientService,
    "inventory": InventoryService,
    "kiosk_visitor": KioskVisitorService,
    "fall_evidence_image": FallEvidenceImageService,
    "task_monitor": TaskMonitorService,
    "task_request": TaskRequestService,
    "visit_guide": VisitGuideService,
    "visitor_info": VisitorInfoService,
    "visitor_register": VisitorRegisterService,
    "staff_call": StaffCallService,
}


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
            MESSAGE_CODE_HEARTBEAT: self._dispatch_heartbeat,
            MESSAGE_CODE_LOGIN: self._dispatch_login,
            MESSAGE_CODE_DELIVERY_CREATE_TASK: self._dispatch_delivery_create_task,
            MESSAGE_CODE_PATROL_CREATE_TASK: self._dispatch_patrol_create_task,
            MESSAGE_CODE_PATROL_RESUME_TASK: self._dispatch_patrol_resume_task,
            MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY: self._dispatch_fall_evidence_image_query,
            MESSAGE_CODE_GUIDE_CREATE_TASK: self._dispatch_guide_create_task,
            MESSAGE_CODE_TASK_STATUS_QUERY: self._dispatch_task_status_query,
            MESSAGE_CODE_INTERNAL_RPC: self._dispatch_rpc,
        }

    def _build_async_frame_routes(self):
        return {
            MESSAGE_CODE_HEARTBEAT: self._dispatch_heartbeat_async,
            MESSAGE_CODE_LOGIN: self._dispatch_login_async,
            MESSAGE_CODE_DELIVERY_CREATE_TASK: self._dispatch_delivery_create_task_async,
            MESSAGE_CODE_PATROL_CREATE_TASK: self._dispatch_patrol_create_task_async,
            MESSAGE_CODE_PATROL_RESUME_TASK: self._dispatch_patrol_resume_task_async,
            MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY: (
                self._dispatch_fall_evidence_image_query_async
            ),
            MESSAGE_CODE_GUIDE_CREATE_TASK: self._dispatch_guide_create_task_async,
            MESSAGE_CODE_TASK_STATUS_QUERY: self._dispatch_task_status_query_async,
            MESSAGE_CODE_INTERNAL_RPC: self._dispatch_rpc_async,
        }

    def _dispatch_heartbeat(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        response_payload = {
            "message": "메인 서버 연결 정상",
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }

        if payload.get("check_db"):
            try:
                from server.ropi_main_service.persistence.connection import test_connection

                db_ok, db_result = test_connection()
                response_payload["db"] = {
                    "ok": db_ok,
                    "detail": db_result,
                }
            except Exception as exc:
                response_payload["db"] = {
                    "ok": False,
                    "detail": str(exc),
                }

        if payload.get("check_ros"):
            try:
                ros_result = RosRuntimeReadinessService().get_status()
                response_payload["ros"] = {
                    "ok": bool(ros_result.get("ready")),
                    "detail": ros_result,
                }
            except Exception as exc:
                response_payload["ros"] = {
                    "ok": False,
                    "detail": str(exc),
                }

        if payload.get("check_ai"):
            response_payload["ai"] = _check_ai_server_status()

        return self._success_response(frame, response_payload)

    def _dispatch_login(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        ok, result = AuthService().authenticate(
            payload.get("login_id", ""),
            payload.get("password", ""),
            payload.get("role", ""),
        )
        if ok:
            return self._success_response(frame, result)
        return self._error_response(frame, "AUTH_FAILED", str(result))

    async def _dispatch_login_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        ok, result = await AuthService().async_authenticate(
            payload.get("login_id", ""),
            payload.get("password", ""),
            payload.get("role", ""),
        )
        if ok:
            return self._success_response(frame, result)
        return self._error_response(frame, "AUTH_FAILED", str(result))

    async def _dispatch_heartbeat_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        response_payload = {
            "message": "메인 서버 연결 정상",
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }

        if payload.get("check_db"):
            try:
                from server.ropi_main_service.persistence.async_connection import (
                    async_test_connection,
                )

                db_ok, db_result = await async_test_connection()
                response_payload["db"] = {
                    "ok": db_ok,
                    "detail": db_result,
                }
            except Exception as exc:
                response_payload["db"] = {
                    "ok": False,
                    "detail": str(exc),
                }

        if payload.get("check_ros"):
            try:
                ros_result = await RosRuntimeReadinessService().async_get_status()
                response_payload["ros"] = {
                    "ok": bool(ros_result.get("ready")),
                    "detail": ros_result,
                }
            except Exception as exc:
                response_payload["ros"] = {
                    "ok": False,
                    "detail": str(exc),
                }

        if payload.get("check_ai"):
            response_payload["ai"] = await _async_check_ai_server_status()

        return self._success_response(frame, response_payload)

    def _dispatch_delivery_create_task(self, frame: TCPFrame, payload: dict, *, loop=None) -> TCPFrame:
        service = build_delivery_request_service(loop=loop or asyncio.get_running_loop())

        try:
            result = service.create_delivery_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "DELIVERY_CREATE_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_delivery_create_task_async(self, frame: TCPFrame, payload: dict, *, loop=None) -> TCPFrame:
        service = build_delivery_request_service(loop=loop or asyncio.get_running_loop())

        try:
            result = await service.async_create_delivery_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "DELIVERY_CREATE_ERROR", str(exc))

        await self.task_update_event_publisher.publish_from_response(
            result,
            source="DELIVERY_CREATE",
        )
        return self._success_response(frame, result)

    def _dispatch_patrol_create_task(self, frame: TCPFrame, payload: dict, *, loop=None) -> TCPFrame:
        service = build_patrol_request_service(loop=loop)

        try:
            result = service.create_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_CREATE_ERROR", str(exc))

        if isinstance(result, dict):
            result = {**result, "cancellable": bool(result.get("cancellable", False))}
        return self._success_response(frame, result)

    async def _dispatch_patrol_create_task_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        service = build_patrol_request_service(loop=asyncio.get_running_loop())

        try:
            result = await service.async_create_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_CREATE_ERROR", str(exc))

        if isinstance(result, dict):
            result = {**result, "cancellable": bool(result.get("cancellable", False))}
        await self.task_update_event_publisher.publish_from_response(
            result,
            source="PATROL_CREATE",
            task_type="PATROL",
        )
        return self._success_response(frame, result)

    def _dispatch_patrol_resume_task(self, frame: TCPFrame, payload: dict, *, loop=None) -> TCPFrame:
        service = build_patrol_request_service(loop=loop)

        try:
            result = service.resume_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_RESUME_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_patrol_resume_task_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        service = build_patrol_request_service(loop=asyncio.get_running_loop())

        try:
            result = await service.async_resume_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_RESUME_ERROR", str(exc))

        await self.task_update_event_publisher.publish_from_response(
            result,
            source="PATROL_RESUME",
            task_type="PATROL",
        )
        return self._success_response(frame, result)

    def _dispatch_guide_create_task(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["visit_guide"]()
            result = service.create_guide_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_CREATE_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_guide_create_task_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["visit_guide"]()
            result = await service.async_create_guide_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_CREATE_ERROR", str(exc))

        if isinstance(result, dict):
            result = {**result, "cancellable": bool(result.get("cancellable", False))}
        await self.task_update_event_publisher.publish_from_response(
            result,
            source="GUIDE_CREATE",
            task_type="GUIDE",
        )
        return self._success_response(frame, result)

    def _dispatch_fall_evidence_image_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["fall_evidence_image"]()
            result = service.get_fall_evidence_image(**payload)
        except Exception as exc:
            return self._error_response(frame, "FALL_EVIDENCE_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_fall_evidence_image_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["fall_evidence_image"]()
            async_method = getattr(service, "async_get_fall_evidence_image", None)
            if async_method is not None:
                result = await async_method(**payload)
            else:
                result = await asyncio.to_thread(
                    service.get_fall_evidence_image,
                    **payload,
                )
        except Exception as exc:
            return self._error_response(frame, "FALL_EVIDENCE_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    def _dispatch_task_status_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["task_monitor"]()
            result = service.get_task_status(task_id=payload.get("task_id"))
        except Exception as exc:
            return self._error_response(frame, "TASK_STATUS_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_task_status_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = SERVICE_REGISTRY["task_monitor"]()
            async_method = getattr(service, "async_get_task_status", None)
            if async_method is not None:
                result = await async_method(task_id=payload.get("task_id"))
            else:
                result = await asyncio.to_thread(
                    service.get_task_status,
                    task_id=payload.get("task_id"),
                )
        except Exception as exc:
            return self._error_response(frame, "TASK_STATUS_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def _dispatch_rpc_async(self, frame: TCPFrame, payload: dict):
        result = await self.rpc_dispatcher.async_dispatch(payload)
        if not result.ok:
            return self._error_response(
                frame,
                result.error_code,
                result.error_message,
            )

        return self._success_response(frame, result.payload)

    def _dispatch_rpc(self, frame: TCPFrame, payload: dict, *, loop=None):
        result = self.rpc_dispatcher.dispatch(payload)
        if not result.ok:
            return self._error_response(
                frame,
                result.error_code,
                result.error_message,
            )

        return self._success_response(frame, result.payload)

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
