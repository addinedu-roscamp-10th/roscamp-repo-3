from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class VisitGuideRepository:
    def find_patient(self, keyword: str):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("visit_guide/find_patient.sql"),
                    (f"%{keyword}%", f"%{keyword}%"),
                )
                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "name": row.get("patient_name") or "-",
                    "member_id": row.get("member_id") or "-",
                    "room": row.get("room_no") or "-",
                    "location": row.get("room_no") or "위치 정보 없음",
                    "status": "면회 가능",
                    "member_grade": "-",
                }
        finally:
            conn.close()

    def create_robot_guide_event(self, patient_name: str, room_no: str, member_id=None):
        description = f"[면회 안내] 대상={patient_name}, 목적지={room_no or '미지정'}, 안내 시작 요청"
        target_member_id = self._normalize_member_id(member_id)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("member_event/insert_member_event.sql"),
                    (
                        target_member_id,
                        "GUIDE_REQUESTED",
                        "안내 요청",
                        "VISIT",
                        "INFO",
                        "안내 요청",
                        description,
                    ),
                )
                conn.commit()
                return True, "로봇 안내 요청이 접수되었습니다."
        except Exception as exc:
            conn.rollback()
            return False, f"로봇 안내 요청 등록 중 오류가 발생했습니다: {exc}"
        finally:
            conn.close()

    @staticmethod
    def _normalize_member_id(member_id):
        raw = str(member_id or "").strip()
        if raw.isdigit():
            return int(raw)
        return 1


__all__ = ["VisitGuideRepository"]
