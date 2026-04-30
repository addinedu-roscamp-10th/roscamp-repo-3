from server.ropi_main_service.transport.rudp import (
    HEADER_SIZE,
    RudpFrameAssembler,
    split_frame,
)
from server.ropi_main_service.transport.vision_frame_gateway import (
    VisionFrameGateway,
    VisionFrameGatewayConfig,
)


def test_gateway_reassembles_and_relays_completed_frames_to_ai():
    gateway = VisionFrameGateway(
        VisionFrameGatewayConfig(
            ai_host="127.0.0.1",
            ai_port=5999,
            relay_packet_size=HEADER_SIZE + 6,
            metrics_window_sec=999.0,
        )
    )
    jpeg = b"patrol-frame-for-ai"
    inbound = split_frame(
        jpeg,
        stream_name="pinky3_cam_patrol",
        session_id=77,
        frame_id=31,
        ts_us=123456,
        packet_size=HEADER_SIZE + 5,
    )
    relayed = []

    for datagram in inbound:
        result = gateway.process_datagram(
            datagram,
            addr=("192.168.0.33", 5005),
            now_monotonic=10.0,
        )
        relayed.extend(result.relayed_datagrams)

    ai_assembler = RudpFrameAssembler()
    completed = None
    for datagram in relayed:
        result = ai_assembler.accept_datagram(datagram, now_monotonic=10.1)
        completed = result.frame or completed

    assert completed is not None
    assert completed.payload == jpeg
    assert completed.stream_name == "pinky3_cam_patrol"
    assert completed.session_id == 77
    assert completed.frame_id == 31
    assert completed.ts_us == 123456


def test_gateway_flushes_window_metrics_for_received_relayed_and_dropped_frames():
    gateway = VisionFrameGateway(
        VisionFrameGatewayConfig(
            relay_packet_size=HEADER_SIZE + 32,
            metrics_window_sec=10.0,
        )
    )
    jpeg = b"patrol-frame-for-metrics"
    datagrams = split_frame(
        jpeg,
        stream_name="pinky3_cam_patrol",
        session_id=1,
        frame_id=10,
        ts_us=1_000_000,
        packet_size=HEADER_SIZE + 64,
    )

    gateway.process_datagram(datagrams[0], now_monotonic=100.0)
    gateway.process_datagram(datagrams[0], now_monotonic=100.1)
    snapshots = gateway.flush_metrics(now_monotonic=111.0)

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.stream_name == "pinky3_cam_patrol"
    assert snapshot.robot_id == "pinky3"
    assert snapshot.received_frame_count == 1
    assert snapshot.relayed_frame_count == 1
    assert snapshot.dropped_frame_count == 1
    assert snapshot.latest_frame_id == 10
    assert snapshot.max_latency_ms is not None


def test_gateway_config_from_env_uses_common_ai_server_host(monkeypatch):
    monkeypatch.delenv("VISION_GATEWAY_AI_HOST", raising=False)
    monkeypatch.setenv("AI_SERVER_HOST", "192.168.0.89")

    config = VisionFrameGatewayConfig.from_env()

    assert config.ai_host == "192.168.0.89"


def test_gateway_config_from_env_parses_human_readable_socket_buffers(monkeypatch):
    monkeypatch.setenv("VISION_GATEWAY_RECV_BUFFER", "16MiB")
    monkeypatch.setenv("VISION_GATEWAY_SEND_BUFFER", "8MiB")
    monkeypatch.setenv("VISION_GATEWAY_RECV_BUFFER_BYTES", "1024")
    monkeypatch.setenv("VISION_GATEWAY_SEND_BUFFER_BYTES", "2048")

    config = VisionFrameGatewayConfig.from_env()

    assert config.receive_buffer_bytes == 16 * 1024 * 1024
    assert config.send_buffer_bytes == 8 * 1024 * 1024


def test_gateway_config_from_env_keeps_legacy_socket_buffer_bytes(monkeypatch):
    monkeypatch.delenv("VISION_GATEWAY_RECV_BUFFER", raising=False)
    monkeypatch.delenv("VISION_GATEWAY_SEND_BUFFER", raising=False)
    monkeypatch.setenv("VISION_GATEWAY_RECV_BUFFER_BYTES", "1048576")
    monkeypatch.setenv("VISION_GATEWAY_SEND_BUFFER_BYTES", "2097152")

    config = VisionFrameGatewayConfig.from_env()

    assert config.receive_buffer_bytes == 1 * 1024 * 1024
    assert config.send_buffer_bytes == 2 * 1024 * 1024
