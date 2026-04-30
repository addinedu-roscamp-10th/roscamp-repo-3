from datetime import datetime

from server.ropi_main_service.persistence.repositories.visit_guide_repository import VisitGuideRepository
from server.ropi_main_service.application.guide_command import GuideCommandService
from server.ropi_main_service.application.guide_runtime import (
    DEFAULT_GUIDE_PINKY_ID,
    GuideRuntimeService,
)


class VisitGuideService:
    def __init__(
        self,
        repository=None,
        guide_command_service=None,
        guide_runtime_service=None,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.repository = repository or VisitGuideRepository()
        self.guide_command_service = guide_command_service or GuideCommandService()
        self.guide_runtime_service = guide_runtime_service or GuideRuntimeService(
            default_pinky_id=default_pinky_id
        )
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

    def begin_guide_session(
        self,
        *,
        patient: dict,
        member_id=None,
        pinky_id=None,
        command_type="WAIT_TARGET_TRACKING",
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        if not patient:
            return False, "먼저 어르신을 검색하세요.", None

        guide_task_id = self._build_guide_task_id(patient, pinky_id=pinky_id)
        registration_ok, registration_message = self.start_robot_guide(
            patient,
            member_id=member_id,
        )
        if not registration_ok:
            return False, registration_message, None

        command_ok, command_message, command_response = self.send_guide_command(
            task_id=guide_task_id,
            command_type=command_type,
            pinky_id=pinky_id,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        payload = {
            "task_id": guide_task_id,
            "pinky_id": str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id,
            "patient": self._build_patient_summary(patient),
            "command_type": command_type,
            "command_response": command_response,
            "request_registered": registration_ok,
        }
        if command_ok:
            return True, command_message or registration_message, payload
        return False, command_message or registration_message, payload

    async def async_begin_guide_session(
        self,
        *,
        patient: dict,
        member_id=None,
        pinky_id=None,
        command_type="WAIT_TARGET_TRACKING",
        target_track_id="",
        wait_timeout_sec=0,
        finish_reason="",
    ):
        if not patient:
            return False, "먼저 어르신을 검색하세요.", None

        guide_task_id = self._build_guide_task_id(patient, pinky_id=pinky_id)
        registration_ok, registration_message = await self.async_start_robot_guide(
            patient,
            member_id=member_id,
        )
        if not registration_ok:
            return False, registration_message, None

        command_ok, command_message, command_response = await self.async_send_guide_command(
            task_id=guide_task_id,
            command_type=command_type,
            pinky_id=pinky_id,
            target_track_id=target_track_id,
            wait_timeout_sec=wait_timeout_sec,
            finish_reason=finish_reason,
        )
        payload = {
            "task_id": guide_task_id,
            "pinky_id": str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id,
            "patient": self._build_patient_summary(patient),
            "command_type": command_type,
            "command_response": command_response,
            "request_registered": registration_ok,
        }
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
        response = self.guide_command_service.send(
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
        return False, message or "안내 제어 명령이 거부되었습니다.", response | {
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
        response = await self.guide_command_service.async_send(
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
        return False, message or "안내 제어 명령이 거부되었습니다.", response | {
            "reason_code": reason_code
        }

    def get_guide_runtime_status(self, *, pinky_id=None):
        status = self.guide_runtime_service.get_status(pinky_id=pinky_id)
        guide_runtime = (status or {}).get("guide_runtime") or {}
        if not guide_runtime.get("connected"):
            return False, "안내 추적 업데이트가 아직 수신되지 않았습니다.", status
        if guide_runtime.get("stale"):
            return False, "안내 추적 업데이트가 오래되어 최신 상태가 아닙니다.", status
        return True, "안내 추적 상태를 확인했습니다.", status

    async def async_get_guide_runtime_status(self, *, pinky_id=None):
        status = await self.guide_runtime_service.async_get_status(pinky_id=pinky_id)
        guide_runtime = (status or {}).get("guide_runtime") or {}
        if not guide_runtime.get("connected"):
            return False, "안내 추적 업데이트가 아직 수신되지 않았습니다.", status
        if guide_runtime.get("stale"):
            return False, "안내 추적 업데이트가 오래되어 최신 상태가 아닙니다.", status
        return True, "안내 추적 상태를 확인했습니다.", status

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
