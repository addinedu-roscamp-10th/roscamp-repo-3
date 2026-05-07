import asyncio
import logging
import os

from server.ropi_main_service.application.guide_phase_snapshot import (
    GuidePhaseSnapshotProcessor,
)
from server.ropi_main_service.application.guide_runtime import (
    DEFAULT_GUIDE_PINKY_ID,
    GuideRuntimeService,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)


DISABLED_VALUES = {"0", "false", "no", "off"}
DEFAULT_POLL_INTERVAL_SEC = 0.25
TASK_UPDATE_SOURCE = "GUIDE_PHASE_SNAPSHOT"

logger = logging.getLogger(__name__)


class GuidePhaseSnapshotRuntimePoller:
    def __init__(
        self,
        *,
        runtime_service=None,
        processor=None,
        task_update_publisher=None,
        pinky_id=DEFAULT_GUIDE_PINKY_ID,
        poll_interval_sec=DEFAULT_POLL_INTERVAL_SEC,
    ):
        self.runtime_service = runtime_service or GuideRuntimeService(
            default_pinky_id=pinky_id,
        )
        self.processor = processor or GuidePhaseSnapshotProcessor()
        self.task_update_publisher = task_update_publisher
        self.pinky_id = str(pinky_id or "").strip() or DEFAULT_GUIDE_PINKY_ID
        self.poll_interval_sec = max(0.01, float(poll_interval_sec))

    async def run_forever(self):
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                logger.warning(
                    "guide phase snapshot polling failed: %s",
                    exc,
                    exc_info=True,
                )
            await asyncio.sleep(self.poll_interval_sec)

    async def poll_once(self):
        status = await self.runtime_service.async_get_status(pinky_id=self.pinky_id)
        snapshot = self._extract_snapshot(status)
        if snapshot is None:
            return {
                "result_code": "IGNORED",
                "reason_code": "GUIDE_PHASE_SNAPSHOT_MISSING",
                "result_message": "guide runtime snapshot is not available.",
            }

        response = await self.processor.async_process(snapshot)
        await self._publish_task_update_if_needed(response)
        return response

    @classmethod
    def _extract_snapshot(cls, status):
        status = status if isinstance(status, dict) else {}
        runtime = status.get("guide_runtime") or {}
        update = runtime.get("last_update")
        if not isinstance(update, dict):
            return None

        task_id = str(update.get("task_id") or "").strip()
        guide_phase = str(update.get("guide_phase") or "").strip()
        if not task_id or not guide_phase:
            return None

        return {
            "task_id": task_id,
            "pinky_id": str(
                update.get("pinky_id")
                or runtime.get("pinky_id")
                or status.get("pinky_id")
                or ""
            ).strip(),
            "guide_phase": guide_phase,
            "target_track_id": update.get("target_track_id", -1),
            "reason_code": str(update.get("reason_code") or "").strip(),
            "seq": update.get("seq", 0),
            "occurred_at": cls._extract_time(update, prefix="occurred_at"),
        }

    @staticmethod
    def _extract_time(update, *, prefix):
        sec = update.get(f"{prefix}_sec")
        nanosec = update.get(f"{prefix}_nanosec")
        if sec is None and nanosec is None:
            return update.get(prefix)
        return {
            "sec": GuidePhaseSnapshotRuntimePoller._safe_int(sec),
            "nanosec": GuidePhaseSnapshotRuntimePoller._safe_int(nanosec),
        }

    @staticmethod
    def _safe_int(value):
        try:
            return int(str(value or "0").strip())
        except (TypeError, ValueError):
            return 0

    async def _publish_task_update_if_needed(self, response):
        if self.task_update_publisher is None:
            return
        if not isinstance(response, dict):
            return
        if response.get("result_code") != "ACCEPTED":
            return
        publish_from_response = getattr(
            self.task_update_publisher,
            "publish_from_response",
            None,
        )
        if publish_from_response is None:
            return
        await publish_from_response(
            response,
            source=TASK_UPDATE_SOURCE,
            task_type="GUIDE",
        )


def start_guide_phase_snapshot_polling_if_enabled(
    *,
    loop=None,
    workflow_task_manager=None,
    runtime_service=None,
    processor=None,
    task_update_publisher=None,
    pinky_id=None,
    poll_interval_sec=None,
):
    if not _guide_phase_snapshot_poll_enabled():
        logger.info(
            "Guide phase snapshot polling is disabled; set GUIDE_PHASE_SNAPSHOT_POLL_ENABLED=true to enable it."
        )
        return None

    target_pinky_id = (
        str(pinky_id or os.getenv("GUIDE_PHASE_SNAPSHOT_PINKY_ID") or "").strip()
        or DEFAULT_GUIDE_PINKY_ID
    )
    interval_sec = (
        float(poll_interval_sec)
        if poll_interval_sec is not None
        else _guide_phase_snapshot_poll_interval_sec()
    )
    workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
    poller = GuidePhaseSnapshotRuntimePoller(
        runtime_service=runtime_service,
        processor=processor,
        task_update_publisher=task_update_publisher,
        pinky_id=target_pinky_id,
        poll_interval_sec=interval_sec,
    )
    logger.info(
        "Starting guide phase snapshot poller pinky_id=%s interval_sec=%s",
        target_pinky_id,
        interval_sec,
    )
    return workflow_task_manager.create_task(
        poller.run_forever(),
        name="guide_phase_snapshot_poll",
        loop=loop,
        cancel_on_shutdown=True,
    )


def _guide_phase_snapshot_poll_enabled():
    raw = str(os.getenv("GUIDE_PHASE_SNAPSHOT_POLL_ENABLED", "true")).strip().lower()
    return raw not in DISABLED_VALUES


def _guide_phase_snapshot_poll_interval_sec():
    raw = str(os.getenv("GUIDE_PHASE_SNAPSHOT_POLL_INTERVAL_SEC", "")).strip()
    if not raw:
        return DEFAULT_POLL_INTERVAL_SEC
    try:
        return max(0.01, float(raw))
    except ValueError:
        return DEFAULT_POLL_INTERVAL_SEC


__all__ = [
    "GuidePhaseSnapshotRuntimePoller",
    "start_guide_phase_snapshot_polling_if_enabled",
]
