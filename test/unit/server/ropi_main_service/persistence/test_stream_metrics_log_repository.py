from server.ropi_main_service.persistence.repositories.stream_metrics_log_repository import (
    StreamMetricsLogRepository,
)
from server.ropi_main_service.transport.vision_frame_gateway import (
    StreamMetricsSnapshot,
)


def test_stream_metrics_log_repository_builds_insert_params():
    snapshot = StreamMetricsSnapshot(
        task_id=None,
        robot_id="pinky3",
        stream_name="pinky3_cam_patrol",
        direction="ROBOT_TO_CONTROL_TO_AI",
        window_started_at="2026-04-29T10:00:00",
        window_ended_at="2026-04-29T10:00:10",
        received_frame_count=12,
        relayed_frame_count=11,
        dropped_frame_count=1,
        dropped_frame_rate=1 / 12,
        incomplete_frame_count=0,
        crc_mismatch_count=1,
        assembly_timeout_count=0,
        avg_latency_ms=4.5,
        max_latency_ms=8.0,
        latest_frame_id=77,
    )

    params = StreamMetricsLogRepository._build_params(snapshot)

    assert params == (
        None,
        "pinky3",
        "pinky3_cam_patrol",
        "ROBOT_TO_CONTROL_TO_AI",
        "2026-04-29T10:00:00",
        "2026-04-29T10:00:10",
        12,
        11,
        1,
        1 / 12,
        0,
        1,
        0,
        4.5,
        8.0,
        77,
    )
