from dataclasses import dataclass
from uuid import uuid4

from ui.utils.network.service_clients import StaffCallRemoteService


@dataclass(frozen=True)
class KioskStaffCallSubmissionResult:
    success: bool
    message: str


class KioskStaffCallController:
    def __init__(
        self,
        *,
        staff_call_service=None,
        kiosk_id,
        idempotency_key_factory=None,
    ):
        self.staff_call_service = staff_call_service or StaffCallRemoteService()
        self.kiosk_id = kiosk_id
        self.idempotency_key_factory = (
            idempotency_key_factory or self._default_idempotency_key
        )

    def submit(
        self,
        *,
        source_screen,
        current_patient=None,
        current_visitor_session=None,
        selected_patient=None,
    ):
        context = self._context(
            current_patient=current_patient,
            current_visitor_session=current_visitor_session,
            selected_patient=selected_patient,
        )
        try:
            response = self.staff_call_service.submit_staff_call(
                call_type="직원 호출",
                description=self._description(source_screen, context),
                idempotency_key=self.idempotency_key_factory(),
                visitor_id=context["visitor_id"],
                member_id=context["member_id"],
                kiosk_id=self.kiosk_id,
            )
        except Exception as exc:
            return KioskStaffCallSubmissionResult(
                success=False,
                message=f"서버 연결 중 오류가 발생했습니다: {exc}",
            )

        success = (response or {}).get("result_code") == "ACCEPTED"
        return KioskStaffCallSubmissionResult(
            success=success,
            message=(
                (response or {}).get("result_message")
                or ("직원이 곧 도착합니다." if success else "데스크에 문의해 주세요.")
            ),
        )

    def _context(
        self,
        *,
        current_patient=None,
        current_visitor_session=None,
        selected_patient=None,
    ):
        patient = selected_patient if selected_patient is not None else current_patient
        visitor_id = self._normalize_optional_id(
            (patient or {}).get("visitor_id")
            or (current_visitor_session or {}).get("visitor_id")
        )
        member_id = self._normalize_optional_id(
            (patient or {}).get("member_id")
            or (current_visitor_session or {}).get("member_id")
        )
        return {
            "visitor_id": visitor_id,
            "member_id": member_id,
            "name": str((patient or {}).get("name") or "").strip(),
            "room": str((patient or {}).get("room") or "").strip(),
        }

    def _description(self, source_screen, context):
        parts = [f"{source_screen}에서 직원 호출을 요청했습니다."]
        if context.get("name"):
            parts.append(f"대상={context['name']}")
        if context.get("room"):
            parts.append(f"호실={context['room']}")
        if context.get("visitor_id"):
            parts.append(f"visitor_id={context['visitor_id']}")
        if context.get("member_id"):
            parts.append(f"member_id={context['member_id']}")
        return " ".join(parts)

    @staticmethod
    def _normalize_optional_id(value):
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            normalized = int(raw)
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None

    @staticmethod
    def _default_idempotency_key():
        return f"kiosk_staff_call_{uuid4().hex}"


__all__ = ["KioskStaffCallController", "KioskStaffCallSubmissionResult"]
