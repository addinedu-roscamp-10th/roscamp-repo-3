from server.ropi_main_service.persistence.repositories.staff_call_repository import StaffCallRepository


class StaffCallService:
    def __init__(self, repository=None):
        self.repository = repository or StaffCallRepository()

    def submit_staff_call(self, call_type: str, detail: str, member_id=None):
        call_type = (call_type or "").strip()
        detail = (detail or "").strip()

        if not call_type:
            return False, "요청 유형을 선택하세요."

        if len(detail) < 2:
            return False, "요청 상세를 2자 이상 입력하세요."

        return self.repository.create_staff_call(
            call_type=call_type,
            detail=detail,
            member_id=member_id,
        )

    async def async_submit_staff_call(self, call_type: str, detail: str, member_id=None):
        call_type = (call_type or "").strip()
        detail = (detail or "").strip()

        if not call_type:
            return False, "요청 유형을 선택하세요."

        if len(detail) < 2:
            return False, "요청 상세를 2자 이상 입력하세요."

        return await self.repository.async_create_staff_call(
            call_type=call_type,
            detail=detail,
            member_id=member_id,
        )


__all__ = ["StaffCallService"]
