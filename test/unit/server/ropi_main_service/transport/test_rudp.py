import pytest

from server.ropi_main_service.transport.rudp import (
    HEADER_SIZE,
    PACKET_TYPE_FRAME_CHUNK,
    RudpFrameAssembler,
    RudpPacket,
    RudpProtocolError,
    decode_datagram,
    encode_packet,
    split_frame,
)


def test_rudp_packet_round_trip_uses_if_com_008_header_layout():
    packet = RudpPacket(
        packet_type=PACKET_TYPE_FRAME_CHUNK,
        stream_name="pinky3_front_patrol",
        session_id=42,
        frame_id=1842,
        ts_us=1776554205100000,
        chunk_idx=0,
        chunk_count=2,
        frame_len=9,
        crc32=0x7A31BC9D,
        payload=b"abc",
    )

    encoded = encode_packet(packet)
    decoded = decode_datagram(encoded)

    assert HEADER_SIZE == 60
    assert encoded[:4] == b"RUDP"
    assert decoded == packet


def test_rudp_rejects_stream_name_over_24_bytes():
    packet = RudpPacket(
        stream_name="pinky3_front_patrol_extra_long",
        session_id=1,
        frame_id=1,
        ts_us=1,
        chunk_idx=0,
        chunk_count=1,
        frame_len=1,
        crc32=0,
        payload=b"x",
    )

    with pytest.raises(RudpProtocolError, match="stream_name"):
        encode_packet(packet)


def test_split_frame_chunks_and_reassembles_out_of_order():
    jpeg = b"fake-jpeg-frame-bytes"
    datagrams = split_frame(
        jpeg,
        stream_name="pinky3_cam_patrol",
        session_id=7,
        frame_id=11,
        ts_us=123456,
        packet_size=HEADER_SIZE + 5,
    )
    assembler = RudpFrameAssembler(assembly_timeout_sec=0.7)
    completed = []

    for datagram in reversed(datagrams):
        result = assembler.accept_datagram(datagram, now_monotonic=10.0)
        if result.frame is not None:
            completed.append(result.frame)

    assert len(datagrams) > 1
    assert len(completed) == 1
    frame = completed[0]
    assert frame.stream_name == "pinky3_cam_patrol"
    assert frame.session_id == 7
    assert frame.frame_id == 11
    assert frame.ts_us == 123456
    assert frame.payload == jpeg


def test_assembler_discards_crc_mismatch_and_stale_frames():
    jpeg = b"frame-for-crc-check"
    datagrams = split_frame(
        jpeg,
        stream_name="pinky3_cam_patrol",
        session_id=1,
        frame_id=3,
        ts_us=123,
        packet_size=HEADER_SIZE + 8,
    )
    corrupted = bytearray(datagrams[-1])
    corrupted[-1] ^= 0xFF
    assembler = RudpFrameAssembler()

    results = [
        assembler.accept_datagram(datagram, now_monotonic=1.0)
        for datagram in datagrams[:-1]
    ]
    results.append(assembler.accept_datagram(bytes(corrupted), now_monotonic=1.0))

    assert results[-1].drop_reason == "CRC_MISMATCH"

    completed = None
    for datagram in datagrams:
        result = assembler.accept_datagram(datagram, now_monotonic=2.0)
        completed = result.frame or completed
    assert completed is not None

    stale = assembler.accept_datagram(datagrams[0], now_monotonic=2.1)
    assert stale.drop_reason == "STALE_FRAME"


def test_assembler_discards_incomplete_frames_after_timeout():
    datagrams = split_frame(
        b"incomplete-frame",
        stream_name="pinky3_cam_patrol",
        session_id=1,
        frame_id=9,
        ts_us=123,
        packet_size=HEADER_SIZE + 4,
    )
    assembler = RudpFrameAssembler(assembly_timeout_sec=0.5)

    assembler.accept_datagram(datagrams[0], now_monotonic=1.0)

    assert assembler.discard_timeouts(now_monotonic=1.6) == 1
