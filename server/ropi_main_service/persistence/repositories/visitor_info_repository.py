from server.ropi_main_service.persistence.async_connection import async_fetch_one
from server.ropi_main_service.persistence.connection import fetch_one
from server.ropi_main_service.persistence.sql_loader import load_sql


class VisitorInfoRepository:
    def get_visitor_patient_info(self, keyword: str):
        row = fetch_one(
            load_sql("visitor_info/patient_visit_info.sql"),
            (f"%{keyword}%", f"%{keyword}%"),
        )
        if not row:
            return None

        return self._format_patient_visit_info(row)

    async def async_get_visitor_patient_info(self, keyword: str):
        row = await async_fetch_one(
            load_sql("visitor_info/patient_visit_info.sql"),
            (f"%{keyword}%", f"%{keyword}%"),
        )
        if not row:
            return None

        return self._format_patient_visit_info(row)

    @staticmethod
    def _format_patient_visit_info(row):
        return {
            "name": row.get("name") or "-",
            "room": row.get("room") or "-",
            "meal_status": row.get("meal_status") or "정보 없음",
            "medication_status": row.get("medication_status") or "정보 없음",
            "fall_risk": row.get("fall_risk") or "정보 없음",
            "visit_status": "가능",
            "notes": "등록된 안내 메모가 없습니다.",
        }


__all__ = ["VisitorInfoRepository"]
