import os

from server.ropi_main_service.application.fall_inference_result import (
    FallInferenceResultProcessor,
)
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)


ENABLED_VALUES = {"1", "true", "yes", "on"}


def start_fall_inference_stream_if_enabled(
    *,
    loop=None,
    task_event_publisher=None,
    workflow_task_manager=None,
    client=None,
    processor=None,
):
    if not _fall_inference_stream_enabled():
        return None

    workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
    if client is None:
        from server.ropi_main_service.transport.fall_inference_stream import (
            FallInferenceStreamClient,
        )

        client = FallInferenceStreamClient.from_env()
    processor = processor or FallInferenceResultProcessor(
        task_event_publisher=task_event_publisher,
        pinky_id=client.pinky_id,
    )
    return workflow_task_manager.create_task(
        client.run_forever(processor.async_process_batch),
        name="fall_inference_stream",
        loop=loop,
        cancel_on_shutdown=True,
    )


def _fall_inference_stream_enabled():
    return str(os.getenv("AI_FALL_STREAM_ENABLED", "")).strip().lower() in ENABLED_VALUES


__all__ = [
    "start_fall_inference_stream_if_enabled",
]
