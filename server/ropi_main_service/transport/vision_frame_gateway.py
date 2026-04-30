import argparse
import asyncio
import logging
import os
import re
import signal
import socket
import time
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from dotenv import load_dotenv

from server.ropi_main_service.observability import configure_logging
from server.ropi_main_service.transport.rudp import (
    DEFAULT_PACKET_SIZE,
    RudpFrame,
    RudpFrameAssembler,
    RudpProtocolError,
    decode_datagram,
    split_frame,
)


DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 5005
DEFAULT_AI_HOST = "127.0.0.1"
DEFAULT_AI_PORT = 5006
DEFAULT_ASSEMBLY_TIMEOUT_SEC = 0.7
DEFAULT_METRICS_WINDOW_SEC = 10.0
DEFAULT_DIRECTION = "ROBOT_TO_CONTROL_TO_AI"
DEFAULT_MAX_DATAGRAM_SIZE = 65535
DEFAULT_SOCKET_BUFFER_BYTES = 16 * 1024 * 1024

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SERVER_ROOT = os.path.join(PROJECT_ROOT, "server")

load_dotenv(os.path.join(SERVER_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VisionFrameGatewayConfig:
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    ai_host: str = DEFAULT_AI_HOST
    ai_port: int = DEFAULT_AI_PORT
    assembly_timeout_sec: float = DEFAULT_ASSEMBLY_TIMEOUT_SEC
    relay_packet_size: int = DEFAULT_PACKET_SIZE
    metrics_window_sec: float = DEFAULT_METRICS_WINDOW_SEC
    metrics_flush_interval_sec: float = DEFAULT_METRICS_WINDOW_SEC
    direction: str = DEFAULT_DIRECTION
    max_datagram_size: int = DEFAULT_MAX_DATAGRAM_SIZE
    receive_buffer_bytes: int = DEFAULT_SOCKET_BUFFER_BYTES
    send_buffer_bytes: int = DEFAULT_SOCKET_BUFFER_BYTES

    @classmethod
    def from_env(cls):
        return cls(
            listen_host=_env_text("VISION_GATEWAY_LISTEN_HOST", DEFAULT_LISTEN_HOST),
            listen_port=_env_int("VISION_GATEWAY_LISTEN_PORT", DEFAULT_LISTEN_PORT),
            ai_host=_env_text(
                "VISION_GATEWAY_AI_HOST",
                _env_text("AI_SERVER_HOST", DEFAULT_AI_HOST),
            ),
            ai_port=_env_int("VISION_GATEWAY_AI_PORT", DEFAULT_AI_PORT),
            assembly_timeout_sec=_env_float(
                "VISION_GATEWAY_ASSEMBLY_TIMEOUT_SEC",
                DEFAULT_ASSEMBLY_TIMEOUT_SEC,
            ),
            relay_packet_size=_env_int("VISION_GATEWAY_RELAY_PACKET_SIZE", DEFAULT_PACKET_SIZE),
            metrics_window_sec=_env_float(
                "VISION_GATEWAY_METRICS_WINDOW_SEC",
                DEFAULT_METRICS_WINDOW_SEC,
            ),
            metrics_flush_interval_sec=_env_float(
                "VISION_GATEWAY_METRICS_FLUSH_INTERVAL_SEC",
                DEFAULT_METRICS_WINDOW_SEC,
            ),
            direction=_env_text("VISION_GATEWAY_DIRECTION", DEFAULT_DIRECTION),
            max_datagram_size=_env_int(
                "VISION_GATEWAY_MAX_DATAGRAM_SIZE",
                DEFAULT_MAX_DATAGRAM_SIZE,
            ),
            receive_buffer_bytes=_env_size_bytes(
                "VISION_GATEWAY_RECV_BUFFER",
                "VISION_GATEWAY_RECV_BUFFER_BYTES",
                DEFAULT_SOCKET_BUFFER_BYTES,
            ),
            send_buffer_bytes=_env_size_bytes(
                "VISION_GATEWAY_SEND_BUFFER",
                "VISION_GATEWAY_SEND_BUFFER_BYTES",
                DEFAULT_SOCKET_BUFFER_BYTES,
            ),
        )


@dataclass(frozen=True)
class StreamMetricsSnapshot:
    task_id: int | None
    robot_id: str | None
    stream_name: str
    direction: str
    window_started_at: str
    window_ended_at: str
    received_frame_count: int
    relayed_frame_count: int
    dropped_frame_count: int
    dropped_frame_rate: float
    incomplete_frame_count: int
    crc_mismatch_count: int
    assembly_timeout_count: int
    avg_latency_ms: float | None
    max_latency_ms: float | None
    latest_frame_id: int | None


@dataclass(frozen=True)
class VisionFrameGatewayResult:
    relayed_datagrams: list[bytes]
    metrics_snapshots: list[StreamMetricsSnapshot]


@dataclass
class _StreamMetricsWindow:
    task_id: int | None
    robot_id: str | None
    stream_name: str
    direction: str
    window_started_at: datetime
    window_started_monotonic: float
    received_frame_count: int = 0
    relayed_frame_count: int = 0
    dropped_frame_count: int = 0
    incomplete_frame_count: int = 0
    crc_mismatch_count: int = 0
    assembly_timeout_count: int = 0
    latency_total_ms: float = 0.0
    latency_sample_count: int = 0
    max_latency_ms: float | None = None
    latest_frame_id: int | None = None

    def has_activity(self) -> bool:
        return bool(
            self.received_frame_count
            or self.relayed_frame_count
            or self.dropped_frame_count
            or self.incomplete_frame_count
            or self.crc_mismatch_count
            or self.assembly_timeout_count
        )

    def to_snapshot(self, *, window_ended_at: datetime) -> StreamMetricsSnapshot:
        denominator = self.received_frame_count + self.dropped_frame_count
        dropped_frame_rate = (
            self.dropped_frame_count / denominator
            if denominator > 0
            else 0.0
        )
        avg_latency_ms = (
            self.latency_total_ms / self.latency_sample_count
            if self.latency_sample_count > 0
            else None
        )
        return StreamMetricsSnapshot(
            task_id=self.task_id,
            robot_id=self.robot_id,
            stream_name=self.stream_name,
            direction=self.direction,
            window_started_at=_format_db_datetime(self.window_started_at),
            window_ended_at=_format_db_datetime(window_ended_at),
            received_frame_count=self.received_frame_count,
            relayed_frame_count=self.relayed_frame_count,
            dropped_frame_count=self.dropped_frame_count,
            dropped_frame_rate=dropped_frame_rate,
            incomplete_frame_count=self.incomplete_frame_count,
            crc_mismatch_count=self.crc_mismatch_count,
            assembly_timeout_count=self.assembly_timeout_count,
            avg_latency_ms=avg_latency_ms,
            max_latency_ms=self.max_latency_ms,
            latest_frame_id=self.latest_frame_id,
        )


class VisionFrameGateway:
    def __init__(self, config: VisionFrameGatewayConfig | None = None):
        self.config = config or VisionFrameGatewayConfig()
        self.assembler = RudpFrameAssembler(
            assembly_timeout_sec=self.config.assembly_timeout_sec,
        )
        self._windows: dict[str, _StreamMetricsWindow] = {}

    def process_datagram(
        self,
        datagram: bytes,
        *,
        addr=None,
        now_monotonic: float | None = None,
    ) -> VisionFrameGatewayResult:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        timed_out_count = self.assembler.discard_timeouts(now_monotonic=now)
        if timed_out_count:
            self._record_timeout_drop(timed_out_count, now_monotonic=now)

        try:
            packet = decode_datagram(datagram)
            assembly_result = self.assembler.accept_packet(packet, now_monotonic=now)
        except RudpProtocolError:
            self._record_drop("unknown", "RUDP_PROTOCOL_ERROR", now_monotonic=now)
            return VisionFrameGatewayResult(relayed_datagrams=[], metrics_snapshots=[])

        if assembly_result.drop_reason:
            self._record_drop(
                packet.stream_name,
                assembly_result.drop_reason,
                now_monotonic=now,
            )
            return VisionFrameGatewayResult(relayed_datagrams=[], metrics_snapshots=[])

        if assembly_result.frame is None:
            return VisionFrameGatewayResult(relayed_datagrams=[], metrics_snapshots=[])

        relayed_datagrams = self._relay_frame(assembly_result.frame, now_monotonic=now)
        snapshots = self._flush_expired_windows(now_monotonic=now)
        return VisionFrameGatewayResult(
            relayed_datagrams=relayed_datagrams,
            metrics_snapshots=snapshots,
        )

    def flush_metrics(
        self,
        *,
        now_monotonic: float | None = None,
    ) -> list[StreamMetricsSnapshot]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        return self._flush_windows(now_monotonic=now, force=True)

    def _relay_frame(
        self,
        frame: RudpFrame,
        *,
        now_monotonic: float,
    ) -> list[bytes]:
        relayed_datagrams = split_frame(
            frame.payload,
            stream_name=frame.stream_name,
            session_id=frame.session_id,
            frame_id=frame.frame_id,
            ts_us=frame.ts_us,
            packet_size=self.config.relay_packet_size,
        )
        window = self._get_window(frame.stream_name, now_monotonic=now_monotonic)
        window.received_frame_count += 1
        window.relayed_frame_count += 1
        window.latest_frame_id = frame.frame_id
        latency_ms = _latency_ms_from_frame_ts(frame.ts_us)
        if latency_ms is not None:
            window.latency_total_ms += latency_ms
            window.latency_sample_count += 1
            if window.max_latency_ms is None or latency_ms > window.max_latency_ms:
                window.max_latency_ms = latency_ms
        return relayed_datagrams

    def _record_drop(
        self,
        stream_name: str,
        reason: str,
        *,
        now_monotonic: float,
    ):
        window = self._get_window(stream_name, now_monotonic=now_monotonic)
        window.dropped_frame_count += 1
        if reason == "CRC_MISMATCH":
            window.crc_mismatch_count += 1
        if reason in {
            "CRC_MISMATCH",
            "FRAME_LENGTH_MISMATCH",
            "FRAME_METADATA_MISMATCH",
            "RUDP_PROTOCOL_ERROR",
        }:
            window.incomplete_frame_count += 1

    def _record_timeout_drop(self, count: int, *, now_monotonic: float):
        window = self._get_window("unknown", now_monotonic=now_monotonic)
        window.dropped_frame_count += count
        window.incomplete_frame_count += count
        window.assembly_timeout_count += count

    def _flush_expired_windows(self, *, now_monotonic: float) -> list[StreamMetricsSnapshot]:
        return self._flush_windows(now_monotonic=now_monotonic, force=False)

    def _flush_windows(
        self,
        *,
        now_monotonic: float,
        force: bool,
    ) -> list[StreamMetricsSnapshot]:
        snapshots = []
        expired_stream_names = []
        window_ended_at = _utc_now()

        for stream_name, window in self._windows.items():
            window_age = now_monotonic - window.window_started_monotonic
            if not force and window_age < self.config.metrics_window_sec:
                continue
            if not window.has_activity():
                expired_stream_names.append(stream_name)
                continue
            snapshots.append(window.to_snapshot(window_ended_at=window_ended_at))
            expired_stream_names.append(stream_name)

        for stream_name in expired_stream_names:
            self._windows.pop(stream_name, None)

        return snapshots

    def _get_window(
        self,
        stream_name: str,
        *,
        now_monotonic: float,
    ) -> _StreamMetricsWindow:
        normalized_stream_name = str(stream_name or "unknown").strip() or "unknown"
        window = self._windows.get(normalized_stream_name)
        if window is not None:
            return window

        window = _StreamMetricsWindow(
            task_id=None,
            robot_id=_infer_robot_id(normalized_stream_name),
            stream_name=normalized_stream_name,
            direction=self.config.direction,
            window_started_at=_utc_now(),
            window_started_monotonic=now_monotonic,
        )
        self._windows[normalized_stream_name] = window
        return window


class VisionFrameGatewayProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        gateway: VisionFrameGateway,
        *,
        ai_addr: tuple[str, int],
        metrics_repository=None,
    ):
        self.gateway = gateway
        self.ai_addr = ai_addr
        self.metrics_repository = metrics_repository
        self.transport = None
        self._metric_tasks = set()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        result = self.gateway.process_datagram(data, addr=addr)
        if self.transport is not None:
            for datagram in result.relayed_datagrams:
                self.transport.sendto(datagram, self.ai_addr)
        self._persist_snapshots(result.metrics_snapshots)

    def error_received(self, exc):
        logger.warning("Vision frame UDP gateway error: %s", exc)

    def flush_metrics(self) -> list[StreamMetricsSnapshot]:
        snapshots = self.gateway.flush_metrics()
        self._persist_snapshots(snapshots)
        return snapshots

    async def async_flush_metrics(self) -> list[StreamMetricsSnapshot]:
        snapshots = self.gateway.flush_metrics()
        if self.metrics_repository is None or not snapshots:
            return snapshots

        insert_many = getattr(
            self.metrics_repository,
            "async_insert_stream_metrics_snapshots",
            None,
        )
        if insert_many is not None:
            await insert_many(snapshots)
            return snapshots

        for snapshot in snapshots:
            await self.metrics_repository.async_insert_stream_metrics_snapshot(snapshot)
        return snapshots

    async def drain_metric_writes(self):
        if not self._metric_tasks:
            return
        await asyncio.gather(*list(self._metric_tasks), return_exceptions=True)

    def _persist_snapshots(self, snapshots):
        if self.metrics_repository is None:
            return
        for snapshot in snapshots:
            task = asyncio.create_task(
                self.metrics_repository.async_insert_stream_metrics_snapshot(snapshot)
            )
            self._metric_tasks.add(task)
            task.add_done_callback(self._on_metric_write_done)

    def _on_metric_write_done(self, task: asyncio.Task):
        self._metric_tasks.discard(task)
        _log_metric_write_error(task)


async def run_gateway(
    config: VisionFrameGatewayConfig | None = None,
    *,
    metrics_repository=None,
):
    config = config or VisionFrameGatewayConfig.from_env()
    if metrics_repository is None:
        from server.ropi_main_service.persistence.repositories.stream_metrics_log_repository import (
            StreamMetricsLogRepository,
        )

        metrics_repository = StreamMetricsLogRepository()

    gateway = VisionFrameGateway(config)
    protocol = VisionFrameGatewayProtocol(
        gateway,
        ai_addr=(config.ai_host, config.ai_port),
        metrics_repository=metrics_repository,
    )
    loop = asyncio.get_running_loop()
    sock = _open_udp_socket(config)
    transport, _ = await loop.create_datagram_endpoint(
        lambda: protocol,
        sock=sock,
    )
    shutdown_event = asyncio.Event()

    def _request_shutdown():
        shutdown_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, _request_shutdown)

    flush_task = asyncio.create_task(
        _flush_metrics_until_shutdown(protocol, shutdown_event, config),
    )
    logger.info(
        "ROPI media gateway listening on %s:%s and relaying to %s:%s",
        config.listen_host,
        config.listen_port,
        config.ai_host,
        config.ai_port,
    )

    try:
        await shutdown_event.wait()
    finally:
        flush_task.cancel()
        with suppress(asyncio.CancelledError):
            await flush_task
        await protocol.async_flush_metrics()
        await protocol.drain_metric_writes()
        transport.close()


