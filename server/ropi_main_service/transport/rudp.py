import math
import struct
import time
import zlib
from dataclasses import dataclass


MAGIC = b"RUDP"
VERSION = 1
PACKET_TYPE_FRAME_CHUNK = 1
HEADER_FORMAT = "!4sBBH24sIIQHHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
DEFAULT_PACKET_SIZE = 1200


class RudpProtocolError(ValueError):
    """Raised when an IF-COM-008 RUDP datagram is invalid."""


@dataclass(frozen=True)
class RudpPacket:
    stream_name: str
    session_id: int
    frame_id: int
    ts_us: int
    chunk_idx: int
    chunk_count: int
    frame_len: int
    crc32: int
    payload: bytes
    packet_type: int = PACKET_TYPE_FRAME_CHUNK


@dataclass(frozen=True)
class RudpFrame:
    stream_name: str
    session_id: int
    frame_id: int
    ts_us: int
    payload: bytes
    crc32: int


@dataclass(frozen=True)
class RudpAssemblyResult:
    packet: RudpPacket | None = None
    frame: RudpFrame | None = None
    drop_reason: str | None = None


@dataclass
class _FrameAssembly:
    stream_name: str
    session_id: int
    frame_id: int
    ts_us: int
    frame_len: int
    crc32: int
    chunk_count: int
    first_seen_monotonic: float
    chunks: dict[int, bytes]


def encode_packet(packet: RudpPacket) -> bytes:
    payload = bytes(packet.payload or b"")
    stream_name = _encode_stream_name(packet.stream_name)
    _validate_u8(packet.packet_type, "packet_type")
    _validate_u32(packet.session_id, "session_id")
    _validate_u32(packet.frame_id, "frame_id")
    _validate_u64(packet.ts_us, "ts_us")
    _validate_u16(packet.chunk_idx, "chunk_idx")
    _validate_u16(packet.chunk_count, "chunk_count")
    _validate_u32(packet.frame_len, "frame_len")
    _validate_u32(packet.crc32, "crc32")
    if int(packet.chunk_count) <= 0:
        raise RudpProtocolError("chunk_count must be greater than 0.")
    if int(packet.chunk_idx) >= int(packet.chunk_count):
        raise RudpProtocolError("chunk_idx must be smaller than chunk_count.")

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        int(packet.packet_type),
        0,
        stream_name,
        int(packet.session_id),
        int(packet.frame_id),
        int(packet.ts_us),
        int(packet.chunk_idx),
        int(packet.chunk_count),
        int(packet.frame_len),
        int(packet.crc32),
    )
    return header + payload


def decode_datagram(datagram: bytes) -> RudpPacket:
    datagram = bytes(datagram or b"")
    if len(datagram) < HEADER_SIZE:
        raise RudpProtocolError("datagram is shorter than RUDP header.")

    (
        magic,
        version,
        packet_type,
        _reserved,
        raw_stream_name,
        session_id,
        frame_id,
        ts_us,
        chunk_idx,
        chunk_count,
        frame_len,
        crc32,
    ) = struct.unpack(HEADER_FORMAT, datagram[:HEADER_SIZE])

    if magic != MAGIC:
        raise RudpProtocolError("invalid RUDP magic.")
    if version != VERSION:
        raise RudpProtocolError(f"unsupported RUDP version: {version}")
    if chunk_count <= 0:
        raise RudpProtocolError("chunk_count must be greater than 0.")
    if chunk_idx >= chunk_count:
        raise RudpProtocolError("chunk_idx must be smaller than chunk_count.")

    return RudpPacket(
        packet_type=packet_type,
        stream_name=_decode_stream_name(raw_stream_name),
        session_id=session_id,
        frame_id=frame_id,
        ts_us=ts_us,
        chunk_idx=chunk_idx,
        chunk_count=chunk_count,
        frame_len=frame_len,
        crc32=crc32,
        payload=datagram[HEADER_SIZE:],
    )


