import asyncio
from datetime import UTC, datetime

from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


GUIDE_TRACKING_UPDATE_COMMAND = "publish_guide_tracking_update"
DEFAULT_GUIDE_TRACKING_UPDATE_TIMEOUT_SEC = 1.0


class GuideTrackingUpdatePublisherService:
    def __init__(
        self,
        *,
        command_client=None,
        timeout_sec=DEFAULT_GUIDE_TRACKING_UPDATE_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.timeout_sec = float(timeout_sec)

    def publish(self, **kwargs):
        payload = self.build_payload(**kwargs)
        return self.command_client.send_command(
            GUIDE_TRACKING_UPDATE_COMMAND,
            payload,
            timeout=self.timeout_sec,
        )

    async def async_publish(self, **kwargs):
        payload = self.build_payload(**kwargs)
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            return await async_send_command(
                GUIDE_TRACKING_UPDATE_COMMAND,
                payload,
                timeout=self.timeout_sec,
            )

        return await asyncio.to_thread(
            self.command_client.send_command,
            GUIDE_TRACKING_UPDATE_COMMAND,
            payload,
            timeout=self.timeout_sec,
        )

    @classmethod
    def build_payload(
        cls,
        *,
        pinky_id,
        task_id,
        target_track_id,
        tracking_status,
        tracking_result_seq,
        frame_ts=None,
        frame_ts_sec=None,
        frame_ts_nanosec=None,
        bbox_valid=False,
        bbox_xyxy=None,
        image_width_px=0,
        image_height_px=0,
    ):
        normalized_frame_ts_sec, normalized_frame_ts_nanosec = cls._normalize_frame_ts(
            frame_ts=frame_ts,
            frame_ts_sec=frame_ts_sec,
            frame_ts_nanosec=frame_ts_nanosec,
        )
        normalized_bbox_valid = bool(bbox_valid)
        normalized_bbox = (
            cls._normalize_bbox(bbox_xyxy)
            if normalized_bbox_valid
            else [0, 0, 0, 0]
        )
        return {
            "pinky_id": str(pinky_id or "").strip(),
            "task_id": str(task_id or "").strip(),
            "target_track_id": str(target_track_id or "").strip(),
            "tracking_status": str(tracking_status or "").strip().upper(),
            "tracking_result_seq": cls._normalize_u32(
                tracking_result_seq,
                field_name="tracking_result_seq",
            ),
            "frame_ts_sec": cls._normalize_u32(
                normalized_frame_ts_sec,
                field_name="frame_ts_sec",
            ),
            "frame_ts_nanosec": cls._normalize_u32(
                normalized_frame_ts_nanosec,
                field_name="frame_ts_nanosec",
            ),
            "bbox_valid": normalized_bbox_valid,
            "bbox_xyxy": normalized_bbox,
            "image_width_px": cls._normalize_u32(
                image_width_px,
                field_name="image_width_px",
            ),
            "image_height_px": cls._normalize_u32(
                image_height_px,
                field_name="image_height_px",
            ),
        }

    @classmethod
    def _normalize_frame_ts(cls, *, frame_ts, frame_ts_sec, frame_ts_nanosec):
        if frame_ts_sec is not None:
            return frame_ts_sec, frame_ts_nanosec or 0

        raw = str(frame_ts or "").strip()
        if not raw:
            return 0, 0

        normalized_raw = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized_raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        parsed = parsed.astimezone(UTC)
        return int(parsed.timestamp()), int(parsed.microsecond) * 1000

    @classmethod
    def _normalize_bbox(cls, bbox_xyxy):
        if not isinstance(bbox_xyxy, (list, tuple)) or len(bbox_xyxy) != 4:
            raise ValueError("bbox_xyxy must be int[4].")
        return [cls._normalize_i32(value, field_name="bbox_xyxy") for value in bbox_xyxy]

    @staticmethod
    def _normalize_u32(value, *, field_name):
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be u32.") from exc

        if normalized < 0 or normalized > 0xFFFFFFFF:
            raise ValueError(f"{field_name} is out of u32 range.")
        return normalized

    @staticmethod
    def _normalize_i32(value, *, field_name):
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be i32.") from exc

        if normalized < -0x80000000 or normalized > 0x7FFFFFFF:
            raise ValueError(f"{field_name} is out of i32 range.")
        return normalized


__all__ = [
    "GUIDE_TRACKING_UPDATE_COMMAND",
    "GuideTrackingUpdatePublisherService",
]
