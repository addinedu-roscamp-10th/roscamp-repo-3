import asyncio
import socket

from server.ropi_main_service.transport.rudp import (
    HEADER_SIZE,
    RudpFrameAssembler,
    split_frame,
)
from server.ropi_main_service.transport.vision_frame_gateway import (
    VisionFrameGateway,
    VisionFrameGatewayConfig,
    VisionFrameGatewayProtocol,
)


SERVER_HOST = "127.0.0.1"


class RecordingStreamMetricsRepository:
    def __init__(self):
        self.snapshots = []

    async def async_insert_stream_metrics_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return 1


def test_if_com_008_gateway_relays_robot_udp_frame_to_ai_socket():
    asyncio.run(_run_gateway_relay_check())


async def _run_gateway_relay_check():
    ai_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    robot_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ai_sock.settimeout(2.0)
    ai_sock.bind((SERVER_HOST, 0))
    ai_port = ai_sock.getsockname()[1]

    payload = b"if-com-008-media-gateway-frame" * 12
    stream_name = "pinky3_cam_patrol"
    session_id = 9
    frame_id = 42
    ts_us = 123456789

    config = VisionFrameGatewayConfig(
        listen_host=SERVER_HOST,
        listen_port=0,
        ai_host=SERVER_HOST,
        ai_port=ai_port,
        relay_packet_size=HEADER_SIZE + 17,
        metrics_window_sec=999.0,
    )
    metrics_repository = RecordingStreamMetricsRepository()
    protocol = VisionFrameGatewayProtocol(
        VisionFrameGateway(config),
        ai_addr=(config.ai_host, config.ai_port),
        metrics_repository=metrics_repository,
    )

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: protocol,
        local_addr=(config.listen_host, config.listen_port),
    )
    gateway_addr = transport.get_extra_info("sockname")

    try:
        inbound_datagrams = split_frame(
            payload,
            stream_name=stream_name,
            session_id=session_id,
            frame_id=frame_id,
            ts_us=ts_us,
            packet_size=HEADER_SIZE + 11,
        )
        expected_relay_datagram_count = len(
            split_frame(
                payload,
                stream_name=stream_name,
                session_id=session_id,
                frame_id=frame_id,
                ts_us=ts_us,
                packet_size=config.relay_packet_size,
            )
        )

        for datagram in inbound_datagrams:
            robot_sock.sendto(datagram, gateway_addr)

        completed_frame = await _receive_ai_frame(
            ai_sock,
            expected_datagram_count=expected_relay_datagram_count,
        )
        snapshots = protocol.flush_metrics()
        await protocol.drain_metric_writes()
    finally:
        transport.close()
        ai_sock.close()
        robot_sock.close()

    assert completed_frame is not None
    assert completed_frame.payload == payload
    assert completed_frame.stream_name == stream_name
    assert completed_frame.session_id == session_id
    assert completed_frame.frame_id == frame_id
    assert completed_frame.ts_us == ts_us

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.stream_name == stream_name
    assert snapshot.robot_id == "pinky3"
    assert snapshot.received_frame_count == 1
    assert snapshot.relayed_frame_count == 1
    assert snapshot.dropped_frame_count == 0
    assert snapshot.latest_frame_id == frame_id
    assert metrics_repository.snapshots == snapshots


async def _receive_ai_frame(sock, *, expected_datagram_count):
    assembler = RudpFrameAssembler()
    completed_frame = None

    for _ in range(expected_datagram_count):
        datagram, _ = await asyncio.to_thread(sock.recvfrom, 65535)
        result = assembler.accept_datagram(datagram)
        completed_frame = result.frame or completed_frame

    return completed_frame
