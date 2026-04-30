import asyncio
import json

from server.ropi_main_service.persistence.repositories.task_monitor_repository import (
    TaskMonitorRepository,
)
from server.ropi_main_service.transport.fall_evidence_image_client import (
    DEFAULT_CONSUMER_ID as DEFAULT_AI_EVIDENCE_CONSUMER_ID,
    FallEvidenceImageClient,
)


class FallEvidenceImageService:
    DEFAULT_ALERT_LOOKUP_LIMIT = 20
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(self, repository=None, evidence_client=None):
        self.repository = repository or TaskMonitorRepository()
        self.evidence_client = evidence_client or FallEvidenceImageClient.from_env()

    def get_fall_evidence_image(
        self,
        *,
        consumer_id=None,
        task_id=None,
        alert_id=None,
        evidence_image_id=None,
        result_seq=None,
    ):
        request = self._normalize_request(
            consumer_id=consumer_id,
            task_id=task_id,
            alert_id=alert_id,
            evidence_image_id=evidence_image_id,
            result_seq=result_seq,
        )
        if request["error_response"] is not None:
            return request["error_response"]

        rows = self.repository.get_fall_evidence_alert_candidates(
            task_id=request["task_id"],
            limit=self.DEFAULT_ALERT_LOOKUP_LIMIT,
        )
        return self._query_evidence_image_from_rows(rows, request)

    async def async_get_fall_evidence_image(
        self,
        *,
        consumer_id=None,
        task_id=None,
        alert_id=None,
        evidence_image_id=None,
        result_seq=None,
    ):
        request = self._normalize_request(
            consumer_id=consumer_id,
            task_id=task_id,
            alert_id=alert_id,
            evidence_image_id=evidence_image_id,
            result_seq=result_seq,
        )
        if request["error_response"] is not None:
            return request["error_response"]

        async_get_candidates = getattr(
            self.repository,
            "async_get_fall_evidence_alert_candidates",
            None,
        )
        if async_get_candidates is not None:
            rows = await async_get_candidates(
                task_id=request["task_id"],
                limit=self.DEFAULT_ALERT_LOOKUP_LIMIT,
            )
        else:
            rows = await asyncio.to_thread(
                self.repository.get_fall_evidence_alert_candidates,
                task_id=request["task_id"],
                limit=self.DEFAULT_ALERT_LOOKUP_LIMIT,
            )
        return await self._async_query_evidence_image_from_rows(rows, request)

    def _query_evidence_image_from_rows(self, rows, request):
        alert = self._find_matching_fall_alert(rows, request)
        if alert.get("error_response") is not None:
            return alert["error_response"]

        try:
            response = self.evidence_client.query_evidence_image(
                consumer_id=DEFAULT_AI_EVIDENCE_CONSUMER_ID,
                evidence_image_id=request["evidence_image_id"],
                result_seq=request["result_seq"] or alert.get("result_seq"),
                pinky_id=alert.get("pinky_id"),
            )
        except Exception as exc:
            return self._error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message=f"AI 증거 이미지 조회에 실패했습니다: {exc}",
                reason_code="AI_EVIDENCE_QUERY_FAILED",
                request=request,
                alert=alert,
            )

        return self._format_response(response, request=request, alert=alert)

    async def _async_query_evidence_image_from_rows(self, rows, request):
        alert = self._find_matching_fall_alert(rows, request)
        if alert.get("error_response") is not None:
            return alert["error_response"]

        try:
            async_query = getattr(self.evidence_client, "async_query_evidence_image", None)
            if async_query is not None:
                response = await async_query(
                    consumer_id=DEFAULT_AI_EVIDENCE_CONSUMER_ID,
                    evidence_image_id=request["evidence_image_id"],
                    result_seq=request["result_seq"] or alert.get("result_seq"),
                    pinky_id=alert.get("pinky_id"),
                )
            else:
                response = await asyncio.to_thread(
                    self.evidence_client.query_evidence_image,
                    consumer_id=DEFAULT_AI_EVIDENCE_CONSUMER_ID,
                    evidence_image_id=request["evidence_image_id"],
                    result_seq=request["result_seq"] or alert.get("result_seq"),
                    pinky_id=alert.get("pinky_id"),
                )
        except Exception as exc:
            return self._error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message=f"AI 증거 이미지 조회에 실패했습니다: {exc}",
                reason_code="AI_EVIDENCE_QUERY_FAILED",
                request=request,
                alert=alert,
            )

        return self._format_response(response, request=request, alert=alert)

    @classmethod
    def _normalize_request(
        cls,
        *,
        consumer_id,
        task_id,
        alert_id,
        evidence_image_id,
        result_seq,
    ):
        normalized_consumer_id = str(consumer_id or "").strip()
        normalized_task_id = cls._optional_int(task_id)
        normalized_evidence_image_id = str(evidence_image_id or "").strip()
        normalized_result_seq = cls._optional_int(result_seq)
        normalized_alert_id = str(alert_id or "").strip() or None

        request = {
            "consumer_id": normalized_consumer_id,
            "task_id": normalized_task_id,
            "alert_id": normalized_alert_id,
            "evidence_image_id": normalized_evidence_image_id,
            "result_seq": normalized_result_seq,
        }

        if not normalized_consumer_id:
            return {
                **request,
                "error_response": cls._error_response(
                    result_code="INVALID_REQUEST",
                    result_message="consumer_id가 필요합니다.",
                    reason_code="CONSUMER_ID_REQUIRED",
                    request=request,
                ),
            }
        if normalized_task_id is None:
            return {
                **request,
                "error_response": cls._error_response(
                    result_code="INVALID_REQUEST",
                    result_message="task_id가 필요합니다.",
                    reason_code="TASK_ID_REQUIRED",
                    request=request,
                ),
            }
        if not normalized_evidence_image_id:
            return {
                **request,
                "error_response": cls._error_response(
                    result_code="INVALID_REQUEST",
                    result_message="evidence_image_id가 필요합니다.",
                    reason_code="EVIDENCE_IMAGE_ID_REQUIRED",
                    request=request,
                ),
            }
        if result_seq not in (None, "") and normalized_result_seq is None:
            return {
                **request,
                "error_response": cls._error_response(
                    result_code="INVALID_REQUEST",
                    result_message="result_seq는 숫자여야 합니다.",
                    reason_code="RESULT_SEQ_INVALID",
                    request=request,
                ),
            }

        return {
            **request,
            "error_response": None,
        }

    @classmethod
    def _find_matching_fall_alert(cls, rows, request):
        rows = [row for row in rows or [] if isinstance(row, dict)]
        if not rows:
            return {
                "error_response": cls._error_response(
                    result_code="NOT_FOUND",
                    result_message="순찰 task 또는 낙상 alert를 찾을 수 없습니다.",
                    reason_code="FALL_ALERT_NOT_FOUND",
                    request=request,
                )
            }

        if any(str(row.get("task_type") or "").upper() not in {"", "PATROL"} for row in rows):
            return {
                "error_response": cls._error_response(
                    result_code="FORBIDDEN",
                    result_message="순찰 task의 증거 이미지만 조회할 수 있습니다.",
                    reason_code="TASK_TYPE_NOT_PATROL",
                    request=request,
                )
            }

        saw_alert_id = False
        saw_candidate = False
        for row in rows:
            if row.get("alert_id") is None:
                continue

            payload = cls._json_object(row.get("payload_json"))
            alert_payload = cls._extract_alert_payload(payload)
            row_alert_id = str(row.get("alert_id"))
            payload_alert_id = cls._first_text(
                alert_payload.get("alert_id"),
                payload.get("alert_id"),
            )
            request_alert_id = request.get("alert_id")
            if request_alert_id is not None and request_alert_id not in {
                row_alert_id,
                str(payload_alert_id or ""),
            }:
                continue

            saw_alert_id = True
            candidate_evidence_id = cls._first_text(
                alert_payload.get("evidence_image_id"),
                payload.get("evidence_image_id"),
            )
            candidate_result_seq = cls._optional_int(
                cls._first_text(
                    alert_payload.get("result_seq"),
                    payload.get("result_seq"),
                )
            )
            if not candidate_evidence_id:
                continue

            saw_candidate = True
            if candidate_evidence_id != request["evidence_image_id"]:
                continue
            if (
                request.get("result_seq") is not None
                and candidate_result_seq is not None
                and request["result_seq"] != candidate_result_seq
            ):
                continue

            return {
                "error_response": None,
                "task_id": row.get("task_id") or request.get("task_id"),
                "alert_id": row_alert_id,
                "evidence_image_id": candidate_evidence_id,
                "result_seq": candidate_result_seq or request.get("result_seq"),
                "pinky_id": cls._first_text(
                    alert_payload.get("pinky_id"),
                    row.get("robot_id"),
                    row.get("assigned_robot_id"),
                ),
            }

        reason_code = "FALL_ALERT_NOT_FOUND"
        result_code = "NOT_FOUND"
        result_message = "요청한 낙상 alert를 찾을 수 없습니다."
        if saw_alert_id or saw_candidate:
            reason_code = "EVIDENCE_OWNERSHIP_MISMATCH"
            result_code = "FORBIDDEN"
            result_message = "evidence image가 요청한 task alert에 속하지 않습니다."

        return {
            "error_response": cls._error_response(
                result_code=result_code,
                result_message=result_message,
                reason_code=reason_code,
                request=request,
            )
        }

    @classmethod
    def _format_response(cls, response, *, request, alert):
        payload = response if isinstance(response, dict) else {}
        result_code = str(payload.get("result_code") or "").strip().upper()
        if not result_code:
            return cls._error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message="AI 증거 이미지 응답 형식이 올바르지 않습니다.",
                reason_code="AI_EVIDENCE_RESPONSE_INVALID",
                request=request,
                alert=alert,
            )

        size_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size_bytes > cls.MAX_RESPONSE_BYTES:
            return cls._error_response(
                result_code="PAYLOAD_TOO_LARGE",
                result_message="증거 이미지 응답 크기가 허용 범위를 초과했습니다.",
                reason_code="EVIDENCE_PAYLOAD_TOO_LARGE",
                request=request,
                alert=alert,
            )

        return {
            **payload,
            "result_code": result_code,
            "task_id": alert.get("task_id") or request.get("task_id"),
            "alert_id": str(alert.get("alert_id") or request.get("alert_id") or ""),
            "evidence_image_id": payload.get("evidence_image_id")
            or request.get("evidence_image_id"),
            "result_seq": payload.get("result_seq")
            if payload.get("result_seq") is not None
            else (alert.get("result_seq") or request.get("result_seq")),
        }

    @staticmethod
    def _error_response(
        *,
        result_code,
        result_message,
        reason_code,
        request,
        alert=None,
    ):
        alert = alert or {}
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": request.get("task_id"),
            "alert_id": str(alert.get("alert_id") or request.get("alert_id") or "")
            or None,
            "evidence_image_id": request.get("evidence_image_id"),
            "result_seq": request.get("result_seq") or alert.get("result_seq"),
        }

    @classmethod
    def _extract_alert_payload(cls, payload):
        for key in ("trigger_result", "latest_alert", "alert"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested
        return payload

    @staticmethod
    def _first_text(*values):
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    @staticmethod
    def _json_object(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return loaded if isinstance(loaded, dict) else {}
        return {}

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "FallEvidenceImageService",
]
