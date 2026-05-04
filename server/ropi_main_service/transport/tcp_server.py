import argparse
import asyncio
import inspect
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
from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.goal_pose_navigation import GoalPoseNavigationService
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
from server.ropi_main_service.transport.task_event_stream import TaskEventStreamHub

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = PROJECT_ROOT / "server"

load_dotenv(SERVER_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")

CONTROL_SERVER_HOST = os.getenv("CONTROL_SERVER_HOST", "127.0.0.1")
CONTROL_SERVER_PORT = int(os.getenv("CONTROL_SERVER_PORT", "5050"))
AI_HEALTH_CONNECT_TIMEOUT_SEC = float(os.getenv("AI_HEALTH_CONNECT_TIMEOUT_SEC", "0.5"))
GUIDE_RUNTIME_READINESS_TIMEOUT_SEC = 1.0
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
        self.task_event_stream_hub = TaskEventStreamHub()
        self.fall_inference_stream_task = None
        self.guide_tracking_stream_task = None

    def dispatch_frame(self, frame: TCPFrame, *, loop=None) -> TCPFrame:
        payload = frame.payload or {}

        if frame.message_code == MESSAGE_CODE_HEARTBEAT:
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

        if frame.message_code == MESSAGE_CODE_LOGIN:
            ok, result = AuthService().authenticate(
                payload.get("login_id", ""),
                payload.get("password", ""),
                payload.get("role", ""),
            )
            if ok:
                return self._success_response(frame, result)
            return self._error_response(frame, "AUTH_FAILED", str(result))

        if frame.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK:
            return self._dispatch_delivery_create_task(frame, payload, loop=loop)

        if frame.message_code == MESSAGE_CODE_PATROL_CREATE_TASK:
            return self._dispatch_patrol_create_task(frame, payload, loop=loop)

        if frame.message_code == MESSAGE_CODE_PATROL_RESUME_TASK:
            return self._dispatch_patrol_resume_task(frame, payload, loop=loop)

        if frame.message_code == MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY:
            return self._dispatch_fall_evidence_image_query(frame, payload)

        if frame.message_code == MESSAGE_CODE_GUIDE_CREATE_TASK:
            return self._dispatch_guide_create_task(frame, payload)

        if frame.message_code == MESSAGE_CODE_TASK_STATUS_QUERY:
            return self._dispatch_task_status_query(frame, payload)

        if frame.message_code == MESSAGE_CODE_INTERNAL_RPC:
            return self._dispatch_rpc(frame, payload)

        return self._error_response(
            frame,
            "UNKNOWN_MESSAGE_CODE",
            f"지원하지 않는 message_code입니다: 0x{frame.message_code:04x}",
        )

    async def async_dispatch_frame(self, frame: TCPFrame) -> TCPFrame:
        payload = frame.payload or {}

        if frame.message_code == MESSAGE_CODE_HEARTBEAT:
            return await self._dispatch_heartbeat_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_LOGIN:
            ok, result = await AuthService().async_authenticate(
                payload.get("login_id", ""),
                payload.get("password", ""),
                payload.get("role", ""),
            )
            if ok:
                return self._success_response(frame, result)
            return self._error_response(frame, "AUTH_FAILED", str(result))

        if frame.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK:
            loop = asyncio.get_running_loop()
            return await self._dispatch_delivery_create_task_async(frame, payload, loop=loop)

        if frame.message_code == MESSAGE_CODE_PATROL_CREATE_TASK:
            return await self._dispatch_patrol_create_task_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_PATROL_RESUME_TASK:
            return await self._dispatch_patrol_resume_task_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY:
            return await self._dispatch_fall_evidence_image_query_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_GUIDE_CREATE_TASK:
            return await self._dispatch_guide_create_task_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_TASK_STATUS_QUERY:
            return await self._dispatch_task_status_query_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_INTERNAL_RPC:
            return await self._dispatch_rpc_async(frame, payload)

        if frame.message_code == MESSAGE_CODE_TASK_EVENT_SUBSCRIBE:
            return self._error_response(
                frame,
                "STREAM_REQUIRED",
                "task event subscribe는 persistent TCP stream에서만 처리됩니다.",
            )

        return self._error_response(
            frame,
            "UNKNOWN_MESSAGE_CODE",
            f"지원하지 않는 message_code입니다: 0x{frame.message_code:04x}",
        )

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

        await self._publish_task_updated_from_response(
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
        await self._publish_task_updated_from_response(
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

        await self._publish_task_updated_from_response(
            result,
            source="PATROL_RESUME",
            task_type="PATROL",
        )
        return self._success_response(frame, result)

    def _dispatch_guide_create_task(self, frame: TCPFrame, payload: dict) -> TCPFrame:
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
        await self._publish_task_updated_from_response(
            result,
            source="GUIDE_CREATE",
            task_type="GUIDE",
        )
        return self._success_response(frame, result)

    def _dispatch_fall_evidence_image_query(
        self,
        frame: TCPFrame,
        payload: dict,
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

    def _dispatch_task_status_query(self, frame: TCPFrame, payload: dict) -> TCPFrame:
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
        service_name = payload.get("service")
        method_name = payload.get("method")
        kwargs = payload.get("kwargs") or {}
        task_monitor_handoff_seq = self._task_monitor_handoff_seq(
            service_name,
            method_name,
        )

        factory = SERVICE_REGISTRY.get(service_name)
        if factory is None:
            return self._error_response(
                frame,
                "UNKNOWN_SERVICE",
                f"지원하지 않는 서비스입니다: {service_name}",
            )

        service = self._build_runtime_service(service_name, factory)
        async_method = getattr(service, f"async_{method_name}", None)
        method = async_method or getattr(service, method_name, None)
        if method is None:
            return self._error_response(
                frame,
                "UNKNOWN_METHOD",
                f"지원하지 않는 메서드입니다: {service_name}.{method_name}",
            )

        try:
            if inspect.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = await asyncio.to_thread(method, **kwargs)
        except Exception as exc:
            return self._error_response(frame, "RPC_ERROR", str(exc))

        if service_name == "task_request" and method_name in {
            "cancel_delivery_task",
            "cancel_task",
        }:
            source = (
                "DELIVERY_CANCEL"
                if method_name == "cancel_delivery_task"
                else "TASK_CANCEL"
            )
            await self._publish_task_updated_from_response(
                result,
                source=source,
            )

        if service_name == "visit_guide" and method_name in {
            "begin_guide_session",
            "send_guide_command",
            "finish_guide_session",
            "start_guide_driving",
        }:
            await self._publish_task_updated_from_response(
                self._extract_task_update_response(result),
                source="GUIDE_COMMAND",
                task_type="GUIDE",
            )

        result = self._attach_task_monitor_handoff_seq(result, task_monitor_handoff_seq)

        return self._success_response(frame, result)

    def _dispatch_rpc(self, frame: TCPFrame, payload: dict):
        service_name = payload.get("service")
        method_name = payload.get("method")
        kwargs = payload.get("kwargs") or {}
        task_monitor_handoff_seq = self._task_monitor_handoff_seq(
            service_name,
            method_name,
        )

        factory = SERVICE_REGISTRY.get(service_name)
        if factory is None:
            return self._error_response(
                frame,
                "UNKNOWN_SERVICE",
                f"지원하지 않는 서비스입니다: {service_name}",
            )

        service = factory()
        if not hasattr(service, method_name):
            return self._error_response(
                frame,
                "UNKNOWN_METHOD",
                f"지원하지 않는 메서드입니다: {service_name}.{method_name}",
            )

        try:
            result = getattr(service, method_name)(**kwargs)
        except Exception as exc:
            return self._error_response(frame, "RPC_ERROR", str(exc))

        result = self._attach_task_monitor_handoff_seq(result, task_monitor_handoff_seq)

        return self._success_response(frame, result)

    def _task_monitor_handoff_seq(self, service_name, method_name):
        if (
            service_name == "task_monitor"
            and method_name == "get_task_monitor_snapshot"
        ):
            return self.task_event_stream_hub.current_watermark()
        return None

    @staticmethod
    def _attach_task_monitor_handoff_seq(result, handoff_seq):
        if handoff_seq is None or not isinstance(result, dict):
            return result
        return {
            **result,
            "last_event_seq": handoff_seq,
        }

    @staticmethod
    def _extract_task_update_response(result):
        if isinstance(result, dict):
            return result
        if isinstance(result, (list, tuple)) and len(result) >= 3:
            payload = result[2]
            if isinstance(payload, dict):
                return payload
        return {}

    def _build_runtime_service(self, service_name, factory):
        if service_name == "visit_guide" and factory is VisitGuideService:
            return VisitGuideService(
                guide_navigation_starter=self._start_guide_navigation_background,
            )
        return factory()

    def _get_guide_runtime_readiness_status(self, *, pinky_id):
        try:
            return RosRuntimeReadinessService(
                runtime_config=DeliveryRuntimeConfig(pinky_id=pinky_id),
                arm_ids=[],
                include_guide=True,
                readiness_timeout_sec=GUIDE_RUNTIME_READINESS_TIMEOUT_SEC,
            ).get_status()
        except Exception as exc:
            return {
                "ready": False,
                "checks": [],
                "error": str(exc),
            }

    @staticmethod
    def _guide_runtime_ready(runtime_status, *, pinky_id):
        if not isinstance(runtime_status, dict):
            return False

        checks = runtime_status.get("checks")
        if not isinstance(checks, list):
            return False

        required_endpoints = {
            f"/ropi/control/{pinky_id}/navigate_to_goal",
            f"/ropi/control/{pinky_id}/guide_command",
        }
        readiness_by_endpoint = {}
        for check in checks:
            if not isinstance(check, dict):
                continue
            endpoint = check.get("action_name") or check.get("service_name")
            if endpoint in required_endpoints:
                readiness_by_endpoint[endpoint] = check.get("ready") is True

        return all(readiness_by_endpoint.get(endpoint) is True for endpoint in required_endpoints)

    @staticmethod
    def _build_guide_runtime_not_ready_response(*, task_id, pinky_id, runtime_status):
        error = ""
        if isinstance(runtime_status, dict):
            error = str(runtime_status.get("error") or "").strip()
        result_message = "안내 ROS 런타임이 준비되지 않았습니다."
        if error:
            result_message = f"{result_message} ({error})"

        return {
            "result_code": "REJECTED",
            "result_message": result_message,
            "reason_code": "GUIDE_RUNTIME_NOT_READY",
            "navigation_started": False,
            "task_id": task_id,
            "pinky_id": pinky_id,
            "nav_phase": "GUIDE_DESTINATION",
            "runtime_status": runtime_status,
        }

    def _start_guide_navigation_background(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        target_pinky_id = str(pinky_id or "").strip() or "pinky1"
        runtime_status = self._get_guide_runtime_readiness_status(pinky_id=target_pinky_id)
        if not self._guide_runtime_ready(runtime_status, pinky_id=target_pinky_id):
            return self._build_guide_runtime_not_ready_response(
                task_id=task_id,
                pinky_id=target_pinky_id,
                runtime_status=runtime_status,
            )

        loop = asyncio.get_running_loop()
        navigation_service = GoalPoseNavigationService(
            runtime_config=DeliveryRuntimeConfig(pinky_id=target_pinky_id),
        )
        background_task = self.delivery_workflow_task_manager.create_task(
            navigation_service.async_navigate(
                task_id=task_id,
                pinky_id=target_pinky_id,
                nav_phase="GUIDE_DESTINATION",
                goal_pose=goal_pose,
                timeout_sec=timeout_sec,
            ),
            name=f"guide_destination_navigation_{task_id}",
            loop=loop,
            cancel_on_shutdown=True,
        )
        background_task.add_done_callback(
            lambda task: self._handle_guide_navigation_done(task, task_id=task_id)
        )
        return {
            "result_code": "ACCEPTED",
            "result_message": "안내 목적지 이동을 시작했습니다.",
            "navigation_started": True,
            "task_id": task_id,
            "pinky_id": target_pinky_id,
            "nav_phase": "GUIDE_DESTINATION",
        }

    @staticmethod
    def _handle_guide_navigation_done(task, *, task_id):
        try:
            result = task.result()
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.WARNING,
                "guide_destination_navigation_cancelled",
                task_id=task_id,
                reason_code="GUIDE_NAVIGATION_TASK_CANCELLED",
            )
            return
        except Exception as exc:
            logger.exception(
                "guide destination navigation failed",
                extra={"task_id": task_id, "error": str(exc)},
            )
            return

        log_event(
            logger,
            logging.INFO,
            "guide_destination_navigation_finished",
            task_id=task_id,
            result_code=(result or {}).get("result_code"),
            result_message=(result or {}).get("result_message"),
            reason_code=(result or {}).get("reason_code"),
        )

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
        payload = frame.payload or {}
        ack = await self.task_event_stream_hub.subscribe(
            consumer_id=payload.get("consumer_id"),
            last_seq=payload.get("last_seq", 0),
            writer=writer,
            replay=False,
        )
        if ack.get("result_code") != "ACCEPTED":
            return self._error_response(
                frame,
                "TASK_EVENT_SUBSCRIBE_ERROR",
                ack.get("result_message") or "task event 구독 요청이 거부되었습니다.",
            )
        return self._success_response(frame, ack)

    async def _replay_task_events_after_subscribe(
        self,
        frame: TCPFrame,
        response_frame: TCPFrame,
    ):
        if response_frame.is_error:
            return

        payload = frame.payload or {}
        await self.task_event_stream_hub.replay(
            consumer_id=payload.get("consumer_id"),
            last_seq=payload.get("last_seq", 0),
        )

    async def _publish_task_updated_from_response(self, response, *, source, task_type=None):
        if not isinstance(response, dict):
            return

        task_id = response.get("task_id")
        if task_id in (None, ""):
            return

        cancellable = response.get("cancellable")
        resolved_task_type = task_type or response.get("task_type") or "DELIVERY"
        if resolved_task_type in {"GUIDE", "PATROL"} and cancellable is None:
            cancellable = False

        await self.task_event_stream_hub.publish(
            "TASK_UPDATED",
            {
                "source": source,
                "task_id": task_id,
                "task_type": resolved_task_type,
                "task_status": response.get("task_status"),
                "phase": response.get("phase") or response.get("task_status"),
                "assigned_robot_id": response.get("assigned_robot_id"),
                "latest_reason_code": response.get("reason_code"),
                "result_code": response.get("result_code"),
                "result_message": response.get("result_message"),
                "cancel_requested": response.get("cancel_requested"),
                "cancellable": cancellable,
            },
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