def parse_args():
    parser = argparse.ArgumentParser(description="ROPI IF-COM-008 UDP media gateway")
    parser.add_argument("--listen-host", default=None)
    parser.add_argument("--listen-port", type=int, default=None)
    parser.add_argument("--ai-host", default=None)
    parser.add_argument("--ai-port", type=int, default=None)
    parser.add_argument("--packet-size", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    config = VisionFrameGatewayConfig.from_env()
    if args.listen_host is not None:
        config = replace(config, listen_host=args.listen_host)
    if args.listen_port is not None:
        config = replace(config, listen_port=args.listen_port)
    if args.ai_host is not None:
        config = replace(config, ai_host=args.ai_host)
    if args.ai_port is not None:
        config = replace(config, ai_port=args.ai_port)
    if args.packet_size is not None:
        config = replace(config, relay_packet_size=args.packet_size)

    configure_logging()
    asyncio.run(run_gateway(config))


async def _flush_metrics_until_shutdown(
    protocol: VisionFrameGatewayProtocol,
    shutdown_event: asyncio.Event,
    config: VisionFrameGatewayConfig,
):
    interval = max(0.1, float(config.metrics_flush_interval_sec))
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            protocol.flush_metrics()


def _log_metric_write_error(task: asyncio.Task):
    with suppress(asyncio.CancelledError):
        exc = task.exception()
        if exc is not None:
            logger.warning("Failed to persist stream metrics snapshot: %s", exc)


def _env_text(name: str, default: str) -> str:
    value = str(os.getenv(name, default)).strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, str(default))).strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number.") from exc


