from server.ropi_main_service.persistence.connection import get_connection


class VisitorInfoRepository:
    def get_visitor_patient_info(self, keyword: str):
        query = """
            SELECT
                m.member_name AS name,
                m.room_no AS room,
                MAX(CASE WHEN et.event_type_name = '식사' THEN e.event_name END) AS meal_status,
                MAX(CASE WHEN et.event_type_name = '복약' THEN e.event_name END) AS medication_status,
                MAX(CASE WHEN et.event_type_name = '낙상' THEN e.event_name END) AS fall_risk
            FROM member m
            LEFT JOIN event e
              ON m.member_id = e.member_id
            LEFT JOIN event_type et
              ON e.event_type_id = et.event_type_id
            WHERE m.member_name LIKE %s
               OR m.room_no LIKE %s
            GROUP BY m.member_id, m.member_name, m.room_no
            ORDER BY m.member_name
            LIMIT 1
        """

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (f"%{keyword}%", f"%{keyword}%"))
                row = cur.fetchone()
                if not row:
                    return None

                return {
                    "name": row.get("name") or "-",
                    "room": row.get("room") or "-",
                    "meal_status": row.get("meal_status") or "정보 없음",
                    "medication_status": row.get("medication_status") or "정보 없음",
                    "fall_risk": row.get("fall_risk") or "정보 없음",
                    "visit_status": "가능",
                    "notes": "등록된 안내 메모가 없습니다.",
                }
        finally:
            conn.close()


__all__ = ["VisitorInfoRepository"]
