from server.ropi_main_service.transport.tcp_protocol import (
    MAGIC,
    VERSION,
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
    MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
    MESSAGE_CODE_GUIDE_CREATE_TASK,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_CREATE_TASK,
    MESSAGE_CODE_PATROL_RESUME_TASK,
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrame,
    decode_frame_bytes,
    encode_frame,
)


def test_encode_and_decode_preserve_header_fields_and_payload():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_DELIVERY_CREATE_TASK,
        sequence_no=123,
        payload={"request_id": "req_001", "item_id": "1"},
    )

    encoded = encode_frame(frame)
    decoded = decode_frame_bytes(encoded)

    assert decoded.magic == MAGIC
    assert decoded.version == VERSION
    assert decoded.message_code == MESSAGE_CODE_DELIVERY_CREATE_TASK
    assert decoded.sequence_no == 123
    assert decoded.payload == {"request_id": "req_001", "item_id": "1"}
    assert decoded.is_response is False
    assert decoded.is_error is False


def test_task_event_subscribe_message_code_and_push_flag_are_encoded():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
        sequence_no=3,
        payload={"batch_end_seq": 1, "events": []},
        is_push=True,
    )

    decoded = decode_frame_bytes(encode_frame(frame))

    assert decoded.message_code == 0x1003
    assert decoded.is_push is True
    assert decoded.is_response is False


def test_patrol_create_task_message_code_is_if_pat_001():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_PATROL_CREATE_TASK,
        sequence_no=30,
        payload={
            "request_id": "req_patrol_001",
            "caregiver_id": 1,
            "patrol_area_id": "patrol_ward_night_01",
            "priority": "NORMAL",
            "idempotency_key": "idem_patrol_001",
        },
    )

    decoded = decode_frame_bytes(encode_frame(frame))

    assert decoded.message_code == 0x3001
    assert decoded.payload["patrol_area_id"] == "patrol_ward_night_01"


def test_guide_create_task_message_code_is_if_gui_001():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_GUIDE_CREATE_TASK,
        sequence_no=40,
        payload={
            "request_id": "req_guide_001",
            "visitor_id": 1,
            "idempotency_key": "idem_guide_001",
        },
    )

    decoded = decode_frame_bytes(encode_frame(frame))

    assert decoded.message_code == 0x4001
    assert decoded.payload["visitor_id"] == 1


def test_patrol_resume_task_message_code_is_if_pat_002():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_PATROL_RESUME_TASK,
        sequence_no=31,
        payload={
            "task_id": "2001",
            "caregiver_id": 1,
            "member_id": 301,
            "action_memo": "119 신고 후 병원 이송",
        },
    )

    decoded = decode_frame_bytes(encode_frame(frame))

    assert decoded.message_code == 0x3002
    assert decoded.payload["task_id"] == "2001"
    assert decoded.payload["member_id"] == 301
    assert decoded.payload["action_memo"] == "119 신고 후 병원 이송"


def test_fall_inference_result_subscribe_message_code_is_if_pat_005():
    frame = TCPFrame(
        message_code=MESSAGE_CODE_FALL_INFERENCE_RESULT_SUBSCRIBE,
        sequence_no=50,
        payload={
            "consumer_id": "control_service_ai_fall",
            "last_seq": 540,
            "pinky_id": "pinky3",
        },
    )

    decoded = decode_frame_bytes(encode_frame(frame))

    assert decoded.message_code == 0x5001
    assert decoded.payload["consumer_id"] == "control_service_ai_fall"
    assert decoded.payload["last_seq"] == 540
    assert decoded.payload["pinky_id"] == "pinky3"


def test_retired_guide_tracking_result_subscribe_code_is_not_exported():
    from server.ropi_main_service.transport import tcp_protocol

    assert not hasattr(tcp_protocol, "MESSAGE_CODE_GUIDE_TRACKING_RESULT_SUBSCRIBE")
    assert "GUIDE_TRACKING_RESULT_SUBSCRIBE" not in tcp_protocol.LEGACY_MESSAGE_CODES


def test_fall_evidence_query_message_codes_are_defined():
    ui_request = TCPFrame(
        message_code=MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
        sequence_no=60,
        payload={
            "task_id": 2001,
            "alert_id": "17",
            "evidence_image_id": "fall_evidence_pinky3_541",
        },
    )
    ai_request = TCPFrame(
        message_code=MESSAGE_CODE_FALL_EVIDENCE_IMAGE_QUERY,
        sequence_no=61,
        payload={
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": "fall_evidence_pinky3_541",
        },
    )

    assert decode_frame_bytes(encode_frame(ui_request)).message_code == 0x3003
    assert decode_frame_bytes(encode_frame(ai_request)).message_code == 0x5003
