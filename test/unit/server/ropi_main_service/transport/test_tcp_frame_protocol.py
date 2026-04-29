from server.ropi_main_service.transport.tcp_protocol import (
    MAGIC,
    VERSION,
    MESSAGE_CODE_DELIVERY_CREATE_TASK,
    MESSAGE_CODE_PATROL_CREATE_TASK,
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
