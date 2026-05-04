import logging
import os

from server.ropi_main_service.application.guide_tracking_result import (
    GuideTrackingResultProcessor,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)


ENABLED_VALUES = {"1", "true", "yes", "on"}

logger = logging.getLogger(__name__)


def start_guide_tracking_stream_if_enabled(
    *,
    loop=None,
    task_event_publisher=None,
    workflow_task_manager=None,
    client=None,
    processor=None,
):
    if not _guide_tracking_stream_enabled():
        logger.info(
            "AI guide tracking stream is disabled; set AI_GUIDE_TRACKING_STREAM_ENABLED=true to enable it."
        )
        return None

    workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
    if client is None:
        from server.ropi_main_service.transport.guide_tracking_stream import (
            GuideTrackingStreamClient,
        )

        client = GuideTrackingStreamClient.from_env()
    logger.info(
        "Starting AI guide tracking stream client host=%s port=%s consumer_id=%s pinky_id=%s last_seq=%s",
        getattr(client, "host", None),
        getattr(client, "port", None),
        getattr(client, "consumer_id", None),
        getattr(client, "pinky_id", None),
        getattr(client, "last_seq", None),
    )
    processor = processor or GuideTrackingResultProcessor(
        task_event_publisher=task_event_publisher,
        pinky_id=client.pinky_id,
    )
    return workflow_task_manager.create_task(
        client.run_forever(processor.async_process_batch),
        name="guide_tracking_stream",
        loop=loop,
        cancel_on_shutdown=True,
    )


def _guide_tracking_stream_enabled():
    return (
        str(os.getenv("AI_GUIDE_TRACKING_STREAM_ENABLED", "")).strip().lower()
        in ENABLED_VALUES
    )


__all__ = [
    "start_guide_tracking_stream_if_enabled",
]
