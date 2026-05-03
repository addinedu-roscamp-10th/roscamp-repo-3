import asyncio

from server.ropi_main_service.persistence.repositories.staff_call_repository import (
    StaffCallRepository,
    VisitorSessionInvalidError,
)


MAX_STAFF_CALL_DESCRIPTION_LENGTH = 500


class StaffCallService:
    def __init__(self, repository=None):
        self.repository = repository or StaffCallRepository()

    def submit_staff_call(
        self,
        *,
        call_type: str,
        description: str = None,
        detail: str = None,
        idempotency_key: str = None,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        return asyncio.run(
            self.async_submit_staff_call(
                call_type=call_type,
                description=description,
                detail=detail,
                idempotency_key=idempotency_key,
                visitor_id=visitor_id,
                member_id=member_id,
                kiosk_id=kiosk_id,
            )
        )

    async def async_submit_staff_call(
        self,
        call_type: str,
        detail: str = None,
        member_id=None,
        *,
        description: str = None,
        idempotency_key: str = None,
        visitor_id=None,
        kiosk_id=None,
    ):
        call_type = (call_type or "").strip()
        description = self._normalize_description(description, detail)
        idempotency_key = (idempotency_key or "").strip()
        kiosk_id = (kiosk_id or "").strip() or None

        if not call_type:
            return self._response(
                "INVALID_REQUEST",
                "호출 유형을 선택하세요.",
                "CALL_TYPE_EMPTY",
            )
        if not idempotency_key:
            return self._response(
                "INVALID_REQUEST",
                "멱등 키가 필요합니다.",
                "IDEMPOTENCY_KEY_EMPTY",
            )
        if len(description) > MAX_STAFF_CALL_DESCRIPTION_LENGTH:
            return self._response(
                "INVALID_REQUEST",
                "요청 상세는 500자 이내로 입력하세요.",
                "DESCRIPTION_TOO_LONG",
            )

        normalized_visitor_id = self._normalize_optional_id(visitor_id)
        normalized_member_id = self._normalize_optional_id(member_id)
        if self._has_invalid_optional_id(visitor_id, normalized_visitor_id):
            return self._response(
                "INVALID_REQUEST",
                "방문 등록 정보가 올바르지 않습니다.",
                "VISITOR_SESSION_INVALID",
            )
        if self._has_invalid_optional_id(member_id, normalized_member_id):
            return self._response(
                "INVALID_REQUEST",
                "어르신 정보가 올바르지 않습니다.",
                "VISITOR_SESSION_INVALID",
            )

        try:
            return await self.repository.async_submit_staff_call(
                call_type=call_type,
                description=description,
                idempotency_key=idempotency_key,
                visitor_id=normalized_visitor_id,
                member_id=normalized_member_id,
                kiosk_id=kiosk_id,
            )
        except VisitorSessionInvalidError:
            return self._response(
                "INVALID_REQUEST",
                "방문자 또는 어르신 정보를 찾을 수 없습니다.",
                "VISITOR_SESSION_INVALID",
            )
        except Exception as exc:
            return self._response(
                "ERROR",
                f"직원 호출 접수 중 오류가 발생했습니다: {exc}",
                "STAFF_CALL_WRITE_FAILED",
            )

    @staticmethod
    def _normalize_description(description, detail):
        value = description if description is not None else detail
        return (value or "").strip()

    @staticmethod
    def _normalize_optional_id(value):
        raw = "" if value is None else str(value).strip()
        if not raw:
            return None
        try:
            normalized = int(raw)
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @classmethod
    def _has_invalid_optional_id(cls, original, normalized):
        raw = "" if original is None else str(original).strip()
        return bool(raw) and normalized is None

    @staticmethod
    def _response(result_code, result_message, reason_code):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "call_id": None,
            "linked_visitor_id": None,
            "linked_member_id": None,
        }


__all__ = ["StaffCallService"]
