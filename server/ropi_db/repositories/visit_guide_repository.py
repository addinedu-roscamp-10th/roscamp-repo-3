from server.ropi_db.connection import get_connection


class VisitGuideRepository:
    def find_patient(self, keyword: str):
        query = """
            SELECT
                member_id,
                member_name AS patient_name,
                room_no
            FROM member
            WHERE member_name LIKE %s
               OR room_no LIKE %s
            ORDER BY member_name
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

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO event (
                        event_name,
                        description,
                        event_at,
                        member_id,
                        event_type_id,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, NOW(), %s, %s, NOW(), NOW())
                    """,
                    ("안내 요청", description, str(member_id) if member_id else "MEM001", 4),
                )
                conn.commit()
                return True, "로봇 안내 요청이 접수되었습니다."
        except Exception as exc:
            conn.rollback()
            return False, f"로봇 안내 요청 등록 중 오류가 발생했습니다: {exc}"
        finally:
            conn.close()


__all__ = ["VisitGuideRepository"]
