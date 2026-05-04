import asyncio
import re

from server.ropi_main_service.persistence.repositories.kiosk_visitor_repository import (
    KioskVisitorRepository,
    ResidentNotFoundError,
)


class KioskVisitorService:
    def __init__(self, repository=None):
        self.repository = repository or KioskVisitorRepository()

    def lookup_residents(self, keyword: str, limit=10):
        return asyncio.run(self.async_lookup_residents(keyword=keyword, limit=limit))

    async def async_lookup_residents(self, keyword: str, limit=10):
        keyword = (keyword or "").strip()
        if not keyword:
            return self._lookup_response(
                "INVALID_REQUEST",
                "검색어를 입력하세요.",
                "KEYWORD_EMPTY",
                [],
            )

        normalized_limit = self._normalize_limit(limit)
        matches = await self.repository.async_find_resident_candidates(
            keyword=keyword,
            limit=normalized_limit,
        )
        if not matches:
            return self._lookup_response(
                "NO_MATCH",
                "일치하는 어르신 정보가 없습니다.",
                "RESIDENT_NOT_FOUND",
                [],
            )

        return self._lookup_response(
            "FOUND",
            "어르신 정보를 확인했습니다.",
            None,
            matches,
        )

    def register_visit(
        self,
        *,
        visitor_name: str,
        phone_no: str,
        relationship: str,
        visit_purpose: str,
        target_member_id,
        privacy_agreed: bool,
        kiosk_id=None,
    ):
        return asyncio.run(
            self.async_register_visit(
                visitor_name=visitor_name,
                phone_no=phone_no,
                relationship=relationship,
                visit_purpose=visit_purpose,
                target_member_id=target_member_id,
                privacy_agreed=privacy_agreed,
                kiosk_id=kiosk_id,
            )
        )

    async def async_register_visit(
        self,
        *,
        visitor_name: str,
        phone_no: str,
        relationship: str,
        visit_purpose: str,
        target_member_id,
        privacy_agreed: bool,
        kiosk_id=None,
    ):
        visitor_name = (visitor_name or "").strip()
        phone_no = (phone_no or "").strip()
        relationship = (relationship or "").strip()
        visit_purpose = (visit_purpose or "").strip()
        kiosk_id = (kiosk_id or "").strip() or None

        validation_error = self._validate_registration(
            visitor_name=visitor_name,
            phone_no=phone_no,
            relationship=relationship,
            visit_purpose=visit_purpose,
            target_member_id=target_member_id,
            privacy_agreed=privacy_agreed,
        )
        if validation_error is not None:
            return validation_error

        try:
            registered = await self.repository.async_register_visit(
                visitor_name=visitor_name,
                phone_no=phone_no,
                relationship=relationship,
                visit_purpose=visit_purpose,
                target_member_id=int(target_member_id),
                kiosk_id=kiosk_id,
            )
        except ResidentNotFoundError:
            return self._mutation_response(
                "REJECTED",
                "대상 어르신을 찾을 수 없습니다.",
                "RESIDENT_NOT_FOUND",
            )
        except Exception as exc:
            return self._mutation_response(
                "ERROR",
                f"방문 등록 중 오류가 발생했습니다: {exc}",
                "REGISTRATION_WRITE_FAILED",
            )

        return {
            "result_code": "REGISTERED",
            "result_message": "방문 등록이 완료되었습니다.",
            "reason_code": None,
            "visitor_id": registered["visitor_id"],
            "member_id": registered["member_id"],
            "resident_name": registered["resident_name"],
            "room_no": registered.get("room_no"),
            "visit_status": registered.get("visit_status") or "면회 가능",
        }

    def get_care_history(self, *, visitor_id):
        return asyncio.run(self.async_get_care_history(visitor_id=visitor_id))

    async def async_get_care_history(self, *, visitor_id):
        normalized_visitor_id = self._normalize_positive_id(visitor_id)
        if normalized_visitor_id is None:
            return self._mutation_response(
                "INVALID_REQUEST",
                "방문 등록 정보가 올바르지 않습니다.",
                "VISITOR_ID_INVALID",
            )

        try:
            history = await self.repository.async_get_visitor_care_history(
                visitor_id=normalized_visitor_id,
            )
        except Exception as exc:
            return self._mutation_response(
                "ERROR",
                f"케어 이력 조회 중 오류가 발생했습니다: {exc}",
                "CARE_HISTORY_UNAVAILABLE",
            )

        if history is None:
            return self._mutation_response(
                "NOT_FOUND",
                "방문 등록 정보를 찾을 수 없습니다.",
                "VISITOR_NOT_FOUND",
            )

        return {
            "result_code": "OK",
            "result_message": "케어 이력을 조회했습니다.",
            "reason_code": None,
            "visitor_id": history["visitor_id"],
            "member_id": history["member_id"],
            "resident_summary": history.get("resident_summary"),
            "care_summary": history.get("care_summary"),
            "recent_events": history.get("recent_events") or [],
        }

    @staticmethod
    def _normalize_limit(limit) -> int:
        try:
            numeric_limit = int(limit)
        except (TypeError, ValueError):
            numeric_limit = 10
        return min(max(numeric_limit, 1), 10)

    @staticmethod
    def _normalize_positive_id(value):
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @classmethod
    def _validate_registration(
        cls,
        *,
        visitor_name,
        phone_no,
        relationship,
        visit_purpose,
        target_member_id,
        privacy_agreed,
    ):
        if not visitor_name:
            return cls._mutation_response(
                "INVALID_REQUEST",
                "방문자 이름을 입력하세요.",
                "VISITOR_NAME_EMPTY",
            )
        if not re.fullmatch(r"[0-9\-]{10,13}", phone_no or ""):
            return cls._mutation_response(
                "INVALID_REQUEST",
                "연락처 형식이 올바르지 않습니다. 예: 010-1234-5678",
                "PHONE_INVALID",
            )
        if not relationship:
            return cls._mutation_response(
                "INVALID_REQUEST",
                "관계를 입력하세요.",
                "RELATIONSHIP_EMPTY",
            )
        if not visit_purpose:
            return cls._mutation_response(
                "INVALID_REQUEST",
                "방문 목적을 입력하세요.",
                "VISIT_PURPOSE_EMPTY",
            )
        if not privacy_agreed:
            return cls._mutation_response(
                "INVALID_REQUEST",
                "개인정보 수집 동의가 필요합니다.",
                "PRIVACY_CONSENT_REQUIRED",
            )
        try:
            if int(target_member_id) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return cls._mutation_response(
                "INVALID_REQUEST",
                "대상 어르신 ID가 올바르지 않습니다.",
                "TARGET_MEMBER_ID_INVALID",
            )
        return None

    @staticmethod
    def _lookup_response(result_code, result_message, reason_code, matches):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "matches": matches,
        }

    @staticmethod
    def _mutation_response(result_code, result_message, reason_code):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
        }


__all__ = ["KioskVisitorService"]
