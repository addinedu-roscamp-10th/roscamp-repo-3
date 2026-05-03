import asyncio
import inspect
import logging
import os
from contextlib import suppress
from dataclasses import dataclass

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
    TCPFrame,
    TCPFrameError,
    encode_frame,
    read_frame_from_stream,
)


DEFAULT_CONSUMER_ID = "control_service_ai_guide"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6000
DEFAULT_CONNECT_TIMEOUT_SEC = 3.0
DEFAULT_RECONNECT_DELAY_SEC = 1.0
VALID_TRACKING_STATUSES = {"ACQUIRING", "TRACKING", "LOST"}

logger = logging.getLogger(__name__)


class GuideTrackingStreamError(RuntimeError):
    """Raised when IF-GUI-005 subscribe or push processing fails."""


@dataclass(frozen=True)
class GuideTrackingStreamConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    consumer_id: str = DEFAULT_CONSUMER_ID
    pinky_id: str | None = None
    tracking_mode: str | None = None
    expected_track_id: str | None = None
    last_seq: int = 0
    connect_timeout_sec: float = DEFAULT_CONNECT_TIMEOUT_SEC
    reconnect_delay_sec: float = DEFAULT_RECONNECT_DELAY_SEC


class GuideTrackingStreamClient:
    def __init__(
        self,
        *,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        consumer_id=DEFAULT_CONSUMER_ID,
        pinky_id=None,
        tracking_mode=None,
        expected_track_id=None,
        last_seq=0,
        connect_timeout_sec=DEFAULT_CONNECT_TIMEOUT_SEC,
        reconnect_delay_sec=DEFAULT_RECONNECT_DELAY_SEC,
        sequence_no_start=1,
    ):
        self.host = str(host or DEFAULT_HOST).strip() or DEFAULT_HOST
        self.port = int(port)
        self.consumer_id = str(consumer_id or "").strip()
        self.pinky_id = self._optional_text(pinky_id)
        self.tracking_mode = self._optional_text(tracking_mode)
        self.expected_track_id = self._optional_text(expected_track_id)
        self.last_seq = self._normalize_u32(last_seq, field_name="last_seq")
        self.connect_timeout_sec = float(connect_timeout_sec)
        self.reconnect_delay_sec = float(reconnect_delay_sec)
        self._next_sequence_no = int(sequence_no_start)

    @classmethod
    def from_env(cls):
        return cls(
            host=_first_env_value(
                "AI_GUIDE_TRACKING_STREAM_HOST",
                "AI_SERVER_HOST",
                default=DEFAULT_HOST,
            ),
            port=int(
                os.getenv("AI_GUIDE_TRACKING_STREAM_PORT", str(DEFAULT_PORT))
                or DEFAULT_PORT
            ),
            consumer_id=os.getenv(
                "AI_GUIDE_TRACKING_STREAM_CONSUMER_ID",
                DEFAULT_CONSUMER_ID,
            ),
            pinky_id=os.getenv("AI_GUIDE_TRACKING_STREAM_PINKY_ID") or None,
            tracking_mode=os.getenv("AI_GUIDE_TRACKING_STREAM_MODE") or None,
            expected_track_id=(
                os.getenv("AI_GUIDE_TRACKING_STREAM_EXPECTED_TRACK_ID") or None
            ),
            last_seq=int(os.getenv("AI_GUIDE_TRACKING_STREAM_LAST_SEQ", "0") or "0"),
            connect_timeout_sec=float(
                os.getenv(
                    "AI_GUIDE_TRACKING_STREAM_CONNECT_TIMEOUT_SEC",
                    str(DEFAULT_CONNECT_TIMEOUT_SEC),
                )
                or DEFAULT_CONNECT_TIMEOUT_SEC
            ),
            reconnect_delay_sec=float(
                os.getenv(
                    "AI_GUIDE_TRACKING_STREAM_RECONNECT_DELAY_SEC",
                    str(DEFAULT_RECONNECT_DELAY_SEC),
                )
                or DEFAULT_RECONNECT_DELAY_SEC
            ),
        )

    async def subscribe_and_listen(self, on_results=None, *, max_batches=None):
        logger.info(
            "Connecting to AI guide tracking stream host=%s port=%s consumer_id=%s pinky_id=%s last_seq=%s",
            self.host,
            self.port,
            self.consumer_id,
            self.pinky_id,
            self.last_seq,
        )
        reader, writer = await self._open_connection()
        try:
            ack = await self._send_subscribe_request(reader, writer)
            logger.info(
                "AI guide tracking stream subscribe accepted consumer_id=%s subscribed_pinky_id=%s tracking_mode=%s",
                ack.get("accepted_consumer_id"),
                ack.get("subscribed_pinky_id"),
                ack.get("subscribed_tracking_mode"),
            )
            batch_count = await self._consume_push_batches(
                reader,
                on_results=on_results,
                max_batches=max_batches,
            )
            return {
                "ack": ack,
                "batch_count": batch_count,
                "last_seq": self.last_seq,
            }
        finally:
            writer.close()
            with suppress(OSError, ConnectionError):
                await writer.wait_closed()

    async def run_forever(self, on_results=None, *, stop_event=None):
        while stop_event is None or not stop_event.is_set():
            try:
                await self.subscribe_and_listen(on_results)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if stop_event is not None and stop_event.is_set():
                    break
                logger.warning(
                    "AI guide tracking stream disconnected; reconnecting in %.1fs: %s",
                    self.reconnect_delay_sec,
                    exc,
                )
                await asyncio.sleep(self.reconnect_delay_sec)

    async def _open_connection(self):
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.connect_timeout_sec,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise GuideTrackingStreamError(
                f"AI guide tracking stream connection failed: {exc}"
            ) from exc

    async def _send_subscribe_request(self, reader, writer):
        sequence_no = self._allocate_sequence_no()
        request = TCPFrame(
            message_code=MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE,
            sequence_no=sequence_no,
            payload=self._build_subscribe_payload(),
        )
        writer.write(encode_frame(request))
        await writer.drain()

        try:
            response = await read_frame_from_stream(reader)
        except TCPFrameError as exc:
            raise GuideTrackingStreamError(
                f"IF-GUI-005 subscribe ack read failed: {exc}"
            ) from exc

        return self._parse_subscribe_ack(response, sequence_no=sequence_no)

    def _build_subscribe_payload(self):
        payload = {
            "consumer_id": self.consumer_id,
            "last_seq": self.last_seq,
        }
        if self.pinky_id is not None:
            payload["pinky_id"] = self.pinky_id
        if self.tracking_mode is not None:
            payload["tracking_mode"] = self.tracking_mode
        if self.expected_track_id is not None:
            payload["expected_track_id"] = self.expected_track_id
        return payload

    async def _consume_push_batches(self, reader, *, on_results=None, max_batches=None):
        batch_count = 0
        while max_batches is None or batch_count < int(max_batches):
            try:
                frame = await read_frame_from_stream(reader)
            except TCPFrameError as exc:
                raise GuideTrackingStreamError(
                    f"IF-GUI-005 push frame read failed: {exc}"
                ) from exc

            batch = self._parse_push_batch(frame)
            handler_result = await self._call_result_handler(on_results, batch)
            self.last_seq = max(self.last_seq, int(batch["batch_end_seq"]))
            batch_count += 1
            logger.info(
                "Received AI guide tracking push batch_end_seq=%s result_count=%s handler_result=%s",
                batch["batch_end_seq"],
                len(batch["results"]),
                handler_result,
            )

        return batch_count

    @staticmethod
    def _parse_subscribe_ack(frame, *, sequence_no):
        if frame.message_code != MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE:
            raise GuideTrackingStreamError(
                f"unexpected IF-GUI-005 ack message_code: 0x{frame.message_code:04x}"
            )
        if frame.sequence_no != sequence_no:
            raise GuideTrackingStreamError(
                f"unexpected IF-GUI-005 ack sequence_no: {frame.sequence_no}"
            )
        if not frame.is_response:
            raise GuideTrackingStreamError("IF-GUI-005 subscribe ack must be a response frame.")

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        result_code = str(payload.get("result_code") or "").strip()
        if frame.is_error or result_code != "ACCEPTED":
            result_message = str(payload.get("result_message") or "").strip()
            raise GuideTrackingStreamError(
                f"IF-GUI-005 subscribe rejected: {result_code or 'ERROR'}"
                + (f": {result_message}" if result_message else "")
            )

        return payload

    @classmethod
    def _parse_push_batch(cls, frame):
        if frame.message_code != MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE:
            raise GuideTrackingStreamError(
                f"unexpected IF-GUI-005 push message_code: 0x{frame.message_code:04x}"
            )
        if not frame.is_push:
            raise GuideTrackingStreamError("IF-GUI-005 result frame must be a push frame.")

        payload = frame.payload if isinstance(frame.payload, dict) else {}
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise GuideTrackingStreamError("IF-GUI-005 push payload.results must be a list.")

        results = [cls._normalize_result(item) for item in raw_results]
        result_seq_values = [int(item["result_seq"]) for item in results]
        default_batch_end_seq = max(result_seq_values) if result_seq_values else 0
        batch_end_seq = cls._normalize_u32(
            payload.get("batch_end_seq", default_batch_end_seq),
            field_name="batch_end_seq",
        )
        if result_seq_values and batch_end_seq < max(result_seq_values):
            raise GuideTrackingStreamError(
                "IF-GUI-005 batch_end_seq is smaller than a result_seq."
            )

        return {
            "batch_end_seq": batch_end_seq,
            "results": results,
        }

    @classmethod
    def _normalize_result(cls, item):
        if not isinstance(item, dict):
            raise GuideTrackingStreamError("IF-GUI-005 result item must be an object.")

        normalized = dict(item)
        normalized["result_seq"] = cls._normalize_u32(
            normalized.get("result_seq"),
            field_name="result_seq",
        )
        normalized["pinky_id"] = cls._required_text(
            normalized.get("pinky_id"),
            field_name="pinky_id",
        )
        normalized["frame_ts"] = cls._required_text(
            normalized.get("frame_ts"),
            field_name="frame_ts",
        )
        normalized["tracking_status"] = cls._normalize_tracking_status(
            normalized.get("tracking_status")
        )
        normalized["active_track_id"] = cls._optional_text(
            normalized.get("active_track_id")
        )
        normalized["image_width_px"] = cls._normalize_u32(
            normalized.get("image_width_px"),
            field_name="image_width_px",
        )
        normalized["image_height_px"] = cls._normalize_u32(
            normalized.get("image_height_px"),
            field_name="image_height_px",
        )
        normalized["candidate_tracks"] = cls._normalize_candidate_tracks(
            normalized.get("candidate_tracks", [])
        )
        return normalized

    @classmethod
    def _normalize_candidate_tracks(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise GuideTrackingStreamError(
                "IF-GUI-005 result.candidate_tracks must be a list."
            )
        return [cls._normalize_candidate_track(item) for item in value]

    @classmethod
    def _normalize_candidate_track(cls, item):
        if not isinstance(item, dict):
            raise GuideTrackingStreamError(
                "IF-GUI-005 candidate_tracks item must be an object."
            )
        bbox = item.get("bbox_xyxy")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise GuideTrackingStreamError(
                "IF-GUI-005 candidate_tracks.bbox_xyxy must be int[4]."
            )
        return {
            **item,
            "track_id": cls._required_text(item.get("track_id"), field_name="track_id"),
            "bbox_xyxy": [cls._normalize_i32(value, field_name="bbox_xyxy") for value in bbox],
            "score": float(item.get("score", 0.0)),
        }

    @staticmethod
    async def _call_result_handler(handler, batch):
        if handler is None:
            return None

        result = handler(batch)
        if inspect.isawaitable(result):
            return await result
        return result

    def _allocate_sequence_no(self):
        sequence_no = self._next_sequence_no
        self._next_sequence_no += 1
        return sequence_no

    @staticmethod
    def _optional_text(value):
        normalized = str(value or "").strip()
        return normalized or None

    @classmethod
    def _required_text(cls, value, *, field_name):
        normalized = cls._optional_text(value)
        if normalized is None:
            raise GuideTrackingStreamError(f"IF-GUI-005 result.{field_name} is required.")
        return normalized

    @classmethod
    def _normalize_tracking_status(cls, value):
        normalized = str(value or "").strip().upper()
        if normalized not in VALID_TRACKING_STATUSES:
            raise GuideTrackingStreamError(
                f"IF-GUI-005 result.tracking_status must be one of {sorted(VALID_TRACKING_STATUSES)}."
            )
        return normalized

    @staticmethod
    def _normalize_u32(value, *, field_name):
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise GuideTrackingStreamError(f"IF-GUI-005 {field_name} must be u32.") from exc

        if normalized < 0 or normalized > 0xFFFFFFFF:
            raise GuideTrackingStreamError(f"IF-GUI-005 {field_name} is out of u32 range.")
        return normalized

    @staticmethod
    def _normalize_i32(value, *, field_name):
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise GuideTrackingStreamError(f"IF-GUI-005 {field_name} must be i32.") from exc

        if normalized < -0x80000000 or normalized > 0x7FFFFFFF:
            raise GuideTrackingStreamError(f"IF-GUI-005 {field_name} is out of i32 range.")
        return normalized


def _first_env_value(*names, default):
    for name in names:
        value = os.getenv(name)
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return default


__all__ = [
    "DEFAULT_CONSUMER_ID",
    "GuideTrackingStreamClient",
    "GuideTrackingStreamConfig",
    "GuideTrackingStreamError",
]
