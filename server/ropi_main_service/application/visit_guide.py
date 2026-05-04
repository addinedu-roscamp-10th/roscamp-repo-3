from datetime import datetime

from server.ropi_main_service.persistence.repositories.guide_task_repository import (
    GuideTaskRepository,
)
from server.ropi_main_service.persistence.repositories.guide_task_lifecycle_repository import (
    GuideTaskLifecycleRepository,
)
from server.ropi_main_service.persistence.repositories.guide_task_navigation_repository import (
    GuideTaskNavigationRepository,
)
from server.ropi_main_service.persistence.repositories.visit_guide_repository import VisitGuideRepository
from server.ropi_main_service.application.guide_command import GuideCommandService
from server.ropi_main_service.application.goal_pose_navigation import GoalPoseNavigationService
from server.ropi_main_service.application.guide_runtime import (
    DEFAULT_GUIDE_PINKY_ID,
    GuideRuntimeService,
)
from server.ropi_main_service.application.guide_tracking_snapshot import (
    get_default_guide_tracking_snapshot_store,
)


DEFAULT_GUIDE_NAVIGATION_TIMEOUT_SEC = 120.0
GUIDE_DESTINATION_NAV_PHASE = "GUIDE_DESTINATION"
START_GUIDANCE_COMMAND = "START_GUIDANCE"


