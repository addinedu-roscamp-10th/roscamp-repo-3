import asyncio
import json
from datetime import date, datetime, timezone

from server.ropi_main_service.persistence.repositories.task_monitor_repository import (
    TaskMonitorRepository,
)
from server.ropi_main_service.transport.fall_evidence_image_client import (
    DEFAULT_CONSUMER_ID as DEFAULT_AI_EVIDENCE_CONSUMER_ID,
    FallEvidenceImageClient,
)


ACTIVE_TASK_STATUSES = (
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
    "CANCEL_REQUESTED",
    "CANCELLING",
    "PREEMPTING",
)
TERMINAL_TASK_STATUSES = (
    "COMPLETED",
    "CANCELLED",
    "FAILED",
)
CANCELLABLE_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}


class TaskMonitorService:
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 200
    DEFAULT_RECENT_TERMINAL_LIMIT = 20
    MAX_RECENT_TERMINAL_LIMIT = 100
    DEFAULT_EVIDENCE_ALERT_LOOKUP_LIMIT = 20
    MAX_EVIDENCE_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(self, repository=None, evidence_client=None):
        self.repository = repository or TaskMonitorRepository()
        self.evidence_client = evidence_client or FallEvidenceImageClient.from_env()

    def get_task_monitor_snapshot(
        self,
        *,
        consumer_id=None,
        task_types=None,
        statuses=None,
        include_recent_terminal=True,
        recent_terminal_limit=DEFAULT_RECENT_TERMINAL_LIMIT,
        limit=DEFAULT_LIMIT,
    ):
        query = self._build_query(
            task_types=task_types,
            statuses=statuses,
            include_recent_terminal=include_recent_terminal,
            recent_terminal_limit=recent_terminal_limit,
            limit=limit,
        )
        snapshot = self.repository.get_task_monitor_snapshot(
            task_types=query["task_types"],
            statuses=query["statuses"],
            limit=query["limit"],
        )
        return self._format_snapshot(
            snapshot=snapshot,
            consumer_id=consumer_id,
            recent_terminal_limit=query["recent_terminal_limit"],
            cap_terminal_tasks=query["cap_terminal_tasks"],
        )

    async def async_get_task_monitor_snapshot(
        self,
        *,
        consumer_id=None,
        task_types=None,
        statuses=None,
        include_recent_terminal=True,
        recent_terminal_limit=DEFAULT_RECENT_TERMINAL_LIMIT,
        limit=DEFAULT_LIMIT,
    ):
        query = self._build_query(
            task_types=task_types,
            statuses=statuses,
            include_recent_terminal=include_recent_terminal,
            recent_terminal_limit=recent_terminal_limit,
            limit=limit,
        )
        async_get_snapshot = getattr(
            self.repository,
            "async_get_task_monitor_snapshot",
            None,
        )
        if async_get_snapshot is not None:
            snapshot = await async_get_snapshot(
                task_types=query["task_types"],
                statuses=query["statuses"],
                limit=query["limit"],
            )
        else:
            snapshot = await asyncio.to_thread(
                self.repository.get_task_monitor_snapshot,
                task_types=query["task_types"],
                statuses=query["statuses"],
                limit=query["limit"],
            )
        return self._format_snapshot(
            snapshot=snapshot,
            consumer_id=consumer_id,
            recent_terminal_limit=query["recent_terminal_limit"],
            cap_terminal_tasks=query["cap_terminal_tasks"],
        )

    def get_fall_evidence_image(
        self,
        *,
        consumer_id=None,
        task_id=None,
        alert_id=None,
        evidence_image_id=None,
        result_seq=None,
    ):
        request = self._normalize_fall_evidence_request(
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
            limit=self.DEFAULT_EVIDENCE_ALERT_LOOKUP_LIMIT,
        )
        return self._query_fall_evidence_image_from_rows(rows, request)

    async def async_get_fall_evidence_image(
        self,
        *,
        consumer_id=None,
        task_id=None,
        alert_id=None,
        evidence_image_id=None,
        result_seq=None,
    ):
        request = self._normalize_fall_evidence_request(
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
                limit=self.DEFAULT_EVIDENCE_ALERT_LOOKUP_LIMIT,
            )
        else:
            rows = await asyncio.to_thread(
                self.repository.get_fall_evidence_alert_candidates,
                task_id=request["task_id"],
                limit=self.DEFAULT_EVIDENCE_ALERT_LOOKUP_LIMIT,
            )
        return await self._async_query_fall_evidence_image_from_rows(rows, request)

    def _query_fall_evidence_image_from_rows(self, rows, request):
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
            return self._fall_evidence_error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message=f"AI 증거 이미지 조회에 실패했습니다: {exc}",
                reason_code="AI_EVIDENCE_QUERY_FAILED",
                request=request,
                alert=alert,
            )

        return self._format_fall_evidence_response(response, request=request, alert=alert)

    async def _async_query_fall_evidence_image_from_rows(self, rows, request):
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
            return self._fall_evidence_error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message=f"AI 증거 이미지 조회에 실패했습니다: {exc}",
                reason_code="AI_EVIDENCE_QUERY_FAILED",
                request=request,
                alert=alert,
            )

        return self._format_fall_evidence_response(response, request=request, alert=alert)

    @classmethod
    def _normalize_fall_evidence_request(
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
                "error_response": cls._fall_evidence_error_response(
                    result_code="INVALID_REQUEST",
                    result_message="consumer_id가 필요합니다.",
                    reason_code="CONSUMER_ID_REQUIRED",
                    request=request,
                ),
            }
        if normalized_task_id is None:
            return {
                **request,
                "error_response": cls._fall_evidence_error_response(
                    result_code="INVALID_REQUEST",
                    result_message="task_id가 필요합니다.",
                    reason_code="TASK_ID_REQUIRED",
                    request=request,
                ),
            }
        if not normalized_evidence_image_id:
            return {
                **request,
                "error_response": cls._fall_evidence_error_response(
                    result_code="INVALID_REQUEST",
                    result_message="evidence_image_id가 필요합니다.",
                    reason_code="EVIDENCE_IMAGE_ID_REQUIRED",
                    request=request,
                ),
            }
        if result_seq not in (None, "") and normalized_result_seq is None:
            return {
                **request,
                "error_response": cls._fall_evidence_error_response(
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
                "error_response": cls._fall_evidence_error_response(
                    result_code="NOT_FOUND",
                    result_message="순찰 task 또는 낙상 alert를 찾을 수 없습니다.",
                    reason_code="FALL_ALERT_NOT_FOUND",
                    request=request,
                )
            }

        if any(str(row.get("task_type") or "").upper() not in {"", "PATROL"} for row in rows):
            return {
                "error_response": cls._fall_evidence_error_response(
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
            "error_response": cls._fall_evidence_error_response(
                result_code=result_code,
                result_message=result_message,
                reason_code=reason_code,
                request=request,
            )
        }

    @classmethod
    def _format_fall_evidence_response(cls, response, *, request, alert):
        payload = response if isinstance(response, dict) else {}
        result_code = str(payload.get("result_code") or "").strip().upper()
        if not result_code:
            return cls._fall_evidence_error_response(
                result_code="UPSTREAM_UNAVAILABLE",
                result_message="AI 증거 이미지 응답 형식이 올바르지 않습니다.",
                reason_code="AI_EVIDENCE_RESPONSE_INVALID",
                request=request,
                alert=alert,
            )

        size_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size_bytes > cls.MAX_EVIDENCE_RESPONSE_BYTES:
            return cls._fall_evidence_error_response(
                result_code="PAYLOAD_TOO_LARGE",
                result_message=(
                    "증거 이미지 응답 크기가 허용 범위를 초과했습니다."
                ),
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
    def _fall_evidence_error_response(
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

    @classmethod
    def _build_query(
        cls,
        *,
        task_types,
        statuses,
        include_recent_terminal,
        recent_terminal_limit,
        limit,
    ):
        explicit_statuses = statuses is not None
        normalized_statuses = cls._normalize_text_tuple(statuses)
        normalized_terminal_limit = cls._bounded_int(
            recent_terminal_limit,
            default=cls.DEFAULT_RECENT_TERMINAL_LIMIT,
            minimum=0,
            maximum=cls.MAX_RECENT_TERMINAL_LIMIT,
        )

        if not normalized_statuses:
            normalized_statuses = ACTIVE_TASK_STATUSES
            if include_recent_terminal and normalized_terminal_limit > 0:
                normalized_statuses = normalized_statuses + TERMINAL_TASK_STATUSES

        return {
            "task_types": cls._normalize_text_tuple(task_types),
            "statuses": normalized_statuses,
            "limit": cls._bounded_int(
                limit,
                default=cls.DEFAULT_LIMIT,
                minimum=1,
                maximum=cls.MAX_LIMIT,
            ),
            "recent_terminal_limit": normalized_terminal_limit,
            "cap_terminal_tasks": not explicit_statuses,
        }

    @classmethod
    def _format_snapshot(
        cls,
        *,
        snapshot,
        consumer_id,
        recent_terminal_limit,
        cap_terminal_tasks,
    ):
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        terminal_count = 0
        tasks = []

        for row in snapshot.get("tasks") or []:
            task = cls._format_task(row if isinstance(row, dict) else {})
            if cap_terminal_tasks and task["task_status"] in TERMINAL_TASK_STATUSES:
                if terminal_count >= recent_terminal_limit:
                    continue
                terminal_count += 1
            tasks.append(task)

        return {
            "result_code": "ACCEPTED",
            "result_message": None,
            "consumer_id": str(consumer_id or "").strip() or None,
            "last_event_seq": cls._optional_int(snapshot.get("last_event_seq")) or 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks,
        }

    @classmethod
    def _format_task(cls, row):
        task_status = row.get("task_status") or "UNKNOWN"
        task = {
            "task_id": row.get("task_id"),
            "task_type": row.get("task_type") or "UNKNOWN",
            "task_status": task_status,
            "task_outcome": row.get("task_outcome") or row.get("result_code"),
            "phase": row.get("phase"),
            "assigned_robot_id": row.get("assigned_robot_id"),
            "patrol_area_id": row.get("patrol_area_id"),
            "patrol_area_name": row.get("patrol_area_name"),
            "patrol_area_revision": row.get("patrol_area_revision"),
            "cancellable": task_status in CANCELLABLE_TASK_STATUSES,
            "latest_reason_code": row.get("latest_reason_code"),
            "requested_at": cls._isoformat(row.get("requested_at") or row.get("created_at")),
            "started_at": cls._isoformat(row.get("started_at")),
            "finished_at": cls._isoformat(row.get("finished_at")),
            "updated_at": cls._isoformat(row.get("updated_at")),
            "latest_feedback": cls._format_latest_feedback(row),
            "latest_robot": cls._format_latest_robot(row),
            "latest_alert": cls._format_latest_alert(row),
        }
        return task

    @classmethod
    def _format_latest_feedback(cls, row):
        nested = row.get("latest_feedback")
        if isinstance(nested, dict):
            return {
                "feedback_summary": nested.get("feedback_summary") or nested.get("summary"),
                "pose": nested.get("pose"),
                "updated_at": cls._isoformat(nested.get("updated_at")),
            }

        payload = cls._json_object(row.get("latest_feedback_payload_json"))
        if not payload:
            return None

        pose = payload.get("pose")
        if pose is None:
            pose = cls._pose_from_row(
                row,
                x_key="latest_feedback_pose_x",
                y_key="latest_feedback_pose_y",
                yaw_key="latest_feedback_pose_yaw",
                frame_key="latest_feedback_frame_id",
            )

        return {
            "feedback_summary": cls._build_feedback_summary(
                payload=payload,
                feedback_type=row.get("latest_feedback_type"),
            ),
            "pose": pose,
            "updated_at": cls._isoformat(row.get("latest_feedback_updated_at")),
        }

    @classmethod
    def _format_latest_robot(cls, row):
        nested = row.get("latest_robot")
        if isinstance(nested, dict):
            return {
                "robot_id": nested.get("robot_id"),
                "runtime_state": nested.get("runtime_state"),
                "battery_percent": nested.get("battery_percent"),
                "pose": nested.get("pose"),
                "last_seen_at": cls._isoformat(nested.get("last_seen_at")),
            }

        robot_id = row.get("latest_robot_id") or row.get("assigned_robot_id")
        if not robot_id:
            return None

        return {
            "robot_id": robot_id,
            "runtime_state": row.get("runtime_state"),
            "battery_percent": row.get("battery_percent"),
            "pose": cls._pose_from_row(
                row,
                x_key="pose_x",
                y_key="pose_y",
                yaw_key="pose_yaw",
                frame_key="frame_id",
            ),
            "last_seen_at": cls._isoformat(row.get("last_seen_at")),
        }

    @classmethod
    def _format_latest_alert(cls, row):
        nested = row.get("latest_alert")
        if isinstance(nested, dict):
            alert = dict(nested)
        else:
            payload = cls._json_object(row.get("latest_alert_payload_json"))
            if not payload:
                return None
            alert = dict(payload.get("trigger_result") or payload)
            if "command_response" not in alert and payload.get("command_response"):
                alert["command_response"] = payload.get("command_response")

        alert.setdefault("alert_id", row.get("latest_alert_id"))
        alert.setdefault("occurred_at", cls._isoformat(row.get("latest_alert_occurred_at")))
        return alert

    @classmethod
    def _build_feedback_summary(cls, *, payload, feedback_type):
        if payload.get("feedback_summary"):
            return payload.get("feedback_summary")
        if payload.get("summary"):
            return payload.get("summary")

        nested_payload = (
            payload.get("payload")
            if isinstance(payload.get("payload"), dict)
            else payload
        )
        normalized_type = str(feedback_type or payload.get("feedback_type") or "").strip()
        if normalized_type == "NAVIGATION_FEEDBACK":
            nav_status = nested_payload.get("nav_status") or "NAVIGATION"
            distance = nested_payload.get("distance_remaining_m")
            if distance is None:
                return str(nav_status)
            return f"{nav_status} / 남은 거리 {float(distance):.2f}m"

        if normalized_type == "MANIPULATION_FEEDBACK":
            processed_quantity = nested_payload.get("processed_quantity")
            if processed_quantity is None:
                return "로봇팔 작업 중"
            return f"처리 수량 {processed_quantity}"

        return normalized_type or "ACTION_FEEDBACK"

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

    @classmethod
    def _pose_from_row(cls, row, *, x_key, y_key, yaw_key, frame_key=None):
        x = row.get(x_key)
        y = row.get(y_key)
        yaw = row.get(yaw_key)
        frame_id = row.get(frame_key) if frame_key else None
        if x is None and y is None and yaw is None and frame_id is None:
            return None

        pose = {
            "x": x,
            "y": y,
            "yaw": yaw,
        }
        if frame_id is not None:
            pose["frame_id"] = frame_id
        return pose

    @staticmethod
    def _normalize_text_tuple(values):
        if values in (None, ""):
            return None
        if isinstance(values, str):
            values = [values]

        normalized = []
        for value in values or []:
            text = str(value or "").strip().upper()
            if text:
                normalized.append(text)
        return tuple(dict.fromkeys(normalized)) or None

    @staticmethod
    def _bounded_int(value, *, default, minimum, maximum):
        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            numeric_value = default
        return max(minimum, min(maximum, numeric_value))

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _isoformat(value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)


__all__ = [
    "ACTIVE_TASK_STATUSES",
    "TERMINAL_TASK_STATUSES",
    "TaskMonitorService",
]
