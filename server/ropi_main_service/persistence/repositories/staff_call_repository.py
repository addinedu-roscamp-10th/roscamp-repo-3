import asyncio
import hashlib
import json

from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.sql_loader import load_sql


STAFF_CALL_SCOPE = "KIOSK_STAFF_CALL"
DEFAULT_KIOSK_REQUESTER_ID = "anonymous_kiosk"


class VisitorSessionInvalidError(Exception):
    pass


class StaffCallRepository:
    def create_staff_call(
        self,
        *,
        call_type: str,
        description: str = "",
        idempotency_key: str,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        return asyncio.run(
            self.async_submit_staff_call(
                call_type=call_type,
                description=description,
                idempotency_key=idempotency_key,
                visitor_id=visitor_id,
                member_id=member_id,
                kiosk_id=kiosk_id,
            )
        )

    async def async_submit_staff_call(
        self,
        *,
        call_type: str,
        description: str = "",
        idempotency_key: str,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        request_hash = self._build_request_hash(
            call_type=call_type,
            description=description,
            visitor_id=visitor_id,
            member_id=member_id,
            kiosk_id=kiosk_id,
        )
        requester_id = self._requester_id(kiosk_id)

        async with async_transaction() as cur:
            existing = await self._find_idempotency_response(
                cur,
                requester_id=requester_id,
                idempotency_key=idempotency_key,
            )
            if existing:
                return self._resolve_idempotency_response(existing, request_hash)

            linked_context = await self._resolve_linked_context(
                cur,
                visitor_id=visitor_id,
                member_id=member_id,
            )

            linked_visitor_id = linked_context.get("visitor_id")
            linked_member_id = linked_context.get("member_id")

            if linked_member_id is not None:
                call_id = await self._insert_member_event(
                    cur,
                    call_type=call_type,
                    description=description,
                    linked_context=linked_context,
                    kiosk_id=kiosk_id,
                )
            else:
                call_id = await self._insert_kiosk_call_log(
                    cur,
                    call_type=call_type,
                    description=description,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    visitor_id=linked_visitor_id,
                    member_id=linked_member_id,
                    kiosk_id=kiosk_id,
                )

            response = self._accepted_response(
                call_id=call_id,
                linked_visitor_id=linked_visitor_id,
                linked_member_id=linked_member_id,
            )
            await self._insert_idempotency_response(
                cur,
                requester_id=requester_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
            )
            return response

    async def async_create_staff_call(self, call_type: str, detail: str, member_id=None):
        idempotency_key = self._build_request_hash(
            call_type=call_type,
            description=detail,
            visitor_id=None,
            member_id=member_id,
            kiosk_id=None,
        )
        return await self.async_submit_staff_call(
            call_type=call_type,
            description=detail,
            idempotency_key=idempotency_key,
            member_id=member_id,
        )

    @staticmethod
    async def _find_idempotency_response(cur, *, requester_id, idempotency_key):
        await cur.execute(
            load_sql("staff_call/find_idempotency_response.sql"),
            (STAFF_CALL_SCOPE, requester_id, idempotency_key),
        )
        return await cur.fetchone()

    @classmethod
    async def _resolve_linked_context(cls, cur, *, visitor_id=None, member_id=None):
        if visitor_id is not None:
            await cur.execute(
                load_sql("staff_call/find_visitor_context.sql"),
                (visitor_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise VisitorSessionInvalidError(visitor_id)
            return {
                "visitor_id": int(row["visitor_id"]),
                "member_id": int(row["member_id"]),
                "visitor_name": row.get("visitor_name"),
                "member_name": row.get("member_name"),
                "room_no": row.get("room_no"),
            }

        if member_id is not None:
            await cur.execute(
                load_sql("staff_call/find_member_context.sql"),
                (member_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise VisitorSessionInvalidError(member_id)
            return {
                "visitor_id": None,
                "member_id": int(row["member_id"]),
                "visitor_name": None,
                "member_name": row.get("member_name"),
                "room_no": row.get("room_no"),
            }

        return {
            "visitor_id": None,
            "member_id": None,
            "visitor_name": None,
            "member_name": None,
            "room_no": None,
        }

    @classmethod
    async def _insert_member_event(
        cls,
        cur,
        *,
        call_type,
        description,
        linked_context,
        kiosk_id=None,
    ):
        await cur.execute(
            load_sql("member_event/insert_member_event.sql"),
            (
                linked_context["member_id"],
                "STAFF_CALL",
                "직원 호출",
                "CARE",
                "WARNING",
                "직원 호출",
                cls._build_description(
                    call_type=call_type,
                    description=description,
                    linked_context=linked_context,
                    kiosk_id=kiosk_id,
                ),
            ),
        )
        return f"member_event_{int(cur.lastrowid)}"

    @staticmethod
    async def _insert_kiosk_call_log(
        cur,
        *,
        call_type,
        description,
        idempotency_key,
        request_hash,
        visitor_id=None,
        member_id=None,
        kiosk_id=None,
    ):
        await cur.execute(
            load_sql("staff_call/insert_kiosk_staff_call_log.sql"),
            (
                idempotency_key,
                request_hash,
                call_type,
                description or None,
                visitor_id,
                member_id,
                kiosk_id,
            ),
        )
        return f"kiosk_call_{int(cur.lastrowid)}"

    @staticmethod
    async def _insert_idempotency_response(
        cur,
        *,
        requester_id,
        idempotency_key,
        request_hash,
        response,
    ):
        await cur.execute(
            load_sql("staff_call/insert_idempotency_response.sql"),
            (
                STAFF_CALL_SCOPE,
                requester_id,
                idempotency_key,
                request_hash,
                json.dumps(response, ensure_ascii=False),
            ),
        )

    @classmethod
    def _resolve_idempotency_response(cls, row, request_hash):
        if row.get("request_hash") != request_hash:
            return cls._invalid_request(
                "같은 멱등 키로 다른 직원 호출 요청이 전달되었습니다.",
                "IDEMPOTENCY_KEY_CONFLICT",
            )

        response = row.get("response_json")
        if isinstance(response, dict):
            return response
        if response:
            return json.loads(response)
        return cls._invalid_request(
            "이전 직원 호출 응답을 복원할 수 없습니다.",
            "IDEMPOTENCY_KEY_CONFLICT",
        )

    @staticmethod
    def _build_request_hash(**payload) -> str:
        normalized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _requester_id(kiosk_id):
        return str(kiosk_id or "").strip() or DEFAULT_KIOSK_REQUESTER_ID

    @staticmethod
    def _build_description(*, call_type, description, linked_context, kiosk_id=None):
        parts = [
            f"요청유형={call_type}",
            f"상세={description.strip() if description and description.strip() else '없음'}",
        ]
        if linked_context.get("visitor_id") is not None:
            parts.append(f"visitor_id={linked_context['visitor_id']}")
        if linked_context.get("visitor_name"):
            parts.append(f"방문자={linked_context['visitor_name']}")
        if linked_context.get("member_id") is not None:
            parts.append(f"member_id={linked_context['member_id']}")
        if linked_context.get("member_name"):
            parts.append(f"어르신={linked_context['member_name']}")
        if linked_context.get("room_no"):
            parts.append(f"호실={linked_context['room_no']}")
        if kiosk_id:
            parts.append(f"kiosk_id={kiosk_id}")
        return "[직원 호출] " + ", ".join(parts)

    @staticmethod
    def _accepted_response(*, call_id, linked_visitor_id=None, linked_member_id=None):
        return {
            "result_code": "ACCEPTED",
            "result_message": "직원이 곧 도착합니다.",
            "reason_code": None,
            "call_id": call_id,
            "linked_visitor_id": linked_visitor_id,
            "linked_member_id": linked_member_id,
        }

    @staticmethod
    def _invalid_request(result_message, reason_code):
        return {
            "result_code": "INVALID_REQUEST",
            "result_message": result_message,
            "reason_code": reason_code,
            "call_id": None,
            "linked_visitor_id": None,
            "linked_member_id": None,
        }


__all__ = [
    "StaffCallRepository",
    "VisitorSessionInvalidError",
]
