import asyncio
import logging

from server.ropi_main_service.persistence.repositories.robot_data_log_repository import (
    RobotDataLogRepository,
)


logger = logging.getLogger(__name__)
DEFAULT_DB_WRITE_QUEUE_SIZE = 1000
ROBOT_DATA_LOG_SAMPLE = "robot_data_log_sample"
STOP = object()
_default_background_db_writer = None


class BackgroundDbWriter:
    def __init__(
        self,
        *,
        robot_data_log_repository=None,
        max_queue_size=DEFAULT_DB_WRITE_QUEUE_SIZE,
    ):
        self.robot_data_log_repository = robot_data_log_repository or RobotDataLogRepository()
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


def get_default_background_db_writer() -> BackgroundDbWriter:
    global _default_background_db_writer

    if _default_background_db_writer is None:
        _default_background_db_writer = BackgroundDbWriter()

    return _default_background_db_writer


__all__ = [
    "BackgroundDbWriter",
    "get_default_background_db_writer",
]
