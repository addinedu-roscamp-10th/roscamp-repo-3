import logging

from server.ropi_main_service.application.guide_tracking_update import (
    GuideTrackingUpdatePublisherService,
)
from server.ropi_main_service.application.guide_tracking_snapshot import (
    get_default_guide_tracking_snapshot_store,
)
from server.ropi_main_service.persistence.repositories.guide_tracking_repository import (
    GuideTrackingRepository,
)


DEFAULT_GUIDE_PINKY_ID = "pinky1"
FORWARDABLE_TRACKING_STATUSES = {"TRACKING", "LOST"}

logger = logging.getLogger(__name__)


class GuideTrackingResultProcessor:
    def __init__(
        self,
        *,
        repository=None,
        update_publisher=None,
        snapshot_store=None,
        task_event_publisher=None,
        pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.repository = repository or GuideTrackingRepository()
        self.update_publisher = update_publisher or GuideTrackingUpdatePublisherService()
        self.snapshot_store = snapshot_store or get_default_guide_tracking_snapshot_store()
        self.task_event_publisher = task_event_publisher
        self.pinky_id = str(pinky_id or DEFAULT_GUIDE_PINKY_ID).strip() or DEFAULT_GUIDE_PINKY_ID

    async def async_process_batch(self, batch):
        results = list((batch or {}).get("results") or [])
        summary = {
            "processed_count": 0,
            "published_count": 0,
            "ignored_count": 0,
            "failed_count": 0,
        }

        for result in results:
            outcome = await self._async_process_result(result if isinstance(result, dict) else {})
            summary["processed_count"] += 1
            if outcome.get("published"):
                summary["published_count"] += 1
            if outcome.get("ignored"):
                summary["ignored_count"] += 1
            if outcome.get("failed"):
                summary["failed_count"] += 1

        return summary

    async def _async_process_result(self, result):
        robot_id = self._result_robot_id(result)
        tracking_status = self._normalize_tracking_status(result.get("tracking_status"))
        active_task = await self.repository.async_get_active_guide_task_for_robot(robot_id)
        snapshot = self._build_snapshot(result, robot_id=robot_id, active_task=active_task)
        if snapshot is not None:
            self.snapshot_store.record(snapshot)

        update = self._build_update(result, robot_id=robot_id, active_task=active_task)

        if update is None:
            logger.info(
                "Ignored AI guide tracking result robot_id=%s result_seq=%s tracking_status=%s",
                robot_id,
                result.get("result_seq"),
                tracking_status,
            )
            return {"ignored": True}

        try:
            response = await self.update_publisher.async_publish(**update)
        except Exception:
            logger.exception(
                "Failed to publish guide tracking update robot_id=%s task_id=%s result_seq=%s",
                robot_id,
                update.get("task_id"),
                update.get("tracking_result_seq"),
            )
            return {"failed": True}

        if not self._publish_accepted(response):
            logger.warning(
                "Guide tracking update publish rejected robot_id=%s task_id=%s result_seq=%s response=%s",
                robot_id,
                update.get("task_id"),
                update.get("tracking_result_seq"),
                response,
            )
            return {"failed": True}

        await self._publish_task_updated(update)
        return {"published": True}

    def _build_snapshot(self, result, *, robot_id, active_task):
        if not active_task:
            return None

        active_track_id = self._optional_text(result.get("active_track_id"))
        bbox = self._find_bbox_for_track(
            result,
            target_track_id=active_track_id,
        )
        bbox_valid = bbox is not None
        return {
            "task_id": active_task.get("task_id"),
            "pinky_id": robot_id,
            "task_status": active_task.get("task_status"),
            "phase": active_task.get("phase"),
            "guide_phase": active_task.get("guide_phase"),
            "adopted_target_track_id": self._optional_text(
                active_task.get("target_track_id")
            ),
            "active_track_id": active_track_id,
            "tracking_status": self._normalize_tracking_status(
                result.get("tracking_status")
            ),
            "tracking_result_seq": self._optional_int(result.get("result_seq")) or 0,
            "frame_ts": str(result.get("frame_ts") or "").strip(),
            "confidence": result.get("confidence"),
            "bbox_valid": bbox_valid,
            "bbox_xyxy": bbox if bbox_valid else [0, 0, 0, 0],
            "image_width_px": self._optional_int(result.get("image_width_px")) or 0,
            "image_height_px": self._optional_int(result.get("image_height_px")) or 0,
            "candidate_tracks": [
                dict(candidate)
                for candidate in (result.get("candidate_tracks") or [])
                if isinstance(candidate, dict)
            ],
        }

    def _build_update(self, result, *, robot_id, active_task):
        if not active_task:
            return None

        target_track_id = self._optional_text(active_task.get("target_track_id"))
        if target_track_id is None:
            return None

        tracking_status = self._normalize_tracking_status(result.get("tracking_status"))
        if tracking_status not in FORWARDABLE_TRACKING_STATUSES:
            return None

        active_track_id = self._optional_text(result.get("active_track_id"))
        if active_track_id is not None and active_track_id != target_track_id:
            return None

        if tracking_status == "TRACKING":
            bbox = self._find_bbox_for_track(result, target_track_id=target_track_id)
            if bbox is None:
                return None
            bbox_valid = True
        else:
            bbox = [0, 0, 0, 0]
            bbox_valid = False

        return {
            "pinky_id": robot_id,
            "task_id": active_task.get("task_id"),
            "target_track_id": target_track_id,
            "tracking_status": tracking_status,
            "tracking_result_seq": self._optional_int(result.get("result_seq")) or 0,
            "frame_ts": str(result.get("frame_ts") or "").strip(),
            "bbox_valid": bbox_valid,
            "bbox_xyxy": bbox,
            "image_width_px": self._optional_int(result.get("image_width_px")) or 0,
            "image_height_px": self._optional_int(result.get("image_height_px")) or 0,
        }

    @classmethod
    def _find_bbox_for_track(cls, result, *, target_track_id):
        if target_track_id is None:
            return None

        top_level_bbox = result.get("bbox_xyxy")
        if cls._valid_bbox(top_level_bbox):
            return [int(value) for value in top_level_bbox]

        for candidate in result.get("candidate_tracks") or []:
            if not isinstance(candidate, dict):
                continue
            if cls._optional_text(candidate.get("track_id")) != target_track_id:
                continue
            candidate_bbox = candidate.get("bbox_xyxy")
            if cls._valid_bbox(candidate_bbox):
                return [int(value) for value in candidate_bbox]
        return None

    async def _publish_task_updated(self, update):
        if self.task_event_publisher is None:
            return

        phase = (
            "GUIDANCE_RUNNING"
            if update.get("tracking_status") == "TRACKING"
            else "WAIT_REIDENTIFY"
        )
        await self.task_event_publisher.publish(
            "TASK_UPDATED",
            {
                "source": "GUIDE_TRACKING",
                "task_id": update.get("task_id"),
                "task_type": "GUIDE",
                "task_status": "RUNNING",
                "phase": phase,
                "assigned_robot_id": update.get("pinky_id"),
                "latest_reason_code": f"GUIDE_TRACKING_{update.get('tracking_status')}",
                "result_code": "ACCEPTED",
                "result_message": "안내 tracking 갱신을 전달했습니다.",
                "cancel_requested": None,
                "cancellable": True,
                "guide_detail": {
                    "guide_phase": phase,
                    "target_track_id": update.get("target_track_id"),
                },
            },
        )

    def _result_robot_id(self, result):
        return self._optional_text(result.get("pinky_id")) or self.pinky_id

    @staticmethod
    def _normalize_tracking_status(value):
        return str(value or "").strip().upper()

    @staticmethod
    def _publish_accepted(response):
        if not isinstance(response, dict):
            return False
        if response.get("accepted") is True:
            return True
        return str(response.get("result_code") or "").strip().upper() == "ACCEPTED"

    @staticmethod
    def _valid_bbox(value):
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return False
        try:
            [int(item) for item in value]
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _optional_text(value):
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["GuideTrackingResultProcessor"]
