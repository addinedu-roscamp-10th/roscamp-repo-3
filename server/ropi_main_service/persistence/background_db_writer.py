import asyncio
import logging

from server.ropi_main_service.persistence.repositories.robot_data_log_repository import (
    RobotDataLogRepository,
)
from server.ropi_main_service.persistence.repositories.robot_runtime_status_repository import (
    RobotRuntimeStatusRepository,
)


logger = logging.getLogger(__name__)
DEFAULT_DB_WRITE_QUEUE_SIZE = 1000
ROBOT_DATA_LOG_SAMPLE = "robot_data_log_sample"
ROBOT_RUNTIME_STATUS = "robot_runtime_status"
STOP = object()
_default_background_db_writer = None


class BackgroundDbWriter:
    def __init__(
        self,
        *,
        robot_data_log_repository=None,
        robot_runtime_status_repository=None,
        max_queue_size=DEFAULT_DB_WRITE_QUEUE_SIZE,
    ):
        self.robot_data_log_repository = robot_data_log_repository or RobotDataLogRepository()
        self.robot_runtime_status_repository = robot_runtime_status_repository or RobotRuntimeStatusRepository()
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self._task = None

    def start(self):
        if self._task is not None and not self._task.done():
            return self._task

        loop = asyncio.get_running_loop()
        self._task = loop.create_task(
            self._run(),
            name="ropi_background_db_writer",
        )
        return self._task

    async def stop(self):
        task = self._task
        if task is None:
            return

        if not task.done():
            await self.queue.put(STOP)
            await task

        self._task = None

    async def flush(self):
        await self.queue.join()

    def enqueue_robot_data_log_sample(self, sample: dict) -> bool:
        return self._enqueue(
            {
                "type": ROBOT_DATA_LOG_SAMPLE,
                "payload": dict(sample),
            }
        )

    def enqueue_robot_runtime_status(self, status: dict) -> bool:
        return self._enqueue(
            {
                "type": ROBOT_RUNTIME_STATUS,
                "payload": dict(status),
            }
        )

    def _enqueue(self, item: dict) -> bool:
        try:
            self.queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            logger.warning(
                "background db writer queue is full; dropping db write item",
                extra={"item_type": item.get("type")},
            )
            return False

    async def _run(self):
        while True:
            item = await self.queue.get()
            try:
                if item is STOP:
                    return
                await self._write_item(item)
            except Exception:
                logger.exception(
                    "background db writer failed to process item",
                    extra={"item_type": self._get_item_type(item)},
                )
            finally:
                self.queue.task_done()

    async def _write_item(self, item: dict):
        item_type = item.get("type")
        payload = item.get("payload") or {}

        if item_type == ROBOT_DATA_LOG_SAMPLE:
            await self.robot_data_log_repository.async_insert_feedback_sample(**payload)
            status = self._build_runtime_status_from_sample(payload)
            if status is not None:
                await self.robot_runtime_status_repository.async_upsert_runtime_status(**status)
            return

        if item_type == ROBOT_RUNTIME_STATUS:
            await self.robot_runtime_status_repository.async_upsert_runtime_status(**payload)
            return

        logger.warning(
            "background db writer received unknown item type",
            extra={"item_type": item_type},
        )

    @staticmethod
    def _get_item_type(item):
        if isinstance(item, dict):
            return item.get("type")
        if item is STOP:
            return "stop"
        return type(item).__name__

    @classmethod
    def _build_runtime_status_from_sample(cls, sample: dict):
        robot_id = str(sample.get("robot_id") or "").strip()
        if not robot_id:
            return None

        return {
            "robot_id": robot_id,
            "robot_kind": cls._infer_robot_kind(robot_id),
            "runtime_state": "RUNNING",
            "active_task_id": sample.get("task_id"),
            "battery_percent": sample.get("battery_percent"),
            "pose_x": sample.get("pose_x"),
            "pose_y": sample.get("pose_y"),
            "pose_yaw": sample.get("pose_yaw"),
            "frame_id": cls._extract_frame_id(sample.get("payload") or {}),
            "fault_code": None,
        }

    @staticmethod
    def _infer_robot_kind(robot_id: str) -> str:
        normalized = robot_id.lower()
        if normalized.startswith("pinky"):
            return "PINKY"
        if normalized.startswith("jetcobot"):
            return "JETCOBOT"
        return "UNKNOWN"

    @staticmethod
    def _extract_frame_id(feedback_payload: dict):
        payload = feedback_payload.get("payload")
        if not isinstance(payload, dict):
            return None

        current_pose = payload.get("current_pose")
        if not isinstance(current_pose, dict):
            return None

        header = current_pose.get("header")
        if not isinstance(header, dict):
            return None

        frame_id = str(header.get("frame_id") or "").strip()
        return frame_id or None


def get_default_background_db_writer() -> BackgroundDbWriter:
    global _default_background_db_writer

    if _default_background_db_writer is None:
        _default_background_db_writer = BackgroundDbWriter()

    return _default_background_db_writer


__all__ = [
    "BackgroundDbWriter",
    "get_default_background_db_writer",
]
