import re

from server.ropi_main_service.persistence.repositories.visitor_register_repository import VisitorRegisterRepository


class VisitorRegisterService:
    def __init__(self, repository=None):
        self.repository = repository or VisitorRegisterRepository()

    def submit_registration(
        self,
        visitor_name: str,
        phone: str,
        patient_name: str,
        relation: str,
        purpose: str,
        member_id=None,
    ):
        visitor_name = (visitor_name or "").strip()
        phone = (phone or "").strip()
        patient_name = (patient_name or "").strip()
        relation = (relation or "").strip()
        purpose = (purpose or "").strip()

        if not visitor_name:
            return False, "방문객 이름을 입력하세요."
        if not phone:
            return False, "연락처를 입력하세요."
        if not re.fullmatch(r"[0-9\-]{10,13}", phone):
            return False, "연락처 형식이 올바르지 않습니다. 예: 010-1234-5678"
        if not patient_name:
            return False, "어르신 이름을 입력하세요."
        if not relation:
            return False, "관계를 입력하세요."
        if not purpose:
            return False, "방문 목적을 입력하세요."

        return self.repository.create_visitor_registration(
            visitor_name=visitor_name,
            phone=phone,
            patient_name=patient_name,
            relation=relation,
            purpose=purpose,
            member_id=member_id,
        )

    async def async_submit_registration(
        self,
        visitor_name: str,
        phone: str,
        patient_name: str,
        relation: str,
        purpose: str,
        member_id=None,
    ):
        visitor_name = (visitor_name or "").strip()
        phone = (phone or "").strip()
        patient_name = (patient_name or "").strip()
        relation = (relation or "").strip()
        purpose = (purpose or "").strip()

        if not visitor_name:
            return False, "방문객 이름을 입력하세요."
        if not phone:
            return False, "연락처를 입력하세요."
        if not re.fullmatch(r"[0-9\-]{10,13}", phone):
            return False, "연락처 형식이 올바르지 않습니다. 예: 010-1234-5678"
        if not patient_name:
            return False, "어르신 이름을 입력하세요."
        if not relation:
            return False, "관계를 입력하세요."
        if not purpose:
            return False, "방문 목적을 입력하세요."

        return await self.repository.async_create_visitor_registration(
            visitor_name=visitor_name,
            phone=phone,
            patient_name=patient_name,
            relation=relation,
            purpose=purpose,
            member_id=member_id,
        )

__all__ = ["VisitorRegisterService"]