class VisitGuideService:
    def __init__(
        self,
        repository=None,
        guide_task_repository=None,
        guide_task_lifecycle_repository=None,
        guide_task_navigation_repository=None,
        guide_command_service=None,
        goal_pose_navigation_service=None,
        guide_navigation_starter=None,
        guide_runtime_service=None,
        guide_tracking_snapshot_store=None,
        guide_navigation_timeout_sec=DEFAULT_GUIDE_NAVIGATION_TIMEOUT_SEC,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.repository = repository or VisitGuideRepository()
        self.guide_task_repository = guide_task_repository or GuideTaskRepository(
            default_pinky_id=default_pinky_id
        )
        self.guide_task_lifecycle_repository = (
            guide_task_lifecycle_repository or GuideTaskLifecycleRepository()
        )
        self.guide_task_navigation_repository = (
            guide_task_navigation_repository or GuideTaskNavigationRepository()
        )
        self.guide_command_service = guide_command_service or GuideCommandService()
        self.goal_pose_navigation_service = (
            goal_pose_navigation_service or GoalPoseNavigationService()
        )
        self.guide_navigation_starter = guide_navigation_starter
        self.guide_runtime_service = guide_runtime_service or GuideRuntimeService(
            default_pinky_id=default_pinky_id
        )
        self.guide_tracking_snapshot_store = (
            guide_tracking_snapshot_store or get_default_guide_tracking_snapshot_store()
        )
        self.guide_navigation_timeout_sec = float(guide_navigation_timeout_sec)
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def search_patient(self, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword:
            return False, "검색어를 입력하세요.", None

        patient = self.repository.find_patient(keyword)
        if not patient:
            return False, "검색 결과가 없습니다.", None

        return True, "어르신 정보를 찾았습니다.", patient

    async def async_search_patient(self, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword:
            return False, "검색어를 입력하세요.", None

        patient = await self.repository.async_find_patient(keyword)
        if not patient:
            return False, "검색 결과가 없습니다.", None

        return True, "어르신 정보를 찾았습니다.", patient

    def start_robot_guide(self, patient: dict, member_id=None):
        if not patient:
            return False, "먼저 어르신을 검색하세요."

        return self.repository.create_robot_guide_event(
            patient_name=patient.get("name", "-"),
            room_no=patient.get("room", "-"),
            member_id=member_id,
        )

    async def async_start_robot_guide(self, patient: dict, member_id=None):
        if not patient:
            return False, "먼저 어르신을 검색하세요."

        return await self.repository.async_create_robot_guide_event(
            patient_name=patient.get("name", "-"),
            room_no=patient.get("room", "-"),
            member_id=member_id,
        )

    def create_guide_task(
        self,
        *,
        request_id,
        visitor_id,
        idempotency_key,
        priority="NORMAL",
    ):
        invalid_response = self._validate_create_guide_task_request(
            request_id=request_id,
            visitor_id=visitor_id,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        return self.guide_task_repository.create_guide_task(
            request_id=str(request_id).strip(),
            visitor_id=self._normalize_positive_id(visitor_id),
            priority=str(priority or "NORMAL").strip().upper() or "NORMAL",
            idempotency_key=str(idempotency_key).strip(),
        )

    async def async_create_guide_task(
        self,
        *,
        request_id,
        visitor_id,
        idempotency_key,
        priority="NORMAL",
    ):
        invalid_response = self._validate_create_guide_task_request(
            request_id=request_id,
            visitor_id=visitor_id,
            idempotency_key=idempotency_key,
        )
        if invalid_response is not None:
            return invalid_response

        return await self.guide_task_repository.async_create_guide_task(
            request_id=str(request_id).strip(),
            visitor_id=self._normalize_positive_id(visitor_id),
            priority=str(priority or "NORMAL").strip().upper() or "NORMAL",
            idempotency_key=str(idempotency_key).strip(),
        )

    def begin_guide_session(
        self,
        *,
        patient: dict,
        member_id=None,
        visitor_id=None,
        request_id=None,
        idempotency_key=None,
        pinky_id=None,
        command_type="WAIT_TARGET_TRACKING",
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        if not patient:
            return False, "먼저 어르신을 검색하세요.", None

        create_response = self._create_task_or_member_event(
            patient=patient,
            member_id=member_id,
            visitor_id=visitor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        if not create_response["ok"]:
            return False, create_response["message"], None

        guide_task_id = create_response["task_id"]
        registration_message = create_response["message"]
        target_pinky_id = self._resolve_session_pinky_id(pinky_id, create_response)

        command_ok, command_message, command_response = self.send_guide_command(
            task_id=guide_task_id,
            command_type=command_type,
            pinky_id=target_pinky_id,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        payload = {
            "task_id": guide_task_id,
            "pinky_id": target_pinky_id,
            "patient": self._build_patient_summary(patient),
            "command_type": command_type,
            "command_response": command_response,
            "request_registered": True,
        }
        payload.update(create_response["payload"])
        if command_ok:
            return True, command_message or registration_message, payload
        return False, command_message or registration_message, payload

    async def async_begin_guide_session(
        self,
        *,
        patient: dict,
        member_id=None,
        visitor_id=None,
        request_id=None,
        idempotency_key=None,
        pinky_id=None,
        command_type="WAIT_TARGET_TRACKING",
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        if not patient:
            return False, "먼저 어르신을 검색하세요.", None

        create_response = await self._async_create_task_or_member_event(
            patient=patient,
            member_id=member_id,
            visitor_id=visitor_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        if not create_response["ok"]:
            return False, create_response["message"], None

        guide_task_id = create_response["task_id"]
        registration_message = create_response["message"]
        target_pinky_id = self._resolve_session_pinky_id(pinky_id, create_response)

        command_ok, command_message, command_response = await self.async_send_guide_command(
            task_id=guide_task_id,
            command_type=command_type,
            pinky_id=target_pinky_id,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        payload = {
            "task_id": guide_task_id,
            "pinky_id": target_pinky_id,
            "patient": self._build_patient_summary(patient),
            "command_type": command_type,
            "command_response": command_response,
            "request_registered": True,
        }
        payload.update(create_response["payload"])
        if command_ok:
            return True, command_message or registration_message, payload
        return False, command_message or registration_message, payload

    def finish_guide_session(
        self,
        *,
        task_id,
        pinky_id=None,
        target_track_id="",
        finish_reason="",
    ):
        return self.send_guide_command(
            task_id=task_id,
            command_type="FINISH_GUIDANCE",
            pinky_id=pinky_id,
            target_track_id=target_track_id,
            finish_reason=finish_reason,
        )

    async def async_finish_guide_session(
        self,
        *,
        task_id,
        pinky_id=None,
        target_track_id="",
        finish_reason="",
    ):
        return await self.async_send_guide_command(
            task_id=task_id,
            command_type="FINISH_GUIDANCE",
            pinky_id=pinky_id,
            target_track_id=target_track_id,
            finish_reason=finish_reason,
        )

    def start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
        navigation_timeout_sec=None,
    ):
        invalid = self._validate_start_guide_driving_request(
            task_id=task_id,
            target_track_id=target_track_id,
        )
        if invalid is not None:
            return False, invalid["result_message"], invalid

        context = self.guide_task_navigation_repository.get_guide_driving_context(
            task_id=task_id,
        )
        if context.get("result_code") != "ACCEPTED":
            return False, context.get("result_message") or "안내 주행을 시작할 수 없습니다.", context

        target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
        try:
            navigation_response = self._start_guide_destination_navigation(
                task_id=task_id,
                pinky_id=target_pinky_id,
                goal_pose=context.get("goal_pose"),
                timeout_sec=navigation_timeout_sec,
            )
        except Exception as exc:
            response = self._build_guide_navigation_failure_response(
                context=context,
                navigation_response=self._build_guide_navigation_transport_error_response(exc),
                target_track_id=target_track_id,
                pinky_id=target_pinky_id,
            )
            return False, response["result_message"], response

        if not self._navigation_dispatch_accepted(navigation_response):
            response = self._build_guide_navigation_failure_response(
                context=context,
                navigation_response=navigation_response,
                target_track_id=target_track_id,
                pinky_id=target_pinky_id,
            )
            return False, response["result_message"], response

        command_ok, command_message, command_response = self.send_guide_command(
            task_id=task_id,
            pinky_id=target_pinky_id,
            command_type=START_GUIDANCE_COMMAND,
            target_track_id=target_track_id,
        )
        response = self._build_guide_driving_response(
            context=context,
            command_response=command_response,
            target_track_id=target_track_id,
            pinky_id=target_pinky_id,
        )
        if not command_ok:
            response["navigation_response"] = navigation_response
            return False, command_message, response

        response["navigation_response"] = navigation_response

        response["result_code"] = "ACCEPTED"
        response["result_message"] = "안내 주행을 시작했습니다."
        return True, response["result_message"], response

    async def async_start_guide_driving(
        self,
        *,
        task_id,
        target_track_id,
        pinky_id=None,
        navigation_timeout_sec=None,
    ):
        invalid = self._validate_start_guide_driving_request(
            task_id=task_id,
            target_track_id=target_track_id,
        )
        if invalid is not None:
            return False, invalid["result_message"], invalid

        context = await self.guide_task_navigation_repository.async_get_guide_driving_context(
            task_id=task_id,
        )
        if context.get("result_code") != "ACCEPTED":
            return False, context.get("result_message") or "안내 주행을 시작할 수 없습니다.", context

        target_pinky_id = self._resolve_guide_driving_pinky_id(pinky_id, context)
        try:
            navigation_response = await self._async_start_guide_destination_navigation(
                task_id=task_id,
                pinky_id=target_pinky_id,
                goal_pose=context.get("goal_pose"),
                timeout_sec=navigation_timeout_sec,
            )
        except Exception as exc:
            response = self._build_guide_navigation_failure_response(
                context=context,
                navigation_response=self._build_guide_navigation_transport_error_response(exc),
                target_track_id=target_track_id,
                pinky_id=target_pinky_id,
            )
            return False, response["result_message"], response

        if not self._navigation_dispatch_accepted(navigation_response):
            response = self._build_guide_navigation_failure_response(
                context=context,
                navigation_response=navigation_response,
                target_track_id=target_track_id,
                pinky_id=target_pinky_id,
            )
            return False, response["result_message"], response

        command_ok, command_message, command_response = await self.async_send_guide_command(
            task_id=task_id,
            pinky_id=target_pinky_id,
            command_type=START_GUIDANCE_COMMAND,
            target_track_id=target_track_id,
        )
        response = self._build_guide_driving_response(
            context=context,
            command_response=command_response,
            target_track_id=target_track_id,
            pinky_id=target_pinky_id,
        )
        if not command_ok:
            response["navigation_response"] = navigation_response
            return False, command_message, response

        response["navigation_response"] = navigation_response

        response["result_code"] = "ACCEPTED"
        response["result_message"] = "안내 주행을 시작했습니다."
        return True, response["result_message"], response

    def send_guide_command(
        self,
        *,
        task_id,
        command_type,
        pinky_id=None,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        try:
            response = self.guide_command_service.send(
                task_id=task_id,
                pinky_id=pinky_id or self.default_pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            response = self._build_guide_command_transport_error_response(exc)
        response = self._attach_guide_command_lifecycle(
            response=response,
            task_id=task_id,
            pinky_id=pinky_id or self.default_pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        accepted = bool((response or {}).get("accepted"))
        message = str((response or {}).get("message") or "").strip()
        reason_code = str((response or {}).get("reason_code") or "").strip()
        if accepted:
            return True, message or "안내 제어 명령이 수락되었습니다.", response
        return False, message or "안내 제어 명령이 거부되었습니다.", (response or {}) | {
            "reason_code": reason_code
        }

    async def async_send_guide_command(
        self,
        *,
        task_id,
        command_type,
        pinky_id=None,
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        try:
            response = await self.guide_command_service.async_send(
                task_id=task_id,
                pinky_id=pinky_id or self.default_pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
            )
        except Exception as exc:
            response = self._build_guide_command_transport_error_response(exc)
        response = await self._async_attach_guide_command_lifecycle(
            response=response,
            task_id=task_id,
            pinky_id=pinky_id or self.default_pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        accepted = bool((response or {}).get("accepted"))
        message = str((response or {}).get("message") or "").strip()
        reason_code = str((response or {}).get("reason_code") or "").strip()
        if accepted:
            return True, message or "안내 제어 명령이 수락되었습니다.", response
        return False, message or "안내 제어 명령이 거부되었습니다.", (response or {}) | {
            "reason_code": reason_code
        }

    def get_tracking_status(self, *, task_id=None, pinky_id=None):
        snapshot = self.guide_tracking_snapshot_store.get(
            task_id=task_id,
            pinky_id=pinky_id or self.default_pinky_id,
        )
        return self._build_tracking_status_response(
            snapshot=snapshot,
            task_id=task_id,
            pinky_id=pinky_id or self.default_pinky_id,
        )

    async def async_get_tracking_status(self, *, task_id=None, pinky_id=None):
        return self.get_tracking_status(task_id=task_id, pinky_id=pinky_id)

    def get_guide_runtime_status(self, *, pinky_id=None):
        status = self.guide_runtime_service.get_status(pinky_id=pinky_id)
        guide_runtime = (status or {}).get("guide_runtime") or {}
        if not guide_runtime.get("connected"):
            return False, "안내 추적 업데이트가 아직 수신되지 않았습니다.", status
        if guide_runtime.get("stale"):
            return False, "안내 추적 업데이트가 오래되어 최신 상태가 아닙니다.", status
        return True, "안내 추적 상태를 확인했습니다.", status

    @classmethod
    def _build_tracking_status_response(cls, *, snapshot, task_id=None, pinky_id=None):
        if not snapshot:
            return (
                False,
                "안내 대상 확인 대기 중입니다.",
                {
                    "result_code": "PENDING",
                    "result_message": "안내 대상 확인 대기 중입니다.",
                    "reason_code": "TRACKING_SNAPSHOT_NOT_FOUND",
                    "task_id": cls._normalize_positive_id(task_id),
                    "pinky_id": str(pinky_id or "").strip() or None,
                    "tracking_status": "NOT_TRACKING",
                    "active_track_id": None,
                    "target_track_id": None,
                },
            )

        response = dict(snapshot)
        active_track_id = str(response.get("active_track_id") or "").strip() or None
        adopted_target_track_id = (
            str(response.get("adopted_target_track_id") or "").strip() or None
        )
        tracking_status = str(response.get("tracking_status") or "").strip().upper()
        acquired = tracking_status == "TRACKING" and active_track_id is not None
        result_code = "FOUND" if acquired else "PENDING"
        message = (
            "안내 대상을 확인했습니다."
            if acquired
            else "안내 대상 확인 대기 중입니다."
        )

        response.update(
            {
                "result_code": result_code,
                "result_message": message,
                "reason_code": None if acquired else "TRACKING_TARGET_NOT_ACQUIRED",
                "active_track_id": active_track_id,
                "target_track_id": adopted_target_track_id or active_track_id,
                "tracking_status": tracking_status or "NOT_TRACKING",
            }
        )
        return acquired, message, response

    async def async_get_guide_runtime_status(self, *, pinky_id=None):
        status = await self.guide_runtime_service.async_get_status(pinky_id=pinky_id)
        guide_runtime = (status or {}).get("guide_runtime") or {}
        if not guide_runtime.get("connected"):
            return False, "안내 추적 업데이트가 아직 수신되지 않았습니다.", status
        if guide_runtime.get("stale"):
            return False, "안내 추적 업데이트가 오래되어 최신 상태가 아닙니다.", status
        return True, "안내 추적 상태를 확인했습니다.", status

    @staticmethod
    def _build_guide_command_transport_error_response(exc):
        message = str(exc).strip() or "안내 제어 명령 전송에 실패했습니다."
        return {
            "accepted": False,
            "result_code": "REJECTED",
            "result_message": message,
            "reason_code": "GUIDE_COMMAND_TRANSPORT_ERROR",
            "message": message,
        }

    def _attach_guide_command_lifecycle(
        self,
        *,
        response,
        task_id,
        pinky_id,
        command_type,
        target_track_id,
        wait_timeout_sec,
        finish_reason,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        lifecycle_result = self.guide_task_lifecycle_repository.record_command_result(
            task_id=task_id,
            pinky_id=pinky_id,
            command_type=command_type,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
            command_response=response,
        )
        return self._merge_command_lifecycle_response(response, lifecycle_result)

    async def _async_attach_guide_command_lifecycle(
        self,
        *,
        response,
        task_id,
        pinky_id,
        command_type,
        target_track_id,
        wait_timeout_sec,
        finish_reason,
    ):
        if self._normalize_positive_id(task_id) is None:
            return response

        lifecycle_result = (
            await self.guide_task_lifecycle_repository.async_record_command_result(
                task_id=task_id,
                pinky_id=pinky_id,
                command_type=command_type,
                target_track_id=target_track_id,
                wait_timeout_sec=wait_timeout_sec,
                finish_reason=finish_reason,
                command_response=response,
            )
        )
        return self._merge_command_lifecycle_response(response, lifecycle_result)

    @staticmethod
    def _merge_command_lifecycle_response(command_response, lifecycle_result):
        response = dict(command_response or {}) if isinstance(command_response, dict) else {}
        if lifecycle_result:
            response["lifecycle_result"] = lifecycle_result
            for key in (
                "result_code",
                "result_message",
                "reason_code",
                "task_id",
                "task_type",
                "task_status",
                "phase",
                "assigned_robot_id",
                "guide_phase",
                "target_track_id",
            ):
                if lifecycle_result.get(key) is not None:
                    response[key] = lifecycle_result[key]
        return response

    def _start_guide_destination_navigation(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        timeout = self._normalize_navigation_timeout(timeout_sec)
        if self.guide_navigation_starter is not None:
            return self.guide_navigation_starter(
                task_id=task_id,
                pinky_id=pinky_id,
                goal_pose=goal_pose,
                timeout_sec=timeout,
            )

        return self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            pinky_id=pinky_id,
            nav_phase=GUIDE_DESTINATION_NAV_PHASE,
            goal_pose=goal_pose,
            timeout_sec=timeout,
        )

    async def _async_start_guide_destination_navigation(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        timeout = self._normalize_navigation_timeout(timeout_sec)
        if self.guide_navigation_starter is not None:
            result = self.guide_navigation_starter(
                task_id=task_id,
                pinky_id=pinky_id,
                goal_pose=goal_pose,
                timeout_sec=timeout,
            )
            if hasattr(result, "__await__"):
                return await result
            return result

        return await self.goal_pose_navigation_service.async_navigate(
            task_id=task_id,
            pinky_id=pinky_id,
            nav_phase=GUIDE_DESTINATION_NAV_PHASE,
            goal_pose=goal_pose,
            timeout_sec=timeout,
        )

    def _normalize_navigation_timeout(self, timeout_sec):
        if timeout_sec is None:
            return self.guide_navigation_timeout_sec
        return float(timeout_sec)

    @staticmethod
    def _navigation_dispatch_accepted(navigation_response):
        result_code = str((navigation_response or {}).get("result_code") or "").strip().upper()
        return result_code in {"ACCEPTED", "SUCCESS"}

    @staticmethod
    def _build_guide_navigation_transport_error_response(exc):
        message = str(exc).strip() or "안내 목적지 이동 시작에 실패했습니다."
        return {
            "result_code": "REJECTED",
            "result_message": message,
            "reason_code": "GUIDE_DESTINATION_NAVIGATION_TRANSPORT_ERROR",
        }

    @staticmethod
    def _resolve_guide_driving_pinky_id(pinky_id, context):
        return (
            str(pinky_id or context.get("assigned_robot_id") or DEFAULT_GUIDE_PINKY_ID).strip()
            or DEFAULT_GUIDE_PINKY_ID
        )

    @staticmethod
    def _build_guide_navigation_failure_response(
        *,
        context,
        navigation_response,
        target_track_id,
        pinky_id,
    ):
        message = (
            (navigation_response or {}).get("result_message")
            or "안내 목적지 이동 시작이 수락되지 않았습니다."
        )
        return {
            "result_code": (navigation_response or {}).get("result_code") or "REJECTED",
            "result_message": message,
            "reason_code": (navigation_response or {}).get("reason_code"),
            "task_id": context.get("task_id"),
            "task_type": "GUIDE",
            "task_status": context.get("task_status"),
            "phase": context.get("phase"),
            "guide_phase": context.get("guide_phase"),
            "assigned_robot_id": context.get("assigned_robot_id") or pinky_id,
            "target_track_id": target_track_id,
            "destination_id": context.get("destination_id"),
            "navigation_response": navigation_response,
            "command_response": None,
        }

    @staticmethod
    def _build_guide_driving_response(*, context, command_response, target_track_id, pinky_id):
        response = {
            "result_code": command_response.get("result_code"),
            "result_message": command_response.get("result_message"),
            "reason_code": command_response.get("reason_code"),
            "task_id": command_response.get("task_id") or context.get("task_id"),
            "task_type": "GUIDE",
            "task_status": command_response.get("task_status") or context.get("task_status"),
            "phase": command_response.get("phase") or context.get("phase"),
            "guide_phase": command_response.get("guide_phase"),
            "assigned_robot_id": command_response.get("assigned_robot_id") or pinky_id,
            "target_track_id": command_response.get("target_track_id") or target_track_id,
            "destination_id": context.get("destination_id"),
            "command_response": command_response,
        }
        return response

    @classmethod
    def _validate_start_guide_driving_request(cls, *, task_id, target_track_id):
        if cls._normalize_positive_id(task_id) is None:
            return cls._build_guide_driving_invalid_response(
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
            )
        if cls._is_blank(target_track_id):
            return cls._build_guide_driving_invalid_response(
                result_message="target_track_id가 필요합니다.",
                reason_code="TARGET_TRACK_ID_REQUIRED",
                task_id=task_id,
            )
        return None

    @staticmethod
    def _build_guide_driving_invalid_response(*, result_message, reason_code, task_id=None):
        return {
            "result_code": "INVALID_REQUEST",
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": "GUIDE",
        }

    def _create_task_or_member_event(
        self,
        *,
        patient,
        member_id,
        visitor_id,
        request_id,
        idempotency_key,
    ):
        normalized_visitor_id = visitor_id or (patient or {}).get("visitor_id")
        if normalized_visitor_id and request_id and idempotency_key:
            response = self.create_guide_task(
                request_id=request_id,
                visitor_id=normalized_visitor_id,
                idempotency_key=idempotency_key,
            )
            return self._guide_task_response_to_session_create_result(response)

        guide_task_id = self._build_guide_task_id(patient)
        ok, message = self.start_robot_guide(patient, member_id=member_id)
        return {
            "ok": ok,
            "message": message,
            "task_id": guide_task_id,
            "payload": {},
        }

    async def _async_create_task_or_member_event(
        self,
        *,
        patient,
        member_id,
        visitor_id,
        request_id,
        idempotency_key,
    ):
        normalized_visitor_id = visitor_id or (patient or {}).get("visitor_id")
        if normalized_visitor_id and request_id and idempotency_key:
            response = await self.async_create_guide_task(
                request_id=request_id,
                visitor_id=normalized_visitor_id,
                idempotency_key=idempotency_key,
            )
            return self._guide_task_response_to_session_create_result(response)

        guide_task_id = self._build_guide_task_id(patient)
        ok, message = await self.async_start_robot_guide(patient, member_id=member_id)
        return {
            "ok": ok,
            "message": message,
            "task_id": guide_task_id,
            "payload": {},
        }

    @staticmethod
    def _guide_task_response_to_session_create_result(response):
        accepted = (response or {}).get("result_code") == "ACCEPTED"
        return {
            "ok": accepted,
            "message": (response or {}).get("result_message") or "안내 요청이 접수되었습니다.",
            "task_id": (response or {}).get("task_id"),
            "payload": dict(response or {}),
        }

    def _resolve_session_pinky_id(self, pinky_id, create_response):
        assigned_robot_id = (create_response.get("payload") or {}).get("assigned_robot_id")
        return (
            str(pinky_id or assigned_robot_id or self.default_pinky_id).strip()
            or self.default_pinky_id
        )

    @classmethod
    def _validate_create_guide_task_request(cls, *, request_id, visitor_id, idempotency_key):
        if cls._is_blank(request_id):
            return cls._build_guide_task_response(
                result_code="INVALID_REQUEST",
                result_message="request_id가 필요합니다.",
                reason_code="REQUEST_ID_INVALID",
            )
        if cls._normalize_positive_id(visitor_id) is None:
            return cls._build_guide_task_response(
                result_code="INVALID_REQUEST",
                result_message="visitor_id가 올바르지 않습니다.",
                reason_code="VISITOR_ID_INVALID",
            )
        if cls._is_blank(idempotency_key):
            return cls._build_guide_task_response(
                result_code="INVALID_REQUEST",
                result_message="idempotency_key가 필요합니다.",
                reason_code="IDEMPOTENCY_KEY_INVALID",
            )
        return None

    @staticmethod
    def _build_guide_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        resident_name=None,
        room_no=None,
        destination_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "resident_name": resident_name,
            "room_no": room_no,
            "destination_id": destination_id,
        }

    @staticmethod
    def _normalize_positive_id(value):
        try:
            normalized = int(str(value or "").strip())
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @staticmethod
    def _is_blank(value) -> bool:
        return not str(value or "").strip()

    @staticmethod
    def _build_patient_summary(patient: dict):
        return {
            "name": str((patient or {}).get("name", "-")).strip() or "-",
            "member_id": str((patient or {}).get("member_id", "-")).strip() or "-",
            "room": str((patient or {}).get("room", "-")).strip() or "-",
        }

    def _build_guide_task_id(self, patient: dict, *, pinky_id=None):
        member_id = str((patient or {}).get("member_id", "")).strip() or "unknown"
        room_no = str((patient or {}).get("room", "")).strip().replace(" ", "") or "unknown"
        target_pinky_id = str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"guide_{target_pinky_id}_{member_id}_{room_no}_{timestamp}"


__all__ = ["VisitGuideService"]
