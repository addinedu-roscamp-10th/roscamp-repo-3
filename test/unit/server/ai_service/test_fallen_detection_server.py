import importlib
import sys
import types

import pytest

from server.ropi_main_service.transport.tcp_protocol import decode_frame_bytes


@pytest.fixture
def fallen_detection_module(monkeypatch):
    module_name = "server.ai_service.fallen_detection_server"
    old_module = sys.modules.pop(module_name, None)
    monkeypatch.setitem(sys.modules, "cv2", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        types.SimpleNamespace(YOLO=lambda *args, **kwargs: object()),
    )
    module = importlib.import_module(module_name)

    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if old_module is not None:
            sys.modules[module_name] = old_module


def test_stream_name_to_pinky_id_normalizes_phase1_pinky3(fallen_detection_module):
    server = object.__new__(fallen_detection_module.FallenDetectionServer)

    assert server.stream_name_to_pinky_id("pinky03_cam") == "pinky3"
    assert server.stream_name_to_pinky_id("pinky3_cam") == "pinky3"
    assert server.stream_name_to_pinky_id("pinky10_cam") == "pinky10"


def test_send_result_push_keeps_pinky_id_for_control_demux(fallen_detection_module):
    sent = []
    sock = types.SimpleNamespace(sendall=lambda data: sent.append(data))
    subscriber = fallen_detection_module.FallResultSubscriber(
        sock=sock,
        consumer_id="control_service_ai_fall",
        pinky_id=None,
    )
    server = object.__new__(fallen_detection_module.FallenDetectionServer)

    server.send_result_push(
        subscriber,
        [
            {
                "result_seq": 541,
                "pinky_id": "pinky3",
                "frame_id": "pinky3_cam:1:541",
                "frame_ts": "2026-04-29T12:34:56Z",
                "fall_detected": True,
                "confidence": 0.94,
                "fall_streak_ms": 1032,
                "alert_candidate": True,
            }
        ],
    )

    frame = decode_frame_bytes(sent[0])

    assert frame.is_push is True
    assert frame.payload["results"][0]["pinky_id"] == "pinky3"


def test_build_positive_result_marks_alert_candidate_after_threshold(
    fallen_detection_module,
    monkeypatch,
):
    server = object.__new__(fallen_detection_module.FallenDetectionServer)
    server.result_seq = 0
    server.fall_streak_start_monotonic = {}
    frame_meta = {
        "stream_name": "pinky03_cam",
        "session_id": 1,
        "frame_id": 541,
        "ts_us": 1_776_554_096_000_000,
    }

    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 10.0)
    first = server.build_positive_result(frame_meta, confidence=0.94)

    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 11.1)
    second = server.build_positive_result(frame_meta, confidence=0.95)

    assert first["pinky_id"] == "pinky3"
    assert first["frame_id"] == "541"
    assert first["alert_candidate"] is False
    assert second["pinky_id"] == "pinky3"
    assert second["alert_candidate"] is True
    assert second["fall_streak_ms"] == 1099
