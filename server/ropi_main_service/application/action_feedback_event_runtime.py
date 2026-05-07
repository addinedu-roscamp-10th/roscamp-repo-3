import asyncio
import json
import logging
import os

from server.ropi_main_service.application.action_feedback import (
    RosActionFeedbackService,
)
from server.ropi_main_service.application.task_monitor import (
    ACTIVE_TASK_STATUSES,
    TaskMonitorService,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)

logger = logging.getLogger(__name__)

DISABLED_VALUES = {"0", "false", "no", "off", "disabled"}
DEFAULT_POLL_INTERVAL_SEC = 0.5
DEFAULT_ACTIVE_TASK_LIMIT = 50
DEFAULT_SEEN_KEY_LIMIT = 1000
TASK_EVENT_TYPE = "ACTION_FEEDBACK_UPDATED"
TASK_EVENT_CONSUMER_ID = "action_feedback_event_runtime"


class ActionFeedbackEventRuntime:
    def __init__(
        self,
        *,
        task_monitor_service=None,
        feedback_service=None,
        task_event_publisher=None,
        poll_interval_sec=DEFAULT_POLL_INTERVAL_SEC,
        active_task_limit=DEFAULT_ACTIVE_TASK_LIMIT,
        seen_key_limit=DEFAULT_SEEN_KEY_LIMIT,
    ):
        self.task_monitor_service = task_monitor_service or TaskMonitorService()
        self.feedback_service = feedback_service or RosActionFeedbackService()
        self.task_event_publisher = task_event_publisher
        self.poll_interval_sec = max(0.01, float(poll_interval_sec))
        self.active_task_limit = max(1, int(active_task_limit))
        self.seen_key_limit = max(1, int(seen_key_limit))
        self._seen_keys = set()
        self._seen_key_order = []

    async def run_forever(self):
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                logger.warning(
                    "action feedback event polling failed: %s",
                    exc,
                    exc_info=True,
                )
            await asyncio.sleep(self.poll_interval_sec)

    async def poll_once(self):
        active_task_ids = await self._get_active_task_ids()
        published_count = 0

        for task_id in active_task_ids:
            try:
                response = await self.feedback_service.async_get_latest_feedback(
                    task_id=task_id,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "action feedback polling failed task_id=%s: %s",
                    task_id,
                    exc,
                )
                continue

            response = response if isinstance(response, dict) else {}
            for feedback in response.get("feedback") or []:
                payload = self._build_event_payload(
                    response=response,
                    feedback=feedback,
                    default_task_id=task_id,
                )
                if payload is None:
                    continue

                dedupe_key = self._build_dedupe_key(feedback=feedback, payload=payload)
                if dedupe_key in self._seen_keys:
                    continue

                await self._publish(payload)
                self._remember_dedupe_key(dedupe_key)
                published_count += 1

        return {
            "result_code": "ACCEPTED",
            "active_task_count": len(active_task_ids),
            "published_count": published_count,
        }

    async def _get_active_task_ids(self):
        snapshot = await self.task_monitor_service.async_get_task_monitor_snapshot(
            consumer_id=TASK_EVENT_CONSUMER_ID,
            statuses=ACTIVE_TASK_STATUSES,
            include_recent_terminal=False,
            limit=self.active_task_limit,
        )
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        task_ids = []
        seen = set()
        for task in snapshot.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            task_id = self._normalize_task_id(task.get("task_id"))
            if task_id is None or task_id in seen:
                continue
            seen.add(task_id)
            task_ids.append(task_id)
        return task_ids

    async def _publish(self, payload):
        if self.task_event_publisher is None:
            return None
        publish = getattr(self.task_event_publisher, "publish", None)
        if publish is None:
            publish = self.task_event_publisher
        result = publish(TASK_EVENT_TYPE, payload)
        if asyncio.iscoroutine(result):
            return await result
        return result

    @classmethod
    def _build_event_payload(cls, *, response, feedback, default_task_id):
        if not isinstance(feedback, dict):
            return None

        raw_payload = feedback.get("payload")
        payload_snapshot = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        task_id = cls._normalize_task_id(
            feedback.get("task_id") or response.get("task_id") or default_task_id
        )
        if task_id is None:
            return None

        feedback_type = (
            str(feedback.get("feedback_type") or "ACTION_FEEDBACK").strip()
            or "ACTION_FEEDBACK"
        )
        pose = payload_snapshot.get("current_pose") or payload_snapshot.get("pose")
        normalized_pose = TaskMonitorService._normalize_pose_payload(pose)

        return {
            "task_id": task_id,
            "action_name": cls._normalize_optional_text(
                feedback.get("action_name") or response.get("action_name")
            ),
            "action_type": cls._normalize_optional_text(feedback.get("action_type")),
            "feedback_type": feedback_type,
            "feedback_summary": cls._build_feedback_summary(
                feedback=feedback,
                feedback_type=feedback_type,
            ),
            "pose": normalized_pose,
            "current_pose": normalized_pose,
            "patrol_status": payload_snapshot.get("patrol_status"),
            "current_waypoint_index": TaskMonitorService._optional_int(
                payload_snapshot.get("current_waypoint_index")
            ),
            "total_waypoints": TaskMonitorService._optional_int(
                payload_snapshot.get("total_waypoints")
            ),
            "distance_remaining_m": TaskMonitorService._optional_float(
                payload_snapshot.get("distance_remaining_m")
            ),
            "received_at": cls._normalize_optional_text(feedback.get("received_at")),
            "payload": payload_snapshot,
        }

    @staticmethod
    def _build_feedback_summary(*, feedback, feedback_type):
        try:
            return TaskMonitorService._build_feedback_summary(
                payload=feedback,
                feedback_type=feedback_type,
            )
        except (TypeError, ValueError):
            return feedback_type or "ACTION_FEEDBACK"

    @staticmethod
    def _build_dedupe_key(*, feedback, payload):
        feedback = feedback if isinstance(feedback, dict) else {}
        key_payload = {
            "client": feedback.get("client"),
            "task_id": payload.get("task_id"),
            "action_name": payload.get("action_name"),
            "feedback_type": payload.get("feedback_type"),
            "received_at": payload.get("received_at"),
            "payload": payload.get("payload"),
        }
        return json.dumps(key_payload, sort_keys=True, default=str)

    def _remember_dedupe_key(self, dedupe_key):
        self._seen_keys.add(dedupe_key)
        self._seen_key_order.append(dedupe_key)
        while len(self._seen_key_order) > self.seen_key_limit:
            old_key = self._seen_key_order.pop(0)
            self._seen_keys.discard(old_key)

    @staticmethod
    def _normalize_task_id(value):
        normalized = str(value or "").strip()
        if not normalized:
            return None
        if normalized.isdigit():
            return int(normalized)
        return normalized

    @staticmethod
    def _normalize_optional_text(value):
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


