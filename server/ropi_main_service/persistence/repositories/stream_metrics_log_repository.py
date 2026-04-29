from server.ropi_main_service.persistence.async_connection import (
    async_execute,
    async_execute_many,
)
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.sql_loader import load_sql


class StreamMetricsLogRepository:
    def insert_stream_metrics_snapshot(self, snapshot):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    load_sql("stream_metrics/insert_stream_metrics_log.sql"),
                    self._build_params(snapshot),
                )
                return cur.rowcount
        finally:
            conn.close()

    async def async_insert_stream_metrics_snapshot(self, snapshot):
        return await async_execute(
            load_sql("stream_metrics/insert_stream_metrics_log.sql"),
            self._build_params(snapshot),
        )

    async def async_insert_stream_metrics_snapshots(self, snapshots):
        snapshots = list(snapshots or [])
        if not snapshots:
            return 0

        return await async_execute_many(
            load_sql("stream_metrics/insert_stream_metrics_log.sql"),
            [self._build_params(snapshot) for snapshot in snapshots],
        )

    @staticmethod
    def _build_params(snapshot):
        return (
            getattr(snapshot, "task_id", None),
            getattr(snapshot, "robot_id", None),
            getattr(snapshot, "stream_name"),
            getattr(snapshot, "direction"),
            getattr(snapshot, "window_started_at"),
            getattr(snapshot, "window_ended_at"),
            int(getattr(snapshot, "received_frame_count")),
            int(getattr(snapshot, "relayed_frame_count")),
            int(getattr(snapshot, "dropped_frame_count")),
            float(getattr(snapshot, "dropped_frame_rate")),
            int(getattr(snapshot, "incomplete_frame_count")),
            int(getattr(snapshot, "crc_mismatch_count")),
            int(getattr(snapshot, "assembly_timeout_count")),
            _optional_float(getattr(snapshot, "avg_latency_ms", None)),
            _optional_float(getattr(snapshot, "max_latency_ms", None)),
            getattr(snapshot, "latest_frame_id", None),
        )


def _optional_float(value):
    if value is None:
        return None
    return float(value)


__all__ = ["StreamMetricsLogRepository"]
