from server.ropi_main_service.persistence.connection import get_connection


class VisitorRegisterRepository:
    def create_visitor_registration(
        self,
        visitor_name: str,
        phone: str,
        patient_name: str,
        relation: str,
        purpose: str,
        member_id=None,
    ):
        description = (
            f"[방문 등록] 방문객={visitor_name}, 연락처={phone}, "
            f"대상어르신={patient_name}, 관계={relation}, 목적={purpose}"
        )

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                target_member_id = self._normalize_member_id(member_id) if member_id else self._find_member_id(cur, patient_name)
                cur.execute(
                    """
                    INSERT INTO member_event (
                        member_id,
                        event_type_code,
                        event_type_name,
                        event_category,
                        severity,
                        event_name,
                        description,
                        event_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
                    """,
                    (
                        target_member_id,
                        "VISIT_CHECKIN",
                        "방문 등록",
                        "VISIT",
                        "INFO",
                        "방문 등록",
                        description,
                    ),
                )
                conn.commit()
                return True, "방문 등록이 완료되었습니다."
        except Exception as exc:
            conn.rollback()
            return False, f"방문 등록 중 오류가 발생했습니다: {exc}"
        finally:
            conn.close()

    @staticmethod
    def _find_member_id(cur, patient_name: str):
        cur.execute(
            """
            SELECT member_id
            FROM member
            WHERE member_name = %s
            LIMIT 1
            """,
            (patient_name,),
        )
        row = cur.fetchone()
        return row["member_id"] if row else 1

    @staticmethod
    def _normalize_member_id(member_id):
        raw = str(member_id or "").strip()
        if raw.isdigit():
            return int(raw)
        return 1


__all__ = ["VisitorRegisterRepository"]
