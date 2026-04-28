import hashlib
import json

from server.ropi_main_service.persistence.sql_loader import load_sql


class IdempotencyRepository:
    def build_request_hash(self, **payload) -> str:
        normalized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def find_response(self, cur, *, requester_id, idempotency_key, request_hash):
        cur.execute(
            load_sql("idempotency/find_delivery_create_task_response.sql"),
            (requester_id, idempotency_key),
        )
        row = cur.fetchone()
        return self._response_from_row(row, request_hash)

    async def async_find_response(self, cur, *, requester_id, idempotency_key, request_hash):
        await cur.execute(
            load_sql("idempotency/find_delivery_create_task_response.sql"),
            (requester_id, idempotency_key),
        )
        row = await cur.fetchone()
        return self._response_from_row(row, request_hash)

    def insert_record(self, cur, *, requester_id, idempotency_key, request_hash, response, task_id):
        cur.execute(
            load_sql("idempotency/insert_delivery_create_task_record.sql"),
            (
                requester_id,
                idempotency_key,
                request_hash,
                json.dumps(response, ensure_ascii=False),
                task_id,
            ),
        )

    async def async_insert_record(self, cur, *, requester_id, idempotency_key, request_hash, response, task_id):
        await cur.execute(
            load_sql("idempotency/insert_delivery_create_task_record.sql"),
            (
                requester_id,
                idempotency_key,
                request_hash,
                json.dumps(response, ensure_ascii=False),
                task_id,
            ),
        )

    def _response_from_row(self, row, request_hash):
        if not row:
            return None

        if row.get("request_hash") != request_hash:
            return self._build_delivery_task_response(
                result_code="INVALID_REQUEST",
                result_message="같은 idempotency_key로 다른 요청 payload가 전달되었습니다.",
                reason_code="IDEMPOTENCY_KEY_CONFLICT",
            )

        response = row.get("response_json")
        if isinstance(response, dict):
            return response
        if response:
            return json.loads(response)
        return None

    @staticmethod
    def _build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
        }


__all__ = ["IdempotencyRepository"]