def _env_size_bytes(name: str, legacy_name: str, default: int) -> int:
    raw = _env_optional_text(name)
    field_name = name
    if raw is None:
        raw = _env_optional_text(legacy_name)
        field_name = legacy_name
    if raw is None:
        return default
    return _parse_size_bytes(raw, field_name=field_name)


def _parse_size_bytes(raw: str, *, field_name: str) -> int:
    normalized = str(raw or "").strip()
    if not normalized:
        raise RuntimeError(f"{field_name} must not be empty.")

    if normalized.isdigit():
        return int(normalized)

    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)", normalized)
    if match is None:
        raise RuntimeError(
            f"{field_name} must be bytes or a size like 16MiB, 8MB, or 64KiB."
        )

    value = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1000,
        "mb": 1000 * 1000,
        "gb": 1000 * 1000 * 1000,
        "kib": 1024,
        "mib": 1024 * 1024,
        "gib": 1024 * 1024 * 1024,
    }
    multiplier = multipliers.get(unit)
    if multiplier is None:
        raise RuntimeError(
            f"{field_name} unit must be one of B, KB, MB, GB, KiB, MiB, GiB."
        )
    return int(value * multiplier)


def _env_optional_text(name: str) -> str | None:
    value = os.getenv(name)
    normalized = str(value or "").strip()
    return normalized or None


