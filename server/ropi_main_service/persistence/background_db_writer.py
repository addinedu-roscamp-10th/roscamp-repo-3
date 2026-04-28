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
DEFAULT_DB_WRITE_BATCH_SIZE = 100
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
        max_batch_size=DEFAULT_DB_WRITE_BATCH_SIZE,
    ):
        self.robot_data_log_repository = robot_data_log_repository or RobotDataLogRepository()
        self.robot_runtime_status_repository = robot_runtime_status_repository or RobotRuntimeStatusRepository()
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.max_batch_size = int(max_batch_size)
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
            batch, should_stop = self._drain_batch(item)
            try:
                await self._write_batch(batch)
            except Exception:
                logger.exception(
                    "background db writer failed to process batch",
                    extra={"batch_size": len(batch)},
                )
            finally:
                for _ in batch:
                    self.queue.task_done()

            if should_stop:
                return

    def _drain_batch(self, first_item):
        batch = [first_item]
        should_stop = first_item is STOP

        while not should_stop and len(batch) < self.max_batch_size:
            try:
                item = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            batch.append(item)
            should_stop = item is STOP

        return batch, should_stop

    async def _write_item(self, item: dict):
        await self._write_batch([item])

    async def _write_batch(self, batch):
        robot_data_log_samples = []
        runtime_status_by_robot_id = {}

        for item in batch:
            if item is STOP:
                continue

            item_type = self._get_item_type(item)
            payload = item.get("payload") or {}

            if item_type == ROBOT_DATA_LOG_SAMPLE:
                robot_data_log_samples.append(payload)
                status = self._build_runtime_status_from_sample(payload)
                if status is not None:
                    runtime_status_by_robot_id[status["robot_id"]] = status
                continue

            if item_type == ROBOT_RUNTIME_STATUS:
                robot_id = str(payload.get("robot_id") or "").strip()
                if robot_id:
                    runtime_status_by_robot_id[robot_id] = payload
                continue

            logger.warning(
                "background db writer received unknown item type",
                extra={"item_type": item_type},
            )

        if robot_data_log_samples:
            await self.robot_data_log_repository.async_insert_feedback_samples(robot_data_log_samples)

        if runtime_status_by_robot_id:
            await self.robot_runtime_status_repository.async_upsert_runtime_statuses(
                list(runtime_status_by_robot_id.values())
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
