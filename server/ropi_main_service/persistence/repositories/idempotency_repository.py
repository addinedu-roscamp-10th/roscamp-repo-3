import hashlib
import json


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
            """
            SELECT request_hash, response_json
            FROM idempotency_record
            WHERE scope = 'DELIVERY_CREATE_TASK'
              AND requester_type = 'CAREGIVER'
              AND requester_id = %s
              AND idempotency_key = %s
            LIMIT 1
            """,
            (requester_id, idempotency_key),
        )
        row = cur.fetchone()
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

    def insert_record(self, cur, *, requester_id, idempotency_key, request_hash, response, task_id):
        cur.execute(
            """
            INSERT INTO idempotency_record (
                scope,
                requester_type,
                requester_id,
                idempotency_key,
                request_hash,
                response_json,
                task_id,
                expires_at,
                created_at
            )
            VALUES (
                'DELIVERY_CREATE_TASK',
                'CAREGIVER',
                %s,
                %s,
                %s,
                %s,
                %s,
                DATE_ADD(NOW(3), INTERVAL 1 DAY),
                NOW(3)
            )
            """,
            (
                requester_id,
                idempotency_key,
                request_hash,
                json.dumps(response, ensure_ascii=False),
                task_id,
            ),
        )

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