def _open_udp_socket(config: VisionFrameGatewayConfig):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if config.receive_buffer_bytes > 0:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVBUF,
            int(config.receive_buffer_bytes),
        )
    if config.send_buffer_bytes > 0:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            int(config.send_buffer_bytes),
        )

    sock.bind((config.listen_host, config.listen_port))
    actual_receive_buffer = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    actual_send_buffer = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
    logger.info(
        "Vision gateway UDP socket bound on %s:%s with rcvbuf=%s sndbuf=%s",
        config.listen_host,
        config.listen_port,
        actual_receive_buffer,
        actual_send_buffer,
    )
    return sock


def _latency_ms_from_frame_ts(ts_us: int) -> float | None:
    try:
        timestamp_us = int(ts_us)
    except (TypeError, ValueError):
        return None
    if timestamp_us <= 0:
        return None
    return max(0.0, ((time.time_ns() // 1000) - timestamp_us) / 1000.0)


def _infer_robot_id(stream_name: str) -> str | None:
    normalized = str(stream_name or "").strip()
    if not normalized or normalized == "unknown":
        return None
    return normalized.split("_", 1)[0] or None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _format_db_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


__all__ = [
    "StreamMetricsSnapshot",
    "VisionFrameGateway",
    "VisionFrameGatewayConfig",
    "VisionFrameGatewayProtocol",
    "VisionFrameGatewayResult",
    "main",
    "run_gateway",
]


if __name__ == "__main__":
    main()