def split_frame(
    frame: bytes,
    *,
    stream_name: str,
    session_id: int,
    frame_id: int,
    ts_us: int | None = None,
    packet_size: int = DEFAULT_PACKET_SIZE,
) -> list[bytes]:
    frame = bytes(frame or b"")
    packet_size = int(packet_size)
    max_payload_size = packet_size - HEADER_SIZE
    if max_payload_size <= 0:
        raise RudpProtocolError("packet_size must be larger than RUDP header.")

    chunk_count = max(1, math.ceil(len(frame) / max_payload_size))
    crc32 = zlib.crc32(frame) & 0xFFFFFFFF
    timestamp_us = int(ts_us if ts_us is not None else time.time_ns() // 1000)
    datagrams = []

    for chunk_idx in range(chunk_count):
        start = chunk_idx * max_payload_size
        payload = frame[start : start + max_payload_size]
        datagrams.append(
            encode_packet(
                RudpPacket(
                    stream_name=stream_name,
                    session_id=session_id,
                    frame_id=frame_id,
                    ts_us=timestamp_us,
                    chunk_idx=chunk_idx,
                    chunk_count=chunk_count,
                    frame_len=len(frame),
                    crc32=crc32,
                    payload=payload,
                )
            )
        )

    return datagrams


class RudpFrameAssembler:
    def __init__(self, *, assembly_timeout_sec: float = 0.7):
        self.assembly_timeout_sec = float(assembly_timeout_sec)
        self._assemblies: dict[tuple[str, int, int], _FrameAssembly] = {}
        self._latest_completed_frame_id: dict[tuple[str, int], int] = {}
        self._stream_sessions: dict[str, int] = {}

    def accept_datagram(
        self,
        datagram: bytes,
        *,
        now_monotonic: float | None = None,
    ) -> RudpAssemblyResult:
        packet = decode_datagram(datagram)
        return self.accept_packet(packet, now_monotonic=now_monotonic)

    def accept_packet(
        self,
        packet: RudpPacket,
        *,
        now_monotonic: float | None = None,
    ) -> RudpAssemblyResult:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        self.discard_timeouts(now_monotonic=now)

        if packet.packet_type != PACKET_TYPE_FRAME_CHUNK:
            return RudpAssemblyResult(packet=packet, drop_reason="UNSUPPORTED_PACKET_TYPE")

        previous_session_id = self._stream_sessions.get(packet.stream_name)
        if previous_session_id is not None and previous_session_id != packet.session_id:
            self._discard_stream(packet.stream_name)
        self._stream_sessions[packet.stream_name] = packet.session_id

        latest_frame_id = self._latest_completed_frame_id.get(
            (packet.stream_name, packet.session_id),
            -1,
        )
        if packet.frame_id <= latest_frame_id:
            return RudpAssemblyResult(packet=packet, drop_reason="STALE_FRAME")

        key = (packet.stream_name, packet.session_id, packet.frame_id)
        assembly = self._assemblies.get(key)
        if assembly is None:
            assembly = _FrameAssembly(
                stream_name=packet.stream_name,
                session_id=packet.session_id,
                frame_id=packet.frame_id,
                ts_us=packet.ts_us,
                frame_len=packet.frame_len,
                crc32=packet.crc32,
                chunk_count=packet.chunk_count,
                first_seen_monotonic=now,
                chunks={},
            )
            self._assemblies[key] = assembly
        elif (
            assembly.frame_len != packet.frame_len
            or assembly.crc32 != packet.crc32
            or assembly.chunk_count != packet.chunk_count
        ):
            self._assemblies.pop(key, None)
            return RudpAssemblyResult(packet=packet, drop_reason="FRAME_METADATA_MISMATCH")

        if packet.chunk_idx in assembly.chunks:
            return RudpAssemblyResult(packet=packet, drop_reason="DUPLICATE_CHUNK")

        assembly.chunks[packet.chunk_idx] = packet.payload
        if len(assembly.chunks) < assembly.chunk_count:
            return RudpAssemblyResult(packet=packet)

        payload = b"".join(
            assembly.chunks[idx]
            for idx in range(assembly.chunk_count)
        )
        self._assemblies.pop(key, None)

        if len(payload) != assembly.frame_len:
            return RudpAssemblyResult(packet=packet, drop_reason="FRAME_LENGTH_MISMATCH")
        if (zlib.crc32(payload) & 0xFFFFFFFF) != assembly.crc32:
            return RudpAssemblyResult(packet=packet, drop_reason="CRC_MISMATCH")

        frame = RudpFrame(
            stream_name=assembly.stream_name,
            session_id=assembly.session_id,
            frame_id=assembly.frame_id,
            ts_us=assembly.ts_us,
            payload=payload,
            crc32=assembly.crc32,
        )
        self._latest_completed_frame_id[
            (assembly.stream_name, assembly.session_id)
        ] = assembly.frame_id
        return RudpAssemblyResult(packet=packet, frame=frame)

    def discard_timeouts(self, *, now_monotonic: float | None = None) -> int:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        expired_keys = [
            key
            for key, assembly in self._assemblies.items()
            if now - assembly.first_seen_monotonic > self.assembly_timeout_sec
        ]
        for key in expired_keys:
            self._assemblies.pop(key, None)
        return len(expired_keys)

    def _discard_stream(self, stream_name: str):
        stale_keys = [
            key for key in self._assemblies
            if key[0] == stream_name
        ]
        for key in stale_keys:
            self._assemblies.pop(key, None)


def _encode_stream_name(stream_name: str) -> bytes:
    encoded = str(stream_name or "").strip().encode("utf-8")
    if not encoded:
        raise RudpProtocolError("stream_name is required.")
    if len(encoded) > 24:
        raise RudpProtocolError("stream_name must be 24 bytes or fewer.")
    return encoded.ljust(24, b"\x00")


def _decode_stream_name(value: bytes) -> str:
    return value.rstrip(b"\x00").decode("utf-8")


def _validate_u8(value, field_name: str):
    normalized = int(value)
    if normalized < 0 or normalized > 0xFF:
        raise RudpProtocolError(f"{field_name} must be u8.")


def _validate_u16(value, field_name: str):
    normalized = int(value)
    if normalized < 0 or normalized > 0xFFFF:
        raise RudpProtocolError(f"{field_name} must be u16.")


def _validate_u32(value, field_name: str):
    normalized = int(value)
    if normalized < 0 or normalized > 0xFFFFFFFF:
        raise RudpProtocolError(f"{field_name} must be u32.")


def _validate_u64(value, field_name: str):
    normalized = int(value)
    if normalized < 0 or normalized > 0xFFFFFFFFFFFFFFFF:
        raise RudpProtocolError(f"{field_name} must be u64.")


__all__ = [
    "DEFAULT_PACKET_SIZE",
    "HEADER_SIZE",
    "MAGIC",
    "PACKET_TYPE_FRAME_CHUNK",
    "RudpAssemblyResult",
    "RudpFrame",
    "RudpFrameAssembler",
    "RudpPacket",
    "RudpProtocolError",
    "decode_datagram",
    "encode_packet",
    "split_frame",
]
