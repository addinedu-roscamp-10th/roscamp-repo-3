import asyncio
from datetime import datetime

from server.ropi_main_service.transport.tcp_protocol import (
    TCPFrame,
    build_frame,
)


def _default_missing_dependency(*_args, **_kwargs):
    raise RuntimeError("ControlFrameHandlers dependency is not configured.")


class ControlFrameHandlers:
    def __init__(
        self,
        *,
        service_registry=None,
        rpc_dispatcher=None,
        task_update_event_publisher=None,
        auth_service_factory=_default_missing_dependency,
        ros_readiness_service_factory=_default_missing_dependency,
        delivery_request_service_builder=_default_missing_dependency,
        patrol_request_service_builder=_default_missing_dependency,
        sync_ai_status_checker=None,
        async_ai_status_checker=None,
    ):
        self.service_registry = service_registry or {}
        self.rpc_dispatcher = rpc_dispatcher
        self.task_update_event_publisher = task_update_event_publisher
        self.auth_service_factory = auth_service_factory
        self.ros_readiness_service_factory = ros_readiness_service_factory
        self.delivery_request_service_builder = delivery_request_service_builder
        self.patrol_request_service_builder = patrol_request_service_builder
        self.sync_ai_status_checker = sync_ai_status_checker or (
            lambda: {
                "ok": False,
                "disabled": True,
                "detail": "AI server endpoint is not configured.",
            }
        )
        self.async_ai_status_checker = (
            async_ai_status_checker or self._async_default_ai_status_checker
        )

    def handle_heartbeat(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        response_payload = self._base_heartbeat_payload()

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
                ros_result = self.ros_readiness_service_factory().get_status()
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
            response_payload["ai"] = self.sync_ai_status_checker()

        return self._success_response(frame, response_payload)

    async def handle_heartbeat_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        response_payload = self._base_heartbeat_payload()

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
                ros_result = await (
                    self.ros_readiness_service_factory().async_get_status()
                )
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
            response_payload["ai"] = await self.async_ai_status_checker()

        return self._success_response(frame, response_payload)

    def handle_login(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        ok, result = self.auth_service_factory().authenticate(
            payload.get("login_id", ""),
            payload.get("password", ""),
            payload.get("role", ""),
        )
        if ok:
            return self._success_response(frame, result)
        return self._error_response(frame, "AUTH_FAILED", str(result))

    async def handle_login_async(self, frame: TCPFrame, payload: dict) -> TCPFrame:
        ok, result = await self.auth_service_factory().async_authenticate(
            payload.get("login_id", ""),
            payload.get("password", ""),
            payload.get("role", ""),
        )
        if ok:
            return self._success_response(frame, result)
        return self._error_response(frame, "AUTH_FAILED", str(result))

    def handle_delivery_create_task(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        service = self.delivery_request_service_builder(
            loop=loop or asyncio.get_running_loop(),
        )

        try:
            result = service.create_delivery_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "DELIVERY_CREATE_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_delivery_create_task_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        service = self.delivery_request_service_builder(
            loop=asyncio.get_running_loop(),
        )

        try:
            result = await service.async_create_delivery_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "DELIVERY_CREATE_ERROR", str(exc))

        await self.task_update_event_publisher.publish_from_response(
            result,
            source="DELIVERY_CREATE",
        )
        return self._success_response(frame, result)

    def handle_patrol_create_task(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        service = self.patrol_request_service_builder(loop=loop)

        try:
            result = service.create_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_CREATE_ERROR", str(exc))

        if isinstance(result, dict):
            result = {**result, "cancellable": bool(result.get("cancellable", False))}
        return self._success_response(frame, result)

    async def handle_patrol_create_task_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        service = self.patrol_request_service_builder(loop=asyncio.get_running_loop())

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

    def handle_patrol_resume_task(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        service = self.patrol_request_service_builder(loop=loop)

        try:
            result = service.resume_patrol_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "PATROL_RESUME_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_patrol_resume_task_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        service = self.patrol_request_service_builder(loop=asyncio.get_running_loop())

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

    def handle_guide_create_task(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["visit_guide"]()
            result = service.create_guide_task(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_CREATE_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_guide_create_task_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["visit_guide"]()
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

    def handle_guide_resident_existence_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = service.lookup_residents(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_RESIDENT_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_guide_resident_existence_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = await service.async_lookup_residents(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_RESIDENT_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    def handle_guide_visitor_registration(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = service.register_visit(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_VISITOR_REGISTRATION_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_guide_visitor_registration_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = await service.async_register_visit(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_VISITOR_REGISTRATION_ERROR", str(exc))

        return self._success_response(frame, result)

    def handle_guide_visitor_care_history_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = service.get_care_history(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_CARE_HISTORY_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_guide_visitor_care_history_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["kiosk_visitor"]()
            result = await service.async_get_care_history(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_CARE_HISTORY_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    def handle_guide_staff_call_submission(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["staff_call"]()
            result = service.submit_staff_call(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_STAFF_CALL_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_guide_staff_call_submission_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["staff_call"]()
            result = await service.async_submit_staff_call(**payload)
        except Exception as exc:
            return self._error_response(frame, "GUIDE_STAFF_CALL_ERROR", str(exc))

        return self._success_response(frame, result)

    def handle_fall_evidence_image_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["fall_evidence_image"]()
            result = service.get_fall_evidence_image(**payload)
        except Exception as exc:
            return self._error_response(frame, "FALL_EVIDENCE_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_fall_evidence_image_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["fall_evidence_image"]()
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

    def handle_task_status_query(
        self,
        frame: TCPFrame,
        payload: dict,
        *,
        loop=None,
    ) -> TCPFrame:
        try:
            service = self.service_registry["task_monitor"]()
            result = service.get_task_status(task_id=payload.get("task_id"))
        except Exception as exc:
            return self._error_response(frame, "TASK_STATUS_QUERY_ERROR", str(exc))

        return self._success_response(frame, result)

    async def handle_task_status_query_async(
        self,
        frame: TCPFrame,
        payload: dict,
    ) -> TCPFrame:
        try:
            service = self.service_registry["task_monitor"]()
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

    async def handle_rpc_async(self, frame: TCPFrame, payload: dict):
        result = await self.rpc_dispatcher.async_dispatch(payload)
        if not result.ok:
            return self._error_response(
                frame,
                result.error_code,
                result.error_message,
            )

        return self._success_response(frame, result.payload)

    def handle_rpc(self, frame: TCPFrame, payload: dict, *, loop=None):
        result = self.rpc_dispatcher.dispatch(payload)
        if not result.ok:
            return self._error_response(
                frame,
                result.error_code,
                result.error_message,
            )

        return self._success_response(frame, result.payload)

    @staticmethod
    def _base_heartbeat_payload():
        return {
            "message": "메인 서버 연결 정상",
            "server_time": datetime.now().isoformat(timespec="seconds"),
        }

    async def _async_default_ai_status_checker(self):
        return self.sync_ai_status_checker()

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


__all__ = ["ControlFrameHandlers"]
