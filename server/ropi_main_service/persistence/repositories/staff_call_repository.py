from server.ropi_main_service.persistence.connection import get_connection


class StaffCallRepository:
    def create_staff_call(self, call_type: str, detail: str, member_id=None):
        description = (
            f"[직원 호출] 요청유형={call_type}, "
            f"상세={detail.strip() if detail and detail.strip() else '없음'}"
        )
        target_member_id = self._normalize_member_id(member_id)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
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
                        "STAFF_CALL",
                        "직원 호출",
                        "CARE",
                        "WARNING",
                        "직원 호출",
                        description,
                    ),
                )

                conn.commit()
                return True, "직원 호출 요청이 접수되었습니다."
        except Exception as exc:
            conn.rollback()
            return False, f"직원 호출 등록 중 오류가 발생했습니다: {exc}"
        finally:
            conn.close()

    @staticmethod
    def _normalize_member_id(member_id):
        raw = str(member_id or "").strip()
        if raw.isdigit():
            return int(raw)
        return 1


__all__ = ["StaffCallRepository"]
