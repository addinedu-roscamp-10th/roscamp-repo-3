from server.ropi_main_service.persistence.async_connection import async_execute
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


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
                    load_sql("member_event/insert_member_event.sql"),
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

    async def async_create_staff_call(self, call_type: str, detail: str, member_id=None):
        description = (
            f"[직원 호출] 요청유형={call_type}, "
            f"상세={detail.strip() if detail and detail.strip() else '없음'}"
        )
        target_member_id = self._normalize_member_id(member_id)

        try:
            await async_execute(
                load_sql("member_event/insert_member_event.sql"),
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
            return True, "직원 호출 요청이 접수되었습니다."
        except Exception as exc:
            return False, f"직원 호출 등록 중 오류가 발생했습니다: {exc}"

    @staticmethod
    def _normalize_member_id(member_id):
        raw = str(member_id or "").strip()
        if raw.isdigit():
            return int(raw)
        return 1


__all__ = ["StaffCallRepository"]