def start_action_feedback_event_polling_if_enabled(
    *,
    loop=None,
    workflow_task_manager=None,
    task_monitor_service=None,
    feedback_service=None,
    task_event_publisher=None,
    poll_interval_sec=None,
):
    if not _action_feedback_event_poll_enabled():
        logger.info(
            "Action feedback event polling is disabled; set ACTION_FEEDBACK_EVENT_POLL_ENABLED=true to enable it."
        )
        return None

    interval_sec = (
        float(poll_interval_sec)
        if poll_interval_sec is not None
        else _action_feedback_event_poll_interval_sec()
    )
    workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
    runtime = ActionFeedbackEventRuntime(
        task_monitor_service=task_monitor_service,
        feedback_service=feedback_service,
        task_event_publisher=task_event_publisher,
        poll_interval_sec=interval_sec,
    )
    logger.info(
        "Starting action feedback event poller interval_sec=%s active_task_limit=%s",
        interval_sec,
        runtime.active_task_limit,
    )
    return workflow_task_manager.create_task(
        runtime.run_forever(),
        name="action_feedback_event_poll",
        loop=loop,
        cancel_on_shutdown=True,
    )


def _action_feedback_event_poll_enabled():
    raw = str(os.getenv("ACTION_FEEDBACK_EVENT_POLL_ENABLED", "true")).strip().lower()
    return raw not in DISABLED_VALUES


def _action_feedback_event_poll_interval_sec():
    raw = str(os.getenv("ACTION_FEEDBACK_EVENT_POLL_INTERVAL_SEC", "")).strip()
    if not raw:
        return DEFAULT_POLL_INTERVAL_SEC
    try:
        return max(0.01, float(raw))
    except ValueError:
        return DEFAULT_POLL_INTERVAL_SEC


__all__ = [
    "ActionFeedbackEventRuntime",
    "start_action_feedback_event_polling_if_enabled",
]
