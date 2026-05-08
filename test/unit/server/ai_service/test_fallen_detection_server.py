import importlib
import sys
import types
from base64 import b64encode

import pytest

from server.ropi_main_service.transport.tcp_protocol import (
    build_frame,
    decode_frame_bytes,
    encode_frame,
)


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


def test_build_positive_result_creates_queryable_evidence_after_threshold(
    fallen_detection_module,
    monkeypatch,
):
    class FakeAnnotatedFrame:
        shape = (480, 640, 3)

    class FakeEncodedImage:
        def tobytes(self):
            return b"jpeg-bytes"

    server = object.__new__(fallen_detection_module.FallenDetectionServer)
    server.result_seq = 0
    server.fall_streak_start_monotonic = {}
    frame_meta = {
        "stream_name": "pinky03_cam",
        "session_id": 1,
        "frame_id": 541,
        "ts_us": 1_776_554_096_000_000,
    }
    detections = [
        {"class_name": "fall", "confidence": 0.95, "bbox_xyxy": [10, 20, 120, 180]}
    ]
    monkeypatch.setattr(
        fallen_detection_module.cv2,
        "imencode",
        lambda ext, frame: (True, FakeEncodedImage()),
        raising=False,
    )

    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 10.0)
    first = server.build_positive_result(
        frame_meta,
        confidence=0.94,
        annotated_frame=FakeAnnotatedFrame(),
        detections=detections,
    )

    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 11.1)
    second = server.build_positive_result(
        frame_meta,
        confidence=0.95,
        annotated_frame=FakeAnnotatedFrame(),
        detections=detections,
    )

    assert first["alert_candidate"] is False
    assert first["evidence_image_id"] is None
    assert first["evidence_image_available"] is False
    assert second["alert_candidate"] is True
    assert second["evidence_image_id"] == "fall_evidence_pinky3_2"
    assert second["evidence_image_available"] is True

    response = server.query_evidence_image_payload(
        {
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": second["evidence_image_id"],
            "result_seq": second["result_seq"],
            "pinky_id": "pinky3",
        }
    )

    assert response["result_code"] == "OK"
    assert response["evidence_image_id"] == "fall_evidence_pinky3_2"
    assert response["result_seq"] == second["result_seq"]
    assert response["frame_id"] == "541"
    assert response["frame_ts"] == second["frame_ts"]
    assert response["image_format"] == "jpeg"
    assert response["image_encoding"] == "base64"
    assert response["image_data"] == b64encode(b"jpeg-bytes").decode("ascii")
    assert response["image_width_px"] == 640
    assert response["image_height_px"] == 480
    assert response["detections"] == detections

    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 11.2)
    third = server.build_positive_result(
        frame_meta,
        confidence=0.96,
        annotated_frame=FakeAnnotatedFrame(),
        detections=detections,
    )

    assert third["alert_candidate"] is False
    assert third["evidence_image_id"] is None
    assert third["evidence_image_available"] is False


def test_subscribe_socket_dispatches_fall_evidence_query_on_same_tcp_port(
    fallen_detection_module,
    monkeypatch,
):
    class FakeAnnotatedFrame:
        shape = (480, 640, 3)

    class FakeEncodedImage:
        def tobytes(self):
            return b"jpeg-bytes"

    class FakeSocket:
        def __init__(self, inbound):
            self.inbound = bytearray(inbound)
            self.sent = []
            self.closed = False

        def recv(self, size):
            chunk = bytes(self.inbound[:size])
            del self.inbound[:size]
            return chunk

        def sendall(self, data):
            self.sent.append(data)

        def close(self):
            self.closed = True

    server = object.__new__(fallen_detection_module.FallenDetectionServer)
    server.result_seq = 0
    server.fall_streak_start_monotonic = {}
    frame_meta = {
        "stream_name": "pinky03_cam",
        "session_id": 1,
        "frame_id": 541,
        "ts_us": 1_776_554_096_000_000,
    }
    monkeypatch.setattr(
        fallen_detection_module.cv2,
        "imencode",
        lambda ext, frame: (True, FakeEncodedImage()),
        raising=False,
    )
    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 10.0)
    server.build_positive_result(
        frame_meta,
        confidence=0.94,
        annotated_frame=FakeAnnotatedFrame(),
    )
    monkeypatch.setattr(fallen_detection_module.time, "monotonic", lambda: 11.1)
    result = server.build_positive_result(
        frame_meta,
        confidence=0.95,
        annotated_frame=FakeAnnotatedFrame(),
    )
    request = build_frame(
        fallen_detection_module.MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
        7,
        {
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": result["evidence_image_id"],
            "result_seq": result["result_seq"],
            "pinky_id": "pinky3",
        },
    )
    sock = FakeSocket(encode_frame(request))

    server.handle_subscribe_session(sock)

    response = decode_frame_bytes(sock.sent[0])

    assert sock.closed is True
    assert response.is_response is True
    assert response.message_code == fallen_detection_module.MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY
    assert response.sequence_no == 7
    assert response.payload["result_code"] == "OK"
    assert response.payload["evidence_image_id"] == result["evidence_image_id"]
