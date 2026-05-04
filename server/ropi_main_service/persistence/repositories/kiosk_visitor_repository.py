from server.ropi_main_service.persistence.async_connection import (
    async_fetch_all,
    async_fetch_one,
    async_transaction,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


INTERNAL_KIOSK_VISITOR_PASSWORD = "__kiosk_visit__"


class ResidentNotFoundError(Exception):
    pass


class KioskVisitorRepository:
    async def async_find_resident_candidates(self, *, keyword: str, limit=10):
        rows = await async_fetch_all(
            load_sql("kiosk_visitor/list_resident_candidates.sql"),
            (f"%{keyword}%", f"%{keyword}%", self._normalize_limit(limit)),
        )
        return [self._format_resident_candidate(row) for row in rows]

    async def async_get_visitor_care_history(self, *, visitor_id: int, limit=5):
        context = await async_fetch_one(
            load_sql("kiosk_visitor/get_visitor_context.sql"),
            (visitor_id,),
        )
        if not context:
            return None

        normalized_limit = self._normalize_history_limit(limit)
        events = await async_fetch_all(
            load_sql("kiosk_visitor/get_recent_member_events.sql"),
            (int(context["member_id"]), normalized_limit),
        )

        return {
            "visitor_id": int(context["visitor_id"]),
            "member_id": int(context["member_id"]),
            "resident_summary": {
                "display_name": self._mask_display_name(context.get("member_name") or "-"),
                "room_no": context.get("room_no"),
                "visit_status": "면회 가능",
            },
            "care_summary": self._format_care_summary(events),
            "recent_events": [self._format_recent_event(row) for row in events],
        }

    async def async_register_visit(
        self,
        *,
        visitor_name: str,
        phone_no: str,
        relationship: str,
        visit_purpose: str,
        target_member_id: int,
        kiosk_id=None,
    ):
        async with async_transaction() as cur:
            member = await self._find_member(cur, target_member_id)
            if not member:
                raise ResidentNotFoundError(target_member_id)

            visitor = await self._find_existing_visitor(
                cur,
                visitor_name=visitor_name,
                phone_no=phone_no,
                relationship=relationship,
                target_member_id=target_member_id,
            )
            visitor_id = (
                int(visitor["visitor_id"])
                if visitor
                else await self._insert_visitor(
                    cur,
                    visitor_name=visitor_name,
                    phone_no=phone_no,
                    relationship=relationship,
                    target_member_id=target_member_id,
                )
            )

            await self._insert_visit_event(
                cur,
                member_id=target_member_id,
                visitor_name=visitor_name,
                phone_no=phone_no,
                relationship=relationship,
                visit_purpose=visit_purpose,
                kiosk_id=kiosk_id,
            )

        return {
            "visitor_id": visitor_id,
            "member_id": int(member["member_id"]),
            "resident_name": member.get("member_name") or "-",
            "room_no": member.get("room_no") or "-",
            "visit_status": "면회 가능",
        }

    @staticmethod
    async def _find_member(cur, target_member_id):
        await cur.execute(
            load_sql("kiosk_visitor/find_member_by_id.sql"),
            (target_member_id,),
        )
        return await cur.fetchone()

    @staticmethod
    async def _find_existing_visitor(
        cur,
        *,
        visitor_name,
        phone_no,
        relationship,
        target_member_id,
    ):
        await cur.execute(
            load_sql("kiosk_visitor/find_existing_visitor.sql"),
            (phone_no, target_member_id, visitor_name, relationship),
        )
        return await cur.fetchone()

    @staticmethod
    async def _insert_visitor(
        cur,
        *,
        visitor_name,
        phone_no,
        relationship,
        target_member_id,
    ):
        await cur.execute(
            load_sql("kiosk_visitor/insert_visitor.sql"),
            (
                INTERNAL_KIOSK_VISITOR_PASSWORD,
                phone_no,
                visitor_name,
                None,
                relationship,
                target_member_id,
            ),
        )
        return int(cur.lastrowid)

    @staticmethod
    async def _insert_visit_event(
        cur,
        *,
        member_id,
        visitor_name,
        phone_no,
        relationship,
        visit_purpose,
        kiosk_id=None,
    ):
        description_parts = [
            f"방문객={visitor_name}",
            f"연락처={phone_no}",
            f"관계={relationship}",
            f"목적={visit_purpose}",
        ]
        if kiosk_id:
            description_parts.append(f"kiosk_id={kiosk_id}")
        description = "[방문 등록] " + ", ".join(description_parts)
        await cur.execute(
            load_sql("member_event/insert_member_event.sql"),
            (
                member_id,
                "VISIT_CHECKIN",
                "방문 등록",
                "VISIT",
                "INFO",
                "방문 등록",
                description,
            ),
        )

    @classmethod
    def _format_resident_candidate(cls, row):
        return {
            "member_id": int(row["member_id"]),
            "display_name": cls._mask_display_name(row.get("member_name") or "-"),
            "birth_date": cls._format_date(row.get("birth_date")),
            "room_no": row.get("room_no"),
            "visit_available": True,
            "guide_available": True,
        }

    @staticmethod
    def _mask_display_name(name: str) -> str:
        name = str(name or "").strip()
        if not name:
            return "-"
        if len(name) == 1:
            return name
        middle_mask = "*" * max(1, len(name) - 2)
        return f"{name[0]}{middle_mask}{name[-1]}"

    @classmethod
    def _format_care_summary(cls, events):
        latest_event_at = cls._format_timestamp(events[0].get("event_at")) if events else None
        meal_status = cls._find_latest_event_name(events, "MEAL_RECORDED") or "정보 없음"
        medication_status = (
            cls._find_latest_event_name(events, "MEDICATION_RECORDED") or "정보 없음"
        )
        fall_status = cls._find_latest_event_name(events, "FALL_DETECTED")

        return {
            "meal_status": meal_status,
            "medication_status": medication_status,
            "safety_status": fall_status or "최근 낙상 알림 없음",
            "last_updated_at": latest_event_at,
        }

    @classmethod
    def _format_recent_event(cls, row):
        return {
            "event_at": cls._format_timestamp(row.get("event_at")),
            "event_category": row.get("event_category") or "-",
            "event_name": row.get("event_name") or "-",
            "summary": row.get("description"),
        }

    @staticmethod
    def _find_latest_event_name(events, event_type_code):
        for row in events:
            if row.get("event_type_code") == event_type_code:
                return row.get("event_name")
        return None

    @staticmethod
    def _format_timestamp(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _format_date(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _normalize_limit(limit) -> int:
        try:
            numeric_limit = int(limit)
        except (TypeError, ValueError):
            numeric_limit = 10
        return min(max(numeric_limit, 1), 10)

    @staticmethod
    def _normalize_history_limit(limit) -> int:
        try:
            numeric_limit = int(limit)
        except (TypeError, ValueError):
            numeric_limit = 5
        return min(max(numeric_limit, 1), 20)


__all__ = [
    "KioskVisitorRepository",
    "ResidentNotFoundError",
]
